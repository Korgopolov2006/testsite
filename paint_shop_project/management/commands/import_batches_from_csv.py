"""
Django management command для массового импорта партий товаров из CSV файла
"""
import csv
import logging
from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from paint_shop_project.models import Product, ProductBatch, BatchAuditLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Импортирует партии товаров из CSV файла'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Путь к CSV файлу с партиями',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Проверка без фактического импорта',
        )
        parser.add_argument(
            '--skip-errors',
            action='store_true',
            help='Пропускать строки с ошибками и продолжать импорт',
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        dry_run = options['dry_run']
        skip_errors = options['skip_errors']
        
        self.stdout.write(self.style.SUCCESS('🚀 Начало импорта партий из CSV...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('--- Режим "Сухой прогон" ---'))
        
        # Ожидаемый формат CSV:
        # product_id,batch_number,production_date,expiry_date,quantity,supplier
        # 1,BATCH001,2024-01-01,2024-12-31,100,Поставщик А
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Проверяем наличие обязательных колонок
                required_columns = ['product_id', 'production_date', 'expiry_date', 'quantity']
                missing_columns = [col for col in required_columns if col not in reader.fieldnames]
                if missing_columns:
                    raise CommandError(
                        f'В CSV файле отсутствуют обязательные колонки: {", ".join(missing_columns)}'
                    )
                
                imported_count = 0
                skipped_count = 0
                errors = []
                
                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):  # Начинаем с 2, т.к. первая строка - заголовки
                        try:
                            # Парсим данные
                            product_id = int(row['product_id'])
                            batch_number = row.get('batch_number', '').strip()
                            production_date_str = row['production_date'].strip()
                            expiry_date_str = row['expiry_date'].strip()
                            quantity = int(row['quantity'])
                            supplier = row.get('supplier', '').strip()
                            
                            # Парсим даты
                            try:
                                production_date = datetime.strptime(production_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValueError(f'Неверный формат даты производства: {production_date_str}. Ожидается YYYY-MM-DD')
                            
                            try:
                                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
                            except ValueError:
                                raise ValueError(f'Неверный формат срока годности: {expiry_date_str}. Ожидается YYYY-MM-DD')
                            
                            # Валидация дат
                            if production_date >= expiry_date:
                                raise ValueError('Дата производства должна быть раньше срока годности')
                            
                            if expiry_date < timezone.now().date():
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Строка {row_num}: Партия с истекшим сроком годности ({expiry_date_str})'
                                    )
                                )
                            
                            # Проверяем существование товара
                            try:
                                product = Product.objects.get(id=product_id)
                            except Product.DoesNotExist:
                                raise ValueError(f'Товар с ID {product_id} не найден')
                            
                            # Проверяем, что товар имеет срок годности
                            if not product.has_expiry_date:
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Строка {row_num}: Товар {product.name} (ID: {product_id}) не имеет срока годности'
                                    )
                                )
                            
                            # Генерируем номер партии, если не указан
                            if not batch_number:
                                batch_number = f"CSV-{product_id}-{production_date.strftime('%Y%m%d')}"
                            
                            # Проверяем уникальность номера партии
                            if ProductBatch.objects.filter(batch_number=batch_number).exists():
                                counter = 1
                                original_batch_number = batch_number
                                while ProductBatch.objects.filter(batch_number=batch_number).exists():
                                    batch_number = f"{original_batch_number}-{counter}"
                                    counter += 1
                                self.stdout.write(
                                    self.style.WARNING(
                                        f'Строка {row_num}: Номер партии "{original_batch_number}" уже существует, используется "{batch_number}"'
                                    )
                                )
                            
                            if not dry_run:
                                # Создаем партию
                                batch = ProductBatch.objects.create(
                                    product=product,
                                    batch_number=batch_number,
                                    production_date=production_date,
                                    expiry_date=expiry_date,
                                    quantity=quantity,
                                    remaining_quantity=quantity,
                                    supplier=supplier or 'Импорт из CSV',
                                )
                                
                                # Логируем создание
                                BatchAuditLog.objects.create(
                                    batch=batch,
                                    action='created',
                                    old_value=None,
                                    new_value=quantity,
                                    comment=f'Импортировано из CSV файла (строка {row_num})',
                                )
                            
                            imported_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'Строка {row_num}: Импортирована партия {batch_number} для товара {product.name} (количество: {quantity})'
                                )
                            )
                            
                        except Exception as e:
                            error_msg = f'Строка {row_num}: {str(e)}'
                            errors.append(error_msg)
                            
                            if skip_errors:
                                self.stdout.write(self.style.ERROR(error_msg))
                                skipped_count += 1
                                continue
                            else:
                                raise CommandError(error_msg)
                
                # Выводим итоги
                self.stdout.write(self.style.SUCCESS('\n' + '='*50))
                self.stdout.write(self.style.SUCCESS(f'✅ Импортировано партий: {imported_count}'))
                if skipped_count > 0:
                    self.stdout.write(self.style.WARNING(f'⚠️  Пропущено строк: {skipped_count}'))
                if errors and skip_errors:
                    self.stdout.write(self.style.ERROR(f'❌ Ошибок: {len(errors)}'))
                    self.stdout.write('\nОшибки:')
                    for error in errors:
                        self.stdout.write(self.style.ERROR(f'  - {error}'))
                
                if dry_run:
                    self.stdout.write(self.style.WARNING('\n--- Сухой прогон завершен. Изменения не применены. ---'))
                
        except FileNotFoundError:
            raise CommandError(f'Файл не найден: {csv_file_path}')
        except Exception as e:
            raise CommandError(f'Ошибка при импорте: {str(e)}')
        
        self.stdout.write(self.style.SUCCESS('✨ Импорт завершен.'))


