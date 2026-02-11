"""
Godel Terminal Core Framework (Playwright)
Multi-instance terminal control with network interception
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

logger = logging.getLogger("godel")

# ---------------------------------------------------------------------------
# Network Interceptor
# ---------------------------------------------------------------------------

class NetworkInterceptor:
    """Captures HTTP requests/responses and WebSocket frames on a page."""

    def __init__(self, page: Page):
        self.page = page
        self.requests: List[Dict] = []
        self.responses: List[Dict] = []
        self.ws_frames: List[Dict] = []
        self._ws_objects: List[Any] = []
        self._listening = False

    def start(self, url_filter: Optional[str] = None, capture_ws: bool = True):
        """Begin capturing network traffic."""
        self._url_filter = url_filter
        self._listening = True

        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)
        if capture_ws:
            self.page.on("websocket", self._on_websocket)

    def stop(self):
        """Stop capturing (removes listeners)."""
        self._listening = False
        try:
            self.page.remove_listener("request", self._on_request)
            self.page.remove_listener("response", self._on_response)
            self.page.remove_listener("websocket", self._on_websocket)
        except Exception:
            pass

    # -- internal handlers --------------------------------------------------

    def _on_request(self, request):
        if not self._listening:
            return
        url = request.url
        if self._url_filter and self._url_filter not in url:
            return
        self.requests.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "url": url,
            "resource_type": request.resource_type,
            "headers": dict(request.headers) if request.headers else {},
            "post_data": request.post_data,
        })

    async def _on_response(self, response):
        if not self._listening:
            return
        url = response.url
        if self._url_filter and self._url_filter not in url:
            return
        body_text = None
        try:
            body_text = await response.text()
            # Truncate large bodies
            if len(body_text) > 10000:
                body_text = body_text[:10000] + "...[truncated]"
        except Exception:
            pass
        self.responses.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "status": response.status,
            "url": url,
            "headers": dict(response.headers) if response.headers else {},
            "body_preview": body_text,
        })

    def _on_websocket(self, ws):
        logger.info(f"WebSocket opened: {ws.url}")
        self._ws_objects.append(ws)

        def on_frame_sent(payload):
            self.ws_frames.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "direction": "sent",
                "url": ws.url,
                "payload": payload[:5000] if isinstance(payload, str) and len(payload) > 5000 else payload,
            })

        def on_frame_received(payload):
            self.ws_frames.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "direction": "received",
                "url": ws.url,
                "payload": payload[:5000] if isinstance(payload, str) and len(payload) > 5000 else payload,
            })

        ws.on("framesent", on_frame_sent)
        ws.on("framereceived", on_frame_received)
        ws.on("close", lambda _: logger.info(f"WebSocket closed: {ws.url}"))

    # -- data access --------------------------------------------------------

    def dump(self, filter_type: Optional[str] = None) -> Dict:
        """Return captured traffic as a dict.  filter_type: 'http', 'websocket', or None for all."""
        data: Dict[str, Any] = {}
        if filter_type in (None, "http"):
            data["requests"] = self.requests
            data["responses"] = self.responses
        if filter_type in (None, "websocket"):
            data["websocket_frames"] = self.ws_frames
        return data

    def clear(self):
        self.requests.clear()
        self.responses.clear()
        self.ws_frames.clear()


# ---------------------------------------------------------------------------
# GodelSession  (one browser context == one logged-in session)
# ---------------------------------------------------------------------------

class GodelSession:
    """Single Godel Terminal session backed by a Playwright BrowserContext."""

    def __init__(self, context: BrowserContext, url: str = "https://app.godelterminal.com"):
        self.context = context
        self.url = url
        self.page: Optional[Page] = None
        self.interceptor: Optional[NetworkInterceptor] = None
        self.active_commands: List[Any] = []
        self._tracked_windows: set = set()

    async def init_page(self):
        """Create the page, attach interceptor, navigate to terminal."""
        self.page = await self.context.new_page()
        self.interceptor = NetworkInterceptor(self.page)
        await self.page.goto(self.url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)
        logger.info(f"Connected to {self.url}")

    async def login(self, username: str, password: str):
        """Log in to Godel Terminal."""
        logger.info("Logging in...")

        # Wait for the page to settle
        await self.page.wait_for_timeout(2000)

        # Check if sign-in modal or login button is present
        header_login = self.page.locator("button:has-text('Login')").first
        await header_login.wait_for(state="visible", timeout=15000)
        await header_login.click()
        await self.page.wait_for_timeout(1000)

        # Wait for sign-in modal to appear
        logger.info("Entering credentials...")
        email_field = self.page.locator("input[type='email'], input[autocomplete='username'], input[placeholder*='mail' i]").first
        await email_field.wait_for(state="visible", timeout=10000)

        # Use triple-click to select all, then type to simulate real keystrokes
        # This works with React controlled inputs where fill() may not trigger state
        await email_field.click(click_count=3)
        await self.page.wait_for_timeout(100)
        await email_field.type(username, delay=30)
        logger.info(f"Email typed: {username}")

        password_field = self.page.locator("input[type='password'], input[autocomplete='current-password']").first
        await password_field.click(click_count=3)
        await self.page.wait_for_timeout(100)
        await password_field.type(password, delay=30)
        logger.info("Password typed")
        await self.page.wait_for_timeout(500)

        # Submit by pressing Enter on the password field (most reliable for React forms)
        await password_field.press("Enter")
        logger.info("Login submitted via Enter key")

        logger.info("Waiting for login to complete...")
        await self.page.wait_for_timeout(3000)

        # Check if login succeeded: the sign-in modal should be gone
        # and the header should no longer show "Register"
        sign_in_modal = self.page.locator("text=Sign In").first
        try:
            await sign_in_modal.wait_for(state="hidden", timeout=10000)
            logger.info("Sign-in modal closed — login successful")
        except Exception:
            await self.screenshot("output/login_failed.png")
            raise RuntimeError(
                "Login failed — sign-in modal still visible. "
                "Check credentials in config.py. Screenshot: output/login_failed.png"
            )

        await self.page.wait_for_timeout(1000)
        logger.info("Login complete")

    async def load_layout(self, layout_name: str = "dev") -> bool:
        """Switch to a named layout. Returns False (not fatal) if not found."""
        logger.info(f"Loading layout: {layout_name}")
        try:
            layout = self.page.locator(f"span.whitespace-nowrap:text-is('{layout_name}')")
            await layout.wait_for(state="visible", timeout=10000)
            await layout.click()
            await self.page.wait_for_timeout(1000)
            logger.info(f"Layout '{layout_name}' loaded")
            return True
        except Exception as e:
            logger.warning(f"Layout '{layout_name}' not found, continuing with default: {e}")
            return False

    async def send_command(self, command_str: str) -> bool:
        """Type a command into the terminal input and press Enter."""
        try:
            terminal = self.page.locator("#terminal-input")
            await terminal.fill("")
            await terminal.type(command_str, delay=20)
            await self.page.wait_for_timeout(200)
            await terminal.press("Enter")
            logger.info(f"Command sent: {command_str}")
            return True
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return False

    # -- window helpers -----------------------------------------------------

    async def get_current_windows(self) -> list:
        """Return all window element handles in the DOM."""
        return await self.page.locator("div.resize.inline-block.absolute[id$='-window']").all()

    async def wait_for_new_window(self, previous_count: int, timeout: int = 10000) -> Optional[Any]:
        """Poll until a new window appears or timeout (ms)."""
        deadline = time.monotonic() + timeout / 1000
        while time.monotonic() < deadline:
            windows = await self.get_current_windows()
            if len(windows) > previous_count:
                new_win = windows[-1]
                win_id = await new_win.get_attribute("id")
                if win_id and win_id not in self._tracked_windows:
                    self._tracked_windows.add(win_id)
                    return new_win
            await self.page.wait_for_timeout(100)
        return None

    async def wait_for_loading(self, timeout: int = 30000) -> bool:
        """Wait for the loading spinner to disappear."""
        try:
            await self.page.wait_for_timeout(500)
            spinner = self.page.locator(".anticon-loading.anticon-spin")
            await spinner.wait_for(state="hidden", timeout=timeout)
            return True
        except Exception:
            return False

    async def close_window(self, window) -> bool:
        """Close a command window using multiple fallback strategies."""
        strategies = [
            "span.anticon.anticon-close",
            "svg[data-icon='close']",
            "button[aria-label*='close' i]",
        ]
        for selector in strategies:
            try:
                close_btn = window.locator(selector).first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await self.page.wait_for_timeout(500)
                    return True
            except Exception:
                continue
        logger.warning("Could not close window")
        return False

    async def close_all_windows(self):
        """Close every tracked command window."""
        windows = await self.get_current_windows()
        for win in windows:
            await self.close_window(win)
        self.active_commands.clear()
        self._tracked_windows.clear()
        logger.info("All windows closed")

    async def screenshot(self, path: str = "output/screenshot.png"):
        """Save a screenshot (useful for debugging)."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=path, full_page=True)
        logger.info(f"Screenshot saved: {path}")

    async def close(self):
        """Tear down this session's page and context."""
        try:
            if self.interceptor:
                self.interceptor.stop()
            if self.page:
                await self.page.close()
            await self.context.close()
            logger.info("Session closed")
        except Exception as e:
            logger.error(f"Error closing session: {e}")


