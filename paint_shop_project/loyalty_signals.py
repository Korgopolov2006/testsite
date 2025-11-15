from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Order


@receiver(pre_save, sender=Order)
def _store_previous_status(sender, instance, **kwargs):
    if not instance.pk:
        instance._previous_status = None
        return
    try:
        previous = sender.objects.only('status').get(pk=instance.pk)
        instance._previous_status = previous.status
    except sender.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def _award_cashback_on_delivered(sender, instance, **kwargs):
    previous_status = getattr(instance, '_previous_status', None)
    if instance.status == 'delivered' and previous_status != 'delivered':
        from .loyalty import award_cashback_for_order
        award_cashback_for_order(instance)
