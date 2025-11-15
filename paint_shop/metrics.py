"""
Система метрик Prometheus для приложения Жевжик
Метрики сохраняются в БД для персистентности после перезапуска
"""
from django.db import models
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Max
from decimal import Decimal
from django.utils import timezone
from collections import defaultdict
import threading

# Глобальные счетчики метрик (в памяти)
_metrics_storage = defaultdict(lambda: {
    'counter': 0,
    'histogram': [],
    'gauge': 0
})
_metrics_lock = threading.Lock()

# Импортируем модель Metric из paint_shop_project
try:
    from paint_shop_project.models import Metric
except ImportError:
    # Fallback если модель еще не создана
    class Metric(models.Model):
        name = models.CharField(max_length=255, db_index=True)
        value = models.FloatField()
        labels = models.JSONField(default=dict, blank=True)
        metric_type = models.CharField(max_length=20, choices=[
            ('counter', 'Counter'),
            ('gauge', 'Gauge'),
            ('histogram', 'Histogram'),
        ], default='counter')
        timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
        
        class Meta:
            db_table = 'metrics'
            indexes = [
                models.Index(fields=['name', 'timestamp']),
            ]
            ordering = ['-timestamp']


def increment_counter(name, value=1, labels=None):
    """Увеличить счетчик метрики"""
    labels = labels or {}
    with _metrics_lock:
        key = f"{name}:{hash(frozenset(labels.items()))}"
        _metrics_storage[key]['counter'] += value
    
    # Сохраняем в БД
    Metric.objects.create(
        name=name,
        value=value,
        labels=labels,
        metric_type='counter'
    )


def set_gauge(name, value, labels=None):
    """Установить значение gauge метрики"""
    labels = labels or {}
    with _metrics_lock:
        key = f"{name}:{hash(frozenset(labels.items()))}"
        _metrics_storage[key]['gauge'] = value
    
    # Сохраняем в БД
    Metric.objects.create(
        name=name,
        value=value,
        labels=labels,
        metric_type='gauge'
    )


def observe_histogram(name, value, labels=None):
    """Наблюдать значение для гистограммы"""
    labels = labels or {}
    with _metrics_lock:
        key = f"{name}:{hash(frozenset(labels.items()))}"
        if 'histogram' not in _metrics_storage[key]:
            _metrics_storage[key]['histogram'] = []
        _metrics_storage[key]['histogram'].append(value)
    
    # Сохраняем в БД
    Metric.objects.create(
        name=name,
        value=value,
        labels=labels,
        metric_type='histogram'
    )


def format_labels(labels):
    """Форматировать метки для Prometheus"""
    if not labels:
        return ""
    # Экранируем специальные символы в значениях меток
    formatted = []
    for k, v in sorted(labels.items()):
        # Преобразуем значение в строку и экранируем кавычки и обратные слэши
        v_str = str(v).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        formatted.append(f'{k}="{v_str}"')
    return "{" + ",".join(formatted) + "}"


def _is_valid_number(value):
    """Проверка, что значение является валидным числом для Prometheus"""
    if value is None:
        return False
    try:
        float_val = float(value)
        # Проверяем на NaN и Infinity
        if str(float_val) in ('nan', 'inf', '-inf', 'NaN', 'Infinity', '-Infinity'):
            return False
        return True
    except (ValueError, TypeError):
        return False


def _format_metric_value(value):
    """Форматирование значения метрики для Prometheus"""
    if not _is_valid_number(value):
        return 0.0
    try:
        float_val = float(value)
        # Prometheus не поддерживает NaN и Infinity
        if str(float_val) in ('nan', 'inf', '-inf', 'NaN', 'Infinity', '-Infinity'):
            return 0.0
        return float_val
    except (ValueError, TypeError):
        return 0.0


def generate_prometheus_metrics():
    """Генерировать метрики в формате Prometheus из БД"""
    import json
    output = []
    
    # Counter метрики (суммируем все значения)
    # Группируем вручную, так как JSONField может некорректно группироваться
    counter_groups = {}
    for metric in Metric.objects.filter(metric_type='counter'):
        name = metric.name
        labels = metric.labels or {}
        # Создаем ключ для группировки
        labels_key = json.dumps(labels, sort_keys=True)
        key = (name, labels_key)
        
        if key not in counter_groups:
            counter_groups[key] = {'name': name, 'labels': labels, 'total': 0}
        counter_groups[key]['total'] += _format_metric_value(metric.value)
    
    for group in counter_groups.values():
        if _is_valid_number(group['total']):
            output.append(f"{group['name']}{format_labels(group['labels'])} {group['total']}")
    
    # Gauge метрики (берем последнее значение)
    gauge_groups = {}
    for metric in Metric.objects.filter(metric_type='gauge').order_by('-timestamp'):
        name = metric.name
        labels = metric.labels or {}
        labels_key = json.dumps(labels, sort_keys=True)
        key = (name, labels_key)
        
        # Берем только самое последнее значение для каждой группы
        if key not in gauge_groups or metric.timestamp > gauge_groups[key]['timestamp']:
            gauge_groups[key] = {
                'name': name,
                'labels': labels,
                'value': metric.value,
                'timestamp': metric.timestamp
            }
    
    for group in gauge_groups.values():
        formatted_value = _format_metric_value(group['value'])
        if _is_valid_number(formatted_value):
            output.append(f"{group['name']}{format_labels(group['labels'])} {formatted_value}")
    
    # Histogram метрики (статистика)
    histogram_groups = {}
    for metric in Metric.objects.filter(metric_type='histogram'):
        name = metric.name
        labels = metric.labels or {}
        labels_key = json.dumps(labels, sort_keys=True)
        key = (name, labels_key)
        
        if key not in histogram_groups:
            histogram_groups[key] = {
                'name': name,
                'labels': labels,
                'values': []
            }
        histogram_groups[key]['values'].append(_format_metric_value(metric.value))
    
    for group in histogram_groups.values():
        values = [v for v in group['values'] if _is_valid_number(v)]
        if values:
            count = len(values)
            sum_val = sum(values)
            avg_val = sum_val / count if count > 0 else 0
            
            output.append(f"{group['name']}_count{format_labels(group['labels'])} {count}")
            output.append(f"{group['name']}_sum{format_labels(group['labels'])} {sum_val}")
            output.append(f"{group['name']}_avg{format_labels(group['labels'])} {avg_val}")
    
    return "\n".join(output) if output else ""


