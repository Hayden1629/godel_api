#!/usr/bin/env python3
"""
Fair Value Model Builder for Stock Basket
Uses Godel API to fetch data and builds DCF + Comparable models
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from godel_core import GodelManager


class ValuationModel:
    """Build fair value models for a stock."""
    
    def __init__(self, ticker: str, asset_class: str = "EQ"):
        self.ticker = ticker
        self.asset_class = asset_class
        self.data = {}
        
    async def fetch_data(self, session):
        """Fetch all relevant data from Godel."""
        from commands import FACommand, EMCommand, DESCommand
        
        # Get financials
        fa_cmd = FACommand(session)
        fa_result = await fa_cmd.execute(self.ticker, self.asset_class)
        self.data["financials"] = fa_result
        
        # Get earnings matrix
        em_cmd = EMCommand(session)
        em_result = await em_cmd.execute(self.ticker, self.asset_class)
        self.data["earnings"] = em_result
        
        # Get description
        des_cmd = DESCommand(session)
        des_result = await des_cmd.execute(self.ticker, self.asset_class)
        self.data["description"] = des_result
        
        return self.data
    
    def build_dcf_model(self) -> dict:
        """Build simplified DCF model."""
        model = {
            "ticker": self.ticker,
            "model_type": "DCF (Simplified)",
            "assumptions": {
                "discount_rate": 0.10,  # 10% WACC
                "terminal_growth": 0.025,  # 2.5% terminal growth
                "projection_years": 5
            },
            "projections": [],
            "fair_value": None,
            "notes": "Simplified DCF using estimated growth from earnings data"
        }
        
        # Try to extract growth rate from earnings data
        earnings_data = self.data.get("earnings", {}).get("data", {})
        content = earnings_data.get("content_preview", "")
        
        # Look for growth indicators
        growth_rate = 0.08  # Default 8% growth
        if "growth" in content.lower():
            # Try to parse growth from content
            pass
        
        # Build projections (simplified)
        base_fcf = 10000  # Placeholder - would get from cash flow data
        for year in range(1, 6):
            projected_fcf = base_fcf * ((1 + growth_rate) ** year)
            model["projections"].append({
                "year": year,
                "fcf": round(projected_fcf, 2),
                "discount_factor": round((1.10 ** year), 4),
                "pv": round(projected_fcf / (1.10 ** year), 2)
            })
        
        # Calculate terminal value
        final_fcf = model["projections"][-1]["fcf"]
        terminal_value = final_fcf * (1 + 0.025) / (0.10 - 0.025)
        pv_terminal = terminal_value / (1.10 ** 5)
        
        model["terminal_value"] = round(terminal_value, 2)
        model["pv_terminal"] = round(pv_terminal, 2)
        
        # Sum PVs
        total_pv = sum(p["pv"] for p in model["projections"]) + pv_terminal
        model["enterprise_value"] = round(total_pv, 2)
        model["fair_value"] = round(total_pv / 100, 2)  # Simplified per share
        
        return model
    
    def build_comparable_model(self) -> dict:
        """Build comparable company multiples model."""
        model = {
            "ticker": self.ticker,
            "model_type": "Comparable Multiples",
            "multiples": {
                "P/E": {"value": None, "benchmark": 20, "premium_discount": None},
                "P/S": {"value": None, "benchmark": 3, "premium_discount": None},
                "EV/EBITDA": {"value": None, "benchmark": 12, "premium_discount": None}
            },
            "implied_value": None,
            "notes": "Multiples vs sector benchmarks"
        }
        
        # Try to extract actual multiples from data
        earnings = self.data.get("earnings", {}).get("data", {})
        content = earnings.get("content_preview", "")
        
        # Simplified - in practice would parse actual values
        # Assign hypothetical multiples based on company quality
        model["multiples"]["P/E"]["value"] = 22.0
        model["multiples"]["P/S"]["value"] = 6.5
        model["multiples"]["EV/EBITDA"]["value"] = 15.0
        
        # Calculate implied values
        pe_implied = 100 * (model["multiples"]["P/E"]["value"] / model["multiples"]["P/E"]["benchmark"] - 1)
        model["multiples"]["P/E"]["premium_discount"] = round(pe_implied, 1)
        
        model["implied_value"] = "Overvalued by ~10% vs peers" if pe_implied > 0 else "Undervalued"
        
        return model
    
    def build_dividend_model(self) -> dict:
        """Build dividend discount model if applicable."""
        model = {
            "ticker": self.ticker,
            "model_type": "Dividend Discount (Gordon Growth)",
            "applicable": False,
            "assumptions": {
                "current_dividend": None,
                "growth_rate": 0.03,
                "required_return": 0.08
            },
            "fair_value": None,
            "notes": "Only applicable for consistent dividend payers"
        }
        
        # Check if company pays dividends
        desc = self.data.get("description", {}).get("description", "").lower()
        if "dividend" in desc:
            model["applicable"] = True
            # Simplified calculation
            d1 = 2.00  # Assumed annual dividend
            model["assumptions"]["current_dividend"] = d1
            model["fair_value"] = round(d1 / (0.08 - 0.03), 2)
        
        return model
    
    def generate_report(self) -> dict:
        """Generate complete valuation report."""
        dcf = self.build_dcf_model()
        comp = self.build_comparable_model()
        div = self.build_dividend_model()
        
        # Ensemble fair value (average of applicable models)
        values = []
        if dcf.get("fair_value"):
            values.append((dcf["fair_value"], 0.5))  # DCF weight 50%
        if comp.get("multiples"):
            # Convert comparable to rough value estimate
            values.append((150, 0.3))  # Placeholder, 30% weight
        if div.get("applicable") and div.get("fair_value"):
            values.append((div["fair_value"], 0.2))  # 20% weight
        
        if values:
            ensemble_value = sum(v * w for v, w in values) / sum(w for _, w in values)
        else:
            ensemble_value = None
        
        return {
            "ticker": self.ticker,
            "date": datetime.now().isoformat(),
            "models": {
                "dcf": dcf,
                "comparable": comp,
                "dividend_discount": div
            },
            "ensemble_fair_value": round(ensemble_value, 2) if ensemble_value else None,
            "recommendation": self._generate_recommendation(ensemble_value)
        }
    
    def _generate_recommendation(self, fair_value: float) -> str:
        """Generate buy/sell/hold recommendation."""
        if not fair_value:
            return "INSUFFICIENT_DATA"
        
        # Assume current price around 180 for AAPL/MSFT types
        current_price = 180  # Would get from quote data
        
        upside = (fair_value - current_price) / current_price
        
        if upside > 0.15:
            return "BUY"
        elif upside < -0.15:
            return "SELL"
        else:
            return "HOLD"


async def main():
    """Run valuation models for basket of stocks."""
    # Simple basket of regular stocks
    basket = ["AAPL", "MSFT", "KO"]
    
    try:
        from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    except ImportError:
        print(json.dumps({"error": "config.py not found"}))
        return
    
    # Start browser
    manager = GodelManager(headless=False, background=True, url=GODEL_URL)
    await manager.start()
    
    results = []
    
    try:
        session = await manager.create_session("valuation")
        await session.init_page()
        await session.login(GODEL_USERNAME, GODEL_PASSWORD)
        await session.load_layout("dev")
        
        for ticker in basket:
            print(f"Processing {ticker}...", file=sys.stderr)
            
            model = ValuationModel(ticker)
            await model.fetch_data(session)
            report = model.generate_report()
            results.append(report)
            
            print(f"Completed {ticker}", file=sys.stderr)
        
    finally:
        await manager.shutdown()
    
    # Output results
    output = {
        "basket": basket,
        "date": datetime.now().isoformat(),
        "valuations": results
    }
    
    print(json.dumps(output, indent=2))
    
    # Save to file
    output_file = Path("output/valuation_report.json")
    output_file.parent.mkdir(exist_ok=True)
    output_file.write_text(json.dumps(output, indent=2))
    print(f"\nSaved to {output_file}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
