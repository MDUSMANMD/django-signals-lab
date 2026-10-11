from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AuditRecord, SourceRecord


@receiver(post_save, sender=SourceRecord, dispatch_uid="proofs.audit_source")
def write_audit(sender, instance, created, using, **kwargs):
    if created:
        AuditRecord.objects.using(using).create(source=instance, label=instance.label)
        if instance.fail_receiver:
            raise RuntimeError("Receiver failed after its database write")
