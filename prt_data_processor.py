"""
PRT Data Processor Utilities
Examples of how to use the processed PRT CSV data
"""

import json
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path


class PRTDataProcessor:
    """Process and analyze PRT results data"""
    
    def __init__(self, csv_path: str = None, json_data: List[Dict] = None):
        """
        Initialize with either a CSV file path or JSON data
        
        Args:
            csv_path: Path to PRT results CSV file
            json_data: Pre-loaded JSON data (list of dicts)
        """
        if csv_path:
            self.df = pd.read_csv(csv_path)
        elif json_data:
            self.df = pd.DataFrame(json_data)
        else:
            raise ValueError("Must provide either csv_path or json_data")
    
    def get_top_long_opportunities(self, n: int = 5) -> List[Dict]:
        """Get top N long opportunities based on edge"""
        long_trades = self.df[self.df['direction'] == 'LONG'].copy()
        long_trades = long_trades.sort_values('edge', ascending=False)
        return long_trades.head(n).to_dict('records')
    
    def get_top_short_opportunities(self, n: int = 5) -> List[Dict]:
        """Get top N short opportunities based on edge"""
        short_trades = self.df[self.df['direction'] == 'SHORT'].copy()
        short_trades = short_trades.sort_values('edge', ascending=False)
        return short_trades.head(n).to_dict('records')
    
    def filter_by_probability(self, min_prob: float = 0.5) -> pd.DataFrame:
        """Filter trades by minimum probability of success"""
        return self.df[self.df['prob_up'] >= min_prob]
    
    def get_summary_stats(self) -> Dict:
        """Calculate summary statistics"""
        return {
            'total_symbols': len(self.df),
            'long_count': len(self.df[self.df['direction'] == 'LONG']),
            'short_count': len(self.df[self.df['direction'] == 'SHORT']),
            'avg_edge': self.df['edge'].mean(),
            'avg_prob_up': self.df['prob_up'].mean(),
            'symbols': self.df['symbol'].tolist()
        }
    
    def to_trading_signals(self) -> List[Dict]:
        """
        Convert to simplified trading signals format
        Useful for sending to trading systems or APIs
        """
        signals = []
        for _, row in self.df.iterrows():
            signals.append({
                'symbol': row['symbol'],
                'action': 'BUY' if row['direction'] == 'LONG' else 'SELL',
                'signal_strength': abs(row['edge']),
                'probability': row['prob_up'] if row['direction'] == 'LONG' else (1 - row['prob_up']),
                'timestamp': row['timestamp'],
                'metadata': {
                    'dist1': row['dist1'],
                    'n': row['n'],
                    'mean': row['mean'],
                    'p10': row['p10'],
                    'p90': row['p90']
                }
            })
        return signals
    
    def export_for_api(self, api_format: str = 'standard') -> Dict:
        """
        Export data in various API-ready formats
        
        Args:
            api_format: 'standard', 'compact', or 'detailed'
        """
        if api_format == 'standard':
            return {
                'metadata': {
                    'source': 'PRT',
                    'total_signals': len(self.df),
                    'timestamp': self.df['timestamp'].iloc[0] if len(self.df) > 0 else None
                },
                'signals': self.to_trading_signals()
            }
        
        elif api_format == 'compact':
            return {
                'symbols': self.df['symbol'].tolist(),
                'directions': self.df['direction'].tolist(),
                'edges': self.df['edge'].tolist(),
                'probabilities': self.df['prob_up'].tolist()
            }
        
        elif api_format == 'detailed':
            return {
                'metadata': self.get_summary_stats(),
                'full_data': self.df.to_dict('records'),
                'top_opportunities': {
                    'long': self.get_top_long_opportunities(3),
                    'short': self.get_top_short_opportunities(3)
                }
            }
        
        else:
            raise ValueError(f"Unknown format: {api_format}")
    
    def save_processed(self, output_path: str, format: str = 'json'):
        """Save processed data to file"""
        path = Path(output_path)
        
        if format == 'json':
            with open(path, 'w') as f:
                json.dump(self.export_for_api('detailed'), f, indent=2)
        elif format == 'csv':
            self.df.to_csv(path, index=False)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        print(f"Saved to: {path}")


def example_usage():
    """Example of how to use the PRTDataProcessor"""
    
    # Example 1: Load from CSV
    csv_path = "prt_results (3).csv"
    processor = PRTDataProcessor(csv_path=csv_path)
    
    # Get summary stats
    stats = processor.get_summary_stats()
    print("\n📊 Summary Statistics:")
    print(json.dumps(stats, indent=2))
    
    # Get top opportunities
    print("\n🚀 Top 3 Long Opportunities:")
    for trade in processor.get_top_long_opportunities(3):
        print(f"  {trade['symbol']}: Edge={trade['edge']:.6f}, Prob={trade['prob_up']:.2f}")
    
    print("\n📉 Top 3 Short Opportunities:")
    for trade in processor.get_top_short_opportunities(3):
        print(f"  {trade['symbol']}: Edge={trade['edge']:.6f}, Prob={1-trade['prob_up']:.2f}")
    
    # Export for API
    api_data = processor.export_for_api('standard')
    print(f"\n🌐 API-ready data with {len(api_data['signals'])} signals")
    
    # Save processed data
    processor.save_processed('processed_prt_results.json', format='json')


def send_to_webhook(data: Dict, webhook_url: str):
    """
    Example function to send processed data to a webhook
    
    Args:
        data: Processed PRT data
        webhook_url: URL of the webhook endpoint
    """
    import requests
    
    try:
        response = requests.post(
            webhook_url,
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        print(f"✓ Data sent to webhook: {webhook_url}")
        return response.json()
    except Exception as e:
        print(f"✗ Error sending to webhook: {e}")
        return None


def send_to_database(data: List[Dict], db_config: Dict):
    """
    Example function to send data to a database
    
    Args:
        data: List of trading signals
        db_config: Database connection configuration
    """
    # Example for SQLite
    import sqlite3
    
    conn = sqlite3.connect(db_config.get('path', 'prt_results.db'))
    df = pd.DataFrame(data)
    
    # Save to database
    df.to_sql('trading_signals', conn, if_exists='append', index=False)
    
    print(f"✓ Saved {len(data)} records to database")
    conn.close()


if __name__ == "__main__":
    example_usage()

