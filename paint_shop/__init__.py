"""
Это гарантирует, что приложение Celery загрузится при старте Django (если установлено)
"""
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery не установлен - это нормально для разработки без фоновых задач
    __all__ = ()

