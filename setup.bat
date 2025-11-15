@echo off
chcp 65001 >nul
echo 🐷 Настройка проекта "Жевжик" для Windows
echo ================================================

REM Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Пожалуйста, установите Python 3.8+
    echo    Скачайте с https://www.python.org/downloads/
    pause
    exit /b 1
)

echo ✅ Python найден

REM Проверка наличия MySQL
mysql --version >nul 2>&1
if errorlevel 1 (
    echo ❌ MySQL не найден. Пожалуйста, установите MySQL
    echo    Скачайте с https://dev.mysql.com/downloads/mysql/
    echo    Или используйте XAMPP: https://www.apachefriends.org/
    pause
    exit /b 1
)

echo ✅ MySQL найден

REM Установка зависимостей
echo.
echo 📦 Установка Python зависимостей...
pip install mysql-connector-python
if errorlevel 1 (
    echo ❌ Ошибка установки mysql-connector-python
    echo    Попробуйте: pip install --upgrade pip
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ⚠️ Ошибка установки некоторых зависимостей
    echo    Продолжаем настройку...
)

REM Запуск автоматической настройки
echo.
echo 🚀 Запуск автоматической настройки MySQL...
python setup_mysql.py
if errorlevel 1 (
    echo ❌ Ошибка настройки MySQL
    pause
    exit /b 1
)

REM Миграция данных из SQLite (если файл существует)
if exist "db.sqlite3" (
    echo.
    echo 🔄 Миграция данных из SQLite...
    python migrate_from_sqlite.py
    if errorlevel 1 (
        echo ⚠️ Ошибка миграции данных (продолжаем...)
    )
)

REM Создание суперпользователя
echo.
echo 👑 Создание суперпользователя Django...
echo    (Нажмите Ctrl+C если не хотите создавать сейчас)
python manage.py createsuperuser
if errorlevel 1 (
    echo ⚠️ Суперпользователь не создан (можно создать позже)
)

REM Запуск сервера разработки
echo.
echo 🎉 Настройка завершена!
echo.
echo 🚀 Запуск сервера разработки...
echo    Откройте браузер и перейдите по адресу: http://127.0.0.1:8000
echo    Для остановки сервера нажмите Ctrl+C
echo.
python manage.py runserver

pause

