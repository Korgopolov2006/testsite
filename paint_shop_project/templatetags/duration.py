"""
Template фильтры для форматирования длительности
"""
from django import template

register = template.Library()


@register.filter
def format_duration(duration):
    """Форматирует timedelta для отображения"""
    if not duration:
        return "—"
    
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if hours:
        parts.append(f"{hours}ч")
    if minutes:
        parts.append(f"{minutes}м")
    if seconds or not parts:
        parts.append(f"{seconds}с")
    
    return " ".join(parts)




