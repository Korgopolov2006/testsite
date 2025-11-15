"""
Template фильтры для админки
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Получить значение из словаря по ключу"""
    if dictionary is None:
        return None
    return dictionary.get(key)




