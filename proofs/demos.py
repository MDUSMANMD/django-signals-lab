import threading
import time
from django.dispatch import Signal
from django.db import connection, transaction
from .models import AuditRecord, SourceRecord
from .rectangle import Rectangle


def sync_proof():
    signal = Signal()
    events = []
    def receiver(sender, **kwargs):
        events.append("receiver started")
        time.sleep(0.05)
        events.append("receiver finished")
    signal.connect(receiver, weak=False)
    events.append("caller before send")
    start = time.perf_counter()
    signal.send(sender=sync_proof)
    elapsed = time.perf_counter() - start
    events.append("caller after send")
    expected = ["caller before send", "receiver started", "receiver finished", "caller after send"]
    assert events == expected
    assert elapsed >= 0.05
    return events, elapsed


def thread_proof():
    signal = Signal()
    caller_id = threading.get_ident()
    received_ids = []
    def receiver(sender, **kwargs):
        received_ids.append(threading.get_ident())
    signal.connect(receiver, weak=False)
    signal.send(sender=thread_proof)
    assert received_ids == [caller_id]
    return caller_id, received_ids[0]


def transaction_proof():
    assert connection.get_autocommit(), "Run outside a surrounding transaction"
    prefix = "proof-transaction-"
    SourceRecord.objects.filter(label__startswith=prefix).delete()
    assert not AuditRecord.objects.filter(label__startswith=prefix).exists()
    try:
        with transaction.atomic():
            SourceRecord.objects.create(label=prefix + "atomic", fail_receiver=True)
    except RuntimeError:
        pass
    atomic_counts = (
        SourceRecord.objects.filter(label=prefix + "atomic").count(),
        AuditRecord.objects.filter(label=prefix + "atomic").count(),
    )
    assert atomic_counts == (0, 0)
    try:
        SourceRecord.objects.create(label=prefix + "autocommit", fail_receiver=True)
    except RuntimeError:
        pass
    autocommit_counts = (
        SourceRecord.objects.filter(label=prefix + "autocommit").count(),
        AuditRecord.objects.filter(label=prefix + "autocommit").count(),
    )
    assert autocommit_counts == (1, 1)
    SourceRecord.objects.filter(label__startswith=prefix).delete()
    return atomic_counts, autocommit_counts


def rectangle_proof():
    rectangle = Rectangle(3, 4)
    result = list(rectangle)
    assert result == [{"length": 3}, {"width": 4}]
    assert list(rectangle) == result
    return result
