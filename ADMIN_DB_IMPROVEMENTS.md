# Улучшения админки для управления базой данных

## Этап 1: Модель истории бэкапов и настройка бинарников ✅

### Что было сделано:
1. Создана модель `DatabaseBackup` для отслеживания всех операций резервного копирования
2. Добавлены настройки в `settings.py` для указания путей к бинарникам PostgreSQL
3. Обновлены функции `perform_backup` и `perform_restore_from_file` для автоматической записи истории
4. Добавлена модель в админку с удобным интерфейсом

### Настройка бинарников PostgreSQL:

Если `pg_dump`, `pg_restore`, `psql` не в PATH, добавьте в `settings.py`:

```python
# Вариант 1: Указать один каталог
DATABASE_BACKUP_BIN_DIR = r"C:\Program Files\PostgreSQL\15\bin"

# Вариант 2: Указать конкретные пути
DATABASE_BACKUP_BIN = {
    "pg_dump": r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
    "pg_restore": r"C:\Program Files\PostgreSQL\15\bin\pg_restore.exe",
    "psql": r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
}

# Вариант 3: Список каталогов для поиска
DATABASE_BACKUP_BIN_DIRS = [
    r"C:\Program Files\PostgreSQL\15\bin",
    r"C:\Program Files\PostgreSQL\14\bin",
]
```

### Применение миграций:
```bash
python manage.py migrate
```

---

## Этап 2: Планировщик бэкапов (Celery) ✅

### Что было сделано:
1. ✅ Добавлены зависимости Celery в `requirements.txt`
2. ✅ Создана конфигурация Celery (`paint_shop/celery.py`)
3. ✅ Обновлен `paint_shop/__init__.py` для загрузки Celery
4. ✅ Добавлены настройки Celery в `settings.py`
5. ✅ Создана задача `create_scheduled_backup` для автоматических бэкапов
6. ✅ Добавлена функция `cleanup_old_backups` для очистки старых бэкапов
7. ✅ Создана команда `setup_backup_schedule` для настройки расписания
8. ✅ Добавлена отправка email уведомлений администраторам

### Установка зависимостей:
```bash
pip install -r requirements.txt
```

### Применение миграций для django-celery-beat:
```bash
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_results
```

### Настройка автоматических бэкапов:

1. **Настройте расписание** (по умолчанию 2:00 ночи):
```bash
python manage.py setup_backup_schedule --hour 2 --minute 0
```

2. **Отключить автоматические бэкапы**:
```bash
python manage.py setup_backup_schedule --disable
```

3. **Запустите Celery Beat** (планировщик):
```bash
celery -A paint_shop beat --loglevel=info
```

4. **Запустите Celery Worker** (для выполнения задач):
```bash
celery -A paint_shop worker --loglevel=info
```

### Настройка email для уведомлений:

Убедитесь, что в `settings.py` настроены параметры email:
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `ADMINS` (список администраторов для получения уведомлений)

### Управление через админку:

После применения миграций в админке Django появится раздел **"Periodic Tasks"**, где можно:
- Просматривать и редактировать периодические задачи
- Создавать новые задачи
- Включать/отключать задачи

### Примечания:

- Для разработки используется `memory://` брокер (не требует Redis)
- В продакшене рекомендуется использовать Redis или RabbitMQ:
  ```python
  CELERY_BROKER_URL = 'redis://localhost:6379/0'
  ```

---

## Этап 3: Графики и экспорт отчётов

### Шаг 3.1: Установка Chart.js

Добавьте Chart.js через CDN или установите через npm.

### Шаг 3.2: Создание views для экспорта

Создайте views для экспорта метрик в CSV/XLSX форматы.

### Шаг 3.3: Интеграция графиков

Добавьте графики на страницу метрик продаж.

---

## Этап 4: Расширенные метрики PostgreSQL

### Шаг 4.1: WAL и репликация

Добавьте запросы к системным таблицам PostgreSQL для получения информации о WAL и репликации.

### Шаг 4.2: Рекомендации по вакууму

Добавьте логику анализа статистики для рекомендаций по вакууму.

---

## Полезные команды

### Применение миграций:
```bash
python manage.py migrate
```

### Создание суперпользователя (если нужно):
```bash
python manage.py createsuperuser
```

### Запуск Celery worker:
```bash
celery -A paint_shop worker --loglevel=info
```

### Запуск Celery beat:
```bash
celery -A paint_shop beat --loglevel=info
```





