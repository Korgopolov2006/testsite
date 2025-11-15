#!/usr/bin/env python3
"""
Автоматическая настройка MySQL для проекта "Жевжик"
Создает базу данных, пользователя и выполняет миграции
"""

import os
import sys
import subprocess
import mysql.connector
from mysql.connector import Error
import getpass
import secrets
import string

def generate_password(length=16):
    """Генерация безопасного пароля"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password

def check_mysql_installed():
    """Проверка установки MySQL"""
    try:
        result = subprocess.run(['mysql', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"✅ MySQL найден: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ MySQL не найден. Пожалуйста, установите MySQL:")
        print("   Windows: https://dev.mysql.com/downloads/mysql/")
        print("   Linux: sudo apt install mysql-server")
        print("   macOS: brew install mysql")
        return False

def get_mysql_root_connection():
    """Подключение к MySQL как root"""
    print("\n🔐 Подключение к MySQL...")
    
    while True:
        try:
            root_password = getpass.getpass("Введите пароль root для MySQL (или нажмите Enter если пароль пустой): ")
            
            connection = mysql.connector.connect(
                host='localhost',
                user='root',
                password=root_password if root_password else None,
                charset='utf8mb4'
            )
            
            if connection.is_connected():
                print("✅ Успешное подключение к MySQL")
                return connection
                
        except Error as e:
            print(f"❌ Ошибка подключения: {e}")
            retry = input("Попробовать снова? (y/n): ").lower()
            if retry != 'y':
                sys.exit(1)

def create_database_and_user(connection):
    """Создание базы данных и пользователя"""
    cursor = connection.cursor()
    
    # Генерация пароля для пользователя
    db_password = generate_password()
    
    try:
        print("\n📊 Создание базы данных...")
        
        # Создание базы данных
        cursor.execute("CREATE DATABASE IF NOT EXISTS zhevzhik_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✅ База данных 'zhevzhik_db' создана")
        
        # Создание пользователя
        print("👤 Создание пользователя...")
        cursor.execute(f"CREATE USER IF NOT EXISTS 'zhevzhik_user'@'localhost' IDENTIFIED BY '{db_password}'")
        print("✅ Пользователь 'zhevzhik_user' создан")
        
        # Предоставление прав
        print("🔑 Предоставление прав...")
        cursor.execute("GRANT ALL PRIVILEGES ON zhevzhik_db.* TO 'zhevzhik_user'@'localhost'")
        cursor.execute("FLUSH PRIVILEGES")
        print("✅ Права предоставлены")
        
        return db_password
        
    except Error as e:
        print(f"❌ Ошибка создания БД/пользователя: {e}")
        sys.exit(1)
    finally:
        cursor.close()

def update_settings_file(db_password):
    """Обновление файла настроек Django"""
    settings_file = "paint_shop/settings.py"
    
    print("\n⚙️ Обновление настроек Django...")
    
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Замена пароля в настройках
        content = content.replace('"PASSWORD": "your_password_here"', f'"PASSWORD": "{db_password}"')
        
        with open(settings_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Настройки Django обновлены")
        
        # Сохранение пароля в файл для справки
        with open('.env.example', 'w', encoding='utf-8') as f:
            f.write(f"""# Настройки базы данных
DB_NAME=zhevzhik_db
DB_USER=zhevzhik_user
DB_PASSWORD={db_password}
DB_HOST=localhost
DB_PORT=3306

# Django настройки
SECRET_KEY=django-insecure-#9hn(4ifja!6me!udysk)vzm5f8=wr7xt)4_5&bva#-4nuy%-h
DEBUG=True
""")
        
        print("✅ Создан файл .env.example с настройками")
        
    except Exception as e:
        print(f"❌ Ошибка обновления настроек: {e}")
        sys.exit(1)

def install_requirements():
    """Установка Python зависимостей"""
    print("\n📦 Установка зависимостей...")
    
    try:
        # Проверка наличия pip
        subprocess.run([sys.executable, '-m', 'pip', '--version'], 
                      check=True, capture_output=True)
        
        # Установка зависимостей
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        
        print("✅ Зависимости установлены")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки зависимостей: {e}")
        print("Попробуйте установить вручную: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False
    
    return True

def run_migrations():
    """Выполнение миграций Django"""
    print("\n🔄 Выполнение миграций...")
    
    try:
        # Создание миграций
        print("📝 Создание миграций...")
        subprocess.run([sys.executable, 'manage.py', 'makemigrations'], 
                      check=True)
        
        # Применение миграций
        print("🚀 Применение миграций...")
        subprocess.run([sys.executable, 'manage.py', 'migrate'], 
                      check=True)
        
        print("✅ Миграции выполнены успешно")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка выполнения миграций: {e}")
        return False

def create_superuser():
    """Создание суперпользователя"""
    print("\n👑 Создание суперпользователя...")
    
    try:
        subprocess.run([sys.executable, 'manage.py', 'createsuperuser'], 
                      check=True)
        print("✅ Суперпользователь создан")
        return True
    except subprocess.CalledProcessError:
        print("⚠️ Суперпользователь не создан (можно создать позже)")
        return False

def populate_initial_data():
    """Заполнение начальными данными"""
    print("\n🌱 Заполнение начальными данными...")
    
    try:
        # Попытка выполнить команду populate_data
        subprocess.run([sys.executable, 'manage.py', 'populate_data'], 
                      check=True)
        print("✅ Начальные данные загружены")
        return True
    except subprocess.CalledProcessError:
        print("⚠️ Команда populate_data не найдена (пропускаем)")
        return False

def main():
    """Основная функция"""
    print("🐷 Настройка MySQL для проекта 'Жевжик'")
    print("=" * 50)
    
    # Проверка установки MySQL
    if not check_mysql_installed():
        sys.exit(1)
    
    # Подключение к MySQL
    connection = get_mysql_root_connection()
    
    try:
        # Создание БД и пользователя
        db_password = create_database_and_user(connection)
        
        # Обновление настроек
        update_settings_file(db_password)
        
        # Установка зависимостей
        if not install_requirements():
            print("⚠️ Продолжаем без установки зависимостей...")
        
        # Выполнение миграций
        if not run_migrations():
            print("❌ Ошибка миграций. Проверьте настройки.")
            sys.exit(1)
        
        # Создание суперпользователя (опционально)
        create_superuser()
        
        # Заполнение данными (опционально)
        populate_initial_data()
        
        print("\n" + "=" * 50)
        print("🎉 Настройка завершена успешно!")
        print("\n📋 Информация о подключении:")
        print(f"   База данных: zhevzhik_db")
        print(f"   Пользователь: zhevzhik_user")
        print(f"   Пароль: {db_password}")
        print(f"   Хост: localhost")
        print(f"   Порт: 3306")
        print("\n🚀 Теперь вы можете запустить проект:")
        print("   python manage.py runserver")
        print("\n💾 Пароль сохранен в файле .env.example")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Настройка прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        sys.exit(1)
    finally:
        if connection.is_connected():
            connection.close()
            print("\n🔌 Соединение с MySQL закрыто")

if __name__ == "__main__":
    main()

