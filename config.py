from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import re

ROOT = Path(__file__).resolve().parent
PRODUCT_URL = ''  # e.g. https://www.amazon.co.jp/dp/B012345678
TARGET_ASIN = ''
MAX_PRICE = 7000  # Whole Japanese yen; this watcher supports amazon.co.jp only.
MAX_QUANTITY = 1
MAX_SESSION_SPEND = MAX_PRICE
CHECK_INTERVAL_SECONDS = 60
PROFILE_DIR = ROOT / 'browser-profile'
STATE_FILE = ROOT / 'data' / 'state.json'
DRY_RUN = True

@dataclass(frozen=True)
class Config:
    product_url: str = PRODUCT_URL
    target_asin: str = TARGET_ASIN
    max_price: int = MAX_PRICE
    max_quantity: int = MAX_QUANTITY
    max_session_spend: int = MAX_SESSION_SPEND
    check_interval_seconds: float = CHECK_INTERVAL_SECONDS
    profile_dir: Path = PROFILE_DIR
    state_file: Path = STATE_FILE
    dry_run: bool = DRY_RUN

    def validate(self):
        if type(self.max_quantity) is not int or self.max_quantity != 1:
            raise ValueError('MAX_QUANTITY must equal 1')
        for name, value in [('MAX_PRICE', self.max_price), ('MAX_SESSION_SPEND', self.max_session_spend)]:
            if type(value) is not int or value <= 0:
                raise ValueError(f'{name} must be a positive integer in yen')
        if not re.fullmatch(r'[A-Z0-9]{10}', self.target_asin):
            raise ValueError('TARGET_ASIN must contain 10 uppercase letters/digits')
        url = urlparse(self.product_url)
        if url.scheme != 'https' or url.hostname not in {'amazon.co.jp', 'www.amazon.co.jp'} or url.username or url.password:
            raise ValueError('PRODUCT_URL must be an HTTPS amazon.co.jp product URL')
        if not re.search(r'/(?:dp|gp/product)/' + self.target_asin + r'(?:/|$)', url.path):
            raise ValueError('PRODUCT_URL must identify TARGET_ASIN')
        if self.check_interval_seconds < 10:
            raise ValueError('CHECK_INTERVAL_SECONDS must be at least 10')
        if type(self.dry_run) is not bool:
            raise ValueError('DRY_RUN must be a boolean')
