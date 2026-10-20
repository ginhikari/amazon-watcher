import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from config import Config
from state import StateStore
from models import SafetyError, PriceExceeded, Phase, StateMachine
from amazon import parse_price, validate_cart_values
from main import purchase_flow, watch

ASIN = 'B012345678'
def config(**kwargs):
    return Config(product_url=f'https://www.amazon.co.jp/dp/{ASIN}', target_asin=ASIN, **kwargs)

class SafetyTests(unittest.TestCase):
    def test_prices(self):
        for text, expected in [('￥6,980', 6980), ('¥12,800', 12800), ('6,980円', 6980), (None, None), ('', None), ('free', None), ('¥6,98', None), ('$6980', None), ('6980.00', None), ('-1', None), ('0', None)]:
            with self.subTest(text=text): self.assertEqual(parse_price(text), expected)

    def test_configuration(self):
        config().validate()
        for kwargs in [{'max_quantity': 2}, {'max_quantity': True}, {'max_price': 0}, {'max_session_spend': 0}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): config(**kwargs).validate()

    def test_state_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            store = StateStore(path)
            self.assertFalse(store.already_purchased(ASIN))
            store.mark_purchase_started()
            with self.assertRaises(SafetyError): StateStore(path).guard(ASIN)
            store.mark_as_purchased(ASIN)
            self.assertTrue(StateStore(path).already_purchased(ASIN))
            self.assertFalse(store.load_state().attempting_purchase)
            with self.assertRaises(SafetyError): store.guard(ASIN)
            path.write_text('{broken')
            with self.assertRaises(SafetyError): store.load_state()

    def test_exclusive(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            with store.exclusive():
                with self.assertRaises(SafetyError):
                    with store.exclusive(): pass

    def test_cart(self):
        validate_cart_values(ASIN, 1, 6980, 6980, config())
        for asin, qty, price, total in [(ASIN, 2, 6980, 6980), ('OTHER', 1, 6980, 6980), (ASIN, 1, 7500, 7500), (ASIN, 1, 6980, None), (ASIN, 1, 6980, 7100)]:
            with self.subTest(total=total), self.assertRaises(SafetyError):
                validate_cart_values(asin, qty, price, total, config())

    def test_price_increase_before_click(self):
        import amazon
        page = Mock()
        quantity = Mock()
        quantity.input_value.return_value = '1'
        with patch.object(amazon, 'visible_elements', return_value=[quantity]), patch.object(amazon, 'verify_product'), patch.object(amazon, 'is_product_available', return_value=True), patch.object(amazon, 'get_product_price', return_value=7500), patch.object(amazon, 'unique') as button:
            with self.assertRaises(PriceExceeded): amazon.add_one(page, config())
            button.assert_not_called()

    def test_dry_run_no_cart(self):
        import amazon
        page, store = Mock(), Mock()
        with patch.object(amazon, 'verify_product'), patch.object(amazon, 'get_product_price', return_value=6900), patch.object(amazon, 'is_product_available', return_value=True), patch('main.purchase_flow') as flow:
            watch(page, config(), store, StateMachine())
            flow.assert_not_called()

    def test_failed_attempt_stays_locked(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            machine = StateMachine()
            machine.transition(Phase.WATCHING)
            machine.transition(Phase.CONDITION_MET)
            with patch('amazon.add_one', side_effect=PriceExceeded('Price changed')):
                with self.assertRaises(PriceExceeded): purchase_flow(Mock(), config(), store, machine)
            self.assertTrue(store.load_state().attempting_purchase)

    def test_manual_confirmation(self):
        for answer, purchased in [('y', True), ('n', False)]:
            with self.subTest(answer=answer), tempfile.TemporaryDirectory() as directory:
                store = StateStore(Path(directory) / 'state.json')
                machine = StateMachine()
                machine.transition(Phase.WATCHING)
                machine.transition(Phase.CONDITION_MET)
                page = Mock()
                with patch('amazon.add_one', return_value=6900), patch('amazon.verify_cart', return_value=(6900, 6900)), patch('amazon.open_checkout') as checkout, patch('builtins.print'):
                    purchase_flow(page, config(), store, machine, confirm=lambda _: answer)
                    checkout.assert_called_once()
                self.assertEqual(store.already_purchased(ASIN), purchased)
                self.assertEqual(store.load_state().attempting_purchase, not purchased)
                self.assertEqual(machine.phase, Phase.EXIT)

    def test_invalid_transition(self):
        machine = StateMachine()
        with self.assertRaises(SafetyError): machine.transition(Phase.PURCHASED)

if __name__ == '__main__': unittest.main()
