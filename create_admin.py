import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paint_shop.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Удаляем старого админа если есть
User.objects.filter(username='admin').delete()

# Создаём нового
admin = User.objects.create_superuser(
    username='admin',
    email='admin@admin.com',
    password='admin123'
)

print(f"✅ Superuser created: {admin.username}")
print(f"Password: admin123")
