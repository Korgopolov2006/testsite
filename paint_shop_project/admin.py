from django.contrib import admin
from django.urls import path

try:
    from .admin_views import (
        DatabaseMaintenanceView,
        DashboardView,
        dashboard_api,
        WarehouseDashboardView,
        warehouse_dashboard_api,
        NotificationsCenterView,
        notifications_api,
        ExportReportsView,
        SlowQueriesView,
        RFMAnalysisView,
        BulkOperationsView,
        bulk_users_search,
        OrderAutomationView,
    )
except ImportError:
    DatabaseMaintenanceView = None
    DashboardView = None
    dashboard_api = None
    WarehouseDashboardView = None
    warehouse_dashboard_api = None
    NotificationsCenterView = None
    notifications_api = None
    ExportReportsView = None
    SlowQueriesView = None
    RFMAnalysisView = None
    BulkOperationsView = None
    bulk_users_search = None
    OrderAutomationView = None

from .models import *

# --- OrderAdmin: заполняем обязательные поля, если они не заданы из формы ---
 

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_staff_role', 'can_pick_orders', 'can_deliver_orders', 'can_manage_store']
    search_fields = ['name']
    list_filter = ['is_staff_role', 'can_pick_orders', 'can_deliver_orders', 'can_manage_store']
    fieldsets = (
        (None, {'fields': ('name', 'description')}),
        ('Права роли', {'fields': ('is_staff_role', 'can_pick_orders', 'can_deliver_orders', 'can_manage_store')}),
    )

from django import forms


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'role', 'role_flags_display', 'phone', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff', 'role__is_staff_role', 'role__can_pick_orders', 'role__can_deliver_orders', 'role__can_manage_store']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    list_editable = ['is_active']
    actions = ['make_picker', 'make_delivery', 'make_store_manager', 'remove_staff_role']
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {'fields': ('first_name', 'last_name', 'email', 'phone', 'address', 'birth_date', 'avatar')}),
        ('Права доступа', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Уведомления', {'fields': ('telegram_chat_id', 'telegram_notifications_enabled', 'is_newsletter_subscribed')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )
    
    # Убираем кнопки «Сегодня/Сейчас» у поля даты рождения, используя обычный HTML5 date input
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'birth_date':
            kwargs['widget'] = forms.DateInput(attrs={'type': 'date'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    def role_flags_display(self, obj):
        """Отображает флаги роли пользователя"""
        if not obj.role:
            return "—"
        flags = []
        if obj.role.is_staff_role:
            flags.append("👷 Сотрудник")
        if obj.role.can_pick_orders:
            flags.append("📦 Сборка")
        if obj.role.can_deliver_orders:
            flags.append("🚚 Доставка")
        if obj.role.can_manage_store:
            flags.append("🏪 Магазин")
        return ", ".join(flags) if flags else "—"
    role_flags_display.short_description = "Права роли"
    
    def make_picker(self, request, queryset):
        """Быстрое действие: назначить роль сборщика"""
        picker_role = Role.objects.filter(can_pick_orders=True, is_staff_role=True).first()
        if picker_role:
            count = queryset.update(role=picker_role)
            self.message_user(request, f'Роль "Сборщик" назначена {count} пользователю(ям).')
        else:
            self.message_user(request, 'Роль "Сборщик" не найдена. Создайте её в админке ролей.', level='error')
    make_picker.short_description = "Назначить роль сборщика"
    
    def make_delivery(self, request, queryset):
        """Быстрое действие: назначить роль доставщика"""
        delivery_role = Role.objects.filter(can_deliver_orders=True, is_staff_role=True).first()
        if delivery_role:
            count = queryset.update(role=delivery_role)
            self.message_user(request, f'Роль "Доставщик" назначена {count} пользователю(ям).')
        else:
            self.message_user(request, 'Роль "Доставщик" не найдена. Создайте её в админке ролей.', level='error')
    make_delivery.short_description = "Назначить роль доставщика"
    
    def make_store_manager(self, request, queryset):
        """Быстрое действие: назначить роль управляющего магазином"""
        manager_role = Role.objects.filter(can_manage_store=True, is_staff_role=True).first()
        if manager_role:
            count = queryset.update(role=manager_role)
            self.message_user(request, f'Роль "Управляющий магазином" назначена {count} пользователю(ям).')
        else:
            self.message_user(request, 'Роль "Управляющий магазином" не найдена. Создайте её в админке ролей.', level='error')
    make_store_manager.short_description = "Назначить роль управляющего магазином"
    
    def remove_staff_role(self, request, queryset):
        """Быстрое действие: убрать роль сотрудника"""
        customer_role = Role.objects.filter(is_staff_role=False).first()
        if customer_role:
            count = queryset.update(role=customer_role)
            self.message_user(request, f'Роль сотрудника снята у {count} пользователя(ей).')
        else:
            self.message_user(request, 'Роль "Покупатель" не найдена. Создайте её в админке ролей.', level='error')
    remove_staff_role.short_description = "Убрать роль сотрудника"

@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'email']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'is_active', 'sort_order']
    list_filter = ['is_active', 'parent']
    search_fields = ['name']
    ordering = ['sort_order', 'name']

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'manufacturer', 'price', 'old_price', 'stock_quantity', 'expiry_status_display', 'rating', 'is_featured', 'is_active', 'created_at']
    list_filter = ['category', 'manufacturer', 'is_featured', 'is_active', 'has_expiry_date', 'created_at', 'rating']
    search_fields = ['name', 'description']
    list_editable = ['price', 'old_price', 'stock_quantity', 'is_featured', 'is_active']
    ordering = ['-created_at']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'slug', 'description', 'category', 'manufacturer')
        }),
        ('Цены и наличие', {
            'fields': ('price', 'old_price', 'stock_quantity', 'unit', 'weight')
        }),
        ('Срок годности', {
            'fields': ('has_expiry_date', 'expiry_date', 'production_date', 'shelf_life_days'),
            'classes': ('collapse',)
        }),
        ('Изображение и рейтинг', {
            'fields': ('image', 'rating')
        }),
        ('Настройки', {
            'fields': ('is_featured', 'is_active')
        }),
    )
    
    def expiry_status_display(self, obj):
        """Отображает статус срока годности в списке товаров"""
        if not obj.has_expiry_date:
            return "Без срока годности"
        
        status = obj.expiry_status
        days_left = obj.days_until_expiry
        
        if status == 'expired':
            return "❌ Просрочен"
        elif status == 'expires_soon':
            return f"⚠️ Истекает через {days_left} дн."
        elif status == 'expires_week':
            return f"🟡 Истекает через {days_left} дн."
        elif status == 'fresh':
            return f"✅ Свежий ({days_left} дн.)"
        else:
            return "❓ Неизвестно"
    
    expiry_status_display.short_description = "Срок годности"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'manufacturer')

