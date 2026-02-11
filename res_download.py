"""
Working RES command that filters by ticker and downloads PDFs
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from godel_core import GodelManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("godel.res_working")


async def download_research_pdfs(ticker: str = "AAPL"):
    """Download research PDFs for a specific ticker."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session("res_test")
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout("dev")
    
    logger.info(f"✓ Logged in, searching research for {ticker}")
    await session.page.wait_for_timeout(2000)
    
    # Click RES button to open Research window
    try:
        res_btn = session.page.locator("button:has-text('RES')").first
        if await res_btn.count() > 0 and await res_btn.is_visible():
            await res_btn.click()
            logger.info("✓ Clicked RES button")
            await session.page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning(f"Could not click RES button: {e}")
    
    # Check if Research window opened
    windows = await session.get_current_windows()
    research_window = None
    for win in windows:
        try:
            text = await win.text_content()
            if "Research" in text or "RES" in text:
                research_window = win
                logger.info("✓ Found Research window")
                break
        except:
            pass
    
    if not research_window:
        logger.error("✗ Research window not found")
        await manager.shutdown()
        return
    
    # Filter by ticker
    logger.info(f"Filtering by ticker: {ticker}")
    try:
        # Find ticker input field
        ticker_inputs = await research_window.locator("input[placeholder*='Ticker'], input[aria-label*='Ticker']").all()
        
        for inp in ticker_inputs:
            if await inp.is_visible():
                await inp.fill(ticker)
                await inp.press("Enter")
                logger.info(f"✓ Entered ticker: {ticker}")
                await session.page.wait_for_timeout(2000)
                break
    except Exception as e:
        logger.warning(f"Could not filter by ticker: {e}")
    
    # Take screenshot
    await session.screenshot(f"output/res_{ticker.lower()}.png")
    logger.info(f"✓ Screenshot saved: output/res_{ticker.lower()}.png")
    
    # Find and download PDFs
    logger.info("Looking for PDF links...")
    try:
        # Look for rows in the research table
        rows = await research_window.locator("tr, [role='row']").all()
        logger.info(f"Found {len(rows)} rows")
        
        pdf_count = 0
        for i, row in enumerate(rows[:10]):  # First 10 rows
            try:
                # Check if row has PDF link
                pdf_links = await row.locator("a[href*='.pdf'], button:has-text('PDF')").all()
                
                if pdf_links:
                    logger.info(f"  Row {i}: Found PDF link")
                    # Click to download
                    try:
                        async with session.page.expect_download(timeout=10000) as download_info:
                            await pdf_links[0].click()
                        
                        download = await download_info.value
                        filename = download.suggested_filename or f"{ticker}_research_{i}.pdf"
                        save_path = f"output/pdfs/{filename}"
                        Path("output/pdfs").mkdir(parents=True, exist_ok=True)
                        await download.save_as(save_path)
                        
                        logger.info(f"  ✓ Downloaded: {filename}")
                        pdf_count += 1
                    except Exception as e:
                        logger.warning(f"  ✗ Download failed: {e}")
                        
            except Exception as e:
                continue
        
        logger.info(f"\nTotal PDFs downloaded: {pdf_count}")
        
    except Exception as e:
        logger.error(f"Error finding PDFs: {e}")
    
    await manager.shutdown()
    logger.info("✓ Complete")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", default="AAPL", nargs="?")
    args = parser.parse_args()
    
    asyncio.run(download_research_pdfs(args.ticker))
