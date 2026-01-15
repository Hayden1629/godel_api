"""
Godel Terminal Core Framework
Base classes for terminal control and command execution
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
import time


class DOMMonitor:
    """Monitor DOM changes for new window creation"""
    
    def __init__(self, driver):
        self.driver = driver
        self.tracked_windows = set()
        
    def get_current_windows(self) -> List[Any]:
        """Get all window elements currently in DOM"""
        try:
            windows = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "div.resize.inline-block.absolute[id$='-window']"
            )
            return windows
        except Exception as e:
            print(f"Error getting windows: {e}")
            return []
    
    def get_new_window(self, previous_count: int, timeout: int = 10) -> Optional[Any]:
        """Wait for and return a newly created window"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current_windows = self.get_current_windows()
            
            if len(current_windows) > previous_count:
                # Get the newest window (last in list)
                new_window = current_windows[-1]
                window_id = new_window.get_attribute('id')
                
                if window_id not in self.tracked_windows:
                    self.tracked_windows.add(window_id)
                    return new_window
            
            time.sleep(0.1)
        
        return None
    
    def wait_for_loading(self, timeout: int = 30) -> bool:
        """Wait for loading spinner to disappear"""
        try:
            time.sleep(0.5)  # Brief wait for spinner to appear
            WebDriverWait(self.driver, timeout).until(
                EC.invisibility_of_element_located(
                    (By.CSS_SELECTOR, ".anticon-loading.anticon-spin")
                )
            )
            return True
        except TimeoutException:
            return False


