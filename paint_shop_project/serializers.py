from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Category, Product, Manufacturer, Order, OrderItem, Cart, 
    Review, Promotion, LoyaltyCard, Favorite, FavoriteCategory,
    CashbackTransaction, Notification, Store, PromoCode
)
# UserAddress, DeliverySlot, StoreInventory - модели не существуют

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор категорий"""
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'product_count', 'is_active']
    
    def get_product_count(self, obj):
        return obj.products.filter(is_active=True).count()


class ManufacturerSerializer(serializers.ModelSerializer):
    """Сериализатор производителей"""
    
    class Meta:
        model = Manufacturer
        fields = ['id', 'name', 'address', 'phone', 'email', 'website', 'logo', 'is_active']


class ProductSerializer(serializers.ModelSerializer):
    """Сериализатор товаров"""
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    manufacturer = ManufacturerSerializer(read_only=True)
    manufacturer_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    discount_percent = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'category', 'category_id',
            'manufacturer', 'manufacturer_id', 'price', 'old_price',
            'stock_quantity', 'unit', 'weight', 'image', 'rating',
            'is_featured', 'is_active', 'discount_percent',
            'has_expiry_date', 'expiry_date', 'production_date', 'shelf_life_days'
        ]

    def get_discount_percent(self, obj):
        return obj.discount_percent


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор позиций заказа"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price_per_unit', 'total_price']
    
    def get_total_price(self, obj):
        return obj.total_price


class OrderSerializer(serializers.ModelSerializer):
    """Сериализатор заказов"""
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    delivery_type_display = serializers.CharField(source='get_delivery_type_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    
    fulfillment_store = serializers.StringRelatedField(read_only=True)
    delivery_slot = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'user', 'order_date', 'status', 'status_display',
            'delivery_type', 'delivery_type_display',
            'payment_method', 'payment_method_display',
            'total_amount', 'items', 'delivery_address',
            'comment', 'tracking_number', 'estimated_delivery_time',
            'actual_delivery_time', 'courier_name', 'courier_phone',
            'favorite_discount_amount', 'promotion_discount', 'delivery_cost',
            'fulfillment_store', 'delivery_slot'
        ]
        read_only_fields = ['id', 'order_date']

    def get_delivery_slot(self, obj):
        slot = getattr(obj, 'delivery_slot', None)
        if not slot:
            return None
        return {
            'id': slot.id,
            'date': slot.date.isoformat(),
            'start_time': slot.start_time.strftime('%H:%M'),
            'end_time': slot.end_time.strftime('%H:%M'),
            'store': slot.store.name,
        }


class CartSerializer(serializers.ModelSerializer):
    """Сериализатор корзины"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = ['id', 'product', 'product_id', 'quantity', 'added_at', 'total_price']
        read_only_fields = ['id', 'added_at']
    
    def get_total_price(self, obj):
        return obj.total_price


