# Godel Terminal CLI — Agent Handoff Document

## What This Project Is

A Playwright-based CLI and Python API for automating the [Godel Terminal](https://app.godelterminal.com/) — a browser-based financial terminal. The goal is to let AI agents execute terminal commands from a real terminal, extract structured data from the HTML, and pipe it back as JSON.

## Architecture

```
cli.py                  CLI entry point — all JSON to stdout, logs to godel_cli.log
godel_api.py            Async Python API wrapper (context manager, multi-session)
godel_core.py           Core framework:
                          GodelManager    — owns Playwright browser, spawns sessions
                          GodelSession    — one BrowserContext = one logged-in session
                          NetworkInterceptor — captures HTTP reqs/resps + WebSocket frames
                          BaseCommand     — abstract async command base class
db.py                   SQLite storage (aiosqlite) with abstract DatabaseBackend interface
commands/
  des_command.py        DES — company description, EPS, analyst ratings, snapshot
  most_command.py       MOST — most active stocks table → DataFrame
  prt_command.py        PRT — batch pattern analysis, CSV export
  probe_command.py      Network traffic capture for reverse-engineering the site
  chat_monitor.py       WebSocket interception → SQLite for chat messages
  res_command.py        RES — research PDF finder and downloader
  g_command.py          G — chart (placeholder, no data extraction yet)
  gip_command.py        GIP — intraday chart (placeholder)
  qm_command.py         QM — quote monitor (placeholder)
config.py               Credentials (gitignored) — copy from config-example.py
```

## How It Works

1. `GodelManager` launches a Chromium browser via Playwright.
2. `create_session()` creates a new `BrowserContext` (lightweight, isolated). Each session can run commands independently — this is how multi-instance works.
3. `GodelSession.login()` navigates to the app, fills email/password with `type()` (simulated keystrokes, not `fill()`, because the React app needs real input events), and submits via Enter key.
4. Commands use `session.send_command()` to type into `#terminal-input` and press Enter. They then poll for a new window element (`div[id$='-window']`) to appear, wait for the loading spinner to clear, and extract data from the DOM.
5. All CLI commands output structured JSON to stdout. Logs go to `godel_cli.log`.

## CLI Usage

```bash
python cli.py des AAPL                                  # company description
python cli.py most --tab GAINERS --limit 50             # most active stocks
python cli.py prt AAPL MSFT GOOGL -o results.csv        # pattern analysis
python cli.py probe --duration 30 --filter websocket    # capture network traffic
python cli.py chat --channels general --duration 60     # monitor chat → SQLite
python cli.py res AAPL --download-pdfs                  # download research PDFs
```

Global flags: `--headless`, `--layout <name>`, `--session-id <id>`, `--verbose`, `--url <url>`

## Critical Gotchas

### Headless mode is blocked — use --background instead
Godel Terminal detects headless Chrome and refuses to log in. The sign-in modal stays open and the auth silently fails. **Do not use `--headless`.**

Instead, use `--background` (or `-bg`). This launches a real headed browser but positions the window at coordinates (-10000, -10000) — far off-screen and completely invisible. The site can't distinguish it from a normal user, but you won't see any browser windows. **This is the recommended mode for agents.**

```bash
python cli.py --background des AAPL
python cli.py -bg most --tab ACTIVE --limit 25
```

### Login uses type(), not fill()
The React app uses controlled inputs. Playwright's `fill()` sets the DOM value but doesn't trigger React's synthetic events, so the internal state stays empty. Using `type(delay=30)` simulates real keystrokes and works. The form is submitted by pressing Enter on the password field (clicking the Login button was unreliable).

### Login success detection
The `#terminal-input` element exists on the page even when NOT logged in. Login success is detected by waiting for the "Sign In" modal (`h1.text-lg` with text "Sign In") to become hidden.

### Pre-existing windows
The default layout may have windows already open. Before running a command, `_get_session()` in `cli.py` snapshots all existing window IDs into `session._tracked_windows` so the window detection logic only finds genuinely new windows.

### Layout loading is non-fatal
`load_layout()` returns False (doesn't raise) if the layout name isn't found. The terminal continues with whatever layout is active.

### Window selectors
Windows are identified by: `div.resize.inline-block.absolute[id$='-window']`. Close buttons use fallback strategies: `span.anticon.anticon-close`, `svg[data-icon='close']`, `button[aria-label*='close']`.

## Database

SQLite via aiosqlite at `./godel.db`. Two tables:

- `chat_messages(id, channel, sender, content, timestamp, raw_data, created_at)`
- `pdf_downloads(id, ticker, command, filename, filepath, timestamp)`

The `DatabaseBackend` abstract class in `db.py` is designed so swapping to PostgreSQL means implementing one new class.

## WebSocket Endpoints Discovered

From probe command output:
- `wss://events.godelterminal.com/socket.io/?EIO=4&transport=websocket` — Socket.IO event stream
- `wss://api.godelterminal.com/events` — API event stream

These are the targets for chat monitoring. The `ChatMonitor` attaches to the `NetworkInterceptor` and processes incoming WebSocket frames, looking for JSON payloads with message-like structures. The exact chat message schema hasn't been fully mapped yet — run `python cli.py probe --duration 60 --filter websocket` while chat is active to capture frame payloads and refine the parsing heuristics in `ChatMonitor._extract_chat_message()`.

## HTTP API Discovered

- `GET https://app.godelterminal.com/api/fetchBreaking` — returns breaking news as JSON array with fields: `id`, `type`, `time`, `important`, `data.content`, `impact[].symbol`, `classification[].name`

## What's Left To Do

- **Chat monitoring**: The `ChatMonitor` frame parsing heuristics need tuning once we see actual chat WebSocket payloads. Run probe with chat open to capture them.
- **RES command**: The PDF link detection in `res_command.py` uses generic selectors. Needs testing against actual RES windows to refine the anchor/button selectors.
- **PRT command**: Ported but not yet tested with the new Playwright code. The original Selenium version worked.
- **Headless workaround**: Investigate Playwright stealth or using `channel: "chrome"` to bypass bot detection.
- **Trillion parsing**: Fixed in MOST — the `_parse_number` helper now handles T/B/M/K suffixes.
- **config-example.py**: Should be updated to match the current config.py structure.

## Dependencies

```
playwright>=1.40.0
aiosqlite>=0.19.0
pandas>=2.0.0
```

Playwright Chromium must be installed: `playwright install chromium`

Packages are installed to the conda environment at `/opt/anaconda3/bin/python`. The system Python at `/Library/Frameworks/Python.framework/` also has them but the workspace uses conda.

## File Locations

- Logs: `./godel_cli.log`
- Database: `./godel.db`
- Output files: `./output/`
- Screenshots on error: `./output/*.png`
- Config: `./config.py` (gitignored)
