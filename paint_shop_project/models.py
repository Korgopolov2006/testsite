"""
Модели для приложения paint_shop_project
Восстановлено из миграций
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP


# ==================== РОЛИ И ПОЛЬЗОВАТЕЛИ ====================

class Role(models.Model):
    """Роли пользователей"""
    ROLE_CHOICES = [
        ('admin', 'Администратор'),
        ('manager', 'Менеджер магазина'),
        ('picker', 'Сборщик'),
        ('delivery', 'Доставщик'),
        ('customer', 'Покупатель'),
    ]
    
    name = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        unique=True,
        verbose_name="Название роли"
    )
    description = models.TextField(blank=True, verbose_name="Описание")
    is_staff_role = models.BooleanField(default=False, verbose_name="Роль персонала")
    can_pick_orders = models.BooleanField(default=False, verbose_name="Может собирать заказы")
    can_deliver_orders = models.BooleanField(default=False, verbose_name="Может доставлять заказы")
    can_manage_store = models.BooleanField(default=False, verbose_name="Может управлять магазином")
    
    class Meta:
        verbose_name = "Роль"
        verbose_name_plural = "Роли"
    
    def __str__(self):
        return self.get_name_display()


class User(AbstractUser):
    """Расширенная модель пользователя"""
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Роль"
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    address = models.TextField(blank=True, verbose_name="Адрес доставки")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True, verbose_name="Аватар")
    preferred_delivery_time = models.CharField(max_length=50, blank=True, verbose_name="Предпочитаемое время доставки")
    notification_preferences = models.JSONField(default=dict, blank=True, verbose_name="Настройки уведомлений")
    total_cashback_earned = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Общий кешбэк")
    total_cashback_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Потраченный кешбэк")
    is_newsletter_subscribed = models.BooleanField(default=True, verbose_name="Подписка на рассылку")
    registration_source = models.CharField(max_length=50, default='website', verbose_name="Источник регистрации")
    telegram_chat_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram Chat ID", help_text="ID чата в Telegram для получения уведомлений")
    telegram_notifications_enabled = models.BooleanField(default=False, verbose_name="Включить Telegram уведомления")
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
    
    def can_pick_orders(self):
        """Проверка, может ли пользователь собирать заказы"""
        return self.role and self.role.can_pick_orders
    
    def can_deliver_orders(self):
        """Проверка, может ли пользователь доставлять заказы"""
        return self.role and self.role.can_deliver_orders
    
    def can_manage_store(self):
        """Проверка, может ли пользователь управлять магазином"""
        return self.role and self.role.can_manage_store

    def get_loyalty_level(self):
        """Возвращает название уровня лояльности пользователя."""
        try:
            return self.loyalty_card.get_level_name()
        except ObjectDoesNotExist:
            return "Новичок"

    def get_loyalty_level_slug(self):
        """Техническое значение уровня лояльности пользователя."""
        try:
            return self.loyalty_card.level
        except ObjectDoesNotExist:
            return "novice"

    def get_cashback_balance(self):
        """Текущий баланс кешбэка пользователя."""
        earned = Decimal(str(self.total_cashback_earned or 0))
        spent = Decimal(str(self.total_cashback_spent or 0))
        return earned - spent

    def get_favorite_categories_discount(self, category):
        """Возвращает скидку для любимой категории пользователя."""
        if not category:
            return 0
        try:
            favorite = self.favorite_categories.filter(category=category, is_active=True).only('discount_percent').first()
        except AttributeError:
            return 0
        if favorite:
            return favorite.discount_percent
        return 0


# ==================== КАТЕГОРИИ И ПРОИЗВОДИТЕЛИ ====================

class Category(models.Model):
    """Категории товаров"""
    name = models.CharField(max_length=100, verbose_name="Название категории")
    slug = models.SlugField(unique=True, verbose_name="URL")
    description = models.TextField(blank=True, verbose_name="Описание")
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="Изображение")
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name="Родительская категория")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")
    
    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ['sort_order', 'name']
    
    def __str__(self):
        return self.name


class Manufacturer(models.Model):
    """Производители"""
    name = models.CharField(max_length=200, verbose_name="Название производителя")
    address = models.TextField(blank=True, verbose_name="Адрес")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Сайт")
    logo = models.ImageField(upload_to='manufacturers/', blank=True, null=True, verbose_name="Логотип")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Производитель"
        verbose_name_plural = "Производители"
        ordering = ['name']
    
    def __str__(self):
        return self.name


# ==================== ТОВАРЫ ====================

class Product(models.Model):
    """Товары"""
    UNIT_CHOICES = [
        ('шт', 'Штука'),
        ('кг', 'Килограмм'),
        ('г', 'Грамм'),
        ('л', 'Литр'),
        ('мл', 'Миллилитр'),
        ('уп', 'Упаковка'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Название товара")
    slug = models.SlugField(unique=True, verbose_name="URL")
    description = models.TextField(blank=True, verbose_name="Описание")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Категория")
    manufacturer = models.ForeignKey(Manufacturer, on_delete=models.CASCADE, related_name='products', null=True, blank=True, verbose_name="Производитель")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MinValueValidator(0)], verbose_name="Старая цена")
    stock_quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='шт', verbose_name="Единица измерения")
    weight = models.CharField(max_length=50, blank=True, verbose_name="Вес/объем")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Изображение")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)], verbose_name="Рейтинг")
    is_featured = models.BooleanField(default=False, verbose_name="Рекомендуемый")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    
    # Поля срока годности
    has_expiry_date = models.BooleanField(default=False, verbose_name="Имеет срок годности")
    expiry_date = models.DateField(blank=True, null=True, verbose_name="Срок годности")
    production_date = models.DateField(blank=True, null=True, verbose_name="Дата производства")
    shelf_life_days = models.PositiveIntegerField(blank=True, null=True, verbose_name="Срок хранения (дни)")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return int(((self.old_price - self.price) / self.old_price) * 100)
        return 0
    
    @property
    def expiry_status(self):
        """Возвращает статус срока годности"""
        if not self.has_expiry_date or not self.expiry_date:
            return None
        
        today = timezone.now().date()
        if self.expiry_date < today:
            return 'expired'
        elif (self.expiry_date - today).days <= 3:
            return 'expires_soon'
        elif (self.expiry_date - today).days <= 7:
            return 'expires_week'
        else:
            return 'fresh'


# ==================== ПАРТИИ ТОВАРОВ ====================

class ProductBatch(models.Model):
    """Партия товара со сроком годности"""
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name="Товар"
    )
    batch_number = models.CharField(max_length=100, verbose_name="Номер партии")
    production_date = models.DateField(verbose_name="Дата производства")
    expiry_date = models.DateField(verbose_name="Срок годности")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество в партии")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Остаток")
    supplier = models.CharField(max_length=200, blank=True, verbose_name="Поставщик")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Партия товара"
        verbose_name_plural = "Партии товаров"
        ordering = ['expiry_date', 'production_date']
        indexes = [
            models.Index(fields=['product', 'expiry_date']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['remaining_quantity']),
            models.Index(fields=['expiry_date', 'remaining_quantity']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - Партия {self.batch_number}"
    
    @property
    def is_expired(self):
        """Проверяет, истек ли срок годности партии"""
        return self.expiry_date < timezone.now().date()
    
    @property
    def days_until_expiry(self):
        """Возвращает количество дней до истечения срока годности"""
        delta = self.expiry_date - timezone.now().date()
        return delta.days
    
    @property
    def expiry_status(self):
        """Возвращает статус срока годности"""
        days = self.days_until_expiry
        if days < 0:
            return 'expired'
        elif days <= 3:
            return 'expires_soon'
        elif days <= 7:
            return 'expires_week'
        else:
            return 'fresh'
    
    @property
    def expiry_percent_remaining(self):
        """Возвращает процент оставшегося срока годности (0-100)"""
        if not self.production_date or not self.expiry_date:
            return None
        
        total_days = (self.expiry_date - self.production_date).days
        if total_days <= 0:
            return 0
        
        today = timezone.now().date()
        remaining_days = (self.expiry_date - today).days
        
        if remaining_days < 0:
            return 0
        
        percent = (remaining_days / total_days) * 100
        return min(100, max(0, percent))
    
    def is_sellable(self, min_percent=70):
        """
        Проверяет, можно ли продать эту партию покупателю
        По правилу: минимум 70% срока годности должно остаться
        """
        if self.is_expired:
            return False
        
        if self.remaining_quantity <= 0:
            return False
        
        percent = self.expiry_percent_remaining
        if percent is None:
            return not self.is_expired
        
        return percent >= min_percent


class BatchAuditLog(models.Model):
    """Аудит изменений партий товаров"""
    ACTION_CHOICES = [
        ('created', 'Создана'),
        ('updated', 'Обновлена'),
        ('quantity_changed', 'Изменено количество'),
        ('assigned', 'Назначена заказу'),
        ('unassigned', 'Снята с заказа'),
        ('spoiled', 'Списана'),
        ('deleted', 'Удалена'),
    ]
    
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name="Партия"
    )
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Действие"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batch_audit_logs',
        verbose_name="Пользователь"
    )
    old_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Старое значение (остаток)"
    )
    new_value = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Новое значение (остаток)"
    )
    comment = models.TextField(
        blank=True,
        verbose_name="Комментарий"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP-адрес"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    class Meta:
        verbose_name = "Лог изменений партии"
        verbose_name_plural = "Логи изменений партий"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch', 'created_at']),
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        user_name = self.user.username if self.user else "Система"
        return f"{self.get_action_display()} - {self.batch} ({user_name}, {self.created_at.strftime('%Y-%m-%d %H:%M')})"


# ==================== МАГАЗИНЫ ====================

class Store(models.Model):
    """Магазины"""
    name = models.CharField(max_length=200, verbose_name="Название магазина")
    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    working_hours = models.CharField(max_length=100, verbose_name="Часы работы")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    manager = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='managed_stores',
        verbose_name="Менеджер"
    )
    
    class Meta:
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class DeliverySlot(models.Model):
    """Слоты доставки"""
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='delivery_slots', verbose_name="Магазин")
    date = models.DateField(verbose_name="Дата")
    start_time = models.TimeField(verbose_name="Начало")
    end_time = models.TimeField(verbose_name="Окончание")
    capacity = models.PositiveIntegerField(default=10, verbose_name="Вместимость")
    reserved_count = models.PositiveIntegerField(default=0, verbose_name="Забронировано")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    
    class Meta:
        verbose_name = "Слот доставки"
        verbose_name_plural = "Слоты доставки"
        ordering = ['date', 'start_time']
        unique_together = [['store', 'date', 'start_time', 'end_time']]
    
    def __str__(self):
        return f"{self.store.name} - {self.date} {self.start_time}-{self.end_time}"
    
    def reserve(self, count=1):
        """Резервирует место в слоте"""
        if self.reserved_count + count <= self.capacity:
            self.reserved_count += count
            self.save(update_fields=['reserved_count'])
            return True
        return False
    
    def release(self, count=1):
        """Освобождает место в слоте"""
        self.reserved_count = max(0, self.reserved_count - count)
        self.save(update_fields=['reserved_count'])
    
    @property
    def available(self):
        """Проверяет, есть ли свободные места в слоте"""
        return self.is_active and (self.reserved_count < self.capacity)


class UserAddress(models.Model):
    """Адреса пользователей"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses', verbose_name="Пользователь")
    label = models.CharField(max_length=100, blank=True, verbose_name="Метка (дом, офис)")
    address = models.TextField(verbose_name="Адрес")
    entrance = models.CharField(max_length=20, blank=True, verbose_name="Подъезд")
    floor = models.CharField(max_length=10, blank=True, verbose_name="Этаж")
    apartment = models.CharField(max_length=20, blank=True, verbose_name="Квартира/офис")
    intercom_code = models.CharField(max_length=20, blank=True, verbose_name="Код домофона")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Широта")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Долгота")
    is_default = models.BooleanField(default=False, verbose_name="Адрес по умолчанию")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Адрес пользователя"
        verbose_name_plural = "Адреса пользователей"
        ordering = ['-is_default', '-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.label or self.address}"


# ==================== КОРЗИНА ====================

class Cart(models.Model):
    """Корзина покупок"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items', verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Количество")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"
        ordering = ['-added_at']
        unique_together = [['user', 'product']]
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name} x{self.quantity}"
    
    @property
    def total_price(self):
        """Возвращает общую стоимость позиции в корзине"""
        from decimal import Decimal
        return Decimal(str(self.quantity)) * self.product.price


# ==================== ЗАКАЗЫ ====================

class Order(models.Model):
    """Заказы"""
    STATUS_CHOICES = [
        ('created', 'Создан'),
        ('confirmed', 'Подтверждён'),
        ('ready', 'Готов'),
        ('in_transit', 'В пути'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменён'),
    ]
    
    DELIVERY_CHOICES = [
        ('delivery', 'Доставка'),
        ('pickup', 'Самовывоз'),
    ]
    
    PAYMENT_CHOICES = [
        ('card', 'Карта'),
        ('online', 'Онлайн'),
        ('sbp', 'СБП'),
        ('cash', 'Наличные'),
        ('cashback', 'Кешбэк'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Покупатель")
    order_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата заказа")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name="Статус")
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_CHOICES, verbose_name="Тип доставки")
    delivery_address = models.TextField(blank=True, verbose_name="Адрес доставки")
    pickup_point = models.ForeignKey(Store, on_delete=models.PROTECT, null=True, blank=True, related_name='pickup_orders', verbose_name="Точка самовывоза")
    fulfillment_store = models.ForeignKey(Store, on_delete=models.PROTECT, null=True, blank=True, related_name='fulfilled_orders', verbose_name="Магазин-комплектация")
    delivery_slot = models.ForeignKey('DeliverySlot', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="Слот доставки")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Общая сумма")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, verbose_name="Способ оплаты")
    comment = models.TextField(blank=True, verbose_name="Комментарий к заказу")
    favorite_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Скидка любимых категорий")
    promotion_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Скидка по акции")
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Стоимость доставки")
    
    # Поля отслеживания доставки
    tracking_number = models.CharField(max_length=50, blank=True, verbose_name="Номер отслеживания")
    estimated_delivery_time = models.DateTimeField(null=True, blank=True, verbose_name="Ожидаемое время доставки")
    actual_delivery_time = models.DateTimeField(null=True, blank=True, verbose_name="Фактическое время доставки")
    courier_name = models.CharField(max_length=100, blank=True, verbose_name="Имя курьера")
    courier_phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон курьера")
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-order_date']
    
    def __str__(self):
        return f"Заказ #{self.id} от {self.user.username}"


class OrderItem(models.Model):
    """Позиции заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)], verbose_name="Количество")
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена за единицу")
    batch = models.ForeignKey(
        ProductBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items',
        verbose_name="Партия товара"
    )
    
    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        unique_together = [['order', 'product']]
    
    def __str__(self):
        return f"{self.order} - {self.product.name} x{self.quantity}"
    
    @property
    def total_price(self):
        return self.quantity * self.price_per_unit


