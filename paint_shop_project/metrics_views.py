"""
View для экспорта метрик Prometheus
Интегрировано с django_prometheus для совместимости
"""
from django.http import HttpResponse
from django.views.decorators.http import require_GET
try:
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    from prometheus_client.core import REGISTRY
    PROMETHEUS_CLIENT_AVAILABLE = True
except ImportError:
    PROMETHEUS_CLIENT_AVAILABLE = False
    from paint_shop.metrics import generate_prometheus_metrics, get_custom_metrics


@require_GET
def prometheus_metrics_view(request):
    """Endpoint для экспорта метрик в формате Prometheus"""
    # Если prometheus_client доступен, используем нативные метрики
    if PROMETHEUS_CLIENT_AVAILABLE:
        # Обновляем бизнес-метрики перед экспортом
        try:
            from paint_shop_project.prometheus_metrics import update_business_metrics
            update_business_metrics()
        except Exception:
            pass
        
        # Генерируем все метрики через prometheus_client
        # Это включает метрики django_prometheus и наши кастомные метрики
        output = generate_latest(REGISTRY)
        
        response = HttpResponse(output, content_type=CONTENT_TYPE_LATEST)
        return response
    else:
        # Fallback на старый метод
        try:
            from paint_shop.metrics import generate_prometheus_metrics
            metrics_output = generate_prometheus_metrics()
        except Exception:
            metrics_output = ""
        
        prometheus_output = """# HELP zhevzhik_users_total Total number of users
# TYPE zhevzhik_users_total gauge

# HELP zhevzhik_users_active Number of active users
# TYPE zhevzhik_users_active gauge

# HELP zhevzhik_users_today Number of users registered today
# TYPE zhevzhik_users_today gauge

# HELP zhevzhik_orders_total Total number of orders
# TYPE zhevzhik_orders_total gauge

# HELP zhevzhik_orders_today Number of orders today
# TYPE zhevzhik_orders_today gauge

# HELP zhevzhik_orders_by_status Number of orders by status
# TYPE zhevzhik_orders_by_status gauge

# HELP zhevzhik_cart_items_total Total number of items in carts
# TYPE zhevzhik_cart_items_total gauge

# HELP zhevzhik_carts_active Number of active carts
# TYPE zhevzhik_carts_active gauge

# HELP zhevzhik_products_total Total number of active products
# TYPE zhevzhik_products_total gauge

# HELP zhevzhik_products_with_discount Number of products with discount
# TYPE zhevzhik_products_with_discount gauge

# HELP zhevzhik_products_by_category Number of products by category
# TYPE zhevzhik_products_by_category gauge

# HELP zhevzhik_revenue_total Total revenue
# TYPE zhevzhik_revenue_total gauge

# HELP zhevzhik_revenue_today Revenue today
# TYPE zhevzhik_revenue_today gauge

# HELP zhevzhik_avg_order_value Average order value
# TYPE zhevzhik_avg_order_value gauge

# HELP zhevzhik_reviews_total Total number of reviews
# TYPE zhevzhik_reviews_total gauge

# HELP zhevzhik_reviews_approved Number of approved reviews
# TYPE zhevzhik_reviews_approved gauge

# HELP zhevzhik_avg_rating Average product rating
# TYPE zhevzhik_avg_rating gauge

# HELP zhevzhik_payments_total Total number of payments
# TYPE zhevzhik_payments_total gauge

# HELP zhevzhik_payments_success Number of successful payments
# TYPE zhevzhik_payments_success gauge

# HELP zhevzhik_payments_amount Total amount of successful payments
# TYPE zhevzhik_payments_amount gauge

# HELP zhevzhik_promotions_active Number of active promotions
# TYPE zhevzhik_promotions_active gauge

"""
        
        if metrics_output:
            prometheus_output += metrics_output
        
        response = HttpResponse(prometheus_output, content_type='text/plain; charset=utf-8')
        return response

