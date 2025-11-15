from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import logout as django_logout
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Avg, Sum, Count
from django.db import models
from django.utils import timezone
from .models import Category, Product, Promotion, UserPromotion, Cart, Order, OrderItem, User, Review, LoyaltyCard, LoyaltyTransaction, Favorite, SearchHistory, ViewHistory, PromoCode, Notification, EmployeeRating, FavoriteCategory, CashbackTransaction, SupportTicket, SupportResponse, SpecialSection, UserSpecialSection, Store, PhoneVerification, Payment, ErrorLog, OrderStatusHistory, PaymentMethod, PromoRule, UserAddress
from .notifications import send_order_confirmation
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .forms import PhoneLoginForm, PhoneVerificationForm, PhoneRegistrationForm, send_sms_code, verify_sms_code
from django.core.mail import mail_admins
from decimal import Decimal
import logging
import random
logger = logging.getLogger('paint_shop_project')

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.phone = self.cleaned_data["phone"]
        if commit:
            user.save()
        return user

def logout_view(request):
    """Безопасный выход с редиректом на главную для GET и POST."""
    if request.method in ("POST", "GET"):
        django_logout(request)
        return redirect('home')
    return redirect('home')

def phone_login_view(request):
    """Вход по номеру телефона (автоматически создает пользователя если его нет)"""
    if request.method == 'POST':
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            # Отправляем SMS-код (пользователь будет создан автоматически при подтверждении кода)
            send_sms_code(phone, 'login')
            request.session['phone_for_verification'] = phone
            messages.success(request, f'SMS-код отправлен на номер {phone}')
            return redirect('phone_verification', verification_type='login')
    else:
        form = PhoneLoginForm()
    
    return render(request, 'paint_shop_project/phone_login.html', {'form': form})

def phone_registration_start_view(request):
    """Начало регистрации по номеру телефона - отправка SMS"""
    if request.method == 'POST':
        form = PhoneLoginForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data['phone']
            # Проверяем, не зарегистрирован ли уже этот номер
            if User.objects.filter(phone=phone).exists():
                messages.error(request, 'Пользователь с таким номером уже зарегистрирован. Войдите в систему.')
                return redirect('phone_login')
            else:
                # Отправляем SMS-код для регистрации
                send_sms_code(phone, 'registration')
                request.session['phone_for_verification'] = phone
                messages.success(request, f'SMS-код отправлен на номер {phone}')
                return redirect('phone_verification', verification_type='registration')
    else:
        form = PhoneLoginForm()
    
    return render(request, 'paint_shop_project/phone_registration_start.html', {'form': form})

def phone_verification_view(request, verification_type='login'):
    """Верификация SMS-кода"""
    phone = request.session.get('phone_for_verification')
    if not phone:
        return redirect('phone_login')
    
    if request.method == 'POST':
        # Собираем код из отдельных полей
        code_parts = [
            request.POST.get('code1', ''),
            request.POST.get('code2', ''),
            request.POST.get('code3', ''),
            request.POST.get('code4', ''),
            request.POST.get('code5', ''),
            request.POST.get('code6', '')
        ]
        code = ''.join(code_parts)
        
        if len(code) == 6 and code.isdigit():
            is_valid, message = verify_sms_code(phone, code, verification_type)
            
            if is_valid:
                if verification_type == 'login':
                    # Авторизуем пользователя; если нет – создаем аккаунт автоматически
                    user = User.objects.filter(phone=phone).first()
                    if not user:
                        # Создаем пользователя с минимальными данными
                        user = User.objects.create_user(
                            username=phone,
                            phone=phone,
                            password=None,  # Без пароля, вход только по SMS
                        )
                        messages.info(request, 'Создан новый аккаунт. Заполните профиль в настройках.')
                    
                    login(request, user)
                    del request.session['phone_for_verification']
                    welcome_name = user.first_name or user.username
                    messages.success(request, f'Добро пожаловать, {welcome_name}!')
                    
                    # Перенаправление в зависимости от роли
                    if user.is_superuser or (user.is_staff and user.can_manage_store()):
                        return redirect('admin:index')
                    elif user.can_pick_orders():
                        return redirect('picker_dashboard')
                    elif user.can_deliver_orders():
                        return redirect('delivery_dashboard')
                    else:
                        return redirect('home')
                elif verification_type == 'registration':
                    # Переходим к завершению регистрации
                    return redirect('phone_registration')
            else:
                messages.error(request, message)
        else:
            messages.error(request, 'Введите полный 6-значный код')
    
    form = PhoneVerificationForm(initial={'phone': phone})
    
    return render(request, 'paint_shop_project/phone_verification.html', {
        'form': form, 
        'phone': phone,
        'verification_type': verification_type
    })

def phone_registration_view(request):
    """Регистрация по номеру телефона"""
    phone = request.session.get('phone_for_verification')
    if not phone:
        return redirect('phone_login')
    
    if request.method == 'POST':
        form = PhoneRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.phone = phone
            user.username = phone  # Используем телефон как username
            user.save()
            
            # Авторизуем пользователя
            login(request, user)
            del request.session['phone_for_verification']
            messages.success(request, f'Регистрация успешно завершена! Добро пожаловать, {user.first_name}!')
            
            # Перенаправление в зависимости от роли
            if user.is_superuser or (user.is_staff and user.can_manage_store()):
                return redirect('admin:index')
            elif user.can_pick_orders():
                return redirect('picker_dashboard')
            elif user.can_deliver_orders():
                return redirect('delivery_dashboard')
            else:
                return redirect('home')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    else:
        form = PhoneRegistrationForm(initial={'phone': phone})
    
    return render(request, 'paint_shop_project/phone_registration.html', {'form': form})

