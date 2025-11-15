from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from paint_shop_project.models import Category, Manufacturer, Product
import requests
from decimal import Decimal


PUBLIC_PRODUCTS = [
    # name, category_slug, price, image_url, manufacturer
    ("Молоко Домик в деревне 3.2% 1л", "milk-products", 89.90, "https://upload.wikimedia.org/wikipedia/commons/7/72/Milk_pack.jpg", "Домик в деревне"),
    ("Йогурт питьевой Активиа клубника 290мл", "milk-products", 64.90, "https://upload.wikimedia.org/wikipedia/commons/f/f8/Yogurt.jpg", "Danone"),
    ("Хлеб Батон нарезной 400г", "bread-bakery", 39.90, "https://upload.wikimedia.org/wikipedia/commons/0/0f/Loaf-Bread.jpg", "Жевжик Пекарня"),
    ("Багет французский 300г", "bread-bakery", 59.90, "https://upload.wikimedia.org/wikipedia/commons/6/6b/Baguette.jpg", "Жевжик Пекарня"),
    ("Яблоки Гала 1кг", "vegetables-fruits", 149.90, "https://upload.wikimedia.org/wikipedia/commons/1/15/Red_Apple.jpg", "Свежие овощи"),
    ("Огурцы грунтовые 500г", "vegetables-fruits", 89.90, "https://upload.wikimedia.org/wikipedia/commons/0/08/Cucumber.jpg", "Свежие овощи"),
    ("Куриное филе охлаждённое 1кг", "meat-poultry", 289.90, "https://upload.wikimedia.org/wikipedia/commons/7/7b/Chicken_breast.jpg", "Жевжик Ферма"),
    ("Свинина шея 1кг", "meat-poultry", 359.90, "https://upload.wikimedia.org/wikipedia/commons/8/8f/Raw_pork.jpg", "Жевжик Ферма"),
    ("Апельсиновый сок 1л", "beverages", 119.90, "https://upload.wikimedia.org/wikipedia/commons/0/05/Orange_juice_1.jpg", "Жевжик Напитки"),
    ("Вода питьевая негазированная 1.5л", "beverages", 39.90, "https://upload.wikimedia.org/wikipedia/commons/0/0b/Water_bottle.jpg", "Жевжик Напитки"),
    ("Печенье овсяное 300г", "sweets", 79.90, "https://upload.wikimedia.org/wikipedia/commons/1/1e/Oatmeal_cookies.jpg", "Жевжик Кондитер"),
    ("Шоколад молочный 90г", "sweets", 99.90, "https://upload.wikimedia.org/wikipedia/commons/7/70/Chocolate_%28blue_background%29.jpg", "Жевжик Кондитер"),
    ("Мороженое пломбир 80г", "frozen-food", 69.90, "https://upload.wikimedia.org/wikipedia/commons/3/35/Ice_cream_cone.jpg", "Жевжик Кондитер"),
]


class Command(BaseCommand):
    help = "Импорт публичных демо‑товаров с картинками (Wikimedia/общедоступные изображения)"

    def handle(self, *args, **options):
        created = 0
        for name, cat_slug, price, img_url, manuf_name in PUBLIC_PRODUCTS:
            category, _ = Category.objects.get_or_create(slug=cat_slug, defaults={"name": cat_slug})
            manufacturer = None
            if manuf_name:
                manufacturer, _ = Manufacturer.objects.get_or_create(name=manuf_name)
            slug = slugify(name)[:50]
            product, was_created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'category': category,
                    'manufacturer': manufacturer,
                    'price': Decimal(str(price)),
                    'stock_quantity': 100,
                    'is_active': True,
                }
            )
            if was_created and img_url:
                try:
                    resp = requests.get(img_url, timeout=15)
                    if resp.ok:
                        product.image.save(slug + '.jpg', ContentFile(resp.content), save=True)
                except Exception:
                    pass
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Импортировано товаров: {created}'))


