"""
Views для работников магазина (сборщики и доставщики)
"""
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Q, Count, Sum, Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta

from .models import Order, OrderPicking, OrderDelivery, OrderItem, User, ProductBatch, PickerActionLog, Product, Store, Promotion, PromoCode

logger = logging.getLogger(__name__)


def is_picker(user):
    """Проверка, может ли пользователь собирать заказы (по флагу роли)"""
    return (user.is_authenticated and 
            user.role and 
            user.role.can_pick_orders)


def is_delivery_person(user):
    """Проверка, может ли пользователь доставлять заказы (по флагу роли)"""
    return (user.is_authenticated and 
            user.role and 
            user.role.can_deliver_orders)


def is_manager(user):
    """Проверка, может ли пользователь управлять магазином (по флагу роли)"""
    return (user.is_authenticated and 
            user.role and 
            user.role.can_manage_store)


@login_required
def manager_dashboard(request):
    """Панель управления менеджера магазина"""
    if not is_manager(request.user):
        messages.error(request, _('У вас нет доступа к этой странице. Требуется роль с правом управлять магазином.'))
        return redirect('home')
    
    # Получаем магазины, которыми управляет менеджер
    managed_stores = Store.objects.filter(manager=request.user, is_active=True)
    
    # Если менеджер не привязан к магазину, показываем общую статистику
    if not managed_stores.exists():
        # Общая статистика по всем магазинам
        orders = Order.objects.all()
        products = Product.objects.all()
    else:
        # Статистика по магазинам менеджера
        orders = Order.objects.filter(
            Q(fulfillment_store__in=managed_stores) | Q(pickup_point__in=managed_stores)
        )
        products = Product.objects.all()  # Все товары для менеджера
    
    now = timezone.now()
    today = now.date()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    
    # Статистика заказов
    total_orders = orders.count()
    orders_today = orders.filter(order_date__date=today).count()
    orders_last_7 = orders.filter(order_date__gte=last_7_days).count()
    orders_last_30 = orders.filter(order_date__gte=last_30_days).count()
    
    # Статистика по статусам
    orders_by_status = orders.values('status').annotate(count=Count('id')).order_by('-count')
    
    # Выручка
    delivered_orders = orders.filter(status='delivered')
    total_revenue = delivered_orders.aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_today = delivered_orders.filter(order_date__date=today).aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_last_7 = delivered_orders.filter(order_date__gte=last_7_days).aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_last_30 = delivered_orders.filter(order_date__gte=last_30_days).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Средний чек
    avg_order_value = (total_revenue / delivered_orders.count()) if delivered_orders.count() > 0 else 0
    
    # Топ товары
    top_products = (
        OrderItem.objects.filter(order__in=delivered_orders)
        .values('product__name', 'product__id')
        .annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('price_per_unit')
        )
        .order_by('-total_quantity')[:10]
    )
    
    # Статистика товаров
    total_products = products.count()
    active_products = products.filter(is_active=True).count()
    low_stock_products = products.filter(stock_quantity__lt=10).count()
    out_of_stock_products = products.filter(stock_quantity=0).count()
    
    # Статистика партий
    batches = ProductBatch.objects.all()
    total_batches = batches.count()
    expiring_soon_batches = batches.filter(
        expiry_date__lte=today + timedelta(days=7),
        expiry_date__gte=today,
        remaining_quantity__gt=0
    ).count()
    expired_batches = batches.filter(
        expiry_date__lt=today,
        remaining_quantity__gt=0
    ).count()
    
    # Статистика сборок
    pickings = OrderPicking.objects.filter(order__in=orders)
    total_pickings = pickings.count()
    pending_pickings = pickings.filter(status='pending').count()
    in_progress_pickings = pickings.filter(status='in_progress').count()
    completed_pickings = pickings.filter(status='completed').count()
    
    # Последние заказы
    recent_orders = orders.select_related('user', 'fulfillment_store').order_by('-order_date')[:10]
    
    # Активные акции
    active_promotions = Promotion.objects.filter(is_active=True, end_date__gte=now).count()
    active_promocodes = PromoCode.objects.filter(is_active=True, end_date__gte=now).count()
    
    context = {
        'manager_name': request.user.get_full_name() or request.user.username,
        'managed_stores': managed_stores,
        'total_orders': total_orders,
        'orders_today': orders_today,
        'orders_last_7': orders_last_7,
        'orders_last_30': orders_last_30,
        'orders_by_status': orders_by_status,
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_last_7': revenue_last_7,
        'revenue_last_30': revenue_last_30,
        'avg_order_value': avg_order_value,
        'top_products': top_products,
        'total_products': total_products,
        'active_products': active_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'total_batches': total_batches,
        'expiring_soon_batches': expiring_soon_batches,
        'expired_batches': expired_batches,
        'total_pickings': total_pickings,
        'pending_pickings': pending_pickings,
        'in_progress_pickings': in_progress_pickings,
        'completed_pickings': completed_pickings,
        'recent_orders': recent_orders,
        'active_promotions': active_promotions,
        'active_promocodes': active_promocodes,
    }
    
    return render(request, 'paint_shop_project/staff/manager_dashboard.html', context)