class OrderPicking(models.Model):
    """Сборка заказа"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает сборки'),
        ('in_progress', 'Собирается'),
        ('completed', 'Собран'),
        ('missing_items', 'Недостаточно товаров'),
        ('cancelled', 'Отменена'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='picking', verbose_name="Заказ")
    picker = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='pickings',
        verbose_name="Сборщик"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус сборки")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Начало сборки")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Окончание сборки")
    missing_items_comment = models.TextField(blank=True, verbose_name="Комментарий о недостающих товарах")
    notified_customer = models.BooleanField(default=False, verbose_name="Покупатель уведомлен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    
    class Meta:
        verbose_name = "Сборка заказа"
        verbose_name_plural = "Сборки заказов"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Сборка заказа #{self.order.id} - {self.get_status_display()}"


class OrderDelivery(models.Model):
    """Доставка заказа"""
    STATUS_CHOICES = [
        ('pending', 'Ожидает доставки'),
        ('assigned', 'Назначена'),
        ('picked_up', 'Забрал из магазина'),
        ('in_transit', 'В пути'),
        ('delivered', 'Доставлен'),
        ('failed', 'Не доставлен'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_tracking', verbose_name="Заказ")
    delivery_person = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_deliveries',
        verbose_name="Доставщик"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус доставки")
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name="Назначено")
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name="Забрано")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Доставлено")
    comment = models.TextField(blank=True, verbose_name="Комментарий доставщика")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Обновлено")
    
    class Meta:
        verbose_name = "Доставка заказа"
        verbose_name_plural = "Доставки заказов"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Доставка заказа #{self.order.id} - {self.get_status_display()}"


class OrderStatusHistory(models.Model):
    """История изменения статусов заказа"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history', verbose_name="Заказ")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, verbose_name="Статус")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время изменения")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    courier_name = models.CharField(max_length=100, blank=True, verbose_name="Имя курьера")
    courier_phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон курьера")
    
    class Meta:
        verbose_name = "История статуса заказа"
        verbose_name_plural = "История статусов заказов"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order} - {self.get_status_display()} ({self.timestamp})"


