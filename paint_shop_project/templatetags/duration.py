"""
Template фильтры для форматирования длительности
"""
from django import template

register = template.Library()


@register.filter
def format_duration(duration):
    """Форматирует timedelta или число секунд для отображения"""
    if duration in (None, ''):
        return "—"
    
    try:
        if hasattr(duration, "total_seconds"):
            total_seconds = int(duration.total_seconds())
        else:
            total_seconds = int(float(duration))
    except (ValueError, TypeError):
        return "—"
    
    if total_seconds < 0:
        total_seconds = 0
    
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




