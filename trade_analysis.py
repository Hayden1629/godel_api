"""
Trade Analysis Script
Matches trades between journal and brokerage CSV, finds inconsistencies, and suggests stop loss strategies.
"""
import json
import csv
import pandas as pd
from datetime import datetime
from collections import defaultdict
import re

def parse_price(price_str):
    """Parse price string like '$1.645' to float"""
    if not price_str or price_str == '':
        return None
    return float(price_str.replace('$', '').replace(',', ''))

def parse_quantity(qty_str):
    """Parse quantity string like '1,449' to int"""
    if not qty_str or qty_str == '':
        return None
    return int(qty_str.replace(',', ''))

def parse_fees(fees_str):
    """Parse fees string like '$0.24' to float"""
    if not fees_str or fees_str == '':
        return 0.0
    return float(fees_str.replace('$', '').replace(',', ''))

def load_journal(filepath):
    """Load trade journal JSON"""
    with open(filepath, 'r') as f:
        return json.load(f)

def load_brokerage_csv(filepath):
    """Load brokerage CSV and parse transactions"""
    transactions = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Action'] in ['Buy', 'Sell', 'Sell Short']:
                transactions.append({
                    'date': row['Date'],
                    'action': row['Action'],
                    'symbol': row['Symbol'],
                    'quantity': parse_quantity(row['Quantity']),
                    'price': parse_price(row['Price']),
                    'fees': parse_fees(row['Fees & Comm']),
                    'amount': parse_price(row['Amount'])
                })
    return transactions

def match_trades(journal_trades, brokerage_transactions):
    """Match journal trades with brokerage transactions"""
    matched = []
    unmatched_journal = []
    used_transactions = set()
    
    # Group brokerage transactions by symbol and action
    brokerage_by_symbol = defaultdict(list)
    for i, trans in enumerate(brokerage_transactions):
        key = (trans['symbol'], trans['action'])
        brokerage_by_symbol[key].append((i, trans))
    
    for journal_trade in journal_trades:
        ticker = journal_trade['ticker']
        
        # Determine brokerage action based on journal action
        if journal_trade['action'] == 'LONG':
            entry_action = 'Buy'
            exit_action = 'Sell'
        elif journal_trade['action'] == 'SHORT':
            entry_action = 'Sell Short'
            exit_action = 'Buy'  # Buy to cover
        
        # Find matching entry transaction
        entry_key = (ticker, entry_action)
        exit_key = (ticker, exit_action)
        
        entry_match = None
        exit_match = None
        entry_idx = None
        exit_idx = None
        
        # Try to find entry transaction
        if entry_key in brokerage_by_symbol:
            for idx, trans in brokerage_by_symbol[entry_key]:
                if idx in used_transactions:
                    continue
                if (abs(trans['quantity'] - journal_trade['quantity']) <= 5 and  # Allow small quantity differences
                    abs(trans['price'] - journal_trade['entry_price']) < 0.1):  # Allow small price differences
                    entry_match = trans
                    entry_idx = idx
                    break
        
        # Try to find exit transaction
        if exit_key in brokerage_by_symbol and journal_trade.get('exit_price') is not None:
            for idx, trans in brokerage_by_symbol[exit_key]:
                if idx in used_transactions:
                    continue
                if (abs(trans['quantity'] - journal_trade['quantity']) <= 5 and
                    abs(trans['price'] - journal_trade['exit_price']) < 0.1):
                    exit_match = trans
                    exit_idx = idx
                    break
        
        if entry_match and exit_match:
            matched.append({
                'journal': journal_trade,
                'brokerage_entry': entry_match,
                'brokerage_exit': exit_match
            })
            used_transactions.add(entry_idx)
            used_transactions.add(exit_idx)
        else:
            unmatched_journal.append(journal_trade)
    
    # Find unmatched brokerage transactions
    unmatched_brokerage = [trans for i, trans in enumerate(brokerage_transactions) if i not in used_transactions]
    
    return matched, unmatched_journal, unmatched_brokerage

