"""
Celery задачи для автоматизации резервного копирования
"""
import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone

from paint_shop_project.admin_views.database import perform_backup, _get_backup_root
from .models import DatabaseBackup

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='create_scheduled_backup')
def create_scheduled_backup(self, comment=None):
    """
    Создает автоматическую резервную копию базы данных.
    
    Args:
        comment: Опциональный комментарий для бэкапа
    
    Returns:
        dict: Результат операции
    """
    start_time = timezone.now()
    backup_path = None
    
    try:
        logger.info("Starting scheduled database backup")
        
        # Создаем бэкап в стандартной папке с подпапкой по дате
        today = timezone.localtime().strftime("%Y-%m-%d")
        backup_path = perform_backup(
            label="scheduled",
            folder_name=f"auto_{today}",
            comment=comment or f"Автоматический бэкап от {start_time.strftime('%d.%m.%Y %H:%M')}",
        )
        
        # Получаем запись из истории
        backup_record = DatabaseBackup.objects.filter(
            file_path=str(backup_path),
            operation='backup',
            status='success'
        ).order_by('-started_at').first()
        
        file_size = backup_path.stat().st_size if backup_path.exists() else 0
        duration = (timezone.now() - start_time).total_seconds()
        
        result = {
            'status': 'success',
            'file_path': str(backup_path),
            'file_size': file_size,
            'duration_seconds': duration,
            'backup_record_id': backup_record.id if backup_record else None,
        }
        
        logger.info(
            "Scheduled backup completed successfully: %s (%.2f MB, %.1f sec)",
            backup_path.name,
            file_size / (1024 * 1024),
            duration
        )
        
        # Отправляем уведомление администраторам
        if getattr(settings, 'BACKUP_ENABLE_NOTIFICATIONS', True):
            try:
                send_backup_notification(result)
            except Exception as exc:
                logger.error("Failed to send backup notification: %s", exc)
        
        return result
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error("Scheduled backup failed: %s", error_msg)
        
        result = {
            'status': 'failed',
            'error': error_msg,
            'duration_seconds': (timezone.now() - start_time).total_seconds(),
        }
        
        # Отправляем уведомление об ошибке
        if getattr(settings, 'BACKUP_ENABLE_NOTIFICATIONS', True):
            try:
                send_backup_notification(result, is_error=True)
            except Exception as notif_exc:
                logger.error("Failed to send backup error notification: %s", notif_exc)
        
        # Пробрасываем исключение, чтобы Celery пометил задачу как неудачную
        raise


def send_backup_notification(result: dict, is_error: bool = False):
    """
    Отправляет email уведомление администраторам о результате бэкапа.
    
    Args:
        result: Словарь с результатами операции
        is_error: Флаг, указывающий на ошибку
    """
    if is_error:
        subject = '[Жевжик] Ошибка автоматического бэкапа базы данных'
        message = f"""
Произошла ошибка при создании автоматической резервной копии базы данных.

Ошибка: {result.get('error', 'Неизвестная ошибка')}
Время: {timezone.localtime().strftime('%d.%m.%Y %H:%M:%S')}
Длительность: {result.get('duration_seconds', 0):.1f} секунд

Проверьте логи и настройки резервного копирования.
"""
    else:
        file_size_mb = result.get('file_size', 0) / (1024 * 1024)
        duration = result.get('duration_seconds', 0)
        
        subject = '[Жевжик] Автоматический бэкап успешно создан'
        message = f"""
Автоматическая резервная копия базы данных успешно создана.

Файл: {Path(result.get('file_path', '')).name}
Размер: {file_size_mb:.2f} MB
Время создания: {timezone.localtime().strftime('%d.%m.%Y %H:%M:%S')}
Длительность: {duration:.1f} секунд

Файл сохранен в стандартном каталоге резервных копий.
"""
    
    try:
        mail_admins(subject, message, fail_silently=False)
        logger.info("Backup notification sent successfully")
    except Exception as exc:
        logger.error("Failed to send backup notification email: %s", exc)
        # Не пробрасываем исключение, чтобы не прерывать основной процесс


