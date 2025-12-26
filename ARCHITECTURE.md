# Trading Algorithm Architecture

## Overview

This document describes the architecture and operation of the automated trading system. The system connects to the Schwab API to execute trades based on signals from the PRT (Pattern Recognition Technology) strategy.

## System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MAIN PROGRAM                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────┐         ┌──────────────────────┐                  │
│  │   SUPERVISOR LOOP    │ ──────> │    TRADING LOOP      │                  │
│  │   (Market Closed)    │ <────── │    (Market Open)     │                  │
│  └──────────────────────┘         └──────────────────────┘                  │
│         │                                   │                                │
│         ▼                                   ▼                                │
│  ┌──────────────────────┐         ┌──────────────────────┐                  │
│  │  Token Refresh       │         │  Strategy Execution  │                  │
│  │  Market Monitoring   │         │  Order Placement     │                  │
│  │  Pre-Open Prep       │         │  Position Monitoring │                  │
│  └──────────────────────┘         └──────────────────────┘                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                                   │
├──────────────────────┬──────────────────────┬───────────────────────────────┤
│   Schwab Trader API  │   Schwab Market API  │   Godel Terminal              │
│   - Orders           │   - Quotes           │   - MOST Scanner              │
│   - Positions        │   - Market Hours     │   - PRT Analysis              │
│   - Account Info     │   - Bid/Ask Data     │                               │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
```

## Loop Architecture

### 1. Supervisor Loop (Market Closed)

Runs when the market is closed or not yet ready for trading.

**Responsibilities:**
- Checks market status every **15 minutes**
- Refreshes API tokens every **29 minutes** (tokens expire in 30 min)
- Monitors active positions if any exist
- Prepares for market open (increases check frequency to 1 minute when close to open)

**State Transitions:**
- Returns `'trade'` → Transitions to Trading Loop
- Returns `'closed'` → Market closed for day, continues supervisor loop

### 2. Trading Loop (Market Open)

Runs when market has been open for `MARKET_OPEN_DELAY_MINUTES` until `MARKET_CLOSE_BUFFER_MINUTES` before close.

**Responsibilities:**
- Executes trading strategy (PRT)
- Places trades via Schwab API
- Monitors positions for profit targets and stop losses
- Closes positions after `TRADE_HOLD_MINUTES` or at market close

**Trade Lifecycle:**
```
┌───────────────┐     ┌──────────────┐     ┌────────────────┐     ┌───────────┐
│ Get Strategy  │────>│ Place Order  │────>│ Monitor Trade  │────>│ Close     │
│ Signals       │     │ (Limit/Mkt)  │     │ (SL/TP/Time)   │     │ Position  │
└───────────────┘     └──────────────┘     └────────────────┘     └───────────┘
```

## Key Constants

| Constant | Default | Description |
|----------|---------|-------------|
| `TRADE_HOLD_MINUTES` | 10 | How long to hold trades before auto-closing |
| `MARKET_OPEN_DELAY_MINUTES` | 1 | Wait after market open before trading |
| `MARKET_CLOSE_BUFFER_MINUTES` | 5 | Stop trading this many minutes before close |
| `SUPERVISOR_CHECK_INTERVAL_MINUTES` | 15 | How often supervisor checks market status |
| `TOKEN_REFRESH_INTERVAL_MINUTES` | 29 | How often to refresh API tokens |
| `TAKE_PROFIT_PERCENT` | 1.5 | Close position if profit reaches this % |
| `USE_LIMIT_ORDERS` | True | Use dynamic limit orders vs market orders |
| `LIMIT_ORDER_TIMEOUT_SECONDS` | 10 | Time before adjusting unfilled limit order |

## Order Execution

### Dynamic Limit Orders

When `USE_LIMIT_ORDERS=True`, the system uses intelligent limit orders:

1. **Initial Price Calculation:**
   - Gets current bid/ask spread
   - BUY orders: Start at mid-price + small offset
   - SELL orders: Start at mid-price - small offset

2. **Price Adjustment Loop:**
   - Wait `LIMIT_ORDER_TIMEOUT_SECONDS` for fill
   - If not filled, cancel and adjust price:
     - BUY: Increase price by `LIMIT_ORDER_ADJUSTMENT_PERCENT`
     - SELL: Decrease price by `LIMIT_ORDER_ADJUSTMENT_PERCENT`
   - Repeat up to `LIMIT_ORDER_MAX_ATTEMPTS` times

3. **Fallback:**
   - After max attempts, falls back to market order

### Order Types Used

- **LIMIT**: Entry orders (with dynamic adjustment)
- **STOP**: Stop-loss orders (2% from entry)
- **MARKET**: Fallback and closing orders

## File Structure

```
godel_api/
├── algo_loop.py          # Main trading logic (this file)
├── PRT_Strategy.py       # Trading strategy implementation
├── token_manager.py      # Token refresh management
├── token_storage.py      # Token persistence
├── close_all_positions.py# Emergency position closer
├── config.py             # API keys and credentials (git-ignored)
├── config-example.py     # Example config file
├── trade_journal.json    # Trade history and P&L tracking
└── requirements.txt      # Python dependencies
```

## Classes

### Trade

Represents a single trade with tracking information.

**Key Fields:**
- `ticker`: Stock symbol
- `action`: LONG or SHORT
- `quantity`: Number of shares
- `time_placed`: When trade was opened
- `entry_price`: Execution price
- `stop_loss_price`: Stop loss trigger price
- `take_profit_price`: Take profit target
- `is_closed`: Whether trade is complete

**Key Methods:**
- `get_age_minutes()`: How long trade has been open
- `should_close()`: Whether trade is old enough to close
- `calculate_stop_loss_price()`: Compute stop price from entry

### AccountsTrading

Manages Schwab API connection and trade execution.

**Key Methods:**
- `create_order()`: Place any order type
- `create_dynamic_limit_order()`: Intelligent limit order with adjustment
- `create_stop_loss_order()`: Create stop-loss order for trade
- `get_quote()` / `get_bid_ask()`: Get current prices
- `check_stop_loss_orders()`: Check if stops were triggered
- `check_profit_targets()`: Check if profit targets hit
- `close_all_positions()`: Emergency close all

## Error Handling

### API Errors
- **401 Unauthorized**: Force token refresh and retry
- **429 Rate Limited**: Exponential backoff (2s, 4s, 8s, 16s, 32s)
- **Connection Errors**: Retry with backoff

### Market Errors
- **Market Closed**: Transition to supervisor loop
- **No Valid Trades**: Wait 1 minute and retry
- **Order Rejected**: Log error and continue

## Monitoring

### Logging
Uses `loguru` for structured logging. Key log messages:
- `📈`: Market status
- `✅`: Success
- `❌`: Error
- `⚠️`: Warning
- `🔄`: Refresh/update
- `💤`: Sleeping/waiting
- `🎯`: Profit target hit

### Webhook Notifications
Trade statistics sent to ntfy.sh webhook:
- Win rate
- Total P&L
- Average win/loss

### Dashboard
Real-time data sent to:
- Local server (port 4131)
- Remote server (herstrom.com)

## Getting Started

1. **Initialize Tokens:**
   ```bash
   python get_OG_tokens.py
   ```

2. **Configure Credentials:**
   ```bash
   cp config-example.py config.py
   # Edit config.py with your credentials
   ```

3. **Run the Algorithm:**
   ```bash
   python algo_loop.py
   ```

4. **Emergency Stop:**
   - Press `Ctrl+C` to gracefully shutdown
   - Run `python close_all_positions.py` for emergency close

## Development Notes

### Adding New Features
1. Constants go at top of `algo_loop.py`
2. Add new methods to `AccountsTrading` class
3. Update `Trade` class if tracking new data
4. Update this documentation

### Testing
- Use `DEBUG_MODE=true` environment variable for verbose logging
- Test with small position sizes first
- Monitor trade_journal.json for execution quality

### Common Issues
- **Tokens expired**: Run `get_OG_tokens.py` to re-authenticate
- **Rate limiting**: Increase delays between API calls
- **Positions not closing**: Check stop-loss order status in logs

