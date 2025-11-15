"""
Модуль для работы с Telegram Bot API для отправки уведомлений
"""
import logging
from typing import Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Класс для отправки уведомлений через Telegram Bot API"""
    
    def __init__(self):
        self.bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.enabled = getattr(settings, 'TELEGRAM_ENABLE_NOTIFICATIONS', True)
        
    def is_configured(self) -> bool:
        """Проверяет, настроен ли Telegram бот"""
        return self.bot_token is not None and self.enabled
    
    def send_message(self, chat_id: int, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Отправляет сообщение в Telegram
        
        Args:
            chat_id: ID чата пользователя
            message: Текст сообщения
            parse_mode: Режим парсинга (HTML или Markdown)
        
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if not self.is_configured():
            logger.warning("Telegram bot не настроен, сообщение не отправлено")
            return False
        
        if not chat_id:
            logger.warning("Chat ID не указан, сообщение не отправлено")
            return False
        
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': parse_mode,
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Telegram сообщение отправлено в чат {chat_id}")
            return True
            
        except requests.exceptions.RequestException as exc:
            logger.error(f"Ошибка отправки Telegram сообщения: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Неожиданная ошибка при отправке Telegram сообщения: {exc}")
            return False
    
    def send_backup_notification(
        self,
        chat_id: int,
        status: str,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        error: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> bool:
        """
        Отправляет уведомление о результате бэкапа
        
        Args:
            chat_id: ID чата пользователя
            status: Статус операции ('success' или 'failed')
            file_path: Путь к файлу бэкапа
            file_size: Размер файла в байтах
            error: Сообщение об ошибке (если есть)
            duration: Длительность операции в секундах
        
        Returns:
            bool: True если сообщение отправлено успешно
        """
        if status == 'success':
            file_size_mb = (file_size / (1024 * 1024)) if file_size else 0
            duration_str = f"{duration:.1f} сек" if duration else "—"
            file_name = file_path.split('/')[-1] if file_path else "—"
            
            message = (
                "✅ <b>Резервная копия создана успешно</b>\n\n"
                f"📁 Файл: <code>{file_name}</code>\n"
                f"📊 Размер: {file_size_mb:.2f} MB\n"
                f"⏱ Длительность: {duration_str}\n\n"
                "Резервная копия сохранена в стандартном каталоге."
            )
        else:
            error_msg = error or "Неизвестная ошибка"
            message = (
                "❌ <b>Ошибка при создании резервной копии</b>\n\n"
                f"⚠️ Ошибка: <code>{error_msg}</code>\n\n"
                "Проверьте логи и настройки резервного копирования."
            )
        
        return self.send_message(chat_id, message)
    
    def verify_chat_id(self, chat_id: int) -> bool:
        """
        Проверяет, что chat_id действителен
        
        Args:
            chat_id: ID чата для проверки
        
        Returns:
            bool: True если chat_id валиден
        """
        if not self.is_configured():
            return False
        
        try:
            import requests
            
            url = f"https://api.telegram.org/bot{self.bot_token}/getChat"
            payload = {'chat_id': chat_id}
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as exc:
            logger.error(f"Ошибка проверки chat_id: {exc}")
            return False


def send_notification_to_user(user, message: str) -> bool:
    """
    Отправляет уведомление пользователю через Telegram (если настроено) или email
    
    Args:
        user: Объект пользователя
        message: Текст сообщения
    
    Returns:
        bool: True если уведомление отправлено
    """
    notifier = TelegramNotifier()
    
    # Пробуем отправить через Telegram
    if (
        notifier.is_configured()
        and user.telegram_notifications_enabled
        and user.telegram_chat_id
    ):
        success = notifier.send_message(user.telegram_chat_id, message)
        if success:
            return True
    
    # Если Telegram не сработал, отправляем email (если включены email уведомления)
    if user.email and user.is_newsletter_subscribed:
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            send_mail(
                subject='Уведомление от Жевжик',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            return True
        except Exception as exc:
            logger.error(f"Ошибка отправки email: {exc}")
    
    return False




