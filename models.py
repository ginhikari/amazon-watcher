from dataclasses import dataclass, field
from enum import Enum, auto

class SafetyError(RuntimeError):
    """A condition required for safe checkout could not be verified."""

class WrongProduct(SafetyError): pass
class PriceNotFound(SafetyError): pass
class OutOfStock(SafetyError): pass
class PriceExceeded(SafetyError): pass
class UnexpectedCartQuantity(SafetyError): pass
class UnexpectedCartTotal(SafetyError): pass
class CheckoutUnavailable(SafetyError): pass

@dataclass
class PurchaseState:
    purchased_asins: list[str] = field(default_factory=list)
    attempting_purchase: bool = False

class Phase(Enum):
    STARTING = auto()
    WATCHING = auto()
    CONDITION_MET = auto()
    PURCHASE_LOCKED = auto()
    CART = auto()
    CART_VERIFIED = auto()
    CHECKOUT_READY = auto()
    MANUAL_CONFIRMATION = auto()
    PURCHASED = auto()
    EXIT = auto()

class StateMachine:
    def __init__(self):
        self.phase = Phase.STARTING

    def transition(self, target):
        edges = {
            Phase.STARTING: {Phase.WATCHING},
            Phase.WATCHING: {Phase.CONDITION_MET},
            Phase.CONDITION_MET: {Phase.PURCHASE_LOCKED},
            Phase.PURCHASE_LOCKED: {Phase.CART},
            Phase.CART: {Phase.CART_VERIFIED},
            Phase.CART_VERIFIED: {Phase.CHECKOUT_READY},
            Phase.CHECKOUT_READY: {Phase.MANUAL_CONFIRMATION},
            Phase.MANUAL_CONFIRMATION: {Phase.PURCHASED},
        }
        if target != Phase.EXIT and target not in edges.get(self.phase, set()):
            raise SafetyError(f'Invalid transition: {self.phase.name} -> {target.name}')
        if self.phase == Phase.EXIT:
            raise SafetyError('Application already exited')
        self.phase = target
