"""
Дашборд для менеджеров склада с метриками по партиям товаров
"""
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q, Sum, Avg, Min
from django.db.models.functions import TruncDay
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..models import ProductBatch, Product, Category, BatchAuditLog, OrderItem

logger = logging.getLogger(__name__)


def is_staff_or_manager(user):
    """Проверка, что пользователь - администратор или менеджер"""
    return user.is_staff or (user.role and user.role.can_manage_store)


@method_decorator(user_passes_test(is_staff_or_manager), name='dispatch')
class WarehouseDashboardView(TemplateView):
    """Дашборд для менеджеров склада с метриками по партиям"""
    template_name = 'admin/warehouse_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        
        # Партии, истекающие через разные периоды
        expiring_3_days = ProductBatch.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=3),
            remaining_quantity__gt=0
        ).count()
        
        expiring_7_days = ProductBatch.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=7),
            remaining_quantity__gt=0
        ).count()
        
        expiring_14_days = ProductBatch.objects.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timedelta(days=14),
            remaining_quantity__gt=0
        ).count()
        
        # Просроченные партии
        expired_batches = ProductBatch.objects.filter(
            expiry_date__lt=today,
            remaining_quantity__gt=0
        )
        expired_count = expired_batches.count()
        expired_quantity = expired_batches.aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        # Партии с низким остатком
        low_stock_batches = ProductBatch.objects.filter(
            remaining_quantity__lte=10,
            remaining_quantity__gt=0
        )
        low_stock_count = low_stock_batches.count()
        low_stock_quantity = low_stock_batches.aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        # Статистика списаний за последние 30 дней
        last_30_days = timezone.now() - timedelta(days=30)
        spoiled_logs = BatchAuditLog.objects.filter(
            action='spoiled',
            created_at__gte=last_30_days
        )
        spoiled_count = spoiled_logs.count()
        spoiled_batches = ProductBatch.objects.filter(
            audit_logs__action='spoiled',
            audit_logs__created_at__gte=last_30_days
        ).distinct()
        
        # Общая стоимость списанного (примерная)
        spoiled_value = 0
        for batch in spoiled_batches:
            spoiled_value += float(batch.product.price) * (batch.audit_logs.filter(
                action='spoiled',
                created_at__gte=last_30_days
            ).first().old_value or 0)
        
        # Топ товаров по скорости продаж (за последние 7 дней)
        last_7_days = timezone.now() - timedelta(days=7)
        top_products = (
            OrderItem.objects.filter(
                order__order_date__gte=last_7_days,
                order__status__in=['delivered', 'ready']
            )
            .values('product__name', 'product__id')
            .annotate(
                total_sold=Sum('quantity'),
                total_revenue=Sum('price_per_unit')
            )
            .order_by('-total_sold')[:10]
        )
        
        # Партии по категориям (для карты тепла)
        batches_by_category = (
            ProductBatch.objects.filter(remaining_quantity__gt=0)
            .values('product__category__name')
            .annotate(
                total_batches=Count('id'),
                expiring_soon=Count('id', filter=Q(
                    expiry_date__gte=today,
                    expiry_date__lte=today + timedelta(days=7)
                )),
                total_quantity=Sum('remaining_quantity')
            )
            .order_by('-expiring_soon')[:10]
        )
        
        # Общая статистика
        total_batches = ProductBatch.objects.filter(remaining_quantity__gt=0).count()
        total_quantity = ProductBatch.objects.filter(remaining_quantity__gt=0).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        
        # Средний процент срока годности
        batches_with_percent = ProductBatch.objects.filter(
            remaining_quantity__gt=0,
            production_date__isnull=False
        )
        avg_percent = 0
        count = 0
        for batch in batches_with_percent[:100]:  # Ограничиваем для производительности
            percent = batch.expiry_percent_remaining
            if percent is not None:
                avg_percent += percent
                count += 1
        avg_percent = avg_percent / count if count > 0 else 0
        
        context.update({
            'title': _('Дашборд склада'),
            'expiring_3_days': expiring_3_days,
            'expiring_7_days': expiring_7_days,
            'expiring_14_days': expiring_14_days,
            'expired_count': expired_count,
            'expired_quantity': expired_quantity,
            'low_stock_count': low_stock_count,
            'low_stock_quantity': low_stock_quantity,
            'spoiled_count': spoiled_count,
            'spoiled_value': round(spoiled_value, 2),
            'top_products': list(top_products),
            'batches_by_category': list(batches_by_category),
            'total_batches': total_batches,
            'total_quantity': total_quantity,
            'avg_percent': round(avg_percent, 1),
        })
        
        return context


@csrf_exempt
@require_http_methods(["GET"])
@user_passes_test(is_staff_or_manager)
def warehouse_dashboard_api(request):
    """API endpoint для динамического обновления данных дашборда"""
    try:
        today = timezone.now().date()
        period = int(request.GET.get('period', 30))  # Дни
        start_date = timezone.now() - timedelta(days=period)
        
        # График списаний по дням
        spoiled_by_day = (
            BatchAuditLog.objects.filter(
                action='spoiled',
                created_at__gte=start_date
            )
            .annotate(day=TruncDay('created_at'))
            .values('day')
            .annotate(count=Count('id'), quantity=Sum('old_value'))
            .order_by('day')
        )
        
        # График партий, истекающих по дням (на ближайшие 30 дней)
        future_30_days = today + timedelta(days=30)
        expiring_by_day = (
            ProductBatch.objects.filter(
                expiry_date__gte=today,
                expiry_date__lte=future_30_days,
                remaining_quantity__gt=0
            )
            .values('expiry_date')
            .annotate(count=Count('id'), quantity=Sum('remaining_quantity'))
            .order_by('expiry_date')
        )
        
        # График остатков по категориям
        category_stock = (
            ProductBatch.objects.filter(remaining_quantity__gt=0)
            .values('product__category__name')
            .annotate(
                total_quantity=Sum('remaining_quantity'),
                batch_count=Count('id')
            )
            .order_by('-total_quantity')[:10]
        )
        
        return JsonResponse({
            'success': True,
            'spoiled_by_day': list(spoiled_by_day),
            'expiring_by_day': list(expiring_by_day),
            'category_stock': list(category_stock),
        })
        
    except Exception as e:
        logger.error(f"Ошибка в warehouse_dashboard_api: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