def analyze_inconsistencies(matched_trades):
    """Find inconsistencies between journal and brokerage"""
    inconsistencies = []
    
    for match in matched_trades:
        journal = match['journal']
        entry = match['brokerage_entry']
        exit = match['brokerage_exit']
        
        issues = []
        
        # Check entry price
        entry_price_diff = abs(entry['price'] - journal['entry_price'])
        if entry_price_diff > 0.01:
            issues.append(f"Entry price mismatch: Journal={journal['entry_price']}, Brokerage={entry['price']}, Diff=${entry_price_diff:.4f}")
        
        # Check exit price
        if journal.get('exit_price') is not None:
            exit_price_diff = abs(exit['price'] - journal['exit_price'])
            if exit_price_diff > 0.01:
                issues.append(f"Exit price mismatch: Journal={journal['exit_price']}, Brokerage={exit['price']}, Diff=${exit_price_diff:.4f}")
        
        # Check quantity
        qty_diff = abs(entry['quantity'] - journal['quantity'])
        if qty_diff > 0:
            issues.append(f"Quantity mismatch: Journal={journal['quantity']}, Brokerage={entry['quantity']}, Diff={qty_diff}")
        
        # Calculate actual P&L from brokerage (including fees)
        brokerage_pnl = exit['amount'] - abs(entry['amount']) - entry['fees'] - exit['fees']
        journal_pnl = journal['profit_loss']
        pnl_diff = abs(brokerage_pnl - journal_pnl)
        
        if pnl_diff > 1.0:  # More than $1 difference
            issues.append(f"P&L mismatch: Journal=${journal_pnl:.2f}, Brokerage=${brokerage_pnl:.2f}, Diff=${pnl_diff:.2f}")
        
        if issues:
            inconsistencies.append({
                'ticker': journal['ticker'],
                'action': journal['action'],
                'issues': issues,
                'journal_pnl': journal_pnl,
                'brokerage_pnl': brokerage_pnl,
                'fees': entry['fees'] + exit['fees']
            })
    
    return inconsistencies

def analyze_trades(journal_trades):
    """Analyze trades for stop loss strategy suggestions"""
    df = pd.DataFrame(journal_trades)
    
    # Filter out trades with null P&L
    df = df[df['profit_loss'].notna()]
    
    analysis = {
        'total_trades': len(df),
        'winners': len(df[df['profit_loss'] > 0]),
        'losers': len(df[df['profit_loss'] < 0]),
        'breakeven': len(df[df['profit_loss'] == 0]),
        'total_pnl': df['profit_loss'].sum(),
        'avg_win': df[df['profit_loss'] > 0]['profit_loss'].mean() if len(df[df['profit_loss'] > 0]) > 0 else 0,
        'avg_loss': df[df['profit_loss'] < 0]['profit_loss'].mean() if len(df[df['profit_loss'] < 0]) > 0 else 0,
        'max_win': df['profit_loss'].max(),
        'max_loss': df['profit_loss'].min(),
        'win_rate': len(df[df['profit_loss'] > 0]) / len(df) * 100 if len(df) > 0 else 0,
    }
    
    # Analyze losing trades
    losers = df[df['profit_loss'] < 0].copy()
    if len(losers) > 0:
        losers['loss_pct'] = losers['profit_loss_percent']
        analysis['avg_loss_pct'] = losers['loss_pct'].mean()
        analysis['max_loss_pct'] = losers['loss_pct'].min()
        
        # Count trades that could have been saved with different stop losses
        analysis['trades_saved_1pct'] = len(losers[losers['loss_pct'] < -1.0])
        analysis['trades_saved_2pct'] = len(losers[losers['loss_pct'] < -2.0])
        analysis['trades_saved_3pct'] = len(losers[losers['loss_pct'] < -3.0])
    
    # Analyze winning trades
    winners = df[df['profit_loss'] > 0].copy()
    if len(winners) > 0:
        winners['win_pct'] = winners['profit_loss_percent']
        analysis['avg_win_pct'] = winners['win_pct'].mean()
        analysis['max_win_pct'] = winners['win_pct'].max()
        
        # Count trades that turned from winners to losers
        analysis['winners_turned_losers'] = len(winners[winners['profit_loss'] < 5])  # Small winners
    
    # Analyze by action type
    longs = df[df['action'] == 'LONG']
    shorts = df[df['action'] == 'SHORT']
    
    if len(longs) > 0:
        analysis['long_win_rate'] = len(longs[longs['profit_loss'] > 0]) / len(longs) * 100
        analysis['long_avg_pnl'] = longs['profit_loss'].mean()
    
    if len(shorts) > 0:
        analysis['short_win_rate'] = len(shorts[shorts['profit_loss'] > 0]) / len(shorts) * 100
        analysis['short_avg_pnl'] = shorts['profit_loss'].mean()
    
    return analysis, df

