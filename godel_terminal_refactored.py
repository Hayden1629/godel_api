"""
Godel Terminal Command Framework
Generic command execution with specific command implementations
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
from typing import Dict, Optional, List, Any
from abc import ABC, abstractmethod
import time
import json
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD


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


class DESCommand(BaseCommand):
    """Description (DES) command - extracts company information"""
    
    def get_command_string(self, ticker: str, asset_class: str) -> str:
        return f"{ticker} {asset_class} DES"
    
    def expand_description(self) -> bool:
        """Click 'See more' to expand full description"""
        try:
            # Find the "See more" link using XPath for exact text match
            see_more_link = self.window.find_element(
                By.XPATH,
                ".//a[contains(@class, 'cursor-pointer') and contains(text(), 'See more')]"
            )
            see_more_link.click()
            time.sleep(0.5)  # Wait for expansion animation
            print("Description expanded")
            return True
        except NoSuchElementException:
            print("'See more' link not found (description may already be expanded)")
            return False
        except Exception as e:
            print(f"Error expanding description: {e}")
            return False
    
    def expand_analyst_ratings(self) -> bool:
        """Click 'Show all' to expand all analyst ratings"""
        try:
            show_all_button = self.window.find_element(
                By.XPATH,
                "//div[@class='cursor-pointer p-2' and text()='Show all']"
            )
            if show_all_button:
                show_all_button.click()
                time.sleep(0.5)  # Wait for ratings to load
                print("Analyst ratings expanded")
                return True
            return False
        except NoSuchElementException:
            print("'Show all' button not found (ratings may already be expanded)")
            return False
        except Exception as e:
            print(f"Error expanding analyst ratings: {e}")
            return False
    
    def extract_data(self) -> Dict:
        """Extract all data from DES window"""
        if not self.window:
            raise ValueError("No window available for extraction")
        
        # Expand sections before extracting
        self.expand_description()
        self.expand_analyst_ratings()
        
        data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'window_id': self.window_id,
            'ticker': self._extract_ticker(),
            'company_info': self._extract_company_header(),
            'description': self._extract_description(),
            'eps_estimates': self._extract_eps_estimates(),
            'analyst_ratings': self._extract_analyst_ratings(),
            'snapshot': self._extract_snapshot()
        }
        
        return data
    
    def _extract_ticker(self) -> Optional[str]:
        """Extract ticker from input field"""
        try:
            # Find the ticker input - it has specific classes and is uppercase
            ticker_input = self.window.find_element(
                By.CSS_SELECTOR,
                "input.uppercase.bg-\\[\\#121212\\]"
            )
            ticker_value = ticker_input.get_attribute('value')
            return ticker_value if ticker_value else None
        except Exception as e:
            print(f"Error extracting ticker: {e}")
            return None
    
    def _extract_company_header(self) -> Dict:
        """Extract company name, logo, website, address, CEO"""
        try:
            data = {}
            
            # Company name - extract just the text without the asset class badge
            try:
                company_name_h1 = self.window.find_element(By.CSS_SELECTOR, "h1.text-2xl.font-semibold")
                # Get text and remove the asset class badge text
                full_text = company_name_h1.text
                # Try to find and remove asset class badge
                try:
                    badge = self.window.find_element(By.CSS_SELECTOR, "span.blue-box")
                    badge_text = badge.text.strip()
                    data['company_name'] = full_text.replace(badge_text, '').strip()
                except:
                    data['company_name'] = full_text.strip()
            except Exception as e:
                print(f"Error extracting company name: {e}")
                data['company_name'] = None
            
            # Asset class
            try:
                asset_class = self.window.find_element(By.CSS_SELECTOR, "span.blue-box")
                data['asset_class'] = asset_class.text.strip()
            except:
                data['asset_class'] = None
            
            # Logo URL
            try:
                logo_div = self.window.find_element(By.CSS_SELECTOR, "div.w-16.h-16")
                logo_style = logo_div.get_attribute('style')
                if 'background-image: url(' in logo_style:
                    # Handle both url("...") and url(...)
                    if 'url("' in logo_style:
                        logo_url = logo_style.split('url("')[1].split('")')[0]
                    elif 'url(&quot;' in logo_style:
                        logo_url = logo_style.split('url(&quot;')[1].split('&quot;)')[0]
                    else:
                        logo_url = logo_style.split('url(')[1].split(')')[0].strip('"\'')
                    data['logo_url'] = logo_url
                else:
                    data['logo_url'] = None
            except Exception as e:
                print(f"Error extracting logo: {e}")
                data['logo_url'] = None
            
            # Website
            try:
                website_link = self.window.find_element(By.CSS_SELECTOR, "a[href][target='_blank']")
                data['website'] = website_link.get_attribute('href')
            except Exception as e:
                print(f"Error extracting website: {e}")
                data['website'] = None
            
            # Address and CEO - find by the uppercase text style
            try:
                info_div = self.window.find_element(
                    By.XPATH,
                    ".//div[contains(@class, 'text-right') and contains(@class, 'uppercase')]"
                )
                info_text = info_div.text
                info_lines = [line.strip() for line in info_text.split('\n') if line.strip()]
                data['address'] = info_lines[0] if len(info_lines) > 0 else None
                data['ceo'] = info_lines[1] if len(info_lines) > 1 else None
            except Exception as e:
                print(f"Error extracting address/CEO: {e}")
                data['address'] = None
                data['ceo'] = None
            
            return data
        except Exception as e:
            print(f"Error extracting company header: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _extract_description(self) -> Optional[str]:
        """Extract company description (should be called after expand_description)"""
        try:
            # Find the div containing company description - it's in the main content area
            # Looking for divs with specific color style that contain meaningful text
            desc_divs = self.window.find_elements(By.XPATH, ".//div[contains(@style, 'color: rgb(234, 234, 234)')]")
            for div in desc_divs:
                text = div.text.strip()
                # Check if this looks like a company description (long text mentioning company)
                if len(text) > 100:  # Descriptions are typically longer
                    # Clean up any UI elements
                    text = text.replace("See more", "").replace("See less", "").strip()
                    return text
            return None
        except Exception as e:
            print(f"Error extracting description: {e}")
            return None
    
    def _extract_eps_estimates(self) -> Dict:
        """Extract EPS estimates table - returns flat dict like {'Q4, Dec 25': '-0.85', ...}"""
        try:
            eps_data = {}
            # Find the EPS ESTIMATES table - use relative XPath from window
            eps_table = self.window.find_element(
                By.XPATH,
                ".//span[text()='EPS ESTIMATES']/ancestor::div[1]/following-sibling::table"
            )
            
            # Get headers (Q4, FY25, FY26) from thead
            headers = []
            header_row = eps_table.find_element(By.TAG_NAME, "thead")
            header_cells = header_row.find_elements(By.TAG_NAME, "td")
            for cell in header_cells:
                text = cell.text.strip()
                if text and text.lower() != '':
                    headers.append(text)
            
            # Get data rows from tbody
            tbody = eps_table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            # First row should be Date, second row should be EPS
            date_row = None
            eps_row = None
            
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) > 0:
                    row_label = cells[0].text.strip().lower()
                    if row_label == 'date':
                        date_row = [cell.text.strip() for cell in cells[1:]]
                    elif row_label == 'eps':
                        eps_row = [cell.text.strip() for cell in cells[1:]]
            
            # Combine headers with dates and EPS values
            if date_row and eps_row and headers:
                for i, header in enumerate(headers):
                    if i < len(date_row) and i < len(eps_row):
                        # Format: "Q4, Dec 25" or "FY25, Dec 25"
                        key = f"{header}, {date_row[i]}"
                        eps_data[key] = eps_row[i]
            
            return eps_data
        except Exception as e:
            print(f"Error extracting EPS estimates: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _extract_analyst_ratings(self) -> List[Dict]:
        """Extract analyst ratings table"""
        try:
            ratings = []
            # Find the analyst ratings table - use relative XPath from window
            ratings_table = self.window.find_element(
                By.XPATH,
                ".//span[text()='ANALYST RATINGS']/ancestor::div[1]/following-sibling::div//table"
            )
            
            tbody = ratings_table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 5:
                        # Target field has complex structure with arrows, extract just the text
                        target_text = cells[3].text.strip()
                        # Clean up the target to format like "$50→$50"
                        target_text = target_text.replace('\n', '').replace('  ', ' ')
                        
                        rating = {
                            'Firm': cells[0].text.strip(),
                            'Analyst': cells[1].text.strip(),
                            'Rating': cells[2].text.strip(),
                            'Target': target_text,
                            'Date': cells[4].text.strip()
                        }
                        ratings.append(rating)
                except Exception as e:
                    print(f"Error extracting rating row: {e}")
                    continue
            
            return ratings
        except Exception as e:
            print(f"Error extracting analyst ratings: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _extract_snapshot(self) -> Dict:
        """Extract snapshot data from right panel - returns flat dict"""
        try:
            snapshot = {}
            # Find the SNAPSHOT div and its content area - use relative XPath from window
            snapshot_div = self.window.find_element(
                By.XPATH,
                ".//div[text()='SNAPSHOT']/following-sibling::div[@class='flex-1']"
            )
            
            # Get all sections with mt-2 class (Market Info, Company Stats, etc.)
            sections = snapshot_div.find_elements(By.CSS_SELECTOR, "div.mt-2")
            
            for section in sections:
                try:
                    # Get all key-value pairs in this section
                    pairs = section.find_elements(By.CSS_SELECTOR, "div.flex.justify-between.text-sm")
                    
                    for pair in pairs:
                        spans = pair.find_elements(By.TAG_NAME, "span")
                        if len(spans) >= 2:
                            key = spans[0].text.strip()
                            value = spans[1].text.strip()
                            # Add directly to flat dict, no nesting
                            if key and value:
                                snapshot[key] = value
                except Exception as e:
                    print(f"Error extracting snapshot section: {e}")
                    continue
            
            return snapshot
        except Exception as e:
            print(f"Error extracting snapshot: {e}")
            import traceback
            traceback.print_exc()
            return {}


class GCommand(BaseCommand):
    """Chart (G) command - displays price chart"""
    
    def get_command_string(self, ticker: str, asset_class: str) -> str:
        return f"{ticker} {asset_class} G"
    
    def extract_data(self) -> Dict:
        """Extract chart data - placeholder for future implementation"""
        data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'window_id': self.window_id,
            'ticker': self._extract_ticker(),
            'type': 'chart',
            'note': 'Chart data extraction not yet implemented'
        }
        return data
    
    def _extract_ticker(self) -> Optional[str]:
        """Extract ticker from input field"""
        try:
            ticker_input = self.window.find_element(By.CSS_SELECTOR, "input[value]")
            return ticker_input.get_attribute('value')
        except:
            return None


class GIPCommand(BaseCommand):
    """Intraday Chart (GIP) command - displays intraday price chart"""
    
    def get_command_string(self, ticker: str, asset_class: str) -> str:
        return f"{ticker} {asset_class} GIP"
    
    def extract_data(self) -> Dict:
        """Extract intraday chart data - placeholder for future implementation"""
        data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'window_id': self.window_id,
            'ticker': self._extract_ticker(),
            'type': 'intraday_chart',
            'note': 'Intraday chart data extraction not yet implemented'
        }
        return data
    
    def _extract_ticker(self) -> Optional[str]:
        """Extract ticker from input field"""
        try:
            ticker_input = self.window.find_element(By.CSS_SELECTOR, "input[value]")
            return ticker_input.get_attribute('value')
        except:
            return None


class QMCommand(BaseCommand):
    """Quote Monitor (QM) command - monitors real-time quotes"""
    
    def get_command_string(self, ticker: str, asset_class: str) -> str:
        return f"{ticker} {asset_class} QM"
    
    def extract_data(self) -> Dict:
        """Extract quote monitor data - placeholder for future implementation"""
        data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'window_id': self.window_id,
            'ticker': self._extract_ticker(),
            'type': 'quote_monitor',
            'note': 'Quote monitor data extraction not yet implemented'
        }
        return data
    
    def _extract_ticker(self) -> Optional[str]:
        """Extract ticker from input field"""
        try:
            ticker_input = self.window.find_element(By.CSS_SELECTOR, "input[value]")
            return ticker_input.get_attribute('value')
        except:
            return None


class GodelTerminalController:
    """Generic controller for Godel Terminal"""
    
    # Command registry
    COMMANDS = {
        'DES': DESCommand,
        'G': GCommand,
        'GIP': GIPCommand,
        'QM': QMCommand
    }
    
    def __init__(self, url: str, headless: bool = False):
        self.url = url
        self.driver = None
        self.dom_monitor = None
        self.headless = headless
        self.active_commands = []
        
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
    
    def login(self):
        """Log in to the website"""
        username = GODEL_USERNAME
        password = GODEL_PASSWORD
        
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
        if command_type not in self.COMMANDS:
            return {
                'success': False,
                'error': f'Unknown command type: {command_type}',
                'available_commands': list(self.COMMANDS.keys())
            }, None
        
        # Create command instance
        command_class = self.COMMANDS[command_type]
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


# Main execution script
def main():
    """Main execution function"""
    
    # Configuration
    TERMINAL_URL = GODEL_URL
    TICKER = "SRPT"
    ASSET_CLASS = "EQ"
    
    print("=" * 60)
    print("Godel Terminal Command Framework")
    print("=" * 60)
    
    # Initialize controller
    controller = GodelTerminalController(TERMINAL_URL, headless=False)
    
    try:
        # Connect and login
        controller.connect()
        controller.login()
        
        # Open terminal
        if not controller.open_terminal():
            print("Failed to open terminal")
            return
        
        # Execute DES command
        result, des_command = controller.execute_command('DES', TICKER, ASSET_CLASS)
        
        # Display results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        
        if result['success']:
            # Save full data to JSON
            output_file = f"des_data_{TICKER}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"\n✓ Full data saved to: {output_file}")
            
            # You can now close the window if needed
            des_command.close()
        else:
            print(f"✗ Command failed: {result.get('error')}")
        
        # Keep browser open for inspection
        print("\n" + "=" * 60)
        input("Press Enter to close browser...")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main() 