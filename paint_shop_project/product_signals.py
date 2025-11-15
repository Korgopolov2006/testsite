"""
Сигналы для автоматического создания партий при поступлении товара
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from .models import Product, ProductBatch


@receiver(pre_save, sender=Product)
def track_stock_change(sender, instance, **kwargs):
    """Отслеживает изменение stock_quantity для создания партий"""
    if instance.pk:  # Обновление существующего товара
        try:
            old_instance = Product.objects.get(pk=instance.pk)
            # Сохраняем старое значение для использования в post_save
            instance._old_stock_quantity = old_instance.stock_quantity
        except Product.DoesNotExist:
            instance._old_stock_quantity = 0
    else:
        instance._old_stock_quantity = 0


@receiver(post_save, sender=Product)
def create_batch_on_stock_increase(sender, instance, created, **kwargs):
    """Автоматически создает партию при увеличении stock_quantity"""
    # Работаем только с товарами, имеющими срок годности
    if not instance.has_expiry_date:
        return
    
    old_stock = getattr(instance, '_old_stock_quantity', 0)
    new_stock = instance.stock_quantity or 0
    
    # Если количество увеличилось, создаем партию
    if new_stock > old_stock:
        quantity_added = new_stock - old_stock
        
        # Определяем даты для партии
        today = timezone.now().date()
        production_date = instance.production_date or today
        
        # Если есть shelf_life_days, используем его для расчета expiry_date
        if instance.shelf_life_days:
            expiry_date = production_date + timedelta(days=instance.shelf_life_days)
        elif instance.expiry_date:
            # Если указан конкретный срок годности, используем его
            expiry_date = instance.expiry_date
        else:
            # По умолчанию: 30 дней с даты производства
            expiry_date = production_date + timedelta(days=30)
        
        # Генерируем номер партии
        batch_number = f"AUTO-{instance.id}-{today.strftime('%Y%m%d')}"
        
        # Проверяем, не существует ли уже партия с таким номером
        counter = 1
        while ProductBatch.objects.filter(batch_number=batch_number).exists():
            batch_number = f"AUTO-{instance.id}-{today.strftime('%Y%m%d')}-{counter}"
            counter += 1
        
        # Создаем партию
        batch = ProductBatch.objects.create(
            product=instance,
            batch_number=batch_number,
            production_date=production_date,
            expiry_date=expiry_date,
            quantity=quantity_added,
            remaining_quantity=quantity_added,
            supplier='Автоматическое создание',
        )
        
        # Логируем создание
        from .models import BatchAuditLog
        BatchAuditLog.objects.create(
            batch=batch,
            action='created',
            old_value=None,
            new_value=quantity_added,
            comment=f'Автоматическое создание партии при поступлении товара (добавлено {quantity_added} единиц)',
        )


