# Generated manually for ProductBatch model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paint_shop_project', '0020_metric'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductBatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('batch_number', models.CharField(max_length=100, verbose_name='Номер партии')),
                ('production_date', models.DateField(verbose_name='Дата производства')),
                ('expiry_date', models.DateField(verbose_name='Срок годности')),
                ('quantity', models.PositiveIntegerField(default=0, verbose_name='Количество в партии')),
                ('remaining_quantity', models.PositiveIntegerField(default=0, verbose_name='Остаток')),
                ('supplier', models.CharField(blank=True, max_length=200, verbose_name='Поставщик')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='paint_shop_project.product', verbose_name='Товар')),
            ],
            options={
                'verbose_name': 'Партия товара',
                'verbose_name_plural': 'Партии товаров',
                'ordering': ['expiry_date', 'production_date'],
            },
        ),
        migrations.AddIndex(
            model_name='productbatch',
            index=models.Index(fields=['product', 'expiry_date'], name='paint_shop_product_expiry_idx'),
        ),
        migrations.AddIndex(
            model_name='productbatch',
            index=models.Index(fields=['expiry_date'], name='paint_shop_expiry_date_idx'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='batch',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='order_items', to='paint_shop_project.productbatch', verbose_name='Партия товара'),
        ),
    ]

