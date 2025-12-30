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

### Trading Constants
| Constant | Default | Description |
|----------|---------|-------------|
| `TRADE_HOLD_MINUTES` | 20 | How long to hold trades before auto-closing |
| `MARKET_OPEN_DELAY_MINUTES` | 1 | Wait after market open before trading |
| `MARKET_CLOSE_BUFFER_MINUTES` | 5 | Stop trading this many minutes before close |
| `STOP_LOSS_PERCENT` | 2.0 | Stop loss percentage from entry price |
| `TAKE_PROFIT_PERCENT` | 0.4 | Take profit percentage from entry price (0.4% = $2 on $500 position) |

### Supervisor Loop Constants
| Constant | Default | Description |
|----------|---------|-------------|
| `SUPERVISOR_CHECK_INTERVAL_MINUTES` | 15 | How often supervisor checks market status |
| `TOKEN_REFRESH_INTERVAL_MINUTES` | 29 | How often to refresh API tokens |
| `MARKET_OPEN_PREP_MINUTES` | 30 | Start preparing this many minutes before market open |
| `MAIN_LOOP_RETRY_DELAY_SECONDS` | 60 | Wait time before retrying after error in main loop |

### Order Execution Constants
| Constant | Default | Description |
|----------|---------|-------------|
| `USE_LIMIT_ORDERS` | True | Use dynamic limit orders vs market orders |
| `LIMIT_ORDER_TIMEOUT_SECONDS` | 10 | Time before adjusting unfilled limit order |
| `LIMIT_ORDER_MAX_ATTEMPTS` | 3 | Maximum price adjustments before using market order |
| `LIMIT_ORDER_PRICE_OFFSET_PERCENT` | 0.02 | Initial offset from quote price (2 basis points) |
| `LIMIT_ORDER_ADJUSTMENT_PERCENT` | 0.05 | Price adjustment per attempt (5 basis points) |
| `USE_LIMIT_ORDERS_FOR_CLOSE` | True | Use limit orders when closing positions |
| `CLOSE_LIMIT_ORDER_TIMEOUT_SECONDS` | 5 | Timeout for closing limit orders |
| `CLOSE_LIMIT_ORDER_MAX_ATTEMPTS` | 2 | Max attempts for closing before market fallback |

### API Rate Limiting Constants
| Constant | Default | Description |
|----------|---------|-------------|
| `ORDER_DELAY_SECONDS` | 0.3 | Delay between placing orders |
| `POST_ENTRY_DELAY_SECONDS` | 0.8 | Delay after entry before placing OCO/stop loss |
| `ORDER_CHECK_DELAY_SECONDS` | 0.2 | Delay between checking order status |
| `API_MAX_RETRIES` | 5 | Maximum retry attempts for API calls |
| `API_RETRY_DELAY_SECONDS` | 2.0 | Initial delay between retries (exponential backoff) |

### Dashboard Constants
| Constant | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_LOCAL_PORT` | 4131 | Local development server port |
| `DASHBOARD_ENDPOINTS` | Array | Endpoints for sending live trading data |

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

### OCO Orders (One-Cancels-Other)

The system uses OCO orders to combine stop-loss and take-profit in a single order:

1. **Structure:**
   - Take profit: LIMIT order at `TAKE_PROFIT_PERCENT` (0.4%) above/below entry
   - Stop loss: STOP order at `STOP_LOSS_PERCENT` (2.0%) from entry
   - When one fills, the other is automatically canceled

2. **Benefits:**
   - Single order ID for both exit conditions
   - Automatic cancellation prevents double-fills
   - Reduces API calls and order management complexity

3. **Placement:**
   - Created immediately after entry order fills
   - Uses `POST_ENTRY_DELAY_SECONDS` (0.8s) to ensure entry is processed

### Order Types Used

- **LIMIT**: Entry orders (with dynamic adjustment)
- **OCO**: Combined stop-loss and take-profit orders
- **STOP**: Stop-loss orders (within OCO)
- **MARKET**: Fallback and closing orders

## File Structure

```
godel_api/
├── algo_loop.py          # Main trading logic
├── PRT_Strategy.py       # Trading strategy implementation
├── token_manager.py      # Token refresh management
├── token_storage.py      # Token persistence
├── close_all_positions.py# Emergency position closer
├── calculate_port_stats.py # Portfolio statistics calculator
├── get_OG_tokens.py      # Initial token authentication
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
- `exit_price`: Price when trade was closed
- `stop_loss_price`: Stop loss trigger price
- `take_profit_price`: Take profit target
- `profit_loss`: Calculated P&L in dollars
- `profit_loss_percent`: Calculated P&L as percentage
- `is_closed`: Whether trade is complete
- `order_id`: Entry order ID
- `stop_loss_order_id`: OCO order ID (contains both stop and take profit)
- `close_order_id`: Order ID used to close position
- `exit_order_type`: Type of exit ('OCO_STOP_LOSS', 'OCO_TAKE_PROFIT', 'TIME_CLOSE', etc.)
- `prt_data`: PRT analysis data (edge, prob_up, mean, p10, p90, etc.)

