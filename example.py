#!/usr/bin/env python3
"""
Example usage of Godel Terminal API
"""

from godel_api import GodelAPI

# Example 1: Using context manager (recommended)
print("Example 1: DES command with context manager")
with GodelAPI() as api:
    result = api.des("AAPL", "EQ")
    if result['success']:
        data = result['data']
        print(f"Company: {data['company_info']['company_name']}")
        print(f"Description length: {len(data.get('description', '') or '')} characters")
        print(f"Analyst ratings: {len(data.get('analyst_ratings', []))} ratings")
    else:
        print(f"Error: {result.get('error')}")

print("\n" + "="*50 + "\n")

# Example 2: Manual connection management
print("Example 2: MOST command with manual connection")
api = GodelAPI()
if api.connect():
    result = api.most(tab="ACTIVE", limit=25, output_path="most_active_example.csv")
    if result['success']:
        data = result['data']
        print(f"Extracted {data['row_count']} rows")
        print(f"Tickers: {', '.join(data['tickers'][:10])}")
    api.disconnect()

print("\n" + "="*50 + "\n")

# Example 3: PRT command
print("Example 3: PRT command")
with GodelAPI() as api:
    result = api.prt(["AAPL", "MSFT"], output_path="prt_example.csv")
    if result['success']:
        print(f"CSV file: {result.get('csv_file', 'N/A')}")
        print(f"Progress: {result['data'].get('progress', {})}")
    else:
        print(f"Error: {result.get('error')}")