class BaseCommand(ABC):
    """Base class for all terminal commands"""
    
    def __init__(self, controller):
        self.controller = controller
        self.driver = controller.driver
        self.dom_monitor = controller.dom_monitor
        self.window = None
        self.window_id = None
        self.data = None
    
    @abstractmethod
    def get_command_string(self, ticker: str, asset_class: str) -> str:
        """Return the command string to send to terminal"""
        pass
    
    @abstractmethod
    def extract_data(self) -> Dict:
        """Extract data from the command window"""
        pass
    
    def execute(self, ticker: str, asset_class: str = "EQ") -> Dict:
        """Execute the command and return results"""
        command_str = self.get_command_string(ticker, asset_class)
        
        # Get current window count
        previous_count = len(self.dom_monitor.get_current_windows())
        
        print(f"\nExecuting: {command_str}")
        print(f"Current windows: {previous_count}")
        
        # Send command
        if not self.controller.send_command(command_str):
            return {
                'success': False,
                'error': 'Failed to send command',
                'command': command_str
            }
        
        # Wait for new window
        print("Waiting for new window...")
        self.window = self.dom_monitor.get_new_window(previous_count, timeout=10)
        
        if not self.window:
            return {
                'success': False,
                'error': 'No new window created',
                'command': command_str
            }
        
        self.window_id = self.window.get_attribute('id')
        print(f"New window detected: {self.window_id}")
        
        # Wait for loading to complete
        print("Waiting for content to load...")
        if not self.dom_monitor.wait_for_loading(timeout=30):
            return {
                'success': False,
                'error': 'Loading timeout',
                'command': command_str,
                'window_id': self.window_id
            }
        
        # Extract data
        print("Extracting data...")
        try:
            self.data = self.extract_data()
            return {
                'success': True,
                'command': command_str,
                'data': self.data
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Data extraction failed: {str(e)}',
                'command': command_str,
                'window_id': self.window_id
            }
    
    def close(self, retry_count=0):
        """Close the command window with multiple fallback strategies"""
        if retry_count > 2:  # Prevent infinite recursion
            print(f"Max retries reached for closing window {self.window_id}")
            return False
            
        if not self.window:
            print("No window to close")
            return False
        
        # If we have a window_id, try to refresh the window reference if it's stale
        if self.window_id:
            try:
                # Test if window reference is still valid
                _ = self.window.get_attribute('id')
            except Exception:
                # Window reference is stale, try to find it again
                try:
                    windows = self.dom_monitor.get_current_windows()
                    for win in windows:
                        if win.get_attribute('id') == self.window_id:
                            self.window = win
                            print(f"Refreshed stale window reference for {self.window_id}")
                            break
                except Exception as e:
                    print(f"Could not refresh window reference: {e}")
        
        try:
            # Strategy 1: Try span with close icon (most common)
            try:
                close_button = self.window.find_element(
                    By.CSS_SELECTOR,
                    "span.anticon.anticon-close"
                )
                close_button.click()
                time.sleep(0.5)
                print(f"Window {self.window_id} closed")
                return True
            except NoSuchElementException:
                pass
            
            # Strategy 2: Try SVG with data-icon='close'
            try:
                close_svg = self.window.find_element(
                    By.CSS_SELECTOR,
                    "svg[data-icon='close']"
                )
                close_svg.click()
                time.sleep(0.5)
                print(f"Window {self.window_id} closed (via SVG)")
                return True
            except NoSuchElementException:
                pass
            
            # Strategy 3: Try button with close icon class
            try:
                close_btn = self.window.find_element(
                    By.CSS_SELECTOR,
                    "button[aria-label*='close' i], button[aria-label*='Close' i]"
                )
                close_btn.click()
                time.sleep(0.5)
                print(f"Window {self.window_id} closed (via button)")
                return True
            except NoSuchElementException:
                pass
            
            # Strategy 4: Try to find any element with close-related classes/attributes in header
            try:
                # Look for header element first
                header = self.window.find_element(By.CSS_SELECTOR, ".ant-modal-header, .window-header, [class*='header']")
                close_elements = header.find_elements(
                    By.CSS_SELECTOR,
                    "span[class*='close'], button[class*='close'], svg[data-icon='close'], .anticon-close"
                )
                if close_elements:
                    close_elements[0].click()
                    time.sleep(0.5)
                    print(f"Window {self.window_id} closed (via header element)")
                    return True
            except Exception:
                pass
            
            # Strategy 5: Try to find close button anywhere in window using XPath
            try:
                close_xpath = ".//span[contains(@class, 'close')] | .//button[contains(@class, 'close')] | .//*[contains(@aria-label, 'close')]"
                close_el = self.window.find_element(By.XPATH, close_xpath)
                close_el.click()
                time.sleep(0.5)
                print(f"Window {self.window_id} closed (via XPath)")
                return True
            except NoSuchElementException:
                pass
            
            print(f"Warning: Could not find close button for window {self.window_id}")
            return False
            
        except StaleElementReferenceException:
            # Window element became stale, try to refresh and close again
            print(f"Window element became stale, attempting to refresh and close...")
            if self.window_id:
                try:
                    windows = self.dom_monitor.get_current_windows()
                    for win in windows:
                        if win.get_attribute('id') == self.window_id:
                            self.window = win
                            # Retry closing with fresh reference
                            return self.close(retry_count=retry_count + 1)
                except Exception as e:
                    print(f"Could not refresh stale window reference: {e}")
            return False
        except Exception as e:
            print(f"Error closing window {self.window_id}: {e}")
            import traceback
            traceback.print_exc()
            return False


