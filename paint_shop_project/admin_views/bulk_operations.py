"""
Массовые операции с пользователями
"""
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..models import Role, User


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class BulkOperationsView(TemplateView):
    """Массовые операции с пользователями"""
    template_name = 'admin/bulk_operations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        roles = Role.objects.all()
        context.update({
            'title': _('Массовые операции'),
            'roles': roles,
        })
        return context

    def post(self, request, *args, **kwargs):
        """Выполнение массовой операции"""
        if not request.user.is_superuser:
            messages.error(request, _('Только суперпользователь может выполнять массовые операции'))
            return redirect('admin:bulk-operations')
        
        operation = request.POST.get('operation')
        user_ids = request.POST.getlist('user_ids')
        
        if not user_ids:
            messages.error(request, _('Не выбраны пользователи'))
            return redirect('admin:bulk-operations')
        
        users = User.objects.filter(id__in=user_ids)
        
        if operation == 'change_role':
            role_id = request.POST.get('role_id')
            if role_id:
                role = Role.objects.get(id=role_id)
                count = users.update(role=role)
                messages.success(request, _('Роль изменена для %s пользователей') % count)
        
        elif operation == 'activate':
            count = users.update(is_active=True)
            messages.success(request, _('Активировано пользователей: %s') % count)
        
        elif operation == 'deactivate':
            count = users.update(is_active=False)
            messages.success(request, _('Деактивировано пользователей: %s') % count)
        
        elif operation == 'send_notification':
            # Отправка уведомлений (реализация зависит от вашей системы уведомлений)
            from ..models import Notification
            title = request.POST.get('notification_title', 'Уведомление')
            message = request.POST.get('notification_message', '')
            
            created = 0
            for user in users:
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    notification_type='system'
                )
                created += 1
            
            messages.success(request, _('Отправлено уведомлений: %s') % created)
        
        return redirect('admin:bulk-operations')


@csrf_exempt
@require_http_methods(["GET"])
@user_passes_test(is_staff)
def bulk_users_search(request):
    """API для поиска пользователей для массовых операций"""
    query = request.GET.get('q', '')
    
    users = User.objects.filter(is_staff=False)
    
    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    
    users = users[:50]  # Ограничиваем 50 результатами
    
    return JsonResponse({
        'users': [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'is_active': user.is_active,
                'role': user.role.name if user.role else None,
            }
            for user in users
        ]
    })




