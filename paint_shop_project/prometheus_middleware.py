"""
Middleware для сбора метрик Prometheus
Использует нативные Prometheus метрики если доступны
"""
import time
from django.utils.deprecation import MiddlewareMixin

# Пробуем использовать нативные Prometheus метрики
try:
    from paint_shop_project.prometheus_metrics import (
        http_requests_total, http_request_duration_seconds, 
        http_errors_total, http_exceptions_total
    )
    USE_NATIVE_METRICS = True
except ImportError:
    USE_NATIVE_METRICS = False
    from paint_shop.metrics import increment_counter, observe_histogram


class PrometheusMetricsMiddleware(MiddlewareMixin):
    """Middleware для сбора метрик HTTP запросов"""
    
    def process_request(self, request):
        """Засекаем время начала обработки запроса"""
        request._prometheus_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Собираем метрики после обработки запроса"""
        # Игнорируем запросы к метрикам и статике
        if request.path.startswith('/metrics') or request.path.startswith('/static') or request.path.startswith('/media'):
            return response
        
        # Время обработки запроса
        duration = 0
        if hasattr(request, '_prometheus_start_time'):
            duration = time.time() - request._prometheus_start_time
        
        # Метки для метрик (все значения должны быть строками для Prometheus)
        method = str(request.method)
        status_code = str(response.status_code)
        path = self._sanitize_path(request.path)
        
        if USE_NATIVE_METRICS:
            # Используем нативные Prometheus метрики
            http_requests_total.labels(method=method, status_code=status_code, path=path).inc()
            http_request_duration_seconds.labels(method=method, status_code=status_code, path=path).observe(duration)
            
            if response.status_code >= 400:
                http_errors_total.labels(method=method, status_code=status_code, path=path).inc()
        else:
            # Fallback на старую систему
            labels = {
                'method': method,
                'status_code': status_code,
                'path': path,
            }
            increment_counter('zhevzhik_http_requests_total', labels=labels)
            observe_histogram('zhevzhik_http_request_duration_seconds', duration, labels=labels)
            
            if response.status_code >= 400:
                increment_counter('zhevzhik_http_errors_total', labels=labels)
        
        return response
    
    def process_exception(self, request, exception):
        """Обработка исключений"""
        method = str(request.method)
        path = self._sanitize_path(request.path)
        exception_type = type(exception).__name__
        
        if USE_NATIVE_METRICS:
            http_exceptions_total.labels(method=method, path=path, exception_type=exception_type).inc()
        else:
            labels = {
                'method': method,
                'path': path,
                'exception_type': exception_type,
            }
            increment_counter('zhevzhik_http_exceptions_total', labels=labels)
        return None
    
    def _sanitize_path(self, path):
        """Очистка пути от параметров для группировки"""
        # Убираем ID из URL для группировки
        import re
        # Заменяем числа на placeholder
        path = re.sub(r'/\d+/', '/{id}/', path)
        # Убираем query параметры
        path = path.split('?')[0]
        return path[:100]  # Ограничиваем длину