class GodelTerminalController:
    """Controller for Godel Terminal command execution"""
    
    def __init__(self, url: str ="https://app.godelterminal.com", headless: bool = False):
        self.url = url
        self.driver = None
        self.dom_monitor = None
        self.headless = headless
        self.active_commands = []
        self.command_registry = {}
        
    def register_command(self, command_type: str, command_class):
        """Register a command class"""
        self.command_registry[command_type] = command_class
        
    def connect(self):
        """Initialize browser and navigate to terminal"""
        options = webdriver.ChromeOptions()
        
        if self.headless:
            options.add_argument('--headless')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        # Suppress SSL errors and other Chrome logging
        options.add_argument('--log-level=3')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-gpu')
        options.add_argument('--silent')
        options.add_argument('--disable-extensions')
        # Suppress SSL certificate errors
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--ignore-certificate-errors-spki-list')
        # Suppress console errors
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        # Suppress all logging including SSL errors
        prefs = {
            'logging': {
                'level': 'OFF'
            },"credentials_enable_service": False,
         "profile.password_manager_enabled": False
        }
        options.add_experimental_option('prefs', prefs)
        
        # Suppress SSL handshake errors by filtering stderr
        import sys
        import os
        
        # Save original stderr
        if not hasattr(self, '_original_stderr'):
            self._original_stderr = sys.stderr
            
            # Create a filter for stderr that ignores SSL errors
            class SSLErrorFilter:
                def __init__(self, original):
                    self.original = original
                    self.ssl_error_patterns = [
                        'handshake failed',
                        'SSL error code',
                        'net/socket/ssl_client_socket_impl.cc',
                        'net_error -100'
                    ]
                
                def write(self, message):
                    # Filter out SSL-related errors
                    if any(pattern in message for pattern in self.ssl_error_patterns):
                        return  # Don't write SSL errors
                    self.original.write(message)
                
                def flush(self):
                    self.original.flush()
                
                def __getattr__(self, name):
                    return getattr(self.original, name)
            
            # Install the filter
            sys.stderr = SSLErrorFilter(self._original_stderr)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        
        # Maximize window immediately on initialization
        try:
            self.driver.maximize_window()
        except Exception as e:
            # If maximize fails (e.g., in headless mode), that's okay
            pass
        
        # Initialize DOM monitor
        self.dom_monitor = DOMMonitor(self.driver)
        
        time.sleep(3)
        print(f"Connected to {self.url}")
    
    def disconnect(self):
        """Close browser with robust cleanup"""
        if not self.driver:
            return
        
        driver_ref = self.driver
        self.driver = None  # Clear reference early to prevent reuse
        
        try:
            # First, try to close all windows gracefully (but don't fail if connection is already broken)
            try:
                # Check if driver connection is still alive
                _ = driver_ref.current_url  # This will fail if connection is broken
                
                # If we get here, connection is alive, try to close windows
                windows = driver_ref.window_handles
                for window in windows:
                    try:
                        driver_ref.switch_to.window(window)
                        driver_ref.close()
                    except Exception:
                        # If we can't close a specific window, continue with others
                        pass
            except Exception:
                # Connection is already broken or windows can't be closed - that's okay
                pass
            
            # Then quit the driver (may fail silently if already disconnected)
            try:
                driver_ref.quit()
            except Exception:
                # Driver already quit or connection broken - that's fine
                pass
            
            print("Browser disconnected successfully")
            
            # Small delay to ensure cleanup completes
            time.sleep(0.5)
                
        except Exception as e:
            print(f"Error during disconnect: {e}")
            
            # Force cleanup - try to kill the process if quit() failed (optional, requires psutil)
            try:
                import psutil
                import os
                # Find and kill Chrome/Chromium processes for this driver
                current_pid = os.getpid()
                for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                    try:
                        if proc.info['ppid'] == current_pid and 'chrome' in proc.info['name'].lower():
                            proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
            except ImportError:
                # psutil not available, that's okay - graceful quit is preferred anyway
                pass
            except Exception as e2:
                # Silently ignore force cleanup errors
                pass
    
    def login(self, username: str, password: str):
        """Log in to the website"""
        try:
            print('Logging in...')
            
            # Wait for and click initial login button
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='Login']"))
            )
            login_button = self.driver.find_element(By.XPATH, "//button[text()='Login']")
            login_button.click()

            # Wait for login form and fill credentials
            print('Entering credentials...')
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='username']"))
            )
            username_field.send_keys(username)
            
            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[autocomplete='current-password']")
            password_field.send_keys(password)
            time.sleep(.5)

            # Click login button to submit
            login_button = self.driver.find_element(By.XPATH, '//*[@id="root"]/div[2]/div[3]/div/div[2]/div/form/div[2]/button')
            login_button.click()
            
            print('Waiting for login to complete...')
            
            # Wait for login modal/button to disappear
            WebDriverWait(self.driver, 15).until(
                EC.invisibility_of_element_located((By.XPATH, "//button[text()='Login']"))
            )
            print('Login modal closed')
            
            # Wait for main page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "terminal-input"))
            )
            print('Main page loaded')
            
            time.sleep(1)
            print("✓ Login successful and page ready")
            return True
            
        except TimeoutException as e:
            print(f'✗ Login timeout: {str(e)}')
            print('  Possible issues: wrong credentials, slow network, or page structure changed')
            raise
        except Exception as e:
            print(f'✗ Login failed: {str(e)}')
            raise
    
    def load_layout(self, layout_name: str = "dev"):
        """Navigate to a specific layout"""
        try:
            print(f'Loading layout: {layout_name}...')
            
            # Find and click the layout by name
            layout_span = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, f"//span[@class='whitespace-nowrap' and text()='{layout_name}']"))
            )
            layout_span.click()
            
            time.sleep(1)
            print(f"✓ Layout '{layout_name}' loaded")
            return True
            
        except TimeoutException:
            print(f'✗ Layout "{layout_name}" not found')
            return False
        except Exception as e:
            print(f'✗ Error loading layout: {str(e)}')
            return False
    
    def open_terminal(self):
        """Open terminal using backtick key"""
        try:
            body = self.driver.find_element(By.TAG_NAME, 'body')
            body.send_keys('`')
            time.sleep(0.5)
            
            # Verify terminal input is visible/active
            terminal_input = self.driver.find_element(By.ID, "terminal-input")
            print("Terminal opened")
            return True
            
        except Exception as e:
            print(f"Error opening terminal: {e}")
            return False
    
    def send_command(self, command_str: str) -> bool:
        """Send command string to terminal"""
        try:
            terminal_input = self.driver.find_element(By.ID, "terminal-input")
            terminal_input.clear()
            terminal_input.send_keys(command_str)
            time.sleep(0.3)
            terminal_input.send_keys(Keys.RETURN)
            
            print(f"Command sent: {command_str}")
            return True
            
        except Exception as e:
            print(f"Error sending command: {e}")
            return False
    
    def execute_command(self, command_type: str, ticker = None, asset_class: str = "EQ", **kwargs) -> tuple[Dict, Optional[Any]]:
        """Execute a command by type and return (result_dict, command_instance)
        
        Args:
            command_type: Type of command to execute (DES, PRT, etc.)
            ticker: Single ticker string OR list of tickers (for PRT)
            asset_class: Asset class (for single-ticker commands)
            **kwargs: Additional arguments passed to command constructor
        """
        if command_type not in self.command_registry:
            return {
                'success': False,
                'error': f'Unknown command type: {command_type}',
                'available_commands': list(self.command_registry.keys())
            }, None
        
        # Create command instance
        command_class = self.command_registry[command_type]
        
        # Special handling for PRT command (takes list of tickers in constructor)
        if command_type == 'PRT':
            # ticker should be a list for PRT
            tickers = ticker if isinstance(ticker, list) else [ticker] if ticker else []
            command = command_class(self, tickers=tickers, **kwargs)
            result = command.execute()
        else:
            # Standard commands (DES, GIP, etc.) - single ticker + asset_class
            command = command_class(self, **kwargs)
            result = command.execute(ticker, asset_class)
        
        # Track successful commands
        if result['success']:
            self.active_commands.append(command)
            return result, command
        else:
            return result, None
    
    def close_all_windows(self):
        """Close all active command windows"""
        for command in self.active_commands:
            command.close()
        self.active_commands = []
        print("All windows closed")