# ==================== ПЛАТЕЖИ ====================

class Payment(models.Model):
    """Платежи"""
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('refund', 'Возврат'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments', verbose_name="Заказ")
    payment_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата платежа")
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Сумма")
    payment_method = models.CharField(max_length=20, choices=Order.PAYMENT_CHOICES, verbose_name="Способ оплаты")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name="Статус")
    transaction_id = models.CharField(max_length=100, blank=True, verbose_name="ID транзакции")
    
    class Meta:
        verbose_name = "Платеж"
        verbose_name_plural = "Платежи"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Платеж #{self.id} - {self.order} - {self.amount} ₽"


class PaymentMethod(models.Model):
    """Способы оплаты пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_methods', verbose_name="Пользователь")
    brand = models.CharField(max_length=20, verbose_name="Бренд (Visa/MasterCard)")
    last4 = models.CharField(max_length=4, verbose_name="Последние 4 цифры")
    expiry_month = models.PositiveSmallIntegerField(verbose_name="Месяц истечения")
    expiry_year = models.PositiveSmallIntegerField(verbose_name="Год истечения")
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Способ оплаты"
        verbose_name_plural = "Способы оплаты"
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.brand} ****{self.last4} ({self.user.username})"


# ==================== ОТЗЫВЫ ====================

class Review(models.Model):
    """Отзывы на товары"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="Товар")
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Рейтинг")
    comment = models.TextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_approved = models.BooleanField(default=False, verbose_name="Одобрен")
    
    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ['-created_at']
        unique_together = [['user', 'product']]
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}★)"