@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'phone', 'manager', 'is_active']
    list_filter = ['is_active', 'manager']
    search_fields = ['name', 'address']

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'order_date', 'status', 'delivery_type', 'total_amount', 'payment_method', 'items_count']
    list_filter = ['status', 'delivery_type', 'payment_method', 'order_date']
    search_fields = ['user__username', 'user__email', 'id']
    readonly_fields = ['order_date', 'total_amount']
    list_per_page = 25
    date_hierarchy = 'order_date'
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('user', 'order_date', 'status')
        }),
        ('Доставка', {
            'fields': ('delivery_type', 'pickup_point', 'delivery_address')
        }),
        ('Оплата', {
            'fields': ('payment_method', 'total_amount')
        }),
        ('Дополнительно', {
            'fields': ('comment',)
        }),
    )
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Количество товаров'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'pickup_point')

    def save_model(self, request, obj, form, change):
        # Гарантируем ненулевые значения для обязательных полей
        from decimal import Decimal
        if obj.total_amount is None:
            obj.total_amount = Decimal('0.00')
        if not obj.status:
            obj.status = 'created'
        if getattr(obj, 'delivery_cost', None) is None:
            obj.delivery_cost = Decimal('0.00')
        super().save_model(request, obj, form, change)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'price_per_unit', 'total_price']
    list_filter = ['order__status']

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'quantity', 'added_at']
    list_filter = ['added_at']
    search_fields = ['user__username', 'product__name']

@admin.register(OrderDelivery)
class OrderDeliveryAdmin(admin.ModelAdmin):
    list_display = ['order', 'delivery_person', 'status', 'assigned_at', 'delivered_at']
    list_filter = ['status', 'delivery_person']
    search_fields = ['order__id', 'delivery_person__username']

