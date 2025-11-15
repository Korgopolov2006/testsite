"""
Сигналы для автоматического логирования изменений партий товаров
"""
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import ProductBatch, BatchAuditLog


@receiver(pre_save, sender=ProductBatch)
def log_batch_changes(sender, instance, **kwargs):
    """Логирует изменения остатка в партии"""
    if instance.pk:  # Обновление существующей партии
        try:
            old_instance = ProductBatch.objects.get(pk=instance.pk)
            if old_instance.remaining_quantity != instance.remaining_quantity:
                # Изменение остатка
                BatchAuditLog.objects.create(
                    batch=instance,
                    action='quantity_changed',
                    old_value=old_instance.remaining_quantity,
                    new_value=instance.remaining_quantity,
                    comment=f'Изменение остатка: {old_instance.remaining_quantity} → {instance.remaining_quantity}',
                )
        except ProductBatch.DoesNotExist:
            pass


@receiver(post_save, sender=ProductBatch)
def log_batch_creation(sender, instance, created, **kwargs):
    """Логирует создание новой партии"""
    if created:
        BatchAuditLog.objects.create(
            batch=instance,
            action='created',
            old_value=None,
            new_value=instance.remaining_quantity,
            comment=f'Создана новая партия: {instance.batch_number or instance.id}',
        )


@receiver(post_delete, sender=ProductBatch)
def log_batch_deletion(sender, instance, **kwargs):
    """Логирует удаление партии"""
    BatchAuditLog.objects.create(
        batch=instance,
        action='deleted',
        old_value=instance.remaining_quantity,
        new_value=0,
        comment=f'Партия удалена: {instance.batch_number or instance.id}',
    )


