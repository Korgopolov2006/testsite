"""
Автоматизация обработки заказов
"""
from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.generic import TemplateView

from ..models import Order


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class OrderAutomationView(TemplateView):
    """Автоматизация обработки заказов"""
    template_name = 'admin/order_automation.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Правила автоматизации
        rules = [
            {
                'id': 'auto_confirm_paid',
                'name': _('Автоматическое подтверждение оплаченных заказов'),
                'description': _('Заказы со статусом "оплачен" автоматически переходят в "обработка" через 1 час'),
                'enabled': False,
            },
            {
                'id': 'auto_deliver_prepared',
                'name': _('Автоматическая доставка готовых заказов'),
                'description': _('Заказы со статусом "готов" автоматически переходят в "доставка" через 2 часа'),
                'enabled': False,
            },
            {
                'id': 'remind_unprocessed',
                'name': _('Напоминание о необработанных заказах'),
                'description': _('Отправка уведомления администратору о заказах, не обработанных более 24 часов'),
                'enabled': True,
            },
        ]
        
        # Статистика
        unprocessed_24h = Order.objects.filter(
            ~Q(status__in=['delivered', 'cancelled']),
            order_date__lt=timezone.now() - timedelta(hours=24)
        ).count()
        
        context.update({
            'title': _('Автоматизация обработки заказов'),
            'rules': rules,
            'unprocessed_24h': unprocessed_24h,
        })
        
        return context

    def post(self, request, *args, **kwargs):
        """Включение/выключение правил автоматизации"""
        rule_id = request.POST.get('rule_id')
        enabled = request.POST.get('enabled') == 'true'
        
        # Здесь должна быть логика сохранения настроек автоматизации
        # Для примера просто показываем сообщение
        
        if enabled:
            messages.success(request, _('Правило "%s" включено') % rule_id)
        else:
            messages.success(request, _('Правило "%s" выключено') % rule_id)
        
        return redirect('admin:order-automation')




