"""
Экспорт отчетов в Excel
"""
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import TruncDay
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from ..models import Order, OrderItem, Product, User, ProductBatch, BatchAuditLog, Category


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class ExportReportsView(TemplateView):
    """Экспорт отчетов в Excel"""
    template_name = 'admin/export_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        context.update({
            'title': _('Экспорт отчетов'),
            'today': today,
            'last_month': today - timedelta(days=30),
            'next_month': today + timedelta(days=30),
        })
        return context

    def post(self, request, *args, **kwargs):
        """Генерация и скачивание отчета"""
        report_type = request.POST.get('report_type')
        
        if report_type == 'sales':
            return self._export_sales_report(request)
        elif report_type == 'orders':
            return self._export_orders_report(request)
        elif report_type == 'products':
            return self._export_products_report(request)
        elif report_type == 'customers':
            return self._export_customers_report(request)
        elif report_type == 'batches_expiring':
            return self._export_batches_expiring_report(request)
        elif report_type == 'batches_history':
            return self._export_batches_history_report(request)
        elif report_type == 'batches_losses':
            return self._export_batches_losses_report(request)
        elif report_type == 'batches_by_category':
            return self._export_batches_by_category_report(request)
        else:
            return self.get(request)

    def _export_sales_report(self, request):
        """Экспорт отчета по продажам"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Продажи"
            
            # Заголовки
            headers = ['Дата', 'Заказов', 'Выручка', 'Средний чек']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='1a2a6c', end_color='1a2a6c', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')
            
            # Данные
            now = timezone.now()
            days = int(request.POST.get('days', 30))
            start_date = now - timedelta(days=days)
            
            daily_data = (
                Order.objects.filter(
                    order_date__gte=start_date,
                    status='delivered'
                )
                .annotate(day=TruncDay('order_date'))
                .values('day')
                .annotate(
                    orders=Count('id'),
                    revenue=Sum('total_amount')
                )
                .order_by('day')
            )
            
            row = 2
            for item in daily_data:
                revenue = float(item['revenue'] or 0)
                orders = item['orders']
                avg = revenue / orders if orders > 0 else 0
                
                ws.cell(row=row, column=1, value=item['day'].strftime('%d.%m.%Y'))
                ws.cell(row=row, column=2, value=orders)
                ws.cell(row=row, column=3, value=revenue)
                ws.cell(row=row, column=4, value=avg)
                row += 1
            
            # Итоговая строка
            ws.cell(row=row, column=1, value='ИТОГО').font = Font(bold=True)
            ws.cell(row=row, column=2, value=sum(item['orders'] for item in daily_data))
            ws.cell(row=row, column=3, value=sum(float(item['revenue'] or 0) for item in daily_data))
            ws.cell(row=row, column=4, value=sum(float(item['revenue'] or 0) for item in daily_data) / sum(item['orders'] for item in daily_data) if sum(item['orders'] for item in daily_data) > 0 else 0)
            
            # Сохранение
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename=sales_report_{timezone.now().strftime("%Y%m%d")}.xlsx'
            return response
            
        except ImportError:
            from django.contrib import messages
            messages.error(request, _('Библиотека openpyxl не установлена. Установите: pip install openpyxl'))
            return self.get(request)

    def _export_orders_report(self, request):
        """Экспорт отчета по заказам"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Заказы"
            
            headers = ['ID', 'Дата', 'Клиент', 'Статус', 'Сумма', 'Товаров']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='1a2a6c', end_color='1a2a6c', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')
            
            days = int(request.POST.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            orders = Order.objects.filter(order_date__gte=start_date).select_related('user')
            
            row = 2
            for order in orders:
                items_count = order.orderitem_set.count()
                ws.cell(row=row, column=1, value=order.id)
                ws.cell(row=row, column=2, value=order.order_date.strftime('%d.%m.%Y %H:%M'))
                ws.cell(row=row, column=3, value=order.user.username if order.user else '—')
                ws.cell(row=row, column=4, value=order.get_status_display())
                ws.cell(row=row, column=5, value=float(order.total_amount))
                ws.cell(row=row, column=6, value=items_count)
                row += 1
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename=orders_report_{timezone.now().strftime("%Y%m%d")}.xlsx'
            return response
            
        except ImportError:
            from django.contrib import messages
            messages.error(request, _('Библиотека openpyxl не установлена.'))
            return self.get(request)

    def _export_products_report(self, request):
        """Экспорт отчета по товарам"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Товары"
            
            headers = ['ID', 'Название', 'Категория', 'Цена', 'Продано шт.', 'Выручка', 'Заказов']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='1a2a6c', end_color='1a2a6c', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')
            
            days = int(request.POST.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            # Агрегируем данные по товарам
            products_data = (
                OrderItem.objects.filter(
                    order__order_date__gte=start_date,
                    order__status='delivered'
                )
                .values('product__id', 'product__name', 'product__category__name', 'product__price')
                .annotate(
                    total_quantity=Sum('quantity'),
                    total_revenue=Sum(ExpressionWrapper(F('quantity') * F('price_per_unit'), output_field=DecimalField())),
                    orders_count=Count('order', distinct=True)
                )
                .order_by('-total_revenue')
            )
            
            row = 2
            for item in products_data:
                ws.cell(row=row, column=1, value=item['product__id'] or '—')
                ws.cell(row=row, column=2, value=item['product__name'] or '—')
                ws.cell(row=row, column=3, value=item['product__category__name'] or 'Без категории')
                ws.cell(row=row, column=4, value=float(item['product__price'] or 0))
                ws.cell(row=row, column=5, value=item['total_quantity'] or 0)
                ws.cell(row=row, column=6, value=float(item['total_revenue'] or 0))
                ws.cell(row=row, column=7, value=item['orders_count'] or 0)
                row += 1
            
            # Итоговая строка
            if row > 2:
                ws.cell(row=row, column=1, value='ИТОГО').font = Font(bold=True)
                ws.cell(row=row, column=5, value=sum(item['total_quantity'] or 0 for item in products_data))
                ws.cell(row=row, column=6, value=sum(float(item['total_revenue'] or 0) for item in products_data))
                ws.cell(row=row, column=7, value=sum(item['orders_count'] or 0 for item in products_data))
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename=products_report_{timezone.now().strftime("%Y%m%d")}.xlsx'
            return response
            
        except ImportError:
            from django.contrib import messages
            messages.error(request, _('Библиотека openpyxl не установлена.'))
            return self.get(request)

    def _export_customers_report(self, request):
        """Экспорт отчета по клиентам"""
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            
            wb = Workbook()
            ws = wb.active
            ws.title = "Клиенты"
            
            headers = ['ID', 'Имя пользователя', 'Email', 'Имя', 'Фамилия', 'Заказов', 'Выручка', 'Средний чек', 'Дата регистрации']
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color='1a2a6c', end_color='1a2a6c', fill_type='solid')
                cell.font = Font(bold=True, color='FFFFFF')
                cell.alignment = Alignment(horizontal='center')
            
            days = int(request.POST.get('days', 30))
            start_date = timezone.now() - timedelta(days=days)
            
            # Агрегируем данные по клиентам
            customers_data = (
                User.objects.filter(
                    is_staff=False,
                    order__order_date__gte=start_date,
                    order__status='delivered'
                )
                .annotate(
                    orders_count=Count('order', distinct=True),
                    total_revenue=Sum('order__total_amount'),
                    avg_order_value=ExpressionWrapper(
                        Sum('order__total_amount') / Count('order', distinct=True),
                        output_field=DecimalField()
                    )
                )
                .filter(orders_count__gt=0)
                .order_by('-total_revenue')
            )
            
            row = 2
            for customer in customers_data:
                ws.cell(row=row, column=1, value=customer.id)
                ws.cell(row=row, column=2, value=customer.username)
                ws.cell(row=row, column=3, value=customer.email or '—')
                ws.cell(row=row, column=4, value=customer.first_name or '—')
                ws.cell(row=row, column=5, value=customer.last_name or '—')
                ws.cell(row=row, column=6, value=customer.orders_count or 0)
                ws.cell(row=row, column=7, value=float(customer.total_revenue or 0))
                ws.cell(row=row, column=8, value=float(customer.avg_order_value or 0))
                ws.cell(row=row, column=9, value=customer.date_joined.strftime('%d.%m.%Y') if customer.date_joined else '—')
                row += 1
            
            # Итоговая строка
            if row > 2:
                ws.cell(row=row, column=1, value='ИТОГО').font = Font(bold=True)
                ws.cell(row=row, column=6, value=sum(c.orders_count or 0 for c in customers_data))
                ws.cell(row=row, column=7, value=sum(float(c.total_revenue or 0) for c in customers_data))
            
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename=customers_report_{timezone.now().strftime("%Y%m%d")}.xlsx'
            return response
            
        except ImportError:
            from django.contrib import messages
            messages.error(request, _('Библиотека openpyxl не установлена.'))
            return self.get(request)

