# Настройка Grafana алертов для метрик партий товаров

Этот документ описывает, как настроить алерты в Grafana для мониторинга партий товаров со сроками годности.

## Доступные метрики

1. **`zhevzhik_batches_expired_total`** - Общее количество просроченных партий
2. **`zhevzhik_batches_expiring_in_days{days="3"}`** - Количество партий, истекающих через 3 дня
3. **`zhevzhik_batches_expiring_in_days{days="7"}`** - Количество партий, истекающих через 7 дней
4. **`zhevzhik_batches_low_stock_total`** - Количество партий с низким остатком (<=10 единиц)

## Настройка алертов в Grafana

### 1. Создание Alert Rule для просроченных партий

1. Перейдите в Grafana → Alerting → Alert rules → New alert rule
2. Заполните:
   - **Name**: `Просроченные партии товаров`
   - **Evaluation group**: `warehouse` (или создайте новый)
   - **Evaluation interval**: `1m`

3. В разделе **Query**:
   - **Data source**: Prometheus
   - **Query A**: `zhevzhik_batches_expired_total`
   - **Legend**: `Просрочено`

4. В разделе **Condition**:
   - **WHEN**: `last()`
   - **OF**: `A`
   - **IS ABOVE**: `0`

5. В разделе **Details**:
   - **Summary**: `Обнаружены просроченные партии товаров`
   - **Description**: `Количество просроченных партий: {{ $values.A }}. Требуется немедленная проверка и списание.`
   - **Runbook URL**: (опционально) ссылка на инструкцию

6. В разделе **Notifications**:
   - Добавьте каналы уведомлений (Email, Telegram, Slack и т.д.)

### 2. Создание Alert Rule для партий, истекающих через 3 дня

1. Создайте новое правило:
   - **Name**: `Партии истекают через 3 дня`
   - **Evaluation interval**: `1m`

2. **Query**:
   - **Query A**: `zhevzhik_batches_expiring_in_days{days="3"}`

3. **Condition**:
   - **WHEN**: `last()`
   - **OF**: `A`
   - **IS ABOVE**: `0`

4. **Details**:
   - **Summary**: `Партии товаров истекают через 3 дня`
   - **Description**: `Количество партий, истекающих через 3 дня: {{ $values.A }}. Рекомендуется проверить и принять меры.`

### 3. Создание Alert Rule для партий, истекающих через 7 дней

1. Создайте новое правило:
   - **Name**: `Партии истекают через 7 дней`
   - **Evaluation interval**: `5m`

2. **Query**:
   - **Query A**: `zhevzhik_batches_expiring_in_days{days="7"}`

3. **Condition**:
   - **WHEN**: `last()`
   - **OF**: `A`
   - **IS ABOVE**: `10`

4. **Details**:
   - **Summary**: `Много партий истекает через неделю`
   - **Description**: `Количество партий, истекающих через 7 дней: {{ $values.A }}. Рекомендуется планирование продаж.`

### 4. Создание Alert Rule для низкого остатка

1. Создайте новое правило:
   - **Name**: `Низкий остаток в партиях`
   - **Evaluation interval**: `5m`

2. **Query**:
   - **Query A**: `zhevzhik_batches_low_stock_total`

3. **Condition**:
   - **WHEN**: `last()`
   - **OF**: `A`
   - **IS ABOVE**: `20`

4. **Details**:
   - **Summary**: `Много партий с низким остатком`
   - **Description**: `Количество партий с остатком <=10 единиц: {{ $values.A }}. Рекомендуется пополнение склада.`

### 5. Создание Alert Rule для критического низкого остатка

1. Создайте новое правило:
   - **Name**: `Критический низкий остаток в партиях`
   - **Evaluation interval**: `1m`

2. **Query**:
   - **Query A**: `zhevzhik_batches_low_stock_total`

3. **Condition**:
   - **WHEN**: `last()`
   - **OF**: `A`
   - **IS ABOVE**: `50`

4. **Details**:
   - **Summary**: `Критически низкий остаток в партиях`
   - **Description**: `Количество партий с остатком <=10 единиц: {{ $values.A }}. Требуется срочное пополнение склада!`

## Создание Dashboard

Импортируйте JSON-конфигурацию из файла `grafana_batch_alerts.json` или создайте панели вручную:

1. Перейдите в Dashboards → New dashboard
2. Добавьте панели:
   - **Stat panel**: Просроченные партии (`zhevzhik_batches_expired_total`)
   - **Stat panel**: Партии истекают через 3 дня (`zhevzhik_batches_expiring_in_days{days="3"}`)
   - **Stat panel**: Партии истекают через 7 дней (`zhevzhik_batches_expiring_in_days{days="7"}`)
   - **Stat panel**: Партии с низким остатком (`zhevzhik_batches_low_stock_total`)
   - **Graph panel**: График просроченных партий
   - **Graph panel**: График истекающих партий

## Настройка уведомлений

### Email уведомления

1. Перейдите в Alerting → Notification channels → New channel
2. Выберите тип: **Email**
3. Укажите email-адреса получателей
4. Сохраните канал

### Telegram уведомления

1. Создайте бота через @BotFather в Telegram
2. Получите токен бота
3. Создайте канал или группу
4. Добавьте бота в канал/группу
5. Получите chat_id канала/группы
6. В Grafana создайте Notification channel типа **Telegram**
7. Укажите токен бота и chat_id

## Тестирование алертов

1. Создайте тестовую партию с просроченным сроком годности в админке
2. Проверьте, что метрика `zhevzhik_batches_expired_total` увеличилась
3. Дождитесь срабатывания алерта (обычно через 1-5 минут)
4. Проверьте уведомления

## Рекомендации

- Настройте разные уровни критичности для разных типов алертов
- Используйте группировку алертов для уменьшения шума
- Настройте автоматическое разрешение (resolve) алертов при устранении проблемы
- Регулярно проверяйте работу алертов и корректируйте пороги

