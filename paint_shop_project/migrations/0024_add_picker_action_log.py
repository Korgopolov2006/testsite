# Generated manually for PickerActionLog model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('paint_shop_project', '0023_add_batch_audit_log'),
    ]

    operations = [
        migrations.CreateModel(
            name='PickerActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action_type', models.CharField(choices=[('order_taken', 'Взял заказ в работу'), ('batch_assigned', 'Назначил партию'), ('batch_unassigned', 'Снял партию'), ('order_completed', 'Завершил сборку'), ('missing_reported', 'Сообщил о недостаче'), ('order_started', 'Начал сборку')], max_length=50, verbose_name='Тип действия')),
                ('details', models.TextField(blank=True, verbose_name='Детали')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP-адрес')),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='picker_actions', to='paint_shop_project.order', verbose_name='Заказ')),
                ('picker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='picker_actions', to=settings.AUTH_USER_MODEL, verbose_name='Сборщик')),
            ],
            options={
                'verbose_name': 'Действие сборщика',
                'verbose_name_plural': 'Действия сборщиков',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pickeractionlog',
            index=models.Index(fields=['picker', 'created_at'], name='paint_shop_picker_picker__idx'),
        ),
        migrations.AddIndex(
            model_name='pickeractionlog',
            index=models.Index(fields=['order', 'created_at'], name='paint_shop_picker_order__idx'),
        ),
        migrations.AddIndex(
            model_name='pickeractionlog',
            index=models.Index(fields=['action_type', 'created_at'], name='paint_shop_picker_action__idx'),
        ),
    ]


