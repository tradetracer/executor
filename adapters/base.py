"""
Base adapter interface for broker integrations.

All broker adapters must inherit from BaseAdapter and implement
the required abstract methods. The executor loop calls these methods
at specific points during its tick cycle — adapters never drive the
flow themselves, they only respond when the executor invokes them.

The typical lifecycle is:

1. User clicks **Start** in the web UI.
2. The executor calls `connect()` once to establish a broker session.
3. On every tick, the executor calls `fetch_quote()` for each tracked
   symbol, then sends prices and pending transactions to TradeTracer.
4. TradeTracer responds with orders. The executor calls `execute_order()`,
   which dispatches to `execute_buy()` or `execute_sell()`.
5. When the user clicks **Stop**, the executor calls `disconnect()`.

Example:
    ```python
    from adapters.base import BaseAdapter

    class MyBrokerAdapter(BaseAdapter):
        @classmethod
        def get_config_fields(cls):
            return [{"name": "api_key", "type": "password", "required": True}]

        def connect(self) -> bool:
            self.client = MyBrokerClient(self.api_key)
            return self.client.is_connected()

        def disconnect(self) -> None:
            self.client.close()

        def execute_buy(self, symbol, shares, price):
            result = self.client.buy(symbol, shares)
            return {"success": True, "fill_price": result.price, ...}

        def execute_sell(self, symbol, shares, price):
            result = self.client.sell(symbol, shares)
            return {"success": True, "fill_price": result.price, ...}
    ```
"""

from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict


class ConfigField(TypedDict, total=False):
    """
    Configuration field for the web UI form.

    Displayed as a form input in the executor's web interface.
    The `name` must match an `__init__` parameter on the adapter.
    """

    name: str
    label: str
    type: Literal["text", "password", "number", "checkbox", "select"]
    required: bool
    default: Any
    options: list[dict[str, str]]


class Quote(TypedDict, total=False):
    """
    Price quote for a symbol.

    Returned by `fetch_quote()`. The executor maps this into the
    TradeTracer API format (`ohlcv` with `bid`/`ask`) before sending.
    All fields are optional — return whatever the broker provides.
    """

    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None
    bid: float | None
    ask: float | None


class FillResult(TypedDict, total=False):
    """
    Result of executing a buy or sell order.

    On success, `success` is True and `fill_price`, `fill_shares`,
    and `commission` are set. On failure, `success` is False and
    `error` describes what went wrong.
    """

    success: bool
    fill_price: float
    fill_shares: int
    commission: float
    error: str


class Order(TypedDict):
    """
    Order from the TradeTracer API.

    Passed to `execute_order()`, which dispatches to
    `execute_buy()` or `execute_sell()`.
    """

    order_id: str
    action: Literal["buy", "sell"]
    symbol: str
    volume: int
    price: float


