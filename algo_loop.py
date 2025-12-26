'''
Main algo loop - handles Schwab API connection and trade execution.
Strategy logic is handled by PRT_Strategy module.
https://www.reddit.com/r/Schwab/comments/1c2ioe1/the_unofficial_guide_to_charles_schwabs_trader/
'''
from godel_core import GodelTerminalController
import time
from config import GODEL_USERNAME, GODEL_PASSWORD
import requests
import pandas
from loguru import logger
from PRT_Strategy import run_strategy
from datetime import datetime, timedelta
import pytz
import json
import atexit
import signal
import os
from pathlib import Path

'''
#TODO
make scwab api work
make logger for trade journal
make system to track trades 
make system to abandon all trades
make abort button
'''

# Global constants
TRADE_HOLD_MINUTES = 10  # How long to hold trades before automatically closing them
MARKET_OPEN_DELAY_MINUTES = 1  # How many minutes after market opens before starting to trade
MARKET_CLOSE_BUFFER_MINUTES = 5  # Stop trading this many minutes before market close
TRADE_JOURNAL_FILE = "trade_journal.json"  # File to store trade results
NTFY_WEBHOOK_URL = "https://ntfy.sh/hayden_algo_api"  # Webhook URL for sending trade statistics
TAKE_PROFIT_PERCENT = 1.5  # Close position if profit reaches this percentage

# Debug mode flag - set to True for verbose API response logging
DEBUG_MODE = os.getenv("ALGO_DEBUG", "false").lower() in ("true", "1", "yes")


