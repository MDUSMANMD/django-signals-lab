# Django signals lab

A complete, local-only Django project with runnable proofs for Django signals and an iterable Rectangle. Tested with Python 3.10.12, Django 5.2.18 and SQLite.

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

No server, account or API key is needed. The proof command creates and removes demo records using the `proof-transaction-` prefix in its local SQLite database. Do not point this demo at a production database. The settings contain an explicitly non-secret local demo key and are not production settings.

## Q1: Are Django signals synchronous or asynchronous by default?

For ordinary synchronous receivers dispatched with `Signal.send()`, they are synchronous. The caller waits for the receiver to finish. Most built-in signals use `send()`. Modern Django also supports `asend()` and async receivers, so this answer does not claim every signal/receiver is always synchronous.

The proof records the caller and receiver event order and blocks inside the receiver for 0.05 seconds. `send()` does not return until that work is done. The event-order assertion is the primary proof; the duration check supports it.

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

A synchronous receiver invoked by synchronous `send()` runs in the caller's thread. This is not a universal guarantee for async receivers or async-to-sync adapters. The proof compares the actual caller and receiver thread identifiers.

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

Observed output (thread numbers vary by run):
```text
Q2 caller thread: 140520770748864; receiver thread: 140520770748864; equal: True
```

## Q3: Do signals run in the same database transaction as the caller by default?

A signal does not create a separate transaction. A synchronous receiver using the same database alias/connection participates in an active caller transaction. Inside `transaction.atomic()`, both source and receiver audit writes roll back together if the receiver raises an exception.

However, Django defaults to **autocommit**, not a transaction spanning the entire caller and receiver. Without an enclosing atomic block, each successful query commits. A later receiver exception does not undo those already committed writes. Therefore, an unqualified "yes, always the same transaction by default" is incorrect. Database aliases, async adapters and explicitly deferred `on_commit()` callbacks also change what can be assumed.

`SourceRecord` triggers this registered `post_save` receiver, which writes an audit record and then deliberately raises:

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

The proof tests both transaction contexts:

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

Observed output (counts are source records, audit records):
```text
Q3 atomic after receiver exception (source, audit): (0, 0)
Q3 autocommit after receiver exception (source, audit): (1, 1)
```

The transaction test uses `TransactionTestCase`, not `TestCase`. `TestCase` wraps the test in a transaction and would hide the default-autocommit distinction.

## Q4: Iterable Rectangle

Requirements: initialize with `length: int` and `width: int`; iterating yields `{'length': value}` first and `{'width': value}` second.

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

A new generator is created on each iteration. Non-integer inputs, including bool, are rejected. No positivity rule is imposed because the problem does not specify one.

## Verification

- `python manage.py check`: no issues.
- `python manage.py test -v 2`: 6 tests passed.
- `python manage.py run_proofs`: all four proofs passed.
- Complete captured output: `evidence/run-proofs.txt` and `evidence/tests.txt`.

The included migrations, app configuration and signal registration make this a Django project, not a standalone Python answer file.

## Assistance disclosure

Prepared with AI assistance, including code, tests and explanations. Run, review and understand the project before using or discussing it. Do not describe this as unaided work. 

## Sources

- Django 5.2 signals: https://docs.djangoproject.com/en/5.2/topics/signals/
- Django 5.2 transactions: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
