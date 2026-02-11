"""
Capture HTTP API endpoints by monitoring network traffic during various operations
"""

import asyncio
import json
from godel_core import GodelManager, NetworkInterceptor

async def discover_http_apis():
    """Discover HTTP API endpoints by intercepting network traffic."""
    
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session('api_discovery')
    await session.init_page()
    
    # Set up network interceptor
    interceptor = NetworkInterceptor(session.page)
    interceptor.start(capture_ws=True)
    
    print("✓ Network interceptor started")
    
    # Login
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    print("✓ Logged in")
    await asyncio.sleep(3)
    
    # Load layout
    await session.load_layout('dev')
    print("✓ Layout loaded")
    await asyncio.sleep(2)
    
    # Run various commands to trigger API calls
    commands = [
        'DES AAPL',
        'MOST',
        'FA AAPL',
        'TOP',
        'EM AAPL',
        'AAPL EQ N',
    ]
    
    print("\nRunning commands to trigger API calls...")
    for cmd in commands:
        print(f"  Running: {cmd}")
        await session.send_command(cmd)
        await asyncio.sleep(4)
    
    # Wait a bit more for any pending requests
    await asyncio.sleep(5)
    
    # Stop interceptor and analyze
    interceptor.stop()
    
    print(f"\n✓ Captured {len(interceptor.requests)} HTTP requests")
    print(f"✓ Captured {len(interceptor.responses)} HTTP responses")
    print(f"✓ Captured {len(interceptor.ws_frames)} WebSocket frames")
    
    # Extract unique API endpoints
    api_endpoints = set()
    
    for req in interceptor.requests:
        url = req.get('url', '')
        # Filter for API endpoints
        if any(x in url for x in ['api', 'godelterminal.com', 'fetch', 'data']):
            api_endpoints.add(url)
    
    print(f"\n🎯 Found {len(api_endpoints)} unique API endpoints:")
    for url in sorted(api_endpoints):
        print(f"  - {url}")
    
    # Save to file
    with open('output/discovered_apis.json', 'w') as f:
        json.dump({
            'endpoints': list(api_endpoints),
            'requests': interceptor.requests[:50],  # First 50
            'responses': [{'url': r.get('url'), 'status': r.get('status')} for r in interceptor.responses[:50]]
        }, f, indent=2)
    
    print(f"\n✓ Saved to output/discovered_apis.json")
    
    await manager.shutdown()

if __name__ == "__main__":
    asyncio.run(discover_http_apis())
