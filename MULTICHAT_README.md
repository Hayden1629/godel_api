# Multi-Instance Chat Monitoring Update

## What Was Added

### 1. `multi_chat.py` - Multi-Channel Chat Monitor
- Runs multiple Godel Terminal sessions simultaneously
- Each session monitors a different chat channel
- Uses separate BrowserContexts for true isolation
- Supports `#general`, `#biotech`, `#paid` channels

### 2. `commands/chat_monitor_v2.py` - Improved Chat Monitor
- Better WebSocket frame parsing with multiple strategies
- Socket.IO format support
- Message deduplication
- Improved message extraction heuristics
- Handles nested message formats

### 3. CLI `multichat` Command
```bash
python cli.py multichat --channels general,biotech,paid --duration 120
```

### 4. Test Script
```bash
python test_chat.py  # Discovers chat UI elements
```

## Known Issues

1. **Chat Window Opening**: The chat command/UI discovery is not yet complete. The terminal likely requires:
   - A specific command like `CHAT #channel` or `/join #channel`
   - Or clicking a chat UI element
   - Current implementation tries multiple approaches but may need refinement

2. **WebSocket Message Format**: The exact chat message format from Godel Terminal's WebSocket is not yet captured. The probe command should be run while chat is active to capture real payloads.

## Next Steps to Get It Working

1. **Discover Chat Command**: Run `test_chat.py` to find how to open chat windows
2. **Capture WebSocket Payloads**: Run probe while chat is manually opened to see message format
3. **Refine Parsing**: Update `chat_monitor_v2.py` with actual message structure
4. **Test Multi-Instance**: Run `multichat` command with working chat

## Testing

```bash
# Test single channel
python cli.py -bg chat --channels general --duration 30

# Test multi-channel (once chat opening works)
python cli.py -bg multichat --channels general,biotech,paid --duration 60

# Check captured messages
sqlite3 godel.db "SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT 10;"
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MultiChannelChatMonitor                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │  Session 1  │  │  Session 2  │  │  Session 3  │          │
│  │  #general   │  │  #biotech   │  │   #paid     │          │
│  ├─────────────┤  ├─────────────┤  ├─────────────┤          │
│  │ ChatMonitor │  │ ChatMonitor │  │ ChatMonitor │          │
│  │     V2      │  │     V2      │  │     V2      │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         └─────────────────┴─────────────────┘                │
│                           │                                  │
│                    ┌──────┴──────┐                          │
│                    │  SQLite DB  │                          │
│                    │  godel.db   │                          │
│                    └─────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

## Files Modified

- `cli.py` - Added `multichat` command and `cmd_multichat` handler
- `commands/__init__.py` - Exported `ChatMonitorV2`
- `config.py` - Created with credentials

## Files Created

- `multi_chat.py` - Multi-instance chat monitoring
- `commands/chat_monitor_v2.py` - Improved chat monitor
- `test_chat.py` - Chat discovery test script
- `MULTICHAT_README.md` - This file
