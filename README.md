# 📈 Farmer (Working Name)

A modular, event-driven trading framework for developing, testing, and deploying systematic futures trading strategies.

This project is designed to support multiple strategy types, with reusable building blocks such as:

- Static price levels
- Order flow (delta, volume)
- Time-based and event-based signals
- Custom indicators and analytics

The goal is to create a clean, extensible system where strategies can be developed once and reused across:

- Backtesting
- Simulation / optimization
- Live trading or signal dispatch

## 🚀 Overview

This framework processes tick-level market data and allows strategies to:

1. Analyze historical context (e.g. levels, indicators)
2. React to incoming ticks in real time
3. Emit structured trade signals

It is designed around deterministic, event-driven execution, making it suitable for both research and production systems.

## 🧱 Core Architecture
```
Tick Data → Engine → Strategy → Signal → (Execution / Dispatch)
```

### Key Components

#### 1. **Tick Engine**
- Streams tick data (CSV or future live feeds)
- Processes ticks sequentially
- Calls strategy logic on every tick

#### 2. **Strategy Modules**
- Encapsulate trading logic
- Maintain internal state
- Emit signals when conditions are met
- Fully pluggable and configurable

#### 3. **Backtest Runner**
- Loads YAML configuration
- Instantiates strategies with parameters
- Runs strategies against historical data
- Outputs results (PnL, logs, diagnostics)

#### 4. **Data Sources**
- CSV (historical tick data)
- API (TopstepX / ProjectX)
- Live market feeds

## 🧠 Strategy Design Philosophy

Strategies are modular, self-contained units that operate on tick data.

### Minimal Interface
```python
class Strategy:
    def check(self, tick: Tick) -> Optional[Signal]:
        ...
```

Each strategy:
- Receives ticks
- Maintains internal state
- Emits signals when appropriate

This design enables:
- Easy swapping of strategies
- Independent testing
- Clean separation of concerns
- Reuse across backtest and live systems

## 🔌 Plug-and-Play Strategy Modules

Strategies are defined via configuration and instantiated dynamically.

Example:
```yaml
strategy:
  name: "static_bounce_cl"
  aggregation_params:
    lookback_days: 10
    candle_length: 5
    unit: "minutes"
  strategy_params:
    kind: "static_bounce"
    tick_size: 0.01
    reward_ticks: 20
    risk_ticks: 10
```

You can:
- Swap strategies without changing the engine
- Run multiple strategies with different parameters
- Perform grid searches and parameter sweeps

## 🧰 Strategy Building Blocks

This framework includes reusable components that strategies can leverage, such as:
- Static Level Calculations
  - Derived from historical price action
  - Used for support/resistance detection
- Delta Windows
  - Rolling order flow measurement
  - Tracks aggressive buying vs selling over time
- Tick Aggregation
  - Build candles or custom structures from tick data

These are not tied to any single strategy. They are tools that can be combined in different ways.

## 🔄 Backtest → Live Parity

The core goal is to write a strategy module once and run it anywhere. The same strategy module can be used for backtesting via historical data, simulations for parameter tuning and optimization, or realitime signal generation / trade execution.

## 🧪 Development Workflow

1. Define strategy and parameter classes + parameters in YAML
2. Run backtest via:
```bash
python backtest.py --config config.yaml --name my_strategy
```
3. Review results and iterate on strategy logic

## ⚠️ Disclaimer

This is an experimental trading framework and not financial advice. Use at your own risk.
