"""
Godel Terminal API — async Python interface with multi-session support
"""

import asyncio
from typing import Any, Dict, List, Optional

from godel_core import GodelManager, GodelSession
from commands import (
    DESCommand, PRTCommand, MOSTCommand,
    GCommand, GIPCommand, QMCommand,
    ProbeCommand, ChatMonitor, RESCommand,
)

try:
    from config import GODEL_URL, GODEL_USERNAME, GODEL_PASSWORD
except ImportError:
    GODEL_URL = "https://app.godelterminal.com/"
    GODEL_USERNAME = None
    GODEL_PASSWORD = None


class GodelAPI:
    """Async API wrapper for Godel Terminal with multi-session support."""

    def __init__(self, url: str = None, username: str = None, password: str = None,
                 headless: bool = False):
        self.url = url or GODEL_URL
        self.username = username or GODEL_USERNAME
        self.password = password or GODEL_PASSWORD
        self.headless = headless
        self.manager: Optional[GodelManager] = None
        self._default_session: Optional[GodelSession] = None

        if not self.username or not self.password:
            raise ValueError("Username and password required (via config.py or arguments)")

    async def connect(self, layout: str = "dev", session_id: str = "default") -> GodelSession:
        """Start browser, create session, login, load layout."""
        self.manager = GodelManager(headless=self.headless, url=self.url)
        await self.manager.start()
        session = await self.manager.create_session(session_id)
        await session.init_page()
        await session.login(self.username, self.password)
        await session.load_layout(layout)
        self._default_session = session
        return session

    async def add_session(self, session_id: str, layout: str = "dev") -> GodelSession:
        """Add an additional concurrent session (new browser context)."""
        if not self.manager:
            raise RuntimeError("Call connect() first")
        session = await self.manager.create_session(session_id)
        await session.init_page()
        await session.login(self.username, self.password)
        await session.load_layout(layout)
        return session

    def _session(self, session_id: str = None) -> GodelSession:
        if session_id and self.manager:
            s = self.manager.sessions.get(session_id)
            if s:
                return s
        if self._default_session:
            return self._default_session
        raise RuntimeError("Not connected")

    async def disconnect(self):
        if self.manager:
            await self.manager.shutdown()
            self.manager = None
            self._default_session = None

    # -- commands -----------------------------------------------------------

    async def des(self, ticker: str, asset_class: str = "EQ",
                  session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = DESCommand(s)
        return await cmd.execute(ticker, asset_class)

    async def prt(self, tickers: List[str], output_path: Optional[str] = None,
                  session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = PRTCommand(s, tickers=tickers)
        result = await cmd.execute()
        if result["success"] and output_path and cmd.df is not None:
            if output_path.endswith(".csv"):
                cmd.save_to_csv(output_path)
            elif output_path.endswith(".json"):
                cmd.save_to_json(output_path)
            else:
                cmd.save_to_csv(output_path + ".csv")
        return result

    async def most(self, tab: str = "ACTIVE", limit: int = 75,
                   output_path: Optional[str] = None,
                   session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = MOSTCommand(s, tab=tab, limit=limit)
        result = await cmd.execute()
        if result["success"] and output_path and cmd.df is not None:
            if output_path.endswith(".csv"):
                cmd.save_to_csv(output_path)
            elif output_path.endswith(".json"):
                cmd.save_to_json(output_path)
            else:
                cmd.save_to_csv(output_path + ".csv")
        return result

    async def res(self, ticker: str, asset_class: str = "EQ",
                  download_pdfs: bool = True, output_dir: str = "output/pdfs",
                  session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = RESCommand(s, download_pdfs=download_pdfs, output_dir=output_dir)
        return await cmd.execute(ticker, asset_class)

    async def probe(self, duration: int = 30, filter_type: Optional[str] = None,
                    url_filter: Optional[str] = None, output_path: Optional[str] = None,
                    session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = ProbeCommand(s, duration=duration, filter_type=filter_type,
                           url_filter=url_filter)
        return await cmd.execute_and_save(output_path)

    async def chat(self, channels: Optional[List[str]] = None, duration: int = 60,
                   session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        monitor = ChatMonitor(s, channels=channels)
        await monitor.start(duration=duration)
        return {
            "success": True,
            "messages_captured": monitor.message_count,
            "duration": duration,
            "channels": channels,
        }

    async def g(self, ticker: str, asset_class: str = "EQ",
                session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = GCommand(s)
        return await cmd.execute(ticker, asset_class)

    async def gip(self, ticker: str, asset_class: str = "EQ",
                  session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = GIPCommand(s)
        return await cmd.execute(ticker, asset_class)

    async def qm(self, ticker: str, asset_class: str = "EQ",
                 session_id: str = None) -> Dict[str, Any]:
        s = self._session(session_id)
        cmd = QMCommand(s)
        return await cmd.execute(ticker, asset_class)

    async def close_all_windows(self, session_id: str = None):
        self._session(session_id)
        s = self._session(session_id)
        await s.close_all_windows()

    # -- context manager ----------------------------------------------------

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()


# ---------------------------------------------------------------------------
# Quick functions (connect, execute, disconnect in one call)
# ---------------------------------------------------------------------------

async def quick_des(ticker: str, asset_class: str = "EQ", **kw) -> Dict[str, Any]:
    async with GodelAPI(**kw) as api:
        return await api.des(ticker, asset_class)


async def quick_prt(tickers: List[str], **kw) -> Dict[str, Any]:
    async with GodelAPI(**kw) as api:
        return await api.prt(tickers)


async def quick_most(tab: str = "ACTIVE", limit: int = 75, **kw) -> Dict[str, Any]:
    async with GodelAPI(**kw) as api:
        return await api.most(tab=tab, limit=limit)


async def quick_probe(duration: int = 30, **kw) -> Dict[str, Any]:
    async with GodelAPI(**kw) as api:
        return await api.probe(duration=duration)
