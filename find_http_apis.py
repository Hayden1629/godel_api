"""
Search for HTTP API endpoints by monitoring network traffic
"""

import asyncio
import json
from godel_core import GodelManager, NetworkInterceptor
from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD

async def find_http_apis():
    """Monitor network traffic to find HTTP API endpoints."""
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    try:
        session = await manager.create_session('api_discovery')
        await session.init_page()
        
        # Setup network interceptor
        interceptor = NetworkInterceptor(session.page)
        interceptor.start(capture_ws=True)
        
        print("✓ Started network monitoring")
        
        # Login
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout('dev')
        print("✓ Logged in")
        
        # Run various commands to trigger API calls
        commands = [
            'AAPL EQ DES',
            'AAPL EQ EM',
            'MOST',
            'TOP',
        ]
        
        for cmd in commands:
            print(f"\nSending: {cmd}")
            await session.send_command(cmd)
            await asyncio.sleep(3)
        
        # Wait a bit for any async requests
        await asyncio.sleep(5)
        
        # Stop interceptor and analyze
        interceptor.stop()
        
        print("\n" + "="*60)
        print("HTTP REQUESTS CAPTURED")
        print("="*60)
        
        seen_urls = set()
        for req in interceptor.requests:
            url = req.get('url', '')
            method = req.get('method', 'GET')
            
            # Filter for API endpoints
            if any(x in url for x in ['api.', 'godelterminal.com/api', 'fetch', 'get', 'data']):
                if url not in seen_urls:
                    seen_urls.add(url)
                    print(f"\n{method}: {url[:100]}")
                    
                    # Try to get response if available
                    for resp in interceptor.responses:
                        if resp.get('url') == url:
                            status = resp.get('status', '?')
                            print(f"   Status: {status}")
                            break
        
        print("\n" + "="*60)
        print("WEBSOCKET ENDPOINTS")
        print("="*60)
        
        for ws in interceptor._ws_objects:
            print(f"\nWebSocket: {ws.get('url', 'unknown')}")
        
        # Save results
        results = {
            'http_requests': [{'url': r.get('url'), 'method': r.get('method')} for r in interceptor.requests],
            'http_responses': [{'url': r.get('url'), 'status': r.get('status')} for r in interceptor.responses],
            'ws_connections': [{'url': r.get('url')} for r in interceptor._ws_objects],
        }
        
        with open('output/api_discovery.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print("\n✓ Results saved to output/api_discovery.json")
        
    finally:
        await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(find_http_apis())
