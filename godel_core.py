"""
Godel Terminal Core Framework
Base classes for terminal control and command execution
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
    
    def close(self):
        """Close the command window"""
        if self.window:
            try:
                # Try to find close button by span with close icon
                close_button = self.window.find_element(
                    By.CSS_SELECTOR,
                    "span.anticon.anticon-close"
                )
                close_button.click()
                time.sleep(0.5)
                print(f"Window {self.window_id} closed")
                return True
            except NoSuchElementException:
                # Fallback: try finding by SVG data-icon attribute
                try:
                    close_svg = self.window.find_element(
                        By.CSS_SELECTOR,
                        "svg[data-icon='close']"
                    )
                    close_svg.click()
                    time.sleep(0.5)
                    print(f"Window {self.window_id} closed (via SVG)")
                    return True
                except Exception as e:
                    print(f"Error closing window: {e}")
                    return False
            except Exception as e:
                print(f"Error closing window: {e}")
                return False
        return False


class GodelTerminalController:
    """Controller for Godel Terminal command execution"""
    
    def __init__(self, url: str, headless: bool = False):
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
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(self.url)
        
        # Initialize DOM monitor
        self.dom_monitor = DOMMonitor(self.driver)
        
        time.sleep(3)
        print(f"Connected to {self.url}")
    
    def disconnect(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            print("Disconnected")
    
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

            # Click login button to submit
            login_button = self.driver.find_element(By.XPATH, "//button[text()='Login']")
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
    
    def execute_command(self, command_type: str, ticker: str, asset_class: str = "EQ") -> tuple[Dict, Optional[Any]]:
        """Execute a command by type and return (result_dict, command_instance)"""
        if command_type not in self.command_registry:
            return {
                'success': False,
                'error': f'Unknown command type: {command_type}',
                'available_commands': list(self.command_registry.keys())
            }, None
        
        # Create command instance
        command_class = self.command_registry[command_type]
        command = command_class(self)
        
        # Execute and track
        result = command.execute(ticker, asset_class)
        
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