class BaseAdapter(ABC):
    """
    Abstract base class for broker adapters.

    An adapter is the bridge between the executor and a specific broker.
    It knows how to connect to the broker, execute buy/sell orders, and
    optionally fetch real-time quotes. The executor owns the lifecycle —
    it calls `connect()` on start, `fetch_quote()` and `execute_buy()`/
    `execute_sell()` during each tick, and `disconnect()` on stop.

    Adapters should never raise exceptions for expected failures like
    insufficient funds or rejected orders. Instead, return a result dict
    with `"success": False` and an `"error"` message. The executor logs
    these and continues to the next order.
    """

    @classmethod
    @abstractmethod
    def get_config_fields(cls) -> list[ConfigField]:
        """
        Return configuration fields for the web UI.

        Called by the web UI when rendering the adapter configuration form.
        Each field describes one input the user needs to fill in to connect
        to this broker — for example, an API key, a hostname, or a port number.

        The web UI dynamically renders form inputs based on these field
        definitions. When the user saves, the values are stored in
        `config.json` under `adapter_config` and passed as keyword arguments
        to the adapter's `__init__()`. The `name` of each field must match
        an `__init__` parameter name so the value gets passed through.

        Returns:
            List of field configuration dicts. Each dict has `name`, `label`,
            `type` (text/password/number/checkbox/select), and optionally
            `required`, `default`, and `options`.

        Example:
            ```python
            @classmethod
            def get_config_fields(cls):
                return [
                    {
                        "name": "api_key",
                        "label": "API Key",
                        "type": "password",
                        "required": True
                    },
                    {
                        "name": "sandbox",
                        "label": "Paper Trading",
                        "type": "checkbox",
                        "default": True
                    },
                ]
            ```
        """

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the broker and verify the session is usable.

        Called exactly once when the user starts the executor. This is where
        the adapter should establish a network connection, authenticate with
        credentials, and verify that the session is ready to accept orders.

        If the connection fails — wrong credentials, broker offline, network
        error — return False. The executor will log the failure, stay in the
        stopped state, and the user can fix their config and try again.

        For adapters that don't need a persistent connection (like the sandbox
        adapter), this can simply return True.

        Returns:
            True if the connection was established and the adapter is ready
            to execute orders. False if something went wrong.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """
        Disconnect from the broker and clean up resources.

        Called once when the user stops the executor, or when the container
        shuts down (via SIGTERM/SIGINT). This is where the adapter should
        close network connections, cancel any pending requests, and release
        resources.

        This method should never raise exceptions. If the connection is
        already closed or was never established, it should silently do nothing.
        The executor calls this unconditionally during shutdown regardless of
        the adapter's current state.
        """

    @abstractmethod
    def execute_buy(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a buy order on the broker.

        Called by the executor when TradeTracer issues a buy order during a
        tick. The executor receives orders from the TradeTracer API response,
        then calls this method for each buy order. The adapter should submit
        the order to the broker and return the fill details.

        The `price` parameter is the ask price that TradeTracer used to size
        the order. Depending on your broker integration, you can use it as a
        limit price, a sanity check against slippage, or ignore it entirely
        and use a market order. The fill price you report back is what
        TradeTracer records as the actual execution price.

        On success, you must return all four fields: `success`, `fill_price`,
        `fill_shares`, and `commission`. The executor builds a transaction
        from these and reports it to TradeTracer on the next tick.

        On failure (insufficient funds, symbol not found, broker rejected the
        order), return `"success": False` with an `"error"` message. Do not
        raise exceptions — the executor logs the error and moves on to the
        next order.

        Args:
            symbol: Stock ticker symbol (e.g., `"AAPL"`, `"TSLA"`). Always
                uppercase, as provided by TradeTracer.
            shares: Number of shares to buy. Always a positive integer.
                This is the net consolidated volume from TradeTracer — if
                a strategy called `buy(50)` then `sell(20)` in the same
                tick, you receive `shares=30`.
            price: The ask price TradeTracer used when generating this
                order. Use as a limit price or for slippage validation.

        Returns:
            A dict with `success`, `fill_price`, `fill_shares`, and `commission`
            on success, or `success` and `error` on failure.

        Example:
            ```python
            # Success
            {"success": True, "fill_price": 186.50, "fill_shares": 100, "commission": 1.00}

            # Failure
            {"success": False, "error": "Insufficient funds"}
            ```
        """

    @abstractmethod
    def execute_sell(self, symbol: str, shares: int, price: float) -> FillResult:
        """
        Execute a sell order on the broker.

        Called by the executor when TradeTracer issues a sell order during a
        tick. Behaves identically to `execute_buy()` but for the sell side.

        The `price` parameter is the bid price that TradeTracer used to
        calculate expected proceeds. As with buys, you can use it as a limit,
        a sanity check, or ignore it.

        Args:
            symbol: Stock ticker symbol (e.g., `"AAPL"`, `"TSLA"`). Always
                uppercase, as provided by TradeTracer.
            shares: Number of shares to sell. Always a positive integer.
                The executor only sends sell orders for positions the strategy
                holds, but the adapter should still validate against its own
                position tracking in case of desync.
            price: The bid price TradeTracer used when generating this
                order. Use as a limit price or for slippage validation.

        Returns:
            Same format as `execute_buy()` — a dict with `success`, `fill_price`,
            `fill_shares`, and `commission` on success, or `success` and `error`
            on failure.
        """

    @abstractmethod
    def fetch_quote(self, symbol: str, eod_last_price: float | None) -> Quote | None:
        """
        Fetch a price quote for a symbol.

        Called by the executor at the start of every tick, once per tracked
        symbol. The executor sends the returned quotes to TradeTracer, which
        uses them for intraday strategy evaluation and order pricing.

        The `eod_last_price` is the most recent end-of-day close price from
        TradeTracer's data. Adapters can use it however they need — for
        example, the sandbox adapter uses it to simulate intraday price
        movement via random walk. Broker adapters like IBKR can ignore it
        and fetch real-time data from the broker instead.

        The EOD price also serves as a sanity check — users can compare
        their broker's price against TradeTracer's data to verify accuracy.
        TradeTracer's data is not always correct, and this transparency
        helps users catch discrepancies.

        Args:
            symbol: Stock ticker symbol (e.g., `"AAPL"`). Always uppercase.
            eod_last_price: Last known EOD close price from TradeTracer,
                or None if not yet available (first tick).

        Returns:
            A Quote dict with price fields, or None if unavailable.

        Example:
            ```python
            # Broker adapter — fetch real data, ignore EOD
            def fetch_quote(self, symbol, eod_last_price):
                ticker = self.client.get_ticker(symbol)
                return {"close": ticker.last, "bid": ticker.bid, "ask": ticker.ask}

            # Sandbox adapter — simulate from EOD
            def fetch_quote(self, symbol, eod_last_price):
                if not eod_last_price:
                    return None
                price = eod_last_price * (1 + random.uniform(-0.005, 0.005))
                return {"close": price, "bid": price - 0.01, "ask": price + 0.01}
            ```
        """

    def execute_order(self, order: Order) -> FillResult:
        """
        Dispatch an order from TradeTracer to the appropriate handler.

        This is the method the executor loop actually calls. It reads the
        `action` field from the order dict and routes to `execute_buy()` or
        `execute_sell()`. You do not need to override this method — it
        exists as a convenience so the executor doesn't need to branch on
        order type itself.

        The order dict comes directly from the TradeTracer API response.
        Each order represents a consolidated net trade for one symbol from
        one worker during one tick. TradeTracer handles consolidation — if
        a strategy called `buy(50)` then `sell(20)`, you receive a single
        order with `action: "buy"` and `volume: 30`.

        Args:
            order: Order dict from the TradeTracer API response with keys:

                - `action` (str): `"buy"` or `"sell"`.
                - `symbol` (str): Stock ticker symbol, uppercase.
                - `volume` (int): Number of shares (always positive).
                - `price` (float): Ask price for buys, bid price for sells.
                - `order_id` (str): UUID that links this order to the
                  transaction reported back on the next tick.

        Returns:
            The result dict from `execute_buy()` or `execute_sell()`.

        Example:
            ```python
            order = {
                "action": "buy",
                "symbol": "AAPL",
                "volume": 100,
                "price": 186.50,
                "order_id": "abc-123"
            }
            result = adapter.execute_order(order)
            ```
        """
        if order["action"] == "buy":
            return self.execute_buy(order["symbol"], order["volume"], order["price"])
        else:
            return self.execute_sell(order["symbol"], order["volume"], order["price"])
