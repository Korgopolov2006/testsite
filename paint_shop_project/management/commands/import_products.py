from django.core.management.base import BaseCommand
from django.core.files import File
from django.utils.text import slugify
from paint_shop_project.models import Category, Manufacturer, Product
from pathlib import Path
import csv


class Command(BaseCommand):
    help = 'Импорт реальных товаров из CSV. Колонки: name,category_slug,price,image_path,old_price,manufacturer(optional),slug(optional)'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Путь к CSV-файлу')
        parser.add_argument('--media-root', type=str, default='media/products', help='Корневая папка для картинок')

    def handle(self, *args, **options):
        csv_path = Path(options['csv_path'])
        media_root = Path(options['media_root'])
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f'CSV не найден: {csv_path}'))
            return
        created_count = 0
        with csv_path.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get('name') or '').strip()
                category_slug = (row.get('category_slug') or '').strip()
                price_str = (row.get('price') or '').strip()
                image_path_rel = (row.get('image_path') or '').strip()
                old_price_str = (row.get('old_price') or '').strip()
                manufacturer_name = (row.get('manufacturer') or '').strip() or None
                slug = (row.get('slug') or '').strip() or slugify(name)[:50]
                if not name or not category_slug or not price_str:
                    self.stderr.write(f'Skip row (required empty): {row}')
                    continue
                try:
                    price = float(price_str.replace(',', '.'))
                except Exception:
                    self.stderr.write(f'Bad price: {price_str}')
                    continue
                old_price = None
                if old_price_str:
                    try:
                        old_price = float(old_price_str.replace(',', '.'))
                    except Exception:
                        old_price = None
                category, _ = Category.objects.get_or_create(slug=category_slug, defaults={'name': category_slug})
                manufacturer = None
                if manufacturer_name:
                    manufacturer, _ = Manufacturer.objects.get_or_create(name=manufacturer_name)
                product, created = Product.objects.get_or_create(
                    slug=slug,
                    defaults={
                        'name': name,
                        'category': category,
                        'manufacturer': manufacturer,
                        'price': price,
                        'old_price': old_price,
                        'stock_quantity': 50,
                        'is_active': True,
                    }
                )
                if created:
                    created_count += 1
                    # Картинка
                    if image_path_rel:
                        image_path = Path(image_path_rel)
                        if not image_path.is_absolute():
                            image_path = media_root / image_path_rel
                        try:
                            with image_path.open('rb') as img:
                                product.image.save(image_path.name, File(img), save=True)
                        except Exception:
                            self.stderr.write(f'Не удалось прикрепить картинку: {image_path}')

        self.stdout.write(self.style.SUCCESS(f'Импорт завершён. Создано: {created_count}'))