# ---------------------------------------------------------------------------
# GodelManager  (one browser, many contexts/sessions)
# ---------------------------------------------------------------------------

class GodelManager:
    """Owns the Playwright browser and spawns GodelSession instances."""

    def __init__(self, headless: bool = False, background: bool = False,
                 url: str = "https://app.godelterminal.com"):
        self.headless = headless
        self.background = background
        self.url = url
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self.sessions: Dict[str, GodelSession] = {}

    async def start(self):
        """Launch the browser.

        Modes:
          headless=False, background=False  — normal visible browser
          headless=False, background=True   — real browser positioned off-screen (invisible but undetectable)
          headless=True                     — headless Chromium (may be blocked by some sites)
        """
        self._playwright = await async_playwright().start()

        args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--ignore-certificate-errors",
            "--disable-save-password-bubble",
            "--disable-autofill-keyboard-accessory-view",
        ]

        if self.background and not self.headless:
            # Position the window far off-screen so it's invisible
            # but still a real headed browser (bypasses bot detection)
            args.append("--window-position=-10000,-10000")

        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=args,
        )

        mode = "background" if self.background else ("headless" if self.headless else "visible")
        logger.info(f"Browser launched (mode={mode})")

    async def create_session(self, session_id: str = "default") -> GodelSession:
        """Create a new browser context and session."""
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")
        context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        session = GodelSession(context, self.url)
        self.sessions[session_id] = session
        logger.info(f"Session '{session_id}' created")
        return session

    async def get_session(self, session_id: str = "default") -> Optional[GodelSession]:
        return self.sessions.get(session_id)

    async def close_session(self, session_id: str = "default"):
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()

    async def shutdown(self):
        """Close all sessions and the browser."""
        for sid in list(self.sessions):
            await self.close_session(sid)
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Manager shut down")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *exc):
        await self.shutdown()


