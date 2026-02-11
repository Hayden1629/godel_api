# Godel Terminal - Standalone Chat Monitor

Continuous chat monitoring for Godel Terminal that runs on any computer.

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Configure Credentials

Create `config.py` in the project root:

```python
GODEL_URL = "https://app.godelterminal.com"
GODEL_USERNAME = "your_email@example.com"
GODEL_PASSWORD = "your_password"
```

### 3. Run the Monitor

```bash
# Monitor all default channels (general, biotech, paid)
python standalone_monitor.py

# Monitor specific channel
python standalone_monitor.py -c general

# Monitor multiple channels
python standalone_monitor.py -c general,biotech

# Custom database location
python standalone_monitor.py -d /path/to/chat.db
```

## Features

- **Continuous Monitoring**: Runs 24/7, capturing all messages
- **Multi-Channel**: Monitor multiple channels simultaneously
- **Persistent Storage**: SQLite database with full message history
- **Real-Time Output**: See messages as they appear
- **Graceful Shutdown**: Ctrl+C to stop cleanly

## Database Schema

Messages stored in `chat_messages` table:
- `id` - Auto-increment ID
- `channel` - Channel name (general, biotech, paid)
- `sender` - Message sender
- `content` - Message text
- `timestamp` - When sent
- `is_reply` - Whether it's a reply
- `reply_to` - Who being replied to
- `message_id` - Platform message ID
- `username` - Sender username

## Query Examples

```bash
# View recent messages
sqlite3 godel_chat.db "SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT 20;"

# Count messages by channel
sqlite3 godel_chat.db "SELECT channel, COUNT(*) FROM chat_messages GROUP BY channel;"

# Search messages
sqlite3 godel_chat.db "SELECT * FROM chat_messages WHERE content LIKE '%AAPL%';"

# Export to CSV
sqlite3 godel_chat.db ".mode csv" ".output messages.csv" "SELECT * FROM chat_messages;"
```

## Architecture

```
standalone_monitor.py
├── GodelManager (browser management)
├── DOMChatMonitor (per-channel monitoring)
└── SQLite (persistent storage)

Each channel gets:
- Separate browser context
- Independent polling loop
- Dedicated database writes
```

## Troubleshooting

**Browser doesn't open**
- Run `playwright install` to ensure browsers are installed
- Try without `--headless` for debugging

**Login fails**
- Check credentials in config.py
- Ensure account is active on Godel Terminal

**Missing messages**
- Check channel names match exactly (case-sensitive)
- Ensure Public Channels are expanded in UI
- Check database is writable

## Files

- `standalone_monitor.py` - Main runner script
- `godel_core.py` - Browser automation
- `dom_chat_monitor.py` - Message extraction
- `db.py` - Database operations
- `config.py` - Your credentials (create this)

## License

Private - For authorized Godel Terminal users only.
