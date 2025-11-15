#!/usr/bin/env python3
"""
Автонастройка PostgreSQL для проекта "Жевжик"
Создает БД Jevjik_shop, пользователя postgres (локальный), применяет миграции и загружает тестовые данные
"""

import os
import sys
import subprocess
import getpass

DB_NAME = "Jevjik_shop"
DB_USER = "postgres"
DB_PASSWORD = "1"
DB_HOST = "localhost"
DB_PORT = "5432"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check)


def psql_available() -> bool:
    try:
        run(["psql", "--version"])  # type: ignore[arg-type]
        return True
    except Exception:
        print("❌ Не найден psql. Установите PostgreSQL и добавьте psql в PATH.")
        return False


def createdb_available() -> bool:
    try:
        run(["createdb", "--version"])  # type: ignore[arg-type]
        return True
    except Exception:
        return False


def ensure_database():
    print("📦 Создание базы данных и настройка доступа (PostgreSQL)...")

    # Проверим подключение к postgres
    env = os.environ.copy()
    env.setdefault("PGPASSWORD", DB_PASSWORD)

    # Создать БД, если нет
    try:
        run(["psql", "-h", DB_HOST, "-U", DB_USER, "-p", DB_PORT, "-tc", f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'"], check=True)
        # Если команда прошла, просто попробуем создать БД через createdb (он вернет ошибку если есть)
        run(["createdb", "-h", DB_HOST, "-U", DB_USER, "-p", DB_PORT, DB_NAME], check=False)
    except Exception:
        # Fallback через psql
        run(["psql", "-h", DB_HOST, "-U", DB_USER, "-p", DB_PORT, "-c", f"CREATE DATABASE \"{DB_NAME}\" ENCODING 'UTF8' TEMPLATE template1;"], check=False)

    print("✅ База данных готова")


def install_requirements():
    print("📦 Установка Python зависимостей...")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
    print("✅ Зависимости установлены")


def run_migrations_and_seed():
    print("🔄 Применение миграций...")
    run([sys.executable, "manage.py", "makemigrations"], check=True)
    run([sys.executable, "manage.py", "migrate"], check=True)
    print("✅ Миграции применены")

    print("🌱 Загрузка тестовых данных...")
    try:
        run([sys.executable, "manage.py", "populate_data"], check=True)
        print("✅ Тестовые данные загружены")
    except subprocess.CalledProcessError:
        print("⚠️ Команда populate_data не найдена/завершилась ошибкой — продолжаем")


def main():
    print("🐷 Автонастройка PostgreSQL для проекта 'Жевжик'")
    print("=" * 50)

    if not psql_available():
        sys.exit(1)

    if not createdb_available():
        print("ℹ️ Утилита createdb не найдена, будем использовать psql")

    install_requirements()
    ensure_database()
    run_migrations_and_seed()

    print("\n🎉 Готово! Запускайте сервер:")
    print("   python manage.py runserver")


if __name__ == "__main__":
    main()

