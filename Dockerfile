# TradeTracer Executor
# Execute trading strategies with your broker

FROM python:3.12-slim

LABEL maintainer="TradeTracer <info@tradetracer.ai>"
LABEL description="Connect TradeTracer to your broker"

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY adapters/ adapters/
COPY executor/ executor/
COPY web/ web/

# Create data directory
RUN mkdir -p /data

# Expose web UI port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/status', timeout=2)" || exit 1

# Run web UI (which manages the executor)
CMD ["gunicorn", "web.app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "2"]
