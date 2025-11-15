#!/usr/bin/env python3
"""
Миграция данных из SQLite в MySQL для проекта "Жевжик"
"""

import os
import sys
import sqlite3
import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime

def connect_sqlite():
    """Подключение к SQLite базе"""
    sqlite_file = "db.sqlite3"
    
    if not os.path.exists(sqlite_file):
        print(f"❌ Файл {sqlite_file} не найден")
        return None
    
    try:
        connection = sqlite3.connect(sqlite_file)
        connection.row_factory = sqlite3.Row  # Для доступа к колонкам по имени
        print("✅ Подключение к SQLite успешно")
        return connection
    except Exception as e:
        print(f"❌ Ошибка подключения к SQLite: {e}")
        return None

def connect_mysql():
    """Подключение к MySQL базе"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='zhevzhik_db',
            user='zhevzhik_user',
            password=get_mysql_password(),
            charset='utf8mb4'
        )
        print("✅ Подключение к MySQL успешно")
        return connection
    except Error as e:
        print(f"❌ Ошибка подключения к MySQL: {e}")
        return None

def get_mysql_password():
    """Получение пароля MySQL из файла настроек"""
    try:
        with open('.env.example', 'r') as f:
            for line in f:
                if line.startswith('DB_PASSWORD='):
                    return line.split('=', 1)[1].strip()
    except:
        pass
    
    # Если не найден в файле, запросить у пользователя
    import getpass
    return getpass.getpass("Введите пароль для MySQL пользователя zhevzhik_user: ")

def get_table_list(sqlite_conn):
    """Получение списка таблиц из SQLite"""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return tables

def migrate_table_data(sqlite_conn, mysql_conn, table_name):
    """Миграция данных из одной таблицы"""
    print(f"📊 Миграция таблицы: {table_name}")
    
    try:
        # Получение данных из SQLite
        sqlite_cursor = sqlite_conn.cursor()
        sqlite_cursor.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cursor.fetchall()
        
        if not rows:
            print(f"   ⚠️ Таблица {table_name} пуста")
            return True
        
        # Получение структуры таблицы
        columns = [description[0] for description in sqlite_cursor.description]
        
        # Подготовка запроса для MySQL
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f'`{col}`' for col in columns])
        insert_query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
        
        # Вставка данных в MySQL
        mysql_cursor = mysql_conn.cursor()
        
        for row in rows:
            # Преобразование данных для совместимости с MySQL
            converted_row = []
            for i, value in enumerate(row):
                if value is None:
                    converted_row.append(None)
                elif isinstance(value, str):
                    # Обработка JSON полей
                    if columns[i] in ['notification_preferences']:
                        try:
                            json.loads(value)  # Проверка валидности JSON
                            converted_row.append(value)
                        except:
                            converted_row.append('{}')
                    else:
                        converted_row.append(value)
                elif isinstance(value, (int, float)):
                    converted_row.append(value)
                elif isinstance(value, datetime):
                    converted_row.append(value)
                else:
                    converted_row.append(str(value))
            
            try:
                mysql_cursor.execute(insert_query, converted_row)
            except Error as e:
                print(f"   ⚠️ Ошибка вставки строки: {e}")
                continue
        
        mysql_conn.commit()
        mysql_cursor.close()
        sqlite_cursor.close()
        
        print(f"   ✅ Мигрировано {len(rows)} записей")
        return True
        
    except Exception as e:
        print(f"   ❌ Ошибка миграции таблицы {table_name}: {e}")
        return False

def migrate_auth_tables(sqlite_conn, mysql_conn):
    """Специальная миграция для Django auth таблиц"""
    auth_tables = [
        'auth_user',
        'auth_group', 
        'auth_permission',
        'auth_group_permissions',
        'auth_user_groups',
        'auth_user_user_permissions',
        'django_content_type',
        'django_migrations',
        'django_session'
    ]
    
    print("🔐 Миграция Django auth таблиц...")
    
    for table in auth_tables:
        try:
            sqlite_cursor = sqlite_conn.cursor()
            sqlite_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            
            if sqlite_cursor.fetchone():
                migrate_table_data(sqlite_conn, mysql_conn, table)
            else:
                print(f"   ⚠️ Таблица {table} не найдена в SQLite")
                
            sqlite_cursor.close()
        except Exception as e:
            print(f"   ❌ Ошибка миграции {table}: {e}")

def main():
    """Основная функция миграции"""
    print("🔄 Миграция данных из SQLite в MySQL")
    print("=" * 50)
    
    # Подключение к базам данных
    sqlite_conn = connect_sqlite()
    if not sqlite_conn:
        sys.exit(1)
    
    mysql_conn = connect_mysql()
    if not mysql_conn:
        sqlite_conn.close()
        sys.exit(1)
    
    try:
        # Получение списка таблиц
        tables = get_table_list(sqlite_conn)
        print(f"📋 Найдено таблиц: {len(tables)}")
        
        # Миграция Django auth таблиц
        migrate_auth_tables(sqlite_conn, mysql_conn)
        
        # Миграция пользовательских таблиц
        print("\n📊 Миграция пользовательских таблиц...")
        custom_tables = [t for t in tables if not t.startswith('auth_') and not t.startswith('django_')]
        
        for table in custom_tables:
            migrate_table_data(sqlite_conn, mysql_conn, table)
        
        print("\n" + "=" * 50)
        print("🎉 Миграция завершена успешно!")
        print("\n📋 Статистика:")
        print(f"   Всего таблиц: {len(tables)}")
        print(f"   Django таблиц: {len(tables) - len(custom_tables)}")
        print(f"   Пользовательских таблиц: {len(custom_tables)}")
        
    except Exception as e:
        print(f"\n❌ Ошибка миграции: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        mysql_conn.close()
        print("\n🔌 Соединения закрыты")

if __name__ == "__main__":
    main()