**Key Methods:**
- `get_age_minutes()`: How long trade has been open
- `should_close()`: Whether trade is old enough to close
- `calculate_stop_loss_price()`: Compute stop price from entry
- `calculate_take_profit_price()`: Compute take profit price from entry
- `mark_closed()`: Mark trade as closed with exit details
- `update_from_api_response()`: Update trade from API response

### AccountsTrading

Manages Schwab API connection and trade execution.

**Key Methods:**
- `create_order()`: Place any order type with retry logic
- `create_dynamic_limit_order()`: Intelligent limit order with adjustment
- `create_oco_order()`: Create OCO order combining stop-loss and take-profit
- `get_quote()` / `get_bid_ask()`: Get current prices
- `get_quote_full()`: Get full quote data with bid/ask spread
- `get_order_details()`: Get order status and details
- `get_fill_price_from_order()`: Extract fill price from order details
- `check_stop_loss_orders()`: Check if stops were triggered
- `check_profit_targets()`: Check if profit targets hit
- `verify_and_force_close_all_positions()`: Position safeguard to ensure all positions closed
- `get_positions()`: Get all open positions from account
- `get_all_open_orders()`: Get all open orders
- `close_order()`: Cancel an existing order
- `close_all_positions()`: Emergency close all positions

## Position Safeguard

The `verify_and_force_close_all_positions()` method provides comprehensive protection against edge cases:

**When It Runs:**
- Before placing new trades (prevents partial fills from OCO orders)
- After trade monitoring completes
- At end of trading day
- On program exit (signal handler)
- On manual trigger

**What It Does:**
1. **Cancel all open orders** - Prevents orphaned orders
2. **Check actual positions** - Uses Schwab API to verify positions
3. **Close all positions** - Uses market orders to close any remaining positions
4. **Verify closure** - Confirms all positions are closed with retries
5. **Clear active_trades** - Syncs internal state with actual positions

**Edge Cases Handled:**
- Partial fills from OCO orders
- Orders that appear filled but positions remain
- Network errors during order placement
- Race conditions between order status and positions

## Error Handling

### API Errors
- **401 Unauthorized**: Force token refresh and retry
- **429 Rate Limited**: Exponential backoff (2s, 4s, 8s, 16s, 32s)
- **Connection Errors**: Retry with backoff
- **SSL Errors**: Retry with delays, log diagnostic info

### Market Errors
- **Market Closed**: Transition to supervisor loop
- **No Valid Trades**: Wait 10 seconds and retry
- **Order Rejected**: Log error and continue
- **Fill Price Not Found**: Use quote price as fallback, log warning

### Position Errors
- **Position Mismatch**: Position safeguard verifies and corrects
- **Orphaned Orders**: Safeguard cancels all open orders before new trades

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
- Local server (port 4131) - `http://localhost:4131/api/trading_data`
- Remote server - `https://herstrom.com/api/trading_data`

**Dashboard Data Includes:**
- Account value and buying power
- Current positions (symbol, quantity, P/L)
- Active trades (entry price, age, status)
- Trade statistics (win rate, total P&L)
- Portfolio value over time

**Security:**
- Uses `DASHBOARD_SECURITY_HASH` header for authentication
- Prevents unauthorized updates to dashboard

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
- **Fill price not found**: Check DEBUG logs for order structure - may need to update extraction logic
- **SSL errors**: Temporary network issues - system retries automatically
- **Position mismatch**: Position safeguard should handle automatically on next cycle

### Debug Mode
Set `ALGO_DEBUG=true` environment variable for verbose logging:
- Full API request/response logging
- Detailed order structure dumps
- Diagnostic information for troubleshooting

