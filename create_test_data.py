#!/usr/bin/env python
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paint_shop.settings')
django.setup()

from paint_shop_project.models import *
from django.utils import timezone
from datetime import timedelta

def create_test_promotions():
    """Создание тестовых акций"""
    print("Создание тестовых акций...")
    
    # Удаляем существующие акции
    Promotion.objects.all().delete()
    
    # Создаем новые акции
    promotion1 = Promotion.objects.create(
        name='Скидка 10% на первый заказ',
        description='Специальное предложение для новых клиентов! Получите скидку 10% на первый заказ.',
        discount_type='percentage',
        discount_value=10,
        min_order_amount=1000,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=30),
        is_active=True
    )
    
    promotion2 = Promotion.objects.create(
        name='Скидка 500₽ при заказе от 3000₽',
        description='Экономите 500 рублей при заказе на сумму от 3000 рублей.',
        discount_type='fixed',
        discount_value=500,
        min_order_amount=3000,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=15),
        is_active=True
    )
    
    promotion3 = Promotion.objects.create(
        name='Скидка 15% на молочные продукты',
        description='Специальная скидка на все молочные продукты в нашем магазине.',
        discount_type='percentage',
        discount_value=15,
        min_order_amount=500,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=7),
        is_active=True
    )
    
    print(f"✅ Создано {Promotion.objects.count()} акций:")
    for promotion in Promotion.objects.all():
        print(f"   - {promotion.name} ({promotion.discount_value}{'%' if promotion.discount_type == 'percentage' else '₽'})")

if __name__ == '__main__':
    create_test_promotions()