def suggest_stop_loss_strategies(analysis, df):
    """Suggest stop loss strategies based on analysis"""
    suggestions = []
    
    losers = df[df['profit_loss'] < 0].copy()
    if len(losers) == 0:
        return ["No losing trades to analyze"]
    
    losers['loss_pct'] = losers['profit_loss_percent']
    
    # Strategy 1: Fixed percentage stop loss
    loss_distribution = {
        '1%': len(losers[losers['loss_pct'] <= -1.0]),
        '2%': len(losers[losers['loss_pct'] <= -2.0]),
        '3%': len(losers[losers['loss_pct'] <= -3.0]),
        '5%': len(losers[losers['loss_pct'] <= -5.0]),
    }
    
    suggestions.append("=== STRATEGY 1: Fixed Percentage Stop Loss ===")
    suggestions.append(f"Current max loss: {analysis['max_loss_pct']:.2f}%")
    suggestions.append(f"Average loss: {analysis['avg_loss_pct']:.2f}%")
    suggestions.append(f"\nLoss distribution:")
    for pct, count in loss_distribution.items():
        suggestions.append(f"  - {pct} stop loss would have saved {count} trades")
    
    # Calculate potential savings
    if analysis['trades_saved_2pct'] > 0:
        saved_trades_2pct = losers[losers['loss_pct'] < -2.0]
        potential_savings_2pct = saved_trades_2pct['profit_loss'].sum() - (saved_trades_2pct['profit_loss'] * -0.02 / saved_trades_2pct['profit_loss_percent']).sum()
        suggestions.append(f"\n2% stop loss would have saved ${abs(potential_savings_2pct):.2f} on {len(saved_trades_2pct)} trades")
    
    # Strategy 2: Trailing stop loss
    suggestions.append("\n=== STRATEGY 2: Trailing Stop Loss ===")
    winners = df[df['profit_loss'] > 0].copy()
    if len(winners) > 0:
        winners['win_pct'] = winners['profit_loss_percent']
        # Find winners that gave back significant gains
        gave_back = winners[winners['win_pct'] < winners['win_pct'].quantile(0.5)]
        suggestions.append(f"{len(gave_back)} winning trades gave back significant gains")
        suggestions.append(f"Average win that gave back: {gave_back['win_pct'].mean():.2f}%")
        suggestions.append("Consider trailing stop loss at 50% of peak gain to lock in profits")
    
    # Strategy 3: Time-based stop loss
    suggestions.append("\n=== STRATEGY 3: Time-Based Stop Loss ===")
    # All trades are held for 10 minutes, so this is less relevant
    suggestions.append("All trades are held for fixed 10 minutes")
    suggestions.append("Consider closing early if loss exceeds threshold before time limit")
    
    # Strategy 4: Volatility-based stop loss
    suggestions.append("\n=== STRATEGY 4: Volatility-Based Stop Loss ===")
    suggestions.append("For high volatility stocks, use wider stops (2-3%)")
    suggestions.append("For low volatility stocks, use tighter stops (1-1.5%)")
    
    # Strategy 5: Action-specific stop loss
    suggestions.append("\n=== STRATEGY 5: Action-Specific Stop Loss ===")
    long_losers = losers[losers['action'] == 'LONG']
    short_losers = losers[losers['action'] == 'SHORT']
    
    if len(long_losers) > 0:
        suggestions.append(f"LONG trades: Average loss {long_losers['loss_pct'].mean():.2f}%, Max loss {long_losers['loss_pct'].min():.2f}%")
        suggestions.append(f"  Suggested stop: 1.5-2% for LONG positions")
    
    if len(short_losers) > 0:
        suggestions.append(f"SHORT trades: Average loss {short_losers['loss_pct'].mean():.2f}%, Max loss {short_losers['loss_pct'].min():.2f}%")
        suggestions.append(f"  Suggested stop: 1.5-2% for SHORT positions")
    
    # Strategy 6: Risk/Reward ratio
    suggestions.append("\n=== STRATEGY 6: Risk/Reward Ratio ===")
    if analysis['avg_win'] > 0 and abs(analysis['avg_loss']) > 0:
        risk_reward = analysis['avg_win'] / abs(analysis['avg_loss'])
        suggestions.append(f"Current risk/reward ratio: {risk_reward:.2f}:1")
        if risk_reward < 1.5:
            suggestions.append("WARNING: Risk/Reward ratio is below 1.5:1 - consider tighter stops or better entry timing")
        else:
            suggestions.append("OK: Risk/Reward ratio is acceptable")
    
    return suggestions

