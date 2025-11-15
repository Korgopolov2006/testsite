from django.apps import AppConfig


class PaintShopProjectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paint_shop_project"

    def ready(self):
        """Подключаем сигналы при запуске приложения"""
        import paint_shop_project.batch_signals  # noqa
        import paint_shop_project.product_signals  # noqa
        import paint_shop_project.loyalty_signals  # noqa