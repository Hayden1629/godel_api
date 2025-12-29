"""
Trade Journal Analysis & Visualization
=======================================
Generates comprehensive plots to analyze trading performance and optimize algorithm parameters.

Usage: python trade_analysis.py
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set style for all plots
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['figure.facecolor'] = '#1a1a2e'
plt.rcParams['axes.facecolor'] = '#16213e'
plt.rcParams['axes.edgecolor'] = '#e94560'
plt.rcParams['grid.color'] = '#0f3460'
plt.rcParams['text.color'] = '#eaeaea'
plt.rcParams['axes.labelcolor'] = '#eaeaea'
plt.rcParams['xtick.color'] = '#eaeaea'
plt.rcParams['ytick.color'] = '#eaeaea'

# Color palette
COLORS = {
    'profit': '#00d26a',
    'loss': '#ff6b6b',
    'long': '#4ecdc4',
    'short': '#ff6b9d',
    'neutral': '#95a5a6',
    'accent1': '#f39c12',
    'accent2': '#9b59b6',
    'accent3': '#3498db',
    'gradient': ['#e94560', '#f39c12', '#00d26a']
}


def load_trade_journal(filepath='trade_journal.json'):
    """Load and parse trade journal data."""
    with open(filepath, 'r') as f:
        trades = json.load(f)
    
    df = pd.DataFrame(trades)
    
    # Parse timestamps
    df['time_placed'] = pd.to_datetime(df['time_placed'])
    df['close_time'] = pd.to_datetime(df['close_time'])
    
    # Calculate hold duration in minutes
    df['hold_duration_minutes'] = (df['close_time'] - df['time_placed']).dt.total_seconds() / 60
    
    # Extract time components
    df['date'] = df['time_placed'].dt.date
    df['hour'] = df['time_placed'].dt.hour
    df['minute'] = df['time_placed'].dt.minute
    df['day_of_week'] = df['time_placed'].dt.day_name()
    df['time_of_day'] = df['time_placed'].dt.hour + df['time_placed'].dt.minute / 60
    
    # Calculate position value
    df['position_value'] = df['entry_price'] * df['quantity']
    
    return df


def plot_cumulative_pnl(df):
    """Plot cumulative profit/loss over time."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('📈 Cumulative P/L Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # Overall cumulative P/L
    ax = axes[0, 0]
    df_sorted = df.sort_values('close_time')
    cumulative = df_sorted['profit_loss'].cumsum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in cumulative]
    ax.fill_between(range(len(cumulative)), cumulative, alpha=0.3, color=COLORS['profit'])
    ax.plot(cumulative.values, color=COLORS['profit'], linewidth=2)
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Overall Cumulative P/L')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Cumulative P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Cumulative P/L by date
    ax = axes[0, 1]
    daily_pnl = df.groupby('date')['profit_loss'].sum()
    cumulative_daily = daily_pnl.cumsum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in cumulative_daily]
    ax.bar(range(len(cumulative_daily)), cumulative_daily.values, color=colors, alpha=0.8)
    ax.set_title('Cumulative P/L by Day')
    ax.set_xlabel('Trading Day')
    ax.set_ylabel('Cumulative P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Long vs Short cumulative
    ax = axes[1, 0]
    for action, color in [('LONG', COLORS['long']), ('SHORT', COLORS['short'])]:
        action_df = df_sorted[df_sorted['action'] == action]
        cumulative = action_df['profit_loss'].cumsum()
        ax.plot(range(len(cumulative)), cumulative.values, label=action, color=color, linewidth=2)
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Cumulative P/L: LONG vs SHORT')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Cumulative P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Rolling P/L (last N trades)
    ax = axes[1, 1]
    for window in [10, 25, 50]:
        rolling = df_sorted['profit_loss'].rolling(window=window).sum()
        ax.plot(rolling.values, label=f'Rolling {window}', linewidth=1.5, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Rolling P/L (Sum of Last N Trades)')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Rolling P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/01_cumulative_pnl.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_win_rate_analysis(df):
    """Analyze win rates across different dimensions."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('🎯 Win Rate Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # Overall win rate pie
    ax = axes[0, 0]
    wins = df['is_winner'].sum()
    losses = len(df) - wins
    ax.pie([wins, losses], labels=['Winners', 'Losers'], 
           colors=[COLORS['profit'], COLORS['loss']], 
           autopct='%1.1f%%', explode=(0.05, 0), startangle=90,
           textprops={'color': 'white', 'fontsize': 12})
    ax.set_title(f'Overall Win Rate\n({wins}W / {losses}L)')
    
    # Win rate by action type
    ax = axes[0, 1]
    win_rates = df.groupby('action')['is_winner'].mean() * 100
    bars = ax.bar(win_rates.index, win_rates.values, 
                  color=[COLORS['long'], COLORS['short']], alpha=0.8)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5, label='50% baseline')
    ax.set_title('Win Rate by Action Type')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    for bar, val in zip(bars, win_rates.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                f'{val:.1f}%', ha='center', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Win rate by hour
    ax = axes[0, 2]
    hourly_wr = df.groupby('hour')['is_winner'].mean() * 100
    bars = ax.bar(hourly_wr.index, hourly_wr.values, 
                  color=[COLORS['profit'] if x > 50 else COLORS['loss'] for x in hourly_wr.values], 
                  alpha=0.8)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Hour')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    # Win rate by day of week
    ax = axes[1, 0]
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    daily_wr = df.groupby('day_of_week')['is_winner'].mean() * 100
    daily_wr = daily_wr.reindex(days_order)
    bars = ax.bar(range(len(daily_wr)), daily_wr.values,
                  color=[COLORS['profit'] if x > 50 else COLORS['loss'] for x in daily_wr.values],
                  alpha=0.8)
    ax.set_xticks(range(len(daily_wr)))
    ax.set_xticklabels([d[:3] for d in days_order])
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Day of Week')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    # Rolling win rate
    ax = axes[1, 1]
    df_sorted = df.sort_values('close_time')
    for window in [20, 50, 100]:
        rolling_wr = df_sorted['is_winner'].rolling(window=window).mean() * 100
        ax.plot(rolling_wr.values, label=f'Rolling {window}', linewidth=1.5)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Rolling Win Rate Over Time')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Win rate by position size quartile
    ax = axes[1, 2]
    df['position_quartile'] = pd.qcut(df['position_value'], q=4, labels=['Q1 (Small)', 'Q2', 'Q3', 'Q4 (Large)'])
    quartile_wr = df.groupby('position_quartile')['is_winner'].mean() * 100
    bars = ax.bar(range(len(quartile_wr)), quartile_wr.values,
                  color=[COLORS['profit'] if x > 50 else COLORS['loss'] for x in quartile_wr.values],
                  alpha=0.8)
    ax.set_xticks(range(len(quartile_wr)))
    ax.set_xticklabels(quartile_wr.index, rotation=15)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Position Size')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/02_win_rate_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_pnl_distribution(df):
    """Plot P/L distribution histograms."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('📊 P/L Distribution Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # Overall P/L distribution
    ax = axes[0, 0]
    profits = df[df['profit_loss'] >= 0]['profit_loss']
    losses = df[df['profit_loss'] < 0]['profit_loss']
    ax.hist(profits, bins=30, alpha=0.7, color=COLORS['profit'], label='Profits', edgecolor='white')
    ax.hist(losses, bins=30, alpha=0.7, color=COLORS['loss'], label='Losses', edgecolor='white')
    ax.axvline(x=df['profit_loss'].mean(), color='yellow', linestyle='--', linewidth=2, label=f'Mean: ${df["profit_loss"].mean():.2f}')
    ax.axvline(x=df['profit_loss'].median(), color='cyan', linestyle='--', linewidth=2, label=f'Median: ${df["profit_loss"].median():.2f}')
    ax.set_title('P/L Distribution ($)')
    ax.set_xlabel('Profit/Loss ($)')
    ax.set_ylabel('Frequency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # P/L % distribution
    ax = axes[0, 1]
    ax.hist(df['profit_loss_percent'], bins=50, alpha=0.7, 
            color=[COLORS['profit'] if x >= 0 else COLORS['loss'] for x in df['profit_loss_percent'].sort_values()],
            edgecolor='white')
    ax.axvline(x=0, color='white', linestyle='-', linewidth=2)
    ax.axvline(x=df['profit_loss_percent'].mean(), color='yellow', linestyle='--', 
               label=f'Mean: {df["profit_loss_percent"].mean():.2f}%')
    ax.set_title('P/L Distribution (%)')
    ax.set_xlabel('Profit/Loss (%)')
    ax.set_ylabel('Frequency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # P/L by action type boxplot
    ax = axes[0, 2]
    data = [df[df['action'] == 'LONG']['profit_loss'].values,
            df[df['action'] == 'SHORT']['profit_loss'].values]
    bp = ax.boxplot(data, labels=['LONG', 'SHORT'], patch_artist=True)
    bp['boxes'][0].set_facecolor(COLORS['long'])
    bp['boxes'][1].set_facecolor(COLORS['short'])
    for element in ['whiskers', 'fliers', 'means', 'medians', 'caps']:
        plt.setp(bp[element], color='white')
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('P/L Distribution by Action Type')
    ax.set_ylabel('Profit/Loss ($)')
    ax.grid(True, alpha=0.3)
    
    # Average win vs average loss
    ax = axes[1, 0]
    avg_win = df[df['is_winner']]['profit_loss'].mean()
    avg_loss = abs(df[~df['is_winner']]['profit_loss'].mean())
    bars = ax.bar(['Avg Win', 'Avg Loss'], [avg_win, avg_loss],
                  color=[COLORS['profit'], COLORS['loss']], alpha=0.8)
    ratio = avg_win / avg_loss if avg_loss > 0 else 0
    ax.set_title(f'Average Win vs Loss\nRisk/Reward Ratio: {ratio:.2f}')
    ax.set_ylabel('Amount ($)')
    for bar, val in zip(bars, [avg_win, avg_loss]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'${val:.2f}', ha='center', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Profit factor by period
    ax = axes[1, 1]
    df_sorted = df.sort_values('close_time')
    profit_factors = []
    windows = list(range(20, min(len(df), 200), 20))
    for w in windows:
        gross_profit = df_sorted['profit_loss'].iloc[:w][df_sorted['profit_loss'].iloc[:w] > 0].sum()
        gross_loss = abs(df_sorted['profit_loss'].iloc[:w][df_sorted['profit_loss'].iloc[:w] < 0].sum())
        pf = gross_profit / gross_loss if gross_loss > 0 else 0
        profit_factors.append(pf)
    ax.plot(windows, profit_factors, color=COLORS['accent1'], linewidth=2, marker='o')
    ax.axhline(y=1, color='white', linestyle='--', alpha=0.5, label='Break-even (1.0)')
    ax.set_title('Profit Factor Evolution')
    ax.set_xlabel('Number of Trades')
    ax.set_ylabel('Profit Factor')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Daily P/L distribution
    ax = axes[1, 2]
    daily_pnl = df.groupby('date')['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in daily_pnl.values]
    ax.bar(range(len(daily_pnl)), daily_pnl.values, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.axhline(y=daily_pnl.mean(), color='yellow', linestyle='--', 
               label=f'Mean: ${daily_pnl.mean():.2f}')
    ax.set_title('Daily P/L')
    ax.set_xlabel('Trading Day')
    ax.set_ylabel('P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/03_pnl_distribution.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_time_analysis(df):
    """Analyze performance by time of day."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('⏰ Time-Based Performance Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # P/L by hour
    ax = axes[0, 0]
    hourly_pnl = df.groupby('hour')['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in hourly_pnl.values]
    ax.bar(hourly_pnl.index, hourly_pnl.values, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Hour')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Average P/L by hour
    ax = axes[0, 1]
    hourly_avg = df.groupby('hour')['profit_loss'].mean()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in hourly_avg.values]
    ax.bar(hourly_avg.index, hourly_avg.values, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Average P/L per Trade by Hour')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Average P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Trade count by hour
    ax = axes[0, 2]
    hourly_count = df.groupby('hour').size()
    ax.bar(hourly_count.index, hourly_count.values, color=COLORS['accent3'], alpha=0.8)
    ax.set_title('Trade Volume by Hour')
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Number of Trades')
    ax.grid(True, alpha=0.3)
    
    # P/L heatmap by hour and day
    ax = axes[1, 0]
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    pivot = df.pivot_table(values='profit_loss', index='day_of_week', columns='hour', aggfunc='sum')
    pivot = pivot.reindex(days_order)
    im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto')
    ax.set_yticks(range(len(days_order)))
    ax.set_yticklabels([d[:3] for d in days_order])
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_title('P/L Heatmap (Day × Hour)')
    ax.set_xlabel('Hour')
    ax.set_ylabel('Day')
    plt.colorbar(im, ax=ax, label='P/L ($)')
    
    # Performance by minutes after market open
    ax = axes[1, 1]
    df['minutes_after_open'] = (df['hour'] - 9) * 60 + df['minute'] - 30  # Market opens 9:30
    df['minutes_after_open'] = df['minutes_after_open'].clip(lower=0)
    bins = list(range(0, 400, 30))
    df['time_bucket'] = pd.cut(df['minutes_after_open'], bins=bins)
    time_pnl = df.groupby('time_bucket', observed=True)['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in time_pnl.values]
    ax.bar(range(len(time_pnl)), time_pnl.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(time_pnl)))
    ax.set_xticklabels([f'{int(b.left)}-{int(b.right)}' for b in time_pnl.index], rotation=45)
    ax.set_title('P/L by Minutes After Market Open')
    ax.set_xlabel('Minutes After Open')
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # P/L by day of week
    ax = axes[1, 2]
    daily_pnl = df.groupby('day_of_week')['profit_loss'].sum()
    daily_pnl = daily_pnl.reindex(days_order)
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in daily_pnl.values]
    bars = ax.bar(range(len(daily_pnl)), daily_pnl.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(daily_pnl)))
    ax.set_xticklabels([d[:3] for d in days_order])
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Day of Week')
    ax.set_ylabel('Total P/L ($)')
    for bar, val in zip(bars, daily_pnl.values):
        ypos = bar.get_height() + (5 if val >= 0 else -15)
        ax.text(bar.get_x() + bar.get_width()/2, ypos, f'${val:.0f}', 
                ha='center', fontsize=10, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/04_time_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_hold_duration_analysis(df):
    """Analyze performance by hold duration."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('⏱️ Hold Duration Analysis (Key for TRADE_HOLD_MINUTES optimization)', 
                 fontsize=18, fontweight='bold', color='#e94560')
    
    # Hold duration distribution
    ax = axes[0, 0]
    ax.hist(df['hold_duration_minutes'], bins=50, alpha=0.7, color=COLORS['accent3'], edgecolor='white')
    ax.axvline(x=df['hold_duration_minutes'].mean(), color='yellow', linestyle='--', 
               label=f'Mean: {df["hold_duration_minutes"].mean():.1f} min')
    ax.axvline(x=df['hold_duration_minutes'].median(), color='cyan', linestyle='--',
               label=f'Median: {df["hold_duration_minutes"].median():.1f} min')
    ax.set_title('Hold Duration Distribution')
    ax.set_xlabel('Hold Duration (minutes)')
    ax.set_ylabel('Frequency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Win rate by hold duration
    ax = axes[0, 1]
    duration_bins = [0, 5, 10, 15, 20, 25, 30, 45, 60, float('inf')]
    labels = ['0-5', '5-10', '10-15', '15-20', '20-25', '25-30', '30-45', '45-60', '60+']
    df['duration_bucket'] = pd.cut(df['hold_duration_minutes'], bins=duration_bins, labels=labels)
    wr_by_duration = df.groupby('duration_bucket', observed=True)['is_winner'].mean() * 100
    colors = [COLORS['profit'] if x > 50 else COLORS['loss'] for x in wr_by_duration.values]
    bars = ax.bar(range(len(wr_by_duration)), wr_by_duration.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(wr_by_duration)))
    ax.set_xticklabels(wr_by_duration.index, rotation=45)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Hold Duration')
    ax.set_xlabel('Hold Duration (minutes)')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    # Average P/L by hold duration
    ax = axes[0, 2]
    pnl_by_duration = df.groupby('duration_bucket', observed=True)['profit_loss'].mean()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in pnl_by_duration.values]
    bars = ax.bar(range(len(pnl_by_duration)), pnl_by_duration.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(pnl_by_duration)))
    ax.set_xticklabels(pnl_by_duration.index, rotation=45)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Average P/L by Hold Duration')
    ax.set_xlabel('Hold Duration (minutes)')
    ax.set_ylabel('Average P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Scatter: Hold duration vs P/L %
    ax = axes[1, 0]
    winners = df[df['is_winner']]
    losers = df[~df['is_winner']]
    ax.scatter(losers['hold_duration_minutes'], losers['profit_loss_percent'], 
               alpha=0.5, c=COLORS['loss'], label='Losers', s=30)
    ax.scatter(winners['hold_duration_minutes'], winners['profit_loss_percent'], 
               alpha=0.5, c=COLORS['profit'], label='Winners', s=30)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Hold Duration vs P/L %')
    ax.set_xlabel('Hold Duration (minutes)')
    ax.set_ylabel('P/L (%)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Cumulative P/L if we had different hold times
    ax = axes[1, 1]
    # Simulate different hold durations
    hold_times = [5, 10, 15, 20, 25, 30, 45, 60]
    # We can only approximate this - show total P/L for trades within each duration
    simulated_pnl = []
    for ht in hold_times:
        trades_in_window = df[df['hold_duration_minutes'] <= ht]
        simulated_pnl.append(trades_in_window['profit_loss'].sum())
    ax.plot(hold_times, simulated_pnl, marker='o', linewidth=2, color=COLORS['accent1'])
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Total P/L for Trades Closed Within X Minutes')
    ax.set_xlabel('Max Hold Duration (minutes)')
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Trade count by duration bucket
    ax = axes[1, 2]
    count_by_duration = df.groupby('duration_bucket', observed=True).size()
    ax.bar(range(len(count_by_duration)), count_by_duration.values, color=COLORS['accent2'], alpha=0.8)
    ax.set_xticks(range(len(count_by_duration)))
    ax.set_xticklabels(count_by_duration.index, rotation=45)
    ax.set_title('Trade Count by Hold Duration')
    ax.set_xlabel('Hold Duration (minutes)')
    ax.set_ylabel('Number of Trades')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/05_hold_duration_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_ticker_analysis(df):
    """Analyze performance by ticker."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('🏷️ Ticker Performance Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # Top 15 tickers by P/L
    ax = axes[0, 0]
    ticker_pnl = df.groupby('ticker')['profit_loss'].sum().sort_values()
    top_bottom = pd.concat([ticker_pnl.head(10), ticker_pnl.tail(10)])
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in top_bottom.values]
    ax.barh(range(len(top_bottom)), top_bottom.values, color=colors, alpha=0.8)
    ax.set_yticks(range(len(top_bottom)))
    ax.set_yticklabels(top_bottom.index)
    ax.axvline(x=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Top 10 Best & Worst Tickers by P/L')
    ax.set_xlabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Win rate by ticker (top traded)
    ax = axes[0, 1]
    top_tickers = df['ticker'].value_counts().head(20).index
    ticker_wr = df[df['ticker'].isin(top_tickers)].groupby('ticker')['is_winner'].mean() * 100
    ticker_wr = ticker_wr.sort_values(ascending=True)
    colors = [COLORS['profit'] if x > 50 else COLORS['loss'] for x in ticker_wr.values]
    ax.barh(range(len(ticker_wr)), ticker_wr.values, color=colors, alpha=0.8)
    ax.set_yticks(range(len(ticker_wr)))
    ax.set_yticklabels(ticker_wr.index)
    ax.axvline(x=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Ticker (Top 20 Most Traded)')
    ax.set_xlabel('Win Rate (%)')
    ax.set_xlim(0, 100)
    ax.grid(True, alpha=0.3)
    
    # Trade count by ticker
    ax = axes[1, 0]
    ticker_counts = df['ticker'].value_counts().head(20)
    ax.barh(range(len(ticker_counts)), ticker_counts.values, color=COLORS['accent3'], alpha=0.8)
    ax.set_yticks(range(len(ticker_counts)))
    ax.set_yticklabels(ticker_counts.index)
    ax.set_title('Most Frequently Traded Tickers')
    ax.set_xlabel('Number of Trades')
    ax.grid(True, alpha=0.3)
    
    # Average P/L per trade by ticker
    ax = axes[1, 1]
    ticker_avg = df.groupby('ticker')['profit_loss'].mean()
    ticker_counts_full = df['ticker'].value_counts()
    # Only show tickers with at least 3 trades
    valid_tickers = ticker_counts_full[ticker_counts_full >= 3].index
    ticker_avg = ticker_avg[ticker_avg.index.isin(valid_tickers)].sort_values()
    top_bottom_avg = pd.concat([ticker_avg.head(10), ticker_avg.tail(10)])
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in top_bottom_avg.values]
    ax.barh(range(len(top_bottom_avg)), top_bottom_avg.values, color=colors, alpha=0.8)
    ax.set_yticks(range(len(top_bottom_avg)))
    ax.set_yticklabels(top_bottom_avg.index)
    ax.axvline(x=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Average P/L per Trade (min 3 trades)')
    ax.set_xlabel('Average P/L ($)')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/06_ticker_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_position_size_analysis(df):
    """Analyze performance by position size."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('💰 Position Size Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    # Position value distribution
    ax = axes[0, 0]
    ax.hist(df['position_value'], bins=50, alpha=0.7, color=COLORS['accent2'], edgecolor='white')
    ax.axvline(x=df['position_value'].mean(), color='yellow', linestyle='--',
               label=f'Mean: ${df["position_value"].mean():.0f}')
    ax.set_title('Position Value Distribution')
    ax.set_xlabel('Position Value ($)')
    ax.set_ylabel('Frequency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Scatter: Position size vs P/L
    ax = axes[0, 1]
    winners = df[df['is_winner']]
    losers = df[~df['is_winner']]
    ax.scatter(losers['position_value'], losers['profit_loss'], 
               alpha=0.5, c=COLORS['loss'], label='Losers', s=30)
    ax.scatter(winners['position_value'], winners['profit_loss'], 
               alpha=0.5, c=COLORS['profit'], label='Winners', s=30)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Position Size vs P/L')
    ax.set_xlabel('Position Value ($)')
    ax.set_ylabel('P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # P/L by position size quartile
    ax = axes[0, 2]
    quartile_pnl = df.groupby('position_quartile', observed=True)['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in quartile_pnl.values]
    bars = ax.bar(range(len(quartile_pnl)), quartile_pnl.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(quartile_pnl)))
    ax.set_xticklabels(quartile_pnl.index, rotation=15)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Position Size Quartile')
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Entry price distribution
    ax = axes[1, 0]
    ax.hist(df['entry_price'], bins=50, alpha=0.7, color=COLORS['accent1'], edgecolor='white')
    ax.set_title('Entry Price Distribution')
    ax.set_xlabel('Entry Price ($)')
    ax.set_ylabel('Frequency')
    ax.grid(True, alpha=0.3)
    
    # P/L vs entry price
    ax = axes[1, 1]
    # Bin entry prices
    price_bins = [0, 5, 10, 25, 50, 100, float('inf')]
    price_labels = ['$0-5', '$5-10', '$10-25', '$25-50', '$50-100', '$100+']
    df['price_bucket'] = pd.cut(df['entry_price'], bins=price_bins, labels=price_labels)
    pnl_by_price = df.groupby('price_bucket', observed=True)['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in pnl_by_price.values]
    ax.bar(range(len(pnl_by_price)), pnl_by_price.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(pnl_by_price)))
    ax.set_xticklabels(pnl_by_price.index, rotation=15)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Entry Price Range')
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Win rate by entry price
    ax = axes[1, 2]
    wr_by_price = df.groupby('price_bucket', observed=True)['is_winner'].mean() * 100
    colors = [COLORS['profit'] if x > 50 else COLORS['loss'] for x in wr_by_price.values]
    ax.bar(range(len(wr_by_price)), wr_by_price.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(wr_by_price)))
    ax.set_xticklabels(wr_by_price.index, rotation=15)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Entry Price Range')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/07_position_size_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_drawdown_analysis(df):
    """Analyze drawdowns and risk metrics."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('📉 Drawdown & Risk Analysis', fontsize=18, fontweight='bold', color='#e94560')
    
    df_sorted = df.sort_values('close_time')
    cumulative = df_sorted['profit_loss'].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    
    # Cumulative P/L with drawdown
    ax = axes[0, 0]
    ax.fill_between(range(len(cumulative)), cumulative.values, alpha=0.3, color=COLORS['profit'])
    ax.plot(cumulative.values, color=COLORS['profit'], linewidth=2, label='Cumulative P/L')
    ax.plot(running_max.values, color='yellow', linewidth=1, linestyle='--', label='Running Max')
    ax.set_title('Cumulative P/L with Running Maximum')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Drawdown chart
    ax = axes[0, 1]
    ax.fill_between(range(len(drawdown)), drawdown.values, alpha=0.5, color=COLORS['loss'])
    ax.plot(drawdown.values, color=COLORS['loss'], linewidth=1)
    max_dd = drawdown.min()
    max_dd_idx = drawdown.idxmin()
    ax.scatter([list(drawdown.index).index(max_dd_idx)], [max_dd], color='white', s=100, zorder=5)
    ax.annotate(f'Max DD: ${max_dd:.2f}', 
                xy=(list(drawdown.index).index(max_dd_idx), max_dd),
                xytext=(10, 10), textcoords='offset points',
                fontsize=10, color='white')
    ax.set_title('Drawdown Over Time')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Drawdown ($)')
    ax.grid(True, alpha=0.3)
    
    # Consecutive wins/losses
    ax = axes[1, 0]
    streaks = []
    current_streak = 0
    last_result = None
    for is_win in df_sorted['is_winner']:
        if last_result is None:
            current_streak = 1 if is_win else -1
        elif is_win == last_result:
            current_streak += 1 if is_win else -1
        else:
            streaks.append(current_streak)
            current_streak = 1 if is_win else -1
        last_result = is_win
    streaks.append(current_streak)
    
    colors = [COLORS['profit'] if s > 0 else COLORS['loss'] for s in streaks]
    ax.bar(range(len(streaks)), streaks, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Win/Loss Streaks')
    ax.set_xlabel('Streak Number')
    ax.set_ylabel('Streak Length (+ wins, - losses)')
    ax.grid(True, alpha=0.3)
    
    # Risk metrics summary
    ax = axes[1, 1]
    ax.axis('off')
    
    # Calculate metrics
    total_trades = len(df)
    win_rate = df['is_winner'].mean() * 100
    total_pnl = df['profit_loss'].sum()
    avg_win = df[df['is_winner']]['profit_loss'].mean() if df['is_winner'].any() else 0
    avg_loss = df[~df['is_winner']]['profit_loss'].mean() if (~df['is_winner']).any() else 0
    gross_profit = df[df['profit_loss'] > 0]['profit_loss'].sum()
    gross_loss = abs(df[df['profit_loss'] < 0]['profit_loss'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    max_win = df['profit_loss'].max()
    max_loss = df['profit_loss'].min()
    max_consecutive_wins = max([s for s in streaks if s > 0], default=0)
    max_consecutive_losses = abs(min([s for s in streaks if s < 0], default=0))
    sharpe_approx = df['profit_loss'].mean() / df['profit_loss'].std() if df['profit_loss'].std() > 0 else 0
    
    metrics_text = f"""
    ═══════════════════════════════════════════
                   PERFORMANCE SUMMARY
    ═══════════════════════════════════════════
    
    📊 TRADE STATISTICS
    ────────────────────────────────────────────
    Total Trades:              {total_trades:,}
    Win Rate:                  {win_rate:.1f}%
    Total P/L:                 ${total_pnl:,.2f}
    
    💰 P/L METRICS
    ────────────────────────────────────────────
    Average Win:               ${avg_win:,.2f}
    Average Loss:              ${avg_loss:,.2f}
    Risk/Reward Ratio:         {abs(avg_win/avg_loss) if avg_loss != 0 else 0:.2f}
    Profit Factor:             {profit_factor:.2f}
    
    📈 EXTREMES
    ────────────────────────────────────────────
    Largest Win:               ${max_win:,.2f}
    Largest Loss:              ${max_loss:,.2f}
    Max Drawdown:              ${max_dd:,.2f}
    
    🔥 STREAKS
    ────────────────────────────────────────────
    Max Consecutive Wins:      {max_consecutive_wins}
    Max Consecutive Losses:    {max_consecutive_losses}
    
    📐 RISK METRICS
    ────────────────────────────────────────────
    Approx. Sharpe Ratio:      {sharpe_approx:.3f}
    ═══════════════════════════════════════════
    """
    
    ax.text(0.1, 0.5, metrics_text, transform=ax.transAxes, fontsize=11,
            verticalalignment='center', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#0f3460', alpha=0.8))
    
    plt.tight_layout()
    plt.savefig('plots/08_drawdown_analysis.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_long_vs_short_analysis(df):
    """Deep dive into LONG vs SHORT performance."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('⚔️ LONG vs SHORT Performance Comparison', fontsize=18, fontweight='bold', color='#e94560')
    
    long_df = df[df['action'] == 'LONG']
    short_df = df[df['action'] == 'SHORT']
    
    # Total P/L comparison
    ax = axes[0, 0]
    totals = [long_df['profit_loss'].sum(), short_df['profit_loss'].sum()]
    colors = [COLORS['long'], COLORS['short']]
    bars = ax.bar(['LONG', 'SHORT'], totals, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Action Type')
    ax.set_ylabel('Total P/L ($)')
    for bar, val in zip(bars, totals):
        ypos = bar.get_height() + (5 if val >= 0 else -20)
        ax.text(bar.get_x() + bar.get_width()/2, ypos, f'${val:.2f}', 
                ha='center', fontsize=12, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Trade count comparison
    ax = axes[0, 1]
    counts = [len(long_df), len(short_df)]
    ax.bar(['LONG', 'SHORT'], counts, color=colors, alpha=0.8)
    ax.set_title('Trade Count by Action Type')
    ax.set_ylabel('Number of Trades')
    ax.grid(True, alpha=0.3)
    
    # Average P/L per trade
    ax = axes[0, 2]
    avgs = [long_df['profit_loss'].mean(), short_df['profit_loss'].mean()]
    bars_colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in avgs]
    bars = ax.bar(['LONG', 'SHORT'], avgs, color=bars_colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Average P/L per Trade')
    ax.set_ylabel('Average P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Win rate by hour - LONG vs SHORT
    ax = axes[1, 0]
    long_hourly = long_df.groupby('hour')['is_winner'].mean() * 100
    short_hourly = short_df.groupby('hour')['is_winner'].mean() * 100
    hours = sorted(set(long_hourly.index) | set(short_hourly.index))
    x = np.arange(len(hours))
    width = 0.35
    ax.bar(x - width/2, [long_hourly.get(h, 0) for h in hours], width, 
           label='LONG', color=COLORS['long'], alpha=0.8)
    ax.bar(x + width/2, [short_hourly.get(h, 0) for h in hours], width,
           label='SHORT', color=COLORS['short'], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(hours)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Hour: LONG vs SHORT')
    ax.set_xlabel('Hour')
    ax.set_ylabel('Win Rate (%)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # P/L distribution comparison
    ax = axes[1, 1]
    ax.hist(long_df['profit_loss'], bins=30, alpha=0.6, color=COLORS['long'], label='LONG', edgecolor='white')
    ax.hist(short_df['profit_loss'], bins=30, alpha=0.6, color=COLORS['short'], label='SHORT', edgecolor='white')
    ax.axvline(x=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('P/L Distribution: LONG vs SHORT')
    ax.set_xlabel('P/L ($)')
    ax.set_ylabel('Frequency')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Performance by day - LONG vs SHORT
    ax = axes[1, 2]
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    long_daily = long_df.groupby('day_of_week')['profit_loss'].sum().reindex(days_order).fillna(0)
    short_daily = short_df.groupby('day_of_week')['profit_loss'].sum().reindex(days_order).fillna(0)
    x = np.arange(len(days_order))
    width = 0.35
    ax.bar(x - width/2, long_daily.values, width, label='LONG', color=COLORS['long'], alpha=0.8)
    ax.bar(x + width/2, short_daily.values, width, label='SHORT', color=COLORS['short'], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([d[:3] for d in days_order])
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Total P/L by Day: LONG vs SHORT')
    ax.set_ylabel('Total P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('plots/09_long_vs_short.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def plot_optimization_insights(df):
    """Generate actionable insights for parameter optimization."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    fig.suptitle('🔧 Parameter Optimization Insights', fontsize=18, fontweight='bold', color='#e94560')
    
    # Optimal hold time analysis
    ax = axes[0, 0]
    hold_times = range(5, 65, 5)
    cumulative_pnl = []
    for ht in hold_times:
        # Calculate P/L for trades closed within this time
        pnl = df[df['hold_duration_minutes'] <= ht]['profit_loss'].sum()
        cumulative_pnl.append(pnl)
    
    ax.plot(list(hold_times), cumulative_pnl, marker='o', linewidth=2, color=COLORS['accent1'])
    best_ht = list(hold_times)[np.argmax(cumulative_pnl)]
    ax.axvline(x=best_ht, color=COLORS['profit'], linestyle='--', 
               label=f'Optimal: {best_ht} min')
    ax.set_title('P/L by Maximum Hold Time')
    ax.set_xlabel('Max Hold Duration (minutes)')
    ax.set_ylabel('Total P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Best trading hours
    ax = axes[0, 1]
    hourly_stats = df.groupby('hour').agg({
        'profit_loss': ['sum', 'mean', 'count'],
        'is_winner': 'mean'
    })
    hourly_stats.columns = ['total_pnl', 'avg_pnl', 'count', 'win_rate']
    # Score = avg_pnl * win_rate * log(count)
    hourly_stats['score'] = hourly_stats['avg_pnl'] * hourly_stats['win_rate'] * np.log1p(hourly_stats['count'])
    colors = [COLORS['profit'] if x > 0 else COLORS['loss'] for x in hourly_stats['score']]
    ax.bar(hourly_stats.index, hourly_stats['score'].values, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Hour Quality Score\n(avg_pnl × win_rate × log(trades))')
    ax.set_xlabel('Hour')
    ax.set_ylabel('Quality Score')
    ax.grid(True, alpha=0.3)
    
    # Position size optimization
    ax = axes[0, 2]
    # Group by position size deciles
    df['position_decile'] = pd.qcut(df['position_value'], q=10, labels=range(1, 11), duplicates='drop')
    decile_stats = df.groupby('position_decile', observed=True).agg({
        'profit_loss': ['sum', 'mean'],
        'is_winner': 'mean',
        'position_value': 'mean'
    })
    decile_stats.columns = ['total_pnl', 'avg_pnl', 'win_rate', 'avg_position']
    
    ax2 = ax.twinx()
    ax.bar(range(len(decile_stats)), decile_stats['avg_pnl'].values, 
           color=COLORS['accent3'], alpha=0.6, label='Avg P/L')
    ax2.plot(range(len(decile_stats)), decile_stats['win_rate'].values * 100, 
             color=COLORS['accent1'], marker='o', linewidth=2, label='Win Rate')
    ax.set_xticks(range(len(decile_stats)))
    ax.set_xticklabels([f'D{i}' for i in decile_stats.index])
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('Performance by Position Size Decile')
    ax.set_xlabel('Position Size Decile (D1=smallest)')
    ax.set_ylabel('Average P/L ($)', color=COLORS['accent3'])
    ax2.set_ylabel('Win Rate (%)', color=COLORS['accent1'])
    ax2.axhline(y=50, color=COLORS['accent1'], linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    
    # Price range performance
    ax = axes[1, 0]
    price_bins = [0, 2, 5, 10, 20, 50, 100, float('inf')]
    price_labels = ['<$2', '$2-5', '$5-10', '$10-20', '$20-50', '$50-100', '>$100']
    df['detailed_price_bucket'] = pd.cut(df['entry_price'], bins=price_bins, labels=price_labels)
    price_perf = df.groupby('detailed_price_bucket', observed=True).agg({
        'profit_loss': 'mean',
        'is_winner': 'mean'
    })
    
    x = np.arange(len(price_perf))
    width = 0.35
    ax.bar(x - width/2, price_perf['profit_loss'].values, width, 
           label='Avg P/L ($)', color=COLORS['accent2'], alpha=0.8)
    ax2 = ax.twinx()
    ax2.bar(x + width/2, price_perf['is_winner'].values * 100, width,
            label='Win Rate (%)', color=COLORS['accent1'], alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(price_perf.index, rotation=15)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax2.axhline(y=50, color=COLORS['accent1'], linestyle='--', alpha=0.3)
    ax.set_title('Performance by Stock Price Range')
    ax.set_ylabel('Avg P/L ($)', color=COLORS['accent2'])
    ax2.set_ylabel('Win Rate (%)', color=COLORS['accent1'])
    ax.grid(True, alpha=0.3)
    
    # Filter recommendations
    ax = axes[1, 1]
    ax.axis('off')
    
    # Calculate recommendations
    best_hours = hourly_stats.nlargest(3, 'score').index.tolist()
    worst_hours = hourly_stats.nsmallest(2, 'score').index.tolist()
    
    best_action = 'LONG' if df[df['action']=='LONG']['profit_loss'].sum() > df[df['action']=='SHORT']['profit_loss'].sum() else 'SHORT'
    
    duration_pnl = df.groupby('duration_bucket', observed=True)['profit_loss'].sum()
    best_duration = duration_pnl.idxmax() if not duration_pnl.empty else 'N/A'
    
    long_wr = df[df['action']=='LONG']['is_winner'].mean() * 100
    short_wr = df[df['action']=='SHORT']['is_winner'].mean() * 100
    
    recommendations = f"""
    ╔═══════════════════════════════════════════════════════╗
    ║           OPTIMIZATION RECOMMENDATIONS                ║
    ╠═══════════════════════════════════════════════════════╣
    ║                                                       ║
    ║  🕐 BEST TRADING HOURS                               ║
    ║     → {', '.join([f'{h}:00' for h in best_hours]):40}║
    ║                                                       ║
    ║  🚫 AVOID TRADING HOURS                              ║
    ║     → {', '.join([f'{h}:00' for h in worst_hours]):40}║
    ║                                                       ║
    ║  ⏱️  OPTIMAL HOLD DURATION                           ║
    ║     → Best bucket: {str(best_duration):32}║
    ║     → Suggested TRADE_HOLD_MINUTES: {best_ht:17}║
    ║                                                       ║
    ║  📊 ACTION TYPE PERFORMANCE                          ║
    ║     → LONG Win Rate:  {long_wr:5.1f}%                     ║
    ║     → SHORT Win Rate: {short_wr:5.1f}%                     ║
    ║     → Better performer: {best_action:25}║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝
    """
    
    ax.text(0.05, 0.5, recommendations, transform=ax.transAxes, fontsize=11,
            verticalalignment='center', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#0f3460', alpha=0.8))
    
    # Edge case analysis
    ax = axes[1, 2]
    # Top 10 biggest wins and losses
    biggest = df.nlargest(10, 'profit_loss')[['ticker', 'action', 'profit_loss', 'hold_duration_minutes']]
    smallest = df.nsmallest(10, 'profit_loss')[['ticker', 'action', 'profit_loss', 'hold_duration_minutes']]
    
    ax.axis('off')
    table_text = "TOP 5 WINS                  TOP 5 LOSSES\n"
    table_text += "─" * 50 + "\n"
    for i in range(5):
        win = biggest.iloc[i]
        loss = smallest.iloc[i]
        table_text += f"{win['ticker']:6} ${win['profit_loss']:7.2f}  {win['hold_duration_minutes']:4.0f}m   "
        table_text += f"{loss['ticker']:6} ${loss['profit_loss']:7.2f}  {loss['hold_duration_minutes']:4.0f}m\n"
    
    ax.text(0.1, 0.7, table_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='#0f3460', alpha=0.8))
    
    ax.text(0.1, 0.3, "💡 TIP: Review biggest losses for patterns\nto filter out similar trades.", 
            transform=ax.transAxes, fontsize=10, color='yellow')
    
    plt.tight_layout()
    plt.savefig('plots/10_optimization_insights.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def generate_summary_dashboard(df):
    """Generate a summary dashboard with key metrics."""
    fig = plt.figure(figsize=(20, 14))
    fig.suptitle('📊 TRADING ALGORITHM PERFORMANCE DASHBOARD', 
                 fontsize=24, fontweight='bold', color='#e94560', y=0.98)
    
    # Create grid
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    # Key metrics cards (top row)
    metrics = [
        ('Total Trades', f"{len(df):,}", COLORS['accent3']),
        ('Win Rate', f"{df['is_winner'].mean()*100:.1f}%", 
         COLORS['profit'] if df['is_winner'].mean() > 0.5 else COLORS['loss']),
        ('Total P/L', f"${df['profit_loss'].sum():,.2f}", 
         COLORS['profit'] if df['profit_loss'].sum() > 0 else COLORS['loss']),
        ('Profit Factor', f"{df[df['profit_loss']>0]['profit_loss'].sum() / abs(df[df['profit_loss']<0]['profit_loss'].sum()) if df[df['profit_loss']<0]['profit_loss'].sum() != 0 else 0:.2f}",
         COLORS['accent1'])
    ]
    
    for i, (title, value, color) in enumerate(metrics):
        ax = fig.add_subplot(gs[0, i])
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.add_patch(plt.Rectangle((0.05, 0.1), 0.9, 0.8, fill=True, 
                                    facecolor=color, alpha=0.2, edgecolor=color, linewidth=2))
        ax.text(0.5, 0.65, value, ha='center', va='center', fontsize=24, fontweight='bold', color=color)
        ax.text(0.5, 0.3, title, ha='center', va='center', fontsize=12, color='white')
        ax.axis('off')
    
    # Cumulative P/L chart
    ax = fig.add_subplot(gs[1, :2])
    df_sorted = df.sort_values('close_time')
    cumulative = df_sorted['profit_loss'].cumsum()
    ax.fill_between(range(len(cumulative)), cumulative.values, alpha=0.3, 
                    color=COLORS['profit'] if cumulative.iloc[-1] > 0 else COLORS['loss'])
    ax.plot(cumulative.values, linewidth=2, 
            color=COLORS['profit'] if cumulative.iloc[-1] > 0 else COLORS['loss'])
    ax.axhline(y=0, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Cumulative P/L Over Time', fontsize=14)
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Cumulative P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Win rate by hour
    ax = fig.add_subplot(gs[1, 2:])
    hourly_wr = df.groupby('hour')['is_winner'].mean() * 100
    colors = [COLORS['profit'] if x > 50 else COLORS['loss'] for x in hourly_wr.values]
    ax.bar(hourly_wr.index, hourly_wr.values, color=colors, alpha=0.8)
    ax.axhline(y=50, color='white', linestyle='--', alpha=0.5)
    ax.set_title('Win Rate by Hour', fontsize=14)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Win Rate (%)')
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    
    # LONG vs SHORT comparison
    ax = fig.add_subplot(gs[2, 0])
    long_pnl = df[df['action']=='LONG']['profit_loss'].sum()
    short_pnl = df[df['action']=='SHORT']['profit_loss'].sum()
    colors = [COLORS['long'], COLORS['short']]
    bars = ax.bar(['LONG', 'SHORT'], [long_pnl, short_pnl], color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('P/L: LONG vs SHORT', fontsize=14)
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Hold duration performance
    ax = fig.add_subplot(gs[2, 1])
    duration_bins = [0, 10, 20, 30, 60, float('inf')]
    labels = ['0-10', '10-20', '20-30', '30-60', '60+']
    df['dur_bucket'] = pd.cut(df['hold_duration_minutes'], bins=duration_bins, labels=labels)
    dur_pnl = df.groupby('dur_bucket', observed=True)['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in dur_pnl.values]
    ax.bar(range(len(dur_pnl)), dur_pnl.values, color=colors, alpha=0.8)
    ax.set_xticks(range(len(dur_pnl)))
    ax.set_xticklabels(dur_pnl.index)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.set_title('P/L by Hold Duration (min)', fontsize=14)
    ax.set_ylabel('Total P/L ($)')
    ax.grid(True, alpha=0.3)
    
    # Daily performance
    ax = fig.add_subplot(gs[2, 2:])
    daily_pnl = df.groupby('date')['profit_loss'].sum()
    colors = [COLORS['profit'] if x >= 0 else COLORS['loss'] for x in daily_pnl.values]
    ax.bar(range(len(daily_pnl)), daily_pnl.values, color=colors, alpha=0.8)
    ax.axhline(y=0, color='white', linestyle='-', linewidth=1)
    ax.axhline(y=daily_pnl.mean(), color='yellow', linestyle='--', 
               label=f'Avg: ${daily_pnl.mean():.2f}')
    ax.set_title('Daily P/L', fontsize=14)
    ax.set_xlabel('Trading Day')
    ax.set_ylabel('P/L ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.savefig('plots/00_summary_dashboard.png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()


def main():
    """Main function to generate all plots."""
    print("=" * 60)
    print("   TRADE JOURNAL ANALYSIS & VISUALIZATION")
    print("=" * 60)
    
    # Create plots directory
    plots_dir = Path('plots')
    plots_dir.mkdir(exist_ok=True)
    print(f"\n📁 Plots will be saved to: {plots_dir.absolute()}")
    
    # Load data
    print("\n📂 Loading trade journal...")
    df = load_trade_journal()
    print(f"   ✓ Loaded {len(df):,} trades")
    print(f"   ✓ Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"   ✓ Unique tickers: {df['ticker'].nunique()}")
    
    # Generate all plots
    plots = [
        ("Summary Dashboard", generate_summary_dashboard),
        ("Cumulative P/L Analysis", plot_cumulative_pnl),
        ("Win Rate Analysis", plot_win_rate_analysis),
        ("P/L Distribution", plot_pnl_distribution),
        ("Time-Based Analysis", plot_time_analysis),
        ("Hold Duration Analysis", plot_hold_duration_analysis),
        ("Ticker Analysis", plot_ticker_analysis),
        ("Position Size Analysis", plot_position_size_analysis),
        ("Drawdown & Risk Analysis", plot_drawdown_analysis),
        ("LONG vs SHORT Comparison", plot_long_vs_short_analysis),
        ("Optimization Insights", plot_optimization_insights),
    ]
    
    print("\n🎨 Generating plots...")
    for name, func in plots:
        print(f"   → {name}...", end=" ", flush=True)
        try:
            func(df)
            print("✓")
        except Exception as e:
            print(f"✗ Error: {e}")
    
    print("\n" + "=" * 60)
    print("   ANALYSIS COMPLETE!")
    print("=" * 60)
    print(f"\n📊 Generated {len(plots)} plot files in '{plots_dir}/'")
    print("\nPlot files:")
    for f in sorted(plots_dir.glob('*.png')):
        print(f"   • {f.name}")
    
    # Print quick summary
    print("\n" + "─" * 60)
    print("QUICK STATS:")
    print("─" * 60)
    print(f"  Total P/L:        ${df['profit_loss'].sum():,.2f}")
    
    # Handle NaN values in is_winner for boolean filtering
    winners = df[df['is_winner'] == True]
    losers = df[df['is_winner'] == False]
    
    win_rate = len(winners) / len(df) * 100 if len(df) > 0 else 0
    avg_win = winners['profit_loss'].mean() if len(winners) > 0 else 0
    avg_loss = losers['profit_loss'].mean() if len(losers) > 0 else 0
    
    print(f"  Win Rate:         {win_rate:.1f}%")
    print(f"  Avg Win:          ${avg_win:.2f}")
    print(f"  Avg Loss:         ${avg_loss:.2f}")
    print(f"  Best Day:         ${df.groupby('date')['profit_loss'].sum().max():.2f}")
    print(f"  Worst Day:        ${df.groupby('date')['profit_loss'].sum().min():.2f}")
    print("─" * 60)


if __name__ == "__main__":
    main()