# ==================== АКЦИИ И ПРОМОКОДЫ ====================

class Promotion(models.Model):
    """Акции"""
    name = models.CharField(max_length=200, default='Акция', verbose_name="Название акции")
    description = models.TextField(default='Описание акции', verbose_name="Описание")
    image = models.ImageField(upload_to='promotions/', blank=True, null=True, verbose_name="Изображение")
    discount_type = models.CharField(max_length=20, choices=[('percentage', 'Процент'), ('fixed', 'Фиксированная сумма')], default='percentage', verbose_name="Тип скидки")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Размер скидки")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Минимальная сумма заказа")
    start_date = models.DateTimeField(default=timezone.now, verbose_name="Дата начала")
    end_date = models.DateTimeField(default=timezone.now, verbose_name="Дата окончания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def is_valid(self):
        """Проверяет, активна ли акция в данный момент"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.is_active and
            self.start_date <= now <= self.end_date
        )
    
    def calculate_discount(self, order_total):
        """Рассчитывает размер скидки для суммы заказа"""
        from decimal import Decimal
        if self.discount_type == 'percentage':
            return Decimal(str(order_total)) * Decimal(str(self.discount_value)) / Decimal('100')
        else:
            return min(Decimal(str(self.discount_value)), Decimal(str(order_total)))


class UserPromotion(models.Model):
    """Использованные акции пользователями"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='used_promotions', verbose_name="Пользователь")
    promotion = models.ForeignKey(Promotion, on_delete=models.CASCADE, related_name='users', verbose_name="Акция")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='applied_promotions', verbose_name="Заказ")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Размер скидки")
    used_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата использования")
    
    class Meta:
        verbose_name = "Использованная акция"
        verbose_name_plural = "Использованные акции"
        unique_together = [['user', 'promotion', 'order']]
    
    def __str__(self):
        return f"{self.user.username} - {self.promotion.name} - Заказ #{self.order.id}"


