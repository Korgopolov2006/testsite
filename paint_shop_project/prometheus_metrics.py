"""
Нативные Prometheus метрики для интеграции с django_prometheus
Использует prometheus_client для создания метрик
Все метрики регистрируются в глобальном REGISTRY, который используется django_prometheus
"""
try:
    from prometheus_client import Gauge, Counter, Histogram
    PROMETHEUS_CLIENT_AVAILABLE = True
except ImportError:
    PROMETHEUS_CLIENT_AVAILABLE = False
    # Создаем заглушки для fallback
    class _DummyMetric:
        def set(self, value): pass
        def inc(self, value=1): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self
        def clear(self): pass

if PROMETHEUS_CLIENT_AVAILABLE:
    # Бизнес-метрики
    users_total = Gauge('zhevzhik_users_total', 'Total number of users')
    users_active = Gauge('zhevzhik_users_active', 'Number of active users')
    users_today = Gauge('zhevzhik_users_today', 'Number of users registered today')
    
    orders_total = Gauge('zhevzhik_orders_total', 'Total number of orders')
    orders_today = Gauge('zhevzhik_orders_today', 'Number of orders today')
    orders_by_status = Gauge('zhevzhik_orders_by_status', 'Number of orders by status', ['status'])
    
    revenue_total = Gauge('zhevzhik_revenue_total', 'Total revenue')
    revenue_today = Gauge('zhevzhik_revenue_today', 'Revenue today')
    avg_order_value = Gauge('zhevzhik_avg_order_value', 'Average order value')
    
    cart_items_total = Gauge('zhevzhik_cart_items_total', 'Total number of items in carts')
    carts_active = Gauge('zhevzhik_carts_active', 'Number of active carts')
    
    products_total = Gauge('zhevzhik_products_total', 'Total number of active products')
    products_with_discount = Gauge('zhevzhik_products_with_discount', 'Number of products with discount')
    products_by_category = Gauge('zhevzhik_products_by_category', 'Number of products by category', ['category'])
    
    reviews_total = Gauge('zhevzhik_reviews_total', 'Total number of reviews')
    reviews_approved = Gauge('zhevzhik_reviews_approved', 'Number of approved reviews')
    avg_rating = Gauge('zhevzhik_avg_rating', 'Average product rating')
    
    payments_total = Gauge('zhevzhik_payments_total', 'Total number of payments')
    payments_success = Gauge('zhevzhik_payments_success', 'Number of successful payments')
    payments_amount = Gauge('zhevzhik_payments_amount', 'Total amount of successful payments')
    
    promotions_active = Gauge('zhevzhik_promotions_active', 'Number of active promotions')
    
    # Партионные метрики (сроки годности и остатки)
    batches_expired_total = Gauge('zhevzhik_batches_expired_total', 'Total number of expired product batches')
    batches_expiring_days = Gauge('zhevzhik_batches_expiring_in_days', 'Batches expiring within N days', ['days'])
    batches_low_stock_total = Gauge('zhevzhik_batches_low_stock_total', 'Total number of batches with low remaining quantity')
    
    # HTTP метрики (используются middleware)
    http_requests_total = Counter('zhevzhik_http_requests_total', 'Total number of HTTP requests', 
                                  ['method', 'status_code', 'path'])
    http_request_duration_seconds = Histogram('zhevzhik_http_request_duration_seconds', 
                                              'HTTP request duration in seconds',
                                              ['method', 'status_code', 'path'])
    http_errors_total = Counter('zhevzhik_http_errors_total', 'Total number of HTTP errors',
                               ['method', 'status_code', 'path'])
    http_exceptions_total = Counter('zhevzhik_http_exceptions_total', 'Total number of HTTP exceptions',
                                    ['method', 'path', 'exception_type'])


