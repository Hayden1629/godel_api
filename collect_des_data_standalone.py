"""
Standalone DES Data Collection Script

This script runs independently from the algo loop to collect and update DES (Description) 
data for all tickers found in the trades database. It ensures all tickers have up-to-date 
DES information (updates if data is more than 7 days old).

This script is designed to run on a separate computer from the main algo loop.

Usage:
    python collect_des_data_standalone.py
"""

import sys
from pathlib import Path
import time
from datetime import datetime, timedelta
from loguru import logger
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from godel_core import GodelTerminalController
from commands.des_command import DESCommand
from db_manager import DatabaseManager
from config import GODEL_USERNAME, GODEL_PASSWORD, DB_CONFIG

# Configuration
MAX_AGE_DAYS = 7  # Update DES data if older than this
BATCH_SIZE = 5  # Process this many tickers before taking a break
DELAY_BETWEEN_TICKERS = 3  # Seconds to wait between DES calls
DELAY_BETWEEN_BATCHES = 10  # Seconds to wait between batches


def setup_logging():
    """Configure logging for the standalone script."""
    logger.remove()  # Remove default handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    logger.add(
        "des_collection.log",
        rotation="10 MB",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level="DEBUG"
    )


def initialize_godel_controller() -> Optional[GodelTerminalController]:
    """
    Initialize and connect to Godel Terminal.
    
    Returns:
        GodelTerminalController instance or None if failed
    """
    try:
        logger.info("🔌 Initializing Godel Terminal controller...")
        controller = GodelTerminalController()
        controller.connect()
        controller.login(GODEL_USERNAME, GODEL_PASSWORD)
        controller.load_layout("dev")
        controller.register_command('DES', DESCommand)
        logger.info("✅ Godel controller initialized successfully")
        return controller
    except Exception as e:
        logger.error(f"❌ Failed to initialize Godel controller: {e}")
        return None


def collect_des_for_ticker(controller: GodelTerminalController, ticker: str) -> Optional[dict]:
    """
    Collect DES data for a single ticker.
    
    Args:
        controller: GodelTerminalController instance
        ticker: Ticker symbol
        
    Returns:
        DES data dictionary or None if failed
    """
    try:
        logger.info(f"📊 Collecting DES data for {ticker}...")
        result, des_command = controller.execute_command('DES', ticker, 'EQ')
        
        if not result.get('success'):
            logger.warning(f"DES command failed for {ticker}: {result.get('error')}")
            if des_command:
                des_command.close()
            return None
        
        des_data = result.get('data', {})
        if not des_data:
            logger.warning(f"No data returned from DES for {ticker}")
            if des_command:
                des_command.close()
            return None
        
        # Close the DES window
        if des_command:
            des_command.close()
        
        logger.info(f"✅ Successfully collected DES data for {ticker}")
        return des_data
        
    except Exception as e:
        logger.error(f"Error collecting DES data for {ticker}: {e}")
        return None


def main():
    """Main execution function."""
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("DES Data Collection Script - Standalone")
    logger.info("=" * 60)
    
    # Initialize database connection
    try:
        logger.info("📦 Connecting to database...")
        db = DatabaseManager()
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        logger.error("Please ensure database credentials are configured correctly")
        return 1
    
    # Initialize Godel controller
    controller = initialize_godel_controller()
    if not controller:
        logger.error("Failed to initialize Godel controller. Exiting.")
        db.close()
        return 1
    
    try:
        # Get list of tickers that need DES data
        logger.info(f"🔍 Finding tickers that need DES data (max age: {MAX_AGE_DAYS} days)...")
        tickers_needing_update = db.get_tickers_needing_des_update(max_age_days=MAX_AGE_DAYS)
        
        if not tickers_needing_update:
            logger.info("✅ All tickers have up-to-date DES data!")
            return 0
        
        logger.info(f"📋 Found {len(tickers_needing_update)} tickers needing DES data: {tickers_needing_update[:10]}{'...' if len(tickers_needing_update) > 10 else ''}")
        
        # Process tickers in batches
        total_processed = 0
        total_successful = 0
        total_failed = 0
        
        for i in range(0, len(tickers_needing_update), BATCH_SIZE):
            batch = tickers_needing_update[i:i + BATCH_SIZE]
            logger.info(f"\n📦 Processing batch {i // BATCH_SIZE + 1} ({len(batch)} tickers)...")
            
            for ticker in batch:
                total_processed += 1
                
                # Collect DES data
                des_data = collect_des_for_ticker(controller, ticker)
                
                if des_data:
                    # Store in database (excluding analyst_ratings)
                    success = db.upsert_des_data(ticker, des_data)
                    if success:
                        total_successful += 1
                        logger.info(f"💾 Saved DES data for {ticker} to database")
                    else:
                        total_failed += 1
                        logger.error(f"❌ Failed to save DES data for {ticker} to database")
                else:
                    total_failed += 1
                    logger.warning(f"⚠️  Failed to collect DES data for {ticker}")
                
                # Delay between tickers
                if ticker != batch[-1]:  # Don't delay after last ticker in batch
                    time.sleep(DELAY_BETWEEN_TICKERS)
            
            # Delay between batches (except after last batch)
            if i + BATCH_SIZE < len(tickers_needing_update):
                logger.info(f"⏸️  Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
                time.sleep(DELAY_BETWEEN_BATCHES)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 Collection Summary")
        logger.info("=" * 60)
        logger.info(f"Total tickers processed: {total_processed}")
        logger.info(f"✅ Successful: {total_successful}")
        logger.info(f"❌ Failed: {total_failed}")
        logger.info(f"📈 Success rate: {(total_successful / total_processed * 100) if total_processed > 0 else 0:.1f}%")
        logger.info("=" * 60)
        
        return 0 if total_failed == 0 else 1
        
    except KeyboardInterrupt:
        logger.info("\n🛑 Script interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup
        if controller:
            try:
                logger.info("🧹 Cleaning up Godel controller...")
                controller.close_all_windows()
                controller.disconnect()
                logger.info("✅ Controller closed successfully")
            except Exception as e:
                logger.warning(f"Error closing controller: {e}")
        
        if db:
            db.close()
            logger.info("✅ Database connection closed")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

