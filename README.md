# Amazon product watcher

Python 3.10+ on Windows 10/11, Linux, or macOS. Supports Amazon Japan, whole JPY, one ASIN,
quantity one. Dry-run is enabled by default. No final-order submission code,
CAPTCHA handling, queue bypass, or anti-bot bypass is included.

## Windows setup

Download and extract the [Windows branch ZIP](https://github.com/ginhikari/amazon-watcher/archive/refs/heads/windows.zip).
Install Python 3.10+ from python.org (including the Python launcher).
Open Command Prompt in the extracted folder and run:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m playwright install chromium
```

Edit `config.py` in a text editor to set the product URL, ASIN, and price limits.
Leave `DRY_RUN = True` for your first run. Double-click `run-windows.cmd`,
or run it from Command Prompt. It uses its own folder regardless of where it
is launched and keeps the window open after exit. No administrator access or
PowerShell execution-policy changes are needed.

Run tests with `.venv\Scripts\python.exe -m unittest discover -s tests -v`.
Use a local writable folder, not a network share or cloud-synced directory.
When migrating an existing watcher, stop it first and copy `data/state.json`
to this folder before starting; do not run both versions concurrently. Log in
again on Windows rather than copying a browser profile between operating systems.

Windows uses a nonblocking one-byte `msvcrt` lock; Linux/macOS uses `flock`.
Both retain the lock file and release the operating-system lock on process exit.
State files use UTF-8, flush to disk, and atomically replace the destination.
Directory fsync is performed only on Unix because Windows does not support it
through this API. Keep state backups to protect purchase history.

## Linux/macOS setup

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
