#!/usr/bin/env python3
"""
Diagnostic script to capture and display WebSocket traffic from Godel Terminal chat
"""

import asyncio
import json
import sys
from datetime import datetime

sys.path.insert(0, '/Users/troy/.openclaw/workspace/godel_api')

from godel_core import GodelManager

async def main():
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    
    print("🔍 Starting WebSocket diagnostic...")
    print(f"   URL: {GODEL_URL}")
    print(f"   User: {GODEL_USERNAME}")
    
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    session = await manager.create_session('diagnostic')
    await session.init_page()
    
    # Start interceptor BEFORE login to catch all WebSocket connections
    from godel_core import NetworkInterceptor
    interceptor = NetworkInterceptor(session.page)
    interceptor.start(capture_ws=True)
    
    print("\n📡 WebSocket interceptor started (before login)")
    
    # Login
    print("\n🔐 Logging in...")
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)
    await session.load_layout('dev')
    print("✅ Logged in, layout loaded")
    
    # Wait a moment for any initial WebSocket connections
    print("\n⏳ Waiting 5s for initial WebSocket connections...")
    await asyncio.sleep(5)
    
    print(f"   WebSocket frames so far: {len(interceptor.ws_frames)}")
    
    # Open chat
    print("\n💬 Opening chat with 'CHAT #general'...")
    await session.send_command('CHAT #general')
    await asyncio.sleep(5)
    
    print(f"   WebSocket frames after CHAT command: {len(interceptor.ws_frames)}")
    
    # Monitor for 30 seconds
    print("\n👂 Monitoring for 30 seconds... (wait for chat messages)")
    start_time = datetime.now()
    
    last_frame_count = len(interceptor.ws_frames)
    
    while (datetime.now() - start_time).seconds < 30:
        await asyncio.sleep(2)
        
        current_count = len(interceptor.ws_frames)
        if current_count > last_frame_count:
            print(f"\n📨 {current_count - last_frame_count} new frame(s) captured!")
            
            # Display new frames
            for frame in interceptor.ws_frames[last_frame_count:]:
                print(f"\n   [{frame['direction']}] {frame['url'][:80]}")
                payload = frame['payload']
                if isinstance(payload, str):
                    print(f"   Payload: {payload[:500]}")
                    
                    # Try to parse as JSON
                    try:
                        data = json.loads(payload)
                        print(f"   JSON keys: {list(data.keys())}")
                    except:
                        pass
                else:
                    print(f"   Payload type: {type(payload)}, length: {len(payload) if hasattr(payload, '__len__') else 'unknown'}")
            
            last_frame_count = current_count
    
    # Final summary
    print("\n" + "="*60)
    print("📊 FINAL SUMMARY")
    print("="*60)
    print(f"Total WebSocket frames: {len(interceptor.ws_frames)}")
    print(f"Total HTTP requests: {len(interceptor.requests)}")
    print(f"Total HTTP responses: {len(interceptor.responses)}")
    
    if interceptor.ws_frames:
        print("\n📝 All WebSocket frames:")
        for i, frame in enumerate(interceptor.ws_frames[:20]):  # Show first 20
            print(f"\n   Frame {i+1}: [{frame['direction']}]")
            payload = frame['payload']
            if isinstance(payload, str) and len(payload) < 200:
                print(f"   {payload}")
            elif isinstance(payload, str):
                print(f"   {payload[:200]}... (truncated)")
    
    # Save to file
    output_file = '/Users/troy/.openclaw/workspace/godel_api/output/websocket_diagnostic.json'
    with open(output_file, 'w') as f:
        json.dump({
            'websocket_frames': interceptor.ws_frames,
            'requests': [{'url': r['url'], 'method': r['method']} for r in interceptor.requests[:50]],
            'responses': [{'url': r['url'], 'status': r['status']} for r in interceptor.responses[:50]],
        }, f, indent=2, default=str)
    
    print(f"\n💾 Full data saved to: {output_file}")
    
    await manager.shutdown()
    print("\n✅ Diagnostic complete")

if __name__ == "__main__":
    asyncio.run(main())