@admin.register(ProductBatch)
class ProductBatchAdmin(admin.ModelAdmin):
    list_display = ['product', 'batch_number', 'production_date', 'expiry_date', 'quantity', 'remaining_quantity', 'expiry_status_display', 'expiry_percent_display', 'is_sellable_display']
    list_filter = ['product', 'expiry_date', 'production_date']
    search_fields = ['batch_number', 'product__name']
    date_hierarchy = 'expiry_date'
    readonly_fields = ['created_at', 'updated_at', 'expiry_percent_remaining', 'days_until_expiry_display']
    list_editable = ['remaining_quantity']
    list_per_page = 50  # Пагинация для больших списков
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('product', 'batch_number')
        }),
        ('Сроки годности', {
            'fields': ('production_date', 'expiry_date', 'days_until_expiry_display', 'expiry_percent_remaining')
        }),
        ('Количество', {
            'fields': ('quantity', 'remaining_quantity')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def days_until_expiry_display(self, obj):
        """Отображает количество дней до истечения срока годности"""
        days = obj.days_until_expiry
        if days < 0:
            return f"❌ Просрочено ({abs(days)} дн. назад)"
        return f"{days} дн."
    days_until_expiry_display.short_description = "Дней до истечения"
    
    def expiry_status_display(self, obj):
        """Отображает статус срока годности"""
        if obj.is_expired:
            return "❌ Просрочено"
        days = obj.days_until_expiry
        if days <= 3:
            return f"⚠️ Истекает через {days} дн."
        elif days <= 7:
            return f"🟡 Истекает через {days} дн."
        else:
            return f"✅ Свежий ({days} дн.)"
    expiry_status_display.short_description = "Статус срока годности"
    
    def expiry_percent_display(self, obj):
        """Отображает процент оставшегося срока годности"""
        percent = obj.expiry_percent_remaining
        if percent is None:
            return "—"
        color = "🟢" if percent >= 70 else "🟡" if percent >= 50 else "🔴"
        return f"{color} {percent:.0f}%"
    expiry_percent_display.short_description = "% срока"
    
    def is_sellable_display(self, obj):
        """Отображает, можно ли продать партию (правило 70%)"""
        if obj.is_sellable(min_percent=70):
            return "✅ Можно продать"
        return "❌ Нельзя продать (<70%)"
    is_sellable_display.short_description = "Можно продать"
    
    def get_queryset(self, request):
        """Оптимизация запросов с select_related"""
        return super().get_queryset(request).select_related('product', 'product__category')


@admin.register(BatchAuditLog)
class BatchAuditLogAdmin(admin.ModelAdmin):
    list_display = ['batch', 'action', 'user', 'old_value', 'new_value', 'created_at', 'ip_address']
    list_filter = ['action', 'created_at', 'user']
    search_fields = ['batch__batch_number', 'batch__product__name', 'user__username', 'comment']
    readonly_fields = ['batch', 'action', 'user', 'old_value', 'new_value', 'comment', 'ip_address', 'created_at']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('batch', 'action', 'user', 'created_at')
        }),
        ('Изменения', {
            'fields': ('old_value', 'new_value')
        }),
        ('Дополнительно', {
            'fields': ('comment', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещаем ручное создание логов"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем редактирование логов"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям"""
        return request.user.is_superuser


@admin.register(PickerActionLog)
class PickerActionLogAdmin(admin.ModelAdmin):
    list_display = ['picker', 'order', 'action_type', 'created_at', 'ip_address']
    list_filter = ['action_type', 'created_at', 'picker']
    search_fields = ['picker__username', 'order__id', 'details']
    readonly_fields = ['picker', 'order', 'action_type', 'details', 'created_at', 'ip_address']
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('picker', 'order', 'action_type', 'created_at')
        }),
        ('Детали', {
            'fields': ('details', 'ip_address')
        }),
    )
    
    def has_add_permission(self, request):
        """Запрещаем ручное создание логов"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Запрещаем редактирование логов"""
        return False
    
    def get_queryset(self, request):
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related('picker', 'order')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'payment_method', 'status', 'payment_date']
    list_filter = ['status', 'payment_method', 'payment_date']

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'rating', 'is_approved', 'created_at', 'comment_preview']
    list_filter = ['rating', 'is_approved', 'created_at']
    search_fields = ['user__username', 'product__name', 'comment']
    list_editable = ['is_approved']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Отзыв', {
            'fields': ('user', 'product', 'rating', 'comment')
        }),
        ('Модерация', {
            'fields': ('is_approved',)
        }),
    )
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Комментарий'