@login_required
def picker_dashboard(request):
    """Панель управления сборщика"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице. Требуется роль с правом собирать заказы.'))
        return redirect('home')
    
    # Получаем заказы, ожидающие сборки или в процессе
    # Для самовывоза - заказы собираются в магазине
    # Для доставки - заказы собираются в магазине комплектации
    orders = Order.objects.filter(
        Q(picking__status='pending') | Q(picking__status='in_progress') | Q(picking__status='missing_items'),
        status__in=['created', 'confirmed']
    ).select_related('user', 'picking', 'fulfillment_store').prefetch_related('items').order_by('-order_date')
    
    # Заказы, которые собирает текущий сборщик
    my_pickings = orders.filter(picking__picker=request.user)
    
    # Доступные заказы для взятия в работу (еще не назначены сборщику)
    available_orders = orders.filter(
        Q(picking__picker__isnull=True) | Q(picking__status='pending')
    )
    
    # Завершенные сборки сегодня
    completed_today = Order.objects.filter(
        picking__picker=request.user,
        picking__status='completed',
        picking__completed_at__date=timezone.now().date()
    ).count()
    
    context = {
        'my_pickings': my_pickings,
        'available_orders': available_orders,
        'total_pending': orders.filter(picking__status='pending').count(),
        'completed_today': completed_today,
        'picker_name': request.user.get_full_name() or request.user.username,
    }
    
    return render(request, 'paint_shop_project/staff/picker_dashboard.html', context)


@login_required
def picker_order_detail(request, order_id):
    """Детали заказа для сборщика"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(
        Order.objects.select_related('user', 'fulfillment_store', 'picking'),
        id=order_id
    )
    
    picking, created = OrderPicking.objects.get_or_create(order=order)
    
    # Если заказ еще не назначен сборщику, назначаем текущего
    if not picking.picker and picking.status == 'pending':
        picking.picker = request.user
        picking.status = 'in_progress'
        picking.started_at = timezone.now()
        picking.save()
        
        # Логируем действие
        PickerActionLog.objects.create(
            picker=request.user,
            order=order,
            action_type='order_taken',
            details=f'Взял заказ #{order.id} в работу',
            ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
        )
    
    # Проверяем доступ
    if picking.picker != request.user and picking.status != 'pending':
        messages.error(request, _('Этот заказ собирает другой сборщик.'))
        return redirect('picker_dashboard')
    
    order_items = OrderItem.objects.filter(order=order).select_related('product', 'batch')
    
    # Получаем доступные партии для каждого товара в заказе (FEFO + правило 70%)
    items_with_batches = []
    for item in order_items:
        # Получаем доступные партии для этого товара
        # Фильтруем: не просроченные, с остатком, и с минимум 70% срока годности
        today = timezone.now().date()
        available_batches = ProductBatch.objects.filter(
            product=item.product,
            expiry_date__gte=today,
            remaining_quantity__gte=item.quantity
        ).select_related('product', 'product__category').order_by('expiry_date')  # FEFO: сначала партии с ближайшим сроком годности
        
        # Фильтруем по правилу 70% срока годности
        sellable_batches = []
        for batch in available_batches:
            if batch.is_sellable(min_percent=70):
                sellable_batches.append(batch)
        
        items_with_batches.append({
            'item': item,
            'available_batches': sellable_batches,
            'has_expiry': item.product.has_expiry_date,
        })
    
    context = {
        'order': order,
        'picking': picking,
        'order_items': order_items,
        'items_with_batches': items_with_batches,
        'customer': order.user,
        'customer_phone': order.user.phone or order.user.username,
        'customer_email': order.user.email,
        'picker_name': request.user.get_full_name() or request.user.username,
        'is_pickup': order.delivery_type == 'pickup',
    }
    
    return render(request, 'paint_shop_project/staff/picker_order_detail.html', context)


