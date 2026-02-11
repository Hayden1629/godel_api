"""
FA Command - Financial Analysis (Balance Sheet, Income Statement, Cash Flow)
"""
import asyncio
import json
from typing import Optional
from playwright.async_api import Page


class FACommand:
    """Execute FA command to get financial data."""
    
    def __init__(self, session):
        self.session = session
        self.page = session.page
        
    async def execute(self, ticker: str, asset_class: str = "EQ") -> dict:
        """Execute FA command and extract financial data."""
        try:
            # Open command palette and type FA command
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("x")
            await asyncio.sleep(0.5)
            
            # Type the command
            cmd = f"{ticker} {asset_class} FA"
            await self.page.keyboard.type(cmd)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)  # Wait for window to open
            
            # Extract financial data from the window
            result = {
                "success": True,
                "ticker": ticker,
                "asset_class": asset_class,
                "data": {}
            }
            
            # Look for Financials window
            windows = await self.page.locator("[class*='window']").all()
            fa_window = None
            
            for w in windows:
                title = await w.locator("[class*='title'], [class*='header']").first.inner_text()
                if title and "Financials" in title:
                    fa_window = w
                    break
            
            if fa_window:
                # Extract data from the window
                result["data"]["window_title"] = title
                
                # Get all text content for analysis
                content = await fa_window.inner_text()
                result["data"]["content_preview"] = content[:2000] if content else ""
                
                # Look for specific metrics
                metrics = {}
                lines = content.split("\n") if content else []
                
                for line in lines:
                    line = line.strip()
                    if any(x in line for x in ["Revenue", "Income", "EPS", "Margin", "Cash"]):
                        parts = line.split()
                        if len(parts) >= 2:
                            metrics[parts[0]] = parts[1:]
                
                result["data"]["metrics"] = metrics
                
                # Close the window
                close_btn = fa_window.locator("button:has-text('Close'), [class*='close']").first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await asyncio.sleep(0.5)
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "ticker": ticker}