# ---------------------------------------------------------------------------
# BaseCommand  (async, Playwright-based)
# ---------------------------------------------------------------------------

class BaseCommand(ABC):
    """Abstract base for all terminal commands."""

    def __init__(self, session: GodelSession):
        self.session = session
        self.page = session.page
        self.window = None
        self.window_id: Optional[str] = None
        self.data: Optional[Dict] = None

    @abstractmethod
    def get_command_string(self, ticker: str = None, asset_class: str = None) -> str:
        pass

    @abstractmethod
    async def extract_data(self) -> Dict:
        pass

    async def execute(self, ticker: str = None, asset_class: str = "EQ") -> Dict:
        """Send command, wait for window, wait for loading, extract data."""
        command_str = self.get_command_string(ticker, asset_class)

        previous_count = len(await self.session.get_current_windows())
        logger.info(f"Executing: {command_str}  (windows before: {previous_count})")

        if not await self.session.send_command(command_str):
            return {"success": False, "error": "Failed to send command", "command": command_str}

        logger.info("Waiting for new window...")
        self.window = await self.session.wait_for_new_window(previous_count, timeout=15000)
        if not self.window:
            await self.session.screenshot(f"output/no_window_{command_str.replace(' ', '_')}.png")
            return {"success": False, "error": "No new window created", "command": command_str}

        self.window_id = await self.window.get_attribute("id")
        logger.info(f"New window: {self.window_id}")

        logger.info("Waiting for content to load...")
        if not await self.session.wait_for_loading(timeout=30000):
            # Take a screenshot on failure
            await self.session.screenshot(f"output/timeout_{self.window_id}.png")
            return {"success": False, "error": "Loading timeout", "command": command_str, "window_id": self.window_id}

        logger.info("Extracting data...")
        try:
            self.data = await self.extract_data()
            return {"success": True, "command": command_str, "data": self.data}
        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            await self.session.screenshot(f"output/error_{self.window_id}.png")
            return {"success": False, "error": f"Data extraction failed: {e}", "command": command_str, "window_id": self.window_id}

    async def close(self):
        """Close this command's window."""
        if self.window:
            return await self.session.close_window(self.window)
        return False
