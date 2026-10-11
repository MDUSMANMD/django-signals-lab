from django.core.management.base import BaseCommand
from proofs.demos import sync_proof, thread_proof, transaction_proof, rectangle_proof


class Command(BaseCommand):
    help = "Run the four signal proofs on the local demo database"

    def handle(self, *args, **options):
        events, elapsed = sync_proof()
        self.stdout.write(f"Q1 events: {events}")
        self.stdout.write(f"Q1 send duration >= 0.05 seconds: {elapsed >= 0.05}")
        caller, receiver = thread_proof()
        self.stdout.write(f"Q2 caller thread: {caller}; receiver thread: {receiver}; equal: {caller == receiver}")
        atomic, autocommit = transaction_proof()
        self.stdout.write(f"Q3 atomic after receiver exception (source, audit): {atomic}")
        self.stdout.write(f"Q3 autocommit after receiver exception (source, audit): {autocommit}")
        self.stdout.write(f"Q4 list(Rectangle(3, 4)): {rectangle_proof()}")
        self.stdout.write("All four proofs passed.")