@login_required
def picker_assign_batch(request, order_id, item_id):
    """Назначение партии товара для позиции заказа"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id)
    order_item = get_object_or_404(OrderItem, id=item_id, order=order)
    picking = get_object_or_404(OrderPicking, order=order)
    
    if picking.picker != request.user:
        messages.error(request, _('Этот заказ собирает другой сборщик.'))
        return redirect('picker_dashboard')
    
    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        if batch_id:
            try:
                batch = ProductBatch.objects.get(
                    id=batch_id,
                    product=order_item.product,
                    expiry_date__gte=timezone.now().date(),
                    remaining_quantity__gte=order_item.quantity
                )
                
                # Проверяем правило 70% срока годности
                if not batch.is_sellable(min_percent=70):
                    messages.error(request, _('Выбранная партия не соответствует правилу 70% срока годности для продажи.'))
                    return redirect('picker_order_detail', order_id=order_id)
                order_item.batch = batch
                order_item.save()
                
                # Уменьшаем остаток в партии
                old_quantity = batch.remaining_quantity
                batch.remaining_quantity -= order_item.quantity
                batch.save()
                
                # Логируем назначение партии
                from .models import BatchAuditLog
                from django.utils import timezone
                BatchAuditLog.objects.create(
                    batch=batch,
                    action='assigned',
                    user=request.user,
                    old_value=old_quantity,
                    new_value=batch.remaining_quantity,
                    comment=f'Назначена заказу #{order_id}, позиция: {order_item.product.name} (количество: {order_item.quantity})',
                    ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
                )
                
                # Логируем действие сборщика
                PickerActionLog.objects.create(
                    picker=request.user,
                    order=order,
                    action_type='batch_assigned',
                    details=f'Назначена партия {batch.batch_number} для товара {order_item.product.name} (количество: {order_item.quantity})',
                    ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
                )
                
                messages.success(request, _('Партия успешно назначена!'))
            except ProductBatch.DoesNotExist:
                messages.error(request, _('Выбранная партия недоступна или недостаточно товара.'))
        else:
            # Убираем партию
            if order_item.batch:
                batch = order_item.batch
                old_quantity = batch.remaining_quantity
                # Возвращаем товар в партию
                batch.remaining_quantity += order_item.quantity
                batch.save()
                
                # Логируем снятие партии
                from .models import BatchAuditLog
                BatchAuditLog.objects.create(
                    batch=batch,
                    action='unassigned',
                    user=request.user,
                    old_value=old_quantity,
                    new_value=batch.remaining_quantity,
                    comment=f'Снята с заказа #{order_id}, позиция: {order_item.product.name} (количество: {order_item.quantity})',
                    ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
                )
            order_item.batch = None
            order_item.save()
            
            # Логируем действие сборщика
            PickerActionLog.objects.create(
                picker=request.user,
                order=order,
                action_type='batch_unassigned',
                details=f'Снята партия {batch.batch_number} с товара {order_item.product.name} (количество: {order_item.quantity})',
                ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
            )
            
            messages.success(request, _('Партия удалена.'))
    
    return redirect('picker_order_detail', order_id=order_id)


@login_required
def picker_auto_assign_batches(request, order_id):
    """Автоматическое назначение партий для всех позиций заказа (FEFO + правило 70%)"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id)
    picking = get_object_or_404(OrderPicking, order=order)
    
    if picking.picker != request.user:
        messages.error(request, _('Этот заказ собирает другой сборщик.'))
        return redirect('picker_dashboard')
    
    if request.method == 'POST':
        today = timezone.now().date()
        assigned_count = 0
        failed_items = []
        
        order_items = OrderItem.objects.filter(order=order).select_related('product', 'product__category', 'batch')
        
        for item in order_items:
            # Пропускаем товары без срока годности или уже с назначенной партией
            if not item.product.has_expiry_date or item.batch:
                continue
            
            # Ищем доступные партии (FEFO + правило 70%)
            available_batches = ProductBatch.objects.filter(
                product=item.product,
                expiry_date__gte=today,
                remaining_quantity__gt=0
            ).select_related('product', 'product__category').order_by('expiry_date')
            
            # Фильтруем по правилу 70% и сортируем по приоритету (FEFO)
            sellable_batches = [
                batch for batch in available_batches 
                if batch.is_sellable(min_percent=70)
            ]
            
            if not sellable_batches:
                failed_items.append(item.product.name)
                continue
            
            # Умный подбор: распределяем между несколькими партиями, если нужно
            remaining_needed = item.quantity
            batches_used = []
            
            for batch in sellable_batches:
                if remaining_needed <= 0:
                    break
                
                # Сколько можем взять из этой партии
                take_from_batch = min(remaining_needed, batch.remaining_quantity)
                
                if take_from_batch > 0:
                    # Если это первая партия, назначаем её на item
                    if not batches_used:
                        item.batch = batch
                        item.save()
                    
                    # Уменьшаем остаток
                    old_quantity = batch.remaining_quantity
                    batch.remaining_quantity -= take_from_batch
                    batch.save()
                    
                    # Логируем автоподбор партии
                    from .models import BatchAuditLog
                    BatchAuditLog.objects.create(
                        batch=batch,
                        action='assigned',
                        user=request.user,
                        old_value=old_quantity,
                        new_value=batch.remaining_quantity,
                        comment=f'Автоподбор для заказа #{order_id}, позиция: {item.product.name} (взято: {take_from_batch} из {item.quantity})',
                        ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
                    )
                    
                    batches_used.append((batch, take_from_batch))
                    remaining_needed -= take_from_batch
            
            if remaining_needed > 0:
                # Не хватило партий
                failed_items.append(f"{item.product.name} (недостаточно: нужно {item.quantity}, доступно {item.quantity - remaining_needed})")
            else:
                assigned_count += len(batches_used)
        
        if assigned_count > 0:
            messages.success(request, _('Автоматически назначено партий: %(count)d') % {'count': assigned_count})
        
        if failed_items:
            messages.warning(
                request,
                _('Не удалось назначить партии для товаров: %(names)s') % {'names': ', '.join(failed_items)}
            )
        
        return redirect('picker_order_detail', order_id=order_id)
    
    return redirect('picker_dashboard')