class Trade:
    """
    Represents a trade with initial info and API response details.
    Tracks trades and handles automatic closing after TRADE_HOLD_MINUTES.
    """
    def __init__(self, ticker: str, action: str, quantity: int):
        """
        Initialize a trade with initial calculated values.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'RGTI')
            action: Trade action - 'LONG' (buy) or 'SHORT' (sell short)
            quantity: Number of shares
        """
        self.ticker = ticker
        self.action = action.upper()  # Ensure uppercase: LONG or SHORT
        self.quantity = quantity
        self.time_placed = datetime.now(pytz.timezone('US/Eastern'))
        self.order_id = None
        self.order_status = None
        self.api_response = None  # Full API response from order placement
        self.is_closed = False
        self.close_order_id = None
        self.close_time = None
        self.entry_price = None  # Price when trade was opened
        self.exit_price = None  # Price when trade was closed
        self.profit_loss = None  # Calculated P&L in dollars
        self.profit_loss_percent = None  # Calculated P&L as percentage
        self.stop_loss_order_id = None  # Order ID for stop loss order
        self.stop_loss_price = None  # Stop loss price (2% from entry)
        self.take_profit_price = None  # Take profit price (1.5% from entry)
        
    def update_from_api_response(self, api_response: dict):
        """
        Update trade with details from Schwab API response.
        
        Args:
            api_response: Full JSON response from order placement API
        """
        self.api_response = api_response
        # Extract order ID from response (location may vary based on API response structure)
        if 'orderId' in api_response:
            self.order_id = api_response['orderId']
        elif 'order_id' in api_response:
            self.order_id = api_response['order_id']
        
        if 'status' in api_response:
            self.order_status = api_response['status']
        elif 'orderStatus' in api_response:
            self.order_status = api_response['orderStatus']
        
        # Try to extract fill price from immediate response if available
        # (may not be available immediately for market orders)
        fill_price = None
        if 'orderLegCollection' in api_response and api_response['orderLegCollection']:
            for leg in api_response['orderLegCollection']:
                if 'executionDetails' in leg and leg['executionDetails']:
                    executions = leg['executionDetails']
                    if executions:
                        total_price = 0
                        total_quantity = 0
                        for execution in executions:
                            if 'price' in execution and 'quantity' in execution:
                                total_price += execution['price'] * execution['quantity']
                                total_quantity += execution['quantity']
                        if total_quantity > 0:
                            fill_price = total_price / total_quantity
                            break
                if 'averagePrice' in leg:
                    fill_price = leg['averagePrice']
                    break
                if 'filledPrice' in leg:
                    fill_price = leg['filledPrice']
                    break
        
        if fill_price is None:
            if 'averageFillPrice' in api_response:
                fill_price = api_response['averageFillPrice']
            elif 'filledPrice' in api_response:
                fill_price = api_response['filledPrice']
            elif 'averagePrice' in api_response:
                fill_price = api_response['averagePrice']
        
        if fill_price is not None:
            self.entry_price = float(fill_price)
            logger.info(f"Extracted fill price from order response: ${self.entry_price:.4f}")
    
    def get_age_minutes(self) -> float:
        """Get the age of the trade in minutes."""
        if self.time_placed:
            age = datetime.now(pytz.timezone('US/Eastern')) - self.time_placed
            return age.total_seconds() / 60
        return 0.0
    
    def should_close(self) -> bool:
        """Check if trade should be closed (TRADE_HOLD_MINUTES old)."""
        return self.get_age_minutes() >= TRADE_HOLD_MINUTES and not self.is_closed
    
    def get_close_action(self) -> str:
        """
        Get the action needed to close this trade.
        LONG positions are closed with SELL, SHORT positions are closed with BUY_TO_COVER.
        """
        if self.action == 'LONG':
            return 'SELL'
        elif self.action == 'SHORT':
            return 'BUY_TO_COVER'  # Must use BUY_TO_COVER to close short positions
        else:
            return None
    
    def mark_closed(self, close_order_id: str = None, exit_price: float = None):
        """
        Mark trade as closed and calculate P&L.
        
        Args:
            close_order_id: Order ID for the closing order
            exit_price: Price at which the trade was closed
        """
        self.is_closed = True
        self.close_order_id = close_order_id
        self.close_time = datetime.now(pytz.timezone('US/Eastern'))
        if exit_price is not None:
            self.exit_price = exit_price
            self._calculate_pnl()
    
    def _calculate_pnl(self):
        """Calculate profit/loss for the trade."""
        if self.entry_price is None or self.exit_price is None:
            return
        
        if self.action == 'LONG':
            # LONG: profit = (exit_price - entry_price) * quantity
            self.profit_loss = (self.exit_price - self.entry_price) * self.quantity
            self.profit_loss_percent = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        elif self.action == 'SHORT':
            # SHORT: profit = (entry_price - exit_price) * quantity
            self.profit_loss = (self.entry_price - self.exit_price) * self.quantity
            self.profit_loss_percent = ((self.entry_price - self.exit_price) / self.entry_price) * 100
    
    def calculate_stop_loss_price(self, entry_price: float, stop_loss_percent: float = 2.0) -> float:
        """
        Calculate stop loss price based on entry price and action type.
        Complies with Schwab API requirements: 2 decimals for prices >= $1, 4 decimals for prices < $1.
        
        Args:
            entry_price: Entry price of the trade
            stop_loss_percent: Stop loss percentage (default 2.0%)
            
        Returns:
            float: Stop loss price rounded to appropriate decimal places
        """
        if self.action == 'LONG':
            # For LONG: stop loss is below entry price (2% down)
            stop_price = entry_price * (1 - stop_loss_percent / 100)
        elif self.action == 'SHORT':
            # For SHORT: stop loss is above entry price (2% up)
            stop_price = entry_price * (1 + stop_loss_percent / 100)
        else:
            return None
        
        # Schwab API requirement: 2 decimals for prices >= $1, 4 decimals for prices < $1
        if stop_price >= 1.0:
            return round(stop_price, 2)
        else:
            return round(stop_price, 4)
    
    def calculate_take_profit_price(self, entry_price: float, take_profit_percent: float = 1.5) -> float:
        """
        Calculate take profit price based on entry price and action type.
        
        Args:
            entry_price: Entry price of the trade
            take_profit_percent: Take profit percentage (default 1.5%)
            
        Returns:
            float: Take profit price rounded to appropriate decimal places
        """
        if self.action == 'LONG':
            # For LONG: take profit is above entry price (1.5% up)
            profit_price = entry_price * (1 + take_profit_percent / 100)
        elif self.action == 'SHORT':
            # For SHORT: take profit is below entry price (1.5% down)
            profit_price = entry_price * (1 - take_profit_percent / 100)
        else:
            return None
        
        # Round to 2 decimals for prices >= $1, 4 decimals for prices < $1
        if profit_price >= 1.0:
            return round(profit_price, 2)
        else:
            return round(profit_price, 4)
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary for JSON storage."""
        return {
            'ticker': self.ticker,
            'action': self.action,
            'quantity': self.quantity,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'profit_loss': self.profit_loss,
            'profit_loss_percent': self.profit_loss_percent,
            'time_placed': self.time_placed.isoformat() if self.time_placed else None,
            'close_time': self.close_time.isoformat() if self.close_time else None,
            'order_id': self.order_id,
            'close_order_id': self.close_order_id,
            'stop_loss_order_id': self.stop_loss_order_id,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'is_winner': self.profit_loss > 0 if self.profit_loss is not None else None
        }
    
    def __repr__(self):
        return (f"Trade(ticker={self.ticker}, action={self.action}, quantity={self.quantity}, "
                f"time_placed={self.time_placed.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"age_minutes={self.get_age_minutes():.1f}, is_closed={self.is_closed})")


class AccountsTrading:
    def __init__(self):
        # Initialize token manager for automatic token refresh
        from token_manager import get_token_manager
        self.token_manager = get_token_manager()
        self.account_hash_value = None
        # Trader API base URL - for account and order operations
        self.base_url = "https://api.schwabapi.com/trader/v1"
        # Market Data API base URL - for market hours and market data
        self.market_data_base_url = "https://api.schwabapi.com/marketdata/v1"
        # Track active trades
        self.active_trades: list[Trade] = []
        # Cache headers to avoid frequent token requests
        self._headers_cache = None
        self._headers_cache_time = None
        self._headers_cache_ttl = 60  # Cache headers for 1 minute (refresh more often to catch token updates)
        self._update_headers()
        self.get_account_number_hash_value()
    
    def _update_headers(self, force: bool = False):
        """
        Update headers with current access token.
        Uses caching to avoid frequent token requests.
        
        Args:
            force: If True, force update even if cache is valid
        """
        import time
        current_time = time.time()
        
        # Use cached headers if available and not expired
        if not force and self._headers_cache and self._headers_cache_time:
            age = current_time - self._headers_cache_time
            if age < self._headers_cache_ttl:
                self.headers = self._headers_cache
                return
        
        try:
            access_token = self.token_manager.get_access_token()
            self.headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
            # Cache the headers
            self._headers_cache = self.headers.copy()
            self._headers_cache_time = current_time
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise

    def get_account_number_hash_value(self):
        # Ensure headers are up to date before making request
        self._update_headers()
        response = requests.get(
            self.base_url + f"/accounts/accountNumbers", headers=self.headers
        )
        if response.status_code != 200:
            logger.error(f"Failed to get account numbers: {response.status_code} - {response.text}")
            raise RuntimeError(f"API request failed: {response.status_code}")
        response_frame = pandas.json_normalize(response.json())
        self.account_hash_value = response_frame["hashValue"].iloc[0]
    
    def get_account_info(self) -> dict:
        """
        Get account information including balance, equity, buying power, etc.
        
        Returns:
            dict: Account information or None if unavailable
        """
        try:
            self._update_headers()
            
            if not self.account_hash_value:
                logger.error("Account hash value not set")
                return {}
            
            url = f"{self.base_url}/accounts/{self.account_hash_value}"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                account_data = response.json()
                if DEBUG_MODE:
                    logger.debug(f"Account info retrieved: {json.dumps(account_data, indent=2)}")
                return account_data
            else:
                logger.error(f"Failed to get account info: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return {}
    
    def get_positions(self) -> list:
        """
        Get current account positions.
        
        Returns:
            list: List of position dictionaries or empty list if unavailable
        """
        try:
            self._update_headers()
            
            if not self.account_hash_value:
                logger.error("Account hash value not set")
                return []
            
            url = f"{self.base_url}/accounts/{self.account_hash_value}/positions"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                positions_data = response.json()
                # Response might be a list or an object with positions array
                if isinstance(positions_data, list):
                    return positions_data
                elif isinstance(positions_data, dict) and 'positions' in positions_data:
                    return positions_data['positions']
                else:
                    return []
            elif response.status_code == 404:
                # 404 means no positions, which is a valid state
                if DEBUG_MODE:
                    logger.debug("No positions found (404) - this is normal if account has no open positions")
                return []
            else:
                logger.warning(f"Failed to get positions: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    def is_market_open_for_15_minutes(self) -> tuple[bool, str]:
        """
        Check if the stock market is open and has been open for at least MARKET_OPEN_DELAY_MINUTES.
        
        Returns:
            tuple: (is_open_for_delay_min, message)
                - is_open_for_delay_min: True if market is open and has been open for >= MARKET_OPEN_DELAY_MINUTES
                - message: Descriptive message about market status
        """
        try:
            # Ensure headers are up to date before making request
            self._update_headers()
            
            # Get current date in Eastern timezone (US market timezone)
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            current_date = now_eastern.strftime('%Y-%m-%d')
            
            # Schwab Market Data API market hours endpoint
            # Endpoint: GET /markets/hours (uses Market Data API, not Trader API)
            # Parameters: markets (comma-separated list), date (YYYY-MM-DD)
            market_hours_url = f"{self.market_data_base_url}/markets/hours"
            params = {
                'markets': 'EQUITY',
                'date': current_date
            }
            
            logger.debug(f"Requesting market hours from {market_hours_url} with params {params}")
            response = requests.get(market_hours_url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                error_msg = f"Failed to get market hours: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                return False, error_msg
            
            data = response.json()
            logger.debug(f"Market hours response: {data}")
            
            # Parse the response structure
            # Actual Schwab API response format:
            # {
            #   "equity": {
            #     "EQ": {
            #       "date": "2025-12-23",
            #       "marketType": "EQUITY",
            #       "product": "EQ",
            #       "isOpen": true,
            #       "sessionHours": {
            #         "preMarket": [{"start": "2025-12-23T07:00:00-05:00", "end": "2025-12-23T09:30:00-05:00"}],
            #         "regularMarket": [{"start": "2025-12-23T09:30:00-05:00", "end": "2025-12-23T16:00:00-05:00"}],
            #         "postMarket": [{"start": "2025-12-23T16:00:00-05:00", "end": "2025-12-23T20:00:00-05:00"}]
            #       }
            #     }
            #   }
            # }
            equity_data = None
            
            # Try different response structure patterns
            if 'equity' in data and isinstance(data['equity'], dict):
                # Check if there's an 'EQ' key (or other product keys)
                if 'EQ' in data['equity']:
                    equity_data = data['equity']['EQ']
                else:
                    # Try to get the first key if structure is different
                    for key in data['equity']:
                        equity_data = data['equity'][key]
                        break
            elif 'EQUITY' in data and isinstance(data['EQUITY'], dict):
                if 'equity' in data['EQUITY']:
                    equity_data = data['EQUITY']['equity']
                elif 'EQ' in data['EQUITY']:
                    equity_data = data['EQUITY']['EQ']
                else:
                    equity_data = data['EQUITY']
            elif isinstance(data, dict):
                # Check if top-level has the fields we need
                if 'isOpen' in data:
                    equity_data = data
            
            if not equity_data or not isinstance(equity_data, dict):
                logger.error(f"Unexpected market hours response structure: {data}")
                return False, f"Could not parse market hours response: {data}"
            
            # Check if market is open
            is_open = equity_data.get('isOpen', False)
            
            # If market is closed, return early
            if not is_open:
                return False, "Market is currently closed"
            
            # Get market open and close times from sessionHours
            session_hours = equity_data.get('sessionHours', {})
            regular_market = session_hours.get('regularMarket', [])
            
            # Extract regular market session times
            if regular_market and len(regular_market) > 0:
                regular_session = regular_market[0]
                open_time_str = regular_session.get('start', '2025-12-23T09:30:00-05:00')
                close_time_str = regular_session.get('end', '2025-12-23T16:00:00-05:00')
            else:
                # Fallback to default times if sessionHours structure is unexpected
                logger.warning("Could not find regularMarket session hours, using defaults")
                open_time_str = '09:30'
                close_time_str = '16:00'
            
            # Parse open time (usually ISO format from API)
            try:
                if isinstance(open_time_str, str) and 'T' in open_time_str:
                    # ISO format datetime (e.g., "2025-12-23T09:30:00-05:00")
                    # Handle both Z and timezone offset formats
                    open_time_str_clean = open_time_str.replace('Z', '+00:00')
                    open_time = datetime.fromisoformat(open_time_str_clean)
                    if open_time.tzinfo is None:
                        open_time = eastern.localize(open_time)
                    else:
                        open_time = open_time.astimezone(eastern)
                elif isinstance(open_time_str, str) and ':' in open_time_str and len(open_time_str.split(':')) == 2:
                    # HH:MM format (e.g., "09:30")
                    hour, minute = map(int, open_time_str.split(':'))
                    open_time = eastern.localize(datetime(
                        now_eastern.year,
                        now_eastern.month,
                        now_eastern.day,
                        hour,
                        minute
                    ))
                else:
                    raise ValueError(f"Unexpected open time format: {open_time_str}")
            except Exception as e:
                logger.warning(f"Could not parse open time '{open_time_str}', using default 09:30 ET: {e}")
                open_time = eastern.localize(datetime(
                    now_eastern.year,
                    now_eastern.month,
                    now_eastern.day,
                    9, 30
                ))
            
            # Calculate time difference from market open
            time_diff = now_eastern - open_time
            minutes_open = time_diff.total_seconds() / 60
            
            # Also check if we're past market close
            try:
                if isinstance(close_time_str, str) and 'T' in close_time_str:
                    close_time_str_clean = close_time_str.replace('Z', '+00:00')
                    close_time = datetime.fromisoformat(close_time_str_clean)
                    if close_time.tzinfo is None:
                        close_time = eastern.localize(close_time)
                    else:
                        close_time = close_time.astimezone(eastern)
                elif isinstance(close_time_str, str) and ':' in close_time_str and len(close_time_str.split(':')) == 2:
                    hour, minute = map(int, close_time_str.split(':'))
                    close_time = eastern.localize(datetime(
                        now_eastern.year,
                        now_eastern.month,
                        now_eastern.day,
                        hour,
                        minute
                    ))
                else:
                    close_time = None
                
                if close_time and now_eastern > close_time:
                    return False, f"Market closed at {close_time_str}"
            except Exception as e:
                logger.debug(f"Could not parse close time '{close_time_str}': {e}")
            
            # Check if market has been open for at least MARKET_OPEN_DELAY_MINUTES
            if minutes_open < 0:
                # Market hasn't opened yet today
                open_time_display = open_time.strftime('%H:%M') if isinstance(open_time, datetime) else open_time_str
                return False, f"Market opens at {open_time_display} ET (opens in {abs(int(minutes_open))} minutes)"
            elif minutes_open >= MARKET_OPEN_DELAY_MINUTES:
                # Market is open and has been open for at least MARKET_OPEN_DELAY_MINUTES
                return True, f"Market is open (open for {int(minutes_open)} minutes)"
            else:
                # Market is open but hasn't been open for MARKET_OPEN_DELAY_MINUTES yet
                return False, f"Market is open but has only been open for {int(minutes_open)} minutes (need {MARKET_OPEN_DELAY_MINUTES})"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error checking market hours: {e}")
            return False, f"Network error: {str(e)}"
        except Exception as e:
            logger.error(f"Error checking market hours: {e}")
            import traceback
            traceback.print_exc()
            return False, f"Error checking market hours: {str(e)}"

    def create_stop_loss_order(self, trade: Trade, entry_price: float, stop_loss_percent: float = 2.0) -> dict:
        """
        Create a stop loss order for an existing trade.
        
        Args:
            trade: Trade object to create stop loss for
            entry_price: Entry price of the trade
            stop_loss_percent: Stop loss percentage (default 2.0%)
            
        Returns:
            dict: API response with stop loss order details
        """
        # Calculate stop loss price
        stop_price = trade.calculate_stop_loss_price(entry_price, stop_loss_percent)
        if stop_price is None:
            logger.error(f"Could not calculate stop loss price for {trade.ticker}")
            return {'error': 'Could not calculate stop loss price'}
        
        trade.stop_loss_price = stop_price
        
        # Determine stop loss instruction based on action
        if trade.action == 'LONG':
            # LONG: Stop loss is a SELL order at stop price
            stop_instruction = 'SELL'
        elif trade.action == 'SHORT':
            # SHORT: Stop loss is a BUY_TO_COVER order at stop price
            stop_instruction = 'BUY_TO_COVER'
        else:
            logger.error(f"Unknown action for stop loss: {trade.action}")
            return {'error': f'Unknown action: {trade.action}'}
        
        # Create stop loss order payload
        stop_order_payload = {
            "orderType": "STOP",  # Stop order type
            "stopPrice": stop_price,
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": stop_instruction,
                "quantity": trade.quantity,
                "instrument": {
                    "symbol": trade.ticker,
                    "assetType": "EQUITY"
                }
            }]
        }
        
        logger.info(f"Creating stop loss order for {trade.ticker} {trade.action}: "
                   f"Stop price ${stop_price:.4f} ({stop_loss_percent}% from entry ${entry_price:.4f})")
        
        response = self.create_order(stop_order_payload)
        
        if 'orderId' in response:
            trade.stop_loss_order_id = response['orderId']
            logger.info(f"Stop loss order created: Order ID {trade.stop_loss_order_id}")
        
        return response
    
    def create_order(self, order_payload: dict, max_retries: int = 5, retry_delay: float = 2.0) -> dict:
        """
        Create an order via Schwab API.
        Includes retry logic with exponential backoff for rate limiting (429 errors).
        
        Args:
            order_payload: Order payload dictionary
            max_retries: Maximum number of retry attempts for 429 errors (default 5)
            retry_delay: Initial delay between retries in seconds (default 2.0, exponential backoff)
            
        Returns:
            dict: API response with order details
        """
        self._update_headers()
        
        # Add Content-Type header for POST requests
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json"
        
        url = f"{self.base_url}/accounts/{self.account_hash_value}/orders"
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=order_payload,
                    timeout=10
                )
                
                if response.status_code in [200, 201]:
                    # Order created successfully
                    response_data = response.json() if response.text else {}
                    
                    # Check for order ID in response headers (Location header)
                    if 'Location' in response.headers:
                        location = response.headers['Location']
                        order_id = location.split('/')[-1]
                        response_data['orderId'] = order_id
                    
                    # Log full API response only in debug mode
                    if DEBUG_MODE:
                        logger.debug(f"Order API Response (Status {response.status_code}):")
                        logger.debug(f"  Full response: {json.dumps(response_data, indent=2)}")
                        if response.headers:
                            logger.debug(f"  Response headers: {dict(response.headers)}")
                    else:
                        logger.info(f"Order created successfully (Status {response.status_code}, Order ID: {response_data.get('orderId', 'N/A')})")
                    
                    return response_data
                elif response.status_code == 429:
                    # Rate limited - retry with exponential backoff
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                        logger.warning(f"Rate limited (429) creating order (attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)
                        # Update headers before retry (token might have expired)
                        self._update_headers()
                        headers = self.headers.copy()
                        headers["Content-Type"] = "application/json"
                        continue
                    else:
                        error_msg = f"Failed to create order: 429 Too Many Requests (after {max_retries} attempts)"
                        if response.text:
                            error_msg += f" - {response.text}"
                        logger.error(error_msg)
                        return {'error': error_msg, 'status_code': 429}
                else:
                    # Other error status codes - don't retry
                    error_msg = f"Failed to create order: {response.status_code}"
                    if response.text:
                        error_msg += f" - {response.text}"
                    logger.error(error_msg)
                    return {'error': error_msg, 'status_code': response.status_code}
                    
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Retry on connection errors
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Connection error creating order (attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                    self._update_headers()
                    headers = self.headers.copy()
                    headers["Content-Type"] = "application/json"
                    continue
                else:
                    logger.error(f"Error creating order after {max_retries} attempts: {e}")
                    return {'error': str(e)}
            except Exception as e:
                logger.error(f"Error creating order: {e}")
                return {'error': str(e)}
        
        return {'error': f'Failed after {max_retries} attempts'}
    
    def get_order_details(self, order_id: str, update_headers: bool = True, max_retries: int = 3, retry_delay: float = 1.0) -> dict:
        """
        Get order details including execution/fill price from Schwab API.
        Includes retry logic for SSL/connection errors.
        
        Args:
            order_id: Order ID to get details for
            update_headers: If True, update headers before making request (default True)
            max_retries: Maximum number of retry attempts for SSL/connection errors (default 3)
            retry_delay: Initial delay between retries in seconds (default 1.0, exponential backoff)
            
        Returns:
            dict: API response with order details including fill information
        """
        if update_headers:
            self._update_headers()
        
        url = f"{self.base_url}/accounts/{self.account_hash_value}/orders/{order_id}"
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    order_data = response.json()
                    if DEBUG_MODE:
                        logger.debug(f"Order details for {order_id}: {json.dumps(order_data, indent=2)}")
                    return order_data
                elif response.status_code == 401:
                    # Token likely expired/stale - force header refresh and retry
                    if attempt < max_retries - 1:
                        logger.warning(f"401 Unauthorized for order {order_id} (attempt {attempt + 1}/{max_retries}), refreshing token...")
                        self._update_headers(force=True)  # Force refresh to get new token
                        time.sleep(retry_delay)
                        continue
                    else:
                        error_msg = f"Failed to get order details for {order_id}: 401 Unauthorized (after {max_retries} attempts)"
                        if response.text:
                            error_msg += f" - {response.text}"
                        logger.error(error_msg)
                        return {'error': error_msg, 'status_code': 401}
                else:
                    error_msg = f"Failed to get order details for {order_id}: {response.status_code}"
                    if response.text:
                        error_msg += f" - {response.text}"
                    logger.error(error_msg)
                    return {'error': error_msg, 'status_code': response.status_code}
                    
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                # Retry on SSL/connection errors
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"SSL/connection error getting order details for {order_id} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    # Update headers for retry (token might have expired)
                    if update_headers:
                        self._update_headers()
                else:
                    logger.error(f"Error getting order details for {order_id} after {max_retries} attempts: {e}")
                    return {'error': str(e)}
            except Exception as e:
                logger.error(f"Error getting order details for {order_id}: {e}")
                return {'error': str(e)}
        
        return {'error': f'Failed after {max_retries} attempts'}
    
    def get_fill_price_from_order(self, order_id: str, max_retries: int = 5, retry_delay: float = 1.0, update_headers: bool = True) -> float | None:
        """
        Get the actual fill/execution price from an order by checking its status.
        Retries until order is filled or max retries reached.
        
        Args:
            order_id: Order ID to check
            max_retries: Maximum number of times to check order status
            retry_delay: Seconds to wait between retries
            update_headers: If True, update headers before making request (default True)
            
        Returns:
            float: Fill price if found, None otherwise
        """
        if not order_id:
            return None
            
        for attempt in range(max_retries):
            order_details = self.get_order_details(order_id, update_headers=update_headers)
            
            if 'error' in order_details:
                if attempt < max_retries - 1:
                    logger.debug(f"Error getting order details (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(retry_delay)
                    continue
                return None
            
            # Try to extract fill price from order details
            # Schwab API structure may vary, try multiple possible paths
            fill_price = None
            
            # Check for orderLegCollection with executionDetails
            if 'orderLegCollection' in order_details and order_details['orderLegCollection']:
                for leg in order_details['orderLegCollection']:
                    if 'executionDetails' in leg and leg['executionDetails']:
                        # Get average fill price from executions
                        executions = leg['executionDetails']
                        if executions:
                            # Calculate average fill price from all executions
                            total_price = 0
                            total_quantity = 0
                            for execution in executions:
                                if 'price' in execution and 'quantity' in execution:
                                    total_price += execution['price'] * execution['quantity']
                                    total_quantity += execution['quantity']
                            if total_quantity > 0:
                                fill_price = total_price / total_quantity
                                break
                    
                    # Alternative: check for averagePrice or filledPrice
                    if 'averagePrice' in leg:
                        fill_price = leg['averagePrice']
                        break
                    if 'filledPrice' in leg:
                        fill_price = leg['filledPrice']
                        break
            
            # Check top-level fields
            if fill_price is None:
                if 'averageFillPrice' in order_details:
                    fill_price = order_details['averageFillPrice']
                elif 'filledPrice' in order_details:
                    fill_price = order_details['filledPrice']
                elif 'averagePrice' in order_details:
                    fill_price = order_details['averagePrice']
            
            if fill_price is not None:
                logger.info(f"Found fill price for order {order_id}: ${fill_price:.4f}")
                return float(fill_price)
            
            # Check if order is still pending
            order_status = order_details.get('status', '').upper()
            if order_status in ['FILLED', 'CANCELED', 'REJECTED', 'EXPIRED']:
                # Order is in final state but no fill price found
                logger.warning(f"Order {order_id} is in state {order_status} but no fill price found")
                break
            
            # Order not yet filled, wait and retry
            if attempt < max_retries - 1:
                logger.debug(f"Order {order_id} not yet filled (attempt {attempt + 1}/{max_retries}), waiting...")
                time.sleep(retry_delay)
        
        logger.warning(f"Could not get fill price for order {order_id} after {max_retries} attempts")
        return None

    def close_order(self, order_id: str) -> dict:
        """
        Cancel/close an existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            dict: API response
        """
        self._update_headers()
        
        url = f"{self.base_url}/accounts/{self.account_hash_value}/orders/{order_id}"
        
        try:
            response = requests.delete(url, headers=self.headers)
            
            if response.status_code in [200, 204]:
                logger.info(f"Order {order_id} cancelled successfully")
                return {'success': True, 'order_id': order_id}
            else:
                error_msg = f"Failed to cancel order {order_id}: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                return {'error': error_msg, 'status_code': response.status_code}
                
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return {'error': str(e)}
    
    def check_stop_loss_orders(self):
        """
        Check if any stop loss orders have been triggered (filled).
        If a stop loss was triggered, mark the trade as closed.
        Includes rate limiting to avoid overwhelming the API with rapid requests.
        """
        # Update headers once at the start for all order checks
        self._update_headers()
        
        first_check = True
        for trade in self.active_trades:
            if trade.is_closed or not trade.stop_loss_order_id:
                continue
            
            # Check stop loss order status (headers already updated at start of function)
            # Add small delay between requests to avoid overwhelming API (except for first request)
            if not first_check:
                time.sleep(0.2)  # 200ms delay between order checks to prevent rate limiting
            first_check = False
            
            stop_order_details = self.get_order_details(trade.stop_loss_order_id, update_headers=False)
            if 'error' not in stop_order_details:
                order_status = stop_order_details.get('status', '').upper()
                
                # If stop loss order is filled, the trade was closed by stop loss
                if order_status == 'FILLED':
                    # Try multiple methods to get fill price
                    exit_price = None
                    
                    # Method 1: Try to extract from order details directly
                    if 'orderLegCollection' in stop_order_details and stop_order_details['orderLegCollection']:
                        for leg in stop_order_details['orderLegCollection']:
                            # Check executionDetails first (most accurate)
                            if 'executionDetails' in leg and leg['executionDetails']:
                                executions = leg['executionDetails']
                                if executions:
                                    total_price = 0
                                    total_quantity = 0
                                    for execution in executions:
                                        if 'price' in execution and 'quantity' in execution:
                                            total_price += execution['price'] * execution['quantity']
                                            total_quantity += execution['quantity']
                                    if total_quantity > 0:
                                        exit_price = total_price / total_quantity
                                        break
                            # Check averagePrice
                            if exit_price is None and 'averagePrice' in leg:
                                exit_price = leg['averagePrice']
                                break
                            # Check filledPrice
                            if exit_price is None and 'filledPrice' in leg:
                                exit_price = leg['filledPrice']
                                break
                    
                    # Method 2: Check top-level fields
                    if exit_price is None:
                        if 'averageFillPrice' in stop_order_details:
                            exit_price = stop_order_details['averageFillPrice']
                        elif 'filledPrice' in stop_order_details:
                            exit_price = stop_order_details['filledPrice']
                        elif 'averagePrice' in stop_order_details:
                            exit_price = stop_order_details['averagePrice']
                    
                    # Method 3: Use stop_loss_price as fallback (better than nothing)
                    if exit_price is None and trade.stop_loss_price is not None:
                        exit_price = trade.stop_loss_price
                        logger.warning(f"Could not get exact fill price for stop loss {trade.stop_loss_order_id}, using stop loss price ${exit_price:.4f} as fallback")
                    
                    # Mark trade as closed regardless - we have at least a reasonable price
                    if exit_price is not None:
                        logger.warning(f"Stop loss triggered for {trade.ticker} at ${exit_price:.4f}")
                        trade.mark_closed(close_order_id=trade.stop_loss_order_id, exit_price=exit_price)
                        save_trade_to_journal(trade)
                        
                        if trade.profit_loss is not None:
                            pnl_sign = "+" if trade.profit_loss >= 0 else ""
                            logger.info(f"  Stop Loss P&L: {pnl_sign}${trade.profit_loss:.2f} ({pnl_sign}{trade.profit_loss_percent:.2f}%)")
                    else:
                        # Last resort: mark closed with entry price (shouldn't happen, but prevents infinite loop)
                        logger.error(f"Stop loss order {trade.stop_loss_order_id} filled but could not determine exit price. Using entry price as fallback.")
                        if trade.entry_price is not None:
                            trade.mark_closed(close_order_id=trade.stop_loss_order_id, exit_price=trade.entry_price)
                            save_trade_to_journal(trade)
                elif order_status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    # Stop loss was cancelled/rejected, which is fine if we're closing manually
                    if DEBUG_MODE:
                        logger.debug(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} is {order_status}")
                    elif order_status == 'REJECTED':
                        # Log rejected orders even in non-debug mode as they indicate a problem
                        status_desc = stop_order_details.get('statusDescription', 'Unknown reason')
                        logger.warning(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} was REJECTED: {status_desc}")
        
        # Remove closed trades from active list
        self.active_trades = [t for t in self.active_trades if not t.is_closed]
    
    def check_profit_targets(self):
        """
        Check if any active trades have hit their profit target.
        If profit target is reached, cancel stop loss and close position.
        Includes rate limiting to avoid overwhelming the API.
        """
        first_check = True
        for trade in self.active_trades:
            if trade.is_closed or trade.take_profit_price is None or trade.entry_price is None:
                continue
            
            # Rate limit API calls (except for first request)
            if not first_check:
                time.sleep(0.2)  # 200ms delay between quote checks
            first_check = False
            
            # Get current price
            current_price = self.get_quote(trade.ticker)
            if current_price is None:
                continue
            
            # Check if profit target is hit
            hit_target = False
            if trade.action == 'LONG':
                # LONG: profit when price goes UP above take profit price
                hit_target = current_price >= trade.take_profit_price
            elif trade.action == 'SHORT':
                # SHORT: profit when price goes DOWN below take profit price
                hit_target = current_price <= trade.take_profit_price
            
            if hit_target:
                logger.info(f"🎯 Profit target hit for {trade.ticker}! Current: ${current_price:.4f}, Target: ${trade.take_profit_price:.4f}")
                
                # Cancel stop loss order first
                if trade.stop_loss_order_id:
                    logger.info(f"Cancelling stop loss order {trade.stop_loss_order_id}")
                    self.close_order(trade.stop_loss_order_id)
                    time.sleep(0.3)  # Brief delay after cancelling
                
                # Close position with market order
                close_action = trade.get_close_action()
                if close_action:
                    order_payload = {
                        "orderType": "MARKET",
                        "session": "NORMAL",
                        "duration": "DAY",
                        "orderStrategyType": "SINGLE",
                        "orderLegCollection": [{
                            "instruction": close_action,
                            "quantity": trade.quantity,
                            "instrument": {
                                "symbol": trade.ticker,
                                "assetType": "EQUITY"
                            }
                        }]
                    }
                    
                    response = self.create_order(order_payload)
                    
                    if 'error' not in response:
                        order_id = response.get('orderId', 'unknown')
                        # Get actual fill price
                        exit_price = self.get_fill_price_from_order(order_id)
                        if exit_price is None:
                            exit_price = current_price  # Fallback to quote
                        
                        trade.mark_closed(close_order_id=order_id, exit_price=exit_price)
                        save_trade_to_journal(trade)
                        
                        pnl_sign = "+" if trade.profit_loss >= 0 else ""
                        logger.info(f"✅ Profit target closed {trade.ticker}: {pnl_sign}${trade.profit_loss:.2f} ({pnl_sign}{trade.profit_loss_percent:.2f}%)")
                    else:
                        logger.error(f"Failed to close {trade.ticker} at profit target: {response.get('error')}")
        
        # Remove closed trades from active list
        self.active_trades = [t for t in self.active_trades if not t.is_closed]
    
    def check_and_close_old_trades(self):
        """Check active trades and close any that are TRADE_HOLD_MINUTES or older."""
        logger.debug(f"check_and_close_old_trades called with {len(self.active_trades)} active trades")
        
        # First check if any stop loss orders were triggered
        self.check_stop_loss_orders()
        
        # Check if any trades hit profit target
        self.check_profit_targets()
        
        trades_to_close = [trade for trade in self.active_trades if trade.should_close()]
        logger.info(f"Found {len(trades_to_close)} trades to close (of {len(self.active_trades)} active)")
        
        for trade in trades_to_close:
            logger.info(f"Closing trade {trade.ticker} ({trade.action}) - age: {trade.get_age_minutes():.1f} minutes")
            
            # Cancel stop loss order if it exists and hasn't been triggered
            # First check if stop loss was already filled
            if trade.stop_loss_order_id:
                # Check order status first to avoid trying to cancel already-filled orders
                stop_order_details = self.get_order_details(trade.stop_loss_order_id, update_headers=False)
                if 'error' not in stop_order_details:
                    order_status = stop_order_details.get('status', '').upper()
                    if order_status == 'FILLED':
                        logger.info(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} was already FILLED - trade should have been closed by stop loss handler")
                        # Trade should already be closed, skip manual close
                        continue
                    elif order_status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                        logger.debug(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} is already {order_status}, skipping cancel")
                    else:
                        # Order is still active, cancel it
                        logger.info(f"Cancelling stop loss order {trade.stop_loss_order_id} for {trade.ticker}")
                        cancel_result = self.close_order(trade.stop_loss_order_id)
                        if 'error' in cancel_result:
                            error_msg = cancel_result.get('error', '')
                            # Don't warn if it's already filled (race condition)
                            if 'FILLED' not in error_msg and 'cannot be canceled' not in error_msg:
                                logger.warning(f"Could not cancel stop loss order {trade.stop_loss_order_id}: {error_msg}")
            
            # Determine close action (SELL for LONG, BUY for SHORT)
            close_action = trade.get_close_action()
            if not close_action:
                logger.error(f"Unknown action type for closing trade: {trade.action}")
                continue
            
            # Create closing order
            close_order_payload = {
                "orderType": "MARKET",  # Use market order for immediate execution
                "session": "NORMAL",
                "duration": "DAY",
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [{
                    "instruction": close_action,
                    "quantity": trade.quantity,
                    "instrument": {
                        "symbol": trade.ticker,
                        "assetType": "EQUITY"
                    }
                }]
            }
            
            response = self.create_order(close_order_payload)
            
            if 'error' not in response:
                order_id = response.get('orderId', 'unknown')
                
                # Get actual execution/fill price from close order
                exit_price = self.get_fill_price_from_order(order_id)
                if exit_price is None:
                    logger.warning(f"Could not get fill price for close order {order_id}, using quote as fallback")
                    exit_price = self.get_quote(trade.ticker)
                    if exit_price is not None:
                        logger.warning(f"Using quote price as fallback for {trade.ticker}: ${exit_price:.4f} (may not match execution price)")
                
                trade.mark_closed(close_order_id=order_id, exit_price=exit_price)
                
                # Save trade result to journal
                save_trade_to_journal(trade)
                
                # Log P&L
                if trade.profit_loss is not None:
                    pnl_sign = "+" if trade.profit_loss >= 0 else ""
                    exit_price_display = exit_price if exit_price is not None else 0.0
                    logger.info(f"Close order placed for {trade.ticker}: Order ID {order_id}, Exit Price: ${exit_price_display:.4f}")
                    logger.info(f"  P&L: {pnl_sign}${trade.profit_loss:.2f} ({pnl_sign}{trade.profit_loss_percent:.2f}%)")
                else:
                    logger.info(f"Close order placed for {trade.ticker}: Order ID {order_id} (P&L not calculated)")
            else:
                logger.error(f"Failed to close trade {trade.ticker}: {response.get('error')}")
        
        # Remove closed trades from active list
        self.active_trades = [t for t in self.active_trades if not t.is_closed]
    
    def get_market_close_time_today(self) -> datetime:
        """
        Get the market close time for today in Eastern timezone.
        
        Returns:
            datetime: Market close time in Eastern timezone, or None if unavailable
        """
        try:
            self._update_headers()
            
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            current_date = now_eastern.strftime('%Y-%m-%d')
            
            market_hours_url = f"{self.market_data_base_url}/markets/hours"
            params = {
                'markets': 'EQUITY',
                'date': current_date
            }
            
            response = requests.get(market_hours_url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response structure
                equity_data = None
                if 'equity' in data and isinstance(data['equity'], dict):
                    if 'EQ' in data['equity']:
                        equity_data = data['equity']['EQ']
                
                if equity_data and 'sessionHours' in equity_data:
                    regular_market = equity_data['sessionHours'].get('regularMarket', [])
                    if regular_market and len(regular_market) > 0:
                        close_time_str = regular_market[0].get('end')
                        if close_time_str:
                            # Parse ISO format datetime
                            close_time_str_clean = close_time_str.replace('Z', '+00:00')
                            close_time = datetime.fromisoformat(close_time_str_clean)
                            if close_time.tzinfo is None:
                                close_time = eastern.localize(close_time)
                            else:
                                close_time = close_time.astimezone(eastern)
                            return close_time
            
            # Default to 4:00 PM ET if we can't get it from API
            logger.warning("Could not get market close time from API, using default 4:00 PM ET")
            return eastern.localize(datetime(
                now_eastern.year,
                now_eastern.month,
                now_eastern.day,
                16, 0  # 4:00 PM
            ))
            
        except Exception as e:
            logger.error(f"Error getting market close time: {e}")
            # Default to 4:00 PM ET on error
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            return eastern.localize(datetime(
                now_eastern.year,
                now_eastern.month,
                now_eastern.day,
                16, 0
            ))
    
    def get_market_hours_today(self) -> tuple[datetime, datetime, dict]:
        """
        Get market hours for today from the API and return regular market start/end times.
        
        Returns:
            tuple: (regular_market_start, regular_market_end, full_equity_data)
                - regular_market_start: Market open time in Eastern timezone
                - regular_market_end: Market close time in Eastern timezone
                - full_equity_data: Full equity data dict from API response
        """
        try:
            self._update_headers()
            
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            current_date = now_eastern.strftime('%Y-%m-%d')
            
            market_hours_url = f"{self.market_data_base_url}/markets/hours"
            params = {
                'markets': 'EQUITY',
                'date': current_date
            }
            
            response = requests.get(market_hours_url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                error_msg = f"Failed to get market hours: {response.status_code}"
                if response.text:
                    error_msg += f" - {response.text}"
                logger.error(error_msg)
                # Return default times on error
                default_start = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 9, 30))
                default_end = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 16, 0))
                return default_start, default_end, {}
            
            data = response.json()
            logger.debug(f"Market hours response: {data}")
            
            # Parse the response structure
            equity_data = None
            if 'equity' in data and isinstance(data['equity'], dict):
                if 'EQ' in data['equity']:
                    equity_data = data['equity']['EQ']
                else:
                    for key in data['equity']:
                        equity_data = data['equity'][key]
                        break
            elif 'EQUITY' in data and isinstance(data['EQUITY'], dict):
                if 'EQ' in data['EQUITY']:
                    equity_data = data['EQUITY']['EQ']
                else:
                    equity_data = data['EQUITY']
            
            if not equity_data or not isinstance(equity_data, dict):
                logger.warning("Could not parse market hours, using defaults")
                default_start = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 9, 30))
                default_end = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 16, 0))
                return default_start, default_end, equity_data or {}
            
            # Get regular market session times
            session_hours = equity_data.get('sessionHours', {})
            regular_market = session_hours.get('regularMarket', [])
            
            if regular_market and len(regular_market) > 0:
                regular_session = regular_market[0]
                open_time_str = regular_session.get('start')
                close_time_str = regular_session.get('end')
            else:
                logger.warning("Could not find regularMarket session hours, using defaults")
                default_start = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 9, 30))
                default_end = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 16, 0))
                return default_start, default_end, equity_data
            
            # Parse times
            try:
                if isinstance(open_time_str, str) and 'T' in open_time_str:
                    open_time_str_clean = open_time_str.replace('Z', '+00:00')
                    open_time = datetime.fromisoformat(open_time_str_clean)
                    if open_time.tzinfo is None:
                        open_time = eastern.localize(open_time)
                    else:
                        open_time = open_time.astimezone(eastern)
                else:
                    raise ValueError(f"Unexpected open time format: {open_time_str}")
            except Exception as e:
                logger.warning(f"Could not parse open time '{open_time_str}', using default: {e}")
                open_time = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 9, 30))
            
            try:
                if isinstance(close_time_str, str) and 'T' in close_time_str:
                    close_time_str_clean = close_time_str.replace('Z', '+00:00')
                    close_time = datetime.fromisoformat(close_time_str_clean)
                    if close_time.tzinfo is None:
                        close_time = eastern.localize(close_time)
                    else:
                        close_time = close_time.astimezone(eastern)
                else:
                    raise ValueError(f"Unexpected close time format: {close_time_str}")
            except Exception as e:
                logger.warning(f"Could not parse close time '{close_time_str}', using default: {e}")
                close_time = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 16, 0))
            
            return open_time, close_time, equity_data
            
        except Exception as e:
            logger.error(f"Error getting market hours: {e}")
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            default_start = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 9, 30))
            default_end = eastern.localize(datetime(now_eastern.year, now_eastern.month, now_eastern.day, 16, 0))
            return default_start, default_end, {}
    
    def get_next_execution_time(self, interval_minutes: int = TRADE_HOLD_MINUTES) -> datetime | None:
        """
        Calculate the next scheduled execution time based on market hours.
        
        Args:
            interval_minutes: Minutes between executions (defaults to TRADE_HOLD_MINUTES)
            
        Returns:
            datetime | None: Next execution time in Eastern timezone, or None if no more executions today
        """
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        
        # Get market hours for today
        market_start, market_end, _ = self.get_market_hours_today()
        
        # First execution time: market start + delay
        first_execution = market_start + timedelta(minutes=MARKET_OPEN_DELAY_MINUTES)
        
        # If we're before the first execution, return first execution time
        if now_eastern < first_execution:
            return first_execution
        
        # Calculate next execution time based on interval
        # Find how many intervals have passed since first execution
        time_since_first = (now_eastern - first_execution).total_seconds() / 60
        intervals_passed = int(time_since_first / interval_minutes)
        next_execution = first_execution + timedelta(minutes=(intervals_passed + 1) * interval_minutes)
        
        # Don't schedule past MARKET_CLOSE_BUFFER_MINUTES before close
        stop_time = market_end - timedelta(minutes=MARKET_CLOSE_BUFFER_MINUTES)
        if next_execution > stop_time:
            return None  # No more executions today
        
        return next_execution
    
    def is_market_about_to_close(self, minutes_before_close: int = None) -> tuple[bool, str]:
        """
        Check if market is about to close (within specified minutes).
        
        Args:
            minutes_before_close: How many minutes before close to trigger (default uses MARKET_CLOSE_BUFFER_MINUTES)
            
        Returns:
            tuple: (is_about_to_close, message)
        """
        if minutes_before_close is None:
            minutes_before_close = MARKET_CLOSE_BUFFER_MINUTES
        try:
            close_time = self.get_market_close_time_today()
            eastern = pytz.timezone('US/Eastern')
            now_eastern = datetime.now(eastern)
            
            time_until_close = (close_time - now_eastern).total_seconds() / 60
            
            if time_until_close <= 0:
                return True, f"Market already closed (closed at {close_time.strftime('%H:%M')} ET)"
            elif time_until_close <= minutes_before_close:
                return True, f"Market closing in {int(time_until_close)} minutes (at {close_time.strftime('%H:%M')} ET)"
            else:
                return False, f"Market closes at {close_time.strftime('%H:%M')} ET ({int(time_until_close)} minutes remaining)"
                
        except Exception as e:
            logger.error(f"Error checking if market about to close: {e}")
            return False, f"Error checking market close time: {str(e)}"
    
    def get_quote_full(self, symbol: str) -> dict | None:
        """
        Get full quote data for a symbol from Schwab Market Data API.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            dict: Full quote data including exchange information, or None if unavailable
        """
        try:
            self._update_headers()
            
            # Schwab Market Data API quote endpoint
            quote_url = f"{self.market_data_base_url}/quotes"
            params = {
                'symbols': symbol,
                'fields': 'quote'  # Request quote data
            }
            
            response = requests.get(quote_url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # Parse response structure
                # Response format: {symbol: {quote: {price data}, ...}}
                if symbol in data:
                    symbol_data = data[symbol]
                    quote_data = symbol_data.get('quote', {})
                    return quote_data
                else:
                    logger.warning(f"Symbol {symbol} not found in quote response: {data}")
                    return None
            else:
                logger.error(f"Failed to get quote for {symbol}: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    def get_quote(self, symbol: str) -> float | None:
        """
        Get current quote for a symbol from Schwab Market Data API.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            float: Current last price, or None if unavailable
        """
        quote_data = self.get_quote_full(symbol)
        if quote_data is None:
            return None
        
        # Try different possible fields for last price
        last_price = (
            quote_data.get('lastPrice') or
            quote_data.get('last') or
            quote_data.get('mark') or  # Mark price is often available
            quote_data.get('closePrice') or
            quote_data.get('regularMarketLastPrice') or
            quote_data.get('bidPrice') or  # Fallback to bid if no last price
            quote_data.get('askPrice')  # Fallback to ask if no other price
        )
        if last_price is not None:
            return float(last_price)
        else:
            logger.warning(f"Could not find price in quote data for {symbol}: {quote_data}")
            return None
    
    def has_commission(self, symbol: str) -> bool:
        """
        Check if a stock has commissions associated with trading.
        OTC stocks and certain other securities typically have $6.95 commission per trade.
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            bool: True if stock has commissions, False otherwise
        """
        # Blacklist of known commission stocks (based on user's experience)
        COMMISSION_BLACKLIST = {
            'ASST',  # STRIVE INC CLASS A
            'UP',    # WHEELS UP EXPERIENCE INC CLASS A
            'AMC',   # AMC ENTMT HLDGS INC CLASS CLASS A
            'BTBT',  # BATTLEBIT TECHNOLOGIES INC CLASS A
            'PLUG',  # PLUG POWER INC CLASS A
            'BITF',  # BITFINEX LTD CLASS A
            'DNN',
            'BTG',
            'RIG',
            'RXRX',
            'BBAI',
            'GRAB',
            'JBLU',
            'NIO',
            'CAN',
            'MARA',
            'ONDS',
            'RDW',
            'SOC',
            'BMNR',
            'AAL',
            'ACHR',
            'GRAB',
            'VG',
            'RZLV',
            'SOUN',
            'WULF',
            'CLSK',
            'CIFR',
            'CDE',
            'DJT',   # TRUMP MEDIA & TECHNO
            'HL',    # HECLA MNG CO
            'HYMC',  # HYCROFT MNG HLDG CORP CLASS A
            'IOVA',  # IOVANCE BIOTHERAPEUTICS
            'OMER',  # OMEROS CORP
            'OWL',   # BLUE OWL CAP INC CLASS A
            'PATH',  # UIPATH INC CLASS CLASS A
            'QBTS',  # D-WAVE QUANTUM INC
            'QUBT',  # QUANTUM COMPUTING INC
            'RGTI',  # RIGETTI COMPUTING INC
            'RITM',  # RITHM CAPITAL CORP REIT
            'RIVN',  # RIVIAN AUTOMOTIVE INC CLASS A

        }
        
        # Check blacklist first
        if symbol.upper() in COMMISSION_BLACKLIST:
            logger.info(f"{symbol} is in commission blacklist")
            return True
        
        # Try to get quote data to check exchange
        quote_data = self.get_quote_full(symbol)
        if quote_data is None:
            # If we can't get quote data, be conservative and assume no commission
            # (better to trade than to skip unnecessarily)
            logger.warning(f"Could not get quote data for {symbol}, assuming no commission")
            return False
        
        # Check exchange information
        # OTC stocks typically have commissions
        exchange = quote_data.get('exchange', '').upper()
        primary_exchange = quote_data.get('primaryExchange', '').upper()
        
        # OTC exchanges that typically have commissions
        OTC_EXCHANGES = {
            'OTC', 'OTCMKTS', 'OTCQB', 'OTCQX', 'PINK', 'GREY',
            'OTCBB', 'OTCPK', 'OTC MARKETS'
        }
        
        # Check if exchange indicates OTC
        if exchange in OTC_EXCHANGES or primary_exchange in OTC_EXCHANGES:
            logger.info(f"{symbol} is OTC (exchange: {exchange or primary_exchange}), has commission")
            return True
        
        # Check for other indicators of commission stocks
        # Some penny stocks or low-priced stocks may have commissions
        # But we'll be conservative and only flag known OTC exchanges
        
        return False
    
    def close_all_positions(self):
        """
        Close all active positions regardless of age.
        This is an emergency function to close everything before market close or program shutdown.
        """
        if not self.active_trades:
            logger.info("No active trades to close")
            return
        
        logger.warning(f"=== CLOSING ALL {len(self.active_trades)} ACTIVE POSITIONS ===")
        
        for trade in self.active_trades:
            if trade.is_closed:
                continue
                
            logger.info(f"Closing position: {trade.ticker} ({trade.action}) - age: {trade.get_age_minutes():.1f} minutes")
            
            # Cancel stop loss order if it exists and hasn't been triggered
            # First check if stop loss was already filled
            if trade.stop_loss_order_id:
                # Check order status first to avoid trying to cancel already-filled orders
                stop_order_details = self.get_order_details(trade.stop_loss_order_id, update_headers=False)
                if 'error' not in stop_order_details:
                    order_status = stop_order_details.get('status', '').upper()
                    if order_status == 'FILLED':
                        logger.info(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} was already FILLED - trade should have been closed by stop loss handler")
                        # Trade should already be closed, skip manual close
                        continue
                    elif order_status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                        logger.debug(f"Stop loss order {trade.stop_loss_order_id} for {trade.ticker} is already {order_status}, skipping cancel")
                    else:
                        # Order is still active, cancel it
                        logger.info(f"Cancelling stop loss order {trade.stop_loss_order_id} for {trade.ticker}")
                        cancel_result = self.close_order(trade.stop_loss_order_id)
                        if 'error' in cancel_result:
                            error_msg = cancel_result.get('error', '')
                            # Don't warn if it's already filled (race condition)
                            if 'FILLED' not in error_msg and 'cannot be canceled' not in error_msg:
                                logger.warning(f"Could not cancel stop loss order {trade.stop_loss_order_id}: {error_msg}")
            
            # Determine close action (SELL for LONG, BUY for SHORT)
            close_action = trade.get_close_action()
            if not close_action:
                logger.error(f"Unknown action type for closing trade: {trade.action}")
                continue
            
            # Create closing order
            close_order_payload = {
                "orderType": "MARKET",  # Use market order for immediate execution
                "session": "NORMAL",
                "duration": "DAY",
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [{
                    "instruction": close_action,
                    "quantity": trade.quantity,
                    "instrument": {
                        "symbol": trade.ticker,
                        "assetType": "EQUITY"
                    }
                }]
            }
            
            response = self.create_order(close_order_payload)
            
            if 'error' not in response:
                order_id = response.get('orderId', 'unknown')
                
                # Get actual execution/fill price from close order
                exit_price = self.get_fill_price_from_order(order_id)
                if exit_price is None:
                    logger.warning(f"Could not get fill price for close order {order_id}, using quote as fallback")
                    exit_price = self.get_quote(trade.ticker)
                    if exit_price is not None:
                        logger.warning(f"Using quote price as fallback for {trade.ticker}: ${exit_price:.4f} (may not match execution price)")
                
                trade.mark_closed(close_order_id=order_id, exit_price=exit_price)
                
                # Save trade result to journal
                save_trade_to_journal(trade)
                
                # Log P&L
                if trade.profit_loss is not None:
                    pnl_sign = "+" if trade.profit_loss >= 0 else ""
                    exit_price_display = exit_price if exit_price is not None else 0.0
                    logger.info(f"Close order placed for {trade.ticker}: Order ID {order_id}, Exit Price: ${exit_price_display:.4f}")
                    logger.info(f"  P&L: {pnl_sign}${trade.profit_loss:.2f} ({pnl_sign}{trade.profit_loss_percent:.2f}%)")
                else:
                    logger.info(f"Close order placed for {trade.ticker}: Order ID {order_id} (P&L not calculated)")
            else:
                logger.error(f"Failed to close trade {trade.ticker}: {response.get('error')}")
        
        # Remove closed trades from active list
        self.active_trades = [t for t in self.active_trades if not t.is_closed]
        logger.info(f"Close-all complete. Remaining active trades: {len(self.active_trades)}")


def save_trade_to_journal(trade: Trade):
    """
    Save a closed trade to the trade journal file.
    
    Args:
        trade: Trade object that has been closed
    """
    if not trade.is_closed:
        logger.warning(f"Attempted to save trade {trade.ticker} that is not closed")
        return
    
    # Use absolute path to ensure file is saved in the script's directory
    script_dir = Path(__file__).parent
    journal_path = script_dir / TRADE_JOURNAL_FILE
    
    # Load existing trades
    trades = []
    if journal_path.exists():
        try:
            with open(journal_path, 'r') as f:
                trades = json.load(f)
        except Exception as e:
            logger.error(f"Error reading trade journal: {e}")
            trades = []
    
    # Add new trade
    trade_dict = trade.to_dict()
    trades.append(trade_dict)
    
    # Save back to file
    try:
        with open(journal_path, 'w') as f:
            json.dump(trades, f, indent=2)
        logger.info(f"Saved trade {trade.ticker} to journal")
    except Exception as e:
        logger.error(f"Error saving trade to journal: {e}")


def calculate_win_rate(journal_file: str = TRADE_JOURNAL_FILE) -> dict:
    """
    Calculate win rate statistics from the trade journal.
    
    Args:
        journal_file: Path to the trade journal file
        
    Returns:
        dict: Statistics including win rate, total trades, winners, losers, total P&L
    """
    # Use absolute path to ensure file is found in the script's directory
    script_dir = Path(__file__).parent
    journal_path = script_dir / journal_file
    
    if not journal_path.exists():
        logger.warning(f"Trade journal file {journal_file} does not exist")
        return {
            'total_trades': 0,
            'winners': 0,
            'losers': 0,
            'breakeven': 0,
            'win_rate_percent': 0.0,
            'total_profit_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0
        }
    
    try:
        with open(journal_path, 'r') as f:
            trades = json.load(f)
    except Exception as e:
        logger.error(f"Error reading trade journal: {e}")
        return {
            'total_trades': 0,
            'winners': 0,
            'losers': 0,
            'breakeven': 0,
            'win_rate_percent': 0.0,
            'total_profit_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0
        }
    
    if not trades:
        return {
            'total_trades': 0,
            'winners': 0,
            'losers': 0,
            'breakeven': 0,
            'win_rate_percent': 0.0,
            'total_profit_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0
        }
    
    # Filter trades with valid P&L
    valid_trades = [t for t in trades if t.get('profit_loss') is not None]
    
    if not valid_trades:
        return {
            'total_trades': len(trades),
            'winners': 0,
            'losers': 0,
            'breakeven': 0,
            'win_rate_percent': 0.0,
            'total_profit_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0
        }
    
    winners = [t for t in valid_trades if t['profit_loss'] > 0]
    losers = [t for t in valid_trades if t['profit_loss'] < 0]
    breakeven = [t for t in valid_trades if t['profit_loss'] == 0]
    
    total_trades = len(valid_trades)
    win_count = len(winners)
    loss_count = len(losers)
    breakeven_count = len(breakeven)
    
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
    
    total_pnl = sum(t['profit_loss'] for t in valid_trades)
    
    avg_win = sum(t['profit_loss'] for t in winners) / len(winners) if winners else 0.0
    avg_loss = sum(t['profit_loss'] for t in losers) / len(losers) if losers else 0.0
    
    return {
        'total_trades': total_trades,
        'winners': win_count,
        'losers': loss_count,
        'breakeven': breakeven_count,
        'win_rate_percent': win_rate,
        'total_profit_loss': total_pnl,
        'average_win': avg_win,
        'average_loss': avg_loss
    }


def send_stats_to_webhook(stats: dict):
    """
    Send trade statistics to the ntfy.sh webhook.
    
    Args:
        stats: Dictionary containing trade statistics
    """
    try:
        # Format the message
        message = f"""Trade Statistics Update

