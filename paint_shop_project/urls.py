from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from .views import CustomPasswordResetView
from django.shortcuts import render
from .views import *
from .metrics_views import prometheus_metrics_view
from .staff_views import (
    manager_dashboard,
    picker_dashboard, picker_order_detail, picker_complete_order, picker_report_missing,
    picker_assign_batch, picker_auto_assign_batches,
    delivery_dashboard, delivery_order_detail, delivery_update_status
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Настройка Swagger
schema_view = get_schema_view(
   openapi.Info(
      title="Жевжик API",
      default_version='v1',
      description="Документация API для продуктового магазина Жевжик",
      terms_of_service="https://www.zhevzhik.ru/policies/terms/",
      contact=openapi.Contact(email="contact@zhevzhik.ru"),
      license=openapi.License(name="MIT License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny],
)

# Настройка роутеров для API
from .api_views import (
    CategoryViewSet, ProductViewSet, CartViewSet, OrderViewSet,
    ReviewViewSet, PromotionViewSet, FavoriteViewSet, LoyaltyCardViewSet,
    StoreViewSet, NotificationViewSet, PromoCodeViewSet
)
# UserAddressViewSet, DeliverySlotViewSet, StoreInventoryViewSet - не существуют

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'promotions', PromotionViewSet, basename='promotion')
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'loyalty-card', LoyaltyCardViewSet, basename='loyalty-card')
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'promocodes', PromoCodeViewSet, basename='promocode')
# router.register(r'addresses', UserAddressViewSet, basename='user-address')  # ViewSet не существует
# router.register(r'delivery-slots', DeliverySlotViewSet, basename='delivery-slot')  # ViewSet не существует
# router.register(r'store-inventory', StoreInventoryViewSet, basename='store-inventory')  # ViewSet не существует

