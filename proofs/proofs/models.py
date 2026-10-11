from django.db import models


class SourceRecord(models.Model):
    label = models.CharField(max_length=100)
    fail_receiver = models.BooleanField(default=False)


class AuditRecord(models.Model):
    source = models.ForeignKey(SourceRecord, on_delete=models.CASCADE)
    label = models.CharField(max_length=100)
