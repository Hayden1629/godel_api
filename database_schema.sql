-- Trading Database Schema
-- This schema is designed for Railway MySQL database
-- Note: Railway provides the database, so we don't create it here
-- Make sure you're connected to the Railway database before running this schema

-- Main trades table
CREATE TABLE IF NOT EXISTS trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- 'LONG' or 'SHORT'
    quantity INT NOT NULL,
    entry_price DECIMAL(10, 4) NOT NULL,
    exit_price DECIMAL(10, 4) NULL,
    profit_loss DECIMAL(12, 6) NULL,
    profit_loss_percent DECIMAL(10, 6) NULL,
    time_placed DATETIME NOT NULL,
    close_time DATETIME NULL,
    hold_time_minutes DECIMAL(10, 4) NULL,
    order_id VARCHAR(50) NOT NULL,
    close_order_id VARCHAR(50) NULL,
    stop_loss_order_id VARCHAR(50) NULL,
    stop_loss_price DECIMAL(10, 4) NULL,
    take_profit_price DECIMAL(10, 4) NULL,
    is_winner BOOLEAN NULL,
    entry_order_type VARCHAR(20) NULL,
    exit_order_type VARCHAR(20) NULL,
    entry_spread DECIMAL(10, 4) NULL,
    exit_spread DECIMAL(10, 4) NULL,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ticker (ticker),
    INDEX idx_time_placed (time_placed),
    INDEX idx_is_closed (is_closed),
    INDEX idx_order_id (order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Trade parameters table (one-to-one with trades)
CREATE TABLE IF NOT EXISTS trade_parameters (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_id INT NOT NULL,
    stop_loss_percent DECIMAL(5, 2) NULL,
    take_profit_percent DECIMAL(5, 2) NULL,
    trade_hold_minutes INT NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    UNIQUE KEY unique_trade_id (trade_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- PRT data table (one-to-one with trades)
CREATE TABLE IF NOT EXISTS prt_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_id INT NOT NULL,
    edge DECIMAL(15, 12) NULL,
    prob_up DECIMAL(5, 3) NULL,
    mean DECIMAL(15, 12) NULL,
    p10 DECIMAL(15, 12) NULL,
    p90 DECIMAL(15, 12) NULL,
    dist1 DECIMAL(20, 15) NULL,
    n INT NULL,
    timestamp VARCHAR(50) NULL,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    UNIQUE KEY unique_trade_id (trade_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Dashboard statistics snapshot table (for historical tracking)
CREATE TABLE IF NOT EXISTS dashboard_snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    win_rate DECIMAL(5, 2) NULL,
    total_profit_loss DECIMAL(12, 6) DEFAULT 0,
    total_profit_loss_percent DECIMAL(10, 6) DEFAULT 0,
    avg_profit_per_trade DECIMAL(12, 6) NULL,
    avg_loss_per_trade DECIMAL(12, 6) NULL,
    account_value DECIMAL(15, 2) NULL,
    buying_power DECIMAL(15, 2) NULL,
    cash_balance DECIMAL(15, 2) NULL,
    day_trading_buying_power DECIMAL(15, 2) NULL,
    snapshot_data JSON NULL,  -- Full snapshot data as JSON for flexibility
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Active trades tracking (for real-time monitoring)
CREATE TABLE IF NOT EXISTS active_trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    trade_id INT NOT NULL,
    ticker VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,
    quantity INT NOT NULL,
    entry_price DECIMAL(10, 4) NOT NULL,
    time_placed DATETIME NOT NULL,
    age_minutes DECIMAL(10, 4) NULL,
    stop_loss_price DECIMAL(10, 4) NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (trade_id) REFERENCES trades(id) ON DELETE CASCADE,
    UNIQUE KEY unique_trade_id (trade_id),
    INDEX idx_ticker (ticker),
    INDEX idx_time_placed (time_placed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Portfolio value history (for portfolio value over time chart)
CREATE TABLE IF NOT EXISTS portfolio_value_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    portfolio_value DECIMAL(15, 2) NOT NULL,
    account_value DECIMAL(15, 2) NULL,
    cumulative_pnl DECIMAL(12, 6) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

