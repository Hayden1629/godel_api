"""
Test EM (Earnings Matrix), TRAN (Transcripts), and N (News) commands
"""

import asyncio
from godel_core import GodelManager

async def test_em_command():
    """Test Earnings Matrix command: EM <ticker>"""
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    try:
        session = await manager.create_session('em_test')
        await session.init_page()
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout('dev')
        
        print("✓ Logged in")
        await asyncio.sleep(2)
        
        # Test EM AAPL
        print("\nTesting: EM AAPL")
        windows_before = len(await session.get_current_windows())
        await session.send_command("AAPL EQ EM")
        await asyncio.sleep(4)
        windows_after = len(await session.get_current_windows())
        
        if windows_after > windows_before:
            print("✅ EM command works!")
            new_win = (await session.get_current_windows())[-1]
            win_id = await new_win.get_attribute("id")
            print(f"   Window: {win_id}")
            
            # Get content
            text = await new_win.text_content()
            print(f"   Content preview: {text[:200]}...")
            
            await session.screenshot("output/em_aapl.png")
            return True
        else:
            print("❌ EM command failed - no window opened")
            await session.screenshot("output/em_failed.png")
            return False
            
    finally:
        await manager.shutdown()

async def test_trans_command():
    """Test Transcripts command: TRAN <ticker>"""
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    try:
        session = await manager.create_session('trans_test')
        await session.init_page()
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout('dev')
        
        print("\n✓ Logged in")
        await asyncio.sleep(2)
        
        # Test TRAN AAPL
        print("\nTesting: TRAN AAPL")
        windows_before = len(await session.get_current_windows())
        await session.send_command("AAPL EQ TRAN")
        await asyncio.sleep(4)
        windows_after = len(await session.get_current_windows())
        
        if windows_after > windows_before:
            print("✅ TRAN command works!")
            new_win = (await session.get_current_windows())[-1]
            win_id = await new_win.get_attribute("id")
            print(f"   Window: {win_id}")
            
            text = await new_win.text_content()
            print(f"   Content preview: {text[:200]}...")
            
            await session.screenshot("output/trans_aapl.png")
            return True
        else:
            print("❌ TRAN command failed - no window opened")
            return False
            
    finally:
        await manager.shutdown()

async def test_news_command():
    """Test News command: N <ticker>"""
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    try:
        session = await manager.create_session('news_test')
        await session.init_page()
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout('dev')
        
        print("\n✓ Logged in")
        await asyncio.sleep(2)
        
        # Try different news command formats
        commands = [
            "AAPL N",
            "AAPL EQ N", 
            "N AAPL",
        ]
        
        for cmd in commands:
            print(f"\nTesting: {cmd}")
            windows_before = len(await session.get_current_windows())
            await session.send_command(cmd)
            await asyncio.sleep(4)
            windows_after = len(await session.get_current_windows())
            
            if windows_after > windows_before:
                print(f"✅ News command works with: {cmd}")
                new_win = (await session.get_current_windows())[-1]
                win_id = await new_win.get_attribute("id")
                print(f"   Window: {win_id}")
                
                text = await new_win.text_content()
                print(f"   Content preview: {text[:300]}...")
                
                await session.screenshot(f"output/news_{cmd.replace(' ', '_')}.png")
                return True, cmd
        
        print("❌ News command failed - tried all formats")
        return False, None
            
    finally:
        await manager.shutdown()

async def main():
    print("="*60)
    print("Testing EM, TRAN, and N Commands")
    print("="*60)
    
    # Test EM
    em_result = await test_em_command()
    
    # Test TRAN
    trans_result = await test_trans_command()
    
    # Test News
    news_result, news_cmd = await test_news_command()
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"EM (Earnings Matrix): {'✅' if em_result else '❌'}")
    print(f"TRAN (Transcripts):   {'✅' if trans_result else '❌'}")
    print(f"N (News):             {'✅' if news_result else '❌'} ({news_cmd if news_cmd else 'none'})")

if __name__ == "__main__":
    asyncio.run(main())
