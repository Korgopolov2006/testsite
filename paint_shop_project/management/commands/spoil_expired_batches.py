"""
Django management command для автоматического списания просроченных партий товаров.

Использование:
    python manage.py spoil_expired_batches
    python manage.py spoil_expired_batches --dry-run  # Только показать, что будет списано
    python manage.py spoil_expired_batches --notify   # Отправить уведомления менеджерам

Для автоматического запуска добавьте в crontab:
    0 2 * * * cd /path/to/project && python manage.py spoil_expired_batches
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Q
from django.contrib.auth import get_user_model
from paint_shop_project.models import ProductBatch, Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Списывает просроченные партии товаров и отправляет уведомления менеджерам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Только показать, что будет списано, без фактического списания',
        )
        parser.add_argument(
            '--notify',
            action='store_true',
            help='Отправить уведомления менеджерам о списанных партиях',
        )
        parser.add_argument(
            '--days-overdue',
            type=int,
            default=0,
            help='Списывать партии, просроченные на N дней и более (по умолчанию 0 - все просроченные)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        notify = options['notify']
        days_overdue = options['days_overdue']
        
        today = timezone.now().date()
        expiry_threshold = today - timezone.timedelta(days=days_overdue)
        
        # Находим все просроченные партии с остатком > 0
        expired_batches = ProductBatch.objects.filter(
            expiry_date__lt=expiry_threshold,
            remaining_quantity__gt=0
        ).select_related('product', 'product__category')
        
        total_batches = expired_batches.count()
        total_quantity = expired_batches.aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0
        total_value = 0
        
        if total_batches == 0:
            self.stdout.write(
                self.style.SUCCESS('✅ Нет просроченных партий для списания')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(
                f'\n📦 Найдено просроченных партий: {total_batches}'
            )
        )
        self.stdout.write(
            f'📊 Общий остаток: {total_quantity} единиц'
        )
        
        # Группируем по товарам для отчета
        batches_by_product = {}
        for batch in expired_batches:
            product_name = batch.product.name
            if product_name not in batches_by_product:
                batches_by_product[product_name] = {
                    'batches': [],
                    'total_quantity': 0,
                    'total_value': 0,
                }
            batches_by_product[product_name]['batches'].append(batch)
            batches_by_product[product_name]['total_quantity'] += batch.remaining_quantity
            # Примерная стоимость (можно улучшить, используя реальную цену)
            product_value = float(batch.product.price) * batch.remaining_quantity
            batches_by_product[product_name]['total_value'] += product_value
            total_value += product_value
        
        # Выводим детальный отчет
        self.stdout.write('\n📋 Детали по товарам:')
        for product_name, data in sorted(batches_by_product.items()):
            self.stdout.write(
                f'  • {product_name}: {data["total_quantity"]} ед. '
                f'(~{data["total_value"]:.2f} ₽) - {len(data["batches"])} партий'
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  DRY RUN: Партии НЕ были списаны. '
                    f'Запустите без --dry-run для фактического списания.'
                )
            )
            return
        
        # Списываем партии
        spoiled_count = 0
        spoiled_quantity = 0
        
        for batch in expired_batches:
            old_quantity = batch.remaining_quantity
            batch.remaining_quantity = 0
            batch.save(update_fields=['remaining_quantity'])
            spoiled_count += 1
            spoiled_quantity += old_quantity
            
            # Логируем списание
            from paint_shop_project.models import BatchAuditLog
            BatchAuditLog.objects.create(
                batch=batch,
                action='spoiled',
                old_value=old_quantity,
                new_value=0,
                comment=f'Автоматическое списание просроченной партии (просрочена с {batch.expiry_date})',
                user=None,  # Системное действие
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Списано партий: {spoiled_count}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Списано единиц: {spoiled_quantity}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Примерная стоимость списанного: ~{total_value:.2f} ₽'
            )
        )
        
        # Отправляем уведомления менеджерам
        if notify and spoiled_count > 0:
            self.send_notifications_to_managers(
                spoiled_count, spoiled_quantity, batches_by_product, total_value
            )
    
    def send_notifications_to_managers(self, count, quantity, batches_by_product, total_value):
        """Отправляет уведомления менеджерам о списанных партиях (внутренние + Telegram)"""
        # Находим всех менеджеров (пользователей с ролью, которая может управлять магазином)
        managers = User.objects.filter(
            role__can_manage_store=True,
            is_active=True
        ).distinct()
        
        if not managers.exists():
            self.stdout.write(
                self.style.WARNING('⚠️  Не найдено менеджеров для отправки уведомлений')
            )
            return
        
        # Формируем сообщение
        message_parts = [
            f'📦 <b>Автоматическое списание просроченных партий</b>',
            f'',
            f'Списано партий: <b>{count}</b>',
            f'Списано единиц: <b>{quantity}</b>',
            f'Примерная стоимость: <b>~{total_value:.2f} ₽</b>',
            f'',
            f'<b>Детали по товарам:</b>',
        ]
        
        for product_name, data in sorted(batches_by_product.items())[:10]:  # Первые 10 товаров
            message_parts.append(
                f'  • {product_name}: {data["total_quantity"]} ед.'
            )
        
        if len(batches_by_product) > 10:
            message_parts.append(f'  ... и еще {len(batches_by_product) - 10} товаров')
        
        message = '\n'.join(message_parts)
        message_plain = message.replace('<b>', '').replace('</b>', '')  # Для внутренних уведомлений
        
        # Создаем уведомления для каждого менеджера
        notifications_created = 0
        telegram_sent = 0
        
        try:
            from paint_shop_project.telegram_bot import TelegramNotifier
            telegram_notifier = TelegramNotifier()
            telegram_enabled = telegram_notifier.is_configured()
        except ImportError:
            telegram_enabled = False
            telegram_notifier = None
        
        for manager in managers:
            # Внутреннее уведомление в системе
            Notification.objects.create(
                user=manager,
                title='Списание просроченных партий',
                message=message_plain,
                notification_type='system',
                is_read=False,
            )
            notifications_created += 1
            
            # Отправка в Telegram (если настроено)
            if telegram_enabled and manager.telegram_chat_id and manager.telegram_notifications_enabled:
                try:
                    chat_id = int(manager.telegram_chat_id)
                    if telegram_notifier.send_message(chat_id, message):
                        telegram_sent += 1
                except (ValueError, TypeError):
                    self.stdout.write(
                        self.style.WARNING(
                            f'⚠️  Неверный Telegram chat_id для пользователя {manager.username}'
                        )
                    )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'📧 Отправлено внутренних уведомлений: {notifications_created}'
            )
        )
        if telegram_enabled:
            self.stdout.write(
                self.style.SUCCESS(
                    f'📱 Отправлено Telegram уведомлений: {telegram_sent}'
                )
            )

