from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paint_shop_project', '0011_add_promotions'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='favorite_discount_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Скидка любимых категорий'),
        ),
        migrations.AddField(
            model_name='order',
            name='promotion_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Скидка по акции'),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Стоимость доставки'),
        ),
    ]


