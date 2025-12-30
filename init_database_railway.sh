#!/bin/bash
# Script to initialize database using Railway MySQL credentials
# Usage: export Railway MySQL env vars, then run: bash init_database_railway.sh

echo "============================================================"
echo "Initializing Database with Railway MySQL"
echo "============================================================"
echo ""

# Check if Railway env vars are set
if [ -z "$MYSQL_HOST" ]; then
    echo "❌ Error: MYSQL_HOST environment variable not set"
    echo ""
    echo "Please set Railway MySQL environment variables:"
    echo "  export MYSQL_HOST=your-railway-host"
    echo "  export MYSQL_PORT=3306"
    echo "  export MYSQL_USER=your-username"
    echo "  export MYSQL_PASSWORD=your-password"
    echo "  export MYSQL_DATABASE=your-database-name"
    echo ""
    echo "Then run this script again"
    exit 1
fi

echo "Using Railway MySQL:"
echo "  Host: $MYSQL_HOST"
echo "  Port: ${MYSQL_PORT:-3306}"
echo "  User: $MYSQL_USER"
echo "  Database: $MYSQL_DATABASE"
echo ""

# Run the init script with Railway env vars
python3 init_database.py

