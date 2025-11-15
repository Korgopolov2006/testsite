# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('paint_shop_project', '0022_merge_20251106_2017'),
    ]

    operations = [
        migrations.CreateModel(
            name='BatchAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('created', 'Создана'), ('updated', 'Обновлена'), ('quantity_changed', 'Изменено количество'), ('assigned', 'Назначена заказу'), ('unassigned', 'Снята с заказа'), ('spoiled', 'Списана'), ('deleted', 'Удалена')], max_length=50, verbose_name='Действие')),
                ('old_value', models.PositiveIntegerField(blank=True, null=True, verbose_name='Старое значение (остаток)')),
                ('new_value', models.PositiveIntegerField(blank=True, null=True, verbose_name='Новое значение (остаток)')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP-адрес')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('batch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='paint_shop_project.productbatch', verbose_name='Партия')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='batch_audit_logs', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Лог изменений партии',
                'verbose_name_plural': 'Логи изменений партий',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='batchauditlog',
            index=models.Index(fields=['batch', 'created_at'], name='paint_shop_batch_i_batch_i_idx'),
        ),
        migrations.AddIndex(
            model_name='batchauditlog',
            index=models.Index(fields=['action', 'created_at'], name='paint_shop_batch_i_action__idx'),
        ),
        migrations.AddIndex(
            model_name='batchauditlog',
            index=models.Index(fields=['user', 'created_at'], name='paint_shop_batch_i_user_i_idx'),
        ),
    ]


