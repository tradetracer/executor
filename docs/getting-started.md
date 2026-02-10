# Getting Started

## Docker (Recommended)

```bash
docker run -p 5000:5000 -v tradetracer:/data tradetracer/executor
```

Open [http://localhost:5000](http://localhost:5000) to configure.

## Configuration

| Field | Description |
|-------|-------------|
| **API Key** | Your TradeTracer API key (from the Live tab) |
| **Adapter** | Broker to use (`sandbox` or `ibkr`) |
| **Poll Interval** | Seconds between ticks (default: 60) |

## From Source

```bash
git clone https://github.com/tradetracer/executor.git
cd executor
pip install -r requirements.txt
python -m web.app
```

## Persistence

Config and pending transactions are stored in `/data`:

```bash
# Named volume (recommended)
docker run -v tradetracer:/data tradetracer/executor

# Bind mount
docker run -v ./my-data:/data tradetracer/executor
```

## Running Tests

```bash
pytest tests/ -v
```