@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ['name', 'value', 'metric_type', 'timestamp', 'labels_display']
    list_filter = ['metric_type', 'name', 'timestamp']
    search_fields = ['name']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    list_per_page = 50
    
    def labels_display(self, obj):
        """Отображает метки в читаемом виде"""
        if obj.labels:
            return ", ".join([f"{k}={v}" for k, v in obj.labels.items()])
        return "—"
    labels_display.short_description = "Метки"
    
    def get_queryset(self, request):
        return super().get_queryset(request)


@admin.register(ErrorLog)
class ErrorLogAdmin(admin.ModelAdmin):
    list_display = ['error_type', 'message_short', 'user', 'product', 'is_resolved', 'created_at']
    list_filter = ['error_type', 'is_resolved', 'created_at']
    search_fields = ['message', 'user__username', 'product__name']
    list_editable = ['is_resolved']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'user_agent', 'ip_address', 'url', 'stack_trace']
    list_per_page = 50
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('error_type', 'message', 'user', 'product', 'is_resolved', 'created_at')
        }),
        ('Детали ошибки', {
            'fields': ('stack_trace', 'url'),
            'classes': ('collapse',)
        }),
        ('Техническая информация', {
            'fields': ('user_agent', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    def message_short(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_short.short_description = "Сообщение"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')

# @admin.register(Discount)  # Модель Discount не существует
# class DiscountAdmin(admin.ModelAdmin):
#     list_display = ['product', 'discount_percent', 'start_date', 'end_date', 'is_active']
#     list_filter = ['is_active', 'start_date', 'end_date']

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_type', 'discount_value', 'min_order_amount', 'start_date', 'end_date', 'is_active']
    list_filter = ['discount_type', 'is_active', 'start_date', 'end_date']
    search_fields = ['name', 'description']
    list_editable = ['is_active']
    ordering = ['-created_at']

@admin.register(LoyaltyCard)
class LoyaltyCardAdmin(admin.ModelAdmin):
    list_display = ['card_number', 'user', 'points', 'level', 'created_at', 'last_activity']
    list_filter = ['level', 'created_at', 'last_activity']
    search_fields = ['card_number', 'user__username', 'user__email']
    readonly_fields = ['card_number', 'created_at', 'last_activity']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Информация о карте', {
            'fields': ('user', 'card_number', 'points', 'level')
        }),
        ('Даты', {
            'fields': ('created_at', 'last_activity')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ['card', 'transaction_type', 'points', 'description', 'order', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['card__card_number', 'card__user__username', 'description']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Транзакция', {
            'fields': ('card', 'transaction_type', 'points', 'description', 'order')
        }),
        ('Дата', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('card__user', 'order')

@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'product__name']
    list_per_page = 25
    date_hierarchy = 'created_at'

@admin.register(SearchHistory)
class SearchHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'query', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'query']
    list_per_page = 25
    date_hierarchy = 'created_at'

@admin.register(ViewHistory)
class ViewHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['user__username', 'product__name']
    list_per_page = 25
    date_hierarchy = 'viewed_at'

@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ['code', 'description', 'discount_type', 'discount_value', 'is_active', 'used_count', 'max_uses', 'start_date', 'end_date']
    list_filter = ['discount_type', 'is_active', 'start_date', 'end_date']
    search_fields = ['code', 'description']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('code', 'description', 'discount_type', 'discount_value')
        }),
        ('Условия', {
            'fields': ('min_order_amount', 'max_uses', 'used_count')
        }),
        ('Период действия', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Дата создания', {
            'fields': ('created_at',)
        }),
    )
    
    readonly_fields = ['used_count', 'created_at']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'notification_type', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__username', 'title', 'message']
    list_per_page = 25
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Уведомление', {
            'fields': ('user', 'title', 'message', 'notification_type')
        }),
        ('Статус', {
            'fields': ('is_read',)
        }),
        ('Дата создания', {
            'fields': ('created_at',)
        }),
    )
    
    readonly_fields = ['created_at']

@admin.register(EmployeeRating)
class EmployeeRatingAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_name', 'order', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['user__username', 'employee_name', 'comment']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(FavoriteCategory)
class FavoriteCategoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'cashback_multiplier', 'created_at']
    list_filter = ['cashback_multiplier', 'created_at']
    search_fields = ['user__username', 'category__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(CashbackTransaction)
class CashbackTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'order', 'amount', 'transaction_type', 'description', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__username', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ['user', 'subject', 'status', 'priority', 'category', 'created_at']
    list_filter = ['status', 'priority', 'category', 'created_at']
    search_fields = ['user__username', 'subject', 'message']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

@admin.register(SupportResponse)
class SupportResponseAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'user', 'is_staff_response', 'created_at']
    list_filter = ['is_staff_response', 'created_at']
    search_fields = ['ticket__subject', 'user__username', 'message']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(SpecialSection)
