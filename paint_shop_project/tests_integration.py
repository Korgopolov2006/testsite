"""
Интеграционные тесты для полного цикла работы с партиями товаров
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

from paint_shop_project.models import (
    Product, Category, Manufacturer, ProductBatch, Order, OrderItem, 
    OrderPicking, Role, BatchAuditLog, PickerActionLog
)
from paint_shop_project.staff_views import (
    picker_order_detail, picker_assign_batch, picker_auto_assign_batches,
    picker_complete_order
)

User = get_user_model()


class FullCycleBatchTests(TestCase):
    """Тесты полного цикла: создание партии → заказ → назначение → сборка"""
    
    def setUp(self):
        """Настройка тестовых данных"""
        self.factory = RequestFactory()
        
        # Создаем роли
        self.picker_role = Role.objects.create(
            name='picker',
            can_pick_orders=True,
            is_staff_role=True
        )
        self.customer_role = Role.objects.create(
            name='customer',
            is_staff_role=False
        )
        
        # Создаем пользователей
        self.picker = User.objects.create_user(
            username='picker',
            password='password',
            role=self.picker_role
        )
        self.customer = User.objects.create_user(
            username='customer',
            password='password',
            role=self.customer_role
        )
        
        # Создаем категорию и производителя
        self.category = Category.objects.create(name='Краски', slug='kraski')
        self.manufacturer = Manufacturer.objects.create(name='Производитель А')
        
        # Создаем товар со сроком годности
        self.product = Product.objects.create(
            name='Молоко',
            slug='moloko',
            category=self.category,
            manufacturer=self.manufacturer,
            price=100,
            has_expiry_date=True,
            stock_quantity=100
        )
        
        # Создаем партию (80% срока годности осталось - можно продать)
        today = timezone.now().date()
        self.batch = ProductBatch.objects.create(
            product=self.product,
            batch_number='BATCH001',
            production_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=40),  # 50 дней всего, 40 осталось = 80%
            quantity=50,
            remaining_quantity=50
        )
        
        # Создаем заказ
        self.order = Order.objects.create(
            user=self.customer,
            delivery_type='pickup',
            payment_method='cash',
            total_amount=500,
            status='created'
        )
        
        # Создаем позицию заказа
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=10,
            price_per_unit=100
        )
        
        # Создаем OrderPicking
        self.picking = OrderPicking.objects.create(
            order=self.order,
            status='pending'
        )
        
        # Настройка messages framework
        setattr(self.factory, 'session', {})
        setattr(self.factory, 'user', self.picker)
        self.messages = FallbackStorage(self.factory)
        setattr(self.factory, '_messages', self.messages)
    
    def test_full_cycle_success(self):
        """Тест полного цикла: взятие заказа → назначение партии → завершение сборки"""
        
        # Шаг 1: Сборщик берет заказ в работу
        request = self.factory.get(reverse('picker_order_detail', args=[self.order.id]))
        request.user = self.picker
        response = picker_order_detail(request, self.order.id)
        
        self.picking.refresh_from_db()
        self.assertEqual(self.picking.picker, self.picker)
        self.assertEqual(self.picking.status, 'in_progress')
        
        # Проверяем логирование
        self.assertTrue(
            PickerActionLog.objects.filter(
                picker=self.picker,
                order=self.order,
                action_type='order_taken'
            ).exists()
        )
        
        # Шаг 2: Назначаем партию
        request = self.factory.post(
            reverse('picker_assign_batch', args=[self.order.id, self.order_item.id]),
            {'batch_id': self.batch.id}
        )
        request.user = self.picker
        response = picker_assign_batch(request, self.order.id, self.order_item.id)
        
        self.order_item.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.order_item.batch, self.batch)
        self.assertEqual(self.batch.remaining_quantity, 40)  # 50 - 10
        
        # Проверяем логирование
        self.assertTrue(
            PickerActionLog.objects.filter(
                picker=self.picker,
                order=self.order,
                action_type='batch_assigned'
            ).exists()
        )
        self.assertTrue(
            BatchAuditLog.objects.filter(
                batch=self.batch,
                action='assigned'
            ).exists()
        )
        
        # Шаг 3: Завершаем сборку
        request = self.factory.post(reverse('picker_complete_order', args=[self.order.id]))
        request.user = self.picker
        response = picker_complete_order(request, self.order.id)
        
        self.picking.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.picking.status, 'completed')
        self.assertEqual(self.order.status, 'ready')
        
        # Проверяем логирование
        self.assertTrue(
            PickerActionLog.objects.filter(
                picker=self.picker,
                order=self.order,
                action_type='order_completed'
            ).exists()
        )
    
    def test_auto_assign_batches_success(self):
        """Тест автоподбора партий"""
        request = self.factory.post(reverse('picker_auto_assign_batches', args=[self.order.id]))
        request.user = self.picker
        response = picker_auto_assign_batches(request, self.order.id)
        
        self.order_item.refresh_from_db()
        self.batch.refresh_from_db()
        self.assertEqual(self.order_item.batch, self.batch)
        self.assertEqual(self.batch.remaining_quantity, 40)
    
    def test_complete_order_fails_without_batch(self):
        """Тест блокировки завершения без назначенной партии"""
        # Не назначаем партию
        request = self.factory.post(reverse('picker_complete_order', args=[self.order.id]))
        request.user = self.picker
        response = picker_complete_order(request, self.order.id)
        
        self.picking.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.picking.status, 'pending')  # Не изменился
        self.assertEqual(self.order.status, 'created')  # Не изменился
    
    def test_complete_order_fails_with_invalid_batch(self):
        """Тест блокировки завершения с партией, не соответствующей правилу 70%"""
        # Создаем партию с 50% срока годности (нельзя продать)
        today = timezone.now().date()
        invalid_batch = ProductBatch.objects.create(
            product=self.product,
            batch_number='BATCH002',
            production_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=10),  # 20 дней всего, 10 осталось = 50%
            quantity=50,
            remaining_quantity=50
        )
        
        # Назначаем невалидную партию
        self.order_item.batch = invalid_batch
        self.order_item.save()
        
        # Пытаемся завершить сборку
        request = self.factory.post(reverse('picker_complete_order', args=[self.order.id]))
        request.user = self.picker
        response = picker_complete_order(request, self.order.id)
        
        self.picking.refresh_from_db()
        self.assertEqual(self.picking.status, 'pending')  # Не изменился
    
    def test_auto_assign_distributes_between_batches(self):
        """Тест автоподбора с распределением между несколькими партиями"""
        # Создаем вторую партию
        today = timezone.now().date()
        batch2 = ProductBatch.objects.create(
            product=self.product,
            batch_number='BATCH002',
            production_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=40),  # 80% осталось
            quantity=30,
            remaining_quantity=30
        )
        
        # Увеличиваем количество в заказе до 60 (больше чем в одной партии)
        self.order_item.quantity = 60
        self.order_item.save()
        
        # Автоподбор должен взять из обеих партий
        request = self.factory.post(reverse('picker_auto_assign_batches', args=[self.order.id]))
        request.user = self.picker
        response = picker_auto_assign_batches(request, self.order.id)
        
        self.order_item.refresh_from_db()
        self.batch.refresh_from_db()
        batch2.refresh_from_db()
        
        # Первая партия должна быть назначена на item
        self.assertEqual(self.order_item.batch, self.batch)
        # Остатки должны уменьшиться
        # (50 из первой + 10 из второй = 60)
        self.assertEqual(self.batch.remaining_quantity, 0)  # 50 - 50 = 0
        self.assertEqual(batch2.remaining_quantity, 20)  # 30 - 10 = 20


