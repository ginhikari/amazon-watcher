import logging
import time
from config import Config
from state import StateStore
from models import Phase, StateMachine, SafetyError
import amazon

log = logging.getLogger(__name__)

def purchase_flow(page, config, store, machine, confirm=input):
    store.guard(config.target_asin)
    store.mark_purchase_started()
    machine.transition(Phase.PURCHASE_LOCKED)
    # Do not clear the persistent guard on exceptions: cart/order outcome is unresolved.
    observed = amazon.add_one(page, config)
    machine.transition(Phase.CART)
    page.goto('https://www.amazon.co.jp/gp/cart/view.html', wait_until='domcontentloaded')
    price, total = amazon.verify_cart(page, config)
    if store.already_purchased(config.target_asin):
        raise SafetyError('Target has already been purchased')
    machine.transition(Phase.CART_VERIFIED)
    amazon.open_checkout(page)
    machine.transition(Phase.CHECKOUT_READY)
    print(f'''\n================================
CHECKOUT READY FOR MANUAL REVIEW
================================
ASIN: {config.target_asin}
Maximum allowed price: ¥{config.max_price:,}
Observed product price: ¥{observed:,}
Cart item price: ¥{price:,}
Cart subtotal: ¥{total:,}
Quantity: 1

Review product, seller, shipping, delivery date, final total and payment method.
Final total must not exceed ¥{config.max_session_spend:,}.
Submit the order manually in the browser. Automation has stopped.
''')
    machine.transition(Phase.MANUAL_CONFIRMATION)
    answer = confirm('Was the order successfully placed? [y/N]: ').strip().lower()
    if answer == 'y':
        store.mark_as_purchased(config.target_asin)
        machine.transition(Phase.PURCHASED)
    else:
        log.warning('Purchase unconfirmed. Persistent guard retained; manual review required.')
    machine.transition(Phase.EXIT)

def watch(page, config, store, machine):
    machine.transition(Phase.WATCHING)
    while True:
        store.guard(config.target_asin)
        log.info('Checking product')
        page.goto(config.product_url, wait_until='domcontentloaded')
        amazon.verify_product(page, config.target_asin)
        price = amazon.get_product_price(page)
        available = amazon.is_product_available(page)
        if price is None:
            log.info('Unknown price')
        elif price > config.max_price:
            log.info('Price: ¥%s; above maximum price', format(price, ','))
        elif not available:
            log.info('Product unavailable')
        else:
            log.info('Purchase conditions met at ¥%s', format(price, ','))
            machine.transition(Phase.CONDITION_MET)
            if config.dry_run:
                print(f'DRY RUN: Would add ASIN {config.target_asin} at ¥{price:,}.')
                machine.transition(Phase.EXIT)
            else:
                purchase_flow(page, config, store, machine)
            return
        time.sleep(config.check_interval_seconds)

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    try:
        config = Config()
        config.validate()
        store = StateStore(config.state_file)
        with store.exclusive():
            store.guard(config.target_asin)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(str(config.profile_dir), headless=False)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto('https://www.amazon.co.jp/', wait_until='domcontentloaded')
                    input('Log in normally in the browser, then press Enter here to monitor: ')
                    watch(page, config, store, StateMachine())
                finally:
                    context.close()
    except (SafetyError, ValueError, OSError, EOFError) as exc:
        log.error('%s', exc)
        return 1
    except KeyboardInterrupt:
        log.info('Stopped by user. Any unresolved purchase guard is retained.')
        return 130
    except ImportError:
        log.error('Install dependencies: python -m pip install -r requirements.txt')
        return 1
    except Exception as exc:
        # Last-resort process boundary: stop, preserve state, avoid logging URLs/tokens.
        log.error('Stopped after unexpected %s; review browser and purchase state.', type(exc).__name__)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