class SpecialSectionAdmin(admin.ModelAdmin):
    list_display = ['name', 'cashback_multiplier', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    ordering = ['name']

@admin.register(UserSpecialSection)
class UserSpecialSectionAdmin(admin.ModelAdmin):
    list_display = ['user', 'section', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'section__name']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ['operation', 'status', 'file_size_display', 'started_at', 'completed_at', 'duration_display']
    list_filter = ['operation', 'status', 'started_at']
    search_fields = ['file_path', 'comment', 'error_message']
    readonly_fields = ['started_at', 'completed_at', 'duration_display', 'file_size_display']
    ordering = ['-started_at']
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('Операция', {
            'fields': ('operation', 'status')
        }),
        ('Файл', {
            'fields': ('file_path', 'file_size', 'file_size_display')
        }),
        ('Информация', {
            'fields': ('comment', 'error_message')
        }),
        ('Временные метки', {
            'fields': ('started_at', 'completed_at', 'duration_display'),
            'classes': ('collapse',)
        }),
    )
    
    def file_size_display(self, obj):
        if obj.file_size:
            size = obj.file_size
            for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
                if size < 1024.0:
                    return f"{size:.2f} {unit}"
                size /= 1024.0
            return f"{size:.2f} ТБ"
        return "—"
    file_size_display.short_description = "Размер файла"
    
    def duration_display(self, obj):
        duration = obj.duration
        if duration:
            total_seconds = int(duration)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours:
                return f"{hours}ч {minutes}м {seconds}с"
            elif minutes:
                return f"{minutes}м {seconds}с"
            return f"{seconds}с"
        return "—"
    duration_display.short_description = "Длительность"


# --- Дополнительные URL административной панели ---
original_admin_get_urls = admin.site.get_urls


def get_custom_admin_urls():
    urls = original_admin_get_urls()
    custom_urls = []
    
    if DatabaseMaintenanceView:
        custom_urls.append(
            path(
                "database/maintenance/",
                admin.site.admin_view(DatabaseMaintenanceView.as_view()),
                name="database-maintenance",
            ),
        )
    
    if DashboardView:
        custom_urls.extend([
            path(
                "dashboard/",
                admin.site.admin_view(DashboardView.as_view()),
                name="dashboard",
            ),
            path(
                "dashboard/api/",
                admin.site.admin_view(dashboard_api),
                name="dashboard-api",
            ),
        ])
    
    if NotificationsCenterView:
        custom_urls.extend([
            path(
                "notifications/",
                admin.site.admin_view(NotificationsCenterView.as_view()),
                name="notifications-center",
            ),
            path(
                "notifications/api/",
                admin.site.admin_view(notifications_api),
                name="notifications-api",
            ),
        ])
    
    if ExportReportsView:
        custom_urls.append(
            path(
                "export-reports/",
                admin.site.admin_view(ExportReportsView.as_view()),
                name="export-reports",
            ),
        )
    
    if SlowQueriesView:
        custom_urls.append(
            path(
                "slow-queries/",
                admin.site.admin_view(SlowQueriesView.as_view()),
                name="slow-queries",
            ),
        )
    
    if RFMAnalysisView:
        custom_urls.append(
            path(
                "rfm-analysis/",
                admin.site.admin_view(RFMAnalysisView.as_view()),
                name="rfm-analysis",
            ),
        )
    
    if BulkOperationsView:
        custom_urls.extend([
            path(
                "bulk-operations/",
                admin.site.admin_view(BulkOperationsView.as_view()),
                name="bulk-operations",
            ),
            path(
                "bulk-operations/search/",
                admin.site.admin_view(bulk_users_search),
                name="bulk-users-search",
            ),
        ])
    
    if OrderAutomationView:
        custom_urls.append(
            path(
                "order-automation/",
                admin.site.admin_view(OrderAutomationView.as_view()),
                name="order-automation",
            ),
        )
    
    if WarehouseDashboardView:
        custom_urls.extend([
            path(
                "warehouse-dashboard/",
                admin.site.admin_view(WarehouseDashboardView.as_view()),
                name="warehouse-dashboard",
            ),
            path(
                "warehouse-dashboard/api/",
                admin.site.admin_view(warehouse_dashboard_api),
                name="warehouse-dashboard-api",
            ),
        ])
    
    return custom_urls + urls


admin.site.get_urls = get_custom_admin_urls
