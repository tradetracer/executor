# TradeTracer Executor

Execute your [TradeTracer](https://tradetracer.ai) trading strategies with your own broker.

## Quick Start

```bash
docker run -p 5000:5000 -v tradetracer:/data tradetracer/executor
```

Open [http://localhost:5000](http://localhost:5000), enter your API key, click **Start**.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                      Your Computer                      │
│  ┌────────────────────────────────────────────────────┐ │
│  │                TradeTracer Executor                │ │
│  │                                                    │ │
│  │  1. Report fills    ──────────►  TradeTracer API   │ │
│  │  2. Receive orders  ◄──────────                    │ │
│  │  3. Execute orders  ──────────►  Your Broker       │ │
│  │  4. Repeat                                         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

1. **TradeTracer** runs your strategy and decides when to buy/sell
2. **Executor** receives orders and executes them with your broker
3. **Executor** reports fills back to TradeTracer
4. Repeat every tick (configurable interval)

## Configuration

All configuration is done through the web UI at `http://localhost:5000`:

| Field | Description |
|-------|-------------|
| **API Key** | Your TradeTracer API key (from Live tab) |
| **Adapter** | Your broker (Sandbox for testing, IBKR for real trading) |
| **Poll Interval** | Seconds between ticks (default: 60) |

## Adapters

### Sandbox (Paper Trading)

For testing without real money. Simulates a broker account with:
- Configurable starting cash
- Immediate order fills at specified price
- Position tracking

### Interactive Brokers

Connect to IBKR TWS or Gateway. Requires:
- TWS or IB Gateway running
- API connections enabled (Configure > API > Settings)
- Paper trading account recommended for testing

## Persistence

Configuration and pending transactions are stored in `/data`:

```bash
# Named volume (recommended)
docker run -v tradetracer:/data tradetracer/executor

# Bind mount to local folder
docker run -v ./my-data:/data tradetracer/executor
```

## Development

### Run from Source

```bash
git clone https://github.com/tradetracer/executor.git
cd executor
pip install -r requirements.txt
python -m web.app
```

### Run Tests

```bash
pip install pytest
pytest tests/ -v
```

### Project Structure

```
executor/
├── adapters/           # Broker integrations
│   ├── base.py         # Abstract adapter interface
│   ├── sandbox.py      # Paper trading
│   └── ibkr.py         # Interactive Brokers
├── executor/           # Core executor
│   ├── config.py       # Configuration
│   ├── main.py         # Main loop
│   └── transactions.py # Pending fills
├── web/                # Web UI
│   ├── app.py          # Flask app
│   ├── templates/      # HTML
│   └── static/         # CSS
└── tests/              # Test suite
```

## Adapter Interface

Adapters connect the executor to brokers. The interface:

| Method | Description |
|--------|-------------|
| `get_config_fields()` | Return UI configuration fields |
| `connect()` | Connect to broker, return True on success |
| `disconnect()` | Clean up connection |
| `execute_buy(symbol, shares, price)` | Execute buy, return fill details |
| `execute_sell(symbol, shares, price)` | Execute sell, return fill details |
| `get_quote(symbol)` | Return current quote or None |

### get_quote()

Returns current price data for a symbol. Used for:
- **Order execution** - accurate prices for buy/sell orders
- **Intraday trading** - real-time quotes between market open/close

```python
def get_quote(self, symbol: str) -> dict | None:
    return {
        "open": 185.00,
        "high": 187.50,
        "low": 184.25,
        "close": 186.50,  # Current/last price
        "volume": 1234567,
        "bid": 186.45,
        "ask": 186.55,
    }
```

**Return None** if unavailable (e.g., sandbox mode, market closed).
TradeTracer falls back to EOD cache.

### execute_buy() / execute_sell()

Returns fill details on success, error on failure:

```python
# Success
{"success": True, "fill_price": 186.50, "fill_shares": 100, "commission": 1.00}

# Failure
{"success": False, "error": "Insufficient funds"}
```

## Creating Custom Adapters

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
            return None  # TradeTracer uses EOD cache
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

Register in `adapters/__init__.py`:

```python
from .my_broker import MyBrokerAdapter
ADAPTERS["my_broker"] = MyBrokerAdapter
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [TradeTracer](https://tradetracer.ai) - Build and backtest trading strategies
- [Documentation](https://tradetracer.ai/docs/executor) - Full documentation
- [GitHub Issues](https://github.com/tradetracer/executor/issues) - Report bugs
