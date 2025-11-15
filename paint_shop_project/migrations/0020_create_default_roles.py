# Generated manually for creating default roles

from django.db import migrations


def create_default_roles(apps, schema_editor):
    """Создает роли по умолчанию если их нет"""
    Role = apps.get_model('paint_shop_project', 'Role')
    
    roles_data = [
        {
            'name': 'admin',
            'description': 'Администратор системы с полными правами',
            'is_staff_role': True,
            'can_manage_store': True,
            'can_pick_orders': True,
            'can_deliver_orders': True,
        },
        {
            'name': 'manager',
            'description': 'Менеджер магазина, может управлять магазином и собирать заказы',
            'is_staff_role': True,
            'can_manage_store': True,
            'can_pick_orders': True,
            'can_deliver_orders': False,
        },
        {
            'name': 'picker',
            'description': 'Сборщик заказов, собирает товары для клиентов',
            'is_staff_role': True,
            'can_manage_store': False,
            'can_pick_orders': True,
            'can_deliver_orders': False,
        },
        {
            'name': 'delivery',
            'description': 'Доставщик, доставляет заказы клиентам',
            'is_staff_role': True,
            'can_manage_store': False,
            'can_pick_orders': False,
            'can_deliver_orders': True,
        },
        {
            'name': 'customer',
            'description': 'Обычный покупатель',
            'is_staff_role': False,
            'can_manage_store': False,
            'can_pick_orders': False,
            'can_deliver_orders': False,
        },
    ]
    
    for role_data in roles_data:
        role, created = Role.objects.get_or_create(
            name=role_data['name'],
            defaults={
                'description': role_data['description'],
                'is_staff_role': role_data['is_staff_role'],
                'can_manage_store': role_data['can_manage_store'],
                'can_pick_orders': role_data['can_pick_orders'],
                'can_deliver_orders': role_data['can_deliver_orders'],
            }
        )
        if not created:
            # Обновляем существующую роль
            role.description = role_data['description']
            role.is_staff_role = role_data['is_staff_role']
            role.can_manage_store = role_data['can_manage_store']
            role.can_pick_orders = role_data['can_pick_orders']
            role.can_deliver_orders = role_data['can_deliver_orders']
            role.save()


def reverse_create_default_roles(apps, schema_editor):
    """Откат миграции - удаляет роли (опционально)"""
    # Можно оставить пустым или удалить только созданные роли
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('paint_shop_project', '0019_role_can_deliver_orders_role_can_manage_store_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_roles, reverse_create_default_roles),
    ]

