# Custom Adapters

How to connect the executor to your broker.

## Interface

Inherit from [`BaseAdapter`](reference/base-adapter.md) and implement all abstract methods:

```python
from adapters.base import BaseAdapter

class MyBrokerAdapter(BaseAdapter):
    def __init__(self, api_key: str = "", **kwargs):
        self.api_key = api_key
        self.client = None

    @classmethod
    def get_config_fields(cls):
        return [
            {"name": "api_key", "label": "API Key", "type": "password", "required": True},
        ]

    def connect(self) -> bool:
        self.client = MyBrokerClient(self.api_key)
        return self.client.is_connected()

    def disconnect(self) -> None:
        if self.client:
            self.client.close()

    def execute_buy(self, symbol: str, shares: int, price: float) -> dict:
        result = self.client.buy(symbol, shares, limit=price)
        if result.filled:
            return {
                "success": True,
                "fill_price": result.price,
                "fill_shares": result.shares,
                "commission": result.commission,
            }
        return {"success": False, "error": result.error}

    def execute_sell(self, symbol: str, shares: int, price: float) -> dict:
        result = self.client.sell(symbol, shares, limit=price)
        if result.filled:
            return {
                "success": True,
                "fill_price": result.price,
                "fill_shares": result.shares,
                "commission": result.commission,
            }
        return {"success": False, "error": result.error}

    def get_quote(self, symbol: str) -> dict | None:
        quote = self.client.get_quote(symbol)
        if not quote:
            return None
        return {
            "open": quote.open,
            "high": quote.high,
            "low": quote.low,
            "close": quote.last,
            "volume": quote.volume,
            "bid": quote.bid,
            "ask": quote.ask,
        }
```

## Register

Add your adapter to `adapters/__init__.py`:

```python
from .my_broker import MyBrokerAdapter
ADAPTERS["my_broker"] = MyBrokerAdapter
```

## Return Formats

### execute_buy / execute_sell

```python
# Success
{"success": True, "fill_price": 186.50, "fill_shares": 100, "commission": 1.00}

# Failure
{"success": False, "error": "Insufficient funds"}
```

### get_quote

```python
# Available
{"open": 185.0, "high": 187.5, "low": 184.25, "close": 186.5, "volume": 1234567, "bid": 186.45, "ask": 186.55}

# Unavailable
None
```

Return `None` if quotes aren't available. TradeTracer falls back to its EOD cache.
