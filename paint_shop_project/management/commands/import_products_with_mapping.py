from django.core.management.base import BaseCommand
from pathlib import Path
import csv
from paint_shop_project.models import Category
from .import_products import Command as ImportProductsBase


class Command(BaseCommand):
    help = 'Импорт товаров с маппингом категорий. mapping.csv: source_slug,target_slug,target_name(optional)'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Путь к CSV-файлу товаров')
        parser.add_argument('mapping_csv', type=str, help='Путь к CSV с маппингом категорий')
        parser.add_argument('--media-root', type=str, default='media/products')

    def handle(self, *args, **opts):
        mapping_path = Path(opts['mapping_csv'])
        if not mapping_path.exists():
            self.stderr.write(self.style.ERROR('Файл маппинга не найден'))
            return
        mapping = {}
        with mapping_path.open('r', encoding='utf-8') as mf:
            r = csv.DictReader(mf)
            for row in r:
                src = (row.get('source_slug') or '').strip()
                tgt = (row.get('target_slug') or '').strip()
                tgt_name = (row.get('target_name') or '').strip() or tgt
                if src and tgt:
                    mapping[src] = (tgt, tgt_name)
        # Применим маппинг: создадим категории и заменим slug в файле товаров на лету
        tmp_rows = []
        products_path = Path(opts['csv_path'])
        with products_path.open('r', encoding='utf-8') as pf:
            pr = csv.DictReader(pf)
            for row in pr:
                src_slug = (row.get('category_slug') or '').strip()
                if src_slug in mapping:
                    tgt_slug, tgt_name = mapping[src_slug]
                    row['category_slug'] = tgt_slug
                    Category.objects.get_or_create(slug=tgt_slug, defaults={'name': tgt_name})
                tmp_rows.append(row)
        # Сохраним во временный CSV и вызовем базовую команду
        tmp_path = products_path.parent / ('__tmp_import.csv')
        if tmp_rows:
            with tmp_path.open('w', encoding='utf-8', newline='') as out:
                w = csv.DictWriter(out, fieldnames=tmp_rows[0].keys())
                w.writeheader()
                w.writerows(tmp_rows)
            base = ImportProductsBase()
            base.handle(csv_path=str(tmp_path), media_root=opts['media_root'])
            tmp_path.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS('Импорт по маппингу завершён'))


