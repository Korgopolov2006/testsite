from django.utils.deprecation import MiddlewareMixin
from django.template import TemplateSyntaxError
from django.core.mail import mail_admins
from django.urls import resolve
from .models import ErrorLog

class TemplateSyntaxErrorLoggingMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, TemplateSyntaxError):
            try:
                ErrorLog.objects.create(
                    error_type='server',
                    message=str(exception),
                    stack_trace='',
                    user=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
                    url=request.build_absolute_uri(),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )
            except Exception:
                pass
            subject = 'TemplateSyntaxError на сайте'
            body = f"URL: {request.build_absolute_uri()}\nОшибка: {str(exception)}"
            try:
                mail_admins(subject, body, fail_silently=True)
            except Exception:
                pass
            return None
        return None
