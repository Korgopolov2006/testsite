from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from paint_shop_project.models import Role, Category, Product, Promotion, Manufacturer, Store
from datetime import datetime, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Заполняет базу данных тестовыми данными'

    def handle(self, *args, **options):
        # Создаем роли
        roles_data = [
            {'name': 'admin', 'description': 'Администратор системы'},
            {'name': 'manager', 'description': 'Менеджер магазина'},
            {'name': 'courier', 'description': 'Курьер'},
            {'name': 'customer', 'description': 'Покупатель'},
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )
            if created:
                self.stdout.write(f'Создана роль: {role.get_name_display()}')

        # Создаем производителей
        manufacturers_data = [
            {'name': 'Шарлиз', 'email': 'info@charlize.ru'},
            {'name': 'Dolce Granto', 'email': 'info@dolcegranto.com'},
            {'name': 'Домик в деревне', 'email': 'info@domik-v-derevne.ru'},
            {'name': 'Свежие овощи', 'email': 'info@fresh-vegetables.ru'},
        ]

        for manuf_data in manufacturers_data:
            manufacturer, created = Manufacturer.objects.get_or_create(
                name=manuf_data['name'],
                defaults={'email': manuf_data['email']}
            )
            if created:
                self.stdout.write(f'Создан производитель: {manufacturer.name}')

        # Создаем категории
        categories_data = [
            {'name': 'Молочные продукты', 'slug': 'milk-products'},
            {'name': 'Мясо и птица', 'slug': 'meat-poultry'},
            {'name': 'Овощи и фрукты', 'slug': 'vegetables-fruits'},
            {'name': 'Хлеб и выпечка', 'slug': 'bread-bakery'},
            {'name': 'Напитки', 'slug': 'beverages'},
            {'name': 'Консервы', 'slug': 'canned-food'},
            {'name': 'Сладости', 'slug': 'sweets'},
            {'name': 'Замороженные продукты', 'slug': 'frozen-food'},
        ]

        for cat_data in categories_data:
            category, created = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={'name': cat_data['name']}
            )
            if created:
                self.stdout.write(f'Создана категория: {category.name}')

        # Создаем магазины
        stores_data = [
            {
                'name': 'Жевжик на Свинской',
                'address': 'Москва, ул. Свинская, 42',
                'phone': '+7 (495) 123-45-67',
                'working_hours': '8:00 - 23:00',
            },
            {
                'name': 'Жевжик на Хрюшкиной',
                'address': 'Москва, ул. Хрюшкина, 15',
                'phone': '+7 (495) 234-56-78',
                'working_hours': '8:00 - 23:00',
            },
        ]

        # Создаем тестового менеджера
        manager_role = Role.objects.get(name='manager')
        manager, created = User.objects.get_or_create(
            username='manager1',
            defaults={
                'email': 'manager@zhevzhik.ru',
                'first_name': 'Иван',
                'last_name': 'Менеджеров',
                'role': manager_role,
                'phone': '+7 (495) 111-11-11',
            }
        )
        if created:
            manager.set_password('manager123')
            manager.save()
            self.stdout.write(f'Создан менеджер: {manager.username}')

        for store_data in stores_data:
            store, created = Store.objects.get_or_create(
                name=store_data['name'],
                defaults={
                    'address': store_data['address'],
                    'phone': store_data['phone'],
                    'working_hours': store_data['working_hours'],
                    'manager': manager,
                }
            )
            if created:
                self.stdout.write(f'Создан магазин: {store.name}')

        # Создаем продукты
        products_data = [
            {
                'name': 'Палочки сдобные Шарлиз Снежка с малиновым джемом',
                'slug': 'charlize-snezka-raspberry',
                'category_slug': 'sweets',
                'manufacturer_name': 'Шарлиз',
                'price': 89.90,
                'old_price': 105.90,
                'weight': '370 г',
                'rating': 4.89,
                'is_featured': True,
                'stock_quantity': 50,
            },
            {
                'name': 'Сдобные палочки Шарлиз Снежка с абрикосовым джемом',
                'slug': 'charlize-snezka-apricot',
                'category_slug': 'sweets',
                'manufacturer_name': 'Шарлиз',
                'price': 89.90,
                'old_price': 105.90,
                'weight': '370 г',
                'rating': 4.88,
                'is_featured': True,
                'stock_quantity': 45,
            },
            {
                'name': 'Сыр Dolce Granto Пармезан тертый 40% БЗМЖ',
                'slug': 'dolce-granto-parmesan',
                'category_slug': 'milk-products',
                'manufacturer_name': 'Dolce Granto',
                'price': 199.90,
                'old_price': 299.90,
                'weight': '150 г',
                'rating': 4.85,
                'is_featured': True,
                'stock_quantity': 30,
            },
            {
                'name': 'Томаты Медовые черри красные круглые',
                'slug': 'honey-cherry-tomatoes',
                'category_slug': 'vegetables-fruits',
                'manufacturer_name': 'Свежие овощи',
                'price': 149.90,
                'old_price': 195.90,
                'weight': '200 г',
                'rating': 4.89,
                'is_featured': True,
                'stock_quantity': 25,
            },
            {
                'name': 'Хурма',
                'slug': 'persimmon',
                'category_slug': 'vegetables-fruits',
                'manufacturer_name': 'Свежие овощи',
                'price': 299.90,
                'old_price': 359.90,
                'weight': 'Цена за 1 кг',
                'rating': 4.78,
                'is_featured': True,
                'stock_quantity': 20,
            },
            {
                'name': 'Молоко Домик в деревне 3.2%',
                'slug': 'domik-v-derevne-milk',
                'category_slug': 'milk-products',
                'manufacturer_name': 'Домик в деревне',
                'price': 89.90,
                'old_price': None,
                'weight': '1 л',
                'rating': 4.75,
                'is_featured': True,
                'stock_quantity': 100,
            },
        ]

        # Дополняем ~40 товаров по категориям
        extra_products = []
        def add_items(prefix, slug_prefix, category_slug, manufacturer, base_price, count):
            for i in range(1, count+1):
                extra_products.append({
                    'name': f'{prefix} #{i}',
                    'slug': f'{slug_prefix}-{i}',
                    'category_slug': category_slug,
                    'manufacturer_name': manufacturer,
                    'price': round(base_price + (i % 7) * 5.5, 2),
                    'old_price': None,
                    'weight': '500 г',
                    'rating': 4.5,
                    'is_featured': False,
                    'stock_quantity': 30 + (i % 10),
                })

        add_items('Молоко ультрапастеризованное', 'milk-up', 'milk-products', 'Домик в деревне', 79.9, 8)
        add_items('Йогурт питьевой', 'yogurt-drink', 'milk-products', 'Домик в деревне', 49.9, 6)
        add_items('Куриное филе охлажденное', 'chicken-fillet', 'meat-poultry', 'Шарлиз', 249.9, 6)
        add_items('Свинина шея', 'pork-neck', 'meat-poultry', 'Шарлиз', 329.9, 4)
        add_items('Яблоки сезонные', 'apple-fresh', 'vegetables-fruits', 'Свежие овощи', 99.9, 6)
        add_items('Огурцы грунтовые', 'cucumber-ground', 'vegetables-fruits', 'Свежие овощи', 89.9, 4)
        add_items('Хлеб пшеничный', 'bread-wheat', 'bread-bakery', 'Шарлиз', 39.9, 3)
        add_items('Булочки с корицей', 'bun-cinnamon', 'bread-bakery', 'Шарлиз', 59.9, 3)
        add_items('Сок апельсиновый', 'juice-orange', 'beverages', 'Dolce Granto', 119.9, 4)
        add_items('Вода негазированная', 'water-still', 'beverages', 'Dolce Granto', 39.9, 4)
        add_items('Печенье овсяное', 'cookies-oat', 'sweets', 'Шарлиз', 69.9, 4)
        add_items('Мороженое пломбир', 'icecream-plombir', 'frozen-food', 'Dolce Granto', 129.9, 4)

        products_data.extend(extra_products)

        for prod_data in products_data:
            category = Category.objects.get(slug=prod_data['category_slug'])
            manufacturer = Manufacturer.objects.get(name=prod_data['manufacturer_name'])
            product, created = Product.objects.get_or_create(
                slug=prod_data['slug'],
                defaults={
                    'name': prod_data['name'],
                    'category': category,
                    'manufacturer': manufacturer,
                    'price': prod_data['price'],
                    'old_price': prod_data['old_price'],
                    'weight': prod_data['weight'],
                    'rating': prod_data['rating'],
                    'is_featured': prod_data['is_featured'],
                    'stock_quantity': prod_data['stock_quantity'],
                }
            )
            if created:
                self.stdout.write(f'Создан продукт: {product.name}')

        # Создаем акции
        promotions_data = [
            {
                'name': 'Скидка 500 ₽ на первый заказ от 1500 ₽',
                'description': 'Получите скидку 500 рублей на ваш первый заказ при сумме покупки от 1500 рублей',
            },
            {
                'name': 'Бесплатная доставка от 2000 ₽',
                'description': 'Закажите на сумму от 2000 рублей и получите бесплатную доставку',
            },
            {
                'name': 'Скидки до 50% на молочные продукты',
                'description': 'Специальные цены на молочные продукты и сыры',
            },
        ]

        for promo_data in promotions_data:
            promotion, created = Promotion.objects.get_or_create(
                name=promo_data['name'],
                defaults={'description': promo_data['description']}
            )
            if created:
                self.stdout.write(f'Создана акция: {promotion.name}')

        self.stdout.write(
            self.style.SUCCESS('Тестовые данные успешно добавлены!')
        )
