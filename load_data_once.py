import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paint_shop.settings')
django.setup()

from django.core.management import call_command

try:
    print("Loading data from data.json...")
    call_command('loaddata', 'data.json')
    print("✅ Data loaded successfully!")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    sys.exit(1)
