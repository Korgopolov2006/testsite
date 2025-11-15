"""
Модель PickerActionLog для добавления в models.py

Добавьте этот код в конец файла models.py после всех существующих моделей.
"""

from django.db import models
from django.utils import timezone


class PickerActionLog(models.Model):
    """История действий сборщика"""
    ACTION_CHOICES = [
        ('order_taken', 'Взял заказ в работу'),
        ('batch_assigned', 'Назначил партию'),
        ('batch_unassigned', 'Снял партию'),
        ('order_completed', 'Завершил сборку'),
        ('missing_reported', 'Сообщил о недостаче'),
        ('order_started', 'Начал сборку'),
    ]
    
    picker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='picker_actions',
        verbose_name="Сборщик"
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='picker_actions',
        verbose_name="Заказ"
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Тип действия"
    )
    details = models.TextField(
        blank=True,
        verbose_name="Детали"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP-адрес"
    )
    
    class Meta:
        verbose_name = "Действие сборщика"
        verbose_name_plural = "Действия сборщиков"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['picker', 'created_at']),
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.picker.username} - {self.get_action_type_display()} - Заказ #{self.order.id}"