@login_required
def picker_complete_order(request, order_id):
    """Завершение сборки заказа"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id)
    picking = get_object_or_404(OrderPicking, order=order)
    
    if picking.picker != request.user:
        messages.error(request, _('Этот заказ собирает другой сборщик.'))
        return redirect('picker_dashboard')
    
    if request.method == 'POST':
        # Блокируем завершение, если у скоропортящихся товаров не назначены партии
        missing_batches = (
            OrderItem.objects
            .filter(order=order, product__has_expiry_date=True, batch__isnull=True)
            .select_related('product')
        )
        if missing_batches.exists():
            names = ", ".join(sorted({it.product.name for it in missing_batches}))
            messages.error(
                request,
                _('Нельзя завершить сборку: не назначены партии для товаров: %(names)s') % {'names': names}
            )
            return redirect('picker_order_detail', order_id=order_id)
        
        # Проверяем, что назначенные партии соответствуют правилу 70%
        invalid_batches = []
        for item in OrderItem.objects.filter(order=order, batch__isnull=False).select_related('product', 'batch'):
            if item.product.has_expiry_date and not item.batch.is_sellable(min_percent=70):
                invalid_batches.append(item.product.name)
        
        if invalid_batches:
            messages.error(
                request,
                _('Нельзя завершить сборку: партии для товаров не соответствуют правилу 70%%: %(names)s') % {'names': ', '.join(invalid_batches)}
            )
            return redirect('picker_order_detail', order_id=order_id)
        
        picking.status = 'completed'
        picking.completed_at = timezone.now()
        picking.save()
        
        # Обновляем статус заказа
        order.status = 'ready'
        order.save()
        
        # Создаем запись в истории статусов
        from .models import OrderStatusHistory
        OrderStatusHistory.objects.create(
            order=order,
            status='ready',
            comment='Заказ собран'
        )
        
        # Логируем действие сборщика
        PickerActionLog.objects.create(
            picker=request.user,
            order=order,
            action_type='order_completed',
            details=f'Завершил сборку заказа #{order.id}',
            ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
        )
        
        messages.success(request, _('Заказ успешно собран!'))
        return redirect('picker_dashboard')
    
    return redirect('picker_order_detail', order_id=order_id)


@login_required
def picker_report_missing(request, order_id):
    """Сообщение о недостающих товарах"""
    if not is_picker(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id)
    picking = get_object_or_404(OrderPicking, order=order)
    
    if picking.picker != request.user:
        messages.error(request, _('Этот заказ собирает другой сборщик.'))
        return redirect('picker_dashboard')
    
    if request.method == 'POST':
        comment = request.POST.get('comment', '')
        picking.status = 'missing_items'
        picking.missing_items_comment = comment
        picking.save()
        
        # Уведомляем покупателя
        try:
            customer = order.user
            subject = _('Информация о заказе #{}').format(order.id)
            message = _(
                'Здравствуйте!\n\n'
                'К сожалению, в заказе #{} не хватает некоторых товаров.\n'
                'Комментарий сборщика: {}\n\n'
                'Мы свяжемся с вами для уточнения деталей.\n\n'
                'С уважением, команда Жевжик'
            ).format(order.id, comment)
            
            if customer.email:
                send_mail(
                    subject,
                    message,
                    'noreply@zhevzhik.ru',
                    [customer.email],
                    fail_silently=False,
                )
            
            # Telegram уведомление
            if customer.telegram_notifications_enabled and customer.telegram_chat_id:
                try:
                    from .telegram_bot import TelegramNotifier
                    notifier = TelegramNotifier()
                    notifier.send_message(
                        customer.telegram_chat_id,
                        f'Заказ #{order.id}: {message}'
                    )
                except Exception as e:
                    logger.error("Failed to send Telegram notification: %s", e)
            
            picking.notified_customer = True
            picking.save()
            
            # Логируем действие сборщика
            PickerActionLog.objects.create(
                picker=request.user,
                order=order,
                action_type='missing_reported',
                details=f'Сообщил о недостаче товаров: {comment}',
                ip_address=request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None,
            )
            
            messages.success(request, _('Покупатель уведомлен о недостающих товарах.'))
        except Exception as e:
            logger.error("Failed to notify customer: %s", e)
            messages.warning(request, _('Не удалось отправить уведомление покупателю.'))
        
        return redirect('picker_order_detail', order_id=order_id)
    
    return redirect('picker_order_detail', order_id=order_id)


@login_required
def delivery_dashboard(request):
    """Панель управления доставщика"""
    if not is_delivery_person(request.user):
        messages.error(request, _('У вас нет доступа к этой странице. Требуется роль с правом доставлять заказы.'))
        return redirect('home')
    
    # Заказы с доставкой, готовые к доставке (собранные)
    orders = Order.objects.filter(
        delivery_type='delivery',
        status__in=['ready', 'in_transit'],
    ).select_related('user', 'delivery_tracking', 'fulfillment_store').prefetch_related('items').order_by('-order_date')
    
    # Заказы, которые доставляет текущий доставщик
    my_deliveries = orders.filter(delivery_tracking__delivery_person=request.user)
    
    # Доступные заказы для взятия в доставку (еще не назначены доставщику)
    available_orders = orders.filter(
        Q(delivery_tracking__delivery_person__isnull=True) | Q(delivery_tracking__status='pending'),
        status='ready'
    )
    
    # Доставленные сегодня
    delivered_today = Order.objects.filter(
        delivery_tracking__delivery_person=request.user,
        delivery_tracking__status='delivered',
        delivery_tracking__delivered_at__date=timezone.now().date()
    ).count()
    
    context = {
        'my_deliveries': my_deliveries,
        'available_orders': available_orders,
        'total_pending': orders.filter(delivery_tracking__status='pending').count(),
        'delivered_today': delivered_today,
        'delivery_person_name': request.user.get_full_name() or request.user.username,
    }
    
    return render(request, 'paint_shop_project/staff/delivery_dashboard.html', context)


@login_required
def delivery_order_detail(request, order_id):
    """Детали заказа для доставщика"""
    if not is_delivery_person(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(
        Order.objects.select_related('user', 'fulfillment_store', 'delivery_tracking'),
        id=order_id,
        delivery_type='delivery'
    )
    
    delivery, created = OrderDelivery.objects.get_or_create(
        order=order,
        defaults={'status': 'pending'}
    )
    
    # Если доставка еще не назначена, назначаем текущего доставщика
    if not delivery.delivery_person and delivery.status == 'pending':
        delivery.delivery_person = request.user
        delivery.status = 'assigned'
        delivery.assigned_at = timezone.now()
        delivery.save()
    
    # Проверяем доступ
    if delivery.delivery_person != request.user and delivery.status != 'pending':
        messages.error(request, _('Этот заказ доставляет другой доставщик.'))
        return redirect('delivery_dashboard')
    
    order_items = OrderItem.objects.filter(order=order).select_related('product')
    
    context = {
        'order': order,
        'delivery': delivery,
        'order_items': order_items,
        'customer': order.user,
        'customer_phone': order.user.phone or order.user.username,
        'customer_email': order.user.email,
        'delivery_address': order.delivery_address,
        'delivery_person_name': request.user.get_full_name() or request.user.username,
    }
    
    return render(request, 'paint_shop_project/staff/delivery_order_detail.html', context)


@login_required
def delivery_update_status(request, order_id):
    """Обновление статуса доставки"""
    if not is_delivery_person(request.user):
        messages.error(request, _('У вас нет доступа к этой странице.'))
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id, delivery_type='delivery')
    delivery = get_object_or_404(OrderDelivery, order=order)
    
    if delivery.delivery_person != request.user:
        messages.error(request, _('Этот заказ доставляет другой доставщик.'))
        return redirect('delivery_dashboard')
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        comment = request.POST.get('comment', '')
        
        if new_status in dict(OrderDelivery.STATUS_CHOICES):
            old_status = delivery.status
            delivery.status = new_status
            delivery.comment = comment
            
            # Обновляем временные метки
            if new_status == 'picked_up' and not delivery.picked_up_at:
                delivery.picked_up_at = timezone.now()
            elif new_status == 'delivered' and not delivery.delivered_at:
                delivery.delivered_at = timezone.now()
                order.status = 'delivered'
                order.save()
            elif new_status == 'in_transit':
                order.status = 'in_transit'
                order.save()
            
            delivery.save()
            
            # Создаем запись в истории статусов
            from .models import OrderStatusHistory
            OrderStatusHistory.objects.create(
                order=order,
                status=order.status,
                comment=f'Доставщик: {comment}' if comment else 'Обновлен статус доставки'
            )
            
            messages.success(request, _('Статус доставки обновлен!'))
        
        return redirect('delivery_order_detail', order_id=order_id)
    
    return redirect('delivery_order_detail', order_id=order_id)
