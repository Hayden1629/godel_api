#!/usr/bin/env python3
"""
Godel Terminal CLI
All output is structured JSON to stdout (parseable by agents).
Logging goes to godel_cli.log.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — all human-readable logs go to file, NOT stdout
# ---------------------------------------------------------------------------

logger = logging.getLogger("godel")
LOG_FILE = Path(__file__).parent / "godel_cli.log"

def _setup_logging(verbose: bool = False):
    root = logging.getLogger("godel")
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # File handler (always)
    fh = logging.FileHandler(LOG_FILE, mode="a")
    fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s  %(message)s"))
    root.addHandler(fh)
    # Stderr handler only in verbose mode (never stdout)
    if verbose:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("%(levelname)s  %(message)s"))
        root.addHandler(sh)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_out(data: dict, output_file: str = None):
    """Write result dict as JSON to stdout (or file)."""
    text = json.dumps(data, indent=2, default=str)
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        Path(output_file).write_text(text)
    else:
        print(text)


async def _get_session(args):
    """Create manager + session, login, load layout, return (manager, session)."""
    from godel_core import GodelManager

    try:
        from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
    except ImportError:
        _json_out({"success": False, "error": "config.py not found. Copy config-example.py to config.py."})
        sys.exit(1)

    url = args.url if hasattr(args, "url") and args.url else GODEL_URL
    headless = getattr(args, "headless", False)
    background = getattr(args, "background", False)

    manager = GodelManager(headless=headless, background=background, url=url)
    await manager.start()

    session_id = getattr(args, "session_id", "default") or "default"
    session = await manager.create_session(session_id)
    await session.init_page()
    await session.login(GODEL_USERNAME, GODEL_PASSWORD)

    layout = getattr(args, "layout", "dev") or "dev"
    await session.load_layout(layout)

    # Snapshot existing windows so commands can detect new ones
    existing = await session.get_current_windows()
    for w in existing:
        wid = await w.get_attribute("id")
        if wid:
            session._tracked_windows.add(wid)
    logger.info(f"Pre-existing windows: {len(existing)}")

    return manager, session


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_des(args):
    manager, session = await _get_session(args)
    try:
        from commands import DESCommand
        cmd = DESCommand(session)
        result = await cmd.execute(args.ticker, args.asset_class)
        _json_out(result, args.output)
    finally:
        await manager.shutdown()


async def cmd_prt(args):
    manager, session = await _get_session(args)
    try:
        from commands import PRTCommand
        cmd = PRTCommand(session, tickers=args.tickers)
        result = await cmd.execute()
        # Save CSV/JSON if requested
        if args.output and cmd.df is not None:
            if args.output.endswith(".csv"):
                cmd.save_to_csv(args.output)
            elif args.output.endswith(".json"):
                cmd.save_to_json(args.output)
            else:
                cmd.save_to_csv(args.output + ".csv")
            result["saved_to"] = args.output
        _json_out(result, None)  # always print result to stdout
    finally:
        await manager.shutdown()


async def cmd_most(args):
    manager, session = await _get_session(args)
    try:
        from commands import MOSTCommand
        cmd = MOSTCommand(session, tab=args.tab, limit=args.limit)
        result = await cmd.execute()
        if args.output and cmd.df is not None:
            if args.output.endswith(".csv"):
                cmd.save_to_csv(args.output)
            elif args.output.endswith(".json"):
                cmd.save_to_json(args.output)
            else:
                cmd.save_to_csv(args.output + ".csv")
            result["saved_to"] = args.output
        _json_out(result, None)
    finally:
        await manager.shutdown()


async def cmd_res(args):
    manager, session = await _get_session(args)
    try:
        from commands import RESCommand
        cmd = RESCommand(session, download_pdfs=args.download_pdfs,
                         output_dir=args.pdf_dir)
        result = await cmd.execute(args.ticker, args.asset_class)
        _json_out(result, args.output)
    finally:
        await manager.shutdown()


async def cmd_probe(args):
    manager, session = await _get_session(args)
    try:
        from commands import ProbeCommand
        cmd = ProbeCommand(session, duration=args.duration,
                           filter_type=args.filter, url_filter=args.url_filter)
        result = await cmd.execute_and_save(args.output)
        _json_out(result)
    finally:
        await manager.shutdown()


async def cmd_chat(args):
    manager, session = await _get_session(args)
    try:
        from commands import ChatMonitor
        channels = args.channels.split(",") if args.channels else None
        monitor = ChatMonitor(session, channels=channels)
        await monitor.start(duration=args.duration)
        _json_out({
            "success": True,
            "messages_captured": monitor.message_count,
            "duration": args.duration,
            "channels": channels,
        })
    finally:
        from db import close_db
        await close_db()
        await manager.shutdown()


async def cmd_g(args):
    manager, session = await _get_session(args)
    try:
        from commands import GCommand
        cmd = GCommand(session)
        result = await cmd.execute(args.ticker, args.asset_class)
        _json_out(result, args.output)
    finally:
        await manager.shutdown()


async def cmd_gip(args):
    manager, session = await _get_session(args)
    try:
        from commands import GIPCommand
        cmd = GIPCommand(session)
        result = await cmd.execute(args.ticker, args.asset_class)
        _json_out(result, args.output)
    finally:
        await manager.shutdown()


async def cmd_qm(args):
    manager, session = await _get_session(args)
    try:
        from commands import QMCommand
        cmd = QMCommand(session)
        result = await cmd.execute(args.ticker, args.asset_class)
        _json_out(result, args.output)
    finally:
        await manager.shutdown()


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Godel Terminal CLI — structured JSON output for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py des AAPL
  python cli.py most --tab GAINERS --limit 50 -o gainers.json
  python cli.py prt AAPL MSFT GOOGL -o results.csv
  python cli.py probe --duration 30 --filter websocket
  python cli.py chat --channels general,trading --duration 60
  python cli.py res AAPL --download-pdfs
        """,
    )

    # Global flags
    parser.add_argument("--headless", action="store_true", help="Run browser headless (may be blocked by site)")
    parser.add_argument("--background", "-bg", action="store_true",
                        help="Run browser off-screen (invisible but bypasses bot detection — recommended for agents)")
    parser.add_argument("--url", default=None, help="Godel Terminal URL override")
    parser.add_argument("--layout", default="dev", help="Layout name (default: dev)")
    parser.add_argument("--session-id", default="default", help="Session identifier (for multi-instance)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging to stderr")

    sub = parser.add_subparsers(dest="command", help="Command to execute")

    # -- DES ----------------------------------------------------------------
    p = sub.add_parser("des", help="Company description")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--asset-class", default="EQ")
    p.add_argument("-o", "--output", help="Output JSON file")

    # -- PRT ----------------------------------------------------------------
    p = sub.add_parser("prt", help="Pattern Real-Time batch analysis")
    p.add_argument("tickers", nargs="+", help="Ticker symbols")
    p.add_argument("-o", "--output", help="Output CSV/JSON file")

    # -- MOST ---------------------------------------------------------------
    p = sub.add_parser("most", help="Most active stocks")
    p.add_argument("--tab", choices=["ACTIVE", "GAINERS", "LOSERS", "VALUE"], default="ACTIVE")
    p.add_argument("--limit", type=int, choices=[10, 25, 50, 75, 100], default=75)
    p.add_argument("-o", "--output", help="Output CSV/JSON file")

    # -- RES ----------------------------------------------------------------
    p = sub.add_parser("res", help="Research / PDF downloads")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--asset-class", default="EQ")
    p.add_argument("--download-pdfs", action="store_true", default=True)
    p.add_argument("--no-download", dest="download_pdfs", action="store_false")
    p.add_argument("--pdf-dir", default="output/pdfs", help="PDF download directory")
    p.add_argument("-o", "--output", help="Output JSON file")

    # -- PROBE --------------------------------------------------------------
    p = sub.add_parser("probe", help="Capture network traffic for reverse-engineering")
    p.add_argument("--duration", type=int, default=30, help="Seconds to capture (default 30)")
    p.add_argument("--filter", choices=["http", "websocket"], default=None, help="Traffic type filter")
    p.add_argument("--url-filter", default=None, help="Only capture URLs containing this string")
    p.add_argument("-o", "--output", help="Output JSON file")

    # -- CHAT ---------------------------------------------------------------
    p = sub.add_parser("chat", help="Monitor chat channels")
    p.add_argument("--channels", default=None, help="Comma-separated channel names")
    p.add_argument("--duration", type=int, default=60, help="Seconds to monitor (default 60)")

    # -- G ------------------------------------------------------------------
    p = sub.add_parser("g", help="Price chart")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--asset-class", default="EQ")
    p.add_argument("-o", "--output", help="Output JSON file")

    # -- GIP ----------------------------------------------------------------
    p = sub.add_parser("gip", help="Intraday chart")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--asset-class", default="EQ")
    p.add_argument("-o", "--output", help="Output JSON file")

    # -- QM -----------------------------------------------------------------
    p = sub.add_parser("qm", help="Quote monitor")
    p.add_argument("ticker", help="Ticker symbol")
    p.add_argument("--asset-class", default="EQ")
    p.add_argument("-o", "--output", help="Output JSON file")

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

DISPATCH = {
    "des": cmd_des,
    "prt": cmd_prt,
    "most": cmd_most,
    "res": cmd_res,
    "probe": cmd_probe,
    "chat": cmd_chat,
    "g": cmd_g,
    "gip": cmd_gip,
    "qm": cmd_qm,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    _setup_logging(verbose=getattr(args, "verbose", False))

    handler = DISPATCH.get(args.command)
    if not handler:
        _json_out({"success": False, "error": f"Unknown command: {args.command}"})
        sys.exit(1)

    try:
        asyncio.run(handler(args))
    except KeyboardInterrupt:
        _json_out({"success": False, "error": "Interrupted"})
        sys.exit(130)
    except Exception as e:
        logging.getLogger("godel").error(f"Fatal: {e}", exc_info=True)
        _json_out({"success": False, "error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
