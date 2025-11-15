from django.db import migrations


def set_role_flags(apps, schema_editor):
    Role = apps.get_model('paint_shop_project', 'Role')
    for code, flags in [
        ('admin', dict(is_staff_role=True, can_manage_store=True, can_pick_orders=True, can_deliver_orders=True)),
        ('manager', dict(is_staff_role=True, can_manage_store=True, can_pick_orders=True, can_deliver_orders=False)),
        ('picker', dict(is_staff_role=True, can_manage_store=False, can_pick_orders=True, can_deliver_orders=False)),
        ('delivery', dict(is_staff_role=True, can_manage_store=False, can_pick_orders=False, can_deliver_orders=True)),
        ('customer', dict(is_staff_role=False, can_manage_store=False, can_pick_orders=False, can_deliver_orders=False)),
    ]:
        try:
            role = Role.objects.filter(name=code).first()
            if role:
                for k, v in flags.items():
                    setattr(role, k, v)
                role.save(update_fields=list(flags.keys()))
        except Exception:
            continue


class Migration(migrations.Migration):
    dependencies = [
        ('paint_shop_project', '0017_alter_delivery_courier_alter_role_name_orderdelivery_and_more'),
    ]

    operations = [
        migrations.RunPython(set_role_flags, migrations.RunPython.noop),
    ]




