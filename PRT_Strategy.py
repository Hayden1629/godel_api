"""
PRT Strategy Module
Handles all strategy logic: MOST data fetching, PRT analysis, and trade processing.
Returns processed trades ready for execution via Schwab API.
"""
from godel_core import GodelTerminalController
from commands.most_command import MOSTCommand
from commands.prt_command import PRTCommand
import pandas as pd
from loguru import logger

DOLLAR_AMOUNT = 500

# Edge threshold - minimum edge value to consider a trade valid
EDGE_THRESHOLD = 0.00010

# Maximum number of trades to execute per cycle (must be even for market neutral strategy)
_MAX_TRADES_RAW = 50
# Ensure MAX_TRADES is even (subtract 1 if odd)
MAX_TRADES = _MAX_TRADES_RAW if _MAX_TRADES_RAW % 2 == 0 else _MAX_TRADES_RAW - 1
MAX_TRADES_PER_DIRECTION = MAX_TRADES // 2  # Half long, half short

# Blacklist of known commission stocks
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
    'JOBY',
    'SBSW',
    'SNAP',
    'BBD',
    'AUR',
    'AGNC',
    'VALE',
    'PBR',
    'QS',
    'RIOT',
    'NGD',
}


def is_blacklisted(ticker: str) -> bool:
    """
    Check if a ticker is in the commission blacklist.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        bool: True if ticker is blacklisted, False otherwise
    """
    return ticker.upper() in COMMISSION_BLACKLIST


def filter_blacklisted_tickers(tickers: list, ticker_and_share_price: dict) -> tuple[list, dict]:
    """
    Filter out blacklisted tickers from the list and share price dictionary.
    
    Args:
        tickers: List of ticker symbols
        ticker_and_share_price: Dictionary mapping tickers to share prices
        
    Returns:
        tuple: (filtered_tickers, filtered_ticker_and_share_price)
    """
    filtered_tickers = []
    filtered_ticker_and_share_price = {}
    blacklisted = []
    
    for ticker in tickers:
        if is_blacklisted(ticker):
            blacklisted.append(ticker)
            logger.info(f"Filtering out {ticker} - in commission blacklist")
        else:
            filtered_tickers.append(ticker)
            if ticker in ticker_and_share_price:
                filtered_ticker_and_share_price[ticker] = ticker_and_share_price[ticker]
    
    if blacklisted:
        logger.info(f"Filtered out {len(blacklisted)} blacklisted tickers: {blacklisted}")
    
    return filtered_tickers, filtered_ticker_and_share_price

def process_most(dataframe):
    """Process MOST data and extract tickers"""
    if 'Ticker' in dataframe.columns:
        list_of_tickers = dataframe['Ticker'].tolist()
        #make ticker and share price dictionary
        ticker_and_share_price = {ticker: dataframe[dataframe['Ticker'] == ticker]['Last'].iloc[0] for ticker in list_of_tickers}
        return list_of_tickers, ticker_and_share_price
    else:
        logger.warning("'Ticker' column not found in MOST dataframe")
        return []


def process_prt(dataframe):
    """Process PRT data and extract trade signals"""
    if dataframe is not None and len(dataframe) > 0:
        list_of_trades = dataframe.to_dict('records')
        return list_of_trades
    else:
        logger.warning("Empty PRT dataframe")
        return []


def get_most(controller: GodelTerminalController):
    """
    Fetch MOST data and extract tickers.
    
    Args:
        controller: GodelTerminalController instance
    
    Returns:
        List of ticker symbols
    """
    logger.info("=== Fetching MOST data ===")
    most_cmd = MOSTCommand(controller, tab="ACTIVE", limit=75)
    most_result = most_cmd.execute()
    
    if most_result['success']:
        most_df = most_cmd.get_dataframe()
        logger.info(f"MOST DataFrame shape: {most_df.shape}")
        logger.debug(f"Columns: {most_df.columns.tolist()}")
        
        list_of_tickers, ticker_and_share_price = process_most(most_df)
        most_cmd.close()
        
        logger.info(f"Extracted {len(list_of_tickers)} tickers: {list_of_tickers[:10]}...")
        return list_of_tickers, ticker_and_share_price
    else:
        logger.error(f"MOST failed: {most_result.get('error')}")
        return [], {}


