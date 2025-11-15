from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

from paint_shop_project.models import (
    Category,
    Product,
    Promotion,
    Order,
    OrderItem,
    OrderStatusHistory,
    FavoriteCategory,
)


User = get_user_model()


class Command(BaseCommand):
    help = "Создает демо-акции и демо-заказы с историей статусов для презентации"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n▶ Создание демо-данных..."))

        # 1) Пользователь
        user, _ = User.objects.get_or_create(username="demo", defaults={
            "email": "demo@example.com",
        })
        if not user.password:
            user.set_password("demo12345")
            user.save()
        self.stdout.write(self.style.SUCCESS(f"✔ Пользователь: {user.username}"))

        # 2) Категория
        category, _ = Category.objects.get_or_create(
            name="Демо категория",
            defaults={"slug": "demo-category"}
        )
        self.stdout.write(self.style.SUCCESS(f"✔ Категория: {category.name}"))

        # 3) Товары
        product1, _ = Product.objects.get_or_create(
            name="Демо товар 1",
            defaults={
                "slug": "demo-product-1",
                "category": category,
                "price": Decimal("199.90"),
                "stock_quantity": 50,
                "is_active": True,
            }
        )
        product2, _ = Product.objects.get_or_create(
            name="Демо товар 2",
            defaults={
                "slug": "demo-product-2",
                "category": category,
                "price": Decimal("349.90"),
                "stock_quantity": 25,
                "is_active": True,
            }
        )
        product3, _ = Product.objects.get_or_create(
            name="Демо товар 3",
            defaults={
                "slug": "demo-product-3",
                "category": category,
                "price": Decimal("129.90"),
                "stock_quantity": 100,
                "is_active": True,
            }
        )
        self.stdout.write(self.style.SUCCESS("✔ Товары созданы"))

        # 4) Акции
        now = timezone.now()
        promo1, _ = Promotion.objects.get_or_create(
            name="Скидка 10% на заказ от 1000",
            defaults={
                "description": "Промо для презентации",
                "discount_type": "percentage",
                "discount_value": Decimal("10.0"),
                "min_order_amount": Decimal("1000.00"),
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=14),
                "is_active": True,
            }
        )
        promo2, _ = Promotion.objects.get_or_create(
            name="-200 ₽ при заказе от 1500",
            defaults={
                "description": "Фиксированная скидка",
                "discount_type": "fixed",
                "discount_value": Decimal("200.00"),
                "min_order_amount": Decimal("1500.00"),
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=7),
                "is_active": True,
            }
        )
        promo3, _ = Promotion.objects.get_or_create(
            name="Всё по 129 ₽ на выбор",
            defaults={
                "description": "Флеш-распродажа демо",
                "discount_type": "fixed",
                "discount_value": Decimal("129.00"),
                "min_order_amount": Decimal("500.00"),
                "start_date": now - timedelta(days=1),
                "end_date": now + timedelta(days=3),
                "is_active": True,
            }
        )
        self.stdout.write(self.style.SUCCESS("✔ Акции активны"))

        # 5) Любимые категории (для скидок/кешбэка)
        FavoriteCategory.objects.get_or_create(user=user, category=category)

        # 6) Заказ #1 с историей (в пути)
        order, created_order = Order.objects.get_or_create(
            user=user,
            status="created",
            defaults={
                "delivery_type": "delivery",
                "delivery_address": "Москва, ул. Презентационная, д. 1",
                "total_amount": Decimal("0.00"),
                "payment_method": "card",
                "courier_name": "Иван Курьеров",
                "courier_phone": "+7 900 000-00-00",
                "tracking_number": "TRK123456",
                "estimated_delivery_time": now + timedelta(hours=4),
            }
        )

        # Позиции заказа
        if created_order or order.items.count() == 0:
            OrderItem.objects.create(order=order, product=product1, quantity=2, price_per_unit=product1.price)
            OrderItem.objects.create(order=order, product=product2, quantity=1, price_per_unit=product2.price)
            order.total_amount = sum(i.total_price for i in order.items.all())
            order.save()

        # История статусов
        if order.status_history.count() == 0:
            OrderStatusHistory.objects.create(order=order, status="created", comment="Заказ создан", timestamp=now - timedelta(hours=3, minutes=50))
            OrderStatusHistory.objects.create(order=order, status="confirmed", comment="Подтвержден магазином", timestamp=now - timedelta(hours=3))
            OrderStatusHistory.objects.create(order=order, status="ready", comment="Собран на складе", timestamp=now - timedelta(hours=2))
            OrderStatusHistory.objects.create(order=order, status="in_transit", comment="Передан курьеру", courier_name=order.courier_name, courier_phone=order.courier_phone, timestamp=now - timedelta(minutes=30))

        self.stdout.write(self.style.SUCCESS(f"✔ Заказ #{order.id} подготовлен (в пути)"))

        # 7) Заказ #2 доставлен
        order2, created_order2 = Order.objects.get_or_create(
            user=user,
            status="delivered",
            defaults={
                "delivery_type": "delivery",
                "delivery_address": "Москва, пр-т Примерный, д. 2",
                "total_amount": Decimal("0.00"),
                "payment_method": "card",
                "courier_name": "Петр Курьеров",
                "courier_phone": "+7 900 000-00-01",
                "tracking_number": "TRK654321",
                "estimated_delivery_time": now - timedelta(hours=1),
                "actual_delivery_time": now - timedelta(minutes=10),
            }
        )
        if created_order2 or order2.items.count() == 0:
            OrderItem.objects.get_or_create(order=order2, product=product2, defaults={"quantity": 1, "price_per_unit": product2.price})
            OrderItem.objects.get_or_create(order=order2, product=product1, defaults={"quantity": 1, "price_per_unit": product1.price})
            order2.total_amount = sum(i.total_price for i in order2.items.all())
            order2.save()
        if order2.status_history.count() == 0:
            OrderStatusHistory.objects.create(order=order2, status="created", timestamp=now - timedelta(hours=4))
            OrderStatusHistory.objects.create(order=order2, status="confirmed", timestamp=now - timedelta(hours=3, minutes=30))
            OrderStatusHistory.objects.create(order=order2, status="ready", timestamp=now - timedelta(hours=2, minutes=45))
            OrderStatusHistory.objects.create(order=order2, status="in_transit", courier_name=order2.courier_name, courier_phone=order2.courier_phone, timestamp=now - timedelta(hours=1, minutes=30))
            OrderStatusHistory.objects.create(order=order2, status="delivered", comment="Доставлен покупателю", timestamp=now - timedelta(minutes=10))
        self.stdout.write(self.style.SUCCESS(f"✔ Заказ #{order2.id} подготовлен (доставлен)"))

        # 8) Заказ #3 самовывоз, готов
        order3, created_order3 = Order.objects.get_or_create(
            user=user,
            status="ready",
            defaults={
                "delivery_type": "pickup",
                "delivery_address": "Пункт самовывоза №1",
                "total_amount": Decimal("0.00"),
                "payment_method": "cash",
                "tracking_number": "PICK000777",
            }
        )
        if created_order3 or order3.items.count() == 0:
            OrderItem.objects.get_or_create(order=order3, product=product3, defaults={"quantity": 3, "price_per_unit": product3.price})
            order3.total_amount = sum(i.total_price for i in order3.items.all())
            order3.save()
        if order3.status_history.count() == 0:
            OrderStatusHistory.objects.create(order=order3, status="created", timestamp=now - timedelta(hours=2))
            OrderStatusHistory.objects.create(order=order3, status="confirmed", timestamp=now - timedelta(hours=1, minutes=40))
            OrderStatusHistory.objects.create(order=order3, status="ready", comment="Ожидает на стойке", timestamp=now - timedelta(minutes=15))
        self.stdout.write(self.style.SUCCESS(f"✔ Заказ #{order3.id} подготовлен (самовывоз, готов)"))

        self.stdout.write(self.style.HTTP_INFO("Готово. Войдите пользователем demo/demo12345 и проверьте /order-tracking/<id>/ и /api/order/<id>/tracking/ для нескольких заказов."))


