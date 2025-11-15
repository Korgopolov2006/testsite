# Utility helpers for loyalty and cashback logic

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist


def award_cashback_for_order(order):
    """Начисляет кешбэк за заказ, если это ещё не сделано."""
    if order is None or not getattr(order, "user", None):
        return Decimal('0.00')

    try:
        loyalty_card = order.user.loyalty_card
    except ObjectDoesNotExist:
        return Decimal('0.00')

    if not getattr(order, 'total_amount', None):
        return Decimal('0.00')

    return loyalty_card.add_cashback(order.total_amount, order=order, description=f'Кешбэк за заказ #{order.id}')
