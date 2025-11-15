# 🚀 Руководство по деплою Django Paint Shop

## Варианты деплоя

### 1. 🟢 Railway.app (Рекомендуется)

**Преимущества:** Бесплатный план, автоматический деплой, PostgreSQL включен

**Шаги:**

1. Зарегистрируйтесь на [Railway.app](https://railway.app/)
2. Нажмите "New Project" → "Deploy from GitHub repo"
3. Подключите ваш GitHub аккаунт и выберите репозиторий
4. Railway автоматически определит Django проект
5. Добавьте PostgreSQL: кликните "+ New" → "Database" → "PostgreSQL"
6. Настройте переменные окружения (см. ниже)
7. Railway автоматически задеплоит ваш проект

**Переменные окружения для Railway:**
```
SECRET_KEY=django-insecure-change-this-to-random-50-chars
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app
DATABASE_URL=postgresql://... (автоматически от Railway PostgreSQL)
```

### 2. 🔵 Render.com

**Преимущества:** Бесплатный план, простота использования

**Шаги:**

1. Зарегистрируйтесь на [Render.com](https://render.com/)
2. Нажмите "New +" → "Web Service"
3. Подключите GitHub репозиторий
4. Настройки:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn paint_shop.wsgi:application`
5. Добавьте PostgreSQL: "New +" → "PostgreSQL"
6. Настройте переменные окружения

### 3. 🟣 Heroku

**Шаги:**

1. Установите [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
2. Выполните команды:

```bash
heroku login
heroku create your-app-name
heroku addons:create heroku-postgresql:mini
heroku config:set SECRET_KEY="your-secret-key"
heroku config:set DEBUG=False
git push heroku main
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
```

### 4. 🟠 PythonAnywhere

**Преимущества:** Специализируется на Python/Django

**Шаги:**

1. Зарегистрируйтесь на [PythonAnywhere](https://www.pythonanywhere.com/)
2. Загрузите код через Git или файлы
3. Создайте виртуальное окружение
4. Настройте Web App в разделе "Web"
5. Укажите путь к WSGI файлу: `/home/yourusername/Django1-master/paint_shop/wsgi.py`

### 5. 💻 VPS (DigitalOcean, Linode, AWS)

Для продвинутых пользователей. Требует настройки:
- Nginx/Apache
- Gunicorn/uWSGI
- PostgreSQL
- SSL сертификат (Let's Encrypt)

## 📝 Подготовка проекта к деплою

### 1. Обновите settings.py для продакшена

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Отредактируйте `.env`:
```
SECRET_KEY=your-unique-secret-key-generate-new-one
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### 2. Обновите requirements.txt

Добавьте:
```bash
gunicorn==21.2.0
dj-database-url==2.1.0
whitenoise==6.6.0
django-prometheus==2.3.1
```

Выполните:
```bash
pip install -r requirements.txt
```

### 3. Настройте статические файлы

В `settings.py` добавьте:
```python
STATIC_ROOT = BASE_DIR / 'staticfiles'
```

Соберите статику:
```bash
python manage.py collectstatic
```

### 4. Создайте .gitignore

```
*.pyc
__pycache__/
db.sqlite3
.env
venv/
staticfiles/
media/
logs/
```

## 🔧 Переменные окружения

Обязательные переменные для продакшена:

```bash
SECRET_KEY=your-50-char-random-string
DEBUG=False
ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgresql://user:pass@host:5432/dbname
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
TELEGRAM_BOT_TOKEN=your-bot-token (опционально)
```

## 📊 После деплоя

1. **Миграции:**
```bash
python manage.py migrate
```

2. **Создайте суперпользователя:**
```bash
python manage.py createsuperuser
```

3. **Соберите статику:**
```bash
python manage.py collectstatic --noinput
```

4. **Импортируйте данные (если нужно):**
```bash
python manage.py import_products
python manage.py seed_demo_data
```

## 🔒 Безопасность

1. **Смените SECRET_KEY** на уникальный
2. **Установите DEBUG=False**
3. **Настройте ALLOWED_HOSTS**
4. **Используйте HTTPS** (большинство платформ предоставляют бесплатно)
5. **Не коммитьте .env** в Git

## 📞 Поддержка

Если нужна помощь:
- Railway: [документация](https://docs.railway.app/)
- Render: [документация](https://render.com/docs)
- Heroku: [документация](https://devcenter.heroku.com/)

## 🎯 Быстрый старт (Railway - самый простой)

1. Загрузите код на GitHub
2. Зайдите на railway.app
3. Нажмите "Start a New Project" → "Deploy from GitHub"
4. Выберите репозиторий
5. Добавьте PostgreSQL базу данных
6. Готово! Ваш сайт в интернете через 2 минуты
