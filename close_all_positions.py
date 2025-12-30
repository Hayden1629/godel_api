"""
Emergency Position Closer - Closes all open positions immediately.
Run this script if something goes wrong with the main algo.

Flow:
1. Cancel all open orders (stop losses, etc.)
2. Wait for cancellations to process
3. Close all positions with market orders
"""
import time
import requests
from loguru import logger
from datetime import datetime
import pytz

# Import the same class algo_loop uses
from algo_loop import AccountsTrading


def get_open_orders(client: AccountsTrading) -> list:
    """
    Get all open/pending orders.
    Uses the same logic as algo_loop.py's get_all_open_orders() method.
    """
    try:
        client._update_headers()
        
        if not client.account_hash_value:
            logger.error("Account hash value not set")
            return []
        
        # Schwab API requires fromEnteredTime and toEnteredTime parameters (ZonedDateTime format)
        # Use start and end of today in Eastern timezone (ISO 8601 format with timezone)
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        # Start of today (00:00:00) in Eastern timezone
        start_of_today = now_eastern.replace(hour=0, minute=0, second=0, microsecond=0)
        # End of today (23:59:59) in Eastern timezone
        end_of_today = now_eastern.replace(hour=23, minute=59, second=59, microsecond=999999)
        # Use isoformat() to get proper ISO 8601 format with timezone
        from_date = start_of_today.isoformat()
        to_date = end_of_today.isoformat()
        
        url = f"{client.base_url}/accounts/{client.account_hash_value}/orders"
        params = {
            'fromEnteredTime': from_date,
            'toEnteredTime': to_date
        }
        
        response = requests.get(url, headers=client.headers, params=params)
        
        if response.status_code == 200:
            orders = response.json()
            # Filter to only open/pending orders (exclude filled, canceled, rejected, expired)
            open_statuses = ['WORKING', 'PENDING_ACTIVATION', 'QUEUED', 'ACCEPTED', 'AWAITING_PARENT_ORDER']
            open_orders = [o for o in orders if o.get('status', '').upper() in open_statuses]
            logger.debug(f"Filtered {len(open_orders)} open orders from {len(orders)} total orders")
            return open_orders
        elif response.status_code == 404:
            # 404 means no orders, which is valid
            logger.debug("No orders found (404) - this is normal if there are no orders")
            return []
        else:
            logger.error(f"Failed to get orders: {response.status_code} - {response.text}")
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error getting open orders: {e}")
        return []
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        return []


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


def close_position(client: AccountsTrading, symbol: str, quantity: float, is_long: bool = True) -> dict:
    """Close a position with a market order."""
    instruction = "SELL" if is_long else "BUY_TO_COVER"
    
    order_payload = {
        "orderType": "MARKET",
        "session": "NORMAL",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [{
            "instruction": instruction,
            "quantity": int(abs(quantity)),
            "instrument": {
                "symbol": symbol,
                "assetType": "EQUITY"
            }
        }]
    }
    
    result = client.create_order(order_payload)
    
    if 'orderId' in result or 'success' in result:
        order_id = result.get('orderId', 'unknown')
        logger.info(f"✓ Closed {symbol}: {instruction} {int(abs(quantity))} shares (Order ID: {order_id})")
        return {'success': True, 'orderId': order_id}
    else:
        logger.error(f"✗ Failed to close {symbol}: {result}")
        return result


def main():
    print("\n" + "="*60)
    print("  EMERGENCY POSITION CLOSER")
    print("  This will cancel ALL orders and close ALL positions")
    print("="*60 + "\n")
    
    # Confirm before proceeding
    confirm = input("Are you sure? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return
    
    try:
        # Initialize
        logger.info("Initializing Schwab API client...")
        client = AccountsTrading()
        logger.info(f"Connected to account: {client.account_hash_value[:8]}...")
        
        # ===== STEP 1: Cancel all open orders =====
        logger.info("\n--- STEP 1: Cancelling all open orders ---")
        open_orders = get_open_orders(client)
        
        if open_orders:
            logger.info(f"Found {len(open_orders)} open order(s) to cancel")
            for order in open_orders:
                order_id = order.get('orderId')
                symbol = order.get('orderLegCollection', [{}])[0].get('instrument', {}).get('symbol', 'Unknown')
                order_type = order.get('orderType', 'Unknown')
                status = order.get('status', 'Unknown')
                
                logger.info(f"  Cancelling {order_type} order for {symbol} (ID: {order_id}, Status: {status})")
                result = client.close_order(str(order_id))
                if 'error' in result:
                    logger.warning(f"    Could not cancel: {result.get('error')}")
            
            # Wait for cancellations to process
            logger.info("Waiting 2 seconds for cancellations to process...")
            time.sleep(2)
        else:
            logger.info("No open orders found")
        
        # ===== STEP 2: Get and close all positions =====
        logger.info("\n--- STEP 2: Closing all positions ---")
        positions = get_positions(client)
        
        if not positions:
            logger.info("No open positions found. Done!")
            return
        
        logger.info(f"Found {len(positions)} position(s)")
        print("-" * 40)
        
        # Display positions
        for pos in positions:
            symbol = pos.get('instrument', {}).get('symbol', 'Unknown')
            quantity = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
            avg_price = pos.get('averagePrice', 0)
            market_value = pos.get('marketValue', 0)
            position_type = "LONG" if quantity > 0 else "SHORT"
            print(f"  {symbol}: {abs(quantity):.0f} shares ({position_type}) @ ${avg_price:.2f} = ${market_value:.2f}")
        
        print("-" * 40)
        
        # Confirm closing positions
        confirm2 = input(f"\nClose all {len(positions)} position(s) with MARKET orders? (yes/no): ").strip().lower()
        if confirm2 != "yes":
            print("Aborted.")
            return
        
        # Close each position
        print("\nClosing positions...")
        success_count = 0
        fail_count = 0
        
        for pos in positions:
            symbol = pos.get('instrument', {}).get('symbol')
            long_qty = pos.get('longQuantity', 0)
            short_qty = pos.get('shortQuantity', 0)
            
            if not symbol:
                continue
            
            if long_qty > 0:
                result = close_position(client, symbol, long_qty, is_long=True)
                if 'success' in result:
                    success_count += 1
                else:
                    fail_count += 1
                    
            if short_qty > 0:
                result = close_position(client, symbol, short_qty, is_long=False)
                if 'success' in result:
                    success_count += 1
                else:
                    fail_count += 1
        
        print("\n" + "="*40)
        print(f"  COMPLETE: {success_count} closed, {fail_count} failed")
        print("="*40 + "\n")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