def get_prt(controller: GodelTerminalController, list_of_tickers: list, max_retries: int = 3):
    """
    Fetch PRT data for given tickers with retry logic for Run button failures.
    
    Args:
        controller: GodelTerminalController instance
        list_of_tickers: List of ticker symbols to analyze
        max_retries: Maximum number of retry attempts (default 3)
    
    Returns:
        List of trade dictionaries from PRT analysis
    """
    import time
    
    logger.info("=== Fetching PRT data ===")
    
    for attempt in range(1, max_retries + 1):
        prt_cmd = PRTCommand(controller, list_of_tickers)
        prt_result = prt_cmd.execute()
        
        if prt_result['success']:
            prt_df = prt_cmd.get_dataframe()
            list_of_trades = process_prt(prt_df)
            prt_cmd.close()
            return list_of_trades
        else:
            error = prt_result.get('error', 'Unknown error')
            logger.warning(f"PRT attempt {attempt}/{max_retries} failed: {error}")
            
            # Check if it's a Run button error that we should retry
            if 'Run button' in error or 'element not interactable' in error:
                if attempt < max_retries:
                    logger.info(f"Retrying PRT in 2 seconds... (attempt {attempt + 1}/{max_retries})")
                    prt_cmd.close()  # Clean up the failed attempt
                    time.sleep(2)  # Wait before retrying
                    continue
                else:
                    logger.error(f"PRT failed after {max_retries} attempts: {error}")
                    prt_cmd.close()
                    return []
            else:
                # Non-retryable error, return immediately
                logger.error(f"PRT failed with non-retryable error: {error}")
                prt_cmd.close()
                return []
    
    return []