class ReviewSerializer(serializers.ModelSerializer):
    """Сериализатор отзывов"""
    user = serializers.StringRelatedField(read_only=True)
    product = serializers.StringRelatedField(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Review
        fields = ['id', 'user', 'product', 'product_id', 'rating', 'comment', 'created_at', 'is_approved']
        read_only_fields = ['id', 'created_at']


class PromotionSerializer(serializers.ModelSerializer):
    """Сериализатор акций"""
    is_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = Promotion
        fields = [
            'id', 'name', 'description', 'discount_type', 'discount_value',
            'min_order_amount', 'start_date', 'end_date', 'is_active',
            'image', 'created_at', 'is_valid'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_is_valid(self, obj):
        return obj.is_valid()


class LoyaltyCardSerializer(serializers.ModelSerializer):
    """Сериализатор карты лояльности"""
    user = serializers.StringRelatedField(read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    
    class Meta:
        model = LoyaltyCard
        fields = [
            'id', 'user', 'card_number', 'points', 'total_spent',
            'level', 'level_display', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'created_at', 'last_activity']


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор избранного"""
    product = ProductSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Favorite
        fields = ['id', 'product', 'product_id', 'created_at']
        read_only_fields = ['id', 'created_at']


class FavoriteCategorySerializer(serializers.ModelSerializer):
    """Сериализатор любимых категорий"""
    category = CategorySerializer(read_only=True)
    category_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = FavoriteCategory
        fields = ['id', 'category', 'category_id', 'cashback_multiplier', 'discount_percent', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class CashbackTransactionSerializer(serializers.ModelSerializer):
    """Сериализатор транзакций кешбэка"""
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    
    class Meta:
        model = CashbackTransaction
        fields = [
            'id', 'order', 'amount', 'transaction_type', 'transaction_type_display',
            'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    """Сериализатор уведомлений"""
    notification_type_display = serializers.CharField(source='get_notification_type_display', read_only=True)
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'notification_type', 'notification_type_display',
            'is_read', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class StoreSerializer(serializers.ModelSerializer):
    """Сериализатор магазинов"""
    manager = serializers.StringRelatedField(read_only=True)
    
    class Meta:
        model = Store
        fields = ['id', 'name', 'address', 'phone', 'email', 'working_hours', 'manager', 'is_active']
        read_only_fields = ['id']


# class UserAddressSerializer(serializers.ModelSerializer):
#     """Сериализатор адресов пользователя"""
#     class Meta:
#         model = UserAddress  # Модель не существует
#         fields = [
#             'id', 'label', 'address', 'entrance', 'floor', 'apartment',
#             'latitude', 'longitude', 'is_default', 'created_at', 'updated_at'
#         ]
#         read_only_fields = ['id', 'created_at', 'updated_at']


# class DeliverySlotSerializer(serializers.ModelSerializer):
#     """Сериализатор слотов доставки"""
#     store = StoreSerializer(read_only=True)
#     store_id = serializers.IntegerField(write_only=True)
#     available = serializers.SerializerMethodField()
#
#     class Meta:
#         model = DeliverySlot  # Модель не существует
#         fields = [
#             'id', 'store', 'store_id', 'date', 'start_time', 'end_time',
#             'capacity', 'reserved_count', 'is_active', 'available'
#         ]
#         read_only_fields = ['id', 'reserved_count', 'available']
#
#     def get_available(self, obj):
#         return obj.available


# class StoreInventorySerializer(serializers.ModelSerializer):
#     """Сериализатор остатков в магазинах (read-only)"""
#     store = StoreSerializer(read_only=True)
#     product = ProductSerializer(read_only=True)
#
#     class Meta:
#         model = StoreInventory  # Модель не существует
#         fields = ['id', 'store', 'product', 'quantity', 'updated_at']
#         read_only_fields = ['id', 'updated_at']


class PromoCodeSerializer(serializers.ModelSerializer):
    """Сериализатор промокодов"""
    is_valid = serializers.SerializerMethodField()
    discount_type_display = serializers.CharField(source='get_discount_type_display', read_only=True)
    
    class Meta:
        model = PromoCode
        fields = [
            'id', 'code', 'description', 'discount_type', 'discount_type_display',
            'discount_value', 'min_order_amount', 'start_date', 'end_date',
            'is_active', 'created_at', 'is_valid', 'max_uses', 'used_count'
        ]
        read_only_fields = ['id', 'created_at', 'used_count']
    
    def get_is_valid(self, obj):
        return obj.is_valid()


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователей"""
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    loyalty_level = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'address', 'avatar', 'role_display', 'loyalty_level',
            'total_cashback_earned', 'total_cashback_spent', 'date_joined'
        ]
        read_only_fields = ['id', 'date_joined']
    
    def get_loyalty_level(self, obj):
        return obj.get_loyalty_level()


class CartCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания/обновления корзины"""
    
    class Meta:
        model = Cart
        fields = ['product_id', 'quantity']
    
    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Количество должно быть больше 0")
        return value
    
    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        user = self.context['request'].user
        product = Product.objects.get(id=product_id)
        
        cart_item, created = Cart.objects.get_or_create(
            user=user,
            product=product,
            defaults={'quantity': validated_data['quantity']}
        )
        
        if not created:
            cart_item.quantity = validated_data['quantity']
            cart_item.save()
        
        return cart_item