@shared_task(name='cleanup_old_backups')
def cleanup_old_backups(days_to_keep=30):
    """
    Удаляет старые резервные копии старше указанного количества дней.
    
    Args:
        days_to_keep: Количество дней для хранения бэкапов (по умолчанию 30)
    
    Returns:
        dict: Статистика очистки
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    backup_root = _get_backup_root()
    
    deleted_count = 0
    freed_space = 0
    errors = []
    
    try:
        # Находим все бэкапы старше указанной даты
        old_backups = DatabaseBackup.objects.filter(
            operation='backup',
            status='success',
            started_at__lt=cutoff_date
        )
        
        for backup_record in old_backups:
            try:
                backup_path = Path(backup_record.file_path)
                
                # Проверяем, существует ли файл
                if backup_path.exists():
                    file_size = backup_path.stat().st_size
                    
                    # Удаляем файл
                    backup_path.unlink()
                    freed_space += file_size
                    deleted_count += 1
                    
                    logger.info("Deleted old backup: %s", backup_path)
                else:
                    logger.warning("Backup file not found: %s", backup_path)
                
                # Удаляем запись из истории (опционально - можно оставить для архива)
                # backup_record.delete()
                
            except Exception as exc:
                error_msg = f"Failed to delete {backup_record.file_path}: {exc}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        result = {
            'status': 'success',
            'deleted_count': deleted_count,
            'freed_space_mb': freed_space / (1024 * 1024),
            'errors': errors,
        }
        
        logger.info(
            "Cleanup completed: deleted %d backups, freed %.2f MB",
            deleted_count,
            freed_space / (1024 * 1024)
        )
        
        return result
        
    except Exception as exc:
        logger.error("Cleanup failed: %s", exc)
        raise


"""
import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.mail import mail_admins
from django.utils import timezone

from paint_shop_project.admin_views.database import perform_backup, _get_backup_root
from .models import DatabaseBackup

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='create_scheduled_backup')
def create_scheduled_backup(self, comment=None):
    """
    Создает автоматическую резервную копию базы данных.
    
    Args:
        comment: Опциональный комментарий для бэкапа
    
    Returns:
        dict: Результат операции
    """
    start_time = timezone.now()
    backup_path = None
    
    try:
        logger.info("Starting scheduled database backup")
        
        # Создаем бэкап в стандартной папке с подпапкой по дате
        today = timezone.localtime().strftime("%Y-%m-%d")
        backup_path = perform_backup(
            label="scheduled",
            folder_name=f"auto_{today}",
            comment=comment or f"Автоматический бэкап от {start_time.strftime('%d.%m.%Y %H:%M')}",
        )
        
        # Получаем запись из истории
        backup_record = DatabaseBackup.objects.filter(
            file_path=str(backup_path),
            operation='backup',
            status='success'
        ).order_by('-started_at').first()
        
        file_size = backup_path.stat().st_size if backup_path.exists() else 0
        duration = (timezone.now() - start_time).total_seconds()
        
        result = {
            'status': 'success',
            'file_path': str(backup_path),
            'file_size': file_size,
            'duration_seconds': duration,
            'backup_record_id': backup_record.id if backup_record else None,
        }
        
        logger.info(
            "Scheduled backup completed successfully: %s (%.2f MB, %.1f sec)",
            backup_path.name,
            file_size / (1024 * 1024),
            duration
        )
        
        # Отправляем уведомление администраторам
        if getattr(settings, 'BACKUP_ENABLE_NOTIFICATIONS', True):
            try:
                send_backup_notification(result)
            except Exception as exc:
                logger.error("Failed to send backup notification: %s", exc)
        
        return result
        
    except Exception as exc:
        error_msg = str(exc)
        logger.error("Scheduled backup failed: %s", error_msg)
        
        result = {
            'status': 'failed',
            'error': error_msg,
            'duration_seconds': (timezone.now() - start_time).total_seconds(),
        }
        
        # Отправляем уведомление об ошибке
        if getattr(settings, 'BACKUP_ENABLE_NOTIFICATIONS', True):
            try:
                send_backup_notification(result, is_error=True)
            except Exception as notif_exc:
                logger.error("Failed to send backup error notification: %s", notif_exc)
        
        # Пробрасываем исключение, чтобы Celery пометил задачу как неудачную
        raise


