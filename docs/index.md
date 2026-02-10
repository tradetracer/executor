# TradeTracer Executor

Execute your [TradeTracer](https://tradetracer.ai) trading strategies with your own broker.

---

## How It Works

```
You                          TradeTracer
 │                               │
 │  ┌──────────────────────┐     │
 │  │     Executor         │     │
 │  │                      │     │
 │  │  1. Report fills  ───────► │
 │  │  2. Receive orders ◄────── │
 │  │  3. Execute orders ──► Broker
 │  │  4. Repeat           │     │
 │  └──────────────────────┘     │
```

1. **TradeTracer** runs your strategy and decides when to buy/sell
2. **Executor** receives orders and executes them with your broker
3. **Executor** reports fills back to TradeTracer
4. Repeat every tick

## Quick Start

```bash
docker run -p 5000:5000 -v tradetracer:/data tradetracer/executor
```

Open [http://localhost:5000](http://localhost:5000), enter your API key, click **Start**.

## Adapters

| Adapter | Description |
|---------|-------------|
| **Sandbox** | Paper trading for testing, no real money |
| **IBKR** | Interactive Brokers via TWS/Gateway |

Need a different broker? See [Custom Adapters](custom-adapters.md).
