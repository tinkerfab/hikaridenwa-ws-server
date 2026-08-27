from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

import pjsua2 as pj

from app.sip.pj_call import WhoisCall

logger = logging.getLogger(__name__)

OnRinging = Callable[[dict], Awaitable[None]]
OnEnded = Callable[[str, str], Awaitable[None]]
OnRegState = Callable[[bool, int, str], None]


class WhoisAccount(pj.Account):
    """Thin pjsua2 adapter: registers as the HGW's internal extension and
    spawns a WhoisCall for each inbound INVITE. All real decision logic
    lives in CallLifecycle; this class only bridges pjsua2's native
    callbacks to our own async event handlers.
    """

    def __init__(
        self,
        *,
        ring_timeout_s: float,
        loop: asyncio.AbstractEventLoop,
        on_ringing: OnRinging,
        on_ended: OnEnded,
        on_reg_state: OnRegState | None = None,
    ):
        super().__init__()
        self._ring_timeout_s = ring_timeout_s
        self._loop = loop
        self._on_ringing = on_ringing
        self._on_ended = on_ended
        self._on_reg_state = on_reg_state
        self._calls: dict[str, WhoisCall] = {}

    def onRegState(self, prm) -> None:  # noqa: N802 - pjsua2 callback naming
        info = self.getInfo()
        logger.info(
            "SIP registration state: active=%s code=%s reason=%s",
            info.regIsActive,
            info.regStatus,
            info.regStatusText,
        )
        if self._on_reg_state is not None:
            self._on_reg_state(info.regIsActive, info.regStatus, info.regStatusText)

    def onIncomingCall(self, prm) -> None:  # noqa: N802 - pjsua2 callback naming
        whole_msg = prm.rdata.wholeMsg if prm.rdata else ""
        call = WhoisCall(
            self,
            whole_msg=whole_msg,
            ring_timeout_s=self._ring_timeout_s,
            loop=self._loop,
            on_ringing=self._on_ringing,
            on_ended=self._wrap_on_ended,
            call_id=prm.callId,
        )
        self._calls[str(prm.callId)] = call

    async def _wrap_on_ended(self, call_id: str, reason: str) -> None:
        self._calls.pop(call_id, None)
        await self._on_ended(call_id, reason)
