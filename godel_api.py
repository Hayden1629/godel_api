"""
Godel Terminal API
Python module interface for programmatic use
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from godel_core import GodelTerminalController
from commands import (
    DESCommand, PRTCommand, MOSTCommand,
    GCommand, GIPCommand, QMCommand
)

try:
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
except ImportError:
    GODEL_URL = "https://app.godelterminal.com/"
    GODEL_USERNAME = None
    GODEL_PASSWORD = None


class GodelAPI:
    """
    High-level API wrapper for Godel Terminal commands.
    Manages controller lifecycle and provides convenient methods for each command.
    """
    
    def __init__(self, url: str = None, username: str = None, password: str = None, headless: bool = False):
        """
        Initialize Godel API
        
        Args:
            url: Godel Terminal URL (defaults to config.py or default URL)
            username: Godel Terminal username (defaults to config.py)
            password: Godel Terminal password (defaults to config.py)
            headless: Run browser in headless mode
        """
        self.url = url or GODEL_URL
        self.username = username or GODEL_USERNAME
        self.password = password or GODEL_PASSWORD
        self.headless = headless
        self.controller: Optional[GodelTerminalController] = None
        self._connected = False
        
        if not self.username or not self.password:
            raise ValueError("Username and password must be provided either via config.py or as arguments")
    
    def connect(self, layout: str = "dev") -> bool:
        """
        Connect to Godel Terminal and log in
        
        Args:
            layout: Layout name to load (default: "dev")
            
        Returns:
            bool: True if connection successful
        """
        try:
            self.controller = GodelTerminalController(self.url, headless=self.headless)
            self.controller.connect()
            self.controller.login(self.username, self.password)
            
            if layout:
                self.controller.load_layout(layout)
            
            self._connected = True
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Godel Terminal"""
        if self.controller:
            self.controller.close_all_windows()
            self.controller.disconnect()
            self.controller = None
            self._connected = False
    
    def _ensure_connected(self):
        """Ensure controller is connected"""
        if not self._connected or not self.controller:
            raise RuntimeError("Not connected. Call connect() first.")
    
    def des(self, ticker: str, asset_class: str = "EQ") -> Dict[str, Any]:
        """
        Execute DES (Description) command
        
        Args:
            ticker: Ticker symbol
            asset_class: Asset class (default: "EQ")
            
        Returns:
            dict: Result dictionary with 'success', 'data', etc.
        """
        self._ensure_connected()
        des = DESCommand(self.controller)
        return des.execute(ticker, asset_class)
    
    def prt(self, tickers: List[str], output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute PRT (Pattern Real-Time) command
        
        Args:
            tickers: List of ticker symbols to analyze
            output_path: Optional path to save CSV/JSON (default: None, uses Downloads folder)
            
        Returns:
            dict: Result dictionary with 'success', 'data', 'csv_file', etc.
        """
        self._ensure_connected()
        prt = PRTCommand(self.controller, tickers=tickers)
        result = prt.execute()
        
        if result['success'] and output_path:
            if output_path.endswith('.csv'):
                prt.save_to_csv(output_path)
            elif output_path.endswith('.json'):
                prt.save_to_json(output_path)
            else:
                prt.save_to_csv(output_path + '.csv')
        
        return result
    
    def most(self, tab: str = "ACTIVE", limit: int = 75, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute MOST (Most Active Stocks) command
        
        Args:
            tab: Tab to select - "ACTIVE", "GAINERS", "LOSERS", or "VALUE" (default: "ACTIVE")
            limit: Number of results - 10, 25, 50, 75, or 100 (default: 75)
            output_path: Optional path to save CSV/JSON
            
        Returns:
            dict: Result dictionary with 'success', 'data', etc.
        """
        self._ensure_connected()
        most = MOSTCommand(self.controller, tab=tab, limit=limit)
        result = most.execute()
        
        if result['success'] and output_path:
            if output_path.endswith('.csv'):
                most.save_to_csv(output_path)
            elif output_path.endswith('.json'):
                most.save_to_json(output_path)
            else:
                most.save_to_csv(output_path + '.csv')
        
        return result
    
    def g(self, ticker: str, asset_class: str = "EQ") -> Dict[str, Any]:
        """
        Execute G (Chart) command
        
        Args:
            ticker: Ticker symbol
            asset_class: Asset class (default: "EQ")
            
        Returns:
            dict: Result dictionary with 'success', 'data', etc.
        """
        self._ensure_connected()
        g = GCommand(self.controller)
        return g.execute(ticker, asset_class)
    
    def gip(self, ticker: str, asset_class: str = "EQ") -> Dict[str, Any]:
        """
        Execute GIP (Intraday Chart) command
        
        Args:
            ticker: Ticker symbol
            asset_class: Asset class (default: "EQ")
            
        Returns:
            dict: Result dictionary with 'success', 'data', etc.
        """
        self._ensure_connected()
        gip = GIPCommand(self.controller)
        return gip.execute(ticker, asset_class)
    
    def qm(self, ticker: str, asset_class: str = "EQ") -> Dict[str, Any]:
        """
        Execute QM (Quote Monitor) command
        
        Args:
            ticker: Ticker symbol
            asset_class: Asset class (default: "EQ")
            
        Returns:
            dict: Result dictionary with 'success', 'data', etc.
        """
        self._ensure_connected()
        qm = QMCommand(self.controller)
        return qm.execute(ticker, asset_class)
    
    def close_all_windows(self):
        """Close all active command windows"""
        if self.controller:
            self.controller.close_all_windows()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Convenience functions for quick usage
def quick_des(ticker: str, asset_class: str = "EQ", url: str = None, 
              username: str = None, password: str = None) -> Dict[str, Any]:
    """
    Quick DES command execution (connects, executes, disconnects)
    
    Args:
        ticker: Ticker symbol
        asset_class: Asset class (default: "EQ")
        url: Godel Terminal URL (optional, uses config.py if not provided)
        username: Username (optional, uses config.py if not provided)
        password: Password (optional, uses config.py if not provided)
        
    Returns:
        dict: Result dictionary
    """
    with GodelAPI(url=url, username=username, password=password) as api:
        return api.des(ticker, asset_class)


def quick_prt(tickers: List[str], url: str = None, 
              username: str = None, password: str = None) -> Dict[str, Any]:
    """
    Quick PRT command execution (connects, executes, disconnects)
    
    Args:
        tickers: List of ticker symbols
        url: Godel Terminal URL (optional, uses config.py if not provided)
        username: Username (optional, uses config.py if not provided)
        password: Password (optional, uses config.py if not provided)
        
    Returns:
        dict: Result dictionary
    """
    with GodelAPI(url=url, username=username, password=password) as api:
        return api.prt(tickers)


def quick_most(tab: str = "ACTIVE", limit: int = 75, url: str = None,
               username: str = None, password: str = None) -> Dict[str, Any]:
    """
    Quick MOST command execution (connects, executes, disconnects)
    
    Args:
        tab: Tab to select (default: "ACTIVE")
        limit: Number of results (default: 75)
        url: Godel Terminal URL (optional, uses config.py if not provided)
        username: Username (optional, uses config.py if not provided)
        password: Password (optional, uses config.py if not provided)
        
    Returns:
        dict: Result dictionary
    """
    with GodelAPI(url=url, username=username, password=password) as api:
        return api.most(tab=tab, limit=limit)
