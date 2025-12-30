"""
Database initialization script for Railway MySQL.
Run this to create the database schema on Railway MySQL.
Requires Railway environment variables to be set.
"""
import mysql.connector
from mysql.connector import Error
from pathlib import Path
from config import DB_CONFIG

def init_database():
    """Initialize the Railway MySQL database with schema."""
    try:
        # Connect directly to Railway database
        print(f"Connecting to Railway MySQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}...")
        print(f"Database: {DB_CONFIG['database']}")
        
        # Add connection timeout
        config_with_timeout = DB_CONFIG.copy()
        config_with_timeout['connection_timeout'] = 5
        
        try:
            connection = mysql.connector.connect(**config_with_timeout)
        except Error as e:
            if e.errno == 2003:  # Can't connect to MySQL server
                print(f"\n❌ Cannot connect to Railway MySQL at {DB_CONFIG['host']}:{DB_CONFIG['port']}")
                print("\nPlease ensure Railway environment variables are set:")
                print("  - MYSQLHOST or MYSQL_HOST")
                print("  - MYSQLPORT or MYSQL_PORT")
                print("  - MYSQLUSER or MYSQL_USER")
                print("  - MYSQLPASSWORD or MYSQL_PASSWORD")
                print("  - MYSQLDATABASE or MYSQL_DATABASE")
                print("\nYou can set them by running:")
                print("  source setup_railway_env.sh")
                return False
            else:
                raise
        
        cursor = connection.cursor()
        
        # Railway database already exists, just use it
        print(f"Using Railway database '{DB_CONFIG['database']}'...")
        
        # Read and execute schema file
        schema_file = Path(__file__).parent / "database_schema.sql"
        if not schema_file.exists():
            print(f"Error: Schema file not found at {schema_file}")
            return False
        
        print(f"Reading schema from {schema_file}...")
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Filter out CREATE DATABASE and USE statements (handled above)
        # Split by semicolons and execute each statement
        statements = []
        for s in schema_sql.split(';'):
            s = s.strip()
            if s and not s.startswith('--') and not s.upper().startswith('CREATE DATABASE') and not s.upper().startswith('USE '):
                statements.append(s + ';')
        
        print("Creating tables...")
        for statement in statements:
            if statement.strip() and statement.strip() != ';':
                try:
                    cursor.execute(statement)
                    print(f"  ✓ Executed: {statement[:50]}...")
                except Error as e:
                    if "already exists" not in str(e).lower():
                        print(f"  ⚠ Warning: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"\n✅ Railway database '{DB_CONFIG['database']}' initialized successfully!")
        print("\nYou can now run the algo loop and it will store trades in the database.")
        return True
        
    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
        return False
    except Error as e:
        print(f"❌ Error initializing database: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Railway MySQL Database Initialization")
    print("=" * 60)
    print()
    
    success = init_database()
    
    if success:
        print("\nNext steps:")
        print("1. Make sure Railway environment variables are set (use: source setup_railway_env.sh)")
        print("2. Run your algo loop - it will automatically use the Railway database")
    else:
        print("\nPlease ensure Railway MySQL environment variables are set")
        print("Run: source setup_railway_env.sh")

