import json
from dataclasses import dataclass
from pathlib import Path

PRICE_BOOK_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "service_desk_v1" / "price_book.json"


@dataclass(frozen=True)
class MethodPrice:
    price_book_version: str
    amount_micro_usd: int
    latency_ms: int


def load_price_book() -> dict:
    return json.loads(PRICE_BOOK_PATH.read_text(encoding="utf-8"))


def price_method(method: str) -> MethodPrice:
    book = load_price_book()
    entry = book["methods"].get(method)
    if entry is None:
        raise ValueError(f"method {method} is not in price book {book['version']}")
    amount = entry["amount_micro_usd"]
    latency = entry["latency_ms"]
    if not isinstance(amount, int) or amount < 0:
        raise ValueError("price book amount must be a non-negative integer micro-USD")
    if not isinstance(latency, int) or latency < 0:
        raise ValueError("price book latency must be a non-negative integer millisecond")
    return MethodPrice(book["version"], amount, latency)