def get_custom_metrics():
    """Получить кастомные метрики приложения"""
    from paint_shop_project.models import User, Order, Cart, Product, OrderItem, Review, Payment
    
    # 1. Количество пользователей (всего, активных и новых сегодня)
    users_total = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    users_today = User.objects.filter(date_joined__date=timezone.now().date()).count()


    
    # 2. Количество заказов (всего и по статусам)
    orders_total = Order.objects.count()
    orders_by_status = Order.objects.values('status').annotate(count=Count('id'))
    orders_today = Order.objects.filter(order_date__date=timezone.now().date()).count()
    
    # 3. Количество товаров в корзине (активных)
    cart_items_total = Cart.objects.count()
    active_carts = Cart.objects.values('user').distinct().count()
    
    # 4. Количество товаров в каталоге
    products_total = Product.objects.filter(is_active=True).count()
    products_with_discount = Product.objects.filter(is_active=True, old_price__isnull=False).count()
    
    # 5. Выручка
    revenue_total = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_today = Order.objects.filter(order_date__date=timezone.now().date()).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # 6. Средний чек
    avg_order_value = Order.objects.aggregate(avg=Avg('total_amount'))['avg'] or 0
    
    # 7. Отзывы
    reviews_total = Review.objects.count()
    reviews_approved = Review.objects.filter(is_approved=True).count()
    avg_rating = Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg'] or 0
    
    # 8. Платежи
    payments_total = Payment.objects.count()
    payments_success = Payment.objects.filter(status='success').count()
    payments_total_amount = Payment.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0
    
    # 9. Товары по категориям
    products_by_category = Product.objects.filter(is_active=True).values('category__name').annotate(count=Count('id'))
    
    # 10. Активные промоакции
    from paint_shop_project.models import Promotion
    active_promotions = Promotion.objects.filter(is_active=True).count()
    
    # Сохраняем кастомные метрики
    set_gauge('zhevzhik_users_total', users_total)
    set_gauge('zhevzhik_users_active', active_users)
    set_gauge('zhevzhik_users_today', users_today)
    set_gauge('zhevzhik_orders_total', orders_total)
    set_gauge('zhevzhik_orders_today', orders_today)
    set_gauge('zhevzhik_cart_items_total', cart_items_total)
    set_gauge('zhevzhik_carts_active', active_carts)
    set_gauge('zhevzhik_products_total', products_total)
    set_gauge('zhevzhik_products_with_discount', products_with_discount)
    set_gauge('zhevzhik_revenue_total', float(revenue_total))
    set_gauge('zhevzhik_revenue_today', float(revenue_today))
    set_gauge('zhevzhik_avg_order_value', float(avg_order_value))
    set_gauge('zhevzhik_reviews_total', reviews_total)
    set_gauge('zhevzhik_reviews_approved', reviews_approved)
    set_gauge('zhevzhik_avg_rating', float(avg_rating))
    set_gauge('zhevzhik_payments_total', payments_total)
    set_gauge('zhevzhik_payments_success', payments_success)
    set_gauge('zhevzhik_payments_amount', float(payments_total_amount))
    set_gauge('zhevzhik_promotions_active', active_promotions)
    
    # Заказы по статусам
    for order_stat in orders_by_status:
        set_gauge('zhevzhik_orders_by_status', order_stat['count'], {
            'status': order_stat['status']
        })
    
    # Товары по категориям
    for cat_stat in products_by_category:
        if cat_stat['category__name']:
            set_gauge('zhevzhik_products_by_category', cat_stat['count'], {
                'category': cat_stat['category__name']
            })
    
    return {
        'users_total': users_total,
        'users_active': active_users,
        'users_today': users_today,
        'orders_total': orders_total,
        'orders_today': orders_today,
        'cart_items_total': cart_items_total,
        'carts_active': active_carts,
        'products_total': products_total,
        'products_with_discount': products_with_discount,
        'revenue_total': float(revenue_total),
        'revenue_today': float(revenue_today),
        'avg_order_value': float(avg_order_value),
        'reviews_total': reviews_total,
        'reviews_approved': reviews_approved,
        'avg_rating': float(avg_rating),
        'payments_total': payments_total,
        'payments_success': payments_success,
        'payments_amount': float(payments_total_amount),
        'promotions_active': active_promotions,
    }

