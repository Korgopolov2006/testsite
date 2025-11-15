from django.contrib import messages


class SuppressSuccessMessagesMiddleware:
    """Удаляет пользовательские success-сообщения на админских и auth-страницах."""

    SUPPRESS_SUBSTRINGS = (
        'добавлен в корзину',
        'успешно создан',
        'ваша корзина пуста',
    )

    AUTH_PATHS = {'/login/', '/register/', '/admin/login/'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._should_filter(request.path):
            storage = messages.get_messages(request)
            filtered = []
            for message in storage:
                if not self._should_remove(message):
                    filtered.append(message)
            storage.used = False
            storage._queued_messages = filtered
        return self.get_response(request)

    def _should_filter(self, path: str) -> bool:
        if path in self.AUTH_PATHS:
            return True
        return path.startswith('/admin')

    def _should_remove(self, message) -> bool:
        if message.level != messages.SUCCESS:
            return False
        text = (message.message or '').lower()
        return any(substr in text for substr in self.SUPPRESS_SUBSTRINGS)
