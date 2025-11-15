"""
RFM-анализ клиентов
"""
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from ..models import Order, User


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class RFMAnalysisView(TemplateView):
    """RFM-анализ клиентов"""
    template_name = 'admin/rfm_analysis.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        now = timezone.now()
        
        # RFM параметры
        customers = User.objects.filter(is_staff=False).annotate(
            last_order_date=Max('order__order_date'),
            total_orders=Count('order'),
            total_spent=Sum('order__total_amount', filter=Q(order__status='delivered')),
            first_order_date=Min('order__order_date'),
        ).filter(total_orders__gt=0)
        
        rfm_segments = {
            'champions': [],
            'loyal_customers': [],
            'potential_loyalists': [],
            'new_customers': [],
            'promising': [],
            'needs_attention': [],
            'about_to_sleep': [],
            'at_risk': [],
            'lost': [],
        }
        
        for customer in customers:
            if not customer.last_order_date or not customer.total_spent:
                continue
            
            # Recency (давность последней покупки)
            days_since_last = (now.date() - customer.last_order_date.date()).days
            
            # Frequency (частота покупок)
            frequency = customer.total_orders
            
            # Monetary (сумма потраченных средств)
            monetary = float(customer.total_spent or 0)
            
            # RFM scores (1-5, где 5 - лучший)
            if days_since_last <= 30:
                r_score = 5
            elif days_since_last <= 60:
                r_score = 4
            elif days_since_last <= 90:
                r_score = 3
            elif days_since_last <= 180:
                r_score = 2
            else:
                r_score = 1
            
            if frequency >= 10:
                f_score = 5
            elif frequency >= 5:
                f_score = 4
            elif frequency >= 3:
                f_score = 3
            elif frequency >= 2:
                f_score = 2
            else:
                f_score = 1
            
            if monetary >= 50000:
                m_score = 5
            elif monetary >= 20000:
                m_score = 4
            elif monetary >= 10000:
                m_score = 3
            elif monetary >= 5000:
                m_score = 2
            else:
                m_score = 1
            
            rfm_score = f"{r_score}{f_score}{m_score}"
            
            customer_data = {
                'customer': customer,
                'r_score': r_score,
                'f_score': f_score,
                'm_score': m_score,
                'rfm_score': rfm_score,
                'days_since_last': days_since_last,
                'frequency': frequency,
                'monetary': monetary,
            }
            
            # Сегментация
            if r_score >= 4 and f_score >= 4 and m_score >= 4:
                rfm_segments['champions'].append(customer_data)
            elif r_score >= 3 and f_score >= 4 and m_score >= 3:
                rfm_segments['loyal_customers'].append(customer_data)
            elif r_score >= 3 and f_score <= 2 and m_score >= 3:
                rfm_segments['potential_loyalists'].append(customer_data)
            elif r_score >= 4 and f_score <= 2:
                rfm_segments['new_customers'].append(customer_data)
            elif r_score >= 3 and f_score <= 2 and m_score <= 2:
                rfm_segments['promising'].append(customer_data)
            elif r_score <= 3 and f_score >= 3:
                rfm_segments['needs_attention'].append(customer_data)
            elif r_score <= 3 and f_score <= 2 and m_score >= 3:
                rfm_segments['about_to_sleep'].append(customer_data)
            elif r_score <= 2 and f_score >= 3:
                rfm_segments['at_risk'].append(customer_data)
            else:
                rfm_segments['lost'].append(customer_data)
        
        # Статистика по сегментам
        segment_stats = {
            name: {
                'count': len(segments),
                'total_revenue': sum(c['monetary'] for c in segments),
                'avg_order_value': (
                    sum(c['monetary'] for c in segments) / len(segments)
                    if segments else 0
                ),
            }
            for name, segments in rfm_segments.items()
        }
        
        # Названия сегментов для отображения
        segment_names = {
            'champions': _('Чемпионы (VIP)'),
            'loyal_customers': _('Постоянные клиенты'),
            'potential_loyalists': _('Потенциальные постоянные'),
            'new_customers': _('Новые клиенты'),
            'promising': _('Перспективные'),
            'needs_attention': _('Требуют внимания'),
            'about_to_sleep': _('Уходящие'),
            'at_risk': _('В зоне риска'),
            'lost': _('Потерянные'),
        }
        
        context.update({
            'title': _('RFM-анализ клиентов'),
            'rfm_segments': rfm_segments,
            'segment_stats': segment_stats,
            'segment_names': segment_names,
        })
        
        return context

