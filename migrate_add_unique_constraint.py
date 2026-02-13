#!/usr/bin/env python3
"""
Migration script to add UNIQUE constraint on (channel, message_id) 
to existing databases.

SQLite doesn't support adding UNIQUE constraints to existing columns,
so we need to recreate the table.
"""

import sqlite3
import sys
from pathlib import Path

def migrate(db_path: str):
    """Add UNIQUE constraint to chat_messages table."""
    
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='chat_messages'")
    result = cursor.fetchone()
    
    if result and 'UNIQUE' in result[0]:
        print("UNIQUE constraint already exists. No migration needed.")
        conn.close()
        return True
    
    print("Migrating database to add UNIQUE constraint...")
    
    # Step 1: Create new table with proper schema
    cursor.execute("""
        CREATE TABLE chat_messages_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            sender TEXT,
            content TEXT,
            timestamp DATETIME,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_reply INTEGER DEFAULT 0,
            reply_to TEXT,
            message_id TEXT,
            username TEXT,
            UNIQUE(channel, message_id)
        )
    """)
    
    # Step 2: Copy data from old table
    cursor.execute("""
        INSERT INTO chat_messages_new 
        (id, channel, sender, content, timestamp, raw_data, created_at, 
         is_reply, reply_to, message_id, username)
        SELECT id, channel, sender, content, timestamp, raw_data, created_at,
               is_reply, reply_to, message_id, username
        FROM chat_messages
    """)
    
    # Step 3: Drop old table
    cursor.execute("DROP TABLE chat_messages")
    
    # Step 4: Rename new table
    cursor.execute("ALTER TABLE chat_messages_new RENAME TO chat_messages")
    
    # Step 5: Recreate indexes
    cursor.execute("CREATE INDEX idx_chat_channel ON chat_messages(channel)")
    cursor.execute("CREATE INDEX idx_chat_ts ON chat_messages(timestamp)")
    
    conn.commit()
    conn.close()
    
    print("Migration complete!")
    return True

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "godel.db"
    migrate(db_path)
