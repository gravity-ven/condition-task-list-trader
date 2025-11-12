# Condition Task List Trader

An autonomous trading system that waits for user-provided "Condition Task List" inputs before executing trades. The system monitors market data in real-time, tracks condition completion like a todo list, and automatically executes trades when ALL conditions are met.

## Features

- **Natural Language Condition Input**: Just say "Condition Task List: RSI < 30, price above 50-day SMA, volume spike"
- **Visual Todo-List Interface**: Track condition completion with ✅ and ⏳ indicators
- **Real-Time Market Monitoring**: Continuous evaluation of technical indicators
- **Risk Management**: Built-in position sizing, stop loss, and profit targets
- **Automated Trade Execution**: Trades execute only when all conditions are satisfied

## Quick Start

1. **Run the system**:
```bash
cd condition_task_list_trader
python main.py
```

2. **Provide your conditions**:
```
Condition Task List: RSI < 30, price < 150, volume > 2000000
```

3. **Watch the magic**: The system will monitor and show:
```
Status: 0/3 conditions met
📋 Added 3 tasks:
   [⏳] RSI < 30
   [⏳] Price < 150
   [⏳] Volume > 2000000
```

4. **Automatic execution**: When all conditions are ✅, the system executes a trade

## Example Conditions

**Technical Indicators**:
- `"RSI < 30"` - Oversold condition
- `"price > 50-day SMA"` - Above moving average
- `"MACD > 0"` - Buy signal
- `"volume > 2x average"` - Volume confirmation
- `"Bollinger Bands < lower band"` - Price below lower band

**Operators Supported**:
- `>`, `<`, `>=`, `<=,` `above`, `below`, `over`, `under`
- `spike` (for volume), `drop` (for price)

## System Architecture

```
User Input → Condition Parser → Conditions Matcher → Market Data Feed
     ↓                                           ↓
   Dashboard ← Trade Executor ← Risk Management ← Market Analysis
```

## Components

1. **Condition Parser**: Translates natural language into structured trading criteria
2. **Conditions Matcher**: Real-time evaluation against market data
3. **Market Data Simulator**: Provides realistic market scenarios (replace with real feeds)
4. **Trade Executor**: Handles position sizing and trade execution
5. **Visual Dashboard**: Todo-list style condition tracking
6. **Risk Management**: Position limits, stop loss, profit targets

## Configuration

Risk parameters can be adjusted in `trade_executor.py`:
```python
max_position_size = 10000.0      # Max position value
max_daily_loss = 1000.0         # Daily loss limit  
stop_loss_percentage = 0.02     # 2% stop loss
take_profit_percentage = 0.05   # 5% take profit
max_risk_per_trade = 0.01       # 1% per trade
```

## Demo Mode

Try the demo to see the system in action:
```
> demo
```

This runs a scenario where conditions are met one by one, showing how the system tracks completion and executes automatically.

## Next Steps

- **Real Market Data**: Connect to Alpha Vantage, Polygon.io, or broker APIs
- **Broker Integration**: Execute real trades through Alpaca, Interactive Brokers, etc.
- **Multiple Symbols**: Track conditions across different instruments
- **Advanced Indicators**: Add more technical analysis indicators
- **Strategy Backtesting**: Test condition sets against historical data
- **Alert System**: Webhook/email notifications for condition completion

## Disclaimer

This system is for educational and demonstration purposes. For live trading, ensure proper risk management, backtesting, and compliance with regulations. Always test extensively with paper trading before deploying real capital.

## License

MIT License - See LICENSE file for details
