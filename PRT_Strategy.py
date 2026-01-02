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
from typing import Optional, List, Dict, Tuple
from db_manager import get_db_manager
import numpy as np
try:
    from scipy.optimize import minimize, linprog, differential_evolution
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available - will use fallback optimization method")

DOLLAR_AMOUNT = 500  # Maximum position size per trade
MIN_POSITION_SIZE = 200  # Minimum position size per trade

# Edge threshold - minimum edge value to consider a trade valid (increased from 0.00010 to filter for higher quality trades)
EDGE_THRESHOLD = 0.00020

# Maximum number of trades to execute per cycle
MAX_TRADES = 20

# Blacklist of known commission stocks
COMMISSION_BLACKLIST = {
    'ASST',  # STRIVE INC CLASS A
    'UP',    # WHEELS UP EXPERIENCE INC CLASS A
    'AMC',   # AMC ENTMT HLDGS INC CLASS CLASS A
    'BTBT',  # BATTLEBIT TECHNOLOGIES INC CLASS A
    'BTQ',
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
            
            # Delete the CSV file after use to avoid cluttering the Downloads folder
            csv_file_path = prt_cmd.csv_file_path
            if csv_file_path:
                try:
                    import os
                    if os.path.exists(csv_file_path):
                        os.remove(csv_file_path)
                        logger.debug(f"Deleted PRT CSV file: {csv_file_path}")
                except Exception as e:
                    logger.debug(f"Could not delete PRT CSV file {csv_file_path}: {e}")
            
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


def get_beta_for_trade(ticker: str) -> Optional[float]:
    """
    Get beta value for a ticker from database.
    
    Args:
        ticker: Stock ticker symbol
        
    Returns:
        Beta value or None if unavailable
    """
    try:
        db = get_db_manager()
        if not db:
            return None
        
        des_data = db.get_des_data(ticker)
        if des_data:
            # Beta is stored in the snapshot dict (reconstructed by get_des_data)
            snapshot = des_data.get('snapshot', {})
            if snapshot:
                beta_str = snapshot.get('Beta')
                if beta_str:
                    try:
                        # Remove any non-numeric characters (like "x" suffix)
                        beta = float(beta_str.replace('x', '').strip())
                        logger.debug(f"Retrieved beta {beta:.2f} for {ticker} from database")
                        return beta
                    except (ValueError, AttributeError):
                        pass
        
        return None
    except Exception as e:
        logger.debug(f"Error getting beta for {ticker}: {e}")
        return None


def calculate_portfolio_metrics(selected_trades: list, ticker_and_share_price: dict, beta_cache: dict = None) -> tuple[float, float]:
    """
    Calculate portfolio beta and net exposure for a set of trades.
    Uses variable position sizes stored in each trade dict (based on whole shares).
    
    Args:
        selected_trades: List of trade dicts with 'symbol', 'direction', 'edge', 'quantity' (shares), and optionally 'beta'
        ticker_and_share_price: Dictionary mapping tickers to share prices
        beta_cache: Optional dictionary mapping tickers to beta values (to avoid repeated lookups)
        
    Returns:
        Tuple of (portfolio_beta, net_exposure_dollars)
    """
    if not selected_trades:
        return 0.0, 0.0
    
    weighted_beta_sum = 0.0
    total_abs_market_value = 0.0
    net_exposure = 0.0
    
    for trade in selected_trades:
        ticker = trade.get('symbol', '')
        direction = trade.get('direction', 'LONG')
        
        if ticker not in ticker_and_share_price:
            continue
        
        price = float(ticker_and_share_price[ticker])
        # Use quantity from trade dict if available (from optimization), otherwise calculate from position_size or default
        if 'quantity' in trade:
            quantity = trade['quantity']
        elif 'position_size' in trade:
            quantity = int(trade['position_size'] / price)
        else:
            quantity = int(DOLLAR_AMOUNT / price)
        
        market_value = quantity * price  # Actual market value based on whole shares
        
        # Get beta for this ticker - use cached value if available, otherwise from trade dict, otherwise lookup
        beta = None
        if beta_cache and ticker in beta_cache:
            beta = beta_cache[ticker]
        elif 'beta' in trade:
            beta = trade['beta']
        else:
            beta = get_beta_for_trade(ticker)
        
        if beta is None:
            # Skip trades without beta data
            continue
        
        # Long positions contribute positive beta and positive exposure
        # Short positions contribute negative beta and negative exposure
        if direction == 'LONG':
            beta_contribution = beta * market_value
            net_exposure += market_value
        else:  # SHORT
            beta_contribution = -beta * market_value
            net_exposure -= market_value
        
        weighted_beta_sum += beta_contribution
        total_abs_market_value += abs(market_value)
    
    # Calculate portfolio beta
    portfolio_beta = weighted_beta_sum / total_abs_market_value if total_abs_market_value > 0 else 0.0
    
    return portfolio_beta, net_exposure


def optimize_portfolio_beta(candidate_trades: list, ticker_and_share_price: dict, beta_cache: dict) -> list:
    """
    Optimize share quantities for all candidate trades to achieve EXACT beta = 0.
    Uses linear algebra to solve the system: Σ(β_i * q_i * p_i * d_i) = 0
    where β_i = beta, q_i = quantity, p_i = price, d_i = direction (+1 LONG, -1 SHORT)
    
    Args:
        candidate_trades: List of all candidate trades with beta data
        ticker_and_share_price: Dictionary mapping tickers to share prices
        beta_cache: Dictionary mapping tickers to beta values
        
    Returns:
        List of trades with optimized quantities for exact beta = 0
    """
    if not candidate_trades:
        return []
    
    # Prepare trade data with constraints
    trade_data = []
    for trade in candidate_trades:
        ticker = trade.get('symbol', '')
        if ticker not in ticker_and_share_price:
            continue
        
        price = float(ticker_and_share_price[ticker])
        direction = trade.get('direction', 'LONG')
        beta = trade.get('beta')
        
        if beta is None:
            continue
        
        # Calculate min and max share quantities
        min_shares = max(1, int(MIN_POSITION_SIZE / price))
        max_shares = int(DOLLAR_AMOUNT / price)
        
        if max_shares < min_shares:
            continue
        
        trade_data.append({
            'trade': trade,
            'ticker': ticker,
            'price': price,
            'direction': direction,
            'beta': beta,
            'min_shares': min_shares,
            'max_shares': max_shares
        })
    
    if not trade_data:
        return []
    
    n = len(trade_data)
    logger.info(f"Solving for exact beta=0 with {n} trades using linear algebra...")
    
    # Build the system: we want Σ(β_i * q_i * p_i * d_i) = 0
    # For LONG: d_i = +1, for SHORT: d_i = -1
    # We'll use scipy.optimize.minimize to find integer quantities that minimize |beta|
    
    # Prepare coefficient vector: β_i * p_i * d_i for each trade
    # Use Python list only (no numpy arrays) to avoid memory corruption issues
    coeffs_list = []
    for td in trade_data:
        direction_mult = 1.0 if td['direction'] == 'LONG' else -1.0
        coeff = td['beta'] * td['price'] * direction_mult
        coeffs_list.append(float(coeff))
    
    # Objective function: minimize |Σ(β_i * q_i * p_i * d_i)|
    def objective(quantities):
        try:
            # Convert to list first to avoid numpy issues
            q_list = list(quantities) if not isinstance(quantities, list) else quantities
            
            # Use pure Python calculation instead of numpy to avoid memory issues
            # Calculate weighted_beta_sum manually
            weighted_beta_sum = sum(coeffs_list[i] * q_list[i] for i in range(n))
            
            # Calculate total abs value
            total_abs_value = sum(abs(q_list[i] * trade_data[i]['price']) for i in range(n))
            if total_abs_value == 0:
                return 1e6  # Penalty for zero portfolio
            portfolio_beta = weighted_beta_sum / total_abs_value
            return abs(portfolio_beta)
        except Exception as e:
            logger.debug(f"Error in objective function: {e}")
            return 1e6  # Return high penalty on error
    
    # Constraints: min_shares <= q_i <= max_shares (integer)
    bounds = [(td['min_shares'], td['max_shares']) for td in trade_data]
    
    # Initial guess: middle of range for each trade
    x0 = [max(td['min_shares'], min(td['max_shares'], int(500 / td['price']))) for td in trade_data]
    
    # Use optimization to find integer quantities that minimize |beta|
    if HAS_SCIPY:
        # Use differential evolution for global optimization with integer constraints
        # This handles the discrete nature of share quantities better
        
        # Round the result to integers
        def round_and_evaluate(quantities):
            rounded = [int(round(q)) for q in quantities]
            # Enforce bounds
            for i in range(len(rounded)):
                rounded[i] = max(trade_data[i]['min_shares'], min(trade_data[i]['max_shares'], rounded[i]))
            return objective(rounded)
        
        try:
            # Use smaller population size and fewer iterations to reduce memory usage
            # and avoid potential segfaults with large problems
            result = differential_evolution(
                round_and_evaluate,
                bounds=bounds,
                seed=42,
                maxiter=min(100, n * 5),  # Scale iterations with problem size
                popsize=min(15, max(5, n)),  # Scale population with problem size
                atol=1e-4,  # Slightly relaxed tolerance
                tol=1e-4,
                workers=1,  # Use single worker to avoid multiprocessing issues
                updating='immediate'  # Immediate updating can be more stable
            )
            
            # Safely extract solution and convert to Python native types immediately
            # This prevents memory corruption from numpy arrays in scipy result objects
            optimal_quantities = None
            result_x = None
            try:
                if hasattr(result, 'x') and result.x is not None:
                    # Convert numpy array to Python list immediately to avoid memory issues
                    if hasattr(result.x, 'tolist'):
                        result_x = result.x.tolist()
                    else:
                        result_x = list(result.x)
                else:
                    raise ValueError("Optimization did not return a valid solution")
            except Exception as e:
                logger.warning(f"Error extracting solution from result: {e}")
                raise ValueError("Could not extract solution from optimization result")
            finally:
                # Explicitly clean up the result object immediately after extraction
                # This prevents memory corruption from scipy's internal numpy arrays
                try:
                    del result
                except:
                    pass
            
            # Now work with the Python list (not numpy array)
            if result_x is not None:
                # Get rounded integer solution from Python list
                optimal_quantities = [int(round(float(q))) for q in result_x]
                
                # Enforce bounds one more time
                for i in range(len(optimal_quantities)):
                    optimal_quantities[i] = max(trade_data[i]['min_shares'], 
                                               min(trade_data[i]['max_shares'], optimal_quantities[i]))
                
                # Clear the result_x list to free memory
                del result_x
            else:
                raise ValueError("Optimization did not return a valid solution")
            
            # Build optimized trades
            optimized_trades = []
            for i, td in enumerate(trade_data):
                quantity = optimal_quantities[i]
                trade = td['trade'].copy()
                trade['quantity'] = quantity
                trade['position_size'] = quantity * td['price']
                optimized_trades.append(trade)
            
            # Verify the solution
            final_beta, _ = calculate_portfolio_metrics(optimized_trades, ticker_and_share_price, beta_cache)
            logger.info(f"Optimization complete: Portfolio Beta = {final_beta:.6f} (target: 0.000000)")
            
            if abs(final_beta) > 0.01:
                logger.warning(f"Warning: Could not achieve exact beta=0. Final beta: {final_beta:.6f}")
                # Try a refinement pass using local search
                optimized_trades = refine_beta_neutrality(optimized_trades, trade_data, ticker_and_share_price, beta_cache)
                final_beta, _ = calculate_portfolio_metrics(optimized_trades, ticker_and_share_price, beta_cache)
                logger.info(f"After refinement: Portfolio Beta = {final_beta:.6f}")
            
            # Clean up any remaining references to prevent memory issues
            # (coeffs_list is a Python list, so no special cleanup needed)
            
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"scipy optimization failed with error: {e}. Falling back to iterative method.")
            import traceback
            logger.debug(traceback.format_exc())
            optimized_trades = optimize_portfolio_beta_iterative(trade_data, ticker_and_share_price, beta_cache)
        except Exception as e:
            logger.warning(f"Unexpected error in scipy optimization: {e}. Falling back to iterative method.")
            import traceback
            logger.debug(traceback.format_exc())
            optimized_trades = optimize_portfolio_beta_iterative(trade_data, ticker_and_share_price, beta_cache)
    else:
        # No scipy - use iterative method
        logger.info("Using iterative optimization (scipy not available)")
        optimized_trades = optimize_portfolio_beta_iterative(trade_data, ticker_and_share_price, beta_cache)
    
    # Filter out trades with zero quantity
    optimized_trades = [t for t in optimized_trades if t.get('quantity', 0) > 0]
    
    return optimized_trades


