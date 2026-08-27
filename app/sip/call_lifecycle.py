from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class CallStatus(str, Enum):
    RINGING = "ringing"
    ENDED = "ended"


@dataclass
class CallLifecycle:
    """Pure decision logic for one inbound call's ring-timeout safety valve.

    Deliberately has no pjsua2 import and owns no real timer/thread: the
    pjsua2 adapter (sip/pj_call.py's WhoisCall) owns a real threading.Timer
    and calls on_ring_timeout()/on_remote_terminated() at the right moments.
    This class only decides *whether* a hangup/notify should still happen,
    guarding against acting twice on a call that already ended.
    """

    call_id: str
    hangup_fn: Callable[[str], None]
    notify_ended_fn: Callable[[str, str], None]
    status: CallStatus = field(default=CallStatus.RINGING, init=False)

    def on_ring_timeout(self) -> None:
        """Invoked when the ring-timeout timer fires with no CANCEL/BYE seen.

        Rejects the call with a 480 so our virtual extension doesn't keep
        ringing forever from the HGW's perspective.
        """
        if self.status is not CallStatus.RINGING:
            return
        self.status = CallStatus.ENDED
        self.hangup_fn(self.call_id)
        self.notify_ended_fn(self.call_id, "timeout")

    def on_remote_terminated(self, reason: str = "remote") -> None:
        """Invoked when the HGW sends CANCEL/BYE for this dialog (e.g. another
        extension answered, or the caller hung up). No hangup_fn call is
        needed here — the dialog is already gone on the network side.
        """
        if self.status is not CallStatus.RINGING:
            return
        self.status = CallStatus.ENDED
        self.notify_ended_fn(self.call_id, reason)

    @property
    def is_ended(self) -> bool:
        return self.status is CallStatus.ENDED
