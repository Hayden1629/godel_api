#!/usr/bin/env python3
"""
Script to mark all trades in the active_trades table as closed.

This is useful when trades didn't close properly for whatever reason
and need to be manually closed in the database.
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from loguru import logger

# Add parent directory to path to import config and db_manager
sys.path.insert(0, str(Path(__file__).parent))

from config import DB_CONFIG
from db_manager import DatabaseManager, get_db_manager


def get_all_active_trades(db: DatabaseManager) -> List[Dict]:
    """Get all trades currently in the active_trades table."""
    db._reconnect_if_needed()
    
    try:
        cursor = db.connection.cursor(dictionary=True)
        # Get all active trades with their corresponding trade info
        query = """
            SELECT 
                at.id as active_trade_id,
                at.trade_id,
                at.ticker,
                at.action,
                at.quantity,
                at.entry_price,
                at.time_placed,
                t.order_id,
                t.exit_price,
                t.close_time,
                t.profit_loss,
                t.profit_loss_percent,
                t.is_closed,
                t.close_order_id
            FROM active_trades at
            JOIN trades t ON at.trade_id = t.id
            ORDER BY at.time_placed ASC
        """
        cursor.execute(query)
        trades = cursor.fetchall()
        cursor.close()
        
        logger.info(f"Found {len(trades)} active trades in active_trades table")
        return trades
    except Exception as e:
        logger.error(f"Error getting active trades from database: {e}")
        return []


def close_trade(db: DatabaseManager, trade: Dict) -> bool:
    """Mark a trade as closed in the trades table."""
    order_id = trade['order_id']
    ticker = trade['ticker']
    
    # Prepare update data
    update_data = {
        'is_closed': True
    }
    
    # If trade already has close info, keep it; otherwise set close_time to now
    if not trade.get('close_time'):
        update_data['close_time'] = datetime.now()
    
    # If no exit_order_type set, default to MANUAL_CLOSE
    if not trade.get('exit_order_type'):
        update_data['exit_order_type'] = 'MANUAL_CLOSE'
    
    # Update the trade in database (this will also remove it from active_trades)
    try:
        success = db.update_trade(order_id, update_data)
        if success:
            logger.info(f"✅ Closed trade {ticker} (order_id: {order_id})")
            return True
        else:
            logger.warning(f"Failed to close trade {ticker} (order_id: {order_id})")
            return False
    except Exception as e:
        logger.error(f"Error closing trade {ticker} (order_id: {order_id}): {e}")
        return False


def main():
    """Main function to close all active trades."""
    logger.info("=" * 60)
    logger.info("Close All Active Trades")
    logger.info("=" * 60)
    logger.info("")
    
    # Get database connection
    db = get_db_manager()
    if not db:
        logger.error("Failed to connect to database")
        return False
    
    # Get all active trades
    active_trades = get_all_active_trades(db)
    
    if not active_trades:
        logger.info("No active trades found in active_trades table - nothing to close")
        return True
    
    logger.info(f"\nFound {len(active_trades)} active trades to close")
    logger.info("Closing all trades...\n")
    
    # Close all trades
    closed_count = 0
    error_count = 0
    
    for trade in active_trades:
        if close_trade(db, trade):
            closed_count += 1
        else:
            error_count += 1
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("Summary")
    logger.info("=" * 60)
    logger.info(f"✅ Successfully closed: {closed_count}")
    logger.info(f"❌ Errors: {error_count}")
    logger.info(f"📊 Total active trades processed: {len(active_trades)}")
    
    # Verify active_trades table is now empty
    remaining = get_all_active_trades(db)
    if remaining:
        logger.warning(f"⚠️  Warning: {len(remaining)} trades still remain in active_trades table")
    else:
        logger.info("✅ Verified: active_trades table is now empty")
    
    # Close database connection
    db.close()
    
    return closed_count > 0


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
