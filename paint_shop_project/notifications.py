"""
Система уведомлений для магазина Жевжик
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from .models import Order, User

def send_order_confirmation(order):
    """Отправка подтверждения заказа"""
    subject = f'Подтверждение заказа #{order.id} - Жевжик'
    
    context = {
        'order': order,
        'user': order.user,
    }
    
    message = render_to_string('paint_shop_project/emails/order_confirmation.txt', context)
    html_message = render_to_string('paint_shop_project/emails/order_confirmation.html', context)
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        html_message=html_message,
        fail_silently=False,
    )

def send_order_status_update(order):
    """Отправка уведомления об изменении статуса заказа"""
    subject = f'Обновление статуса заказа #{order.id} - Жевжик'
    
    context = {
        'order': order,
        'user': order.user,
    }
    
    message = render_to_string('paint_shop_project/emails/order_status_update.txt', context)
    html_message = render_to_string('paint_shop_project/emails/order_status_update.html', context)
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.user.email],
        html_message=html_message,
        fail_silently=False,
    )

def send_promotion_notification(user, promotion):
    """Отправка уведомления о новой акции"""
    subject = f'Новая акция: {promotion.title} - Жевжик'
    
    context = {
        'user': user,
        'promotion': promotion,
    }
    
    message = render_to_string('paint_shop_project/emails/promotion_notification.txt', context)
    html_message = render_to_string('paint_shop_project/emails/promotion_notification.html', context)
    
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
