"""
Demo: How to process PRT CSV results
Run this after you get a CSV file from the PRT command
"""

import json
from pathlib import Path
from prt_data_processor import PRTDataProcessor


def demo_basic_processing():
    """Demo 1: Basic CSV processing"""
    print("=" * 60)
    print("DEMO 1: Basic CSV Processing")
    print("=" * 60)
    
    # Point to your actual CSV file
    csv_file = "prt_results (3).csv"
    
    if not Path(csv_file).exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        print("   Update the path to your actual PRT results CSV")
        return
    
    # Create processor
    processor = PRTDataProcessor(csv_path=csv_file)
    
    # Get summary
    stats = processor.get_summary_stats()
    print(f"\n📊 Summary:")
    print(f"   Total symbols: {stats['total_symbols']}")
    print(f"   Long signals: {stats['long_count']}")
    print(f"   Short signals: {stats['short_count']}")
    print(f"   Average edge: {stats['avg_edge']:.6f}")
    print(f"   Average prob up: {stats['avg_prob_up']:.2%}")
    
    # Get top opportunities
    print(f"\n🎯 Top Long Opportunities:")
    for i, trade in enumerate(processor.get_top_long_opportunities(3), 1):
        print(f"   {i}. {trade['symbol']}")
        print(f"      Edge: {trade['edge']:.6f}")
        print(f"      Probability: {trade['prob_up']:.2%}")
        print(f"      Expected return: {trade['mean']:.4f}")
    
    print(f"\n📉 Top Short Opportunities:")
    for i, trade in enumerate(processor.get_top_short_opportunities(3), 1):
        print(f"   {i}. {trade['symbol']}")
        print(f"      Edge: {trade['edge']:.6f}")
        print(f"      Probability: {(1-trade['prob_up']):.2%}")
        print(f"      Expected return: {-trade['mean']:.4f}")


def demo_export_formats():
    """Demo 2: Different export formats"""
    print("\n" + "=" * 60)
    print("DEMO 2: Export Formats")
    print("=" * 60)
    
    csv_file = "prt_results (3).csv"
    if not Path(csv_file).exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return
    
    processor = PRTDataProcessor(csv_path=csv_file)
    
    # Standard API format
    print("\n📤 Standard API Format:")
    api_data = processor.export_for_api('standard')
    print(json.dumps(api_data['metadata'], indent=2))
    print(f"   Signals: {len(api_data['signals'])} entries")
    
    # Compact format
    print("\n📦 Compact Format (good for lightweight APIs):")
    compact = processor.export_for_api('compact')
    print(f"   Symbols: {compact['symbols']}")
    print(f"   Directions: {compact['directions']}")
    
    # Trading signals format
    print("\n🔔 Trading Signals Format:")
    signals = processor.to_trading_signals()
    if signals:
        sample = signals[0]
        print(f"   Sample signal:")
        print(json.dumps(sample, indent=4))


def demo_filtering():
    """Demo 3: Filtering and analysis"""
    print("\n" + "=" * 60)
    print("DEMO 3: Filtering & Analysis")
    print("=" * 60)
    
    csv_file = "prt_results (3).csv"
    if not Path(csv_file).exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return
    
    processor = PRTDataProcessor(csv_path=csv_file)
    
    # Filter by probability
    print("\n🎲 High Probability Trades (>50%):")
    high_prob = processor.filter_by_probability(0.5)
    for _, trade in high_prob.iterrows():
        print(f"   {trade['symbol']}: {trade['direction']} (prob={trade['prob_up']:.2%})")
    
    # Custom filtering with pandas
    print("\n💎 High Edge Trades (edge > 0.0001):")
    high_edge = processor.df[processor.df['edge'] > 0.0001]
    for _, trade in high_edge.iterrows():
        print(f"   {trade['symbol']}: {trade['direction']} (edge={trade['edge']:.6f})")


def demo_integration_examples():
    """Demo 4: Integration with other systems"""
    print("\n" + "=" * 60)
    print("DEMO 4: Integration Examples")
    print("=" * 60)
    
    csv_file = "prt_results (3).csv"
    if not Path(csv_file).exists():
        print(f"⚠️  CSV file not found: {csv_file}")
        return
    
    processor = PRTDataProcessor(csv_path=csv_file)
    
    print("\n🔌 Integration Options:")
    print("\n1. Save to JSON file (for other Python programs):")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    json_file = output_dir / "prt_processed.json"
    processor.save_processed(str(json_file), format='json')
    print(f"   ✓ Saved to: {json_file}")
    
    print("\n2. Send to webhook (uncomment to use):")
    print("   # from prt_data_processor import send_to_webhook")
    print("   # data = processor.export_for_api('standard')")
    print("   # send_to_webhook(data, 'https://your-webhook-url.com/endpoint')")
    
    print("\n3. Save to database (uncomment to use):")
    print("   # from prt_data_processor import send_to_database")
    print("   # signals = processor.to_trading_signals()")
    print("   # send_to_database(signals, {'path': 'trading_signals.db'})")
    
    print("\n4. Use in another Python script:")
    print("   # from prt_data_processor import PRTDataProcessor")
    print("   # processor = PRTDataProcessor(csv_path='your_file.csv')")
    print("   # signals = processor.to_trading_signals()")
    print("   # for signal in signals:")
    print("   #     your_trading_function(signal)")


def main():
    """Run all demos"""
    demo_basic_processing()
    demo_export_formats()
    demo_filtering()
    demo_integration_examples()
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run your PRT command to get a CSV file")
    print("2. The CSV path will be in result['csv_file']")
    print("3. Use process_prt_csv() in main.py to process it")
    print("4. Use PRTDataProcessor for advanced analysis")


if __name__ == "__main__":
    main()

