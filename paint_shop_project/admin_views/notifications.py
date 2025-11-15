"""
Центр уведомлений для администратора
"""
from datetime import timedelta
from typing import Dict, List

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..models import DatabaseBackup, Notification, Order, User


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class NotificationsCenterView(TemplateView):
    """Центр уведомлений администратора"""
    template_name = 'admin/notifications_center.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Собираем все типы уведомлений
        notifications = []
        
        # 1. Проблемные заказы (не обработаны более 24 часов)
        problem_orders = Order.objects.filter(
            ~Q(status__in=['delivered', 'cancelled']),
            order_date__lt=timezone.now() - timedelta(hours=24)
        )
        for order in problem_orders[:10]:
            notifications.append({
                'type': 'warning',
                'category': 'orders',
                'title': _('Необработанный заказ'),
                'message': _('Заказ #%s не обработан более 24 часов') % order.id,
                'url': f'/admin/paint_shop_project/order/{order.id}/change/',
                'time': order.order_date,
            })
        
        # 2. Недавние ошибки бэкапов
        failed_backups = DatabaseBackup.objects.filter(
            status='failed',
            started_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-started_at')[:5]
        
        for backup in failed_backups:
            notifications.append({
                'type': 'error',
                'category': 'backup',
                'title': _('Ошибка резервного копирования'),
                'message': backup.error_message or _('Неизвестная ошибка'),
                'url': f'/admin/paint_shop_project/databasebackup/{backup.id}/change/',
                'time': backup.started_at,
            })
        
        # 3. Новые пользователи (за последние 24 часа)
        new_users = User.objects.filter(
            date_joined__gte=timezone.now() - timedelta(hours=24),
            is_staff=False
        ).count()
        
        if new_users > 0:
            notifications.append({
                'type': 'info',
                'category': 'users',
                'title': _('Новые пользователи'),
                'message': _('Зарегистрировано %s новых пользователей за 24 часа') % new_users,
                'url': '/admin/paint_shop_project/user/',
                'time': timezone.now(),
            })
        
        # 4. Непрочитанные системные уведомления для администратора
        unread_admin_notifications = Notification.objects.filter(
            user=self.request.user,
            is_read=False,
            notification_type='system'
        )[:10]
        
        for notif in unread_admin_notifications:
            notifications.append({
                'type': 'info',
                'category': 'system',
                'title': notif.title,
                'message': notif.message[:100],
                'url': f'/admin/paint_shop_project/notification/{notif.id}/change/',
                'time': notif.created_at,
            })
        
        # Сортируем по времени
        notifications.sort(key=lambda x: x['time'], reverse=True)
        
        context.update({
            'title': _('Центр уведомлений'),
            'notifications': notifications[:50],  # Ограничиваем 50 последними
        })
        
        return context


@csrf_exempt
@require_http_methods(["GET"])
@user_passes_test(is_staff)
def notifications_api(request):
    """API для получения уведомлений"""
    category = request.GET.get('category', 'all')
    unread_only = request.GET.get('unread_only', 'false') == 'true'
    
    notifications = []
    
    if category in ['all', 'orders']:
        # Проблемные заказы
        problem_orders = Order.objects.filter(
            ~Q(status__in=['delivered', 'cancelled']),
            order_date__lt=timezone.now() - timedelta(hours=24)
        )
        for order in problem_orders[:10]:
            notifications.append({
                'id': f'order_{order.id}',
                'type': 'warning',
                'category': 'orders',
                'title': _('Необработанный заказ'),
                'message': _('Заказ #%s не обработан более 24 часов') % order.id,
                'url': f'/admin/paint_shop_project/order/{order.id}/change/',
                'time': order.order_date.isoformat(),
            })
    
    if category in ['all', 'backup']:
        # Ошибки бэкапов
        failed_backups = DatabaseBackup.objects.filter(
            status='failed',
            started_at__gte=timezone.now() - timedelta(days=7)
        ).order_by('-started_at')[:5]
        
        for backup in failed_backups:
            notifications.append({
                'id': f'backup_{backup.id}',
                'type': 'error',
                'category': 'backup',
                'title': _('Ошибка резервного копирования'),
                'message': backup.error_message or _('Неизвестная ошибка'),
                'url': f'/admin/paint_shop_project/databasebackup/{backup.id}/change/',
                'time': backup.started_at.isoformat(),
            })
    
    notifications.sort(key=lambda x: x['time'], reverse=True)
    
    return JsonResponse({
        'notifications': notifications,
        'count': len(notifications)
    })

