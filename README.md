# Godel Terminal CLI

Playwright-based CLI and Python API for automating the [Godel Terminal](https://app.godelterminal.com/). Execute terminal commands from your shell, extract structured data from the HTML, and get JSON back. Built for AI agents.

## Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

Copy `config-example.py` to `config.py` and add your Godel Terminal credentials:

```bash
cp config-example.py config.py
```

## CLI Usage

All commands output structured JSON to stdout. Use `--background` (or `-bg`) to run the browser invisibly.

```bash
# Company description
python cli.py -bg des AAPL

# Most active stocks
python cli.py -bg most --tab GAINERS --limit 50

# Batch pattern analysis
python cli.py -bg prt AAPL MSFT GOOGL -o results.csv

# Network traffic capture (reverse-engineering)
python cli.py -bg probe --duration 30 --filter websocket

# Monitor chat channels → SQLite
python cli.py -bg chat --channels general,trading --duration 60

# Download research PDFs
python cli.py -bg res AAPL --download-pdfs

# Save output to file
python cli.py -bg des AAPL -o output/aapl.json
```

Run `python cli.py --help` for full options.

### Global Flags

| Flag | Description |
|------|-------------|
| `--background`, `-bg` | Run browser off-screen (recommended for agents) |
| `--headless` | Headless mode (blocked by Godel — use `-bg` instead) |
| `--layout NAME` | Load a named layout (default: dev) |
| `--session-id ID` | Session identifier for multi-instance |
| `--verbose`, `-v` | Verbose logging to stderr |
| `-o FILE` | Save output to file |

## Available Commands

### DES — Company Description

Extracts company info, description, EPS estimates, analyst ratings, and financial snapshot.

```bash
python cli.py -bg des AAPL
python cli.py -bg des MSFT --asset-class EQ -o msft.json
```

Returns: `company_info`, `description`, `eps_estimates`, `analyst_ratings`, `snapshot`

### MOST — Most Active Stocks

Extracts the most active stocks table into structured records.

```bash
python cli.py -bg most --tab ACTIVE --limit 75
python cli.py -bg most --tab LOSERS --limit 25 -o losers.json
```

Tabs: `ACTIVE`, `GAINERS`, `LOSERS`, `VALUE`. Limits: 10, 25, 50, 75, 100.

### PRT — Pattern Real-Time

Batch pattern analysis on multiple tickers with CSV export.

```bash
python cli.py -bg prt AAPL MSFT GOOGL NVDA -o results.csv
```

### PROBE — Network Traffic Capture

Captures HTTP requests/responses and WebSocket frames. Use this to reverse-engineer how the site communicates.

```bash
python cli.py -bg probe --duration 30                    # capture everything
python cli.py -bg probe --duration 60 --filter websocket # WebSocket only
python cli.py -bg probe --duration 30 --url-filter chat  # filter by URL
```

### CHAT — Chat Monitor

Monitors chat channels via WebSocket interception and stores messages in SQLite.

```bash
python cli.py -bg chat --channels general,trading --duration 120
```

### RES — Research PDF Downloads

Opens the RES window for a ticker and downloads available PDFs.

```bash
python cli.py -bg res AAPL --download-pdfs --pdf-dir output/pdfs
```

### G, GIP, QM — Chart, Intraday Chart, Quote Monitor

Open windows (data extraction placeholders).

```bash
python cli.py -bg g AAPL
python cli.py -bg gip AAPL
python cli.py -bg qm AAPL
```

## Python API

```python
import asyncio
from godel_api import GodelAPI

async def main():
    async with GodelAPI() as api:
        result = await api.des("AAPL")
        print(result["data"]["company_info"]["company_name"])

        result = await api.most(tab="GAINERS", limit=25)
        print(result["data"]["tickers"])

asyncio.run(main())
```

Multi-session (concurrent instances):

```python
async with GodelAPI() as api:
    session2 = await api.add_session("second", layout="dev")
    result1 = await api.des("AAPL")                        # default session
    result2 = await api.des("MSFT", session_id="second")   # second session
```

## Architecture

```
cli.py                  CLI entry point (JSON to stdout, logs to godel_cli.log)
godel_api.py            Async Python API (context manager, multi-session)
godel_core.py           GodelManager, GodelSession, NetworkInterceptor, BaseCommand
db.py                   SQLite storage with abstract DatabaseBackend interface
commands/
  des_command.py        DES — company description extraction
  most_command.py       MOST — active stocks table → DataFrame
  prt_command.py        PRT — batch analysis, CSV export
  probe_command.py      Network traffic capture
  chat_monitor.py       WebSocket chat → SQLite
  res_command.py        RES — PDF downloads
  g_command.py          G — chart (placeholder)
  gip_command.py        GIP — intraday chart (placeholder)
  qm_command.py         QM — quote monitor (placeholder)
config.py               Credentials (gitignored)
```

## Error Handling

All commands return a dict with `success` (bool), `error` (str if failed), `command`, and `data`. Always check `result["success"]` before accessing `result["data"]`.

On extraction failure, a screenshot is saved to `output/` for debugging.

## Notes

- The `--background` flag positions the browser off-screen — invisible but undetectable by the site
- `--headless` is blocked by Godel's bot detection — do not use it
- All logging goes to `godel_cli.log`, never to stdout (stdout is reserved for JSON output)
- The database is at `./godel.db` (SQLite, will migrate to remote SQL later)
