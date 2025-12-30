-- Fix MySQL authentication for root user
-- Run this with: sudo mysql < fix_mysql_auth.sql
-- Or: sudo mysql, then paste these commands

-- Option 1: Set password for root user (recommended)
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '';
FLUSH PRIVILEGES;

-- Option 2: Create a dedicated user for the trading app (alternative)
-- CREATE USER 'trading_user'@'localhost' IDENTIFIED BY '';
-- GRANT ALL PRIVILEGES ON trading_db.* TO 'trading_user'@'localhost';
-- GRANT ALL PRIVILEGES ON railway.* TO 'trading_user'@'localhost';
-- FLUSH PRIVILEGES;

