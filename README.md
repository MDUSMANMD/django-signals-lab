# Django signals lab

A small Django project to check how signals work. It also has an iterable Rectangle class.

These examples were tested with Python 3.10.12, Django 5.2.18 and SQLite.

## Run
```sh
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test -v 2
python manage.py run_proofs
```

No server or API key is needed. Use the local SQLite database. The command adds and removes demo rows with the `proof-transaction-` prefix. The settings and demo key are only for local use, not production.

## Q1: Are Django signals synchronous or asynchronous by default?

With a normal synchronous receiver and `Signal.send()`, they are synchronous. The caller waits until the receiver finishes. Most built-in signals use `send()`. Django also supports async receivers and `asend()`, so this is not a rule for every signal.

The receiver waits for 0.05 seconds. The recorded order shows that the caller continues only after the receiver finishes. The order assertion is the main check; elapsed time is an extra check.
```python
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

```

Observed output:
```text
Q1 events: ['caller before send', 'receiver started', 'receiver finished', 'caller after send']
Q1 send duration >= 0.05 seconds: True
```

## Q2: Do signals run in the same thread as the caller?

For a synchronous receiver called through `send()`, yes. The example compares the caller's thread ID with the receiver's thread ID. Async receivers and async-to-sync adapters can behave differently.
```python
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

```

Observed output (thread IDs change between runs):
```text
Q2 caller thread: 140520770748864; receiver thread: 140520770748864; equal: True
```

## Q3: Do signals run in the same database transaction as the caller by default?

A signal does not start a separate transaction. If the caller uses `transaction.atomic()` and the receiver uses the same database connection, both writes are part of that transaction. If the receiver raises an error, both roll back.

The important detail is that Django uses autocommit by default. Without an atomic block, successful queries commit separately. A later error in the receiver does not undo those writes. So the answer is not simply "always the same transaction by default". Different database aliases, async adapters and `on_commit()` callbacks also need separate care.

Saving a `SourceRecord` calls this `post_save` receiver. It adds an audit row, then raises an error when `fail_receiver` is set:
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AuditRecord, SourceRecord


@receiver(post_save, sender=SourceRecord, dispatch_uid="proofs.audit_source")
def write_audit(sender, instance, created, using, **kwargs):
    if created:
        AuditRecord.objects.using(using).create(source=instance, label=instance.label)
        if instance.fail_receiver:
            raise RuntimeError("Receiver failed after its database write")

```

The example checks both cases:
```python
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

```

Observed output (source count, audit count):
```text
Q3 atomic after receiver exception (source, audit): (0, 0)
Q3 autocommit after receiver exception (source, audit): (1, 1)
```

The test uses `TransactionTestCase`. Regular `TestCase` wraps the test in a transaction, which would hide the autocommit behaviour being checked here.

## Q4: Iterable Rectangle

The class takes `length: int` and `width: int`. Iterating gives `{'length': value}` first, then `{'width': value}`.
```python
class Rectangle:
    """An iterable rectangle; integers only (bool is intentionally rejected)."""

    def __init__(self, length: int, width: int):
        if type(length) is not int or type(width) is not int:
            raise TypeError("length and width must be integers")
        self.length = length
        self.width = width

    def __iter__(self):
        yield {"length": self.length}
        yield {"width": self.width}

```

Observed output:
```text
Q4 list(Rectangle(3, 4)): [{'length': 3}, {'width': 4}]
```

Each iteration creates a new generator, so the object can be iterated again. Non-integers, including bool, are rejected. There is no positive-number restriction because it was not required.

## Checks

- `python manage.py check`: no issues.
- `python manage.py test -v 2`: 6 tests passed.
- `python manage.py run_proofs`: all four proofs passed.

The full output is in `evidence/run-proofs.txt` and `evidence/tests.txt`. Settings, migrations and signal registration are included, so this runs as a Django project.

## References

- https://docs.djangoproject.com/en/5.2/topics/signals/
- https://docs.djangoproject.com/en/5.2/topics/db/transactions/
