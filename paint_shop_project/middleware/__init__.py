from .messages_filter import SuppressSuccessMessagesMiddleware

# Импортируем TemplateSyntaxErrorLoggingMiddleware из родительского модуля middleware.py
# Используем относительный импорт через sys.modules чтобы избежать циклических импортов
import sys
import importlib.util

# Получаем путь к middleware.py
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
middleware_file = os.path.join(parent_dir, 'middleware.py')

if os.path.exists(middleware_file):
    spec = importlib.util.spec_from_file_location("paint_shop_project.middleware_old", middleware_file)
    middleware_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(middleware_module)
    TemplateSyntaxErrorLoggingMiddleware = middleware_module.TemplateSyntaxErrorLoggingMiddleware
else:
    # Если middleware.py не существует, создаём заглушку
    from django.utils.deprecation import MiddlewareMixin
    import logging
    
    logger = logging.getLogger('paint_shop_project')
    
    class TemplateSyntaxErrorLoggingMiddleware(MiddlewareMixin):
        """Middleware для логирования ошибок синтаксиса шаблонов"""
        def process_exception(self, request, exception):
            if hasattr(exception, 'template_debug'):
                logger.error(f"Template syntax error: {exception}", exc_info=True)
            return None

__all__ = ['SuppressSuccessMessagesMiddleware', 'TemplateSyntaxErrorLoggingMiddleware']
