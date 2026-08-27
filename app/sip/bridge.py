from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

import pjsua2 as pj

from app.config import Config
from app.sip.pj_account import WhoisAccount

logger = logging.getLogger(__name__)

OnRinging = Callable[[dict], Awaitable[None]]
OnEnded = Callable[[str, str], Awaitable[None]]


class SipBridge:
    """Owns the pjsua2 Endpoint/Account lifecycle for the whole process.

    pjsua2 is a C++ library with its own internal worker thread(s); its
    native callbacks (onIncomingCall/onCallState/onRegState, wired through
    WhoisAccount/WhoisCall) fire on that thread. on_ringing/on_ended are
    coroutine functions that get scheduled onto `loop` (the asyncio loop
    driving the FastAPI app) via asyncio.run_coroutine_threadsafe — this
    class and its collaborators are the only place that hand-off happens.
    """

    def __init__(
        self,
        config: Config,
        loop: asyncio.AbstractEventLoop,
        on_ringing: OnRinging,
        on_ended: OnEnded,
    ):
        self._config = config
        self._loop = loop
        self._on_ringing = on_ringing
        self._on_ended = on_ended
        self._endpoint: pj.Endpoint | None = None
        self._account: WhoisAccount | None = None

    def start(self) -> None:
        self._endpoint = pj.Endpoint()
        self._endpoint.libCreate()

        ep_cfg = pj.EpConfig()
        # Persist pjsua2's own SIP protocol trace (the "TX/RX ... bytes ..."
        # lines) to a file for later troubleshooting, in addition to its
        # default console output. pjsua2 writes this file directly (not via
        # Python logging) and does not rotate it — see README for the
        # logrotate note if it grows too large on a long-running device.
        data_dir = Path(self._config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        ep_cfg.logConfig.filename = str(data_dir / "sip.log")
        ep_cfg.logConfig.fileFlags = pj.PJ_O_APPEND
        self._endpoint.libInit(ep_cfg)

        transport_cfg = pj.TransportConfig()
        transport_cfg.port = self._config.hgw_port
        transport_cfg.boundAddress = self._config.local_bind_ip
        self._endpoint.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)

        self._endpoint.libStart()
        logger.info(
            "pjsua2 endpoint started, bound to %s:%s",
            self._config.local_bind_ip,
            self._config.hgw_port,
        )

        account_cfg = pj.AccountConfig()
        account_cfg.idUri = f"sip:{self._config.sip_extension}@{self._config.hgw_host}"
        account_cfg.regConfig.registrarUri = f"sip:{self._config.hgw_host}:{self._config.hgw_port}"
        account_cfg.regConfig.timeoutSec = self._config.sip_register_expires
        account_cfg.sipConfig.authCreds.append(
            pj.AuthCredInfo("digest", "*", self._config.sip_auth_user, 0, self._config.sip_password)
        )

        self._account = WhoisAccount(
            ring_timeout_s=self._config.ring_timeout_s,
            loop=self._loop,
            on_ringing=self._on_ringing,
            on_ended=self._on_ended,
            on_reg_state=self._log_reg_state,
        )
        self._account.create(account_cfg)

    def stop(self) -> None:
        if self._account is not None:
            try:
                self._account.shutdown()
            except Exception:
                logger.warning("error shutting down SIP account", exc_info=True)
            self._account = None
        if self._endpoint is not None:
            try:
                self._endpoint.libDestroy()
            except Exception:
                logger.warning("error destroying pjsua2 endpoint", exc_info=True)
            self._endpoint = None

    @staticmethod
    def _log_reg_state(is_active: bool, status: int, reason: str) -> None:
        if not is_active:
            logger.warning("SIP registration inactive: %s %s", status, reason)
