"""
Context processors для глобального доступа к переменным в шаблонах
"""
from django.urls import reverse, NoReverseMatch


def dashboard_url(request):
    """Добавляет dashboard_url и другие admin URLs в контекст всех шаблонов"""
    context = {}
    
    if request.user.is_authenticated and request.user.is_staff:
        # Безопасная проверка dashboard URL
        dashboard_url_value = None
        try:
            dashboard_url_value = reverse('admin:dashboard')
        except NoReverseMatch:
            try:
                dashboard_url_value = reverse('admin:index')
            except NoReverseMatch:
                dashboard_url_value = None
        context['dashboard_url'] = dashboard_url_value
        
        # Безопасная проверка database-maintenance URL
        database_maintenance_url = None
        try:
            database_maintenance_url = reverse('admin:database-maintenance')
        except NoReverseMatch:
            database_maintenance_url = '/admin/database/maintenance/'
        context['database_maintenance_url'] = database_maintenance_url
        
        # Безопасная проверка notifications-center URL
        notifications_center_url = None
        try:
            notifications_center_url = reverse('admin:notifications-center')
        except NoReverseMatch:
            notifications_center_url = None
        context['notifications_center_url'] = notifications_center_url
        
        # Безопасная проверка export-reports URL
        export_reports_url = None
        try:
            export_reports_url = reverse('admin:export-reports')
        except NoReverseMatch:
            export_reports_url = None
        context['export_reports_url'] = export_reports_url
    
    return context


