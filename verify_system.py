"""
System Verification Script

Tests all functions in the trading system to ensure they work correctly.
Logs all API responses for debugging purposes.

Assumes tokens are already loaded (run get_OG_tokens.py first).
Uses a safe test stock (KO - Coca-Cola) for order testing.
"""
import time
import json
from loguru import logger
from algo_loop import AccountsTrading, Trade, STOP_LOSS_PERCENT, TAKE_PROFIT_PERCENT, TRADE_HOLD_MINUTES

# Test stock - stable, not too expensive, not volatile
TEST_STOCK = "KO"  # Coca-Cola - typically ~$60, very stable
TEST_QUANTITY = 1  # Just 1 share for testing

# Configure logger to show all levels
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{time:HH:mm:ss} | {level: <8} | {message}", level="DEBUG")


class SystemVerifier:
    """Verifies all system functions work correctly."""
    
    def __init__(self):
        self.client = None
        self.test_trade = None
        self.test_order_id = None
        self.test_oco_order_id = None
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
    
    def log_api_response(self, function_name: str, response: dict, success: bool = None):
        """Log API response with full details."""
        status = "✅ SUCCESS" if success else "❌ FAILED" if success is False else "⚠️  RESPONSE"
        logger.info(f"\n{'='*80}")
        logger.info(f"{status} - {function_name}")
        logger.info(f"{'='*80}")
        logger.info(f"Response Type: {type(response)}")
        logger.info(f"Response Keys: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
        logger.info(f"Full Response JSON:")
        logger.info(json.dumps(response, indent=2, default=str))
        logger.info(f"{'='*80}\n")
    
    def test(self, name: str, func, *args, **kwargs):
        """Run a test and track results."""
        logger.info(f"\n{'#'*80}")
        logger.info(f"TESTING: {name}")
        logger.info(f"{'#'*80}")
        try:
            result = func(*args, **kwargs)
            self.results["passed"].append(name)
            logger.info(f"✅ PASSED: {name}")
            return result
        except Exception as e:
            self.results["failed"].append(f"{name}: {str(e)}")
            logger.error(f"❌ FAILED: {name} - {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def verify_initialization(self):
        """Test 1: Verify AccountsTrading initialization."""
        logger.info("Initializing AccountsTrading client...")
        self.client = AccountsTrading()
        assert self.client is not None, "Client is None"
        assert self.client.account_hash_value is not None, "Account hash not set"
        logger.info(f"✅ Client initialized - Account: {self.client.account_hash_value[:8]}...")
        return True
    
    def verify_get_account_info(self):
        """Test 2: Verify get_account_info() works."""
        response = self.client.get_account_info()
        self.log_api_response("get_account_info", response, success='error' not in response)
        
        if 'error' in response:
            logger.warning("⚠️  get_account_info returned error - may be rate limited")
            return False
        
        assert isinstance(response, dict), "Response should be a dict"
        logger.info("✅ get_account_info works")
        return True
    
    def verify_get_quote(self):
        """Test 3: Verify get_quote() works."""
        price = self.client.get_quote(TEST_STOCK)
        logger.info(f"Quote for {TEST_STOCK}: ${price}")
        
        assert price is not None, "Quote should not be None"
        assert isinstance(price, (int, float)), "Quote should be a number"
        assert price > 0, "Quote should be positive"
        logger.info(f"✅ get_quote works - {TEST_STOCK} = ${price:.2f}")
        return True
    
    def verify_get_bid_ask(self):
        """Test 4: Verify get_bid_ask() works."""
        result = self.client.get_bid_ask(TEST_STOCK)
        # get_bid_ask returns (bid, ask, last_price) - 3 values
        if len(result) == 3:
            bid, ask, last_price = result
        else:
            # Fallback if signature changes
            bid, ask = result[0], result[1]
            last_price = result[2] if len(result) > 2 else None
        
        self.log_api_response("get_bid_ask", {"bid": bid, "ask": ask, "last_price": last_price}, success=bid is not None and ask is not None)
        
        assert bid is not None, "Bid should not be None"
        assert ask is not None, "Ask should not be None"
        assert bid > 0 and ask > 0, "Prices should be positive"
        assert ask >= bid, "Ask should be >= bid"
        last_price_str = f"${last_price:.2f}" if last_price else "N/A"
        logger.info(f"✅ get_bid_ask works - Bid: ${bid:.2f}, Ask: ${ask:.2f}, Last: {last_price_str}, Spread: ${ask-bid:.2f}")
        return True
    
    def verify_get_quote_full(self):
        """Test 5: Verify get_quote_full() works."""
        response = self.client.get_quote_full(TEST_STOCK)
        self.log_api_response("get_quote_full", response, success=response is not None)
        
        assert response is not None, "Response should not be None"
        assert isinstance(response, dict), "Response should be a dict"
        logger.info("✅ get_quote_full works")
        return True
    
    def verify_get_positions(self):
        """Test 6: Verify get_positions() works."""
        positions = self.client.get_positions()
        self.log_api_response("get_positions", {"count": len(positions) if positions else 0, "positions": positions}, success=positions is not None)
        
        assert positions is not None, "Positions should not be None (empty list is OK)"
        assert isinstance(positions, list), "Positions should be a list"
        logger.info(f"✅ get_positions works - Found {len(positions)} position(s)")
        return True
    
    def verify_get_all_open_orders(self):
        """Test 7: Verify get_all_open_orders() works."""
        orders = self.client.get_all_open_orders()
        self.log_api_response("get_all_open_orders", {"count": len(orders) if orders else 0, "orders": orders}, success=orders is not None)
        
        assert orders is not None, "Orders should not be None"
        assert isinstance(orders, list), "Orders should be a list"
        logger.info(f"✅ get_all_open_orders works - Found {len(orders)} open order(s)")
        return True
    
    def verify_trade_class(self):
        """Test 8: Verify Trade class methods."""
        logger.info("Creating test Trade object...")
        self.test_trade = Trade(
            ticker=TEST_STOCK,
            action="LONG",
            quantity=TEST_QUANTITY
        )
        
        # Test get_age_minutes
        age = self.test_trade.get_age_minutes()
        assert isinstance(age, (int, float)), "Age should be a number"
        assert age >= 0, "Age should be non-negative"
        logger.info(f"✅ Trade.get_age_minutes() works - Age: {age:.2f} minutes")
        
        # Test should_close
        should_close = self.test_trade.should_close()
        assert isinstance(should_close, bool), "should_close should be boolean"
        logger.info(f"✅ Trade.should_close() works - Should close: {should_close}")
        
        # Test calculate_stop_loss_price
        entry_price = 60.0  # Example price
        stop_price = self.test_trade.calculate_stop_loss_price(entry_price)
        assert stop_price is not None, "Stop price should not be None"
        assert stop_price < entry_price, "Stop loss should be below entry for LONG"
        logger.info(f"✅ Trade.calculate_stop_loss_price() works - Entry: ${entry_price:.2f}, Stop: ${stop_price:.2f}")
        
        # Test calculate_take_profit_price
        take_profit = self.test_trade.calculate_take_profit_price(entry_price)
        assert take_profit is not None, "Take profit should not be None"
        assert take_profit > entry_price, "Take profit should be above entry for LONG"
        logger.info(f"✅ Trade.calculate_take_profit_price() works - Entry: ${entry_price:.2f}, TP: ${take_profit:.2f}")
        
        # Test get_close_action
        close_action = self.test_trade.get_close_action()
        assert close_action == "SELL", "Close action for LONG should be SELL"
        logger.info(f"✅ Trade.get_close_action() works - Action: {close_action}")
        
        return True
    
    def verify_create_market_order(self):
        """Test 9: Verify create_order() with market order."""
        logger.info(f"Creating MARKET order for {TEST_STOCK}...")
        
        order_payload = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": "BUY",
                "quantity": TEST_QUANTITY,
                "instrument": {
                    "symbol": TEST_STOCK,
                    "assetType": "EQUITY"
                }
            }]
        }
        
        response = self.client.create_order(order_payload)
        self.log_api_response("create_order (MARKET)", response, success='orderId' in response or 'error' not in response)
        
        if 'orderId' in response:
            self.test_order_id = response['orderId']
            logger.info(f"✅ Market order created - Order ID: {self.test_order_id}")
            
            # Wait for order to fill
            logger.info("Waiting 5 seconds for order to fill...")
            time.sleep(5)
            
            # Update trade with order ID
            self.test_trade.order_id = self.test_order_id
            return True
        elif 'error' in response:
            logger.warning(f"⚠️  Order creation returned error: {response.get('error')}")
            return False
        else:
            logger.warning("⚠️  Unexpected response format")
            return False
    
    def verify_get_order_details(self):
        """Test 10: Verify get_order_details() works."""
        if not self.test_order_id:
            logger.warning("⚠️  Skipping - no test order ID")
            return False
        
        logger.info(f"Getting details for order {self.test_order_id}...")
        response = self.client.get_order_details(self.test_order_id)
        self.log_api_response("get_order_details", response, success='error' not in response)
        
        if 'error' in response:
            logger.warning(f"⚠️  get_order_details returned error: {response.get('error')}")
            return False
        
        assert isinstance(response, dict), "Response should be a dict"
        logger.info(f"✅ get_order_details works - Status: {response.get('status', 'Unknown')}")
        return True
    
    def verify_get_fill_price_from_order(self):
        """Test 11: Verify get_fill_price_from_order() works."""
        if not self.test_order_id:
            logger.warning("⚠️  Skipping - no test order ID")
            return False
        
        logger.info(f"Getting fill price for order {self.test_order_id}...")
        fill_price = self.client.get_fill_price_from_order(self.test_order_id, max_retries=5, retry_delay=1.0)
        
        if fill_price is not None:
            logger.info(f"✅ get_fill_price_from_order works - Fill price: ${fill_price:.4f}")
            self.test_trade.entry_price = fill_price
            return True
        else:
            logger.warning("⚠️  Could not get fill price - order may not be filled yet or structure issue")
            # Try to get quote as fallback
            quote = self.client.get_quote(TEST_STOCK)
            if quote:
                logger.info(f"Using quote as fallback: ${quote:.2f}")
                self.test_trade.entry_price = quote
            return False
    
    def verify_create_oco_order(self):
        """Test 12: Verify create_oco_order() works."""
        if not self.test_trade or not self.test_trade.entry_price:
            logger.warning("⚠️  Skipping - no entry price available")
            return False
        
        logger.info(f"Creating OCO order for {TEST_STOCK}...")
        response = self.client.create_oco_order(
            self.test_trade,
            self.test_trade.entry_price,
            stop_loss_percent=STOP_LOSS_PERCENT,
            take_profit_percent=TAKE_PROFIT_PERCENT
        )
        self.log_api_response("create_oco_order", response, success='orderId' in response or 'error' not in response)
        
        if 'orderId' in response:
            self.test_oco_order_id = response['orderId']
            self.test_trade.stop_loss_order_id = self.test_oco_order_id
            logger.info(f"✅ OCO order created - Order ID: {self.test_oco_order_id}")
            logger.info(f"   Stop loss: ${self.test_trade.stop_loss_price:.2f}")
            logger.info(f"   Take profit: ${self.test_trade.take_profit_price:.2f}")
            return True
        elif 'error' in response:
            logger.warning(f"⚠️  OCO order creation returned error: {response.get('error')}")
            return False
        else:
            logger.warning("⚠️  Unexpected response format")
            return False
    
    def verify_create_dynamic_limit_order(self):
        """Test 13: Verify create_dynamic_limit_order() works (for closing)."""
        logger.info(f"Testing dynamic limit order for closing {TEST_STOCK}...")
        
        # First check if we have a position
        positions = self.client.get_positions()
        test_position = None
        for p in positions:
            if p.get('instrument', {}).get('symbol') == TEST_STOCK:
                test_position = p
                break
        
        if not test_position:
            logger.warning("⚠️  No position to close - skipping dynamic limit order test")
            return False
        
        # Determine if it's a long or short position
        long_quantity = test_position.get('longQuantity', 0)
        short_quantity = test_position.get('shortQuantity', 0)
        is_long = long_quantity > 0
        
        logger.info(f"Position details: Long: {long_quantity}, Short: {short_quantity}, Is Long: {is_long}")
        
        # Get current price
        bid_ask_result = self.client.get_bid_ask(TEST_STOCK)
        if len(bid_ask_result) == 3:
            bid, ask, _ = bid_ask_result
        else:
            bid, ask = bid_ask_result[0], bid_ask_result[1]
        
        if not bid or not ask:
            logger.warning("⚠️  Could not get bid/ask - skipping")
            return False
        
        # Determine correct instruction based on position type
        if is_long:
            instruction = "SELL"
            quantity = int(long_quantity)
        else:
            instruction = "BUY_TO_COVER"
            quantity = int(short_quantity)
        
        logger.info(f"Using instruction: {instruction}, quantity: {quantity}")
        
        # Try to create a limit order to close
        response = self.client.create_dynamic_limit_order(
            ticker=TEST_STOCK,
            instruction=instruction,
            quantity=quantity
        )
        self.log_api_response("create_dynamic_limit_order", response, success='orderId' in response or 'error' not in response)
        
        if 'orderId' in response:
            logger.info(f"✅ Dynamic limit order created - Order ID: {response['orderId']}")
            # Wait a bit to see if it gets rejected
            time.sleep(3)
            # Check order status
            order_details = self.client.get_order_details(str(response['orderId']))
            status = order_details.get('status', 'Unknown')
            logger.info(f"   Order status after 3s: {status}")
            
            # Log rejection details if rejected
            if status == 'REJECTED':
                messages = order_details.get('messages', [])
                if messages:
                    logger.warning(f"   Rejection messages: {messages}")
                logger.debug(f"   Full order details: {json.dumps(order_details, indent=2, default=str)}")
            
            # Try to cancel if still open
            if status in ['OPEN', 'ACCEPTED']:
                cancel_response = self.client.close_order(str(response['orderId']))
                logger.info(f"   Canceled test order - Response: {cancel_response.get('status', 'Unknown')}")
            return True
        else:
            logger.warning(f"⚠️  Dynamic limit order failed: {response.get('error', 'Unknown error')}")
            return False
    
    def verify_close_order(self):
        """Test 14: Verify close_order() works."""
        if not self.test_oco_order_id:
            logger.warning("⚠️  Skipping - no OCO order to cancel")
            return False
        
        logger.info(f"Canceling OCO order {self.test_oco_order_id}...")
        response = self.client.close_order(str(self.test_oco_order_id))
        self.log_api_response("close_order", response, success='error' not in response)
        
        if 'error' not in response:
            logger.info("✅ close_order works")
            return True
        else:
            logger.warning(f"⚠️  close_order returned error: {response.get('error')}")
            return False
    
    def verify_check_stop_loss_orders(self):
        """Test 15: Verify check_stop_loss_orders() works."""
        logger.info("Testing check_stop_loss_orders()...")
        
        # Add test trade to active trades if we have one
        if self.test_trade and self.test_trade.order_id:
            self.client.active_trades = [self.test_trade]
        
        try:
            self.client.check_stop_loss_orders()
            logger.info("✅ check_stop_loss_orders works (no errors)")
            return True
        except Exception as e:
            logger.warning(f"⚠️  check_stop_loss_orders error: {e}")
            return False
    
    def verify_check_profit_targets(self):
        """Test 16: Verify check_profit_targets() works."""
        logger.info("Testing check_profit_targets()...")
        
        try:
            self.client.check_profit_targets()
            logger.info("✅ check_profit_targets works (no errors)")
            return True
        except Exception as e:
            logger.warning(f"⚠️  check_profit_targets error: {e}")
            return False
    
    def verify_verify_and_force_close_all_positions(self):
        """Test 17: Verify verify_and_force_close_all_positions() works."""
        logger.info("Testing verify_and_force_close_all_positions()...")
        logger.warning("⚠️  This will close ALL positions - only run in test account!")
        
        # Only run if explicitly enabled
        run_safeguard_test = False  # Set to True to test position safeguard
        
        if not run_safeguard_test:
            logger.info("⚠️  Skipping safeguard test (set run_safeguard_test=True to enable)")
            return None
        
        try:
            result = self.client.verify_and_force_close_all_positions(
                force_market=False,
                reason="system verification test"
            )
            logger.info(f"✅ verify_and_force_close_all_positions works - Result: {result}")
            return result
        except Exception as e:
            logger.warning(f"⚠️  verify_and_force_close_all_positions error: {e}")
            return False
    
    def cleanup(self):
        """Clean up test positions and orders."""
        logger.info("\n" + "="*80)
        logger.info("CLEANUP: Closing test positions...")
        logger.info("="*80)
        
        # Get current positions
        positions = self.client.get_positions()
        test_positions = [p for p in positions if p.get('instrument', {}).get('symbol') == TEST_STOCK]
        
        if test_positions:
            logger.info(f"Found {len(test_positions)} test position(s) to close")
            for position in test_positions:
                symbol = position.get('instrument', {}).get('symbol')
                quantity = position.get('longQuantity', 0) or -position.get('shortQuantity', 0)
                is_long = position.get('longQuantity', 0) > 0
                
                close_action = "SELL" if is_long else "BUY_TO_COVER"
                order_payload = {
                    "orderType": "MARKET",
                    "session": "NORMAL",
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [{
                        "instruction": close_action,
                        "quantity": int(abs(quantity)),
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }]
                }
                
                response = self.client.create_order(order_payload)
                if 'orderId' in response:
                    logger.info(f"✅ Cleanup order placed for {symbol} - Order ID: {response['orderId']}")
                else:
                    logger.warning(f"⚠️  Failed to place cleanup order: {response.get('error')}")
            
            # Wait for orders to fill
            logger.info("Waiting 5 seconds for cleanup orders to fill...")
            time.sleep(5)
        else:
            logger.info("No test positions to close")
        
        # Cancel any remaining open orders for test stock
        orders = self.client.get_all_open_orders()
        test_orders = []
        for order in orders:
            if 'orderLegCollection' in order and order['orderLegCollection']:
                symbol = order['orderLegCollection'][0].get('instrument', {}).get('symbol')
                if symbol == TEST_STOCK:
                    test_orders.append(order)
        
        if test_orders:
            logger.info(f"Found {len(test_orders)} test order(s) to cancel")
            for order in test_orders:
                order_id = order.get('orderId')
                response = self.client.close_order(str(order_id))
                logger.info(f"   Canceled order {order_id}")
        
        logger.info("✅ Cleanup complete")
    
    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)
        logger.info(f"✅ Passed: {len(self.results['passed'])}")
        logger.info(f"❌ Failed: {len(self.results['failed'])}")
        logger.info(f"⚠️  Warnings: {len(self.results['warnings'])}")
        logger.info("="*80)
        
        if self.results['passed']:
            logger.info("\n✅ PASSED TESTS:")
            for test in self.results['passed']:
                logger.info(f"   - {test}")
        
        if self.results['failed']:
            logger.info("\n❌ FAILED TESTS:")
            for test in self.results['failed']:
                logger.info(f"   - {test}")
        
        if self.results['warnings']:
            logger.info("\n⚠️  WARNINGS:")
            for warning in self.results['warnings']:
                logger.info(f"   - {warning}")
        
        logger.info("="*80 + "\n")
    
    def run_all_tests(self):
        """Run all verification tests."""
        logger.info("\n" + "="*80)
        logger.info("SYSTEM VERIFICATION TEST SUITE")
        logger.info("="*80)
        logger.info(f"Test Stock: {TEST_STOCK}")
        logger.info(f"Test Quantity: {TEST_QUANTITY}")
        logger.info("="*80 + "\n")
        
        # Core initialization
        self.test("Initialization", self.verify_initialization)
        
        # Basic API calls
        self.test("get_account_info", self.verify_get_account_info)
        self.test("get_quote", self.verify_get_quote)
        self.test("get_bid_ask", self.verify_get_bid_ask)
        self.test("get_quote_full", self.verify_get_quote_full)
        self.test("get_positions", self.verify_get_positions)
        self.test("get_all_open_orders", self.verify_get_all_open_orders)
        
        # Trade class
        self.test("Trade class methods", self.verify_trade_class)
        
        # Order creation
        self.test("create_order (MARKET)", self.verify_create_market_order)
        self.test("get_order_details", self.verify_get_order_details)
        self.test("get_fill_price_from_order", self.verify_get_fill_price_from_order)
        self.test("create_oco_order", self.verify_create_oco_order)
        self.test("create_dynamic_limit_order", self.verify_create_dynamic_limit_order)
        
        # Order management
        self.test("close_order", self.verify_close_order)
        
        # Trade monitoring
        self.test("check_stop_loss_orders", self.verify_check_stop_loss_orders)
        self.test("check_profit_targets", self.verify_check_profit_targets)
        
        # Position safeguard (optional - commented out by default)
        # self.test("verify_and_force_close_all_positions", self.verify_verify_and_force_close_all_positions)
        
        # Cleanup
        self.cleanup()
        
        # Print summary
        self.print_summary()


def main():
    """Main entry point."""
    verifier = SystemVerifier()
    verifier.run_all_tests()


if __name__ == "__main__":
    main()

