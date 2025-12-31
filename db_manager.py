"""
Database Manager for Trading System
Handles all database operations for storing trades and dashboard data.
"""
import mysql.connector
from mysql.connector import Error
from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz
from loguru import logger
from config import DB_CONFIG


class DatabaseManager:
    """Manages database connections and operations for the trading system."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize database manager.
        
        Args:
            config: Database configuration dict. If None, uses DB_CONFIG from config.py
        """
        self.config = config or DB_CONFIG
        self.connection = None
        self._ensure_connection()
    
    def _ensure_connection(self):
        """Ensure database connection is active, reconnect if needed."""
        try:
            if self.connection is None or not self.connection.is_connected():
                self.connection = mysql.connector.connect(**self.config)
                logger.debug("Database connection established")
        except Error as e:
            logger.error(f"Error connecting to database: {e}")
            self.connection = None
            raise
    
    def _reconnect_if_needed(self):
        """Reconnect if connection is lost."""
        try:
            self.connection.ping(reconnect=True, attempts=3, delay=1)
        except Error:
            self._ensure_connection()
    
    def insert_trade(self, trade_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert a trade into the database.
        
        Args:
            trade_data: Dictionary containing trade information matching trade_journal.json structure
            
        Returns:
            Trade ID if successful, None otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # Insert main trade record
            trade_insert = """
                INSERT INTO trades (
                    ticker, action, quantity, entry_price, exit_price,
                    profit_loss, profit_loss_percent, time_placed, close_time,
                    hold_time_minutes, order_id, close_order_id, stop_loss_order_id,
                    stop_loss_price, take_profit_price, is_winner,
                    entry_order_type, exit_order_type, entry_spread, exit_spread, is_closed
                ) VALUES (
                    %(ticker)s, %(action)s, %(quantity)s, %(entry_price)s, %(exit_price)s,
                    %(profit_loss)s, %(profit_loss_percent)s, %(time_placed)s, %(close_time)s,
                    %(hold_time_minutes)s, %(order_id)s, %(close_order_id)s, %(stop_loss_order_id)s,
                    %(stop_loss_price)s, %(take_profit_price)s, %(is_winner)s,
                    %(entry_order_type)s, %(exit_order_type)s, %(entry_spread)s, %(exit_spread)s, %(is_closed)s
                )
            """
            
            # Parse datetime strings if needed - ensure UTC for storage
            time_placed = trade_data.get('time_placed')
            if isinstance(time_placed, str):
                time_placed = datetime.fromisoformat(time_placed.replace('Z', '+00:00'))
                # Ensure timezone-aware UTC
                if time_placed.tzinfo is None:
                    time_placed = pytz.UTC.localize(time_placed)
                else:
                    time_placed = time_placed.astimezone(pytz.UTC)
            elif time_placed and hasattr(time_placed, 'tzinfo') and time_placed.tzinfo is not None:
                # If datetime is timezone-aware, convert to UTC
                time_placed = time_placed.astimezone(pytz.UTC)
            
            close_time = trade_data.get('close_time')
            if close_time:
                if isinstance(close_time, str):
                    close_time = datetime.fromisoformat(close_time.replace('Z', '+00:00'))
                    # Ensure timezone-aware UTC
                    if close_time.tzinfo is None:
                        close_time = pytz.UTC.localize(close_time)
                    else:
                        close_time = close_time.astimezone(pytz.UTC)
                elif hasattr(close_time, 'tzinfo') and close_time.tzinfo is not None:
                    # If datetime is timezone-aware, convert to UTC
                    close_time = close_time.astimezone(pytz.UTC)
            
            trade_values = {
                'ticker': trade_data.get('ticker'),
                'action': trade_data.get('action'),
                'quantity': trade_data.get('quantity'),
                'entry_price': trade_data.get('entry_price'),
                'exit_price': trade_data.get('exit_price'),
                'profit_loss': trade_data.get('profit_loss'),
                'profit_loss_percent': trade_data.get('profit_loss_percent'),
                'time_placed': time_placed,
                'close_time': close_time,
                'hold_time_minutes': trade_data.get('hold_time_minutes'),
                'order_id': trade_data.get('order_id'),
                'close_order_id': trade_data.get('close_order_id'),
                'stop_loss_order_id': trade_data.get('stop_loss_order_id'),
                'stop_loss_price': trade_data.get('stop_loss_price'),
                'take_profit_price': trade_data.get('take_profit_price'),
                'is_winner': trade_data.get('is_winner'),
                'entry_order_type': trade_data.get('entry_order_type'),
                'exit_order_type': trade_data.get('exit_order_type'),
                'entry_spread': trade_data.get('entry_spread'),
                'exit_spread': trade_data.get('exit_spread'),
                'is_closed': trade_data.get('is_closed', close_time is not None)
            }
            
            cursor.execute(trade_insert, trade_values)
            trade_id = cursor.lastrowid
            
            # Insert parameters if they exist
            parameters = trade_data.get('parameters')
            if parameters:
                param_insert = """
                    INSERT INTO trade_parameters (trade_id, stop_loss_percent, take_profit_percent, trade_hold_minutes)
                    VALUES (%s, %s, %s, %s)
                """
                cursor.execute(param_insert, (
                    trade_id,
                    parameters.get('stop_loss_percent'),
                    parameters.get('take_profit_percent'),
                    parameters.get('trade_hold_minutes')
                ))
            
            # Insert PRT data if it exists
            prt_data = trade_data.get('prt_data')
            if prt_data:
                prt_insert = """
                    INSERT INTO prt_data (
                        trade_id, edge, prob_up, mean, p10, p90, dist1, n, timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(prt_insert, (
                    trade_id,
                    prt_data.get('edge'),
                    prt_data.get('prob_up'),
                    prt_data.get('mean'),
                    prt_data.get('p10'),
                    prt_data.get('p90'),
                    prt_data.get('dist1'),
                    prt_data.get('n'),
                    prt_data.get('timestamp')
                ))
            
            self.connection.commit()
            cursor.close()
            logger.debug(f"Trade inserted successfully: ID {trade_id}, Ticker {trade_data.get('ticker')}")
            return trade_id
            
        except Error as e:
            logger.error(f"Error inserting trade: {e}")
            if self.connection:
                self.connection.rollback()
            return None
    
    def update_trade(self, order_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Update an existing trade (e.g., when it closes).
        
        Args:
            order_id: The order_id of the trade to update
            update_data: Dictionary containing fields to update
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # Build update query dynamically
            update_fields = []
            values = []
            
            for key, value in update_data.items():
                if key in ['exit_price', 'profit_loss', 'profit_loss_percent', 'close_time',
                          'hold_time_minutes', 'close_order_id', 'is_winner', 'is_closed',
                          'exit_order_type', 'exit_spread']:
                    update_fields.append(f"{key} = %s")
                    if key == 'close_time' and isinstance(value, str):
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    values.append(value)
            
            if not update_fields:
                cursor.close()
                return False
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(order_id)
            
            update_query = f"""
                UPDATE trades 
                SET {', '.join(update_fields)}
                WHERE order_id = %s
            """
            
            cursor.execute(update_query, values)
            self.connection.commit()
            cursor.close()
            
            # If trade is closed, remove from active_trades
            if update_data.get('is_closed', False):
                self._remove_active_trade(order_id)
            
            logger.debug(f"Trade updated successfully: Order ID {order_id}")
            return True
            
        except Error as e:
            logger.error(f"Error updating trade: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def upsert_active_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Insert or update an active trade in the active_trades table.
        
        Args:
            trade_data: Dictionary containing active trade information
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # First, try to find existing trade by order_id
            cursor.execute("SELECT id FROM trades WHERE order_id = %s", (trade_data.get('order_id'),))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"Trade with order_id {trade_data.get('order_id')} not found in trades table")
                cursor.close()
                return False
            
            trade_id = result[0]
            
            # Parse datetime if needed
            time_placed = trade_data.get('time_placed')
            if isinstance(time_placed, str):
                time_placed = datetime.fromisoformat(time_placed.replace('Z', '+00:00'))
            
            # Upsert active trade
            upsert_query = """
                INSERT INTO active_trades (
                    trade_id, ticker, action, quantity, entry_price, time_placed, age_minutes, stop_loss_price
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ticker = VALUES(ticker),
                    action = VALUES(action),
                    quantity = VALUES(quantity),
                    entry_price = VALUES(entry_price),
                    time_placed = VALUES(time_placed),
                    age_minutes = VALUES(age_minutes),
                    stop_loss_price = VALUES(stop_loss_price),
                    last_updated = CURRENT_TIMESTAMP
            """
            
            cursor.execute(upsert_query, (
                trade_id,
                trade_data.get('ticker'),
                trade_data.get('action'),
                trade_data.get('quantity'),
                trade_data.get('entry_price'),
                time_placed,
                trade_data.get('age_minutes'),
                trade_data.get('stop_loss_price')
            ))
            
            self.connection.commit()
            cursor.close()
            return True
            
        except Error as e:
            logger.error(f"Error upserting active trade: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def _remove_active_trade(self, order_id: str):
        """Remove a trade from active_trades table."""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                DELETE FROM active_trades 
                WHERE trade_id IN (SELECT id FROM trades WHERE order_id = %s)
            """, (order_id,))
            self.connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error removing active trade: {e}")
    
    def insert_dashboard_snapshot(self, snapshot_data: Dict[str, Any]) -> bool:
        """
        Insert a dashboard snapshot for historical tracking.
        
        Args:
            snapshot_data: Dictionary containing dashboard statistics and metrics
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # Parse timestamp if needed - convert to UTC for storage
            timestamp = snapshot_data.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # Ensure timezone-aware UTC
                if timestamp.tzinfo is None:
                    timestamp = pytz.UTC.localize(timestamp)
                else:
                    timestamp = timestamp.astimezone(pytz.UTC)
            else:
                # Default to current time in UTC
                timestamp = datetime.now(pytz.UTC)
            
            stats = snapshot_data.get('statistics', {})
            account_metrics = snapshot_data.get('account_metrics', {})
            
            import json
            snapshot_json = json.dumps(snapshot_data)
            
            insert_query = """
                INSERT INTO dashboard_snapshots (
                    timestamp, total_trades, winning_trades, losing_trades, win_rate,
                    total_profit_loss, total_profit_loss_percent, avg_profit_per_trade,
                    avg_loss_per_trade, account_value, buying_power, cash_balance,
                    day_trading_buying_power, snapshot_data
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                timestamp,
                stats.get('total_trades', 0),
                stats.get('winning_trades', 0),
                stats.get('losing_trades', 0),
                stats.get('win_rate', 0),
                stats.get('total_profit_loss', 0),
                stats.get('total_profit_loss_percent', 0),
                stats.get('avg_profit_per_trade'),
                stats.get('avg_loss_per_trade'),
                account_metrics.get('account_value'),
                account_metrics.get('buying_power'),
                account_metrics.get('cash_balance'),
                account_metrics.get('day_trading_buying_power'),
                snapshot_json
            ))
            
            self.connection.commit()
            cursor.close()
            logger.debug("Dashboard snapshot inserted successfully")
            return True
            
        except Error as e:
            logger.error(f"Error inserting dashboard snapshot: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent trades from database.
        
        Args:
            limit: Number of recent trades to retrieve
            
        Returns:
            List of trade dictionaries
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    t.*,
                    tp.stop_loss_percent, tp.take_profit_percent, tp.trade_hold_minutes,
                    pd.edge, pd.prob_up, pd.mean, pd.p10, pd.p90, pd.dist1, pd.n, pd.timestamp as prt_timestamp
                FROM trades t
                LEFT JOIN trade_parameters tp ON t.id = tp.trade_id
                LEFT JOIN prt_data pd ON t.id = pd.trade_id
                ORDER BY t.time_placed DESC
                LIMIT %s
            """
            
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()
            
            # Convert to expected format
            trades = []
            for row in results:
                trade = dict(row)
                # Reconstruct parameters dict
                if trade.get('stop_loss_percent') is not None:
                    trade['parameters'] = {
                        'stop_loss_percent': trade.pop('stop_loss_percent'),
                        'take_profit_percent': trade.pop('take_profit_percent'),
                        'trade_hold_minutes': trade.pop('trade_hold_minutes')
                    }
                # Reconstruct prt_data dict
                if trade.get('edge') is not None:
                    trade['prt_data'] = {
                        'edge': trade.pop('edge'),
                        'prob_up': trade.pop('prob_up'),
                        'mean': trade.pop('mean'),
                        'p10': trade.pop('p10'),
                        'p90': trade.pop('p90'),
                        'dist1': trade.pop('dist1'),
                        'n': trade.pop('n'),
                        'timestamp': trade.pop('prt_timestamp')
                    }
                # Convert datetime objects to ISO strings
                for key in ['time_placed', 'close_time', 'created_at', 'updated_at']:
                    if key in trade and trade[key] and isinstance(trade[key], datetime):
                        trade[key] = trade[key].isoformat()
                
                trades.append(trade)
            
            return trades
            
        except Error as e:
            logger.error(f"Error getting recent trades: {e}")
            return []
    
    def get_active_trades(self) -> List[Dict[str, Any]]:
        """
        Get all active trades.
        
        Returns:
            List of active trade dictionaries
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
                SELECT 
                    at.*,
                    t.order_id, t.close_order_id, t.stop_loss_order_id,
                    t.take_profit_price, t.entry_order_type
                FROM active_trades at
                JOIN trades t ON at.trade_id = t.id
                ORDER BY at.time_placed ASC
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            
            # Convert datetime objects to ISO strings
            for trade in results:
                if 'time_placed' in trade and trade['time_placed'] and isinstance(trade['time_placed'], datetime):
                    trade['time_placed'] = trade['time_placed'].isoformat()
            
            return results
            
        except Error as e:
            logger.error(f"Error getting active trades: {e}")
            return []
    
    def insert_portfolio_value(self, portfolio_value: float, account_value: Optional[float] = None, 
                               cumulative_pnl: Optional[float] = None, timestamp: Optional[datetime] = None) -> bool:
        """
        Insert a portfolio value snapshot into the portfolio_value_history table.
        
        Args:
            portfolio_value: Current portfolio value
            account_value: Current account value (optional)
            cumulative_pnl: Cumulative profit/loss (optional)
            timestamp: Timestamp for this snapshot (defaults to now)
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # Convert timestamp to UTC for storage
            if timestamp is None:
                timestamp = datetime.now(pytz.UTC)
            elif isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # Ensure timezone-aware UTC
                if timestamp.tzinfo is None:
                    timestamp = pytz.UTC.localize(timestamp)
                else:
                    timestamp = timestamp.astimezone(pytz.UTC)
            elif hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                # If timestamp is timezone-aware, convert to UTC
                timestamp = timestamp.astimezone(pytz.UTC)
            else:
                # If timestamp is naive, assume it's UTC and localize
                timestamp = pytz.UTC.localize(timestamp)
            
            insert_query = """
                INSERT INTO portfolio_value_history (timestamp, portfolio_value, account_value, cumulative_pnl)
                VALUES (%s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                timestamp,
                portfolio_value,
                account_value,
                cumulative_pnl
            ))
            
            self.connection.commit()
            cursor.close()
            logger.debug(f"Portfolio value snapshot inserted: ${portfolio_value:.2f}")
            return True
            
        except Error as e:
            logger.error(f"Error inserting portfolio value: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def get_portfolio_value_over_time(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get portfolio value history from the portfolio_value_history table.
        
        Args:
            limit: Maximum number of records to retrieve (default 1000)
            
        Returns:
            List of dicts with 'timestamp' and 'portfolio_value' keys, sorted by timestamp
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
                SELECT timestamp, portfolio_value
                FROM portfolio_value_history
                ORDER BY timestamp ASC
                LIMIT %s
            """
            
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()
            
            # Convert to expected format
            portfolio_history = []
            for row in results:
                timestamp = row['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.isoformat()
                
                portfolio_history.append({
                    'timestamp': timestamp,
                    'portfolio_value': float(row['portfolio_value'])
                })
            
            return portfolio_history
            
        except Error as e:
            logger.error(f"Error getting portfolio value over time: {e}")
            return []
    
    def insert_beta_over_time(self, portfolio_beta: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Insert a portfolio beta snapshot into the beta_over_time table.
        
        Args:
            portfolio_beta: Current portfolio beta value
            timestamp: Timestamp for this snapshot (defaults to now)
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            
            # Convert timestamp to UTC for storage
            if timestamp is None:
                timestamp = datetime.now(pytz.UTC)
            elif isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # Ensure timezone-aware UTC
                if timestamp.tzinfo is None:
                    timestamp = pytz.UTC.localize(timestamp)
                else:
                    timestamp = timestamp.astimezone(pytz.UTC)
            elif hasattr(timestamp, 'tzinfo') and timestamp.tzinfo is not None:
                # If timestamp is timezone-aware, convert to UTC
                timestamp = timestamp.astimezone(pytz.UTC)
            else:
                # If timestamp is naive, assume it's UTC and localize
                timestamp = pytz.UTC.localize(timestamp)
            
            insert_query = """
                INSERT INTO beta_over_time (timestamp, portfolio_beta)
                VALUES (%s, %s)
            """
            
            cursor.execute(insert_query, (
                timestamp,
                portfolio_beta
            ))
            
            self.connection.commit()
            cursor.close()
            logger.debug(f"Portfolio beta snapshot inserted: {portfolio_beta:.6f}")
            return True
            
        except Error as e:
            logger.error(f"Error inserting portfolio beta: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def get_beta_over_time(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get portfolio beta history from the beta_over_time table.
        
        Args:
            limit: Maximum number of records to retrieve (default 1000)
            
        Returns:
            List of dicts with 'timestamp' and 'portfolio_beta' keys, sorted by timestamp
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            
            query = """
                SELECT timestamp, portfolio_beta
                FROM beta_over_time
                ORDER BY timestamp ASC
                LIMIT %s
            """
            
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()
            
            # Convert to expected format
            beta_history = []
            for row in results:
                timestamp = row['timestamp']
                if isinstance(timestamp, datetime):
                    timestamp = timestamp.isoformat()
                
                beta_history.append({
                    'timestamp': timestamp,
                    'portfolio_beta': float(row['portfolio_beta'])
                })
            
            return beta_history
            
        except Error as e:
            logger.error(f"Error getting beta over time: {e}")
            return []
    
    def get_all_tickers_from_trades(self) -> List[str]:
        """
        Get all unique tickers from the trades table.
        
        Returns:
            List of unique ticker symbols
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT DISTINCT ticker FROM trades ORDER BY ticker")
            results = cursor.fetchall()
            cursor.close()
            
            tickers = [row[0] for row in results if row[0]]
            return tickers
        except Error as e:
            logger.error(f"Error getting tickers from trades: {e}")
            return []
    
    def get_des_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get DES data for a ticker from the database.
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with DES data or None if not found
        """
        self._reconnect_if_needed()
        
        try:
            cursor = self.connection.cursor(dictionary=True)
            query_ticker = ticker.upper()
            cursor.execute("""
                SELECT * FROM des_data WHERE ticker = %s
            """, (query_ticker,))
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                logger.debug(f"Database query for {query_ticker}: Found record, beta field = {result.get('beta')}")
            else:
                logger.debug(f"Database query for {query_ticker}: No record found")
            
            if result:
                # Parse JSON fields
                import json
                if result.get('eps_estimates'):
                    result['eps_estimates'] = json.loads(result['eps_estimates']) if isinstance(result['eps_estimates'], str) else result['eps_estimates']
                
                # Reconstruct snapshot dict from individual fields for backward compatibility
                snapshot = {}
                if result.get('exchange'):
                    snapshot['Exchange'] = result['exchange']
                if result.get('currency'):
                    snapshot['Currency'] = result['currency']
                if result.get('float_value'):
                    snapshot['Float'] = result['float_value']
                if result.get('employees'):
                    snapshot['Employees'] = result['employees']
                if result.get('insiders'):
                    snapshot['Insiders'] = result['insiders']
                if result.get('institutions'):
                    snapshot['Institutions'] = result['institutions']
                if result.get('p_sales'):
                    snapshot['P/Sales'] = result['p_sales']
                if result.get('p_book'):
                    snapshot['P/Book'] = result['p_book']
                if result.get('ev_ebitda'):
                    snapshot['EV/EBITDA'] = result['ev_ebitda']
                if result.get('ev_r'):
                    snapshot['EV/R'] = result['ev_r']
                if result.get('ev'):
                    snapshot['EV'] = result['ev']
                if result.get('trl_pe'):
                    snapshot['Trl P/E'] = result['trl_pe']
                if result.get('fwd_pe'):
                    snapshot['Fwd P/E'] = result['fwd_pe']
                if result.get('trl_yld'):
                    snapshot['Trl Yld'] = result['trl_yld']
                if result.get('fwd_yld'):
                    snapshot['Fwd Yld'] = result['fwd_yld']
                if result.get('five_y_avg_yld'):
                    snapshot['5Y Avg Yld'] = result['five_y_avg_yld']
                if result.get('payout_ratio'):
                    snapshot['Payout R'] = result['payout_ratio']
                if result.get('ex_div_date'):
                    # Convert date to string format "YYYY-MM-DD"
                    ex_div_date = result['ex_div_date']
                    if hasattr(ex_div_date, 'strftime'):
                        snapshot['Ex Div Date'] = ex_div_date.strftime('%Y-%m-%d')
                    else:
                        snapshot['Ex Div Date'] = str(ex_div_date)
                if result.get('div_date'):
                    # Convert date to string format "YYYY-MM-DD"
                    div_date = result['div_date']
                    if hasattr(div_date, 'strftime'):
                        snapshot['Div Date'] = div_date.strftime('%Y-%m-%d')
                    else:
                        snapshot['Div Date'] = str(div_date)
                if result.get('beta'):
                    snapshot['Beta'] = result['beta']
                if result.get('short'):
                    snapshot['Short'] = result['short']
                if result.get('short_ratio'):
                    snapshot['Short R'] = result['short_ratio']
                
                result['snapshot'] = snapshot if snapshot else None
            
            return result
        except Error as e:
            logger.error(f"Error getting DES data for {ticker}: {e}")
            return None
    
    def get_tickers_needing_des_update(self, max_age_days: int = 7) -> List[str]:
        """
        Get list of tickers that need DES data or have data older than max_age_days.
        
        Args:
            max_age_days: Maximum age in days before data needs updating
            
        Returns:
            List of ticker symbols that need DES data
        """
        self._reconnect_if_needed()
        
        try:
            # Get all unique tickers from trades
            all_tickers = self.get_all_tickers_from_trades()
            
            if not all_tickers:
                return []
            
            # Get tickers that have DES data and check their age
            cursor = self.connection.cursor()
            placeholders = ','.join(['%s'] * len(all_tickers))
            cursor.execute(f"""
                SELECT ticker, updated_at 
                FROM des_data 
                WHERE ticker IN ({placeholders})
            """, all_tickers)
            
            existing_des = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.close()
            
            # Calculate cutoff date
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            # Find tickers that need updating
            tickers_needing_update = []
            for ticker in all_tickers:
                if ticker not in existing_des:
                    # No DES data exists
                    tickers_needing_update.append(ticker)
                elif existing_des[ticker] < cutoff_date:
                    # DES data is too old
                    tickers_needing_update.append(ticker)
            
            return tickers_needing_update
        except Error as e:
            logger.error(f"Error getting tickers needing DES update: {e}")
            return []
    
    def upsert_des_data(self, ticker: str, des_data: Dict[str, Any]) -> bool:
        """
        Insert or update DES data for a ticker.
        Note: Analyst ratings are excluded as per requirements.
        
        Args:
            ticker: Ticker symbol
            des_data: DES data dictionary from DESCommand.extract_data()
            
        Returns:
            True if successful, False otherwise
        """
        self._reconnect_if_needed()
        
        try:
            import json
            from datetime import datetime
            
            # Extract company info
            company_info = des_data.get('company_info', {})
            
            # Prepare EPS estimates as JSON
            eps_estimates = des_data.get('eps_estimates', {})
            eps_estimates_json = json.dumps(eps_estimates) if eps_estimates else None
            
            # Extract snapshot fields individually
            snapshot = des_data.get('snapshot', {})
            
            # Helper function to parse dates (format: "2026-01-15")
            def parse_date(date_str):
                if not date_str:
                    return None
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
                except (ValueError, TypeError):
                    return None
            
            cursor = self.connection.cursor()
            
            upsert_query = """
                INSERT INTO des_data (
                    ticker, company_name, asset_class, logo_url, website, address, ceo,
                    description, eps_estimates,
                    exchange, currency, float_value, employees, insiders, institutions,
                    p_sales, p_book, ev_ebitda, ev_r, ev,
                    trl_pe, fwd_pe, trl_yld, fwd_yld, five_y_avg_yld,
                    payout_ratio, ex_div_date, div_date, beta, short, short_ratio
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON DUPLICATE KEY UPDATE
                    company_name = VALUES(company_name),
                    asset_class = VALUES(asset_class),
                    logo_url = VALUES(logo_url),
                    website = VALUES(website),
                    address = VALUES(address),
                    ceo = VALUES(ceo),
                    description = VALUES(description),
                    eps_estimates = VALUES(eps_estimates),
                    exchange = VALUES(exchange),
                    currency = VALUES(currency),
                    float_value = VALUES(float_value),
                    employees = VALUES(employees),
                    insiders = VALUES(insiders),
                    institutions = VALUES(institutions),
                    p_sales = VALUES(p_sales),
                    p_book = VALUES(p_book),
                    ev_ebitda = VALUES(ev_ebitda),
                    ev_r = VALUES(ev_r),
                    ev = VALUES(ev),
                    trl_pe = VALUES(trl_pe),
                    fwd_pe = VALUES(fwd_pe),
                    trl_yld = VALUES(trl_yld),
                    fwd_yld = VALUES(fwd_yld),
                    five_y_avg_yld = VALUES(five_y_avg_yld),
                    payout_ratio = VALUES(payout_ratio),
                    ex_div_date = VALUES(ex_div_date),
                    div_date = VALUES(div_date),
                    beta = VALUES(beta),
                    short = VALUES(short),
                    short_ratio = VALUES(short_ratio),
                    updated_at = CURRENT_TIMESTAMP
            """
            
            # Extract ticker from des_data if not provided (remove " US" suffix if present)
            if not ticker:
                ticker = des_data.get('ticker', '').replace(' US', '').upper()
            else:
                ticker = ticker.upper()
            
            cursor.execute(upsert_query, (
                ticker,
                company_info.get('company_name'),
                company_info.get('asset_class'),
                company_info.get('logo_url'),
                company_info.get('website'),
                company_info.get('address'),
                company_info.get('ceo'),
                des_data.get('description'),
                eps_estimates_json,
                # Snapshot fields
                snapshot.get('Exchange'),
                snapshot.get('Currency'),
                snapshot.get('Float'),
                snapshot.get('Employees'),
                snapshot.get('Insiders'),
                snapshot.get('Institutions'),
                snapshot.get('P/Sales'),
                snapshot.get('P/Book'),
                snapshot.get('EV/EBITDA'),
                snapshot.get('EV/R'),
                snapshot.get('EV'),
                snapshot.get('Trl P/E'),
                snapshot.get('Fwd P/E'),
                snapshot.get('Trl Yld'),
                snapshot.get('Fwd Yld'),
                snapshot.get('5Y Avg Yld'),
                snapshot.get('Payout R'),
                parse_date(snapshot.get('Ex Div Date')),
                parse_date(snapshot.get('Div Date')),
                snapshot.get('Beta'),
                snapshot.get('Short'),
                snapshot.get('Short R')
            ))
            
            self.connection.commit()
            cursor.close()
            logger.debug(f"DES data upserted for {ticker}")
            return True
            
        except Error as e:
            logger.error(f"Error upserting DES data for {ticker}: {e}")
            if self.connection:
                self.connection.rollback()
            return False
    
    def close(self):
        """Close database connection."""
        if self.connection and self.connection.is_connected():
            self.connection.close()
            logger.debug("Database connection closed")


# Global database manager instance
_db_manager_instance = None


def get_db_manager() -> Optional[DatabaseManager]:
    """
    Get or create a global database manager instance.
    This ensures we reuse the same connection across the application.
    
    Returns:
        DatabaseManager instance, or None if connection fails
    """
    global _db_manager_instance
    
    if _db_manager_instance is None:
        try:
            _db_manager_instance = DatabaseManager()
        except Exception as e:
            logger.error(f"Failed to create database manager: {e}")
            return None
    
    return _db_manager_instance

