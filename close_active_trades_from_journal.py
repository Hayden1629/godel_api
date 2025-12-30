#!/usr/bin/env python3
"""
Script to mark all active trades in the MySQL database as closed,
using data from trade_journal.json to get exit prices and close times.

This is useful when trades were closed but not properly saved to the database,
or when you need to sync the database with the journal file.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger

# Add parent directory to path to import config and db_manager
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_CONFIG
from db_manager import DatabaseManager, get_db_manager

# Import TRADE_JOURNAL_FILE from algo_loop
TRADE_JOURNAL_FILE = "trade_journal.json"


def load_trade_journal(journal_path: Path) -> List[Dict]:
    """Load trades from trade_journal.json."""
    if not journal_path.exists():
        logger.error(f"Trade journal file not found: {journal_path}")
        return []
    
    try:
        with open(journal_path, 'r') as f:
            trades = json.load(f)
        logger.info(f"Loaded {len(trades)} trades from journal file")
        return trades
    except Exception as e:
        logger.error(f"Error loading trade journal: {e}")
        return []


def get_active_trades_from_db(db: DatabaseManager) -> List[Dict]:
    """Get all active (non-closed) trades from the database, including close_order_id if it exists."""
    db._reconnect_if_needed()
    
    try:
        cursor = db.connection.cursor(dictionary=True)
        # Get trades that are marked as not closed, OR trades that have close_order_id but is_closed is still False
        query = """
            SELECT id, ticker, action, order_id, entry_price, time_placed, quantity,
                   close_order_id, exit_price, close_time, profit_loss, profit_loss_percent
            FROM trades
            WHERE (is_closed = FALSE OR is_closed IS NULL)
               OR (close_order_id IS NOT NULL AND (is_closed = FALSE OR is_closed IS NULL))
        """
        cursor.execute(query)
        trades = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(trades)} active trades in database")
        return trades
    except Exception as e:
        logger.error(f"Error getting active trades from database: {e}")
        return []


def match_trade_by_order_id(journal_trades: List[Dict], order_id: str) -> Optional[Dict]:
    """Find a trade in the journal by order_id."""
    for trade in journal_trades:
        if trade.get('order_id') == order_id:
            return trade
    return None


def update_trade_from_journal(db: DatabaseManager, db_trade: Dict, journal_trade: Dict) -> bool:
    """Update a database trade with information from the journal."""
    order_id = db_trade['order_id']
    
    # Extract close information from journal trade
    exit_price = journal_trade.get('exit_price')
    close_time_str = journal_trade.get('close_time')
    close_order_id = journal_trade.get('close_order_id')
    exit_order_type = journal_trade.get('exit_order_type', 'MANUAL_CLOSE')
    profit_loss = journal_trade.get('profit_loss')
    profit_loss_percent = journal_trade.get('profit_loss_percent')
    hold_time_minutes = journal_trade.get('hold_time_minutes')
    is_winner = journal_trade.get('is_winner')
    
    if exit_price is None:
        logger.warning(f"Trade {db_trade['ticker']} (order_id: {order_id}) has no exit_price in journal - skipping")
        return False
    
    if close_time_str is None:
        logger.warning(f"Trade {db_trade['ticker']} (order_id: {order_id}) has no close_time in journal - skipping")
        return False
    
    # Parse close_time
    try:
        if isinstance(close_time_str, str):
            # Handle ISO format with timezone
            if close_time_str.endswith('Z'):
                close_time_str = close_time_str.replace('Z', '+00:00')
            close_time = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
        else:
            logger.warning(f"Invalid close_time format for {db_trade['ticker']}: {close_time_str}")
            return False
    except Exception as e:
        logger.error(f"Error parsing close_time for {db_trade['ticker']}: {e}")
        return False
    
    # Calculate is_winner if not provided
    if is_winner is None and profit_loss is not None:
        is_winner = profit_loss > 0
    
    # Prepare update data
    update_data = {
        'exit_price': exit_price,
        'profit_loss': profit_loss,
        'profit_loss_percent': profit_loss_percent,
        'close_time': close_time.isoformat(),
        'hold_time_minutes': hold_time_minutes,
        'close_order_id': close_order_id,
        'is_winner': is_winner,
        'is_closed': True,
        'exit_order_type': exit_order_type or 'MANUAL_CLOSE',
        'exit_spread': journal_trade.get('exit_spread')
    }
    
    # Update the trade in database
    try:
        success = db.update_trade(order_id, update_data)
        if success:
            logger.info(f"✅ Updated trade {db_trade['ticker']} (order_id: {order_id}) - "
                       f"Exit: ${exit_price:.4f}, P&L: ${profit_loss:.2f} ({profit_loss_percent:.2f}%)")
            return True
        else:
            logger.warning(f"Failed to update trade {db_trade['ticker']} (order_id: {order_id})")
            return False
    except Exception as e:
        logger.error(f"Error updating trade {db_trade['ticker']} (order_id: {order_id}): {e}")
        return False


def main():
    """Main function to close all active trades from journal."""
    logger.info("=" * 60)
    logger.info("Close Active Trades from Journal")
    logger.info("=" * 60)
    logger.info("")
    
    # Get database connection
    db = get_db_manager()
    if not db:
        logger.error("Failed to connect to database")
        return False
    
    # Load trade journal
    script_dir = Path(__file__).parent
    journal_path = script_dir / TRADE_JOURNAL_FILE
    journal_trades = load_trade_journal(journal_path)
    
    if not journal_trades:
        logger.error("No trades found in journal file")
        return False
    
    # Get active trades from database
    active_trades = get_active_trades_from_db(db)
    
    if not active_trades:
        logger.info("No active trades found in database - nothing to update")
        return True
    
    logger.info(f"\nFound {len(active_trades)} active trades to potentially close")
    logger.info("Matching with journal trades...\n")
    
    # Match and update trades
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    for db_trade in active_trades:
        order_id = db_trade['order_id']
        ticker = db_trade['ticker']
        
        # First, check if trade already has close information in database (from force close)
        if db_trade.get('close_order_id') and db_trade.get('exit_price'):
            # Trade was closed but not marked as is_closed - just update the flag
            logger.info(f"Found close info in database for {ticker} (order_id: {order_id}) - marking as closed")
            update_data = {
                'is_closed': True,
                'exit_order_type': 'FORCE_CLOSE_MARKET'
            }
            # Use existing close_time if available, otherwise use now
            if db_trade.get('close_time'):
                if hasattr(db_trade['close_time'], 'isoformat'):
                    update_data['close_time'] = db_trade['close_time'].isoformat()
                else:
                    update_data['close_time'] = str(db_trade['close_time'])
            else:
                update_data['close_time'] = datetime.now().isoformat()
            
            # Calculate P&L if not already set
            if db_trade.get('profit_loss') is None and db_trade.get('exit_price') and db_trade.get('entry_price'):
                entry_price = float(db_trade['entry_price'])
                exit_price = float(db_trade['exit_price'])
                quantity = int(db_trade['quantity'])
                action = db_trade['action']
                
                if action == 'LONG':
                    profit_loss = (exit_price - entry_price) * quantity
                else:  # SHORT
                    profit_loss = (entry_price - exit_price) * quantity
                
                profit_loss_percent = (profit_loss / (entry_price * quantity)) * 100
                update_data['profit_loss'] = profit_loss
                update_data['profit_loss_percent'] = profit_loss_percent
                update_data['is_winner'] = profit_loss > 0
            
            if db.update_trade(order_id, update_data):
                logger.info(f"✅ Marked {ticker} as closed (already had close info in database)")
                updated_count += 1
            else:
                error_count += 1
            continue
        
        # Find matching trade in journal
        journal_trade = match_trade_by_order_id(journal_trades, order_id)
        
        if not journal_trade:
            # No journal entry - just mark as closed with minimal info
            logger.warning(f"⚠️  No matching journal entry for {ticker} (order_id: {order_id})")
            logger.info(f"   Marking as closed anyway (exit_price will be NULL)")
            
            update_data = {
                'is_closed': True,
                'close_time': datetime.now().isoformat(),
                'exit_order_type': 'FORCE_CLOSE_MARKET'
                # exit_price, profit_loss, etc. will remain NULL
            }
            
            if db.update_trade(order_id, update_data):
                logger.info(f"✅ Marked {ticker} as closed (no close price available)")
                updated_count += 1
            else:
                error_count += 1
            continue
        
        # Check if journal trade is actually closed
        if not journal_trade.get('exit_price') or not journal_trade.get('close_time'):
            logger.warning(f"⚠️  Journal entry for {ticker} (order_id: {order_id}) is not closed - skipping")
            not_found_count += 1
            continue
        
        # Update trade in database
        if update_trade_from_journal(db, db_trade, journal_trade):
            updated_count += 1
        else:
            error_count += 1
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"✅ Successfully updated: {updated_count}")
    logger.info(f"⚠️  Not found in journal: {not_found_count}")
    logger.info(f"❌ Errors: {error_count}")
    logger.info(f"📊 Total active trades processed: {len(active_trades)}")
    
    # Close database connection
    db.close()
    
    return updated_count > 0


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)