def refine_beta_neutrality(optimized_trades: list, trade_data: list, ticker_and_share_price: dict, beta_cache: dict) -> list:
    """Refine quantities using local search to get closer to beta=0."""
    current_beta, _ = calculate_portfolio_metrics(optimized_trades, ticker_and_share_price, beta_cache)
    best_trades = optimized_trades.copy()
    best_beta_abs = abs(current_beta)
    
    # Try adjusting each trade by ±1, ±2 shares
    for iteration in range(3):
        improved = False
        for i, td in enumerate(trade_data):
            current_qty = best_trades[i]['quantity']
            for delta in [-2, -1, 1, 2]:
                new_qty = current_qty + delta
                if new_qty < td['min_shares'] or new_qty > td['max_shares']:
                    continue
                
                test_trades = best_trades.copy()
                test_trades[i] = best_trades[i].copy()
                test_trades[i]['quantity'] = new_qty
                test_trades[i]['position_size'] = new_qty * td['price']
                
                test_beta, _ = calculate_portfolio_metrics(test_trades, ticker_and_share_price, beta_cache)
                if abs(test_beta) < best_beta_abs:
                    best_beta_abs = abs(test_beta)
                    best_trades = test_trades
                    improved = True
                    break
        
        if not improved:
            break
    
    return best_trades


