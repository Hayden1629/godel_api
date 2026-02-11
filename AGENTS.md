# Godel Terminal CLI — Agent Handoff Document

## Project Goal

Build a command-line interface for [Godel Terminal](https://app.godelterminal.com/) so that AI agents can interface with financial data. The user inputs commands from their terminal (or an agent does it), information is extracted from the HTML components, and structured JSON is relayed back to the terminal.

The Godel Terminal is a browser-based financial terminal with a keyboard-first CLI design. You open the command bar with the backtick key, type a command like `DES AAPL`, and a window opens with data. This project automates that entire flow with Playwright and extracts the data from the DOM.

## Specific Goals (from the user)

1. **Multi-instance support** — Run multiple Godel sessions simultaneously. Done via Playwright BrowserContexts (each context is an isolated session sharing one browser process).

2. **Agent-testable infrastructure** — The agent (you) must be able to run commands and read results to iterate on features. The CLI outputs JSON to stdout, logs go to `godel_cli.log`, and screenshots are saved on failure. Use `--background` mode to run invisibly.

3. **CLI-compatible everything** — Every feature must be accessible from the command line. No feature should only be available via the Python API.

4. **Chat logging to SQL** — Monitor chat messages from multiple channels and store them in a SQL database. Currently SQLite (`godel.db`), will migrate to a remote SQL database later. The `ChatMonitor` uses WebSocket interception to capture messages. The parsing heuristics need refinement once actual chat frame payloads are captured.

5. **PDF downloads from RES** — Automate downloading research PDFs from the RES component. The `RESCommand` opens the RES window, finds PDF links/buttons, and uses Playwright's download API. Records are stored in the `pdf_downloads` table.

6. **Technical figures from DES** — Extract company description, EPS estimates, analyst ratings, and financial snapshot from the DES component. This is fully working and tested.

7. **Network interception for chat** — Instead of polling the DOM for chat updates, intercept WebSocket frames directly. The `NetworkInterceptor` class captures all HTTP and WebSocket traffic. The `probe` command lets you record and analyze traffic to understand how the site communicates.

8. **Reverse-engineer the site** — Use the probe tool to capture all network traffic and understand how the site works under the hood. Two WebSocket endpoints and one HTTP API have been discovered so far.

9. **Database will move to remote SQL** — The `DatabaseBackend` abstract class in `db.py` is designed so that swapping SQLite for PostgreSQL (or any other SQL) means implementing one new class. Keep this in mind when adding new tables or queries.

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
AGENTS.md               This file
```

## How It Works

1. `GodelManager` launches a Chromium browser via Playwright.
2. `create_session()` creates a new `BrowserContext` (lightweight, isolated). Each session can run commands independently — this is how multi-instance works.
3. `GodelSession.login()` navigates to the app, fills email/password with `type()` (simulated keystrokes, not `fill()`, because the React app needs real input events), and submits via Enter key.
4. Commands use `session.send_command()` to type into `#terminal-input` and press Enter. They then poll for a new window element (`div[id$='-window']`) to appear, wait for the loading spinner to clear, and extract data from the DOM.
5. All CLI commands output structured JSON to stdout. Logs go to `godel_cli.log`.

## How to Run Commands

```bash
python cli.py -bg des AAPL                                  # company description
python cli.py -bg most --tab GAINERS --limit 50             # most active stocks
python cli.py -bg prt AAPL MSFT GOOGL -o results.csv        # pattern analysis
python cli.py -bg probe --duration 30 --filter websocket    # capture network traffic
python cli.py -bg chat --channels general --duration 60     # monitor chat → SQLite
python cli.py -bg res AAPL --download-pdfs                  # download research PDFs
```

Global flags: `--background` / `-bg` (recommended), `--layout <name>`, `--session-id <id>`, `--verbose`, `-o <file>`

## Critical Gotchas

### Headless mode is blocked — use --background instead

Godel Terminal detects headless Chrome and refuses to log in. The sign-in modal stays open and the auth silently fails. **Do not use `--headless`.**

Use `--background` (or `-bg`) instead. This launches a real headed browser positioned off-screen at (-10000, -10000) — completely invisible but undetectable by the site. **This is the recommended mode for agents.**

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

The `DatabaseBackend` abstract class in `db.py` is designed so swapping to PostgreSQL means implementing one new class. Add new tables by adding methods to the abstract class and implementing them in `SQLiteBackend`.

## WebSocket Endpoints Discovered

From probe command output:

- `wss://events.godelterminal.com/socket.io/?EIO=4&transport=websocket` — Socket.IO event stream
- `wss://api.godelterminal.com/events` — API event stream

These are the targets for chat monitoring. The `ChatMonitor` attaches to the `NetworkInterceptor` and processes incoming WebSocket frames, looking for JSON payloads with message-like structures. The exact chat message schema hasn't been fully mapped yet — run `python cli.py -bg probe --duration 60 --filter websocket` while chat is active to capture frame payloads and refine the parsing heuristics in `ChatMonitor._extract_chat_message()`.

## HTTP API Discovered

- `GET https://app.godelterminal.com/api/fetchBreaking` — returns breaking news as JSON array with fields: `id`, `type`, `time`, `important`, `data.content`, `impact[].symbol`, `classification[].name`

## What's Working

- **DES command** — Fully working and tested. Extracts company info, description, EPS estimates, analyst ratings, snapshot.
- **MOST command** — Fully working and tested. Extracts most active stocks with tab/limit/market cap filters. Handles T/B/M/K suffixes.
- **Probe command** — Working. Captures HTTP and WebSocket traffic, saves to JSON.
- **Login flow** — Working in non-headless and background modes. Uses type() + Enter.

- **Multi-instance architecture** — GodelManager + BrowserContexts are wired up and tested.

## What Needs Work

- **Chat monitoring** — The `ChatMonitor` frame parsing heuristics in `_extract_chat_message()` need tuning. Run probe with chat open to capture real WebSocket payloads and refine the parsing. The chat window on Godel Terminal shows as "Chat" with an "Anonymous" user label — explore this component to understand the message structure. Need to monitor #General, #biotech, #paid
- **RES command** — The PDF link detection uses generic selectors (`a[href]` with "pdf" in text/href). Needs testing against actual RES windows to find the right selectors for PDF download buttons.
- **PRT command** — Ported from Selenium to Playwright but not yet tested end-to-end. The original Selenium version worked. Test with: `python cli.py -bg prt AAPL MSFT -o test_prt.csv`
- **More Godel commands** — The site supports many more commands (FA, ANR, HMS, SI, TOP, WEI, TAS, FOCUS, HDS, etc.). Each needs a command class in `commands/` following the `BaseCommand` pattern.
- **WebSocket frame capture** — The interceptor detects WS connections opening/closing but captured 0 frames in initial testing. The connections may be short-lived or the frames may fire before handlers attach. Investigate by starting the interceptor earlier (before login) or by using CDP directly.
- **config-example.py** — Should be updated to match current structure.
- **Background mode** — Working. Off-screen browser, invisible to user, undetectable by site.
- **Find more API backends** — similar to breaking news, find more like that.

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
- Docs site (may timeout): https://docs.godelterminal.com/
- Beginner guide: https://godelguide.com/godel-terminal-complete-beginners-guide/