def main():
    journal_file = "trade_journal.json"
    brokerage_file = r"C:\Users\Richard\Downloads\Individual_XXX240_Transactions_20251226-023552.csv"
    
    print("Loading trade journal...")
    journal_trades = load_journal(journal_file)
    print(f"Loaded {len(journal_trades)} trades from journal")
    
    print("\nLoading brokerage transactions...")
    brokerage_transactions = load_brokerage_csv(brokerage_file)
    print(f"Loaded {len(brokerage_transactions)} transactions from brokerage CSV")
    
    print("\nMatching trades...")
    matched, unmatched_journal, unmatched_brokerage = match_trades(journal_trades, brokerage_transactions)
    print(f"Matched {len(matched)} trades")
    print(f"Unmatched journal trades: {len(unmatched_journal)}")
    print(f"Unmatched brokerage transactions: {len(unmatched_brokerage)}")
    
    print("\n" + "="*80)
    print("INCONSISTENCIES ANALYSIS")
    print("="*80)
    inconsistencies = analyze_inconsistencies(matched)
    if inconsistencies:
        print(f"\nFound {len(inconsistencies)} trades with inconsistencies:\n")
        for inc in inconsistencies:
            print(f"Ticker: {inc['ticker']} ({inc['action']})")
            print(f"  Journal P&L: ${inc['journal_pnl']:.2f}")
            print(f"  Brokerage P&L: ${inc['brokerage_pnl']:.2f}")
            print(f"  Fees: ${inc['fees']:.2f}")
            for issue in inc['issues']:
                print(f"  WARNING: {issue}")
            print()
    else:
        print("No significant inconsistencies found!")
    
    print("\n" + "="*80)
    print("TRADE PERFORMANCE ANALYSIS")
    print("="*80)
    analysis, df = analyze_trades(journal_trades)
    print(f"\nTotal Trades: {analysis['total_trades']}")
    print(f"Winners: {analysis['winners']} ({analysis['win_rate']:.2f}%)")
    print(f"Losers: {analysis['losers']}")
    print(f"Breakeven: {analysis['breakeven']}")
    print(f"\nTotal P&L: ${analysis['total_pnl']:.2f}")
    print(f"Average Win: ${analysis['avg_win']:.2f}")
    print(f"Average Loss: ${analysis['avg_loss']:.2f}")
    print(f"Max Win: ${analysis['max_win']:.2f}")
    print(f"Max Loss: ${analysis['max_loss']:.2f}")
    
    if 'avg_loss_pct' in analysis:
        print(f"\nAverage Loss %: {analysis['avg_loss_pct']:.2f}%")
        print(f"Max Loss %: {analysis['max_loss_pct']:.2f}%")
    
    if 'long_win_rate' in analysis:
        print(f"\nLONG Trades:")
        print(f"  Win Rate: {analysis['long_win_rate']:.2f}%")
        print(f"  Average P&L: ${analysis['long_avg_pnl']:.2f}")
    
    if 'short_win_rate' in analysis:
        print(f"\nSHORT Trades:")
        print(f"  Win Rate: {analysis['short_win_rate']:.2f}%")
        print(f"  Average P&L: ${analysis['short_avg_pnl']:.2f}")
    
    print("\n" + "="*80)
    print("STOP LOSS STRATEGY SUGGESTIONS")
    print("="*80)
    suggestions = suggest_stop_loss_strategies(analysis, df)
    for suggestion in suggestions:
        print(suggestion)
    
    # Save detailed report
    report_file = "trade_analysis_report.txt"
    with open(report_file, 'w') as f:
        f.write("TRADE ANALYSIS REPORT\n")
        f.write("="*80 + "\n\n")
        f.write("INCONSISTENCIES:\n")
        f.write("-"*80 + "\n")
        if inconsistencies:
            for inc in inconsistencies:
                f.write(f"\nTicker: {inc['ticker']} ({inc['action']})\n")
                for issue in inc['issues']:
                    f.write(f"  {issue}\n")
        else:
            f.write("No inconsistencies found.\n")
        
        f.write("\n\nPERFORMANCE ANALYSIS:\n")
        f.write("-"*80 + "\n")
        f.write(f"Total Trades: {analysis['total_trades']}\n")
        f.write(f"Win Rate: {analysis['win_rate']:.2f}%\n")
        f.write(f"Total P&L: ${analysis['total_pnl']:.2f}\n")
        
        f.write("\n\nSTOP LOSS SUGGESTIONS:\n")
        f.write("-"*80 + "\n")
        for suggestion in suggestions:
            f.write(suggestion + "\n")
    
    print(f"\n\nDetailed report saved to {report_file}")

if __name__ == "__main__":
    main()