def send_backup_notification(result: dict, is_error: bool = False):
    """
    Отправляет email уведомление администраторам о результате бэкапа.
    
    Args:
        result: Словарь с результатами операции
        is_error: Флаг, указывающий на ошибку
    """
    if is_error:
        subject = '[Жевжик] Ошибка автоматического бэкапа базы данных'
        message = f"""
Произошла ошибка при создании автоматической резервной копии базы данных.

Ошибка: {result.get('error', 'Неизвестная ошибка')}
Время: {timezone.localtime().strftime('%d.%m.%Y %H:%M:%S')}
Длительность: {result.get('duration_seconds', 0):.1f} секунд

Проверьте логи и настройки резервного копирования.
"""
    else:
        file_size_mb = result.get('file_size', 0) / (1024 * 1024)
        duration = result.get('duration_seconds', 0)
        
        subject = '[Жевжик] Автоматический бэкап успешно создан'
        message = f"""
Автоматическая резервная копия базы данных успешно создана.

Файл: {Path(result.get('file_path', '')).name}
Размер: {file_size_mb:.2f} MB
Время создания: {timezone.localtime().strftime('%d.%m.%Y %H:%M:%S')}
Длительность: {duration:.1f} секунд

Файл сохранен в стандартном каталоге резервных копий.
"""
    
    try:
        mail_admins(subject, message, fail_silently=False)
        logger.info("Backup notification sent successfully")
    except Exception as exc:
        logger.error("Failed to send backup notification email: %s", exc)
        # Не пробрасываем исключение, чтобы не прерывать основной процесс


@shared_task(name='cleanup_old_backups')
def cleanup_old_backups(days_to_keep=30):
    """
    Удаляет старые резервные копии старше указанного количества дней.
    
    Args:
        days_to_keep: Количество дней для хранения бэкапов (по умолчанию 30)
    
    Returns:
        dict: Статистика очистки
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    backup_root = _get_backup_root()
    
    deleted_count = 0
    freed_space = 0
    errors = []
    
    try:
        # Находим все бэкапы старше указанной даты
        old_backups = DatabaseBackup.objects.filter(
            operation='backup',
            status='success',
            started_at__lt=cutoff_date
        )
        
        for backup_record in old_backups:
            try:
                backup_path = Path(backup_record.file_path)
                
                # Проверяем, существует ли файл
                if backup_path.exists():
                    file_size = backup_path.stat().st_size
                    
                    # Удаляем файл
                    backup_path.unlink()
                    freed_space += file_size
                    deleted_count += 1
                    
                    logger.info("Deleted old backup: %s", backup_path)
                else:
                    logger.warning("Backup file not found: %s", backup_path)
                
                # Удаляем запись из истории (опционально - можно оставить для архива)
                # backup_record.delete()
                
            except Exception as exc:
                error_msg = f"Failed to delete {backup_record.file_path}: {exc}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        result = {
            'status': 'success',
            'deleted_count': deleted_count,
            'freed_space_mb': freed_space / (1024 * 1024),
            'errors': errors,
        }
        
        logger.info(
            "Cleanup completed: deleted %d backups, freed %.2f MB",
            deleted_count,
            freed_space / (1024 * 1024)
        )
        
        return result
        
    except Exception as exc:
        logger.error("Cleanup failed: %s", exc)
        raise