class PromoCode(models.Model):
    """Промокоды"""
    code = models.CharField(max_length=20, unique=True, verbose_name="Код")
    description = models.CharField(max_length=200, verbose_name="Описание")
    discount_type = models.CharField(max_length=20, choices=[('percent', 'Процент'), ('fixed', 'Фиксированная сумма')], verbose_name="Тип скидки")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Размер скидки")
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Минимальная сумма заказа")
    max_uses = models.PositiveIntegerField(default=1, verbose_name="Максимум использований")
    used_count = models.PositiveIntegerField(default=0, verbose_name="Количество использований")
    start_date = models.DateTimeField(verbose_name="Дата начала")
    end_date = models.DateTimeField(verbose_name="Дата окончания")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.code


class PromoRule(models.Model):
    """Правила промо"""
    RULE_TYPE_CHOICES = [
        ('n_for_m', 'N за M (например 3 за 2)'),
        ('percent_category', 'Скидка % на категорию при мин. количестве'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Название")
    rule_type = models.CharField(max_length=30, choices=RULE_TYPE_CHOICES, verbose_name="Тип правила")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Категория")
    n = models.PositiveIntegerField(default=0, verbose_name="N")
    m = models.PositiveIntegerField(default=0, verbose_name="M")
    percent = models.PositiveIntegerField(default=0, verbose_name="Скидка %")
    min_qty = models.PositiveIntegerField(default=0, verbose_name="Мин. количество")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    per_user_once = models.BooleanField(default=False, verbose_name="Одноразовая для пользователя")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Правило промо"
        verbose_name_plural = "Правила промо"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


# ==================== ЛОЯЛЬНОСТЬ ====================

class LoyaltyCard(models.Model):
    """Карты лояльности"""
    LEVEL_CHOICES = [
        ('bronze', 'Бронзовый'),
        ('silver', 'Серебряный'),
        ('gold', 'Золотой'),
        ('platinum', 'Платиновый'),
    ]

    LEVEL_CONFIG = {
        'bronze': {
            'name': 'Бронзовый',
            'min_points': 0,
            'cashback_percent': Decimal('5'),
            'discount_percent': 5,
        },
        'silver': {
            'name': 'Серебряный',
            'min_points': 1000,
            'cashback_percent': Decimal('7'),
            'discount_percent': 10,
        },
        'gold': {
            'name': 'Золотой',
            'min_points': 5000,
            'cashback_percent': Decimal('10'),
            'discount_percent': 15,
        },
        'platinum': {
            'name': 'Платиновый',
            'min_points': 10000,
            'cashback_percent': Decimal('12'),
            'discount_percent': 20,
        },
    }
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='loyalty_card', verbose_name="Пользователь")
    card_number = models.CharField(max_length=20, unique=True, verbose_name="Номер карты")
    points = models.PositiveIntegerField(default=0, verbose_name="Баллы")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='bronze', verbose_name="Уровень")
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Общая сумма покупок")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    
    class Meta:
        verbose_name = "Карта лояльности"
        verbose_name_plural = "Карты лояльности"
        ordering = ['-points']
    
    def __str__(self):
        return f"{self.card_number} - {self.user.username} ({self.points} баллов)"

    def get_level_settings(self):
        return self.LEVEL_CONFIG.get(self.level, self.LEVEL_CONFIG['bronze'])
 
    def get_level_name(self):
        return self.get_level_settings()['name']
 
    def get_discount_percent(self):
        return self.get_level_settings()['discount_percent']
 
    def get_cashback_percent(self):
        return self.get_level_settings()['cashback_percent']

    def _ordered_levels(self):
        return sorted(self.LEVEL_CONFIG.items(), key=lambda item: item[1]['min_points'])

    def get_next_level_config(self):
        current_min = self.get_level_settings()['min_points']
        for code, config in self._ordered_levels():
            if config['min_points'] > current_min:
                return code, config
        return None, None

    def get_next_level_name(self):
        next_code, next_config = self.get_next_level_config()
        if next_config:
            return next_config['name']
        return "Максимальный уровень"

    def points_to_next_level(self):
        next_code, next_config = self.get_next_level_config()
        if not next_config:
            return 0
        return max(0, next_config['min_points'] - (self.points or 0))

    def progress_to_next_level(self):
        current_settings = self.get_level_settings()
        current_min = Decimal(str(current_settings['min_points']))
        points = Decimal(str(self.points or 0))
        next_code, next_config = self.get_next_level_config()
        if not next_config:
            return Decimal('100')
        next_min = Decimal(str(next_config['min_points']))
        span = next_min - current_min
        if span <= 0:
            return Decimal('100')
        progress = (points - current_min) / span * Decimal('100')
        return max(Decimal('0'), min(progress.quantize(Decimal('0.1')), Decimal('100')))
 
    def calculate_cashback(self, amount, order=None):
        amount = Decimal(str(amount or 0))
        if amount <= 0:
            return Decimal('0.00')
        base_percent = Decimal(str(self.get_cashback_percent()))
        cashback = Decimal('0')

        try:
            order_items = order.items.select_related('product__category') if order else None
        except AttributeError:
            order_items = None

        if order_items:
            favorite_map = {}
            try:
                favorites = self.user.favorite_categories.filter(is_active=True).select_related('category')
                favorite_map = {fav.category_id: Decimal(str(fav.cashback_multiplier)) for fav in favorites}
            except Exception:
                favorite_map = {}

            for item in order_items:
                line_amount = Decimal(str(item.total_price))
                percent = base_percent
                multiplier = favorite_map.get(getattr(item.product, 'category_id', None))
                if multiplier and multiplier > 0:
                    percent = (base_percent * multiplier)
                cashback += line_amount * percent / Decimal('100')
        else:
            cashback = amount * base_percent / Decimal('100')

        return cashback.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def update_level(self, commit=True):
        points = self.points or 0
        new_level = self.level
        for level_key, config in sorted(self.LEVEL_CONFIG.items(), key=lambda item: item[1]['min_points'], reverse=True):
            if points >= config['min_points']:
                new_level = level_key
                break
        if new_level != self.level:
            self.level = new_level
            if commit:
                self.save(update_fields=['level'])
        return self.level

    def add_cashback(self, purchase_amount, order=None, description=None):
        """Начислить кешбэк за покупку и обновить показатели карты."""
        amount = Decimal(str(purchase_amount or 0))
        if amount <= 0:
            return Decimal('0.00')

        if order and CashbackTransaction.objects.filter(order=order, transaction_type='earned').exists():
            return Decimal('0.00')

        cashback_amount = self.calculate_cashback(amount, order=order)

        points_to_add = int(amount.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
        self.total_spent = Decimal(str(self.total_spent or 0)) + amount
        self.points = (self.points or 0) + max(points_to_add, 0)
        self.last_activity = timezone.now()
        self.update_level(commit=False)
        self.save(update_fields=['points', 'level', 'total_spent', 'last_activity'])

        if cashback_amount > 0 and order is not None:
            CashbackTransaction.objects.create(
                user=self.user,
                order=order,
                amount=cashback_amount,
                transaction_type='earned',
                description=description or f'Кешбэк за заказ #{order.id}',
            )
            self.user.total_cashback_earned = Decimal(str(self.user.total_cashback_earned or 0)) + cashback_amount
            self.user.save(update_fields=['total_cashback_earned'])

        LoyaltyTransaction.objects.create(
            card=self,
            transaction_type='earned',
            points=max(points_to_add, 0),
            description=description or (f'Покупка #{order.id}' if order else 'Покупка'),
            order=order,
        )

        return cashback_amount


class LoyaltyTransaction(models.Model):
    """Транзакции лояльности"""
    TRANSACTION_TYPE_CHOICES = [
        ('earned', 'Начислено'),
        ('spent', 'Потрачено'),
        ('bonus', 'Бонус'),
        ('refund', 'Возврат'),
    ]
    
    card = models.ForeignKey(LoyaltyCard, on_delete=models.CASCADE, related_name='transactions', verbose_name="Карта")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="Тип транзакции")
    points = models.IntegerField(verbose_name="Баллы")
    description = models.CharField(max_length=200, verbose_name="Описание")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Заказ")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Транзакция лояльности"
        verbose_name_plural = "Транзакции лояльности"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.card.card_number} - {self.get_transaction_type_display()} - {self.points} баллов"


