import re
from urllib.parse import urlparse
from models import (SafetyError, WrongProduct, PriceNotFound, OutOfStock,
                    PriceExceeded, UnexpectedCartQuantity, UnexpectedCartTotal,
                    CheckoutUnavailable)

SELECTORS = {
    'price': ['#corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen', '#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen'],
    'asin': ['input#ASIN'],
    'quantity': ['select#quantity'],
    'add_to_cart': ['#add-to-cart-button', 'input[name="submit.add-to-cart"]'],
    'blocked': ['#captchacharacters', 'form[action*="validateCaptcha"]'],
    'cart_items': ['#sc-active-cart .sc-list-item[data-asin]'],
    'cart_price': ['.sc-product-price'],
    'cart_quantity': ['select[name="quantity"]', 'input[name="quantityBox"]', '[data-a-selector="value"]'],
    'cart_subtotal': ['#sc-subtotal-amount-activecart .a-size-medium'],
    'checkout': ['input[name="proceedToRetailCheckout"]'],
}

def parse_price(value):
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = re.fullmatch(r'(?:[¥￥]\s*)?((?:[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*))(?:\s*円)?', text)
    return int(match[1].replace(',', '')) if match else None

def visible_elements(root, key):
    for selector in SELECTORS[key]:
        elements = root.locator(selector)
        found = [elements.nth(i) for i in range(elements.count()) if elements.nth(i).is_visible()]
        if found:
            return found
    return []

def unique(root, key):
    elements = visible_elements(root, key)
    if len(elements) != 1:
        raise SafetyError(f'Cannot uniquely verify {key}')
    return elements[0]

def check_blocked(page):
    if visible_elements(page, 'blocked'):
        raise SafetyError('Amazon requires manual verification; automation stopped')

def verify_product(page, expected_asin):
    check_blocked(page)
    url = urlparse(page.url)
    match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)', url.path)
    if url.scheme != 'https' or url.hostname not in {'amazon.co.jp', 'www.amazon.co.jp'} or not match or match[1] != expected_asin:
        raise WrongProduct('Product URL does not identify target ASIN')
    for selector in SELECTORS['asin']:
        nodes = page.locator(selector)
        for i in range(nodes.count()):
            if nodes.nth(i).get_attribute('value') != expected_asin:
                raise WrongProduct('Product metadata disagrees with target ASIN')

def get_product_price(page):
    values = visible_elements(page, 'price')
    prices = [parse_price(v.inner_text()) for v in values]
    return prices[0] if prices and None not in prices and len(set(prices)) == 1 else None

def is_product_available(page):
    buttons = visible_elements(page, 'add_to_cart')
    return len(buttons) == 1 and buttons[0].is_enabled()

def enforce_price(price, maximum):
    if price is None:
        raise PriceNotFound('Price could not be verified')
    if price > maximum:
        raise PriceExceeded('Price exceeds configured maximum')

def add_one(page, config):
    quantities = visible_elements(page, 'quantity')
    if len(quantities) != 1:
        raise UnexpectedCartQuantity('Product quantity selector cannot be verified')
    quantities[0].select_option('1')
    if quantities[0].input_value() != '1':
        raise UnexpectedCartQuantity('Product quantity is not 1')
    verify_product(page, config.target_asin)
    if not is_product_available(page):
        raise OutOfStock('Product unavailable')
    price = get_product_price(page)
    enforce_price(price, config.max_price)
    unique(page, 'add_to_cart').click()
    return price

def validate_cart_values(asin, quantity, price, total, config):
    if asin != config.target_asin:
        raise WrongProduct('Unexpected ASIN in cart')
    if quantity != 1:
        raise UnexpectedCartQuantity('Cart quantity must equal 1')
    enforce_price(price, config.max_price)
    if total is None or total < price or total > config.max_session_spend:
        raise UnexpectedCartTotal('Cart subtotal is unknown or outside allowed spend')

def verify_cart(page, config):
    check_blocked(page)
    items = visible_elements(page, 'cart_items')
    if len(items) != 1:
        raise UnexpectedCartQuantity('Cart must contain exactly one active product')
    item = items[0]
    quantity_node = unique(item, 'cart_quantity')
    raw = quantity_node.input_value() if quantity_node.evaluate('(e) => ["INPUT", "SELECT"].includes(e.tagName)') else quantity_node.inner_text().strip()
    quantity = int(raw) if raw.isdigit() else None
    price = parse_price(unique(item, 'cart_price').inner_text())
    total = parse_price(unique(page, 'cart_subtotal').inner_text())
    validate_cart_values(item.get_attribute('data-asin'), quantity, price, total, config)
    return price, total

def open_checkout(page):
    unique(page, 'checkout').click()
    page.wait_for_load_state('domcontentloaded')
    check_blocked(page)
    url = urlparse(page.url)
    if url.hostname not in {'amazon.co.jp', 'www.amazon.co.jp'} or not url.path.startswith(('/gp/buy/', '/checkout/')):
        raise CheckoutUnavailable('Checkout not reached; review browser manually')
