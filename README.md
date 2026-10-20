# Amazon product watcher

Python 3.10+ on Linux/macOS. Supports Amazon Japan, whole JPY, one ASIN,
quantity one. Dry-run is enabled by default. No final-order submission code,
CAPTCHA handling, queue bypass, or anti-bot bypass is included.

## Setup

```sh
cd amazon-watcher
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Edit `config.py`: set `PRODUCT_URL` and `TARGET_ASIN`, review `MAX_PRICE` and
`MAX_SESSION_SPEND`. Run `python main.py` in a desktop session. Log in manually
in the persistent browser, then press Enter at the terminal. Dry-run exits when
conditions match without modifying the cart. Change `DRY_RUN = False` explicitly
to enable cart/checkout actions. Start with an empty active cart.

At checkout, review the product, seller, shipping, delivery date, payment method,
and final total. The checked cart subtotal does not establish shipping/tax or
other checkout charges: manually enforce the displayed spend ceiling before
submitting. Only a terminal answer of `y` records a purchase. The browser closes
after the answer, so complete your review/order first.

## Interrupted or unconfirmed attempts

State is written atomically to `data/state.json`; a kernel lock prevents concurrent
watchers using the same file. Keep the same state file and profile across runs.
Never delete purchase history to restart. If an attempt is interrupted or the
answer is not `y`, the purchase flag stays set. Review Amazon orders and the cart
manually. With the watcher stopped, if the order succeeded, add its ASIN to
`purchased_asins` and set `attempting_purchase` to false. If no order succeeded,
resolve any remaining cart item manually, then set only the flag to false.
Back up the state first. A missing state file represents first use; do not remove
it after purchases. Browser profiles contain sensitive login state: keep them private.

Selectors are centralized in `amazon.py`. Unsupported layouts and ambiguous
values stop checkout. Amazon markup can change; validate locally in dry-run.
The application does not change an unexpected cart. Login redirects, CAPTCHA,
and unknown checkout routes stop the attempt and retain its guard.

## Tests

```sh
python -m unittest discover -s tests -v
```

Tests use mocks and local state; they do not access Amazon or place orders.
Live Amazon selectors and authenticated checkout require local manual validation.