# ==================== КЕШБЭК ====================

class CashbackTransaction(models.Model):
    """Транзакции кешбэка"""
    TRANSACTION_TYPE_CHOICES = [
        ('earned', 'Заработан'),
        ('spent', 'Потрачен'),
        ('expired', 'Истек'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cashback_transactions', verbose_name="Пользователь")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='cashback_transactions', verbose_name="Заказ")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Сумма кешбэка")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, verbose_name="Тип транзакции")
    description = models.CharField(max_length=200, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата транзакции")
    
    class Meta:
        verbose_name = "Транзакция кешбэка"
        verbose_name_plural = "Транзакции кешбэка"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.get_transaction_type_display()} - {self.amount} ₽"


# ==================== ИЗБРАННОЕ ====================

class Favorite(models.Model):
    """Избранные товары (любимые товары) - максимум 4, скидка 10%"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites', verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Товар")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    last_updated = models.DateTimeField(auto_now=True, verbose_name="Дата последнего изменения")
    
    class Meta:
        verbose_name = "Любимый товар"
        verbose_name_plural = "Любимые товары"
        ordering = ['-created_at']
        unique_together = [['user', 'product']]
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
    
    @staticmethod
    def can_user_modify_favorites(user):
        """Проверяет, может ли пользователь изменять любимые товары (раз в неделю)"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Проверяем, есть ли недавние изменения
        last_favorite = Favorite.objects.filter(user=user).order_by('-last_updated').first()
        if last_favorite:
            week_ago = timezone.now() - timedelta(days=7)
            if last_favorite.last_updated > week_ago:
                return False, last_favorite.last_updated + timedelta(days=7)
        return True, None
    
    @staticmethod
    def get_user_favorites_count(user):
        """Возвращает количество любимых товаров пользователя"""
        return Favorite.objects.filter(user=user).count()


class FavoriteCategory(models.Model):
    """Любимые категории пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_categories', verbose_name="Пользователь")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='favorited_by', verbose_name="Категория")
    cashback_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=2.0, verbose_name="Множитель кешбэка")
    discount_percent = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(50)], verbose_name="Скидка (%)")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    class Meta:
        verbose_name = "Любимая категория"
        verbose_name_plural = "Любимые категории"
        unique_together = [['user', 'category']]
    
    def __str__(self):
        return f"{self.user.username} - {self.category.name}"


# ==================== ИСТОРИЯ ====================

class SearchHistory(models.Model):
    """История поиска"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_history', verbose_name="Пользователь")
    query = models.CharField(max_length=200, verbose_name="Поисковый запрос")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата поиска")
    
    class Meta:
        verbose_name = "История поиска"
        verbose_name_plural = "Истории поиска"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.query}"


class ViewHistory(models.Model):
    """История просмотров товаров"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='view_history', verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='viewed_by', verbose_name="Товар")
    viewed_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата просмотра")
    
    class Meta:
        verbose_name = "История просмотра"
        verbose_name_plural = "Истории просмотров"
        ordering = ['-viewed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.product.name}"


# ==================== УВЕДОМЛЕНИЯ ====================

class Notification(models.Model):
    """Уведомления пользователей"""
    NOTIFICATION_TYPE_CHOICES = [
        ('order', 'Заказ'),
        ('promotion', 'Акция'),
        ('delivery', 'Доставка'),
        ('payment', 'Оплата'),
        ('system', 'Системное'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Пользователь")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, verbose_name="Тип уведомления")
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title}"


# ==================== СПЕЦИАЛЬНЫЕ РАЗДЕЛЫ ====================

class SpecialSection(models.Model):
    """Специальные разделы"""
    name = models.CharField(max_length=100, verbose_name="Название раздела")
    description = models.TextField(verbose_name="Описание")
    icon = models.CharField(max_length=50, verbose_name="Иконка")
    color = models.CharField(max_length=7, default='#ff6b9d', verbose_name="Цвет")
    cashback_multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=2.0, verbose_name="Множитель кешбэка")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Специальный раздел"
        verbose_name_plural = "Специальные разделы"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class UserSpecialSection(models.Model):
    """Связь пользователей со специальными разделами"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='special_sections', verbose_name="Пользователь")
    section = models.ForeignKey(SpecialSection, on_delete=models.CASCADE, related_name='users', verbose_name="Раздел")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    
    class Meta:
        verbose_name = "Раздел пользователя"
        verbose_name_plural = "Разделы пользователей"
        unique_together = [['user', 'section']]
    
    def __str__(self):
        return f"{self.user.username} - {self.section.name}"


# ==================== ПОДДЕРЖКА ====================

class SupportTicket(models.Model):
    """Тикеты поддержки"""
    STATUS_CHOICES = [
        ('open', 'Открыт'),
        ('in_progress', 'В работе'),
        ('resolved', 'Решен'),
        ('closed', 'Закрыт'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]
    
    CATEGORY_CHOICES = [
        ('order', 'Заказ'),
        ('delivery', 'Доставка'),
        ('payment', 'Оплата'),
        ('product', 'Товар'),
        ('loyalty', 'Программа лояльности'),
        ('technical', 'Техническая поддержка'),
        ('other', 'Другое'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets', verbose_name="Пользователь")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Связанный заказ")
    subject = models.CharField(max_length=200, verbose_name="Тема")
    message = models.TextField(verbose_name="Сообщение")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', verbose_name="Статус")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium', verbose_name="Приоритет")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, verbose_name="Категория")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Тикет поддержки"
        verbose_name_plural = "Тикеты поддержки"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"#{self.id} - {self.subject} ({self.user.username})"


class SupportResponse(models.Model):
    """Ответы на тикеты поддержки"""
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='responses', verbose_name="Тикет")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Автор ответа")
    message = models.TextField(verbose_name="Сообщение")
    is_staff_response = models.BooleanField(default=False, verbose_name="Ответ сотрудника")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата ответа")
    
    class Meta:
        verbose_name = "Ответ поддержки"
        verbose_name_plural = "Ответы поддержки"
        ordering = ['created_at']
    
    def __str__(self):
        return f"Ответ на тикет #{self.ticket.id} от {self.user.username}"


# ==================== ОЦЕНКИ СОТРУДНИКОВ ====================

class EmployeeRating(models.Model):
    """Оценки сотрудников"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_ratings', verbose_name="Покупатель")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='employee_ratings', verbose_name="Заказ")
    employee_name = models.CharField(max_length=100, verbose_name="Имя сотрудника")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Оценка")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата оценки")
    
    class Meta:
        verbose_name = "Оценка сотрудника"
        verbose_name_plural = "Оценки сотрудников"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee_name} - {self.rating}★ от {self.user.username}"


# ==================== SMS-ВЕРИФИКАЦИЯ ====================

class PhoneVerification(models.Model):
    """SMS-верификация"""
    VERIFICATION_TYPE_CHOICES = [
        ('registration', 'Регистрация'),
        ('login', 'Вход'),
        ('password_reset', 'Сброс пароля'),
    ]
    
    phone = models.CharField(max_length=20, verbose_name="Номер телефона")
    code = models.CharField(max_length=6, verbose_name="SMS-код")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    expires_at = models.DateTimeField(verbose_name="Истекает")
    is_used = models.BooleanField(default=False, verbose_name="Использован")
    verification_type = models.CharField(max_length=20, choices=VERIFICATION_TYPE_CHOICES, default='registration', verbose_name="Тип верификации")
    
    class Meta:
        verbose_name = "SMS-верификация"
        verbose_name_plural = "SMS-верификации"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.phone} - {self.code} ({self.verification_type})"


# ==================== ОШИБКИ ====================

class ErrorLog(models.Model):
    """Логи ошибок"""
    ERROR_TYPE_CHOICES = [
        ('javascript', 'JavaScript ошибка'),
        ('server', 'Серверная ошибка'),
        ('validation', 'Ошибка валидации'),
        ('payment', 'Ошибка платежа'),
        ('cart', 'Ошибка корзины'),
        ('other', 'Другая ошибка'),
    ]
    
    error_type = models.CharField(max_length=20, choices=ERROR_TYPE_CHOICES, verbose_name="Тип ошибки")
    message = models.TextField(verbose_name="Сообщение об ошибке")
    stack_trace = models.TextField(blank=True, null=True, verbose_name="Стек вызовов")
    url = models.URLField(blank=True, null=True, verbose_name="URL страницы")
    user_agent = models.TextField(blank=True, null=True, verbose_name="User Agent")
    ip_address = models.GenericIPAddressField(blank=True, null=True, verbose_name="IP адрес")
    is_resolved = models.BooleanField(default=False, verbose_name="Исправлено")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Пользователь")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Товар")
    
    class Meta:
        verbose_name = "Ошибка"
        verbose_name_plural = "Ошибки"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_error_type_display()} - {self.message[:50]}"


# ==================== МЕТРИКИ ====================

class Metric(models.Model):
    """Метрики для Prometheus"""
    METRIC_TYPE_CHOICES = [
        ('counter', 'Counter'),
        ('gauge', 'Gauge'),
        ('histogram', 'Histogram'),
    ]
    
    name = models.CharField(max_length=255, db_index=True, verbose_name="Название метрики")
    value = models.FloatField(verbose_name="Значение")
    labels = models.JSONField(default=dict, blank=True, verbose_name="Метки")
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPE_CHOICES, default='counter', verbose_name="Тип метрики")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Время создания")
    
    class Meta:
        verbose_name = "Метрика"
        verbose_name_plural = "Метрики"
        db_table = "metrics"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['name', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.name} = {self.value}"


# ==================== ИСТОРИЯ ДЕЙСТВИЙ СБОРЩИКА ====================

class PickerActionLog(models.Model):
    """История действий сборщика"""
    ACTION_CHOICES = [
        ('order_taken', 'Взял заказ в работу'),
        ('batch_assigned', 'Назначил партию'),
        ('batch_unassigned', 'Снял партию'),
        ('order_completed', 'Завершил сборку'),
        ('missing_reported', 'Сообщил о недостаче'),
        ('order_started', 'Начал сборку'),
    ]
    
    picker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='picker_actions',
        verbose_name="Сборщик"
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='picker_actions',
        verbose_name="Заказ"
    )
    action_type = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        verbose_name="Тип действия"
    )
    details = models.TextField(
        blank=True,
        verbose_name="Детали"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP-адрес"
    )
    
    class Meta:
        verbose_name = "Действие сборщика"
        verbose_name_plural = "Действия сборщиков"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['picker', 'created_at']),
            models.Index(fields=['order', 'created_at']),
            models.Index(fields=['action_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.picker.username} - {self.get_action_type_display()} - Заказ #{self.order.id}"
