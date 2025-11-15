from django import template
 
register = template.Library()

@register.filter
def sub(value, arg):
    """Вычитает arg из value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """Умножает value на arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def div(value, arg):
    """Делит value на arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0


@register.filter
def get_item(dictionary, key):
    """Получить элемент словаря по ключу в шаблоне."""
    try:
        return dictionary.get(key, 0)
    except AttributeError:
        try:
            return dictionary[int(key)]
        except Exception:
            return 0