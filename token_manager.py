"""
Token manager that automatically refreshes Schwab API tokens every 29 minutes.
Provides thread-safe access to current access token.
"""
import threading
import time
from datetime import datetime, timedelta
from loguru import logger
from token_storage import (
    get_access_token, 
    get_refresh_token, 
    is_token_expired, 
    token_file_exists,
    save_tokens
)
from config import SCWAB_APP_KEY, SCWAB_APP_SECRET
import base64
import requests


class TokenManager:
    """
    Manages Schwab API tokens with automatic refresh every 29 minutes.
    Thread-safe singleton pattern.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TokenManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._token_lock = threading.Lock()
        self._refresh_thread = None
        self._stop_refresh = threading.Event()
        self._access_token = None
        self._refresh_interval = 29 * 60  # 29 minutes in seconds
        
        # Verify token file exists
        if not token_file_exists():
            logger.error("Token file not found. Please run get_OG_tokens.py first.")
            raise FileNotFoundError("Token file not found. Run get_OG_tokens.py to initialize tokens.")
        
        # Load initial token
        self._refresh_token_sync()
        
        # Start background refresh thread
        self.start_auto_refresh()
        
        self._initialized = True
        logger.info("TokenManager initialized")
    
    def _refresh_token_sync(self) -> bool:
        """
        Synchronously refresh the access token.
        Thread-safe.
        
        Returns:
            True if refresh was successful, False otherwise
        """
        with self._token_lock:
            try:
                # Check if we need to refresh
                if not is_token_expired() and self._access_token:
                    logger.debug("Token still valid, skipping refresh")
                    return True
                
                logger.info("Refreshing access token...")
                
                refresh_token_value = get_refresh_token()
                if not refresh_token_value:
                    logger.error("No refresh token available")
                    return False
                
                # Make refresh request
                payload = {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token_value,
                }
                headers = {
                    "Authorization": f'Basic {base64.b64encode(f"{SCWAB_APP_KEY}:{SCWAB_APP_SECRET}".encode()).decode()}',
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                
                response = requests.post(
                    url="https://api.schwabapi.com/v1/oauth/token",
                    headers=headers,
                    data=payload,
                )
                
                if response.status_code == 200:
                    token_dict = response.json()
                    if save_tokens(token_dict):
                        self._access_token = token_dict.get("access_token")
                        logger.info("Token refreshed successfully")
                        return True
                    else:
                        logger.error("Failed to save refreshed tokens")
                        return False
                else:
                    logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                    return False
                    
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                return False
    
    def get_access_token(self) -> str:
        """
        Get the current access token.
        Automatically refreshes if expired.
        Thread-safe.
        
        Returns:
            Current access token string
            
        Raises:
            RuntimeError: If token cannot be obtained
        """
        with self._token_lock:
            # Refresh if expired
            if is_token_expired() or not self._access_token:
                if not self._refresh_token_sync():
                    raise RuntimeError("Failed to refresh access token")
            
            return self._access_token
    
    def _refresh_loop(self):
        """Background thread that refreshes tokens every 29 minutes."""
        logger.info(f"Starting token refresh loop (every {self._refresh_interval/60:.1f} minutes)")
        
        while not self._stop_refresh.is_set():
            # Wait for refresh interval or until stopped
            if self._stop_refresh.wait(timeout=self._refresh_interval):
                # Stop event was set
                break
            
            # Refresh token
            self._refresh_token_sync()
        
        logger.info("Token refresh loop stopped")
    
    def start_auto_refresh(self):
        """Start the background thread for automatic token refresh."""
        if self._refresh_thread is None or not self._refresh_thread.is_alive():
            self._stop_refresh.clear()
            self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
            self._refresh_thread.start()
            logger.info("Auto-refresh thread started")
    
    def stop_auto_refresh(self):
        """Stop the background token refresh thread."""
        if self._refresh_thread and self._refresh_thread.is_alive():
            self._stop_refresh.set()
            self._refresh_thread.join(timeout=5)
            logger.info("Auto-refresh thread stopped")
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop_auto_refresh()


# Global instance getter
def get_token_manager() -> TokenManager:
    """
    Get the global TokenManager instance.
    
    Returns:
        TokenManager singleton instance
    """
    return TokenManager()

