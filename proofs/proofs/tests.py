from django.test import SimpleTestCase, TransactionTestCase
from .demos import sync_proof, thread_proof, transaction_proof, rectangle_proof
from .rectangle import Rectangle


class SignalDispatchTests(SimpleTestCase):
    def test_sync_receiver_finishes_before_send_returns(self):
        events, elapsed = sync_proof()
        self.assertEqual(events[-1], "caller after send")
        self.assertGreaterEqual(elapsed, 0.05)

    def test_sync_receiver_runs_on_caller_thread(self):
        caller, receiver = thread_proof()
        self.assertEqual(caller, receiver)


class TransactionProofTests(TransactionTestCase):
    # TransactionTestCase, not TestCase: TestCase's wrapping atomic block
    # would hide the default-autocommit distinction being demonstrated.
    def test_atomic_rollback_and_autocommit_contrast(self):
        atomic, autocommit = transaction_proof()
        self.assertEqual(atomic, (0, 0))
        self.assertEqual(autocommit, (1, 1))


class RectangleTests(SimpleTestCase):
    def test_order_and_shape(self):
        self.assertEqual(rectangle_proof(), [{"length": 3}, {"width": 4}])

    def test_repeatable_iteration(self):
        r = Rectangle(5, 6)
        self.assertEqual(list(r), list(r))

    def test_non_integer_input_rejected(self):
        for args in [(3.0, 4), (3, "4"), (True, 4)]:
            with self.subTest(args=args), self.assertRaises(TypeError):
                Rectangle(*args)
