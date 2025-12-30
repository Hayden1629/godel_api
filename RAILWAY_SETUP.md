# Railway MySQL Setup Guide

## Quick Setup

1. **Get your Railway Private Domain:**
   - Go to Railway dashboard
   - Click on your MySQL service
   - Go to "Connect" tab
   - Under "Private Networking", copy the domain (looks like: `xxxxx.railway.internal` or `xxxxx.railway.app`)

2. **Set environment variables:**
   
   Option A: Temporary (current shell session):
   ```bash
   export MYSQLHOST="your-actual-domain.railway.app"  # Replace with actual domain
   export MYSQLPORT="3306"
   export MYSQLUSER="root"
   export MYSQLPASSWORD="eFpkmKiauoilGietfPxhphBgBngicXwT"
   export MYSQLDATABASE="railway"
   ```
   
   Option B: Permanent (add to ~/.bashrc or ~/.zshrc):
   ```bash
   echo 'export MYSQLHOST="your-actual-domain.railway.app"' >> ~/.bashrc
   echo 'export MYSQLPORT="3306"' >> ~/.bashrc
   echo 'export MYSQLUSER="root"' >> ~/.bashrc
   echo 'export MYSQLPASSWORD="eFpkmKiauoilGietfPxhphBgBngicXwT"' >> ~/.bashrc
   echo 'export MYSQLDATABASE="railway"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. **Initialize the database:**
   ```bash
   python init_database.py
   ```

4. **Run your algo:**
   The algo will automatically detect Railway MySQL via environment variables and use it!

## How It Works

- When you set `MYSQLHOST` (or `MYSQL_HOST`), the config automatically switches to Railway MySQL
- The database name is set to "railway" (Railway's default)
- All trades will be stored in Railway MySQL
- Your dashboard on Railway will read from the same database

## Troubleshooting

- **Connection timeout:** Make sure you're using the Private Networking domain, not the public URL
- **Can't find domain:** Check Railway dashboard -> MySQL service -> Connect -> Private Networking
- **Wrong database:** Make sure `MYSQLDATABASE=railway` (Railway's default database name)

