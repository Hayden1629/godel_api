# Godel Terminal API

A Selenium-based API for interacting with the Godel Terminal to extract data programmatically.

## Overview

This API allows you to automate interactions with the Godel Terminal, specifically focusing on the DES (Description) command. It handles:
- Command execution
- Window detection and management
- Loading state monitoring
- Content extraction
- Error handling

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

```python
from des_command_api import GodelTerminalAPI

# Initialize the API with your terminal URL
terminal_url = "https://your-godel-terminal-url.com"

# Use context manager for automatic cleanup
with GodelTerminalAPI(terminal_url) as api:
    # Get description for a single ticker
    result = api.get_description("SRPT", "EQ")
    
    if result["success"]:
        print(f"Description: {result['data']['content_text']}")
    else:
        print(f"Error: {result['error']}")
```

You must put your credentials into config.py if you want the program to be able to login.

## Key Features

### 1. Single Ticker Query
```python
result = api.get_description(
    ticker="SRPT",
    asset_class="EQ",
    close_after=True  # Close window after extraction
)
```

### 2. Multiple Tickers
```python
tickers = ["AAPL", "MSFT", "GOOGL"]
results = api.get_multiple_descriptions(tickers, asset_class="EQ")

for result in results:
    if result["success"]:
        print(f"{result['ticker']}: {result['data']['content_text'][:100]}")
```

### 3. Manual Connection Management
```python
api = GodelTerminalAPI(terminal_url)
api.connect()

# Your operations here
result = api.get_description("AAPL", "EQ")

api.disconnect()
```

## Response Structure

### Success Response
```python
{
    "success": True,
    "command": "SRPT EQ DES",
    "ticker": "SRPT",
    "asset_class": "EQ",
    "data": {
        "window_id": "3729",
        "ticker": "SRPT US",
        "title": "Description",
        "content_text": "...",  # Plain text content
        "content_html": "...",  # HTML content
        "timestamp": "2025-10-01T12:00:00Z"
    }
}
```

### Error Response
```python
{
    "success": False,
    "command": "INVALID EQ DES",
    "ticker": "INVALID",
    "asset_class": "EQ",
    "error": "Window did not appear after command execution",
    "timestamp": "2025-10-01T12:00:00Z"
}
```

## Configuration

### Headless Mode
```python
# Modify the connect() method in the class
options = webdriver.ChromeOptions()
options.add_argument('--headless')
```

### Custom Chrome Driver Path
```python
api = GodelTerminalAPI(
    url=terminal_url,
    driver_path="/path/to/chromedriver"
)
```

### Timeout Configuration
You can modify timeouts in the method calls:
```python
result = api.get_description("SRPT", "EQ")
# Default timeouts:
# - Window creation: 10 seconds (in _wait_for_new_window)
# - Loading completion: 30 seconds (in _wait_for_loading_complete)
```

## Files

- **des_command_api.py**: Main API implementation
- **DES_API_Specification.md**: Detailed technical specification
- **requirements.txt**: Python dependencies
- **README.md**: This file

## Common Issues

### 1. Window Not Appearing
- **Cause**: Invalid ticker or network issues
- **Solution**: Verify ticker symbol and check network connection

### 2. Loading Timeout
- **Cause**: Slow network or large data sets
- **Solution**: Increase timeout in `_wait_for_loading_complete()`

### 3. Content Extraction Fails
- **Cause**: Content structure changed or window closed prematurely
- **Solution**: Check the HTML structure matches expected format

### 4. ChromeDriver Issues
- **Solution**: Use webdriver-manager for automatic driver management:
```python
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

service = Service(ChromeDriverManager().install())
self.driver = webdriver.Chrome(service=service, options=options)
```

## Advanced Usage

### Custom Content Extraction
You can extend the `_extract_window_content()` method to extract specific data:

```python
def _extract_custom_data(self, window):
    """Extract specific data fields"""
    content = self._extract_window_content(window)
    
    # Parse content_html for specific elements
    # Add custom extraction logic here
    
    return content
```

### Handling Multiple Window Types
The API can be extended to handle other commands (not just DES):

```python
def execute_command(self, command: str):
    """Generic command execution"""
    self._send_command(command)
    window = self._wait_for_new_window()
    # ... handle window based on command type
```

## License

MIT LICENSE