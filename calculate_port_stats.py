"""
Portfolio Statistics Calculator - Calculates statistics on all open positions.

Flow:
1. Get all open positions
2. For each position, fetch market data (including PE ratio and beta)
3. Calculate portfolio-level statistics including exposure, PE ratios, and beta
"""
import time
import requests
from loguru import logger
from typing import Dict, List, Optional

# Import the same class algo_loop uses
from algo_loop import AccountsTrading

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not available. Beta calculation will be limited to Schwab API data.")


def get_positions(client: AccountsTrading) -> list:
    """Get all open positions."""
    client._update_headers()
    url = f"{client.base_url}/accounts/{client.account_hash_value}?fields=positions"
    response = requests.get(url, headers=client.headers)
    
    if response.status_code == 200:
        account_data = response.json()
        securities = account_data.get('securitiesAccount', {})
        return securities.get('positions', [])
    return []


def get_beta_from_yfinance(symbol: str) -> Optional[float]:
    """
    Get beta from Yahoo Finance using yfinance library.
    
    Args:
        symbol: Stock ticker symbol
        
    Returns:
        float: Beta value, or None if unavailable
    """
    if not YFINANCE_AVAILABLE:
        return None
        
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        beta = info.get('beta')
        
        if beta is not None:
            logger.debug(f"Retrieved beta {beta:.2f} for {symbol} from Yahoo Finance")
            return float(beta)
        else:
            logger.warning(f"Beta not available for {symbol} from Yahoo Finance")
            return None
            
    except Exception as e:
        logger.warning(f"Error getting beta from Yahoo Finance for {symbol}: {e}")
        return None