Total Trades: {stats['total_trades']}
Winners: {stats['winners']}
Losers: {stats['losers']}
Breakeven: {stats['breakeven']}
Win Rate: {stats['win_rate_percent']:.2f}%
Total P&L: ${stats['total_profit_loss']:.2f}"""
        
        if stats['winners'] > 0:
            message += f"\nAverage Win: ${stats['average_win']:.2f}"
        if stats['losers'] > 0:
            message += f"\nAverage Loss: ${stats['average_loss']:.2f}"
        
        # Send POST request to ntfy.sh
        response = requests.post(
            NTFY_WEBHOOK_URL,
            data=message.encode('utf-8'),
            headers={
                'Content-Type': 'text/plain',
                'Title': 'Algo Trade Statistics'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("Trade statistics sent to webhook successfully")
        else:
            logger.warning(f"Webhook returned status {response.status_code}: {response.text}")
            
    except Exception as e:
        logger.error(f"Error sending statistics to webhook: {e}")


def collect_dashboard_data(accounts_trading: AccountsTrading) -> dict:
    """
    Collect all dashboard data including stats, trades, and account information.
    
    Args:
        accounts_trading: AccountsTrading instance
        
    Returns:
        dict: Complete dashboard data
    """
    # Get trade statistics
    stats = calculate_win_rate()
    
    # Get recent trades from journal
    script_dir = Path(__file__).parent
    journal_path = script_dir / TRADE_JOURNAL_FILE
    recent_trades = []
    if journal_path.exists():
        try:
            with open(journal_path, 'r') as f:
                all_trades = json.load(f)
                # Get last 50 trades
                recent_trades = all_trades[-50:] if len(all_trades) > 50 else all_trades
        except Exception as e:
            logger.error(f"Error reading trade journal for dashboard: {e}")
    
    # Get active trades
    active_trades = []
    for trade in accounts_trading.active_trades:
        if not trade.is_closed:
            active_trades.append({
                'ticker': trade.ticker,
                'action': trade.action,
                'quantity': trade.quantity,
                'entry_price': trade.entry_price,
                'time_placed': trade.time_placed.isoformat() if trade.time_placed else None,
                'age_minutes': trade.get_age_minutes(),
                'stop_loss_price': trade.stop_loss_price
            })
    
    # Get account information
    account_info = accounts_trading.get_account_info()
    positions = accounts_trading.get_positions()
    
    # Extract key account metrics
    account_metrics = {}
    if account_info:
        # Try to extract common fields - handle different response structures
        # Schwab API might return data in different nested structures
        current_balances = None
        if 'currentBalances' in account_info:
            current_balances = account_info['currentBalances']
        elif 'securitiesAccount' in account_info and 'currentBalances' in account_info['securitiesAccount']:
            current_balances = account_info['securitiesAccount']['currentBalances']
        elif isinstance(account_info, dict):
            # Try direct access if structure is flat
            current_balances = account_info
        
        if current_balances:
            # Try various field names that might exist
            account_metrics['account_value'] = (
                current_balances.get('liquidationValue') or
                current_balances.get('totalEquity') or
                current_balances.get('equity') or
                current_balances.get('netValue')
            )
            account_metrics['buying_power'] = (
                current_balances.get('buyingPower') or
                current_balances.get('buyingPowerNonMarginableTrade')
            )
            account_metrics['cash_balance'] = (
                current_balances.get('cashBalance') or
                current_balances.get('availableFunds')
            )
            account_metrics['day_trading_buying_power'] = (
                current_balances.get('dayTradingBuyingPower') or
                current_balances.get('dayTradingBuyingPowerCall')
            )
        
        # Remove None values
        account_metrics = {k: v for k, v in account_metrics.items() if v is not None}
    
    dashboard_data = {
        'timestamp': datetime.now(pytz.timezone('US/Eastern')).isoformat(),
        'statistics': stats,
        'active_trades': active_trades,
        'recent_trades': recent_trades,
        'account_metrics': account_metrics,
        'positions': positions,
        'account_info': account_info  # Include full account info for debugging
    }
    
    return dashboard_data


def send_dashboard_data_to_website(dashboard_data: dict, local_port: int = 4131):
    """
    Send dashboard data to both local and remote website endpoints.
    
    Args:
        dashboard_data: Dashboard data dictionary
        local_port: Local server port (default 4131)
    """
    endpoints = [
        f"http://localhost:{local_port}/api/trading_data",
        "https://herstrom.com/api/trading_data"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.post(
                endpoint,
                json=dashboard_data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            if response.status_code == 200:
                logger.debug(f"Dashboard data sent to {endpoint} successfully")
            else:
                logger.warning(f"Failed to send dashboard data to {endpoint}: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"Could not send dashboard data to {endpoint}: {e}")
        except Exception as e:
            logger.error(f"Error sending dashboard data to {endpoint}: {e}")


def print_win_rate_stats(send_webhook: bool = False, accounts_trading: AccountsTrading = None, send_dashboard: bool = True):
    """
    Print win rate statistics to the logger and optionally send to webhook and dashboard.
    
    Args:
        send_webhook: If True, send statistics to webhook
        accounts_trading: AccountsTrading instance for dashboard data (optional)
        send_dashboard: If True and accounts_trading provided, send to dashboard
    """
    stats = calculate_win_rate()
    
    logger.info("=== Trade Statistics ===")
    logger.info(f"Total Trades: {stats['total_trades']}")
    logger.info(f"Winners: {stats['winners']}")
    logger.info(f"Losers: {stats['losers']}")
    logger.info(f"Breakeven: {stats['breakeven']}")
    logger.info(f"Win Rate: {stats['win_rate_percent']:.2f}%")
    logger.info(f"Total P&L: ${stats['total_profit_loss']:.2f}")
    if stats['winners'] > 0:
        logger.info(f"Average Win: ${stats['average_win']:.2f}")
    if stats['losers'] > 0:
        logger.info(f"Average Loss: ${stats['average_loss']:.2f}")
    
    # Send to webhook if requested
    if send_webhook:
        send_stats_to_webhook(stats)
    
    # Send to dashboard if requested
    if send_dashboard and accounts_trading:
        try:
            dashboard_data = collect_dashboard_data(accounts_trading)
            send_dashboard_data_to_website(dashboard_data)
        except Exception as e:
            logger.error(f"Error sending dashboard data: {e}")


def send_trades(list_of_trades, accounts_trading: AccountsTrading):
    """
    Execute trades via Schwab API and create Trade objects to track them.
    
    Args:
        list_of_trades: List of processed trades from strategy (dicts with ticker, action, quantity)
        accounts_trading: AccountsTrading instance with API connection
    """
    logger.info(f"=== Executing {len(list_of_trades)} trades via Schwab API ===")
    
    # Ensure headers are up to date with fresh token
    accounts_trading._update_headers()
    
    executed_trades = []
    
    for idx, trade_dict in enumerate(list_of_trades):
        ticker = trade_dict.get('ticker')
        action = trade_dict.get('action')  # LONG or SHORT
        quantity = trade_dict.get('quantity')
        
        if not all([ticker, action, quantity]):
            logger.error(f"Invalid trade data: {trade_dict}")
            continue
        
        # Add small delay between orders to avoid rate limiting (except for first order)
        if idx > 0:
            time.sleep(0.3)  # 300ms delay between orders to prevent rate limiting
        
        # Convert LONG/SHORT to Schwab API instructions
        # LONG -> BUY, SHORT -> SELL_SHORT
        if action.upper() == 'LONG':
            instruction = 'BUY'
        elif action.upper() == 'SHORT':
            instruction = 'SELL_SHORT'
        else:
            logger.error(f"Unknown action: {action}, skipping trade")
            continue
        
        # Create Trade object
        trade = Trade(ticker=ticker, action=action, quantity=quantity)
        
        # Create order payload
        order_payload = {
            "orderType": "MARKET",  # Market order for immediate execution
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": instruction,
                "quantity": quantity,
                "instrument": {
                    "symbol": ticker,
                    "assetType": "EQUITY"
                }
            }]
        }
        
        # Place order via API
        logger.info(f"Placing order: {ticker} {action} {quantity} shares")
        api_response = accounts_trading.create_order(order_payload)
        
        # Update trade with API response
        trade.update_from_api_response(api_response)
        
        # Get actual execution/fill price from order details
        if trade.order_id:
            fill_price = accounts_trading.get_fill_price_from_order(trade.order_id)
            if fill_price is not None:
                trade.entry_price = fill_price
                logger.info(f"Set entry price from order execution: ${trade.entry_price:.4f}")
            else:
                logger.warning(f"Could not get fill price for order {trade.order_id}, entry_price may be inaccurate")
        
        # Fallback: If we still don't have entry price, use quote (less accurate)
        if trade.entry_price is None:
            entry_price = accounts_trading.get_quote(ticker)
            if entry_price is not None:
                trade.entry_price = entry_price
                logger.warning(f"Using quote price as fallback for {ticker}: ${entry_price:.4f} (may not match execution price)")
        
        # Create stop loss order and set take profit target if we have entry price
        # Wait a moment to ensure entry order is fully processed
        if trade.entry_price is not None:
            time.sleep(0.8)  # Brief delay to ensure entry order is processed and to avoid rate limiting
            stop_loss_response = accounts_trading.create_stop_loss_order(trade, trade.entry_price, stop_loss_percent=2.0)
            if 'error' in stop_loss_response:
                logger.error(f"Failed to create stop loss order for {ticker}: {stop_loss_response.get('error')}")
            elif trade.stop_loss_order_id:
                logger.info(f"Stop loss order placed for {ticker} at ${trade.stop_loss_price:.4f} (2% from entry ${trade.entry_price:.4f})")
            else:
                logger.warning(f"Stop loss order created but no order ID returned for {ticker}")
            
            # Set take profit price target (monitored, not a limit order)
            trade.take_profit_price = trade.calculate_take_profit_price(trade.entry_price, TAKE_PROFIT_PERCENT)
            if trade.take_profit_price:
                logger.info(f"Take profit target set for {ticker} at ${trade.take_profit_price:.4f} ({TAKE_PROFIT_PERCENT}% from entry)")
        else:
            logger.warning(f"Cannot create stop loss order for {ticker} - no entry price available")
        
        # Add to active trades list
        accounts_trading.active_trades.append(trade)
        executed_trades.append(trade)
        
        logger.info(f"Trade placed: {trade}")
    
    logger.info(f"Executed {len(executed_trades)} trades via Schwab API")
    return executed_trades

def market_timing_loop(accounts_trading: AccountsTrading):
    """
    Separate loop that handles market timing - waits for market to be open for MARKET_OPEN_DELAY_MINUTES.
    This loop runs independently from the algo loop.
    
    Returns:
        bool: True when market is open for MARKET_OPEN_DELAY_MINUTES and ready for algo, False otherwise
    """
    while True:
        is_market_open, message = accounts_trading.is_market_open_for_15_minutes()
        
        if is_market_open:
            logger.info(f"Market timing check: {message}")
            logger.info(f"Market has been open for {MARKET_OPEN_DELAY_MINUTES}+ minutes - ready to start algo loop")
            return True
        else:
            logger.info(f"Market timing check: {message}")
            # Check for closing trades less frequently when market is closed
            if accounts_trading.active_trades:
                logger.info(f"Have {len(accounts_trading.active_trades)} active trades waiting to close when market opens")
            time.sleep(60 * 5)  # Check every 5 minutes when waiting for market to open


def algo_loop(accounts_trading: AccountsTrading, controller: GodelTerminalController):
    """
    Main algo loop that runs strategy and executes trades at scheduled times based on market hours.
    Only runs when market has been open for MARKET_OPEN_DELAY_MINUTES until MARKET_CLOSE_BUFFER_MINUTES before close.
    """
    logger.info("=== Starting algo loop ===")
    
    # Get market hours to calculate execution schedule
    market_start, market_end, equity_data = accounts_trading.get_market_hours_today()
    logger.info(f"Market hours today: {market_start.strftime('%H:%M')} - {market_end.strftime('%H:%M')} ET")
    
    # Send initial dashboard data
    try:
        dashboard_data = collect_dashboard_data(accounts_trading)
        send_dashboard_data_to_website(dashboard_data)
    except Exception as e:
        logger.debug(f"Could not send initial dashboard data: {e}")
    
    try:
        while True:
            # Verify we're still in valid trading window (MARKET_OPEN_DELAY_MINUTES min after open, MARKET_CLOSE_BUFFER_MINUTES min before close)
            is_market_open, open_message = accounts_trading.is_market_open_for_15_minutes()
            if not is_market_open:
                logger.warning(f"Market no longer in valid trading window: {open_message}")
                logger.warning("Exiting algo loop - returning to market timing loop")
                break
            
            # Check if market is about to close (within MARKET_CLOSE_BUFFER_MINUTES)
            is_about_to_close, close_message = accounts_trading.is_market_about_to_close()
            if is_about_to_close:
                logger.warning(f"Market about to close: {close_message}")
                logger.warning("Stopping algo loop - closing all positions before market close...")
                accounts_trading.close_all_positions()
                print_win_rate_stats(send_webhook=True, accounts_trading=accounts_trading)  # Send webhook after closing all positions
                break  # Exit algo loop when market is about to close
            
            # Check and close any trades that are TRADE_HOLD_MINUTES or older
            trades_closed = len(accounts_trading.active_trades)
            accounts_trading.check_and_close_old_trades()
            trades_after_close = len(accounts_trading.active_trades)
            
            # If trades were closed, print stats and send to webhook
            if trades_closed > trades_after_close:
                print_win_rate_stats(send_webhook=True, accounts_trading=accounts_trading)
            else:
                print_win_rate_stats(accounts_trading=accounts_trading)
            
            # If we have active trades, monitor them until they're ready to close
            if accounts_trading.active_trades:
                # Use wall-clock time for reliable timing (not affected by API call durations)
                loop_start_time = time.time()
                check_interval_seconds = 60  # Check stop losses and profit targets every 60 seconds
                last_check_time = 0  # Track last API check time
                is_about_to_close = False  # Initialize for safety
                
                logger.info(f"=== Monitoring {len(accounts_trading.active_trades)} active trades ===")
                
                # Loop until all trades are closed or old enough to close
                while accounts_trading.active_trades:
                    # Get current oldest trade age (recalculate each iteration)
                    oldest_trade = min(accounts_trading.active_trades, key=lambda t: t.time_placed)
                    age_minutes = oldest_trade.get_age_minutes()
                    remaining_minutes = TRADE_HOLD_MINUTES - age_minutes
                    
                    logger.info(f"Trade status: {len(accounts_trading.active_trades)} active, oldest age: {age_minutes:.1f} min (close in {max(0, remaining_minutes):.1f} min)")
                    
                    # CRITICAL CHECK: If trades are old enough, close them immediately
                    if age_minutes >= TRADE_HOLD_MINUTES:
                        logger.info(f"✅ Trades reached {TRADE_HOLD_MINUTES} min hold time - closing now...")
                        accounts_trading.check_and_close_old_trades()
                        print_win_rate_stats(send_webhook=True, accounts_trading=accounts_trading)
                        break  # Exit wait loop, continue to make new trades
                    
                    # Check if market is about to close
                    is_about_to_close, close_message = accounts_trading.is_market_about_to_close()
                    if is_about_to_close:
                        logger.warning(f"⚠️ Market about to close: {close_message}")
                        accounts_trading.close_all_positions()
                        print_win_rate_stats(send_webhook=True, accounts_trading=accounts_trading)
                        break  # Exit wait loop, main loop will also exit
                    
                    # Periodically check stop losses and profit targets (every check_interval_seconds)
                    current_time = time.time()
                    if current_time - last_check_time >= check_interval_seconds:
                        logger.debug(f"Checking stop losses and profit targets...")
                        accounts_trading.check_stop_loss_orders()
                        accounts_trading.check_profit_targets()
                        last_check_time = current_time
                    
                    # Sleep for a short interval then check again
                    # Use 30 second intervals to balance responsiveness vs CPU usage
                    time.sleep(30)
                
                # If we exited because market is closing, propagate that to main loop
                if is_about_to_close:
                    break
                
                # Otherwise, continue to make new trades
                logger.info("Trade monitoring complete - proceeding to next cycle")
                continue
            
            # No active trades, run strategy to get new trades
            processed_trades = run_strategy(controller, accounts_trading)
            
            if processed_trades:
                # Execute trades via Schwab API
                send_trades(processed_trades, accounts_trading)
                logger.info(f"Placed {len(processed_trades)} new trades - will wait {TRADE_HOLD_MINUTES} minutes before closing")
                # Continue to next iteration to wait for trades to close
                continue
            else:
                logger.info("No trades to execute")
                # If no trades and no active trades, wait a bit before checking again
                # But check market hours first
                is_about_to_close, close_message = accounts_trading.is_market_about_to_close()
                if is_about_to_close:
                    logger.warning(f"Market about to close: {close_message}")
                    accounts_trading.close_all_positions()
                    print_win_rate_stats(send_webhook=True, accounts_trading=accounts_trading)  # Send webhook after closing all positions
                    break
                
                # Wait a short time before checking again
                logger.info("No trades available - waiting 1 minute before checking again...")
                time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("\nStopping algo loop (KeyboardInterrupt)...")
        raise
    except Exception as e:
        logger.error(f"Error in algo loop: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Main loop for MOST -> PRT -> Schwab API workflow"""
    # Initialize Schwab API connection with token manager
    accounts_trading = None
    try:
        accounts_trading = AccountsTrading()
        logger.info("Schwab API connection initialized with token manager")
    except Exception as e:
        logger.error(f"Failed to initialize Schwab API connection: {e}")
        logger.error("Make sure you have run get_OG_tokens.py first to initialize tokens")
        return
    
    # Register cleanup function to close all positions on exit
    def cleanup_on_exit():
        if accounts_trading:
            logger.warning("Program exiting - closing all positions...")
            accounts_trading.close_all_positions()
    
    atexit.register(cleanup_on_exit)
    
    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.warning(f"Received signal {signum} - closing all positions and exiting...")
        if accounts_trading:
            accounts_trading.close_all_positions()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Main outer loop - handles market timing separately from algo execution
    controller = None
    while True:
        try:
            # Market timing loop - waits for market to be open for MARKET_OPEN_DELAY_MINUTES
            market_timing_loop(accounts_trading)
            
            # Initialize controller when market is ready
            if controller is None:
                logger.info("Initializing Godel controller...")
                controller = GodelTerminalController()
                controller.connect()
                controller.login(GODEL_USERNAME, GODEL_PASSWORD)
                controller.load_layout("dev")
                logger.info("Godel controller initialized successfully")
            
            # Run algo loop - only runs from MARKET_OPEN_DELAY_MINUTES min after open until MARKET_CLOSE_BUFFER_MINUTES min before close
            algo_loop(accounts_trading, controller)
            
            # Algo loop exited (market about to close or error)
            logger.info("Algo loop exited - returning to market timing loop")
            
        except KeyboardInterrupt:
            logger.info("\nProgram interrupted by user - shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            # Wait a bit before retrying
            logger.info("Waiting 60 seconds before retrying...")
            time.sleep(60)
        finally:
            # Clean up controller if needed (but keep it for next market session)
            # Only close if we're shutting down completely
            pass
    
    # Final cleanup
    if accounts_trading:
        logger.warning("Final cleanup - closing all positions...")
        accounts_trading.close_all_positions()
    
    if controller:
        try:
            logger.info("Cleaning up controller...")
            controller.close_all_windows()
            controller.disconnect()
            logger.info("Controller closed successfully")
        except Exception as e:
            logger.error(f"Error closing controller: {e}")

if __name__ == "__main__":
    main()
    
    