urlpatterns = [
    path('addresses/', manage_addresses_view, name='manage_addresses'),
    path('payment-methods/', manage_payment_methods_view, name='manage_payment_methods'),
    path('', home_view, name='home'),
    path('info/', info_view, name='info'),
    path('register/', register_view, name='register'),
    path('login/', login_view, name='login'),
    # Восстановление пароля
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='paint_shop_project/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(
        template_name='paint_shop_project/password_reset_confirm.html',
        success_url='/password-reset/complete/'
    ), name='password_reset_confirm'),
    path('password-reset/complete/', PasswordResetCompleteView.as_view(
        template_name='paint_shop_project/password_reset_complete.html'
    ), name='password_reset_complete'),
    path('logout/', logout_view, name='logout'),
    path('cart/', cart_view, name='cart'),
    path('cart-count/', cart_count_view, name='cart_count'),
    path('cart-summary/', cart_summary_view, name='cart_summary'),
    path('add-to-cart/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('get-cart-id/<int:product_id>/', get_cart_id_by_product, name='get_cart_id_by_product'),
    path('update-cart-quantity/<int:cart_id>/', update_cart_quantity, name='update_cart_quantity'),
    path('remove-from-cart/<int:cart_id>/', remove_from_cart, name='remove_from_cart'),
    path('checkout/', checkout_view, name='checkout'),
    path('create-order/', create_order, name='create_order'),
    path('order-success/', order_success_view, name='order_success'),
    path('products/', product_list_view, name='product_list'),
    path('product/<int:product_id>/', product_detail_view, name='product_detail'),
    path('add-review/<int:product_id>/', add_review, name='add_review'),
    path('get-reviews/<int:product_id>/', get_reviews, name='get_reviews'),
    path('order-history/', order_history_view, name='order_history'),
    path('order/<int:order_id>/', order_detail_view, name='order_detail'),
    path('cancel-order/<int:order_id>/', cancel_order, name='cancel_order'),
    path('process-payment/<int:order_id>/', process_payment, name='process_payment'),
    path('payment-success/', payment_success, name='payment_success'),
    path('payment-failed/', payment_failed, name='payment_failed'),
    path('loyalty-card/', loyalty_card_view, name='loyalty_card'),
    path('loyalty-levels/', loyalty_levels_view, name='loyalty_levels'),
    path('profile/', profile_view, name='profile'),
    path('profile/address/', update_primary_address, name='update_primary_address'),
    path('update-profile/', update_profile, name='update_profile'),
    path('promotions/', promotions_view, name='promotions'),
    path('stores/', stores_view, name='stores'),
    path('contacts/', contacts_view, name='contacts'),
    path('support/', support_view, name='support'),
    path('favorite-categories/', favorite_categories_view, name='favorite_categories'),
    path('add-favorite-category/<int:category_id>/', add_favorite_category_view, name='add_favorite_category'),
    path('remove-favorite-category/<int:category_id>/', remove_favorite_category_view, name='remove_favorite_category'),
    path('favorites/', favorites_view, name='favorites'),
    path('add-to-favorites/<int:product_id>/', add_to_favorites, name='add_to_favorites'),
    path('remove-from-favorites/<int:product_id>/', remove_from_favorites, name='remove_from_favorites'),
    path('view-history/', view_history_view, name='view_history'),
    path('search-history/', search_history_view, name='search_history'),
    path('add-to-view-history/<int:product_id>/', add_to_view_history, name='add_to_view_history'),
    path('validate-promo-code/', validate_promo_code, name='validate_promo_code'),
    path('notifications/', notifications_view, name='notifications'),
    path('mark-notification-read/<int:notification_id>/', mark_notification_read, name='mark_notification_read'),
    path('mark-all-notifications-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('analytics/', analytics_view, name='analytics'),
    # REST API endpoints
    path('api/v1/', include(router.urls)),
    
    # JWT Authentication
    path('api/v1/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Swagger/OpenAPI Documentation
    path('api/swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/swagger.json/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    
    # Старые API endpoints (для обратной совместимости)
    path('api/', api_root, name='api_root'),
    path('api/docs/', api_docs_view, name='api_docs'),
    path('api/schema.json', api_schema, name='api_schema'),
    path('api/products/', api_products, name='api_products'),
    path('api/categories/', api_categories, name='api_categories'),
    path('api/product/<int:product_id>/', api_product_detail, name='api_product_detail'),
    path('api/user/orders/', api_user_orders, name='api_user_orders'),
    path('api/user/favorites/', api_user_favorites, name='api_user_favorites'),
    path('api/order/<int:order_id>/tracking/', api_order_tracking, name='api_order_tracking'),
    
    # Новые функции для покупателей
    path('rate-employee/<int:order_id>/', rate_employee, name='rate_employee'),
    path('favorite-categories/', favorite_categories_view, name='favorite_categories'),
    path('cashback-history/', cashback_history_view, name='cashback_history'),
    path('cashback-history/export/csv/', cashback_history_export_csv, name='cashback_history_export_csv'),
    path('support-tickets/', support_tickets_view, name='support_tickets'),
    path('support-ticket/<int:ticket_id>/', support_ticket_detail_view, name='support_ticket_detail'),
    path('special-sections/', special_sections_view, name='special_sections'),
    path('join-section/<int:section_id>/', join_section_view, name='join_section'),
    path('leave-section/<int:section_id>/', leave_section_view, name='leave_section'),
    path('favorite-categories/', favorite_categories_view, name='favorite_categories'),
    path('add-favorite-category/<int:category_id>/', add_favorite_category_view, name='add_favorite_category'),
    path('remove-favorite-category/<int:category_id>/', remove_favorite_category_view, name='remove_favorite_category'),
    path('yoomoney-payment/', yoomoney_payment_view, name='yoomoney_payment'),
    path('sbp-payment/', sbp_payment_view, name='sbp_payment'),
    path('error-log/', error_log_view, name='error_log'),
    path('log-error/', log_error_view, name='log_error'),
    path('promotions/', promotions_view, name='promotions'),
    path('apply-promotion/<int:promotion_id>/', apply_promotion_view, name='apply_promotion'),
    path('order-tracking/<int:order_id>/', order_tracking_view, name='order_tracking'),
    path('enhanced-profile/', enhanced_profile_view, name='enhanced_profile'),
    # Prometheus metrics endpoint (объединяет django_prometheus и кастомные метрики)
    path('metrics/', prometheus_metrics_view, name='prometheus_metrics'),
    
    # URLs для работников
    path('staff/manager/', manager_dashboard, name='manager_dashboard'),
    path('staff/picker/', picker_dashboard, name='picker_dashboard'),
    path('staff/picker/order/<int:order_id>/', picker_order_detail, name='picker_order_detail'),
        path('staff/picker/order/<int:order_id>/item/<int:item_id>/assign-batch/', picker_assign_batch, name='picker_assign_batch'),
        path('staff/picker/order/<int:order_id>/auto-assign-batches/', picker_auto_assign_batches, name='picker_auto_assign_batches'),
        path('staff/picker/order/<int:order_id>/complete/', picker_complete_order, name='picker_complete_order'),
    path('staff/picker/order/<int:order_id>/missing/', picker_report_missing, name='picker_report_missing'),
    
    path('staff/delivery/', delivery_dashboard, name='delivery_dashboard'),
    path('staff/delivery/order/<int:order_id>/', delivery_order_detail, name='delivery_order_detail'),
    path('staff/delivery/order/<int:order_id>/update-status/', delivery_update_status, name='delivery_update_status'),
]