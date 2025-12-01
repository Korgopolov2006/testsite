"""
Дашборд аналитики с графиками продаж
"""
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..models import Order, OrderItem, Product, User

logger = logging.getLogger(__name__)


def is_staff(user):
    """Проверка, что пользователь - администратор"""
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class DashboardView(TemplateView):
    """Дашборд с графиками продаж и аналитикой"""
    template_name = 'admin/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        # Общая статистика
        all_orders = Order.objects.all()
        delivered_orders = all_orders.filter(status='delivered')
        
        # Выручка
        total_revenue = delivered_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')
        
        revenue_last_30 = delivered_orders.filter(
            order_date__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        revenue_last_7 = delivered_orders.filter(
            order_date__gte=last_7_days
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        # Заказы
        orders_total = all_orders.count()
        orders_last_30 = all_orders.filter(order_date__gte=last_30_days).count()
        orders_last_7 = all_orders.filter(order_date__gte=last_7_days).count()
        
        # Клиенты
        total_customers = User.objects.filter(is_staff=False).count()
        new_customers_30 = User.objects.filter(
            date_joined__gte=last_30_days,
            is_staff=False
        ).count()
        
        # Средний чек
        avg_order_value = (
            total_revenue / delivered_orders.count()
            if delivered_orders.count() > 0
            else Decimal('0')
        )
        
        # Топ товары
        revenue_expr = ExpressionWrapper(
            F('quantity') * F('price_per_unit'),
            output_field=DecimalField(max_digits=16, decimal_places=2)
        )
        
        top_products = list(
            OrderItem.objects.filter(order__status='delivered')
            .values('product__name', 'product__id')
            .annotate(
                revenue=Sum(revenue_expr),
                quantity=Sum('quantity'),
                orders=Count('order', distinct=True)
            )
            .order_by('-revenue')[:10]
        )
        
        # Статистика по статусам
        orders_by_status = list(
            all_orders.values('status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Данные для графиков (последние 30 дней)
        daily_data = list(
            delivered_orders.filter(order_date__gte=last_30_days)
            .annotate(day=TruncDay('order_date'))
            .values('day')
            .annotate(
                revenue=Sum('total_amount'),
                orders=Count('id')
            )
            .order_by('day')
        )
        
        context.update({
            'title': _('Дашборд аналитики'),
            'total_revenue': total_revenue,
            'revenue_last_30': revenue_last_30,
            'revenue_last_7': revenue_last_7,
            'orders_total': orders_total,
            'orders_last_30': orders_last_30,
            'orders_last_7': orders_last_7,
            'total_customers': total_customers,
            'new_customers_30': new_customers_30,
            'avg_order_value': avg_order_value,
            'top_products': top_products,
            'orders_by_status': orders_by_status,
            'daily_data': daily_data,
        })
        
        return context


@csrf_exempt
@require_http_methods(["GET"])
@user_passes_test(is_staff)
def dashboard_api(request):
    """API endpoint для получения данных для графиков"""
    logger.info("Dashboard API called by user=%s, period=%s", request.user.username, request.GET.get('period'))
    
    period = request.GET.get('period', '30')  # 7, 30, 90, 365
    
    try:
        days = int(period)
        logger.debug("Parsed period days: %d", days)
    except ValueError:
        days = 30
        logger.warning("Invalid period value: %s, using default 30", period)
    
    now = timezone.now()
    start_date = now - timedelta(days=days)
    logger.debug("Query date range: %s to %s", start_date, now)
    
    # Данные по дням
    try:
        daily_data = (
            Order.objects.filter(
                order_date__gte=start_date,
                status='delivered'
            )
            .annotate(day=TruncDay('order_date'))
            .values('day')
            .annotate(
                revenue=Sum('total_amount'),
                orders=Count('id')
            )
            .order_by('day')
        )
        logger.info("Daily data query returned %d items", len(list(daily_data)))
    except Exception as e:
        logger.error("Error querying daily data: %s", e, exc_info=True)
        daily_data = []
    
    # Данные по месяцам (если период > 90 дней)
    monthly_data = []
    if days > 90:
        try:
            monthly_data = (
                Order.objects.filter(
                    order_date__gte=start_date,
                    status='delivered'
                )
                .annotate(month=TruncMonth('order_date'))
                .values('month')
                .annotate(
                    revenue=Sum('total_amount'),
                    orders=Count('id')
                )
                .order_by('month')
            )
            monthly_data = [
                {
                    'month': item['month'].strftime('%Y-%m'),
                    'revenue': float(item['revenue'] or 0),
                    'orders': item['orders']
                }
                for item in monthly_data
            ]
            logger.info("Monthly data processed: %d items", len(monthly_data))
        except Exception as e:
            logger.error("Error processing monthly data: %s", e, exc_info=True)
    
    daily_list = []
    for item in daily_data:
        try:
            day_str = item['day'].strftime('%Y-%m-%d') if hasattr(item['day'], 'strftime') else str(item['day'])
            daily_list.append({
                'day': day_str,
                'revenue': float(item['revenue'] or 0),
                'orders': item['orders'] or 0
            })
        except Exception as e:
            logger.warning("Error processing daily data item: %s, item: %s", e, item)
            continue
    
    logger.info("Returning response: daily=%d items, monthly=%d items", len(daily_list), len(monthly_data))
    
    response_data = {
        'daily': daily_list,
        'monthly': monthly_data,
        'period': days
    }
    
    return JsonResponse(response_data)