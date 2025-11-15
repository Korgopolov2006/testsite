#!/usr/bin/env python
"""
Скрипт для генерации SECRET_KEY для Django
"""
from django.core.management.utils import get_random_secret_key

if __name__ == '__main__':
    secret_key = get_random_secret_key()
    print("\n" + "="*70)
    print("🔑 Ваш новый SECRET_KEY для Django:")
    print("="*70)
    print(f"\n{secret_key}\n")
    print("="*70)
    print("\n📋 Скопируйте эту строку и добавьте в переменные окружения:")
    print(f"SECRET_KEY={secret_key}")
    print("\n⚠️  ВАЖНО: Никогда не публикуйте этот ключ в Git!\n")
