#!/bin/bash
# Initialize Railway MySQL database with tables
# This script sets Railway env vars and runs the database initialization

echo "============================================================"
echo "Initializing Railway MySQL Database"
echo "============================================================"
echo ""

# Check if Railway env vars are already set
if [ -z "$MYSQLHOST" ]; then
    echo "⚠️  Railway environment variables not set!"
    echo ""
    echo "Please set them first:"
    echo "  export MYSQLHOST=\"your-railway-private-domain.railway.app\""
    echo "  export MYSQLPORT=\"3306\""
    echo "  export MYSQLUSER=\"root\""
    echo "  export MYSQLPASSWORD=\"eFpkmKiauoilGietfPxhphBgBngicXwT\""
    echo "  export MYSQLDATABASE=\"railway\""
    echo ""
    echo "Or source setup_railway_env.sh first:"
    echo "  source setup_railway_env.sh"
    echo "  bash init_railway_db.sh"
    echo ""
    exit 1
fi

echo "Using Railway MySQL:"
echo "  Host: $MYSQLHOST"
echo "  Port: ${MYSQLPORT:-3306}"
echo "  User: $MYSQLUSER"
echo "  Database: ${MYSQLDATABASE:-railway}"
echo ""

# Run the initialization script
cd "$(dirname "$0")"
python3 init_database.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Database tables created successfully!"
    echo "Your algo will now be able to store trades in Railway MySQL."
else
    echo ""
    echo "❌ Failed to initialize database. Check the error messages above."
    exit 1
fi

