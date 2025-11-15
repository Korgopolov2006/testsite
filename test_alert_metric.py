#!/usr/bin/env python
"""
Скрипт для тестирования метрики заказов и демонстрации Alert Rules
Использование: python test_alert_metric.py
"""
import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paint_shop.settings')
django.setup()

from paint_shop_project.models import Order, User
from paint_shop_project.prometheus_metrics import update_business_metrics
from django.utils import timezone
from decimal import Decimal


def get_today_orders_count():
    """Получить количество заказов за сегодня"""
    return Order.objects.filter(order_date__date=timezone.now().date()).count()


def create_test_order(user=None):
    """Создать тестовый заказ"""
    if user is None:
        user = User.objects.filter(is_staff=False).first()
        if user is None:
            print("Ошибка: нет пользователей для создания заказа")
            return None
    
    try:
        order = Order.objects.create(
            user=user,
            order_date=timezone.now(),
            status='created',
            delivery_type='pickup',
            total_amount=Decimal('1000.00'),
            delivery_cost=Decimal('0.00'),
            discount=Decimal('0.00'),
        )
        return order
    except Exception as e:
        print(f"Ошибка создания заказа: {e}")
        return None


def delete_today_orders(count=None):
    """Удалить заказы за сегодня"""
    today_orders = Order.objects.filter(order_date__date=timezone.now().date())
    
    if count is None:
        # Удалить все заказы за сегодня
        deleted_count = today_orders.count()
        today_orders.delete()
        return deleted_count
    else:
        # Удалить указанное количество
        orders_to_delete = today_orders[:count]
        deleted_count = orders_to_delete.count()
        orders_to_delete.delete()
        return deleted_count


def test_alert_scenarios():
    """Тестирование различных сценариев alert"""
    
    print("=" * 60)
    print("Тестирование Alert Rules для метрики zhevzhik_orders_today")
    print("=" * 60)
    
    # Получаем текущее количество заказов
    current_count = get_today_orders_count()
    print(f"\nТекущее количество заказов за сегодня: {current_count}")
    
    # Сценарий 1: Нормальное состояние
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 1: Нормальное состояние (Normal)")
    print("=" * 60)
    print("Цель: Метрика < 50 заказов")
    
    if current_count >= 50:
        print(f"\nТекущее значение ({current_count}) >= 50. Удаляем лишние заказы...")
        delete_today_orders(current_count - 10)
        current_count = get_today_orders_count()
        print(f"Удалено. Теперь заказов: {current_count}")
    
    update_business_metrics()
    print(f"\n✅ Метрика обновлена: {current_count} заказов")
    print("📊 Проверьте в Grafana:")
    print("   - Alerting → Alert rules")
    print("   - Статус должен быть: Normal (зелёный)")
    print("   - Панель должна показывать значение < 50")
    
    input("\nНажмите Enter для перехода к следующему сценарию...")
    
    # Сценарий 2: Превышение порога (Pending)
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 2: Превышение порога (Pending)")
    print("=" * 60)
    print("Цель: Метрика > 50 заказов, но ещё не прошло 5 минут")
    
    target_count = 55
    needed = target_count - current_count
    
    if needed > 0:
        print(f"\nСоздаём {needed} заказов для достижения порога 50...")
        for i in range(needed):
            order = create_test_order()
            if order:
                print(f"  Создан заказ #{order.id}")
            else:
                print(f"  Ошибка создания заказа #{i+1}")
    
    current_count = get_today_orders_count()
    update_business_metrics()
    
    print(f"\n✅ Метрика обновлена: {current_count} заказов")
    print("📊 Проверьте в Grafana:")
    print("   - Alerting → Alert rules")
    print("   - Статус должен быть: Pending (жёлтый) ⏳")
    print("   - Таймер должен показывать время до Firing (~5 минут)")
    print("   - Панель должна показывать значение > 50")
    
    print("\n⏱️  Подождите 5 минут для перехода в Firing...")
    print("   (Или измените For период в Alert Rule на 1 минуту для быстрого теста)")
    
    input("\nНажмите Enter для перехода к следующему сценарию (или подождите 5 минут)...")
    
    # Сценарий 3: Firing (если прошло достаточно времени)
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 3: Alert Firing")
    print("=" * 60)
    print("Цель: Метрика > 50 заказов и прошло 5+ минут")
    
    current_count = get_today_orders_count()
    update_business_metrics()
    
    print(f"\n✅ Метрика: {current_count} заказов")
    print("📊 Проверьте в Grafana:")
    print("   - Alerting → Alert rules")
    if current_count > 50:
        print("   - Статус должен быть: Firing (красный) 🔴")
        print("   - Alerting → Alerts должен показывать активный alert")
    else:
        print("   - ⚠️  Внимание: количество заказов < 50. Увеличьте до 55+")
    
    input("\nНажмите Enter для перехода к следующему сценарию...")
    
    # Сценарий 4: Resolved
    print("\n" + "=" * 60)
    print("СЦЕНАРИЙ 4: Alert Resolved")
    print("=" * 60)
    print("Цель: Метрика вернулась к нормальному значению (< 50)")
    
    current_count = get_today_orders_count()
    if current_count > 50:
        print(f"\nТекущее значение ({current_count}) > 50. Удаляем лишние заказы...")
        delete_today_orders(current_count - 10)
        current_count = get_today_orders_count()
        print(f"Удалено. Теперь заказов: {current_count}")
    
    update_business_metrics()
    
    print(f"\n✅ Метрика обновлена: {current_count} заказов")
    print("📊 Проверьте в Grafana:")
    print("   - Alerting → Alert rules")
    print("   - Статус должен быть: Normal (зелёный) ✅")
    print("   - Alerting → Alerts")
    print("   - Статус alert должен быть: Resolved")
    print("   - Alerting → Alert history")
    print("   - Должна быть запись о переходе из Firing в Resolved")
    
    print("\n" + "=" * 60)
    print("✅ Тестирование завершено!")
    print("=" * 60)
    print("\nРезюме:")
    print("  ✅ Normal: Метрика < 50")
    print("  ✅ Pending: Метрика > 50, ожидание 5 минут")
    print("  ✅ Firing: Метрика > 50, прошло 5+ минут")
    print("  ✅ Resolved: Метрика вернулась < 50")


if __name__ == '__main__':
    try:
        test_alert_scenarios()
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    except Exception as e:
        print(f"\n\nОшибка: {e}")
        import traceback
        traceback.print_exc()