def update_business_metrics():
    """Обновить все бизнес-метрики из БД (с кэшированием)"""
    if not PROMETHEUS_CLIENT_AVAILABLE:
        return
    
    # Простое кэширование в памяти (обновление раз в минуту)
    import time
    cache_key = 'prometheus_metrics_cache'
    cache_timeout = 60  # секунд
    
    if not hasattr(update_business_metrics, '_cache'):
        update_business_metrics._cache = {}
    
    cache = update_business_metrics._cache
    now = time.time()
    
    # Проверяем кэш
    if cache_key in cache:
        cached_time, cached_data = cache[cache_key]
        if now - cached_time < cache_timeout:
            # Используем кэшированные значения
            for metric_name, value in cached_data.items():
                if hasattr(update_business_metrics, metric_name):
                    metric = getattr(update_business_metrics, metric_name)
                    if hasattr(metric, 'set'):
                        metric.set(value)
            return
    
    from paint_shop_project.models import User, Order, Cart, Product, Review, Payment, ProductBatch
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    
    metrics_data = {}
    
    try:
        # Пользователи
        users_total.set(User.objects.count())
        users_active.set(User.objects.filter(is_active=True).count())
        users_today.set(User.objects.filter(date_joined__date=timezone.now().date()).count())
        
        # Заказы
        orders_total.set(Order.objects.count())
        orders_today.set(Order.objects.filter(order_date__date=timezone.now().date()).count())
        
        # Заказы по статусам
        orders_by_status.clear()
        for order_stat in Order.objects.values('status').annotate(count=Count('id')):
            orders_by_status.labels(status=order_stat['status']).set(order_stat['count'])
        
        # Выручка
        revenue_total.set(float(Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0))
        revenue_today.set(float(Order.objects.filter(order_date__date=timezone.now().date()).aggregate(total=Sum('total_amount'))['total'] or 0))
        avg_order_value.set(float(Order.objects.aggregate(avg=Avg('total_amount'))['avg'] or 0))
        
        # Корзины
        cart_items_total.set(Cart.objects.count())
        carts_active.set(Cart.objects.values('user').distinct().count())
        
        # Товары
        products_total.set(Product.objects.filter(is_active=True).count())
        products_with_discount.set(Product.objects.filter(is_active=True, old_price__isnull=False).count())
        
        # Товары по категориям
        products_by_category.clear()
        for cat_stat in Product.objects.filter(is_active=True).values('category__name').annotate(count=Count('id')):
            if cat_stat['category__name']:
                products_by_category.labels(category=cat_stat['category__name']).set(cat_stat['count'])
        
        # Отзывы
        reviews_total.set(Review.objects.count())
        reviews_approved.set(Review.objects.filter(is_approved=True).count())
        avg_rating.set(float(Review.objects.filter(is_approved=True).aggregate(avg=Avg('rating'))['avg'] or 0))
        
        # Платежи
        payments_total.set(Payment.objects.count())
        payments_success.set(Payment.objects.filter(status='success').count())
        payments_amount.set(float(Payment.objects.filter(status='success').aggregate(total=Sum('amount'))['total'] or 0))
        
        # Промоакции
        from paint_shop_project.models import Promotion
        promotions_active.set(Promotion.objects.filter(is_active=True).count())
        
        # Партии товаров: просроченные / истекающие / низкий остаток
        today = timezone.now().date()
        expired = ProductBatch.objects.filter(expiry_date__lt=today).count()
        batches_expired_total.set(expired)
        
        # Настраиваемые окна: 3 и 7 дней
        for days in (3, 7):
            until = today + timezone.timedelta(days=days)
            count = ProductBatch.objects.filter(expiry_date__gte=today, expiry_date__lte=until).count()
            batches_expiring_days.labels(days=str(days)).set(count)
        
        # Низкий остаток (порог: <=10 единиц)
        low_stock = ProductBatch.objects.filter(remaining_quantity__lte=10).count()
        batches_low_stock_total.set(low_stock)
        metrics_data['batches_low_stock_total'] = low_stock
        
        # Сохраняем в кэш
        cache[cache_key] = (now, metrics_data)
        
    except Exception:
        # Игнорируем ошибки если БД не готова
        pass