def get_market_data(client: AccountsTrading, symbol: str) -> Optional[Dict]:
    """
    Get comprehensive market data for a symbol including fundamental data (PE ratio and beta).
    
    Args:
        client: AccountsTrading instance
        symbol: Stock ticker symbol
        
    Returns:
        dict: Market data including quote and fundamental data, or None if unavailable
    """
    try:
        client._update_headers()
        
        # Schwab Market Data API quote endpoint with multiple fields
        quote_url = f"{client.market_data_base_url}/quotes"
        params = {
            'symbols': symbol,
            'fields': 'quote,fundamental,reference'  # Request quote, fundamental (beta), and reference data
        }
        
        response = requests.get(quote_url, headers=client.headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse response structure
            # Response format: {symbol: {quote: {...}, fundamental: {...}, reference: {...}}}
            if symbol in data:
                return data[symbol]
            else:
                logger.warning(f"Symbol {symbol} not found in market data response: {data}")
                return None
        else:
            logger.warning(f"Failed to get market data for {symbol}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting market data for {symbol}: {e}")
        return None


def calculate_portfolio_statistics(client: AccountsTrading) -> Dict:
    """
    Calculate comprehensive portfolio statistics.
    
    Returns:
        dict: Portfolio statistics including weighted beta, total value, position details, etc.
    """
    logger.info("Fetching open positions...")
    positions = get_positions(client)
    
    if not positions:
        logger.info("No open positions found.")
        return {
            'total_positions': 0,
            'total_long_exposure': 0.0,
            'total_short_exposure': 0.0,
            'net_exposure': 0.0,
            'avg_pe_long': None,
            'avg_pe_short': None,
            'portfolio_beta': None,
            'positions': []
        }
    
    logger.info(f"Found {len(positions)} position(s)")
    
    # Initialize portfolio aggregates
    total_long_exposure = 0.0
    total_short_exposure = 0.0
    weighted_pe_long_sum = 0.0
    weighted_pe_short_sum = 0.0
    total_long_value_for_pe = 0.0
    total_short_value_for_pe = 0.0
    weighted_beta_sum = 0.0  # For portfolio beta calculation
    total_abs_value_for_beta = 0.0  # Total absolute market value for beta weighting
    position_details = []
    
    # Process each position
    for i, pos in enumerate(positions, 1):
        symbol = pos.get('instrument', {}).get('symbol')
        if not symbol:
            continue
            
        long_qty = pos.get('longQuantity', 0)
        short_qty = pos.get('shortQuantity', 0)
        quantity = long_qty - short_qty  # Net quantity (positive for long, negative for short)
        avg_price = pos.get('averagePrice', 0)
        market_value = pos.get('marketValue', 0)
        current_price = pos.get('currentPrice', avg_price)
        
        position_type = "LONG" if quantity > 0 else "SHORT"
        
        logger.info(f"[{i}/{len(positions)}] Fetching market data for {symbol}...")
        
        # Get market data including PE ratio
        market_data = get_market_data(client, symbol)
        
        # Extract PE ratio and beta from fundamental data
        pe_ratio = None
        beta = None
        if market_data and 'fundamental' in market_data:
            fundamental = market_data['fundamental']
            pe_ratio = fundamental.get('peRatio')
            beta = fundamental.get('beta')  # Try to get beta from Schwab API
        
        # If beta not available from Schwab, try Yahoo Finance
        if beta is None:
            logger.debug(f"Beta not found in Schwab data for {symbol}, trying Yahoo Finance...")
            beta = get_beta_from_yfinance(symbol)
        
        # Extract additional quote data
        quote_data = {}
        if market_data and 'quote' in market_data:
            quote = market_data['quote']
            quote_data = {
                'last_price': quote.get('lastPrice'),
                'bid_price': quote.get('bidPrice'),
                'ask_price': quote.get('askPrice'),
                'volume': quote.get('totalVolume'),
                '52_week_high': quote.get('52WeekHigh'),
                '52_week_low': quote.get('52WeekLow'),
            }
        
        # Calculate exposure
        abs_market_value = abs(market_value)
        if market_value > 0:
            total_long_exposure += market_value
            # For PE calculation, weight by market value
            if pe_ratio is not None:
                weighted_pe_long_sum += pe_ratio * market_value
                total_long_value_for_pe += market_value
        elif market_value < 0:
            total_short_exposure += abs_market_value
            # For PE calculation, weight by absolute market value
            if pe_ratio is not None:
                weighted_pe_short_sum += pe_ratio * abs_market_value
                total_short_value_for_pe += abs_market_value
        
        # For beta calculation: weight by absolute market value
        # Long positions contribute positive beta, short positions contribute negative beta
        if beta is not None:
            # For longs: beta * market_value (positive)
            # For shorts: -beta * abs_market_value (negative, as shorts have opposite exposure)
            beta_contribution = beta * market_value  # This handles both long (positive) and short (negative)
            weighted_beta_sum += beta_contribution
            total_abs_value_for_beta += abs_market_value
        
        # Calculate unrealized P/L
        cost_basis = quantity * avg_price
        unrealized_pl = market_value - cost_basis
        unrealized_pl_percent = (unrealized_pl / cost_basis * 100) if cost_basis != 0 else 0
        
        position_info = {
            'symbol': symbol,
            'quantity': quantity,
            'position_type': position_type,
            'average_price': avg_price,
            'current_price': current_price,
            'market_value': market_value,
            'cost_basis': cost_basis,
            'unrealized_pl': unrealized_pl,
            'unrealized_pl_percent': unrealized_pl_percent,
            'pe_ratio': pe_ratio,
            'beta': beta,
            **quote_data
        }
        
        position_details.append(position_info)
        
        # Small delay to avoid rate limiting
        #if i < len(positions):
            #time.sleep(0.2)
    
    # Calculate net exposure
    net_exposure = total_long_exposure - total_short_exposure
    
    # Calculate weighted average PE ratios
    avg_pe_long = weighted_pe_long_sum / total_long_value_for_pe if total_long_value_for_pe > 0 else None
    avg_pe_short = weighted_pe_short_sum / total_short_value_for_pe if total_short_value_for_pe > 0 else None
    
    # Calculate portfolio beta (weighted by market value, accounting for long/short)
    # Portfolio beta = sum(beta_i * market_value_i) / sum(abs(market_value_i))
    # This accounts for shorts having opposite beta exposure
    portfolio_beta = weighted_beta_sum / total_abs_value_for_beta if total_abs_value_for_beta > 0 else None
    
    # Calculate total unrealized P/L
    total_unrealized_pl = sum(p['unrealized_pl'] for p in position_details)
    total_cost_basis = sum(abs(p['cost_basis']) for p in position_details)
    total_unrealized_pl_percent = (total_unrealized_pl / total_cost_basis * 100) if total_cost_basis > 0 else 0
    
    return {
        'total_positions': len(positions),
        'total_long_exposure': total_long_exposure,
        'total_short_exposure': total_short_exposure,
        'net_exposure': net_exposure,
        'avg_pe_long': avg_pe_long,
        'avg_pe_short': avg_pe_short,
        'portfolio_beta': portfolio_beta,
        'total_cost_basis': total_cost_basis,
        'total_unrealized_pl': total_unrealized_pl,
        'total_unrealized_pl_percent': total_unrealized_pl_percent,
        'positions': position_details
    }


def print_portfolio_statistics(stats: Dict):
    """Print formatted portfolio statistics."""
    print("\n" + "="*80)
    print("  PORTFOLIO STATISTICS")
    print("="*80 + "\n")
    
    print(f"Total Positions: {stats['total_positions']}")
    print(f"Total Long Exposure: ${stats['total_long_exposure']:,.2f}")
    print(f"Total Short Exposure: ${stats['total_short_exposure']:,.2f}")
    print(f"Net Exposure: ${stats['net_exposure']:,.2f}")
    print(f"Total Cost Basis: ${stats['total_cost_basis']:,.2f}")
    print(f"Total Unrealized P/L: ${stats['total_unrealized_pl']:,.2f} ({stats['total_unrealized_pl_percent']:+.2f}%)")
    
    # PE ratios
    pe_long_str = f"{stats['avg_pe_long']:.2f}" if stats['avg_pe_long'] is not None else "N/A"
    pe_short_str = f"{stats['avg_pe_short']:.2f}" if stats['avg_pe_short'] is not None else "N/A"
    print(f"\n{'Average PE (Longs):':<25} {pe_long_str}")
    print(f"{'Average PE (Shorts):':<25} {pe_short_str}")
    
    # Portfolio Beta
    beta_str = f"{stats['portfolio_beta']:.2f}" if stats['portfolio_beta'] is not None else "N/A"
    print(f"{'Portfolio Beta:':<25} {beta_str}")
    
    if stats['total_positions'] == 0:
        print("\nNo positions to display.")
        return
    
    print("\n" + "-"*80)
    print("POSITION DETAILS")
    print("-"*80)
    print(f"{'Symbol':<10} {'Type':<6} {'Qty':>8} {'Avg $':>10} {'Cur $':>10} {'Value':>12} {'P/L':>25} {'PE':>10} {'Beta':>10}")
    print("-"*80)
    
    for pos in stats['positions']:
        symbol = pos['symbol']
        pos_type = pos['position_type']
        qty = pos['quantity']
        avg_price = pos['average_price']
        cur_price = pos['current_price'] or avg_price
        value = pos['market_value']
        pl = pos['unrealized_pl']
        pl_pct = pos['unrealized_pl_percent']
        pe = pos['pe_ratio']
        beta = pos.get('beta')
        
        pe_str = f"{pe:.2f}" if pe is not None else "N/A"
        beta_str = f"{beta:.2f}" if beta is not None else "N/A"
        
        print(f"{symbol:<10} {pos_type:<6} {qty:>7.0f} ${avg_price:>8.2f} ${cur_price:>8.2f} "
              f"${value:>10,.2f} ${pl:>+10,.2f} ({pl_pct:>+6.2f}%) {pe_str:>10} {beta_str:>10}")
    
    print("-"*80)
    print("="*80 + "\n")


def main():
    """Main function to calculate and display portfolio statistics."""
    try:
        # Initialize
        logger.info("Initializing Schwab API client...")
        client = AccountsTrading()
        logger.info(f"Connected to account: {client.account_hash_value[:8]}...")
        
        # Calculate statistics
        stats = calculate_portfolio_statistics(client)
        
        # Display results
        print_portfolio_statistics(stats)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

