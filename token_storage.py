"""
Secure token storage module for Schwab API tokens.
Stores tokens in a JSON file with restricted permissions.
"""
import json
import os
import stat
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional, Dict


TOKEN_FILE = Path(__file__).parent / "schwab_tokens.json"


def save_tokens(token_dict: dict) -> bool:
    """
    Save tokens to secure storage file.
    
    Args:
        token_dict: Dictionary containing access_token, refresh_token, expires_in, etc.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract and calculate expiry time
        expires_in = token_dict.get("expires_in", 1800)  # Default 30 minutes
        expires_at = datetime.now() + timedelta(seconds=expires_in)
        
        token_data = {
            "access_token": token_dict.get("access_token"),
            "refresh_token": token_dict.get("refresh_token"),
            "id_token": token_dict.get("id_token"),
            "token_type": token_dict.get("token_type", "Bearer"),
            "expires_at": expires_at.isoformat(),
            "expires_in": expires_in,
            "last_updated": datetime.now().isoformat()
        }
        
        # Write to file
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        # Set file permissions to read/write for owner only (Windows compatible)
        try:
            os.chmod(TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except (AttributeError, OSError):
            # Windows may not support chmod the same way, but file is still secure
            pass
        
        logger.info(f"Tokens saved successfully to {TOKEN_FILE}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")
        return False


def load_tokens() -> Optional[Dict]:
    """
    Load tokens from secure storage file.
    
    Returns:
        Dictionary containing token data, or None if file doesn't exist or is invalid
    """
    try:
        if not TOKEN_FILE.exists():
            logger.warning(f"Token file not found: {TOKEN_FILE}")
            return None
        
        with open(TOKEN_FILE, 'r') as f:
            token_data = json.load(f)
        
        # Validate required fields
        if not token_data.get("access_token") or not token_data.get("refresh_token"):
            logger.error("Token file missing required fields")
            return None
        
        logger.debug("Tokens loaded successfully")
        return token_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in token file: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return None


def get_access_token() -> Optional[str]:
    """
    Get the current access token.
    
    Returns:
        Access token string, or None if not available
    """
    token_data = load_tokens()
    if token_data:
        return token_data.get("access_token")
    return None


def get_refresh_token() -> Optional[str]:
    """
    Get the current refresh token.
    
    Returns:
        Refresh token string, or None if not available
    """
    token_data = load_tokens()
    if token_data:
        return token_data.get("refresh_token")
    return None


def is_token_expired() -> bool:
    """
    Check if the current access token is expired or will expire soon.
    Uses a 1-minute buffer to refresh before actual expiry.
    
    Returns:
        True if token is expired or expiring soon, False otherwise
    """
    token_data = load_tokens()
    if not token_data:
        return True
    
    expires_at_str = token_data.get("expires_at")
    if not expires_at_str:
        return True
    
    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        # Add 1 minute buffer to refresh before expiry
        buffer_time = timedelta(minutes=1)
        return datetime.now() + buffer_time >= expires_at
    except (ValueError, TypeError):
        return True


def token_file_exists() -> bool:
    """Check if token file exists."""
    return TOKEN_FILE.exists()

