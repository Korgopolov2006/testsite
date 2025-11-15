from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User, PhoneVerification
import random
import string
from django.utils import timezone
from datetime import timedelta

class PhoneLoginForm(forms.Form):
    """Форма входа по номеру телефона"""
    phone = forms.CharField(
        max_length=20,
        label="Номер телефона",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67',
            'id': 'phone-input'
        })
    )
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Очищаем номер от всех символов кроме цифр
            phone_clean = ''.join(filter(str.isdigit, phone))
            if len(phone_clean) < 10:
                raise ValidationError('Введите корректный номер телефона')
            return phone_clean
        return phone

class PhoneVerificationForm(forms.Form):
    """Форма ввода SMS-кода"""
    code = forms.CharField(
        max_length=6,
        label="SMS-код",
        widget=forms.TextInput(attrs={
            'class': 'form-control verification-input',
            'placeholder': '000000',
            'maxlength': '6',
            'id': 'verification-code'
        })
    )
    phone = forms.CharField(widget=forms.HiddenInput())
    
    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code or len(code) != 6:
            raise ValidationError('Введите 6-значный код')
        return code

class PhoneRegistrationForm(forms.ModelForm):
    """Форма регистрации по номеру телефона"""
    phone = forms.CharField(
        max_length=20,
        label="Номер телефона",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+7 (999) 123-45-67',
            'id': 'reg-phone-input'
        })
    )
    first_name = forms.CharField(
        max_length=30,
        label="Имя",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите ваше имя'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        label="Фамилия",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Введите вашу фамилию'
        })
    )
    email = forms.EmailField(
        label="Email (необязательно)",
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your@email.com'
        })
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Придумайте пароль'
        })
    )
    password2 = forms.CharField(
        label="Подтверждение пароля",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Повторите пароль'
        })
    )
    agree_terms = forms.BooleanField(
        label="Я согласен с обработкой персональных данных",
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'agree-terms'
        })
    )
    agree_privacy = forms.BooleanField(
        label="Я согласен с политикой конфиденциальности",
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'agree-privacy'
        })
    )
    
    class Meta:
        model = User
        fields = ('phone', 'first_name', 'last_name', 'email', 'password1', 'password2')
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            phone_clean = ''.join(filter(str.isdigit, phone))
            if len(phone_clean) < 10:
                raise ValidationError('Введите корректный номер телефона')
            # Проверяем, не зарегистрирован ли уже этот номер
            if User.objects.filter(phone=phone_clean).exists():
                raise ValidationError('Пользователь с таким номером уже зарегистрирован')
            return phone_clean
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError('Пароли не совпадают')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user

def generate_sms_code():
    """Генерирует 6-значный SMS-код"""
    return ''.join(random.choices(string.digits, k=6))

def send_sms_code(phone, verification_type='registration'):
    """Отправляет SMS-код (в реальном проекте здесь будет интеграция с SMS-провайдером)"""
    code = generate_sms_code()
    expires_at = timezone.now() + timedelta(minutes=5)
    
    # Помечаем старые коды как использованные
    PhoneVerification.objects.filter(
        phone=phone,
        verification_type=verification_type,
        is_used=False
    ).update(is_used=True)
    
    # Создаем новый код
    PhoneVerification.objects.create(
        phone=phone,
        code=code,
        expires_at=expires_at,
        verification_type=verification_type
    )
    
    # В реальном проекте здесь будет отправка SMS
    print(f"SMS-код для {phone}: {code} (действителен 5 минут)")
    
    return code

def verify_sms_code(phone, code, verification_type='registration'):
    """Проверяет SMS-код"""
    try:
        verification = PhoneVerification.objects.get(
            phone=phone,
            code=code,
            verification_type=verification_type,
            is_used=False
        )
        
        if verification.is_expired():
            return False, "Код истек"
        
        verification.is_used = True
        verification.save()
        return True, "Код подтвержден"
    
    except PhoneVerification.DoesNotExist:
        return False, "Неверный код"

