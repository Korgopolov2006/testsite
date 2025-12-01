from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Sum, Count
from django.utils import timezone

from .models import (
    Category, Product, Order, OrderItem, Cart, Review,
    Promotion, LoyaltyCard, Favorite, FavoriteCategory,
    CashbackTransaction, Notification, Store, PromoCode, User
)
# UserAddress, DeliverySlot, StoreInventory - модели не существуют
from .serializers import (
    CategorySerializer, ProductSerializer, OrderSerializer, OrderItemSerializer,
    CartSerializer, ReviewSerializer, PromotionSerializer, LoyaltyCardSerializer,
    FavoriteSerializer, FavoriteCategorySerializer, CashbackTransactionSerializer,
    NotificationSerializer, StoreSerializer, PromoCodeSerializer, UserSerializer,
    CartCreateSerializer
)
# UserAddressSerializer, DeliverySlotSerializer, StoreInventorySerializer - не используются


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для категорий (только чтение)"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'description']


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для товаров (только чтение)"""
    queryset = Product.objects.filter(is_active=True).select_related('category', 'manufacturer')
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'manufacturer', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'rating', 'created_at']
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Получить отзывы для товара"""
        product = self.get_object()
        reviews = product.reviews.filter(is_approved=True)
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_review(self, request, pk=None):
        """Добавить отзыв к товару"""
        product = self.get_object()
        rating = request.data.get('rating')
        comment = request.data.get('comment')
        
        if not rating or not comment:
            return Response(
                {'error': 'Рейтинг и комментарий обязательны'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, не оставлял ли пользователь уже отзыв
        existing_review = Review.objects.filter(
            user=request.user,
            product=product
        ).first()
        
        if existing_review:
            return Response(
                {'error': 'Вы уже оставляли отзыв об этом товаре'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        review = Review.objects.create(
            user=request.user,
            product=product,
            rating=rating,
            comment=comment,
            is_approved=True
        )
        
        serializer = ReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CartViewSet(viewsets.ModelViewSet):
    """ViewSet для корзины"""
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).select_related('product')
    
    def create(self, request, *args, **kwargs):
        """Добавить товар в корзину"""
        serializer = CartCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            cart_item = Cart.objects.filter(
                user=request.user,
                product_id=request.data['product_id']
            ).first()
            response_serializer = CartSerializer(cart_item)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Получить итоговую информацию по корзине"""
        cart_items = self.get_queryset()
        subtotal = sum(item.total_price for item in cart_items)
        
        # Скидка любимых категорий
        favorite_discount_amount = 0.0
        for item in cart_items:
            try:
                favorite = FavoriteCategory.objects.filter(
                    user=request.user,
                    category=item.product.category,
                    is_active=True
                ).first()
                if favorite and favorite.discount_percent > 0:
                    favorite_discount_amount += item.total_price * favorite.discount_percent / 100.0
            except Exception:
                pass
        
        favorite_discount_amount = round(favorite_discount_amount, 2)
        
        # Акции
        active_promotions = Promotion.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now()
        )
        promotion_discount = 0.0
        for promo in active_promotions:
            try:
                disc = promo.calculate_discount(max(float(subtotal) - favorite_discount_amount, 0.0))
                promotion_discount = max(promotion_discount, float(disc))
            except Exception:
                pass
        
        total_after_discounts = max(float(subtotal) - favorite_discount_amount - promotion_discount, 0.0)
        
        # Ожидаемый кешбэк
        expected_cashback = 0.0
        try:
            loyalty_card = request.user.loyalty_card
            if loyalty_card:
                expected_cashback = loyalty_card.calculate_cashback(total_after_discounts)
        except Exception:
            pass
        
        return Response({
            'subtotal': round(float(subtotal), 2),
            'favorite_discount_amount': favorite_discount_amount,
            'promotion_discount': round(promotion_discount, 2),
            'total_after_discounts': round(total_after_discounts, 2),
            'expected_cashback': round(float(expected_cashback), 2),
            'items_count': cart_items.count()
        })
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Очистить корзину"""
        cart_items = self.get_queryset()
        count = cart_items.count()
        cart_items.delete()
        return Response({'message': f'Корзина очищена. Удалено товаров: {count}'})


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для заказов (только чтение)"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'delivery_type', 'payment_method']
    ordering_fields = ['order_date', 'total_amount']
    
    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Отменить заказ"""
        order = self.get_object()
        
        if order.status not in ['created', 'confirmed']:
            return Response(
                {'error': 'Нельзя отменить заказ в текущем статусе'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        return Response({'message': 'Заказ успешно отменен'})
    
    @action(detail=True, methods=['get'])
    def tracking(self, request, pk=None):
        """Отслеживание заказа"""
        order = self.get_object()
        
        from django.db.models import Prefetch
        status_history = order.status_history.all().order_by('-timestamp')
        
        status_progress = {
            'created': 0,
            'confirmed': 25,
            'ready': 50,
            'in_transit': 75,
            'delivered': 100,
            'cancelled': 0
        }
        
        progress = status_progress.get(order.status, 0)
        
        history_data = []
        for h in status_history:
            history_data.append({
                'status': h.get_status_display() if hasattr(h, 'get_status_display') else h.status,
                'status_code': h.status,
                'timestamp': h.timestamp.isoformat(),
                'comment': h.comment,
                'courier_name': h.courier_name,
                'courier_phone': h.courier_phone,
            })
        
        return Response({
            'order_id': order.id,
            'status': order.get_status_display(),
            'status_code': order.status,
            'progress': progress,
            'tracking_number': order.tracking_number,
            'courier_name': order.courier_name,
            'courier_phone': order.courier_phone,
            'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
            'history': history_data
        })


class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet для отзывов"""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Review.objects.filter(is_approved=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PromotionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для акций (только чтение)"""
    queryset = Promotion.objects.filter(is_active=True)
    serializer_class = PromotionSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'description']


class FavoriteViewSet(viewsets.ModelViewSet):
    """ViewSet для избранного"""
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('product')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Добавить/удалить товар из избранного (любимые товары - максимум 4, изменение раз в неделю)"""
        import logging
        logger = logging.getLogger('paint_shop_project')
        
        product_id = request.data.get('product_id')
        logger.info("favorites/toggle called: user=%s product_id=%s", request.user.id, product_id)
        
        if not product_id:
            logger.warning("favorites/toggle: product_id missing")
            return Response({'error': 'product_id обязателен'}, status=status.HTTP_400_BAD_REQUEST)
        
        from .models import Product
        try:
            product = Product.objects.get(id=product_id)
            logger.info("favorites/toggle: product found id=%s name=%s", product.id, product.name)
        except Product.DoesNotExist:
            logger.warning("favorites/toggle: product not found id=%s", product_id)
            return Response({'error': 'Товар не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Проверяем, существует ли уже этот товар в избранном
        existing_favorite = Favorite.objects.filter(user=request.user, product=product).first()
        logger.info("favorites/toggle: existing_favorite=%s", existing_favorite is not None)
        
        if existing_favorite:
            # Удаление - всегда разрешаем удаление
            logger.info("favorites/toggle: deleting favorite id=%s", existing_favorite.id)
            try:
                existing_favorite.delete()
                logger.info("favorites/toggle: favorite deleted successfully")
                return Response({
                    'message': 'Товар удален из любимых',
                    'is_favorite': False
                })
            except Exception as e:
                logger.exception("favorites/toggle: error deleting favorite: %s", e)
                return Response({
                    'error': f'Ошибка при удалении товара из любимых: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Добавление - проверяем ограничения
            can_modify, next_change_date = Favorite.can_user_modify_favorites(request.user)
            logger.info("favorites/toggle: can_modify=%s next_change_date=%s", can_modify, next_change_date)
            if not can_modify:
                logger.warning("favorites/toggle: user cannot modify favorites, next_change_date=%s", next_change_date)
                return Response({
                    'error': f'Любимые товары можно изменять раз в неделю. Следующее изменение возможно {next_change_date.strftime("%d.%m.%Y") if next_change_date else "позже"}.',
                    'can_modify': False,
                    'next_change_date': next_change_date.isoformat() if next_change_date else None
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Проверяем максимальное количество (4)
            favorites_count = Favorite.get_user_favorites_count(request.user)
            logger.info("favorites/toggle: current favorites_count=%s", favorites_count)
            if favorites_count >= 4:
                logger.warning("favorites/toggle: max favorites reached, count=%s", favorites_count)
                return Response({
                    'error': 'Максимум 4 любимых товара. Удалите один из существующих, чтобы добавить новый.',
                    'max_reached': True
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                favorite = Favorite.objects.create(
                    user=request.user,
                    product=product
                )
                logger.info("favorites/toggle: favorite created id=%s", favorite.id)
                
                serializer = self.get_serializer(favorite)
                return Response({
                    'message': 'Товар добавлен в любимые (скидка 10%)',
                    'is_favorite': True,
                    'data': serializer.data
                })
            except Exception as e:
                logger.exception("favorites/toggle: error creating favorite: %s", e)
                return Response({
                    'error': f'Ошибка при добавлении товара в любимые: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoyaltyCardViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для карты лояльности (только чтение)"""
    serializer_class = LoyaltyCardSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return LoyaltyCard.objects.filter(user=self.request.user)


class StoreViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для магазинов (только чтение)"""
    queryset = Store.objects.filter(is_active=True)
    serializer_class = StoreSerializer
    permission_classes = [AllowAny]
    filter_backends = [SearchFilter]
    search_fields = ['name', 'address']


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для уведомлений"""
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Отметить все уведомления как прочитанные"""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'Все уведомления отмечены как прочитанные'})


class PromoCodeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для промокодов (только чтение)"""
    queryset = PromoCode.objects.filter(is_active=True)
    serializer_class = PromoCodeSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    def validate_code(self, request):
        """Проверить промокод"""
        code = request.data.get('code')
        if not code:
            return Response({'error': 'Код обязателен'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            promo_code = PromoCode.objects.get(code=code)
            if promo_code.is_valid():
                return Response({
                    'valid': True,
                    'message': f'Промокод "{promo_code.description}" применим!',
                    'discount_type': promo_code.discount_type,
                    'discount_value': float(promo_code.discount_value),
                    'min_order_amount': float(promo_code.min_order_amount)
                })
            else:
                return Response({'valid': False, 'message': 'Промокод недействителен'})
        except PromoCode.DoesNotExist:
            return Response({'valid': False, 'message': 'Промокод не найден'})


# class UserAddressViewSet(viewsets.ModelViewSet):
#     """Адреса пользователя"""
#     serializer_class = UserAddressSerializer  # Сериализатор не существует
#     permission_classes = [IsAuthenticated]
#
#     def get_queryset(self):
#         return UserAddress.objects.filter(user=self.request.user)  # Модель не существует
#
#     def perform_create(self, serializer):
#         created = serializer.save(user=self.request.user)
#         if created.is_default:
#             UserAddress.objects.filter(user=self.request.user).exclude(id=created.id).update(is_default=False)
#
#     def perform_update(self, serializer):
#         updated = serializer.save()
#         if updated.is_default:
#             UserAddress.objects.filter(user=self.request.user).exclude(id=updated.id).update(is_default=False)


# class DeliverySlotViewSet(viewsets.ReadOnlyModelViewSet):
#     """Доступные слоты доставки"""
#     serializer_class = DeliverySlotSerializer  # Сериализатор не существует
#     permission_classes = [AllowAny]
#     filter_backends = [DjangoFilterBackend, OrderingFilter]
#     filterset_fields = ['store', 'date', 'is_active']
#     ordering_fields = ['date', 'start_time']
#
#     def get_queryset(self):
#         qs = DeliverySlot.objects.filter(is_active=True).select_related('store')  # Модель не существует
#         only_available = self.request.query_params.get('only_available')
#         if only_available in ['1', 'true', 'True']:
#             qs = qs.filter(reserved_count__lt=models.F('capacity'))
#         return qs


# class StoreInventoryViewSet(viewsets.ReadOnlyModelViewSet):
#     """Остатки товаров по магазинам (read-only)"""
#     serializer_class = StoreInventorySerializer  # Сериализатор не существует
#     permission_classes = [AllowAny]
#     filter_backends = [DjangoFilterBackend, SearchFilter]
#     search_fields = ['product__name', 'store__name']
#     filterset_fields = ['store', 'product']
#
#     def get_queryset(self):
#         return StoreInventory.objects.select_related('store', 'product')  # Модель не существует