def process_trades(list_of_trades: list, ticker_and_share_price: dict, accounts_trading=None) -> list:
    """
    Process raw PRT trades and convert them to Schwab API order format.
    This is where your strategy logic goes - filter, validate, format trades.
    
    Args:
        list_of_trades: Raw trade data from PRT analysis
        ticker_and_share_price: Dictionary mapping tickers to share prices
        accounts_trading: Optional AccountsTrading instance to check for commissions
    
    Returns:
        List of processed trades ready for Schwab API execution
    """
    logger.info(f"=== Processing {len(list_of_trades)} trades ===")
    
    if not list_of_trades:
        logger.warning("No trades to process")
        return []
    
    processed_trades = []
    
    # Filter trades by edge threshold and take up to MAX_TRADES (half long, half short)
    '''
    Information from PRT analysis:
    {'symbol': 'AMZN', 'timestamp': '2025-12-22 15:55', 'dist1': 8.344650268554688e-07,
    'n': 40, 'prob_up': 0.575, 'mean': 6.50965869156e-05, 'p10': -0.000876135398262,
    'p90': 0.0013433074378059, 'direction': 'LONG', 'edge': 3.74305374765e-05, 'actual': nan}
    Filter by edge threshold, then take up to MAX_TRADES (balanced long/short)
    '''
    # First, filter trades that meet the edge threshold
    valid_trades = [trade for trade in list_of_trades if trade.get('edge', 0) >= EDGE_THRESHOLD]
    valid_long = [t for t in valid_trades if t.get('direction') == 'LONG']
    valid_short = [t for t in valid_trades if t.get('direction') == 'SHORT']
    
    logger.info(f"=== Edge Threshold Report ===")
    logger.info(f"Edge threshold: {EDGE_THRESHOLD}")
    logger.info(f"Trades meeting threshold: {len(valid_trades)} of {len(list_of_trades)} total")
    logger.info(f"  - LONG trades above threshold: {len(valid_long)}")
    logger.info(f"  - SHORT trades above threshold: {len(valid_short)}")
    
    # Sort valid trades by edge (highest first)
    sorted_long = sorted(valid_long, key=lambda x: x.get('edge', 0), reverse=True)
    sorted_short = sorted(valid_short, key=lambda x: x.get('edge', 0), reverse=True)
    
    # Select equal number of long and short (limited by whichever has fewer, and by MAX)
    num_each = min(len(sorted_long), len(sorted_short), MAX_TRADES_PER_DIRECTION)
    
    top_long_trades = sorted_long[:num_each]
    top_short_trades = sorted_short[:num_each]
    top_trades = top_long_trades + top_short_trades
    
    logger.info(f"Selected {len(top_trades)} trades for execution ({len(top_long_trades)} LONG, {len(top_short_trades)} SHORT)")
    
    # Note: Blacklisted stocks are already filtered before PRT, but we still check for OTC stocks via API
    # Filter out stocks with commissions (OTC stocks) if accounts_trading is provided
    filtered_trades = []
    commission_filtered = []
    
    for trade in top_trades:
        ticker = trade.get('symbol', '')
        
        # Check for commissions (OTC stocks) if accounts_trading is available
        # Blacklisted stocks are already filtered before PRT, so this only catches OTC stocks
        if accounts_trading is not None:
            if accounts_trading.has_commission(ticker):
                commission_filtered.append(ticker)
                logger.warning(f"Filtering out {ticker} - has commission (OTC)")
                continue
        
        filtered_trades.append(trade)
    
    if commission_filtered:
        logger.info(f"Filtered out {len(commission_filtered)} stocks with commissions (OTC): {commission_filtered}")
    
    # Process only the filtered trades
    for trade in filtered_trades:
        ticker = trade.get('symbol', '')
        if ticker not in ticker_and_share_price:
            logger.warning(f"Skipping {ticker} - no share price available")
            continue
            
        processed_trade = {
            'ticker': ticker,
            'action': trade.get('direction', 'LONG'),  # LONG, SHORT, etc.
            'quantity': int(DOLLAR_AMOUNT / float(ticker_and_share_price[ticker])), #calculate quantity for certain dollar amount to nearest whole number of shares
        }
        processed_trades.append(processed_trade)
    
    logger.info(f"Processed {len(processed_trades)} trades for execution (filtered {len(top_trades) - len(processed_trades)} with commissions)")
    return processed_trades


def run_strategy(controller: GodelTerminalController, accounts_trading=None) -> list:
    """
    Main strategy execution method.
    Runs the full strategy: MOST -> PRT -> Process Trades
    
    Args:
        controller: GodelTerminalController instance
        accounts_trading: Optional AccountsTrading instance to check for commissions
    
    Returns:
        List of processed trades ready for Schwab API execution
    """
    try:
        # Step 1: Get tickers from MOST
        list_of_tickers, ticker_and_share_price = get_most(controller)
        
        if not list_of_tickers:
            logger.warning("No tickers found from MOST")
            return []
        
        # Step 1.5: Filter out blacklisted tickers before sending to PRT
        list_of_tickers, ticker_and_share_price = filter_blacklisted_tickers(list_of_tickers, ticker_and_share_price)
        
        if not list_of_tickers:
            logger.warning("No tickers remaining after blacklist filtering")
            return []
        
        # Step 2: Get PRT analysis for tickers
        list_of_trades = get_prt(controller, list_of_tickers)
        
        if not list_of_trades:
            logger.warning("No trades found from PRT")
            return []
        
        # Step 3: Process trades according to strategy
        processed_trades = process_trades(list_of_trades, ticker_and_share_price, accounts_trading)
        
        return processed_trades
        
    except Exception as e:
        logger.error(f"Error in strategy execution: {e}")
        import traceback
        traceback.print_exc()
        return []