def optimize_portfolio_beta_iterative(trade_data: list, ticker_and_share_price: dict, beta_cache: dict) -> list:
    """Fallback iterative optimization method."""
    optimized_trades = []
    for td in trade_data:
        default_quantity = max(td['min_shares'], min(td['max_shares'], int(500 / td['price'])))
        trade = td['trade'].copy()
        trade['quantity'] = default_quantity
        trade['position_size'] = default_quantity * td['price']
        optimized_trades.append(trade)
    
    # Simple coordinate descent
    for iteration in range(50):
        for i, td in enumerate(trade_data):
            current_beta, _ = calculate_portfolio_metrics(optimized_trades, ticker_and_share_price, beta_cache)
            best_qty = optimized_trades[i]['quantity']
            best_beta_abs = abs(current_beta)
            
            for qty in range(td['min_shares'], td['max_shares'] + 1):
                test_trades = optimized_trades.copy()
                test_trades[i] = optimized_trades[i].copy()
                test_trades[i]['quantity'] = qty
                test_trades[i]['position_size'] = qty * td['price']
                
                test_beta, _ = calculate_portfolio_metrics(test_trades, ticker_and_share_price, beta_cache)
                if abs(test_beta) < best_beta_abs:
                    best_beta_abs = abs(test_beta)
                    best_qty = qty
            
            optimized_trades[i]['quantity'] = best_qty
            optimized_trades[i]['position_size'] = best_qty * td['price']
    
    return optimized_trades


