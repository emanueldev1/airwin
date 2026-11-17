"""Bucle asyncio en un hilo aparte para pyatv / aiohttp."""
from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Awaitable, Callable, Optional


class AsyncRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="airwin-asyncio", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(
        self,
        coro: Awaitable[Any],
        on_done: Optional[Callable[[concurrent.futures.Future], None]] = None,
    ) -> concurrent.futures.Future:
        fut = asyncio.run_coroutine_threadsafe(coro, self.loop)  # type: ignore[arg-type]
        if on_done:
            fut.add_done_callback(on_done)
        return fut

    def run_sync(self, coro: Awaitable[Any], timeout: float = 15) -> Any:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)  # type: ignore[arg-type]

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=3)
