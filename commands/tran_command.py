"""
TRAN Command - Transcripts
"""
import asyncio
from typing import Optional


class TRANCommand:
    """Execute TRAN command for earnings transcripts."""
    
    def __init__(self, session):
        self.session = session
        self.page = session.page
        
    async def execute(self, ticker: str, asset_class: str = "EQ") -> dict:
        """Execute TRAN command and extract transcript data."""
        try:
            # Open command palette
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("x")
            await asyncio.sleep(0.5)
            
            # Type TRAN command
            cmd = f"{ticker} {asset_class} TRAN"
            await self.page.keyboard.type(cmd)
            await asyncio.sleep(0.5)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
            
            result = {
                "success": True,
                "ticker": ticker,
                "asset_class": asset_class,
                "transcripts": []
            }
            
            # Look for Transcripts window
            windows = await self.page.locator("[class*='window']").all()
            tran_window = None
            
            for w in windows:
                try:
                    title_elem = w.locator("[class*='title'], [class*='header']").first
                    if await title_elem.count() > 0:
                        title = await title_elem.inner_text()
                        if "Transcript" in title:
                            tran_window = w
                            break
                except:
                    continue
            
            if tran_window:
                content = await tran_window.inner_text()
                result["content_preview"] = content[:5000] if content else ""
                
                # Extract available quarters
                quarters = []
                lines = content.split("\n") if content else []
                
                for line in lines:
                    line = line.strip()
                    if "Q" in line and any(x in line for x in ["2024", "2025", "2026"]):
                        quarters.append(line)
                
                result["available_quarters"] = list(set(quarters))[:10]
                
                # Close window
                try:
                    close_btn = tran_window.locator("button:has-text('Close'), [class*='close']").first
                    if await close_btn.count() > 0:
                        await close_btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e), "ticker": ticker}