def select_trades_for_beta_neutral_portfolio(valid_trades: list, ticker_and_share_price: dict, 
                                             accounts_trading=None) -> list:
    """
    Optimize ALL candidate trades to create a beta-neutral portfolio.
    
    Primary objective: Minimize portfolio beta (target 0)
    Uses all trades that meet edge threshold and optimizes share quantities.
    
    Args:
        valid_trades: List of valid trades (already filtered by edge threshold)
        ticker_and_share_price: Dictionary mapping tickers to share prices
        accounts_trading: Optional AccountsTrading instance to check for commissions
        
    Returns:
        List of optimized trades with quantities set for beta neutrality
    """
    # Filter out trades with commissions and missing data
    # Also cache beta values to avoid repeated lookups
    candidate_trades = []
    beta_cache = {}  # Cache beta values to avoid repeated database lookups
    commission_filtered = []
    missing_beta = []
    missing_price = []
    
    for trade in valid_trades:
        ticker = trade.get('symbol', '')
        
        # Check for commissions (OTC stocks)
        if accounts_trading is not None:
            if accounts_trading.has_commission(ticker):
                commission_filtered.append(ticker)
                continue
        
        # Check for share price
        if ticker not in ticker_and_share_price:
            missing_price.append(ticker)
            continue
        
        # Check for beta data and cache it
        beta = get_beta_for_trade(ticker)
        if beta is None:
            missing_beta.append(ticker)
            continue
        
        # Cache beta value and store in trade dict
        beta_cache[ticker] = beta
        trade['beta'] = beta  # Store beta in trade dict for easy access
        candidate_trades.append(trade)
    
    if commission_filtered:
        logger.info(f"Filtered out {len(commission_filtered)} stocks with commissions: {commission_filtered[:5]}{'...' if len(commission_filtered) > 5 else ''}")
    if missing_beta:
        logger.info(f"Filtered out {len(missing_beta)} stocks without beta data: {missing_beta[:5]}{'...' if len(missing_beta) > 5 else ''}")
    if missing_price:
        logger.info(f"Filtered out {len(missing_price)} stocks without price data: {missing_price[:5]}{'...' if len(missing_price) > 5 else ''}")
    
    if not candidate_trades:
        logger.warning("No candidate trades remaining after filtering")
        return []
    
    logger.info(f"=== Beta-Neutral Portfolio Optimization ===")
    logger.info(f"Optimizing {len(candidate_trades)} candidate trades for beta = 0")
    
    # If we have more than MAX_TRADES, optimize the top MAX_TRADES by edge first
    # This ensures we optimize the best trades while maintaining beta neutrality
    if len(candidate_trades) > MAX_TRADES:
        # Sort by edge and take top MAX_TRADES for optimization
        candidate_trades = sorted(candidate_trades, key=lambda x: x.get('edge', 0), reverse=True)[:MAX_TRADES]
        logger.info(f"Limiting to top {MAX_TRADES} trades by edge before optimization")
    
    # Optimize selected trades simultaneously for beta = 0
    optimized_trades = optimize_portfolio_beta(candidate_trades, ticker_and_share_price, beta_cache)
    
    # Final metrics
    if optimized_trades:
        portfolio_beta, net_exposure = calculate_portfolio_metrics(optimized_trades, ticker_and_share_price, beta_cache)
        num_long = sum(1 for t in optimized_trades if t.get('direction') == 'LONG')
        num_short = len(optimized_trades) - num_long
        
        logger.info(f"=== Final Portfolio Selection ===")
        logger.info(f"Selected {len(optimized_trades)} trades ({num_long} LONG, {num_short} SHORT)")
        logger.info(f"Portfolio Beta: {portfolio_beta:.3f} (target: 0.000)")
        logger.info(f"Net Exposure: ${net_exposure:.2f}")
        
        # Log position sizes
        total_position_value = sum(abs(t.get('position_size', 0)) for t in optimized_trades)
        logger.info(f"Total Position Value: ${total_position_value:.2f}")
    
    return optimized_trades


