#!/bin/bash

echo "🐷 Настройка проекта 'Жевжик' для Linux/macOS"
echo "================================================"

# Проверка наличия Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Пожалуйста, установите Python 3.8+"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "   CentOS/RHEL: sudo yum install python3 python3-pip"
    echo "   macOS: brew install python3"
    exit 1
fi

echo "✅ Python3 найден"

# Проверка наличия MySQL
if ! command -v mysql &> /dev/null; then
    echo "❌ MySQL не найден. Пожалуйста, установите MySQL"
    echo "   Ubuntu/Debian: sudo apt install mysql-server"
    echo "   CentOS/RHEL: sudo yum install mysql-server"
    echo "   macOS: brew install mysql"
    exit 1
fi

echo "✅ MySQL найден"

# Установка зависимостей
echo ""
echo "📦 Установка Python зависимостей..."

# Установка системных зависимостей для mysqlclient
if command -v apt-get &> /dev/null; then
    echo "Установка системных зависимостей для Ubuntu/Debian..."
    sudo apt-get update
    sudo apt-get install -y python3-dev default-libmysqlclient-dev build-essential
elif command -v yum &> /dev/null; then
    echo "Установка системных зависимостей для CentOS/RHEL..."
    sudo yum install -y python3-devel mysql-devel gcc
elif command -v brew &> /dev/null; then
    echo "Установка системных зависимостей для macOS..."
    brew install mysql-client
    export PATH="/usr/local/opt/mysql-client/bin:$PATH"
fi

# Установка Python пакетов
pip3 install mysql-connector-python
if [ $? -ne 0 ]; then
    echo "❌ Ошибка установки mysql-connector-python"
    echo "   Попробуйте: pip3 install --upgrade pip"
    exit 1
fi

pip3 install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "⚠️ Ошибка установки некоторых зависимостей"
    echo "   Продолжаем настройку..."
fi

# Запуск автоматической настройки
echo ""
echo "🚀 Запуск автоматической настройки MySQL..."
python3 setup_mysql.py
if [ $? -ne 0 ]; then
    echo "❌ Ошибка настройки MySQL"
    exit 1
fi

# Миграция данных из SQLite (если файл существует)
if [ -f "db.sqlite3" ]; then
    echo ""
    echo "🔄 Миграция данных из SQLite..."
    python3 migrate_from_sqlite.py
    if [ $? -ne 0 ]; then
        echo "⚠️ Ошибка миграции данных (продолжаем...)"
    fi
fi

# Создание суперпользователя
echo ""
echo "👑 Создание суперпользователя Django..."
echo "   (Нажмите Ctrl+C если не хотите создавать сейчас)"
python3 manage.py createsuperuser
if [ $? -ne 0 ]; then
    echo "⚠️ Суперпользователь не создан (можно создать позже)"
fi

# Запуск сервера разработки
echo ""
echo "🎉 Настройка завершена!"
echo ""
echo "🚀 Запуск сервера разработки..."
echo "   Откройте браузер и перейдите по адресу: http://127.0.0.1:8000"
echo "   Для остановки сервера нажмите Ctrl+C"
echo ""
python3 manage.py runserver

