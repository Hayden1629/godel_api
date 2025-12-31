"""
Standalone DES Data Collection Script - Continuous Mode

This script runs independently from the algo loop to collect and update DES (Description) 
data for all tickers found in the trades database. It runs continuously, checking every 
10 minutes for tickers that need DES data updates.

The script will process:
- Tickers that haven't been processed yet (no DES data)
- Tickers whose last update was more than 7 days ago

After each processing cycle, the script disconnects from the database and waits 10 minutes 
before checking again. The Godel controller remains connected between cycles for efficiency.

This script is designed to run on a separate computer from the main algo loop.

Usage:
    python collect_des_data_standalone.py
    
Press Ctrl+C to stop the script gracefully.
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
from commands.most_command import MOSTCommand
from db_manager import DatabaseManager
from config import GODEL_USERNAME, GODEL_PASSWORD, DB_CONFIG

# Configuration
MAX_AGE_DAYS = 7  # Update DES data if older than this
BATCH_SIZE = 5  # Process this many tickers before taking a break
DELAY_BETWEEN_TICKERS = 3  # Seconds to wait between DES calls
DELAY_BETWEEN_BATCHES = 10  # Seconds to wait between batches
CHECK_INTERVAL_SECONDS = 600  # Check for new tickers every 10 minutes (600 seconds)
TICKER_LIST_FILE = "tickers_to_process.txt"  # File containing space-separated tickers to process


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
        controller.register_command('MOST', MOSTCommand)
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


def get_tickers_from_most(controller: GodelTerminalController) -> List[str]:
    """
    Get list of tickers from MOST command with 50 billion market cap filter.
    
    Args:
        controller: GodelTerminalController instance
        
    Returns:
        List of ticker symbols
    """
    try:
        logger.info("📊 Fetching tickers from MOST (50B+ market cap)...")
        most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=100)
        
        # Execute MOST command - it will automatically set market cap to FIFTY_BILLION
        result = most_cmd.execute()
        
        if not result.get('success'):
            logger.warning(f"MOST command failed: {result.get('error')}")
            if most_cmd.window:
                most_cmd.close()
            return []
        
        # Get tickers from the result
        data = result.get('data', {})
        tickers = data.get('tickers', [])
        
        # Close the MOST window
        if most_cmd.window:
            most_cmd.close()
        
        if tickers:
            logger.info(f"✅ Found {len(tickers)} tickers from MOST: {tickers[:10]}{'...' if len(tickers) > 10 else ''}")
        else:
            logger.warning("⚠️  No tickers found in MOST results")
        
        return tickers
        
    except Exception as e:
        logger.error(f"Error getting tickers from MOST: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_tickers_from_file(file_path: str) -> List[str]:
    """
    Read tickers from a .txt file (space-separated).
    
    Args:
        file_path: Path to the ticker list file
        
    Returns:
        List of ticker symbols (empty list if file doesn't exist or is empty)
    """
    try:
        ticker_file = Path(file_path)
        
        if not ticker_file.exists():
            return []
        
        # Read file content
        with open(ticker_file, 'r') as f:
            content = f.read().strip()
        
        # If file is empty or blank, return empty list
        if not content:
            return []
        
        # Split by spaces and filter out empty strings
        tickers = [ticker.upper().strip() for ticker in content.split() if ticker.strip()]
        
        return tickers
        
    except Exception as e:
        logger.warning(f"Error reading ticker list file {file_path}: {e}")
        return []


def process_tickers_from_file(controller: GodelTerminalController, db: DatabaseManager, 
                               file_tickers: List[str]) -> tuple[int, int, int]:
    """
    Process tickers from file.
    
    Args:
        controller: GodelTerminalController instance
        db: DatabaseManager instance
        file_tickers: List of tickers from file
        
    Returns:
        Tuple of (total_processed, total_successful, total_failed)
    """
    if not file_tickers:
        return (0, 0, 0)
    
    logger.info(f"📋 Processing {len(file_tickers)} tickers from file: {file_tickers[:10]}{'...' if len(file_tickers) > 10 else ''}")
    
    # Process tickers in batches
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    for i in range(0, len(file_tickers), BATCH_SIZE):
        batch = file_tickers[i:i + BATCH_SIZE]
        logger.info(f"\n📦 Processing file batch {i // BATCH_SIZE + 1} ({len(batch)} tickers)...")
        
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
        if i + BATCH_SIZE < len(file_tickers):
            logger.info(f"⏸️  Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)
    
    return (total_processed, total_successful, total_failed)


def process_new_tickers_from_most(controller: GodelTerminalController, db: DatabaseManager, 
                                   most_tickers: List[str]) -> tuple[int, int, int]:
    """
    Process tickers from MOST that aren't in the database yet.
    
    Args:
        controller: GodelTerminalController instance
        db: DatabaseManager instance
        most_tickers: List of tickers from MOST command
        
    Returns:
        Tuple of (total_processed, total_successful, total_failed)
    """
    if not most_tickers:
        return (0, 0, 0)
    
    # Get all tickers currently in database
    logger.info("🔍 Checking which MOST tickers are already in database...")
    db_tickers = set(db.get_all_tickers_from_trades())
    
    # Find tickers from MOST that aren't in database
    new_tickers = [ticker.upper() for ticker in most_tickers if ticker.upper() not in db_tickers]
    
    if not new_tickers:
        logger.info("✅ All MOST tickers are already in the database")
        return (0, 0, 0)
    
    logger.info(f"📋 Found {len(new_tickers)} new tickers from MOST not in database: {new_tickers[:10]}{'...' if len(new_tickers) > 10 else ''}")
    
    # Process new tickers in batches
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    for i in range(0, len(new_tickers), BATCH_SIZE):
        batch = new_tickers[i:i + BATCH_SIZE]
        logger.info(f"\n📦 Processing MOST batch {i // BATCH_SIZE + 1} ({len(batch)} tickers)...")
        
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
        if i + BATCH_SIZE < len(new_tickers):
            logger.info(f"⏸️  Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...")
            time.sleep(DELAY_BETWEEN_BATCHES)
    
    return (total_processed, total_successful, total_failed)


def process_tickers_cycle(controller: GodelTerminalController, db: DatabaseManager) -> tuple[int, int, int]:
    """
    Process one cycle of ticker updates.
    
    Args:
        controller: GodelTerminalController instance
        db: DatabaseManager instance
        
    Returns:
        Tuple of (total_processed, total_successful, total_failed)
    """
    # Get list of tickers that need DES data
    logger.info(f"🔍 Finding tickers that need DES data (max age: {MAX_AGE_DAYS} days)...")
    tickers_needing_update = db.get_tickers_needing_des_update(max_age_days=MAX_AGE_DAYS)
    
    # Process tickers in batches
    total_processed = 0
    total_successful = 0
    total_failed = 0
    
    if not tickers_needing_update:
        logger.info("✅ All database tickers have up-to-date DES data!")
    else:
        logger.info(f"📋 Found {len(tickers_needing_update)} tickers needing DES data: {tickers_needing_update[:10]}{'...' if len(tickers_needing_update) > 10 else ''}")
        
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
    
    # Summary for database tickers
    db_total_processed = total_processed
    db_total_successful = total_successful
    db_total_failed = total_failed
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 Database Tickers Collection Summary")
    logger.info("=" * 60)
    logger.info(f"Total tickers processed: {db_total_processed}")
    logger.info(f"✅ Successful: {db_total_successful}")
    logger.info(f"❌ Failed: {db_total_failed}")
    logger.info(f"📈 Success rate: {(db_total_successful / db_total_processed * 100) if db_total_processed > 0 else 0:.1f}%")
    logger.info("=" * 60)
    
    # Now process tickers from MOST (50B+ market cap) that aren't in database
    logger.info("\n" + "=" * 60)
    logger.info("📊 Processing MOST Tickers (50B+ Market Cap)")
    logger.info("=" * 60)
    
    most_tickers = get_tickers_from_most(controller)
    most_processed, most_successful, most_failed = process_new_tickers_from_most(controller, db, most_tickers)
    
    # Summary for MOST tickers
    logger.info("\n" + "=" * 60)
    logger.info("📊 MOST Tickers Collection Summary")
    logger.info("=" * 60)
    logger.info(f"Total tickers processed: {most_processed}")
    logger.info(f"✅ Successful: {most_successful}")
    logger.info(f"❌ Failed: {most_failed}")
    logger.info(f"📈 Success rate: {(most_successful / most_processed * 100) if most_processed > 0 else 0:.1f}%")
    logger.info("=" * 60)
    
    # Now process tickers from file (if any)
    script_dir = Path(__file__).parent
    ticker_file_path = script_dir / TICKER_LIST_FILE
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 Processing Tickers from File")
    logger.info("=" * 60)
    
    file_tickers = get_tickers_from_file(str(ticker_file_path))
    file_processed, file_successful, file_failed = process_tickers_from_file(controller, db, file_tickers)
    
    # Summary for file tickers
    logger.info("\n" + "=" * 60)
    logger.info("📊 File Tickers Collection Summary")
    logger.info("=" * 60)
    logger.info(f"Total tickers processed: {file_processed}")
    logger.info(f"✅ Successful: {file_successful}")
    logger.info(f"❌ Failed: {file_failed}")
    logger.info(f"📈 Success rate: {(file_successful / file_processed * 100) if file_processed > 0 else 0:.1f}%")
    logger.info("=" * 60)
    
    # Combined summary
    total_processed = db_total_processed + most_processed + file_processed
    total_successful = db_total_successful + most_successful + file_successful
    total_failed = db_total_failed + most_failed + file_failed
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 Overall Collection Summary")
    logger.info("=" * 60)
    logger.info(f"Total tickers processed: {total_processed}")
    logger.info(f"✅ Successful: {total_successful}")
    logger.info(f"❌ Failed: {total_failed}")
    logger.info(f"📈 Success rate: {(total_successful / total_processed * 100) if total_processed > 0 else 0:.1f}%")
    logger.info("=" * 60)
    
    return (total_processed, total_successful, total_failed)


def main():
    """Main execution function - runs continuously."""
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("DES Data Collection Script - Continuous Mode")
    logger.info("=" * 60)
    logger.info(f"Checking every {CHECK_INTERVAL_SECONDS // 60} minutes for tickers needing updates")
    logger.info(f"Update threshold: {MAX_AGE_DAYS} days")
    logger.info("=" * 60)
    
    # Initialize Godel controller (keep it connected between cycles)
    controller = initialize_godel_controller()
    if not controller:
        logger.error("Failed to initialize Godel controller. Exiting.")
        return 1
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            logger.info(f"\n{'=' * 60}")
            logger.info(f"🔄 Starting cycle #{cycle_count}")
            logger.info(f"{'=' * 60}")
            
            # Initialize database connection for this cycle
            db = None
            try:
                logger.info("📦 Connecting to database...")
                db = DatabaseManager()
                logger.info("✅ Database connection established")
            except Exception as e:
                logger.error(f"❌ Failed to connect to database: {e}")
                logger.error("Please ensure database credentials are configured correctly")
                logger.info(f"⏸️  Waiting {CHECK_INTERVAL_SECONDS} seconds before retry...")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue
            
            try:
                # Process tickers
                total_processed, total_successful, total_failed = process_tickers_cycle(controller, db)
                
                # Disconnect from database after processing
                logger.info("🔌 Disconnecting from database...")
                db.close()
                db = None
                logger.info("✅ Database connection closed")
                
                # Wait before next check
                if total_processed > 0:
                    logger.info(f"\n✅ Cycle #{cycle_count} completed. Waiting {CHECK_INTERVAL_SECONDS // 60} minutes before next check...")
                else:
                    logger.info(f"\n✅ No tickers to process. Waiting {CHECK_INTERVAL_SECONDS // 60} minutes before next check...")
                
                time.sleep(CHECK_INTERVAL_SECONDS)
                
            except Exception as e:
                logger.error(f"❌ Error during processing cycle: {e}")
                import traceback
                traceback.print_exc()
                
                # Close database on error
                if db:
                    try:
                        db.close()
                        db = None
                    except:
                        pass
                
                logger.info(f"⏸️  Waiting {CHECK_INTERVAL_SECONDS} seconds before retry...")
                time.sleep(CHECK_INTERVAL_SECONDS)
        
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
            try:
                db.close()
                logger.info("✅ Database connection closed")
            except:
                pass


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

