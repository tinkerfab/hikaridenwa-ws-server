from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Awaitable, Callable

import pjsua2 as pj

from app.sip.call_lifecycle import CallLifecycle

logger = logging.getLogger(__name__)

OnRinging = Callable[[dict], Awaitable[None]]
OnEnded = Callable[[str, str], Awaitable[None]]


class WhoisCall(pj.Call):
    """Thin pjsua2 adapter for one inbound call.

    Owns the one real threading.Timer used as the ring-timeout safety valve
    and wires pjsua2's native onCallState callback to a plain-Python
    CallLifecycle (see app/sip/call_lifecycle.py), which decides *whether*
    to hang up / notify — this class only supplies the pjsua2-specific
    "how" (answer(), hangup(), getInfo()).

    We never call accept()/answer() with a final 200 — this is a passive
    caller-ID observer, not a real phone; only a 180 Ringing provisional
    response is sent, so other extensions/physical phones handle the actual
    call.
    """

    def __init__(
        self,
        account: "pj.Account",
        *,
        whole_msg: str,
        ring_timeout_s: float,
        loop: asyncio.AbstractEventLoop,
        on_ringing: OnRinging,
        on_ended: OnEnded,
        call_id: int = pj.PJSUA_INVALID_ID,
    ):
        super().__init__(account, call_id)
        self._loop = loop
        self._on_ended = on_ended
        self._lifecycle = CallLifecycle(
            call_id=str(self.getId()),
            hangup_fn=self._reject_with_480,
            notify_ended_fn=self._notify_ended,
        )
        self._timer = threading.Timer(ring_timeout_s, self._lifecycle.on_ring_timeout)
        self._timer.daemon = True

        self._answer_ringing()
        self._notify_ringing(on_ringing, whole_msg)
        self._timer.start()

    def _answer_ringing(self) -> None:
        try:
            prm = pj.CallOpParam()
            prm.statusCode = pj.PJSIP_SC_RINGING
            self.answer(prm)
        except Exception:
            logger.warning("failed to send 180 Ringing for call %s", self.getId(), exc_info=True)

    def _notify_ringing(self, on_ringing: OnRinging, whole_msg: str) -> None:
        event = {
            "call_id": str(self.getId()),
            "timestamp": time.time(),
            "whole_msg": whole_msg,
        }
        asyncio.run_coroutine_threadsafe(on_ringing(event), self._loop)

    def onCallState(self, prm) -> None:  # noqa: N802 - pjsua2 callback naming
        try:
            state = self.getInfo().state
        except Exception:
            logger.warning("failed to read call state for %s", self.getId(), exc_info=True)
            return
        if state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self._timer.cancel()
            self._lifecycle.on_remote_terminated("disconnected")

    def _reject_with_480(self, call_id: str) -> None:
        try:
            # This callback runs on the threading.Timer's own thread, not
            # one of pjsua2's own worker threads — any pjsua2 call from an
            # unregistered thread hits a hard pjlib assertion that aborts
            # the whole process (uncatchable from Python). Registering the
            # thread first (idempotent per-thread) avoids that.
            ep = pj.Endpoint.instance()
            if not ep.libIsThreadRegistered():
                ep.libRegisterThread("ring-timeout")
            if self.getInfo().state != pj.PJSIP_INV_STATE_DISCONNECTED:
                prm = pj.CallOpParam()
                prm.statusCode = pj.PJSIP_SC_TEMPORARILY_UNAVAILABLE
                self.hangup(prm)
        except Exception:
            logger.warning("failed to reject call %s with 480", call_id, exc_info=True)

    def _notify_ended(self, call_id: str, reason: str) -> None:
        asyncio.run_coroutine_threadsafe(self._on_ended(call_id, reason), self._loop)