def process_trades(list_of_trades: list, ticker_and_share_price: dict, accounts_trading=None) -> list:
    """
    Process raw PRT trades and convert them to Schwab API order format.
    Uses beta-neutral portfolio selection: primary objective is beta=0, secondary is market neutral.
    
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
    
    # Filter trades by edge threshold
    valid_trades = [trade for trade in list_of_trades if trade.get('edge', 0) >= EDGE_THRESHOLD]
    valid_long = [t for t in valid_trades if t.get('direction') == 'LONG']
    valid_short = [t for t in valid_trades if t.get('direction') == 'SHORT']
    
    logger.info(f"=== Edge Threshold Report ===")
    logger.info(f"Edge threshold: {EDGE_THRESHOLD}")
    logger.info(f"Trades meeting threshold: {len(valid_trades)} of {len(list_of_trades)} total")
    logger.info(f"  - LONG trades above threshold: {len(valid_long)}")
    logger.info(f"  - SHORT trades above threshold: {len(valid_short)}")
    
    # Select trades using beta-neutral optimization
    selected_trades = select_trades_for_beta_neutral_portfolio(valid_trades, ticker_and_share_price, accounts_trading)
    
    if not selected_trades:
        logger.warning("No trades selected after beta-neutral optimization")
        return []
    
    # Convert selected trades to processed format
    # Use optimized quantities from the selection algorithm
    processed_trades = []
    for trade in selected_trades:
        ticker = trade.get('symbol', '')
        if ticker not in ticker_and_share_price:
            logger.warning(f"Skipping {ticker} - no share price available")
            continue
        
        # Use optimized quantity from trade dict (already calculated as whole shares)
        quantity = trade.get('quantity')
        if quantity is None:
            # Fallback: calculate from position_size or default
            position_size = trade.get('position_size', DOLLAR_AMOUNT)
            price = float(ticker_and_share_price[ticker])
            quantity = int(position_size / price)
        
        price = float(ticker_and_share_price[ticker])
        actual_position_size = quantity * price
        
        processed_trade = {
            'ticker': ticker,
            'action': trade.get('direction', 'LONG'),  # LONG, SHORT, etc.
            'quantity': quantity,  # Quantity (whole shares) from optimization
            'position_size': actual_position_size,  # Store the actual dollar amount for reference
            # Preserve PRT data for trade journal
            'prt_data': {
                'edge': trade.get('edge'),
                'prob_up': trade.get('prob_up'),
                'mean': trade.get('mean'),
                'p10': trade.get('p10'),
                'p90': trade.get('p90'),
                'dist1': trade.get('dist1'),
                'n': trade.get('n'),
                'timestamp': trade.get('timestamp'),
            }
        }
        processed_trades.append(processed_trade)
    
    logger.info(f"Processed {len(processed_trades)} trades for execution")
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