def resend_sms_view(request):
    """Повторная отправка SMS-кода"""
    if request.method == 'POST':
        phone = request.session.get('phone_for_verification')
        verification_type = request.POST.get('verification_type', 'login')
        
        if phone:
            send_sms_code(phone, verification_type)
            return JsonResponse({'success': True, 'message': 'SMS-код отправлен повторно'})
        else:
            return JsonResponse({'success': False, 'message': 'Номер телефона не найден'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def special_sections_view(request):
    """Страница специальных разделов"""
    sections = SpecialSection.objects.filter(is_active=True)
    user_section_ids = list(UserSpecialSection.objects.filter(user=request.user).values_list('section_id', flat=True))
    
    context = {
        'sections': sections,
        'user_section_ids': user_section_ids,
    }
    return render(request, 'paint_shop_project/special_sections.html', context)

@login_required
def join_section_view(request, section_id):
    """Присоединиться к специальному разделу"""
    if request.method == 'POST':
        section = get_object_or_404(SpecialSection, id=section_id)
        user_section, created = UserSpecialSection.objects.get_or_create(
            user=request.user,
            section=section
        )
        
        if created:
            return JsonResponse({'success': True, 'message': f'Вы присоединились к разделу "{section.name}"'})
        else:
            return JsonResponse({'success': False, 'message': 'Вы уже участвуете в этом разделе'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def leave_section_view(request, section_id):
    """Покинуть специальный раздел"""
    if request.method == 'POST':
        section = get_object_or_404(SpecialSection, id=section_id)
        user_section = UserSpecialSection.objects.filter(user=request.user, section=section).first()
        
        if user_section:
            user_section.delete()
            return JsonResponse({'success': True, 'message': f'Вы покинули раздел "{section.name}"'})
        else:
            return JsonResponse({'success': False, 'message': 'Вы не участвуете в этом разделе'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def favorite_categories_view(request):
    """Страница любимых категорий"""
    categories = Category.objects.filter(is_active=True)
    selected_categories = FavoriteCategory.objects.filter(user=request.user).select_related('category')
    selected_category_ids = list(selected_categories.values_list('category_id', flat=True))
    
    context = {
        'categories': categories,
        'selected_categories': selected_categories,
        'selected_category_ids': selected_category_ids,
    }
    return render(request, 'paint_shop_project/favorite_categories.html', context)

@login_required
def add_favorite_category_view(request, category_id):
    """Добавить категорию в избранное"""
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        favorite_category, created = FavoriteCategory.objects.get_or_create(
            user=request.user,
            category=category
        )
        
        if created:
            return JsonResponse({'success': True, 'message': f'Категория "{category.name}" добавлена в избранное'})
        else:
            return JsonResponse({'success': False, 'message': 'Категория уже в избранном'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def remove_favorite_category_view(request, category_id):
    """Удалить категорию из избранного"""
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id)
        favorite_category = FavoriteCategory.objects.filter(user=request.user, category=category).first()
        
        if favorite_category:
            favorite_category.delete()
            return JsonResponse({'success': True, 'message': f'Категория "{category.name}" удалена из избранного'})
        else:
            return JsonResponse({'success': False, 'message': 'Категория не найдена в избранном'})
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

def home_view(request):
    try:
        # Получаем активные категории
        categories = Category.objects.filter(is_active=True)[:8]
        
        # Получаем рекомендуемые товары
        featured_products = Product.objects.filter(is_featured=True, is_active=True)[:6]
        
        # Получаем акции
        promotions = Promotion.objects.filter(is_active=True)[:3]
        
    except Exception as e:
        # Если база данных не готова, используем тестовые данные
        categories = [
            {'name': 'Молочные продукты', 'slug': 'milk-products'},
            {'name': 'Мясо и птица', 'slug': 'meat-poultry'},
            {'name': 'Овощи и фрукты', 'slug': 'vegetables-fruits'},
            {'name': 'Хлеб и выпечка', 'slug': 'bread-bakery'},
            {'name': 'Напитки', 'slug': 'beverages'},
            {'name': 'Консервы', 'slug': 'canned-food'},
            {'name': 'Сладости', 'slug': 'sweets'},
            {'name': 'Замороженные продукты', 'slug': 'frozen-food'},
        ]
        
        featured_products = [
            {
                'name': 'Палочки сдобные Шарлиз Снежка с малиновым джемом',
                'price': 89.90,
                'old_price': 105.90,
                'weight': '370 г',
                'rating': 4.89,
                'discount_percent': 15,
            },
            {
                'name': 'Сдобные палочки Шарлиз Снежка с абрикосовым джемом',
                'price': 89.90,
                'old_price': 105.90,
                'weight': '370 г',
                'rating': 4.88,
                'discount_percent': 15,
            },
            {
                'name': 'Сыр Dolce Granto Пармезан тертый 40% БЗМЖ',
                'price': 199.90,
                'old_price': 299.90,
                'weight': '150 г',
                'rating': 4.85,
                'discount_percent': 33,
            },
            {
                'name': 'Томаты Медовые черри красные круглые',
                'price': 149.90,
                'old_price': 195.90,
                'weight': '200 г',
                'rating': 4.89,
                'discount_percent': 23,
            },
            {
                'name': 'Хурма',
                'price': 299.90,
                'old_price': 359.90,
                'weight': 'Цена за 1 кг',
                'rating': 4.78,
                'discount_percent': 17,
            },
            {
                'name': 'Молоко Домик в деревне 3.2%',
                'price': 89.90,
                'old_price': None,
                'weight': '1 л',
                'rating': 4.75,
                'discount_percent': 0,
            },
        ]
        
        promotions = [
            {
                'title': 'Скидка 500 ₽ на первый заказ от 1500 ₽',
                'description': 'Получите скидку 500 рублей на ваш первый заказ при сумме покупки от 1500 рублей',
            },
            {
                'title': 'Бесплатная доставка от 2000 ₽',
                'description': 'Закажите на сумму от 2000 рублей и получите бесплатную доставку',
            },
            {
                'title': 'Скидки до 50% на молочные продукты',
                'description': 'Специальные цены на молочные продукты и сыры',
            },
        ]
    
    # Количество товаров пользователя в корзине (для бейджей на главной)
    product_id_to_qty = {}
    try:
        if request.user.is_authenticated:
            product_id_to_qty = {pid: qty for pid, qty in Cart.objects.filter(user=request.user).values_list('product_id', 'quantity')}
    except Exception:
        product_id_to_qty = {}

    context = {
        'categories': categories,
        'featured_products': featured_products,
        'promotions': promotions,
        'product_id_to_qty': product_id_to_qty,
    }
    return render(request, 'paint_shop_project/home.html', context)

def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать в Жевжик, {username}!')
                
                # Перенаправление в зависимости от роли
                if user.is_superuser or (user.is_staff and user.can_manage_store()):
                    return redirect('admin:index')
                elif user.can_pick_orders():
                    return redirect('picker_dashboard')
                elif user.can_deliver_orders():
                    return redirect('delivery_dashboard')
                else:
                    return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'paint_shop_project/register.html', {'form': form})

def login_view(request):
    import logging
    logger = logging.getLogger('paint_shop_project')
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        
        # Логируем попытку входа
        logger.info(f"Попытка входа пользователя: {username} с IP: {get_client_ip(request)}")
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            logger.info(f"Успешный вход пользователя: {username} (ID: {user.id})")
            messages.success(request, f'Добро пожаловать в Жевжик, {username}!')
            
            # Перенаправление в зависимости от роли
            if user.is_superuser or (user.is_staff and user.can_manage_store()):
                # Администратор или менеджер - в админку
                return redirect('admin:index')
            elif user.can_pick_orders():
                # Сборщик - в панель сборщика
                return redirect('picker_dashboard')
            elif user.can_deliver_orders():
                # Доставщик - в панель доставщика
                return redirect('delivery_dashboard')
            else:
                # Обычный пользователь - на главную
                return redirect('home')
        else:
            logger.warning(f"Неудачная попытка входа пользователя: {username} с IP: {get_client_ip(request)}")
            messages.error(request, 'Неверное имя пользователя или пароль.')
    return render(request, 'paint_shop_project/login.html')

def cart_count_view(request):
    """Получить количество товаров в корзине"""
    if request.user.is_authenticated:
        count = Cart.objects.filter(user=request.user).count()
    else:
        count = 0
    return JsonResponse({'count': count})

@login_required
def _calculate_cart_promotions(cart_items):
    """Расширенная промо: 1+1 (сладости), mix&match (напитки) + PromoRule."""
    from decimal import Decimal
    extra_discount = Decimal('0')
    # 1+1 для категории 'Сладости'
    sweets_qs = [ci for ci in cart_items if getattr(ci.product.category, 'slug', '') == 'sweets']
    for ci in sweets_qs:
        free_units = ci.quantity // 2
        if free_units > 0:
            extra_discount += Decimal(str(ci.product.price)) * free_units
    # mix&match: напитки — при суммарно >=3 единиц скидка 10% на напитки
    beverages = [ci for ci in cart_items if getattr(ci.product.category, 'slug', '') == 'beverages']
    beverages_qty = sum(ci.quantity for ci in beverages)
    if beverages_qty >= 3:
        beverages_subtotal = sum(Decimal(str(ci.total_price)) for ci in beverages)
        extra_discount += beverages_subtotal * Decimal('0.10')

    # Общие правила PromoRule (активные и по времени)
    try:
        from django.utils import timezone
        now = timezone.now()
        rules = PromoRule.objects.filter(is_active=True, start_date__lte=now, end_date__gte=now)
        for rule in rules:
            if rule.rule_type == 'n_for_m' and rule.category:
                qty_sum = sum(ci.quantity for ci in cart_items if ci.product.category_id == rule.category_id)
                if qty_sum >= max(rule.n, rule.m, 1):
                    # Скидка = бесплатные единицы по самой дешёвой цене категории
                    free_units = (qty_sum // max(rule.n, 1)) * max(rule.n - rule.m, 0)
                    if free_units > 0:
                        cat_items = [ci for ci in cart_items if ci.product.category_id == rule.category_id]
                        unit_prices = []
                        for ci in cat_items:
                            unit_prices += [Decimal(str(ci.product.price))] * ci.quantity
                        unit_prices.sort()  # самые дешёвые бесплатно
                        extra_discount += sum(unit_prices[:free_units])
            elif rule.rule_type == 'percent_category' and rule.category and rule.percent > 0:
                cat_items = [ci for ci in cart_items if ci.product.category_id == rule.category_id]
                qty_sum = sum(ci.quantity for ci in cat_items)
                if qty_sum >= max(rule.min_qty, 1):
                    cat_subtotal = sum(Decimal(str(ci.total_price)) for ci in cat_items)
                    extra_discount += cat_subtotal * Decimal(str(rule.percent/100))
    except Exception:
        pass
    return extra_discount


def cart_summary_view(request):
    """Возвращает актуальные суммы корзины с учетом скидок и ожидаемый кешбэк"""
    logger.debug("cart_summary_view user=%s", getattr(request.user, 'id', None))
    cart_items = Cart.objects.filter(user=request.user)
    subtotal = sum(item.total_price for item in cart_items)
    # Скидка любимых категорий
    favorite_discount_amount = 0.0
    try:
        for item in cart_items:
            discount_percent = 0
            if hasattr(request.user, 'get_favorite_categories_discount'):
                discount_percent = request.user.get_favorite_categories_discount(item.product.category)
            if discount_percent and discount_percent > 0:
                favorite_discount_amount += float(item.total_price) * float(discount_percent) / 100.0
    except Exception:
        favorite_discount_amount = 0.0
    favorite_discount_amount = round(favorite_discount_amount, 2)

    # Лучшая активная акция (оценочно)
    from django.utils import timezone
    active_promotions = Promotion.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    promotion_discount = 0.0
    for promo in active_promotions:
        try:
            disc = float(promo.calculate_discount(max(float(subtotal) - favorite_discount_amount, 0.0)))
            promotion_discount = max(promotion_discount, disc)
        except Exception:
            pass
    # Доп. промо: 1+1 и mix&match
    try:
        extra_disc = float(_calculate_cart_promotions(cart_items))
    except Exception:
        extra_disc = 0.0
    total_after_discounts = max(float(subtotal) - favorite_discount_amount - promotion_discount - extra_disc, 0.0)

    # Ожидаемый кешбэк
    expected_cashback = 0.0
    try:
        loyalty_card = getattr(request.user, 'loyalty_card', None)
        if loyalty_card:
            expected_cashback = float(loyalty_card.calculate_cashback(total_after_discounts))
    except Exception:
        expected_cashback = 0.0

    data = {
        'subtotal': round(float(subtotal), 2),
        'favorite_discount_amount': round(float(favorite_discount_amount), 2),
        'promotion_discount': round(float(promotion_discount + extra_disc), 2),
        'total_after_discounts': round(float(total_after_discounts), 2),
        'expected_cashback': round(float(expected_cashback), 2),
    }
    logger.debug("cart_summary_view result=%s", data)
    return JsonResponse(data)

@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user)
    subtotal = sum(item.total_price for item in cart_items)
    # Скидка по любимым категориям и ожидаемый кешбэк
    favorite_discount_amount = 0.0
    try:
        for item in cart_items:
            discount_percent = 0
            if hasattr(request.user, 'get_favorite_categories_discount'):
                discount_percent = request.user.get_favorite_categories_discount(item.product.category)
            if discount_percent and discount_percent > 0:
                favorite_discount_amount += float(item.total_price) * float(discount_percent) / 100.0
    except Exception:
        favorite_discount_amount = 0.0
    favorite_discount_amount = round(favorite_discount_amount, 2)

    # Акции (без промокода на корзине: просто показать ориентировочно лучшую)
    from django.utils import timezone
    active_promotions = Promotion.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    promotion_discount = 0.0
    for promo in active_promotions:
        try:
            disc = float(promo.calculate_discount(max(float(subtotal) - favorite_discount_amount, 0.0)))
            promotion_discount = max(promotion_discount, disc)
        except Exception:
            pass
    total_after_discounts = max(float(subtotal) - favorite_discount_amount - promotion_discount, 0.0)

    # Ожидаемый кешбэк
    expected_cashback = 0
    try:
        loyalty_card = getattr(request.user, 'loyalty_card', None)
        if loyalty_card:
            expected_cashback = float(loyalty_card.calculate_cashback(total_after_discounts))
    except Exception:
        expected_cashback = 0

    context = {
        'cart_items': cart_items,
        'total': subtotal,
        'cart_total': subtotal,
        'favorite_discount_amount': favorite_discount_amount,
        'promotion_discount': round(promotion_discount, 2),
        'expected_cashback': expected_cashback,
    }
    return render(request, 'paint_shop_project/cart.html', context)

@login_required
def add_to_cart(request, product_id):
    import logging
    logger = logging.getLogger('paint_shop_project')
    
    if not request.user.is_authenticated:
        logger.warning(f"Попытка добавления в корзину неавторизованным пользователем. IP: {get_client_ip(request)}")
        return JsonResponse({'success': False, 'message': 'Необходимо войти в систему'}, status=401)
    
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, id=product_id)
            logger.info(f"Пользователь {request.user.username} добавляет товар {product.name} в корзину")
            
            cart_item, created = Cart.objects.get_or_create(
                user=request.user,
                product=product,
                defaults={'quantity': 1}
            )
            if not created:
                # Ограничение количеством на складе
                max_qty = getattr(product, 'stock_quantity', None)
                new_qty = cart_item.quantity + 1
                if max_qty is not None and max_qty > 0:
                    new_qty = min(new_qty, max_qty)
                cart_item.quantity = new_qty
                cart_item.save()
            
            logger.info(f"Товар {product.name} успешно добавлен в корзину пользователя {request.user.username}")
            
            accepts_json = 'application/json' in request.headers.get('Accept', '')
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Всегда возвращаем JSON для AJAX запросов
            if accepts_json or is_ajax or request.headers.get('Content-Type') == 'application/json':
                # Подсчитываем текущее количество этой позиции в корзине и общий счётчик
                try:
                    qty = Cart.objects.filter(user=request.user, product=product).values_list('quantity', flat=True).first() or 0
                    total_count = Cart.objects.filter(user=request.user).aggregate(total=Sum('quantity'))['total'] or 0
                except Exception:
                    qty = Cart.objects.filter(user=request.user, product=product).values_list('quantity', flat=True).first() or 0
                    total_count = 0
                return JsonResponse({
                    'success': True,
                    'message': f'{product.name} добавлен в корзину!',
                    'quantity': int(qty),
                    'cart_count': int(total_count),
                    'product_id': product.id,
                })
            
            messages.success(request, f'{product.name} добавлен в корзину!')
            return redirect('home')
        except Exception as e:
            logger.error(f"Ошибка при добавлении товара в корзину: {str(e)}")
            return JsonResponse({'success': False, 'message': 'Ошибка при добавлении товара в корзину'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Метод не разрешен'}, status=405)

@login_required
def get_cart_id_by_product(request, product_id):
    """Получить cart_id для товара текущего пользователя"""
    try:
        cart_item = Cart.objects.filter(user=request.user, product_id=product_id).first()
        if cart_item:
            return JsonResponse({
                'success': True,
                'cart_id': cart_item.id,
                'quantity': cart_item.quantity
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Товар не найден в корзине'
            })
    except Exception as e:
        logger.error(f"Ошибка при получении cart_id: {str(e)}")
        return JsonResponse({'success': False, 'message': 'Ошибка при получении данных'}, status=500)

@login_required
def update_cart_quantity(request, cart_id):
    """Обновить количество товара в корзине"""
    if request.method == 'POST':
        cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
        quantity = int(request.POST.get('quantity', 1))
        logger.info("update_cart_quantity user=%s cart_id=%s requested=%s", request.user.id, cart_id, quantity)
        
        if quantity <= 0:
            cart_item.delete()
            return JsonResponse({'success': True, 'message': 'Товар удален из корзины!'})
        
        # Применяем ограничение по остатку товара
        max_qty = getattr(cart_item.product, 'stock_quantity', None)
        if max_qty is not None and max_qty > 0:
            quantity = max(1, min(quantity, max_qty))
        cart_item.quantity = quantity
        cart_item.save()
        logger.debug("update_cart_quantity applied user=%s cart_id=%s new=%s max=%s", request.user.id, cart_id, cart_item.quantity, getattr(cart_item.product, 'stock_quantity', None))
        
        return JsonResponse({
            'success': True, 
            'message': 'Количество обновлено!',
            'quantity': cart_item.quantity,
            'max_quantity': getattr(cart_item.product, 'stock_quantity', None) or '',
            'total_price': float(cart_item.total_price)
        })
    else:
        return JsonResponse({'success': False, 'message': 'Метод не разрешен'}, status=405)

@login_required
def remove_from_cart(request, cart_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
        logger.info("remove_from_cart user=%s cart_id=%s product_id=%s", request.user.id, cart_id, cart_item.product_id)
        cart_item.delete()
        
        accepts_json = 'application/json' in request.headers.get('Accept', '')
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if accepts_json or is_ajax or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({'success': True, 'message': 'Товар удален из корзины!'})
        
        messages.success(request, 'Товар удален из корзины!')
        return redirect('cart')
    else:
        return JsonResponse({'success': False, 'message': 'Метод не разрешен'}, status=405)

@login_required
def checkout_view(request):
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items.exists():
        messages.warning(request, 'Ваша корзина пуста!')
        return redirect('cart')
    
    subtotal = sum(item.total_price for item in cart_items)
    # Скидка по любимым категориям
    favorite_discount_amount = 0.0
    try:
        for item in cart_items:
            discount_percent = 0
            if hasattr(request.user, 'get_favorite_categories_discount'):
                discount_percent = request.user.get_favorite_categories_discount(item.product.category)
            if discount_percent and discount_percent > 0:
                favorite_discount_amount += float(item.total_price) * float(discount_percent) / 100.0
    except Exception:
        favorite_discount_amount = 0.0
    favorite_discount_amount = round(favorite_discount_amount, 2)
    
    # Скидка 10% на любимые товары (максимум 4)
    favorite_products_discount = 0.0
    try:
        from .models import Favorite
        user_favorite_product_ids = set(Favorite.objects.filter(user=request.user).values_list('product_id', flat=True))
        for item in cart_items:
            if item.product.id in user_favorite_product_ids:
                # Скидка 10% на любимые товары
                favorite_products_discount += float(item.total_price) * 0.10
    except Exception:
        favorite_products_discount = 0.0
    favorite_products_discount = round(favorite_products_discount, 2)

    # Применяем промокод, если задан, иначе лучшую действующую акцию к промежуточной сумме (после любимых категорий)
    from django.utils import timezone
    active_promotions = Promotion.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    # Одноразовые: исключим уже использованные пользователем
    try:
        used_ids = set(UserPromotion.objects.filter(user=request.user).values_list('promotion_id', flat=True)) if request.user.is_authenticated else set()
        active_promotions = active_promotions.exclude(id__in=used_ids)
    except Exception:
        pass
    promotion_discount = 0.0
    applied_promotion = None
    applied_promo_code = None
    promo_message = None
    base_for_promo = max(float(subtotal) - favorite_discount_amount - favorite_products_discount, 0.0)
    # Принудительное применение промокода, если передан
    promo_code_value = request.GET.get('promo_code') or None
    if promo_code_value:
        try:
            promo_code_obj = PromoCode.objects.get(code=promo_code_value)
            if promo_code_obj.is_valid() and base_for_promo >= float(promo_code_obj.min_order_amount):
                if promo_code_obj.discount_type == 'percent':
                    promotion_discount = float(base_for_promo) * float(promo_code_obj.discount_value) / 100.0
                else:
                    promotion_discount = min(float(promo_code_obj.discount_value), float(base_for_promo))
                applied_promo_code = promo_code_obj
            else:
                promo_message = 'Промокод недействителен или не подходит по сумме заказа'
        except PromoCode.DoesNotExist:
            promo_message = 'Промокод не найден'
    
    # Если промокод не применён, применяем выбранную пользователем акцию (либо ничего)
    selected_promotion_id = request.GET.get('promotion_id')
    if not applied_promo_code:
        if selected_promotion_id:
            try:
                sp = active_promotions.get(id=int(selected_promotion_id))
                promotion_discount = float(sp.calculate_discount(base_for_promo))
                applied_promotion = sp
            except Exception:
                applied_promotion = None
                promotion_discount = 0.0
        else:
            promotion_discount = 0.0
            applied_promotion = None

    # Стоимость доставки по умолчанию для отображения (переключается на фронте)
    # Бесплатная доставка от 5000 (после скидок)
    FREE_DELIVERY_THRESHOLD = 5000
    default_delivery_cost = 200

    total_without_delivery = max(base_for_promo - promotion_discount, 0.0)
    
    # Определяем тип доставки из GET параметров или по умолчанию самовывоз
    selected_delivery_type = request.GET.get('delivery_type', 'pickup')
    
    # Отображаемый итог: для самовывоза доставка = 0, для доставки зависит от порога
    if selected_delivery_type == 'delivery':
        delivery_display_cost = 0 if total_without_delivery >= FREE_DELIVERY_THRESHOLD else default_delivery_cost
    else:
        delivery_display_cost = 0  # Самовывоз - бесплатно
    
    total = total_without_delivery + delivery_display_cost

    # Список акций с потенциальной экономией
    promotions_with_saving = []
    for promo in active_promotions:
        try:
            promotions_with_saving.append({
                'promo': promo,
                'saving': float(promo.calculate_discount(base_for_promo))
            })
        except Exception:
            promotions_with_saving.append({'promo': promo, 'saving': 0.0})

    # Адреса пользователя и тайм-слоты
    user_addresses = []
    delivery_slots = []
    try:
        user_addresses = request.user.addresses.all() if request.user.is_authenticated else []
    except Exception:
        user_addresses = []
    try:
        from .models import DeliverySlot
        delivery_slots = DeliverySlot.objects.filter(is_active=True, date__gte=timezone.now().date()).order_by('date','start_time')[:50]
    except Exception:
        delivery_slots = []

    # Способы оплаты пользователя (маски)
    payment_methods = []
    try:
        payment_methods = PaymentMethod.objects.filter(user=request.user).order_by('-is_default','-created_at') if request.user.is_authenticated else []
    except Exception:
        payment_methods = []

    # Баланс кешбэка пользователя
    cashback_balance = 0
    try:
        from .models import CashbackTransaction
        total_earned = CashbackTransaction.objects.filter(
            user=request.user, 
            transaction_type='earned'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        total_spent = CashbackTransaction.objects.filter(
            user=request.user, 
            transaction_type='spent'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        cashback_balance = float(total_earned - total_spent)
    except Exception:
        cashback_balance = 0

    logger.info("checkout_view user=%s promo_code=%s promotion_id=%s delivery_type=%s", getattr(request.user,'id',None), request.GET.get('promo_code'), request.GET.get('promotion_id'), selected_delivery_type)
    context = {
        'cart_items': cart_items,
        'total': subtotal,
        'favorite_discount_amount': favorite_discount_amount,
        'favorite_products_discount': favorite_products_discount,
        'promotion_discount': round(promotion_discount, 2),
        'applied_promotion': applied_promotion,
        'applied_promo_code': applied_promo_code,
        'promo_message': promo_message,
        'total_without_delivery': total_without_delivery,
        'default_delivery_cost': default_delivery_cost,
        'free_delivery_threshold': FREE_DELIVERY_THRESHOLD,
        'computed_total': total,
        'promotions_with_saving': promotions_with_saving,
        'user_addresses': user_addresses,
        'cashback_balance': cashback_balance,
        'delivery_slots': delivery_slots,
        'delivery_display_cost': delivery_display_cost,
        'selected_promotion_id': int(selected_promotion_id) if selected_promotion_id else None,
        'payment_methods': payment_methods,
        'selected_delivery_type': selected_delivery_type,  # Добавляем выбранный тип доставки
    }
    return render(request, 'paint_shop_project/checkout.html', context)

@login_required
def create_order(request):
    if request.method == 'POST':
        logger.info("create_order start user=%s", request.user.id)
        payment_method = request.POST.get('payment_method', 'cash')
        
        # Для онлайн-оплаты заказ создается только после успешной оплаты в yoomoney_payment_view или sbp_payment_view
        # Если это AJAX запрос с онлайн-оплатой, возвращаем ошибку
        if payment_method in ['online', 'sbp'] or (payment_method and payment_method.startswith('saved:')):
            # Проверяем, это AJAX запрос или обычная отправка формы
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': False, 'message': 'Для онлайн-оплаты используйте процесс оплаты'}, status=400)
            else:
                # Если это обычная отправка формы (не должно происходить, но на всякий случай)
                messages.error(request, 'Для онлайн-оплаты используйте процесс оплаты на странице оформления заказа.')
                return redirect('checkout')
        
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            messages.warning(request, 'Ваша корзина пуста!')
            return redirect('cart')
        
        subtotal = sum(item.total_price for item in cart_items)
        delivery_type = request.POST.get('delivery_type', 'pickup')
        delivery_address = request.POST.get('delivery_address', '')
        delivery_entrance = request.POST.get('delivery_entrance', '')
        delivery_apartment = request.POST.get('delivery_apartment', '')
        delivery_floor = request.POST.get('delivery_floor', '')
        delivery_comment = request.POST.get('comment', '')
        selected_address_id = request.POST.get('address_id')
        save_address = request.POST.get('save_address') == 'on'
        fulfillment_store_id = request.POST.get('fulfillment_store_id')
        delivery_slot_id = request.POST.get('delivery_slot_id')
        
        # Добавляем стоимость доставки если выбрана доставка
        # Бесплатная доставка от 5000 (будет пересчитано после применения скидок)
        FREE_DELIVERY_THRESHOLD = 5000

        # Скидка по любимым категориям (как на checkout)
        favorite_discount_amount = 0.0
        try:
            for item in cart_items:
                discount_percent = 0
                if hasattr(request.user, 'get_favorite_categories_discount'):
                    discount_percent = request.user.get_favorite_categories_discount(item.product.category)
                if discount_percent and discount_percent > 0:
                    favorite_discount_amount += float(item.total_price) * float(discount_percent) / 100.0
        except Exception:
            favorite_discount_amount = 0.0
        favorite_discount_amount = round(favorite_discount_amount, 2)
        
        # Скидка 10% на любимые товары (максимум 4)
        favorite_products_discount = 0.0
        try:
            from .models import Favorite
            user_favorite_product_ids = set(Favorite.objects.filter(user=request.user).values_list('product_id', flat=True))
            for item in cart_items:
                if item.product.id in user_favorite_product_ids:
                    # Скидка 10% на любимые товары
                    favorite_products_discount += float(item.total_price) * 0.10
        except Exception:
            favorite_products_discount = 0.0
        favorite_products_discount = round(favorite_products_discount, 2)

        # Промокод/акции
        from django.utils import timezone
        active_promotions = Promotion.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
        promotion_discount = 0.0
        applied_promotion = None
        applied_promo_code = None
        base_for_promo = max(float(subtotal) - favorite_discount_amount - favorite_products_discount, 0.0)
        promo_code_value = request.POST.get('promo_code') or None
        # Промокод имеет приоритет
        if promo_code_value:
            try:
                promo_code_obj = PromoCode.objects.get(code=promo_code_value)
                if promo_code_obj.is_valid() and base_for_promo >= float(promo_code_obj.min_order_amount):
                    if promo_code_obj.discount_type == 'percent':
                        promotion_discount = float(base_for_promo) * float(promo_code_obj.discount_value) / 100.0
                    else:
                        promotion_discount = min(float(promo_code_obj.discount_value), float(base_for_promo))
                    applied_promo_code = promo_code_obj
                    # увеличиваем использований
                    try:
                        promo_code_obj.used_count = (promo_code_obj.used_count or 0) + 1
                        promo_code_obj.save(update_fields=['used_count'])
                    except Exception:
                        pass
                # иначе упадём на авто-акции ниже
            except PromoCode.DoesNotExist:
                pass
        for promo in active_promotions:
            try:
                disc = float(promo.calculate_discount(base_for_promo))
                if disc > promotion_discount and not applied_promo_code:
                    promotion_discount = disc
                    applied_promotion = promo
            except Exception:
                pass
        # Доп. промо (1+1, mix&match)
        try:
            extra_disc = float(_calculate_cart_promotions(cart_items))
            promotion_discount += extra_disc
        except Exception:
            pass

        total_without_delivery = max(base_for_promo - promotion_discount, 0.0)
        
        # Расчет стоимости доставки
        if delivery_type == 'delivery':
            # Бесплатная доставка от 5000 (после скидок)
            if total_without_delivery >= FREE_DELIVERY_THRESHOLD:
                delivery_cost = 0
            else:
                delivery_cost = 200
        else:
            # Самовывоз - доставка бесплатна
            delivery_cost = 0
        
        final_total = total_without_delivery + float(delivery_cost)
        
        # Обработка использования кешбэка (чекбокс, не способ оплаты)
        cashback_used = 0
        use_cashback = request.POST.get('use_cashback') == 'on'
        if use_cashback:
            try:
                from .models import CashbackTransaction
                from decimal import Decimal
                total_earned = CashbackTransaction.objects.filter(
                    user=request.user, 
                    transaction_type='earned'
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                total_spent = CashbackTransaction.objects.filter(
                    user=request.user, 
                    transaction_type='spent'
                ).aggregate(total=models.Sum('amount'))['total'] or 0
                cashback_balance = Decimal(str(total_earned - total_spent))
                
                if cashback_balance <= 0:
                    messages.error(request, 'Недостаточно средств на балансе кешбэка')
                    return redirect('checkout')
                
                # Получаем сумму кешбэка из формы
                cashback_amount_str = request.POST.get('cashback_amount', '0')
                try:
                    # Проверяем, что строка не пустая и содержит только цифры и точку
                    if not cashback_amount_str or not cashback_amount_str.strip():
                        cashback_amount_str = '0'
                    # Удаляем пробелы и заменяем запятую на точку
                    cashback_amount_str = cashback_amount_str.strip().replace(',', '.')
                    # Проверяем, что это валидное число
                    if not cashback_amount_str.replace('.', '').replace('-', '').isdigit():
                        cashback_amount_str = '0'
                    cashback_amount = Decimal(cashback_amount_str)
                    # Ограничиваем максимальной суммой баланса и итоговой суммой заказа
                    cashback_used = min(cashback_balance, Decimal(str(final_total)), cashback_amount)
                    if cashback_used < 0:
                        cashback_used = Decimal('0')
                except (ValueError, TypeError, Exception) as e:
                    logger.warning("Invalid cashback amount: %s, error: %s", cashback_amount_str, e)
                    cashback_used = Decimal('0')
                
                final_total = float(Decimal(str(final_total)) - cashback_used)
                
            except Exception as e:
                logger.exception("cashback_payment_error: %s", e)
                messages.error(request, 'Ошибка при использовании кешбэка')
                return redirect('checkout')
        
        # Определяем магазин комплектации и слот (если доставка)
        fulfillment_store = None
        selected_slot = None
        if fulfillment_store_id:
            try:
                fulfillment_store = Store.objects.get(id=int(fulfillment_store_id))
            except Exception:
                fulfillment_store = None
        if delivery_type == 'delivery' and delivery_slot_id:
            from .models import DeliverySlot
            try:
                selected_slot = DeliverySlot.objects.select_for_update().get(id=int(delivery_slot_id))
                if not selected_slot.available:
                    messages.error(request, 'Выбранный слот доставки недоступен')
                    return redirect('checkout')
            except DeliverySlot.DoesNotExist:
                messages.error(request, 'Слот доставки не найден')
                logger.warning("create_order slot_not_found user=%s slot=%s", request.user.id, delivery_slot_id)
                return redirect('checkout')

        # Адрес: выбрать сохраненный или сохранить новый (только для доставки)
        if delivery_type == 'delivery':
            # Валидация адреса доставки
            if not delivery_address or not delivery_address.strip():
                messages.error(request, 'Для доставки необходимо указать адрес')
                return redirect('checkout')
            
            if selected_address_id:
                try:
                    addr = request.user.addresses.get(id=int(selected_address_id))
                    delivery_address = addr.address
                    # Заполняем дополнительные поля из сохраненного адреса
                    if not delivery_entrance:
                        delivery_entrance = addr.entrance or ''
                    if not delivery_floor:
                        delivery_floor = addr.floor or ''
                    if not delivery_apartment:
                        delivery_apartment = addr.apartment or ''
                except Exception:
                    pass
            elif save_address and delivery_address:
                try:
                    from .models import UserAddress
                    UserAddress.objects.create(
                        user=request.user,
                        label='Дом',
                        address=delivery_address,
                        entrance=delivery_entrance,
                        floor=delivery_floor,
                        apartment=delivery_apartment,
                        is_default=True,
                    )
                except Exception:
                    pass
        else:
            # При самовывозе адрес не требуется
            delivery_address = ''

        # Проверяем доступность товаров с учетом партий и правила 70% срока годности
        from django.utils import timezone
        from .models import ProductBatch
        today = timezone.now().date()
        unavailable_products = []
        
        for cart_item in cart_items.select_related('product'):
            product = cart_item.product
            
            # Для товаров с партиями проверяем доступность по партиям
            if product.has_expiry_date:
                # Ищем доступные партии с правилом 70%
                available_batches = ProductBatch.objects.filter(
                    product=product,
                    expiry_date__gte=today,
                    remaining_quantity__gte=cart_item.quantity
                )
                
                # Фильтруем по правилу 70%
                sellable_batches = [b for b in available_batches if b.is_sellable(min_percent=70)]
                
                if not sellable_batches:
                    # Проверяем, есть ли вообще партии
                    all_batches = ProductBatch.objects.filter(product=product)
                    if all_batches.exists():
                        unavailable_products.append(
                            f"{product.name} (нет доступных партий с минимум 70% срока годности, требуется {cart_item.quantity})"
                        )
                    else:
                        # Если партий нет, проверяем старое поле stock_quantity
                        if product.stock_quantity is not None and product.stock_quantity < cart_item.quantity:
                            unavailable_products.append(
                                f"{product.name} (доступно {product.stock_quantity}, требуется {cart_item.quantity})"
                            )
                else:
                    # Проверяем, достаточно ли остатка в доступных партиях
                    total_available = sum(b.remaining_quantity for b in sellable_batches)
                    if total_available < cart_item.quantity:
                        unavailable_products.append(
                            f"{product.name} (доступно {total_available} в пригодных партиях, требуется {cart_item.quantity})"
                        )
            else:
                # Для товаров без срока годности проверяем только stock_quantity
                if product.stock_quantity is not None and product.stock_quantity < cart_item.quantity:
                    unavailable_products.append(
                        f"{product.name} (доступно {product.stock_quantity}, требуется {cart_item.quantity})"
                    )
        
        # Если есть недоступные товары - отменяем заказ
        if unavailable_products:
            messages.error(request, 
                f'Невозможно оформить заказ:\n' + 
                '\n'.join([f"- {p}" for p in unavailable_products])
            )
            return redirect('cart')
        
        # Создаем заказ только после всех проверок
        # Если использован кешбэк, сохраняем исходную сумму в total_amount (до списания кешбэка)
        # для корректного отображения и расчета прогресса лояльности
        from decimal import Decimal
        order_total = final_total
        if use_cashback and cashback_used > 0:
            # Восстанавливаем исходную сумму заказа (до списания кешбэка)
            order_total = float(Decimal(str(final_total)) + Decimal(str(cashback_used)))
        
        order = Order.objects.create(
            user=request.user,
            delivery_type=delivery_type,
            delivery_address=delivery_address,
            total_amount=order_total,
            payment_method=payment_method,
            favorite_discount_amount=favorite_discount_amount,
            promotion_discount=promotion_discount,
            delivery_cost=delivery_cost,
            fulfillment_store=fulfillment_store,
            delivery_slot=selected_slot,
            comment=delivery_comment,
        )
        logger.info("create_order created user=%s order=%s total=%.2f", request.user.id, order.id, final_total)
        
        # Создаем запись о сборке заказа
        from .models import OrderPicking, OrderDelivery
        OrderPicking.objects.create(order=order, status='pending')
        
        # Если заказ с доставкой, создаем запись о доставке
        if delivery_type == 'delivery':
            OrderDelivery.objects.create(order=order, status='pending')

        # Запишем использованную акцию
        if applied_promotion and promotion_discount > 0:
            try:
                UserPromotion.objects.create(
                    user=request.user,
                    promotion=applied_promotion,
                    order=order,
                    discount_amount=promotion_discount,
                )
            except Exception:
                pass
        
        # Создаем позиции заказа
        for cart_item in cart_items.select_related('product'):
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                quantity=cart_item.quantity,
                price_per_unit=cart_item.product.price
            )
            # Списываем остаток со склада
            try:
                product = cart_item.product
                if product.stock_quantity is not None:
                    product.stock_quantity = max(0, int(product.stock_quantity) - int(cart_item.quantity))
                    product.save(update_fields=['stock_quantity'])
            except Exception:
                pass
        
        # Резервируем место в слоте и очищаем корзину
        if selected_slot:
            try:
                selected_slot.reserve(1)
            except Exception:
                pass
        cart_items.delete()
        
        # Списание кешбэка, если использован
        if use_cashback and cashback_used > 0:
            try:
                from .models import CashbackTransaction
                CashbackTransaction.objects.create(
                    user=request.user,
                    order=order,
                    amount=Decimal(str(cashback_used)),
                    transaction_type='spent',
                    description=f'Использование кешбэка для заказа #{order.id}'
                )
                messages.success(request, f'Списано кешбэка: {cashback_used:.2f} ₽')
            except Exception as e:
                logger.exception("cashback_spend_error order=%s err=%s", order.id, e)
        
        # Обновляем статистику лояльности (кешбэк начислится автоматически при статусе 'delivered' через сигнал)
        try:
            loyalty_card = request.user.loyalty_card
            if loyalty_card:
                # Учитываем сумму заказа для прогрессии уровня
                # order.total_amount уже содержит исходную сумму (до списания кешбэка при оплате кешбеком)
                from decimal import Decimal
                original_total = Decimal(str(order.total_amount))
                loyalty_card.total_spent = (loyalty_card.total_spent or 0) + original_total
                # Обновляем уровень в зависимости от суммарных трат
                loyalty_card.update_level()
                loyalty_card.save()
        except Exception as e:
            logger.exception("loyalty_update_error order=%s err=%s", order.id, e)
        
        # Отправляем уведомление о заказе
        try:
            send_order_confirmation(order)
        except Exception as e:
            logger.exception("email_error order=%s err=%s", order.id, e)
        
        messages.success(request, f'Заказ #{order.id} успешно создан!')
        return redirect('home')
    
    return redirect('checkout')

from django.core.paginator import Paginator

def product_list_view(request):
    category_id = request.GET.get('category')
    search_query = request.GET.get('search')
    sort_by = request.GET.get('sort', 'name')
    
    products = Product.objects.filter(is_active=True)
    
    if category_id:
        products = products.filter(category_id=category_id)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query)
        )
    
    # Сортировка
    if sort_by == 'price_asc':
        products = products.order_by('price')
    elif sort_by == 'price_desc':
        products = products.order_by('-price')
    elif sort_by == 'name':
        products = products.order_by('name')
    elif sort_by == 'rating':
        products = products.order_by('-rating')
    elif sort_by == 'newest':
        products = products.order_by('-created_at')
    
    # Пагинация
    paginator = Paginator(products, 12)  # 12 товаров на страницу
    page_number = request.GET.get('page')
    products = paginator.get_page(page_number)
    
    categories = Category.objects.filter(is_active=True)
    selected_category_obj = None
    if category_id:
        try:
            selected_category_obj = categories.get(id=int(category_id))
        except Exception:
            selected_category_obj = None

    # Количество товаров пользователя в корзине (для бейджей в каталоге)
    product_id_to_qty = {}
    try:
        if request.user.is_authenticated:
            from .models import Cart
            product_id_to_qty = {pid: qty for pid, qty in Cart.objects.filter(user=request.user).values_list('product_id', 'quantity')}
    except Exception:
        product_id_to_qty = {}

    context = {
        'products': products,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
        'selected_category_obj': selected_category_obj,
        'search_query': search_query,
        'sort_by': sort_by,
        'product_id_to_qty': product_id_to_qty,
    }
    return render(request, 'paint_shop_project/product_list.html', context)

def product_detail_view(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    context = {
        'product': product,
    }
    return render(request, 'paint_shop_project/product_detail.html', context)

def info_view(request):
    return render(request, 'paint_shop_project/info.html')

@login_required
def add_review(request, product_id):
    """Добавление отзыва о товаре"""
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)

        rating = None
        comment = None

        if request.content_type and 'application/json' in request.content_type:
            try:
                import json
                payload = json.loads(request.body.decode('utf-8'))
                rating = payload.get('rating')
                comment = payload.get('comment')
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'success': False, 'message': 'Некорректный формат данных'})
        else:
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
        
        if not rating or not comment or str(rating).strip() == '' or str(comment).strip() == '':
            return JsonResponse({'success': False, 'message': 'Заполните все поля'})
        
        # Проверяем, не оставлял ли пользователь уже отзыв
        existing_review = Review.objects.filter(user=request.user, product=product).first()
        if existing_review:
            return JsonResponse({'success': False, 'message': 'Вы уже оставляли отзыв об этом товаре'})
        
        # Создаем отзыв
        review = Review.objects.create(
            user=request.user,
            product=product,
            rating=int(rating),
            comment=comment.strip()
        )
        
        # Обновляем рейтинг товара
        update_product_rating(product)
        
        return JsonResponse({'success': True, 'message': 'Отзыв добавлен!'})
    
    return JsonResponse({'success': False, 'message': 'Неверный метод запроса'})

def update_product_rating(product):
    """Обновление рейтинга товара на основе отзывов"""
    reviews = Review.objects.filter(product=product, is_approved=True)
    if reviews.exists():
        avg_rating = reviews.aggregate(models.Avg('rating'))['rating__avg']
        product.rating = round(avg_rating, 2)
        product.save()

@login_required
def get_reviews(request, product_id):
    """Получение отзывов о товаре"""
    product = get_object_or_404(Product, id=product_id)
    reviews = Review.objects.filter(product=product, is_approved=True).order_by('-created_at')
    
    reviews_data = []
    for review in reviews:
        reviews_data.append({
            'id': review.id,
            'user_name': f"{review.user.first_name} {review.user.last_name}".strip() or review.user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%d.%m.%Y'),
        })
    
    return JsonResponse({'reviews': reviews_data})

@login_required
def order_history_view(request):
    """История заказов пользователя"""
    orders_qs = Order.objects.filter(user=request.user).order_by('-order_date')

    # Фильтры
    status = request.GET.get('status')
    delivery_type = request.GET.get('delivery_type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    min_total = request.GET.get('min_total')
    max_total = request.GET.get('max_total')
    search = request.GET.get('q')

    if status:
        orders_qs = orders_qs.filter(status=status)
    if delivery_type:
        orders_qs = orders_qs.filter(delivery_type=delivery_type)
    if date_from:
        try:
            from datetime import datetime
            orders_qs = orders_qs.filter(order_date__date__gte=datetime.fromisoformat(date_from).date())
        except Exception:
            pass
    if date_to:
        try:
            from datetime import datetime
            orders_qs = orders_qs.filter(order_date__date__lte=datetime.fromisoformat(date_to).date())
        except Exception:
            pass
    if min_total:
        try:
            orders_qs = orders_qs.filter(total_amount__gte=float(min_total))
        except Exception:
            pass
    if max_total:
        try:
            orders_qs = orders_qs.filter(total_amount__lte=float(max_total))
        except Exception:
            pass
    if search:
        if search.isdigit():
            orders_qs = orders_qs.filter(id=int(search))

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(orders_qs, 10)
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)

    # Прогресс
    status_progress = {
        'created': 0,
        'confirmed': 25,
        'ready': 50,
        'in_transit': 75,
        'delivered': 100,
        'cancelled': 0,
    }
    for o in orders:
        setattr(o, 'progress', status_progress.get(o.status, 0))
    
    # Статистика по отфильтрованному набору без учета пагинации
    total_orders = orders_qs.count()
    delivered_orders_qs = orders_qs.filter(status='delivered')
    delivered_orders_count = delivered_orders_qs.count()
    delivered_total_spent = delivered_orders_qs.aggregate(total=Sum('total_amount'))['total'] or 0
    average_spent = 0
    if delivered_orders_count:
        average_spent = delivered_total_spent / delivered_orders_count
    
    context = {
        'orders': orders,
        'total_orders': total_orders,
        'total_spent': delivered_total_spent,
        'delivered_orders_count': delivered_orders_count,
        'average_spent': average_spent,
        'selected_status': status,
        'selected_delivery_type': delivery_type,
        'date_from': date_from,
        'date_to': date_to,
        'min_total': min_total,
        'max_total': max_total,
        'search': search,
    }
    return render(request, 'paint_shop_project/order_history.html', context)

@login_required
def order_detail_view(request, order_id):
    """Детальная информация о заказе"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    # Последние 3 статуса для краткого отображения
    recent_statuses = OrderStatusHistory.objects.filter(order=order).order_by('-timestamp')[:3]
    context = {
        'order': order,
        'recent_statuses': recent_statuses,
    }
    return render(request, 'paint_shop_project/order_detail.html', context)

@login_required
def cancel_order(request, order_id):
    """Отмена заказа"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        # Можно отменить только заказы в статусе "Создан" или "Подтверждён"
        if order.status in ['created', 'confirmed']:
            order.status = 'cancelled'
            order.save()
            messages.success(request, 'Заказ успешно отменен!')
        else:
            messages.error(request, 'Нельзя отменить заказ в текущем статусе!')
    
    return redirect('order_history')

@login_required
def process_payment(request, order_id):
    """Обработка платежа"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        logger.info("process_payment user=%s order=%s method=%s", request.user.id, order_id, request.POST.get('payment_method'))
        payment_method = request.POST.get('payment_method')
        
        # Проверяем, что заказ можно оплатить
        if order.status not in ['created', 'confirmed']:
            messages.error(request, 'Этот заказ нельзя оплатить!')
            return redirect('order_detail', order_id=order_id)
        
        # Создаем запись о платеже
        payment = Payment.objects.create(
            order=order,
            amount=order.total_amount,
            payment_method=payment_method,
            status='success'  # В реальном проекте здесь была бы интеграция с платежным шлюзом
        )
        logger.info("process_payment success order=%s payment=%s", order.id, payment.id)
        # Привязываем способ по умолчанию при «сохранить карту»
        try:
            if request.POST.get('save_card') == 'on' and payment_method == 'online':
                # Псевдо-сохранение маски если блок ввода карты заполнялся
                num = (request.POST.get('card_number') or '').replace(' ','').replace('-','')
                last4 = num[-4:] if len(num) >= 4 else ''
                brand = 'Card'
                if num.startswith('4'):
                    brand = 'Visa'
                elif num.startswith(('51','52','53','54','55')):
                    brand = 'MasterCard'
                pm = PaymentMethod.objects.create(
                    user=request.user,
                    brand=brand,
                    last4=last4 or '0000',
                    expiry_month=int((request.POST.get('card_expiry') or '01/99').split('/')[0] or 1),
                    expiry_year=2000 + int((request.POST.get('card_expiry') or '01/99').split('/')[1] or 99),
                    is_default=True,
                )
                PaymentMethod.objects.filter(user=request.user).exclude(id=pm.id).update(is_default=False)
        except Exception:
            pass
        
        # Обновляем статус заказа
        order.status = 'confirmed'
        order.save()
        
        messages.success(request, f'Платеж на сумму {order.total_amount} ₽ успешно обработан!')
        return redirect('order_detail', order_id=order_id)
    
    return redirect('order_detail', order_id=order_id)

def payment_success(request):
    """Страница успешной оплаты"""
    return render(request, 'paint_shop_project/payment_success.html')

def payment_failed(request):
    """Страница неудачной оплаты"""
    return render(request, 'paint_shop_project/payment_failed.html')

@login_required
def loyalty_card_view(request):
    """Страница карты лояльности Жевжик Клуб"""
    try:
        loyalty_card = request.user.loyalty_card
    except LoyaltyCard.DoesNotExist:
        # Создаем карту лояльности для нового пользователя
        import random
        card_number = f"ZHV{random.randint(100000, 999999)}"
        loyalty_card = LoyaltyCard.objects.create(
            user=request.user,
            card_number=card_number
        )
    
    # Получаем последние транзакции
    transactions = loyalty_card.transactions.all()[:10]
    
    context = {
        'loyalty_card': loyalty_card,
        'transactions': transactions,
    }
    return render(request, 'paint_shop_project/loyalty_card.html', context)

@login_required
def loyalty_levels_view(request):
    """Страница уровней лояльности"""
    from django.utils import timezone

    # Составляем уровни из конфигурации, чтобы не дублировать данные
    ordered_levels = sorted(
        LoyaltyCard.LEVEL_CONFIG.items(),
        key=lambda item: item[1]['min_points']
    )
    levels = []
    for idx, (code, config) in enumerate(ordered_levels):
        next_min = ordered_levels[idx + 1][1]['min_points'] if idx < len(ordered_levels) - 1 else None
        levels.append({
            'code': code,
            'name': config['name'],
            'level': code,
            'min_points': config['min_points'],
            'max_points': (next_min - 1) if next_min is not None else None,
            'discount': config['discount_percent'],
            'cashback': config['cashback_percent'],
        })

    # Получаем карту пользователя, если она есть
    loyalty_card = getattr(request.user, 'loyalty_card', None)
    if not loyalty_card:
        # Создаем карту при необходимости
        card_number = f"LC-{timezone.now().strftime('%Y%m%d')}-{request.user.id:04d}"
        loyalty_card = LoyaltyCard.objects.create(
            user=request.user,
            card_number=card_number,
            points=0,
            level='bronze'
        )

    current_settings = loyalty_card.get_level_settings()
    next_level_code, next_level_config = loyalty_card.get_next_level_config()

    context = {
        'levels': levels,
        'loyalty_card': loyalty_card,
        'current_level_name': current_settings['name'],
        'current_discount': current_settings['discount_percent'],
        'current_cashback': current_settings['cashback_percent'],
        'next_level_name': loyalty_card.get_next_level_name(),
        'points_to_next_level': loyalty_card.points_to_next_level(),
        'progress_to_next_level': float(loyalty_card.progress_to_next_level()),
        'next_level_min_points': next_level_config['min_points'] if next_level_config else None,
    }
    return render(request, 'paint_shop_project/loyalty_levels.html', context)

@login_required
def profile_view(request):
    """Личный кабинет пользователя"""
    user = request.user
    
    # Статистика пользователя
    total_orders = Order.objects.filter(user=user).count()
    total_spent = Order.objects.filter(user=user).aggregate(
        total=models.Sum('total_amount')
    )['total'] or 0
    
    # Последние заказы
    recent_orders = Order.objects.filter(user=user).order_by('-order_date')[:5]
    
    # Товары в корзине
    cart_items = Cart.objects.filter(user=user)
    cart_total = sum(item.total_price for item in cart_items)
    
    # Лояльность и кешбэк (бейджи)
    try:
        loyalty_level = user.get_loyalty_level
    except Exception:
        loyalty_level = ""
    try:
        total_cashback_earned = getattr(user, 'total_cashback_earned', 0) or 0
        total_cashback_spent = getattr(user, 'total_cashback_spent', 0) or 0
        cashback_balance = total_cashback_earned - total_cashback_spent
    except Exception:
        cashback_balance = 0
    
    # Популярные категории пользователя
    user_categories = OrderItem.objects.filter(
        order__user=user
    ).values('product__category__name').annotate(
        count=models.Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'user': user,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'recent_orders': recent_orders,
        'cart_items': cart_items,
        'cart_total': cart_total,
        'user_categories': user_categories,
        'loyalty_level': loyalty_level,
        'cashback_balance': cashback_balance,
    }
    return render(request, 'paint_shop_project/profile.html', context)

@login_required
def update_profile(request):
    """Обновление профиля пользователя"""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        user.birth_date = request.POST.get('birth_date') or None
        user.save()
        
        messages.success(request, 'Профиль успешно обновлен!')
        return redirect('profile')
    
    return redirect('profile')

@login_required
def update_primary_address(request):
    """Сохранение основного адреса пользователя из расширенного профиля."""
    if request.method != 'POST':
        return redirect('enhanced_profile')

    address = (request.POST.get('address') or '').strip()
    if not address:
        messages.error(request, 'Укажите адрес доставки.')
        return redirect('enhanced_profile')

    label = (request.POST.get('label') or 'Дом').strip()
    entrance = (request.POST.get('entrance') or '').strip()
    floor = (request.POST.get('floor') or '').strip()
    apartment = (request.POST.get('apartment') or '').strip()
    intercom_code = (request.POST.get('intercom_code') or '').strip()
    comment = (request.POST.get('comment') or '').strip()

    primary = UserAddress.objects.filter(user=request.user, is_default=True).first()
    if not primary:
        primary = UserAddress(user=request.user, is_default=True)

    primary.label = label or primary.label or 'Дом'
    primary.address = address
    primary.entrance = entrance
    primary.floor = floor
    primary.apartment = apartment
    primary.intercom_code = intercom_code
    primary.comment = comment
    primary.is_default = True
    primary.save()

    # Остальные адреса теперь не являются адресом по умолчанию
    UserAddress.objects.filter(user=request.user).exclude(id=primary.id).update(is_default=False)

    # Обновляем краткий адрес в профиле пользователя
    request.user.address = address
    request.user.save(update_fields=['address'])

    messages.success(request, 'Основной адрес обновлён.')
    return redirect('enhanced_profile')

def promotions_view(request):
    """Страница акций и скидок"""
    # Получаем активные акции
    now = timezone.now()
    active_promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=now,
        end_date__gte=now
    ).order_by('-created_at')

    # Метки "Новое" и "Скоро закончится"
    new_ids = set()
    ending_ids = set()
    try:
        for promo in active_promotions:
            try:
                if promo.start_date and (now - promo.start_date).days <= 3:
                    new_ids.add(promo.id)
            except Exception:
                pass
            try:
                if promo.end_date and (promo.end_date - now).days <= 2:
                    ending_ids.add(promo.id)
            except Exception:
                pass
    except Exception:
        pass

    # Товары со скидками
    discounted_products = Product.objects.filter(
        old_price__isnull=False,
        is_active=True
    ).order_by('-created_at')[:12]
    
    context = {
        'promotions': active_promotions,
        'discounted_products': discounted_products,
        'new_ids': new_ids,
        'ending_ids': ending_ids,
    }
    return render(request, 'paint_shop_project/promotions.html', context)

def stores_view(request):
    """Страница магазинов"""
    stores = Store.objects.filter(is_active=True).order_by('name')
    
    context = {
        'stores': stores,
    }
    return render(request, 'paint_shop_project/stores.html', context)

def contacts_view(request):
    """Страница контактов"""
    return render(request, 'paint_shop_project/contacts.html')

def support_view(request):
    """Страница поддержки"""
    return render(request, 'paint_shop_project/support.html')

@login_required
def add_to_favorites(request, product_id):
    """Добавить товар в избранное (принимает GET и POST)."""
    if request.method not in ("GET", "POST"):
        return JsonResponse({"success": False, "message": "Метод не разрешен"}, status=405)
    product = get_object_or_404(Product, id=product_id)
    favorite, created = Favorite.objects.get_or_create(user=request.user, product=product)
    if created:
        return JsonResponse({"success": True, "status": "added", "message": "Товар добавлен в избранное"})
    return JsonResponse({"success": True, "status": "already_exists", "message": "Товар уже в избранном"})

@login_required
def remove_from_favorites(request, product_id):
    """Удалить товар из избранного (принимает GET и POST)."""
    if request.method not in ("GET", "POST"):
        return JsonResponse({"success": False, "message": "Метод не разрешен"}, status=405)
    product = get_object_or_404(Product, id=product_id)
    Favorite.objects.filter(user=request.user, product=product).delete()
    return JsonResponse({"success": True, "status": "removed", "message": "Товар удален из избранного"})

@login_required
def favorites_view(request):
    """Страница избранных товаров"""
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    
    product_id_to_qty = {}
    try:
        product_id_to_qty = {pid: qty for pid, qty in Cart.objects.filter(user=request.user).values_list('product_id', 'quantity')}
    except Exception:
        product_id_to_qty = {}
    
    context = {
        'favorites': favorites,
        'product_id_to_qty': product_id_to_qty,
    }
    return render(request, 'paint_shop_project/favorites.html', context)

@login_required
def add_to_view_history(request, product_id):
    """Добавить товар в историю просмотров"""
    product = get_object_or_404(Product, id=product_id)
    ViewHistory.objects.create(user=request.user, product=product)
    return JsonResponse({'status': 'added'})

@login_required
def view_history_view(request):
    """Страница истории просмотров"""
    view_history = ViewHistory.objects.filter(user=request.user).select_related('product')[:20]
    
    context = {
        'view_history': view_history,
    }
    return render(request, 'paint_shop_project/view_history.html', context)

@login_required
def search_history_view(request):
    """Страница истории поиска"""
    search_history = SearchHistory.objects.filter(user=request.user)[:20]
    
    context = {
        'search_history': search_history,
    }
    return render(request, 'paint_shop_project/search_history.html', context)

def validate_promo_code(request):
    """Проверка промокода"""
    code = request.GET.get('code', '')
    if not code:
        return JsonResponse({'valid': False, 'message': 'Введите промокод'})
    
    try:
        promo_code = PromoCode.objects.get(code=code)
        if promo_code.is_valid():
            return JsonResponse({
                'valid': True, 
                'message': f'Промокод "{promo_code.description}" применен!',
                'discount_type': promo_code.discount_type,
                'discount_value': float(promo_code.discount_value),
                'min_order_amount': float(promo_code.min_order_amount)
            })
        else:
            return JsonResponse({'valid': False, 'message': 'Промокод недействителен'})
    except PromoCode.DoesNotExist:
        return JsonResponse({'valid': False, 'message': 'Промокод не найден'})

@login_required
def notifications_view(request):
    """Страница уведомлений"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'paint_shop_project/notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'read'})

@login_required
def mark_all_notifications_read(request):
    """Отметить все уведомления как прочитанные"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'all_read'})

@login_required
def analytics_view(request):
    """Страница аналитики (только для администраторов)"""
    if not request.user.is_staff:
        return redirect('home')
    
    # Общая статистика
    total_users = User.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_revenue = Order.objects.aggregate(total=models.Sum('total_amount'))['total'] or 0
    
    # Статистика за последние 30 дней
    from datetime import datetime, timedelta
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    recent_orders = Order.objects.filter(order_date__gte=thirty_days_ago)
    recent_revenue = recent_orders.aggregate(total=models.Sum('total_amount'))['total'] or 0
    recent_users = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    
    # Популярные товары
    popular_products = Product.objects.annotate(
        order_count=models.Count('orderitem__order')
    ).order_by('-order_count')[:10]
    
    # Популярные категории
    popular_categories = Category.objects.annotate(
        product_count=models.Count('product'),
        order_count=models.Count('product__orderitem__order')
    ).order_by('-order_count')[:10]
    
    # Статистика по статусам заказов
    order_statuses = Order.objects.values('status').annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    # Активность пользователей
    active_users = User.objects.filter(
        last_login__gte=thirty_days_ago
    ).count()
    
    context = {
        'total_users': total_users,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'recent_revenue': recent_revenue,
        'recent_users': recent_users,
        'popular_products': popular_products,
        'popular_categories': popular_categories,
        'order_statuses': order_statuses,
        'active_users': active_users,
    }
    return render(request, 'paint_shop_project/analytics.html', context)

# API Endpoints
def api_products(request):
    """API: Список товаров"""
    products = Product.objects.filter(is_active=True).select_related('category', 'manufacturer')
    
    # Фильтрация по категории
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Поиск
    search = request.GET.get('search')
    if search:
        products = products.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Пагинация
    from django.core.paginator import Paginator
    page = request.GET.get('page', 1)
    paginator = Paginator(products, 20)
    products_page = paginator.get_page(page)
    
    data = {
        'products': [
            {
                'id': product.id,
                'name': product.name,
                'price': float(product.price),
                'old_price': float(product.old_price) if product.old_price else None,
                'image': product.image.url if product.image else None,
                'category': product.category.name,
                'manufacturer': product.manufacturer.name if product.manufacturer else None,
                'rating': float(product.rating),
                'in_stock': product.is_in_stock,
            }
            for product in products_page
        ],
        'total_pages': paginator.num_pages,
        'current_page': products_page.number,
        'has_next': products_page.has_next(),
        'has_previous': products_page.has_previous(),
    }
    
    return JsonResponse(data)

def api_root(request):
    """API Root: публичная документация и ссылки на эндпоинты"""
    base = request.build_absolute_uri('/')[:-1]
    endpoints = [
        {
            'name': 'Список товаров',
            'path': '/api/products/',
            'method': 'GET',
            'url': f"{base}/api/products/",
            'desc': 'Фильтры: ?category=<id>, ?search=<text>'
        },
        {
            'name': 'Список категорий',
            'path': '/api/categories/',
            'method': 'GET',
            'url': f"{base}/api/categories/",
            'desc': ''
        },
        {
            'name': 'Товар по id',
            'path': '/api/product/<id>/',
            'method': 'GET',
            'url': f"{base}/api/product/1/",
            'desc': 'Замените 1 на реальный id'
        },
        {
            'name': 'Заказы пользователя',
            'path': '/api/user/orders/',
            'method': 'GET',
            'url': f"{base}/api/user/orders/",
            'desc': 'Требуется авторизация'
        },
        {
            'name': 'Избранное пользователя',
            'path': '/api/user/favorites/',
            'method': 'GET',
            'url': f"{base}/api/user/favorites/",
            'desc': 'Требуется авторизация'
        },
        {
            'name': 'Трекинг заказа',
            'path': '/api/order/<id>/tracking/',
            'method': 'GET',
            'url': f"{base}/api/order/1/tracking/",
            'desc': 'Требуется авторизация и владение заказом'
        },
        {
            'name': 'Swagger UI',
            'path': '/api/docs/',
            'method': 'GET',
            'url': f"{base}/api/docs/",
            'desc': 'Интерактивная документация'
        },
    ]
    return render(request, 'paint_shop_project/api_index.html', { 'endpoints': endpoints })

from django.http import HttpResponseForbidden
from django.urls import reverse

def api_docs_view(request):
    """Swagger UI с загрузкой схемы /api/schema.json (доступ только администраторам)"""
    if not request.user.is_authenticated or not request.user.is_staff:
        login_url = reverse('login')
        return redirect(f"{login_url}?next={request.path}")
    return render(request, 'paint_shop_project/api_docs.html')

def api_schema(request):
    """Минимальная OpenAPI-схема для Swagger UI (доступ только администраторам)"""
    if not request.user.is_authenticated or not request.user.is_staff:
        login_url = reverse('login')
        return redirect(f"{login_url}?next={request.path}")
    base = request.build_absolute_uri('/')[:-1]
    schema = {
        'openapi': '3.0.0',
        'info': {
            'title': 'Жевжик API',
            'version': '1.0.0',
            'description': 'Публичное API магазина продуктов Жевжик',
        },
        'components': {
            'schemas': {
                'Product': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 7},
                        'name': {'type': 'string', 'example': 'Томаты Медовые черри красные круглые'},
                        'price': {'type': 'number', 'format': 'float', 'example': 149.9},
                        'old_price': {'type': ['number','null'], 'format': 'float', 'example': 195.9},
                        'image': {'type': ['string','null'], 'example': '/media/products/tomato.jpg'},
                        'category': {'type': 'string', 'example': 'Овощи и фрукты'},
                        'manufacturer': {'type': ['string','null'], 'example': 'Свежие овощи'},
                        'rating': {'type': 'number', 'format': 'float', 'example': 4.89},
                        'in_stock': {'type': 'boolean', 'example': True},
                    }
                },
                'Category': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 3},
                        'name': {'type': 'string', 'example': 'Овощи и фрукты'},
                        'description': {'type': 'string', 'example': 'Свежие овощи и фрукты'},
                        'product_count': {'type': 'integer', 'example': 124},
                    }
                },
                'OrderItem': {
                    'type': 'object',
                    'properties': {
                        'product_name': {'type': 'string', 'example': 'Хурма'},
                        'quantity': {'type': 'integer', 'example': 2},
                        'price': {'type': 'number', 'format': 'float', 'example': 299.9},
                        'total': {'type': 'number', 'format': 'float', 'example': 599.8},
                    }
                },
                'Order': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer', 'example': 15},
                        'status': {'type': 'string', 'example': 'В пути'},
                        'status_code': {'type': 'string', 'example': 'in_transit'},
                        'total_amount': {'type': 'number', 'format': 'float', 'example': 1599.9},
                        'order_date': {'type': 'string', 'format': 'date-time', 'example': '2025-10-25T14:35:12'},
                        'delivery_type': {'type': 'string', 'example': 'Доставка'},
                        'payment_method': {'type': 'string', 'example': 'Картой'},
                        'items': {'type': 'array', 'items': {'$ref': '#/components/schemas/OrderItem'}},
                    }
                },
                'OrderStatusHistory': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string', 'example': 'in_transit'},
                        'status_code': {'type': 'string', 'example': 'in_transit'},
                        'timestamp': {'type': 'string', 'format': 'date-time', 'example': '2025-10-25T15:10:00'},
                        'comment': {'type': ['string','null'], 'example': 'Передан курьеру'},
                        'courier_name': {'type': ['string','null'], 'example': 'Иван Курьеров'},
                        'courier_phone': {'type': ['string','null'], 'example': '+7 900 000-00-00'},
                    }
                },
                'OrderTracking': {
                    'type': 'object',
                    'properties': {
                        'order': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 15},
                                'status': {'type': 'string', 'example': 'В пути'},
                                'status_code': {'type': 'string', 'example': 'in_transit'},
                                'progress': {'type': 'integer', 'example': 75},
                                'tracking_number': {'type': ['string','null'], 'example': 'TRK123456'},
                                'delivery_type': {'type': 'string', 'example': 'delivery'},
                                'delivery_address': {'type': 'string', 'example': 'Москва, ул. Примерная, 1'},
                                'courier_name': {'type': ['string','null'], 'example': 'Иван Курьеров'},
                                'courier_phone': {'type': ['string','null'], 'example': '+7 900 000-00-00'},
                                'estimated_delivery_time': {'type': ['string','null'], 'format': 'date-time', 'example': '2025-10-25T18:00:00'},
                                'actual_delivery_time': {'type': ['string','null'], 'format': 'date-time', 'example': None},
                                'total_amount': {'type': 'number', 'format': 'float', 'example': 1599.9},
                            }
                        },
                        'history': {'type': 'array', 'items': {'$ref': '#/components/schemas/OrderStatusHistory'}},
                    }
                }
            }
        },
        'paths': {
            '/api/products/': {
                'get': {
                    'summary': 'Список товаров',
                    'parameters': [
                        {'name': 'category', 'in': 'query', 'schema': {'type': 'integer'}, 'example': 1, 'description': 'ID категории'},
                        {'name': 'search', 'in': 'query', 'schema': {'type': 'string'}, 'example': 'молоко', 'description': 'Поиск по названию/описанию'},
                        {'name': 'page', 'in': 'query', 'schema': {'type': 'integer', 'default': 1}},
                    ],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'examples': {
                                        'default': {
                                            'value': {
                                                'products': [{'$ref': '#/components/schemas/Product'}],
                                                'total_pages': 1,
                                                'current_page': 1,
                                                'has_next': False,
                                                'has_previous': False
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '/api/categories/': {
                'get': {
                    'summary': 'Список категорий',
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'examples': {
                                        'default': {
                                            'value': {
                                                'categories': [{'$ref': '#/components/schemas/Category'}]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            '/api/product/{id}/': {
                'get': {
                    'summary': 'Товар по id',
                    'parameters': [
                        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                    ],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/Product'}
                                }
                            }
                        },
                        '404': {'description': 'Не найден'}
                    }
                }
            },
            '/api/user/orders/': {
                'get': {
                    'summary': 'Заказы пользователя (auth)',
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'examples': {
                                        'default': {
                                            'value': {
                                                'orders': [{'$ref': '#/components/schemas/Order'}]
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        '403': {'description': 'Требуется авторизация'}
                    }
                }
            },
            '/api/user/favorites/': {
                'get': {
                    'summary': 'Избранное пользователя (auth)',
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {'application/json': {'description': 'Список избранных товаров'}}
                        },
                        '403': {'description': 'Требуется авторизация'}
                    }
                }
            },
            '/api/order/{id}/tracking/': {
                'get': {
                    'summary': 'Трекинг заказа (auth, владелец)',
                    'parameters': [
                        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
                    ],
                    'responses': {
                        '200': {
                            'description': 'OK',
                            'content': {
                                'application/json': {
                                    'schema': {'$ref': '#/components/schemas/OrderTracking'}
                                }
                            }
                        },
                        '403': {'description': 'Требуется авторизация'},
                        '404': {'description': 'Не найден'}
                    }
                }
            },
        },
        'servers': [{ 'url': base }],
    }
    return JsonResponse(schema)

@login_required
def api_order_tracking(request, order_id):
    """API: Отслеживание заказа с историей статусов"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    status_history_qs = OrderStatusHistory.objects.filter(order=order).order_by('-timestamp')
    status_progress = {
        'created': 0,
        'confirmed': 25,
        'ready': 50,
        'in_transit': 75,
        'delivered': 100,
        'cancelled': 0
    }
    progress = status_progress.get(order.status, 0)
    data = {
        'order': {
            'id': order.id,
            'status': order.get_status_display() if hasattr(order, 'get_status_display') else order.status,
            'status_code': order.status,
            'progress': progress,
            'tracking_number': order.tracking_number,
            'delivery_type': order.delivery_type,
            'delivery_address': order.delivery_address,
            'courier_name': order.courier_name,
            'courier_phone': order.courier_phone,
            'estimated_delivery_time': order.estimated_delivery_time.isoformat() if order.estimated_delivery_time else None,
            'actual_delivery_time': order.actual_delivery_time.isoformat() if order.actual_delivery_time else None,
            'total_amount': float(order.total_amount),
        },
        'history': [
            {
                'status': h.get_status_display() if hasattr(h, 'get_status_display') else h.status,
                'status_code': h.status,
                'timestamp': h.timestamp.isoformat(),
                'comment': h.comment,
                'courier_name': h.courier_name,
                'courier_phone': h.courier_phone,
            }
            for h in status_history_qs
        ]
    }
    return JsonResponse(data)

def api_categories(request):
    """API: Список категорий"""
    categories = Category.objects.filter(is_active=True)
    
    data = {
        'categories': [
            {
                'id': category.id,
                'name': category.name,
                'description': category.description,
                'product_count': category.product_set.filter(is_active=True).count(),
            }
            for category in categories
        ]
    }
    
    return JsonResponse(data)

def api_product_detail(request, product_id):
    """API: Детали товара"""
    try:
        product = Product.objects.get(id=product_id, is_active=True)
        
        data = {
            'id': product.id,
            'name': product.name,
            'description': product.description,
            'price': float(product.price),
            'old_price': float(product.old_price) if product.old_price else None,
            'image': product.image.url if product.image else None,
            'category': {
                'id': product.category.id,
                'name': product.category.name,
            },
            'manufacturer': {
                'id': product.manufacturer.id,
                'name': product.manufacturer.name,
            } if product.manufacturer else None,
            'rating': float(product.rating),
            'stock_quantity': product.stock_quantity,
            'unit': product.unit,
            'weight': product.weight,
            'in_stock': product.is_in_stock,
            'reviews': [
                {
                    'id': review.id,
                    'user': review.user.username,
                    'rating': review.rating,
                    'comment': review.comment,
                    'created_at': review.created_at.isoformat(),
                }
                for review in product.reviews.filter(is_approved=True)
            ]
        }
        
        return JsonResponse(data)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Товар не найден'}, status=404)

@login_required
def api_user_orders(request):
    """API: Заказы пользователя"""
    orders = Order.objects.filter(user=request.user).order_by('-order_date')
    
    data = {
        'orders': [
            {
                'id': order.id,
                'status': order.get_status_display(),
                'status_code': order.status,
                'total_amount': float(order.total_amount),
                'order_date': order.order_date.isoformat(),
                'delivery_type': order.get_delivery_type_display(),
                'payment_method': order.get_payment_method_display(),
                'items': [
                    {
                        'product_name': item.product.name,
                        'quantity': item.quantity,
                        'price': float(item.price_per_unit),
                        'total': float(item.total_price),
                    }
                    for item in order.items.all()
                ]
            }
            for order in orders
        ]
    }
    
    return JsonResponse(data)

@login_required
def api_user_favorites(request):
    """API: Избранные товары пользователя"""
    favorites = Favorite.objects.filter(user=request.user).select_related('product')
    
    data = {
        'favorites': [
            {
                'id': favorite.product.id,
                'name': favorite.product.name,
                'price': float(favorite.product.price),
                'image': favorite.product.image.url if favorite.product.image else None,
                'added_at': favorite.created_at.isoformat(),
            }
            for favorite in favorites
        ]
    }
    
    return JsonResponse(data)

# Новые функции для расширенного функционала покупателя

@login_required
def rate_employee(request, order_id):
    """Оценка сотрудника после заказа"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, user=request.user)
        
        employee_name = request.POST.get('employee_name')
        rating = int(request.POST.get('rating'))
        comment = request.POST.get('comment', '')
        
        # Проверяем, не оценивал ли уже пользователь этого сотрудника для этого заказа
        existing_rating = EmployeeRating.objects.filter(
            user=request.user,
            order=order,
            employee_name=employee_name
        ).exists()
        
        if existing_rating:
            messages.error(request, 'Вы уже оценили этого сотрудника для данного заказа.')
        else:
            EmployeeRating.objects.create(
                user=request.user,
                order=order,
                employee_name=employee_name,
                rating=rating,
                comment=comment
            )
            messages.success(request, 'Спасибо за оценку!')
        
        return redirect('order_detail', order_id=order_id)
    
    return redirect('order_history')

@login_required
def favorite_categories_view(request):
    """Управление любимыми категориями"""
    user = request.user
    
    if request.method == 'POST':
        category_id = request.POST.get('category_id')
        action = request.POST.get('action')
        
        if action == 'add':
            category = get_object_or_404(Category, id=category_id)
            favorite_category, created = FavoriteCategory.objects.get_or_create(
                user=user,
                category=category,
                defaults={'cashback_multiplier': 2.0}
            )
            if created:
                messages.success(request, f'Категория "{category.name}" добавлена в любимые!')
            else:
                messages.info(request, f'Категория "{category.name}" уже в любимых.')
        
        elif action == 'remove':
            FavoriteCategory.objects.filter(user=user, category_id=category_id).delete()
            messages.success(request, 'Категория удалена из любимых.')
        
        return redirect('favorite_categories')
    
    # Получаем все категории и отмечаем любимые
    all_categories = Category.objects.all()
    favorite_categories = FavoriteCategory.objects.filter(user=user).select_related('category')
    favorite_category_ids = set(fc.category.id for fc in favorite_categories)
    
    context = {
        'all_categories': all_categories,
        'favorite_categories': favorite_categories,
        'favorite_category_ids': favorite_category_ids,
    }
    return render(request, 'paint_shop_project/favorite_categories.html', context)

@login_required
def cashback_history_view(request):
    """История кешбэка пользователя"""
    user = request.user
    
    # Фильтры
    tx_type = request.GET.get('type')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    min_amount = request.GET.get('min_amount')
    max_amount = request.GET.get('max_amount')

    transactions_qs = CashbackTransaction.objects.filter(user=user).order_by('-created_at')
    if tx_type in ['earned', 'spent', 'expired']:
        transactions_qs = transactions_qs.filter(transaction_type=tx_type)
    if date_from:
        try:
            from datetime import datetime
            transactions_qs = transactions_qs.filter(created_at__date__gte=datetime.fromisoformat(date_from).date())
        except Exception:
            pass
    if date_to:
        try:
            from datetime import datetime
            transactions_qs = transactions_qs.filter(created_at__date__lte=datetime.fromisoformat(date_to).date())
        except Exception:
            pass
    if min_amount:
        try:
            transactions_qs = transactions_qs.filter(amount__gte=float(min_amount))
        except Exception:
            pass
    if max_amount:
        try:
            transactions_qs = transactions_qs.filter(amount__lte=float(max_amount))
        except Exception:
            pass

    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(transactions_qs, 10)
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)
    
    # Статистика
    total_earned = CashbackTransaction.objects.filter(
        user=user, 
        transaction_type='earned'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    total_spent = CashbackTransaction.objects.filter(
        user=user, 
        transaction_type='spent'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    current_balance = total_earned - total_spent
    
    context = {
        'transactions': transactions,
        'total_earned': total_earned,
        'total_spent': total_spent,
        'current_balance': current_balance,
        'tx_type': tx_type,
        'date_from': date_from,
        'date_to': date_to,
        'min_amount': min_amount,
        'max_amount': max_amount,
    }
    return render(request, 'paint_shop_project/cashback_history.html', context)

@login_required
def cashback_history_export_csv(request):
    """Экспорт истории кешбэка в CSV"""
    import csv
    from django.http import HttpResponse

    user = request.user
    transactions = CashbackTransaction.objects.filter(user=user).order_by('-created_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="cashback_history.csv"'

    writer = csv.writer(response)
    writer.writerow(['Дата', 'Тип операции', 'Описание', 'Сумма (₽)'])
    for t in transactions:
        writer.writerow([
            t.created_at.strftime('%d.%m.%Y %H:%M'),
            dict(t._meta.get_field('transaction_type').choices).get(t.transaction_type, t.transaction_type),
            t.description,
            f"{float(t.amount):.2f}",
        ])

    return response

@login_required
def support_tickets_view(request):
    """Тикеты поддержки пользователя"""
    user = request.user
    
    if request.method == 'POST':
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        category = request.POST.get('category')
        order_id = request.POST.get('order_id')
        
        ticket = SupportTicket.objects.create(
            user=user,
            subject=subject,
            message=message,
            category=category,
            order_id=order_id if order_id else None
        )
        
        messages.success(request, 'Ваш запрос отправлен в службу поддержки.')
        return redirect('support_ticket_detail', ticket_id=ticket.id)
    
    # Получаем тикеты пользователя
    tickets = SupportTicket.objects.filter(user=user).order_by('-created_at')
    
    context = {
        'tickets': tickets,
    }
    return render(request, 'paint_shop_project/support_tickets.html', context)

@login_required
def support_ticket_detail_view(request, ticket_id):
    """Детали тикета поддержки"""
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    
    if request.method == 'POST':
        message = request.POST.get('message')
        if message:
            SupportResponse.objects.create(
                ticket=ticket,
                user=request.user,
                message=message,
                is_staff_response=False
            )
            messages.success(request, 'Ваш ответ добавлен.')
            return redirect('support_ticket_detail', ticket_id=ticket.id)
    
    # Получаем все ответы на тикет
    responses = SupportResponse.objects.filter(ticket=ticket).order_by('created_at')
    
    context = {
        'ticket': ticket,
        'responses': responses,
    }
    return render(request, 'paint_shop_project/support_ticket_detail.html', context)

@login_required
def special_sections_view(request):
    """Специальные разделы (аналог Пушистого клуба)"""
    user = request.user
    
    if request.method == 'POST':
        section_id = request.POST.get('section_id')
        action = request.POST.get('action')
        
        if action == 'join':
            section = get_object_or_404(SpecialSection, id=section_id, is_active=True)
            user_section, created = UserSpecialSection.objects.get_or_create(
                user=user,
                section=section
            )
            if created:
                messages.success(request, f'Вы присоединились к разделу "{section.name}"!')
            else:
                messages.info(request, f'Вы уже участвуете в разделе "{section.name}".')
        
        elif action == 'leave':
            UserSpecialSection.objects.filter(user=user, section_id=section_id).delete()
            messages.success(request, 'Вы покинули раздел.')
        
        return redirect('special_sections')
    
    # Получаем все активные разделы
    all_sections = SpecialSection.objects.filter(is_active=True)
    user_sections = UserSpecialSection.objects.filter(user=user).select_related('section')
    user_section_ids = set(us.section.id for us in user_sections)
    
    context = {
        'all_sections': all_sections,
        'user_sections': user_sections,
        'user_section_ids': user_section_ids,
    }
    return render(request, 'paint_shop_project/special_sections.html', context)

@login_required
def enhanced_profile_view(request):
    """Расширенный профиль пользователя с функциями как в Пятёрочке"""
    user = request.user
    
    # Статистика пользователя
    total_orders = Order.objects.filter(user=user).count()
    total_spent = Order.objects.filter(user=user).aggregate(
        total=models.Sum('total_amount')
    )['total'] or 0
    
    # Кешбэк статистика
    total_cashback_earned = user.total_cashback_earned
    total_cashback_spent = user.total_cashback_spent
    current_cashback = total_cashback_earned - total_cashback_spent
    
    # Любимые категории
    favorite_categories = FavoriteCategory.objects.filter(user=user).select_related('category')
    
    # Специальные разделы
    user_sections = UserSpecialSection.objects.filter(user=user).select_related('section')
    
    # Последние заказы
    recent_orders = Order.objects.filter(user=user).order_by('-order_date')[:5]
    
    # Товары в корзине
    cart_items = Cart.objects.filter(user=user)
    cart_total = sum(item.total_price for item in cart_items)
    
    # Популярные категории пользователя
    user_categories = OrderItem.objects.filter(
        order__user=user
    ).values('product__category__name').annotate(
        count=models.Count('id')
    ).order_by('-count')[:5]
    
    # Избранные товары
    favorite_count = Favorite.objects.filter(user=user).count()
    
    try:
        loyalty_card = user.loyalty_card
    except LoyaltyCard.DoesNotExist:
        card_number = f"ZHV{random.randint(100000, 999999)}"
        loyalty_card = LoyaltyCard.objects.create(user=user, card_number=card_number)
    
    loyalty_progress = loyalty_card.progress_to_next_level()
    next_level_name = loyalty_card.get_next_level_name()
    points_to_next_level = loyalty_card.points_to_next_level()
    
    primary_address = user.addresses.filter(is_default=True).first()
    
    # История платежей
    from .models import Payment
    recent_payments = Payment.objects.filter(order__user=user).select_related('order').order_by('-payment_date')[:10]
    
    # Статистика платежей
    total_payments = Payment.objects.filter(order__user=user, status='success').count()
    total_paid = Payment.objects.filter(order__user=user, status='success').aggregate(
        total=models.Sum('amount')
    )['total'] or 0
    
    context = {
        'user': user,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'total_cashback_earned': total_cashback_earned,
        'total_cashback_spent': total_cashback_spent,
        'cashback_balance': current_cashback,
        'favorite_count': favorite_count,
        'user_categories': user_categories,
        'recent_orders': recent_orders,
        'loyalty_card': loyalty_card,
        'loyalty_progress_percent': float(loyalty_progress),
        'next_level_name': next_level_name,
        'points_to_next_level': points_to_next_level,
        'primary_address': primary_address,
        'recent_payments': recent_payments,
        'total_payments': total_payments,
        'total_paid': total_paid,
    }
    return render(request, 'paint_shop_project/enhanced_profile.html', context)

def apply_promotion_view(request, promotion_id):
    """Применить акцию к заказу"""
    if request.method == 'POST':
        try:
            promotion = Promotion.objects.get(id=promotion_id)
            cart_items = Cart.objects.filter(user=request.user)
            total = sum(item.total_price for item in cart_items)
            
            # Проверяем валидность акции
            if not promotion.is_valid():
                return JsonResponse({
                    'success': False,
                    'message': 'Акция недействительна или истек срок её действия'
                })
            
            # Проверяем минимальную сумму заказа
            if total < float(promotion.min_order_amount):
                return JsonResponse({
                    'success': False,
                    'message': f'Заказ не соответствует требованиям акции. Минимальная сумма заказа: {promotion.min_order_amount} ₽, текущая сумма: {total:.2f} ₽'
                })
            
            discount_amount = promotion.calculate_discount(total)
            return JsonResponse({
                'success': True,
                'discount_amount': float(discount_amount),
                'message': f'Акция "{promotion.name}" применена! Скидка: {discount_amount:.2f} ₽'
            })
        except Promotion.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Акция не найдена'
            })
        except Exception as e:
            logger.exception("apply_promotion_error promotion_id=%s err=%s", promotion_id, e)
            return JsonResponse({
                'success': False,
                'message': 'Ошибка при применении акции'
            })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

def error_log_view(request):
    """Страница просмотра ошибок системы"""
    if not request.user.is_staff:
        return redirect('home')
    
    errors = ErrorLog.objects.all().order_by('-created_at')
    
    # Фильтрация
    error_type = request.GET.get('type')
    is_resolved = request.GET.get('resolved')
    
    if error_type:
        errors = errors.filter(error_type=error_type)
    
    if is_resolved is not None:
        errors = errors.filter(is_resolved=is_resolved == 'true')
    
    # Пагинация
    from django.core.paginator import Paginator
    paginator = Paginator(errors, 20)
    page_number = request.GET.get('page')
    errors = paginator.get_page(page_number)
    
    context = {
        'errors': errors,
        'error_types': ErrorLog.ERROR_TYPES,
        'selected_type': error_type,
        'selected_resolved': is_resolved,
    }
    return render(request, 'paint_shop_project/error_log.html', context)

def log_error_view(request):
    """API для логирования ошибок с клиента"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            
            error_log = ErrorLog.objects.create(
                error_type=data.get('type', 'javascript'),
                message=data.get('message', ''),
                stack_trace=data.get('stackTrace', ''),
                user=request.user if request.user.is_authenticated else None,
                url=data.get('url', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=get_client_ip(request)
            )
            
            return JsonResponse({'success': True, 'id': error_log.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'})

def get_client_ip(request):
    """Получение IP адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def _create_order_after_payment(request, payment_id, transaction_id, amount, card_number=None, card_expiry=None, card_holder=None, payment_method_override=None):
    """Создает заказ после успешной онлайн-оплаты (внутренняя функция, вызывается из yoomoney_payment_view)"""
    if not request.user.is_authenticated:
        return None
    from decimal import Decimal
    from django.utils import timezone
    from .models import (
        Cart, Order, OrderItem, ProductBatch, OrderPicking, OrderDelivery, 
        UserAddress, UserPromotion, CashbackTransaction, Payment, PaymentMethod,
        Store, Promotion, PromoCode
    )
    
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items.exists():
        return None
    
    subtotal = sum(item.total_price for item in cart_items)
    delivery_type = request.POST.get('delivery_type', 'pickup')
    payment_method = payment_method_override or request.POST.get('payment_method', 'online')
    saved_payment_id = None
    
    # Обработка сохранённой карты
    if payment_method.startswith('saved:'):
        try:
            saved_payment_id = int(payment_method.split(':',1)[1])
            saved_pm = PaymentMethod.objects.get(id=saved_payment_id, user=request.user)
            # Используем данные сохранённой карты
            card_number = f"****{saved_pm.last4}"
            card_expiry = f"{saved_pm.expiry_month:02d}/{saved_pm.expiry_year % 100:02d}"
            payment_method = 'online'
        except PaymentMethod.DoesNotExist:
            return None
    
    delivery_address = request.POST.get('delivery_address', '')
    delivery_entrance = request.POST.get('delivery_entrance', '')
    delivery_apartment = request.POST.get('delivery_apartment', '')
    delivery_floor = request.POST.get('delivery_floor', '')
    delivery_comment = request.POST.get('comment', '')
    selected_address_id = request.POST.get('address_id')
    save_address = request.POST.get('save_address') == 'on'
    fulfillment_store_id = request.POST.get('fulfillment_store_id')
    delivery_slot_id = request.POST.get('delivery_slot_id')
    
    FREE_DELIVERY_THRESHOLD = 5000
    
    # Скидка по любимым категориям
    favorite_discount_amount = 0.0
    try:
        for item in cart_items:
            discount_percent = 0
            if hasattr(request.user, 'get_favorite_categories_discount'):
                discount_percent = request.user.get_favorite_categories_discount(item.product.category)
            if discount_percent and discount_percent > 0:
                favorite_discount_amount += float(item.total_price) * float(discount_percent) / 100.0
    except Exception:
        favorite_discount_amount = 0.0
    favorite_discount_amount = round(favorite_discount_amount, 2)
    
    # Промокод/акции (та же логика что в create_order)
    active_promotions = Promotion.objects.filter(is_active=True, start_date__lte=timezone.now(), end_date__gte=timezone.now())
    promotion_discount = 0.0
    applied_promotion = None
    applied_promo_code = None
    base_for_promo = max(float(subtotal) - favorite_discount_amount - favorite_products_discount, 0.0)
    promo_code_value = request.POST.get('promo_code') or None
    
    if promo_code_value:
        try:
            promo_code_obj = PromoCode.objects.get(code=promo_code_value)
            if promo_code_obj.is_valid() and base_for_promo >= float(promo_code_obj.min_order_amount):
                if promo_code_obj.discount_type == 'percent':
                    promotion_discount = float(base_for_promo) * float(promo_code_obj.discount_value) / 100.0
                else:
                    promotion_discount = min(float(promo_code_obj.discount_value), float(base_for_promo))
                applied_promo_code = promo_code_obj
                try:
                    promo_code_obj.used_count = (promo_code_obj.used_count or 0) + 1
                    promo_code_obj.save(update_fields=['used_count'])
                except Exception:
                    pass
        except PromoCode.DoesNotExist:
            pass
    
    for promo in active_promotions:
        try:
            disc = float(promo.calculate_discount(base_for_promo))
            if disc > promotion_discount and not applied_promo_code:
                promotion_discount = disc
                applied_promotion = promo
        except Exception:
            pass
    
    total_without_delivery = max(base_for_promo - promotion_discount, 0.0)
    
    # Расчет стоимости доставки
    if delivery_type == 'delivery':
        if total_without_delivery >= FREE_DELIVERY_THRESHOLD:
            delivery_cost = 0
        else:
            delivery_cost = 200
    else:
        delivery_cost = 0
    
    final_total = total_without_delivery + float(delivery_cost)
    
    # Определяем магазин и слот
    fulfillment_store = None
    selected_slot = None
    if fulfillment_store_id:
        try:
            fulfillment_store = Store.objects.get(id=int(fulfillment_store_id))
        except Exception:
            pass
    if delivery_type == 'delivery' and delivery_slot_id:
        from .models import DeliverySlot
        try:
            selected_slot = DeliverySlot.objects.select_for_update().get(id=int(delivery_slot_id))
            if not selected_slot.available:
                return None
        except DeliverySlot.DoesNotExist:
            return None
    
    # Адрес доставки
    if delivery_type == 'delivery':
        if not delivery_address or not delivery_address.strip():
            return None
        
        if selected_address_id:
            try:
                addr = request.user.addresses.get(id=int(selected_address_id))
                delivery_address = addr.address
                if not delivery_entrance:
                    delivery_entrance = addr.entrance or ''
                if not delivery_floor:
                    delivery_floor = addr.floor or ''
                if not delivery_apartment:
                    delivery_apartment = addr.apartment or ''
            except Exception:
                pass
        elif save_address and delivery_address:
            try:
                UserAddress.objects.create(
                    user=request.user,
                    label='Дом',
                    address=delivery_address,
                    entrance=delivery_entrance,
                    floor=delivery_floor,
                    apartment=delivery_apartment,
                    is_default=True,
                )
            except Exception:
                pass
    else:
        delivery_address = ''
    
    # Проверка доступности товаров (упрощённая версия)
    today = timezone.now().date()
    unavailable_products = []
    
    for cart_item in cart_items.select_related('product'):
        product = cart_item.product
        if product.has_expiry_date:
            available_batches = ProductBatch.objects.filter(
                product=product,
                expiry_date__gte=today,
                remaining_quantity__gte=cart_item.quantity
            )
            sellable_batches = [b for b in available_batches if b.is_sellable(min_percent=70)]
            if not sellable_batches:
                all_batches = ProductBatch.objects.filter(product=product)
                if all_batches.exists():
                    unavailable_products.append(f"{product.name} (нет доступных партий)")
                else:
                    if product.stock_quantity is not None and product.stock_quantity < cart_item.quantity:
                        unavailable_products.append(f"{product.name} (недостаточно на складе)")
            else:
                total_available = sum(b.remaining_quantity for b in sellable_batches)
                if total_available < cart_item.quantity:
                    unavailable_products.append(f"{product.name} (недостаточно в партиях)")
        else:
            if product.stock_quantity is not None and product.stock_quantity < cart_item.quantity:
                unavailable_products.append(f"{product.name} (недостаточно на складе)")
    
    if unavailable_products:
        return None
    
    # Создаем заказ
    order = Order.objects.create(
        user=request.user,
        delivery_type=delivery_type,
        delivery_address=delivery_address,
        total_amount=final_total,
        payment_method=payment_method,
        favorite_discount_amount=favorite_discount_amount,
        promotion_discount=promotion_discount,
        delivery_cost=delivery_cost,
        fulfillment_store=fulfillment_store,
        delivery_slot=selected_slot,
        comment=delivery_comment,
        status='confirmed',  # Заказ сразу подтверждён после оплаты
    )
    
    # Создаем запись о платеже
    # Нормализуем payment_method для Payment модели (Payment использует те же choices что Order)
    payment_method_for_payment = payment_method
    if payment_method not in ['online', 'card', 'cash']:
        # Если это СБП или другой метод, сохраняем как 'online' для совместимости
        payment_method_for_payment = 'online' if payment_method == 'sbp' else 'online'
    
    Payment.objects.create(
        order=order,
        amount=Decimal(str(final_total)),
        payment_method=payment_method_for_payment,
        status='success',
        transaction_id=transaction_id,
    )
    
    # Автоматическое сохранение карты
    if card_number and card_expiry and card_holder and request.POST.get('save_card') == 'on':
        try:
            clean_card_number = card_number.replace(' ', '').replace('-', '').replace('*', '')
            if len(clean_card_number) >= 4:
                last4 = clean_card_number[-4:] if '*' not in clean_card_number else card_number[-4:]
                brand = 'Card'
                if clean_card_number.startswith('4'):
                    brand = 'Visa'
                elif clean_card_number.startswith(('51','52','53','54','55')):
                    brand = 'MasterCard'
                
                if '/' in card_expiry:
                    month, year = card_expiry.split('/')
                    expiry_month = int(month)
                    expiry_year = 2000 + int(year)
                    
                    pm = PaymentMethod.objects.create(
                        user=request.user,
                        brand=brand,
                        last4=last4,
                        expiry_month=expiry_month,
                        expiry_year=expiry_year,
                        is_default=True,
                    )
                    PaymentMethod.objects.filter(user=request.user).exclude(id=pm.id).update(is_default=False)
        except Exception as e:
            logger.exception("save_card_error: %s", e)
    
    # Создаем записи о сборке и доставке
    OrderPicking.objects.create(order=order, status='pending')
    if delivery_type == 'delivery':
        OrderDelivery.objects.create(order=order, status='pending')
    
    # Записываем использованную акцию
    if applied_promotion and promotion_discount > 0:
        try:
            UserPromotion.objects.create(
                user=request.user,
                promotion=applied_promotion,
                order=order,
                discount_amount=promotion_discount,
            )
        except Exception:
            pass
    
    # Создаем позиции заказа
    for cart_item in cart_items.select_related('product'):
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity=cart_item.quantity,
            price_per_unit=cart_item.product.price
        )
        try:
            product = cart_item.product
            if product.stock_quantity is not None:
                product.stock_quantity = max(0, int(product.stock_quantity) - int(cart_item.quantity))
                product.save(update_fields=['stock_quantity'])
        except Exception:
            pass
    
    # Резервируем место в слоте и очищаем корзину
    if selected_slot:
        try:
            selected_slot.reserve(1)
        except Exception:
            pass
    cart_items.delete()
    
    # Начисляем кешбэк (логика из loyalty_signals.py сработает при статусе 'delivered')
    try:
        loyalty_card = request.user.loyalty_card
        if loyalty_card:
            from decimal import Decimal
            final_total_dec = Decimal(str(final_total))
            loyalty_card.total_spent = (loyalty_card.total_spent or 0) + final_total_dec
            loyalty_card.update_level()
            loyalty_card.save()
    except Exception as e:
        logger.exception("cashback_error order=%s err=%s", order.id, e)
    
    # Отправляем уведомление
    try:
        send_order_confirmation(order)
    except Exception as e:
        logger.exception("email_error order=%s err=%s", order.id, e)
    
    logger.info("_create_order_after_payment created order=%s user=%s total=%.2f", order.id, request.user.id, final_total)
    return order

@login_required
def yoomoney_payment_view(request):
    """Обработка онлайн оплаты через YooMoney с созданием заказа после успешной оплаты"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        payment_method = request.POST.get('payment_method', 'online')
        card_number = request.POST.get('card_number')
        card_cvv = request.POST.get('card_cvv')
        card_expiry = request.POST.get('card_expiry')
        card_holder = request.POST.get('card_holder')
        saved_payment_id = None
        
        # Проверяем, используется ли сохранённая карта
        if payment_method.startswith('saved:'):
            try:
                saved_payment_id = int(payment_method.split(':',1)[1])
                from .models import PaymentMethod
                saved_pm = PaymentMethod.objects.get(id=saved_payment_id, user=request.user)
                # Для сохранённой карты валидация не требуется
                card_number = f"****{saved_pm.last4}"
                card_expiry = f"{saved_pm.expiry_month:02d}/{saved_pm.expiry_year % 100:02d}"
                card_holder = request.user.get_full_name() or request.user.username
                card_cvv = "***"  # CVV не хранится
            except Exception:
                return JsonResponse({
                    'success': False,
                    'error': 'Сохранённая карта не найдена',
                    'message': 'Выбранная карта не найдена'
                })
        
        # Симуляция обработки платежа через YooMoney
        import time
        import random
        
        # Имитация времени обработки (1-3 секунды)
        processing_time = random.uniform(1, 3)
        time.sleep(processing_time)
        
        # Проверяем данные карты (только для новой карты)
        if saved_payment_id is None:
            if not (card_number and card_cvv and card_expiry and card_holder):
                return JsonResponse({
                    'success': False,
                    'error': 'Неполные данные карты',
                    'message': 'Заполните все поля карты'
                })
            # Проверяем формат номера карты (должен быть 16 цифр)
            clean_card_number = card_number.replace(' ', '').replace('-', '')
            
            if len(clean_card_number) == 16 and clean_card_number.isdigit():
                # Проверяем CVV (3 цифры)
                if len(card_cvv) == 3 and card_cvv.isdigit():
                    # Проверяем срок действия (MM/YY)
                    if len(card_expiry) == 5 and card_expiry[2] == '/':
                        month = card_expiry[:2]
                        year = card_expiry[3:]
                        
                        if month.isdigit() and year.isdigit():
                            month_int = int(month)
                            year_int = int(year)
                            
                            # Проверяем валидность месяца и года
                            if 1 <= month_int <= 12 and year_int >= 25:  # Предполагаем, что год >= 2025
                                # Симулируем успешный платеж
                                payment_id = f'ym_{int(time.time())}_{random.randint(1000, 9999)}'
                                transaction_id = f'TXN_{int(time.time())}'
                                
                                # Создаем заказ после успешной оплаты
                                try:
                                    order = _create_order_after_payment(request, payment_id, transaction_id, amount, card_number, card_expiry, card_holder)
                                    if order:
                                        payment_data = {
                                            'success': True,
                                            'payment_id': payment_id,
                                            'order_id': order.id,
                                            'status': 'succeeded',
                                            'amount': amount,
                                            'currency': 'RUB',
                                            'message': 'Платеж через YooMoney успешно обработан',
                                            'transaction_id': transaction_id,
                                            'processing_time': f'{processing_time:.2f}s'
                                        }
                                    else:
                                        payment_data = {
                                            'success': False,
                                            'error': 'Ошибка создания заказа',
                                            'message': 'Не удалось создать заказ после оплаты'
                                        }
                                except Exception as e:
                                    logger.exception("yoomoney_payment order_creation_error: %s", e)
                                    payment_data = {
                                        'success': False,
                                        'error': 'Ошибка создания заказа',
                                        'message': 'Не удалось создать заказ после оплаты'
                                    }
                            else:
                                payment_data = {
                                    'success': False,
                                    'error': 'Неверный срок действия карты',
                                    'message': 'Проверьте срок действия карты'
                                }
                        else:
                            payment_data = {
                                'success': False,
                                'error': 'Неверный формат срока действия',
                                'message': 'Используйте формат MM/YY'
                            }
                    else:
                        payment_data = {
                            'success': False,
                            'error': 'Неверный формат срока действия',
                            'message': 'Используйте формат MM/YY'
                        }
                else:
                    payment_data = {
                        'success': False,
                        'error': 'Неверный CVV код',
                        'message': 'CVV должен содержать 3 цифры'
                    }
            else:
                payment_data = {
                    'success': False,
                    'error': 'Неверный номер карты',
                    'message': 'Номер карты должен содержать 16 цифр'
                }
        else:
            # Для сохранённой карты сразу обрабатываем оплату
            payment_id = f'ym_{int(time.time())}_{random.randint(1000, 9999)}'
            transaction_id = f'TXN_{int(time.time())}'
            
            try:
                order = _create_order_after_payment(request, payment_id, transaction_id, amount, card_number, card_expiry, card_holder)
                if order:
                    payment_data = {
                        'success': True,
                        'payment_id': payment_id,
                        'order_id': order.id,
                        'status': 'succeeded',
                        'amount': amount,
                        'currency': 'RUB',
                        'message': 'Платеж через YooMoney успешно обработан',
                        'transaction_id': transaction_id,
                        'processing_time': f'{processing_time:.2f}s'
                    }
                else:
                    payment_data = {
                        'success': False,
                        'error': 'Ошибка создания заказа',
                        'message': 'Не удалось создать заказ после оплаты'
                    }
            except Exception as e:
                logger.exception("yoomoney_payment order_creation_error (saved card): %s", e)
                payment_data = {
                    'success': False,
                    'error': 'Ошибка создания заказа',
                    'message': 'Не удалось создать заказ после оплаты'
                }
        
        return JsonResponse(payment_data)
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def sbp_payment_view(request):
    """Обработка оплаты через СБП (Система быстрых платежей)"""
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        # Симуляция обработки платежа через СБП
        import time
        import random
        
        # Имитация времени обработки (быстрее чем YooMoney - мгновенно)
        processing_time = random.uniform(0.5, 1.5)
        time.sleep(processing_time)
        
        # СБП всегда успешен (в реальности здесь была бы интеграция с банком)
        payment_id = f'sbp_{int(time.time())}_{random.randint(1000, 9999)}'
        transaction_id = f'SBP_{int(time.time())}'
        
        # Создаем заказ после успешной оплаты с указанием payment_method='sbp'
        try:
            order = _create_order_after_payment(request, payment_id, transaction_id, amount, payment_method_override='sbp')
            if order:
                payment_data = {
                    'success': True,
                    'payment_id': payment_id,
                    'order_id': order.id,
                    'status': 'succeeded',
                    'amount': amount,
                    'currency': 'RUB',
                    'message': 'Платеж через СБП успешно обработан',
                    'transaction_id': transaction_id,
                    'processing_time': f'{processing_time:.2f}s'
                }
            else:
                payment_data = {
                    'success': False,
                    'error': 'Ошибка создания заказа',
                    'message': 'Не удалось создать заказ после оплаты'
                }
        except Exception as e:
            logger.exception("sbp_payment order_creation_error: %s", e)
            payment_data = {
                'success': False,
                'error': 'Ошибка создания заказа',
                'message': 'Не удалось создать заказ после оплаты'
            }
        
        return JsonResponse(payment_data)
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

def order_success_view(request):
    """Страница успешного оформления заказа"""
    # Получаем данные из сессии или параметров
    order_id = request.session.get('last_order_id', '12345')
    delivery_type = request.session.get('last_delivery_type', 'Самовывоз')
    payment_method = request.session.get('last_payment_method', 'Наличными')
    total_amount = request.session.get('last_total_amount', '1 500')
    payment_id = request.session.get('last_payment_id', None)
    
    context = {
        'order_id': order_id,
        'delivery_type': delivery_type,
        'payment_method': payment_method,
        'total_amount': total_amount,
        'payment_id': payment_id,
    }
    
    # Очищаем сессию
    for key in ['last_order_id', 'last_delivery_type', 'last_payment_method', 'last_total_amount', 'last_payment_id']:
        if key in request.session:
            del request.session[key]
    
    return render(request, 'paint_shop_project/order_success.html', context)

@login_required
def order_tracking_view(request, order_id):
    """Отслеживание заказа"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    status_history = OrderStatusHistory.objects.filter(order=order).order_by('-timestamp')
    
    # Определяем прогресс заказа
    status_progress = {
        'created': 0,
        'confirmed': 25,
        'ready': 50,
        'in_transit': 75,
        'delivered': 100,
        'cancelled': 0
    }
    
    progress = status_progress.get(order.status, 0)
    
    context = {
        'order': order,
        'status_history': status_history,
        'progress': progress,
    }
    return render(request, 'paint_shop_project/order_tracking.html', context)

@login_required
def manage_addresses_view(request):
    """Управление адресами пользователя (список/добавление/удаление/по умолчанию)"""
    from .models import UserAddress
    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            addr = request.POST.get('address','').strip()
            label = request.POST.get('label','')
            entrance = request.POST.get('entrance','')
            floor = request.POST.get('floor','')
            apartment = request.POST.get('apartment','')
            intercom_code = request.POST.get('intercom_code','')
            comment = request.POST.get('comment','')
            is_default = True if request.POST.get('is_default') == 'on' else False
            if addr:
                created = UserAddress.objects.create(
                    user=user,
                    label=label or 'Адрес',
                    address=addr,
                    entrance=entrance,
                    floor=floor,
                    apartment=apartment,
                    intercom_code=intercom_code,
                    comment=comment,
                    is_default=is_default
                )
                if is_default:
                    UserAddress.objects.filter(user=user).exclude(id=created.id).update(is_default=False)
                messages.success(request, 'Адрес добавлен')
        elif action == 'delete':
            try:
                addr_id = int(request.POST.get('address_id'))
                UserAddress.objects.filter(user=user, id=addr_id).delete()
                messages.success(request, 'Адрес удален')
            except Exception:
                messages.error(request, 'Не удалось удалить адрес')
        elif action == 'set_default':
            try:
                addr_id = int(request.POST.get('address_id'))
                UserAddress.objects.filter(user=user).update(is_default=False)
                UserAddress.objects.filter(user=user, id=addr_id).update(is_default=True)
                messages.success(request, 'Адрес по умолчанию обновлен')
            except Exception:
                messages.error(request, 'Не удалось обновить адрес по умолчанию')
        return redirect('manage_addresses')
    addresses = user.addresses.all().order_by('-is_default','-updated_at')
    return render(request, 'paint_shop_project/addresses.html', { 'addresses': addresses })

@login_required
def manage_payment_methods_view(request):
    """Управление сохранёнными способами оплаты (маски карт)"""
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            brand = request.POST.get('brand','').strip() or 'Card'
            last4 = (request.POST.get('last4','') or '')[-4:]
            expiry_month = int(request.POST.get('expiry_month') or 1)
            expiry_year = int(request.POST.get('expiry_year') or 2099)
            is_default = request.POST.get('is_default') == 'on'
            if last4 and len(last4) == 4:
                pm = PaymentMethod.objects.create(
                    user=request.user,
                    brand=brand,
                    last4=last4,
                    expiry_month=expiry_month,
                    expiry_year=expiry_year,
                    is_default=is_default,
                )
                if is_default:
                    PaymentMethod.objects.filter(user=request.user).exclude(id=pm.id).update(is_default=False)
                messages.success(request, 'Способ оплаты добавлен')
        elif action == 'delete':
            try:
                pid = int(request.POST.get('payment_id'))
                PaymentMethod.objects.filter(user=request.user, id=pid).delete()
                messages.success(request, 'Способ оплаты удалён')
            except Exception:
                messages.error(request, 'Не удалось удалить способ оплаты')
        elif action == 'set_default':
            try:
                pid = int(request.POST.get('payment_id'))
                PaymentMethod.objects.filter(user=request.user).update(is_default=False)
                PaymentMethod.objects.filter(user=request.user, id=pid).update(is_default=True)
                messages.success(request, 'Способ оплаты по умолчанию обновлён')
            except Exception:
                messages.error(request, 'Не удалось обновить')
        return redirect('manage_payment_methods')
    methods = PaymentMethod.objects.filter(user=request.user).order_by('-is_default','-created_at')
    return render(request, 'paint_shop_project/payment_methods.html', { 'methods': methods })
