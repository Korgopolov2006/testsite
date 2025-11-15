"""
Конфигурация Celery для проекта Жевжик
"""
import os
from celery import Celery

# Устанавливаем модуль настроек Django по умолчанию
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paint_shop.settings')

app = Celery('paint_shop')

# Загружаем настройки из объекта settings
# Используем namespace='CELERY', чтобы все настройки Celery начинались с CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически обнаруживаем задачи из всех приложений Django
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')




