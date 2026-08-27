from app.sip.call_lifecycle import CallLifecycle, CallStatus


def _make_lifecycle():
    hangup_calls = []
    notify_calls = []
    lifecycle = CallLifecycle(
        call_id="abc123",
        hangup_fn=lambda call_id: hangup_calls.append(call_id),
        notify_ended_fn=lambda call_id, reason: notify_calls.append((call_id, reason)),
    )
    return lifecycle, hangup_calls, notify_calls


def test_starts_in_ringing_state():
    lifecycle, _, _ = _make_lifecycle()

    assert lifecycle.status is CallStatus.RINGING
    assert lifecycle.is_ended is False


def test_ring_timeout_hangs_up_and_notifies():
    lifecycle, hangup_calls, notify_calls = _make_lifecycle()

    lifecycle.on_ring_timeout()

    assert hangup_calls == ["abc123"]
    assert notify_calls == [("abc123", "timeout")]
    assert lifecycle.is_ended is True


def test_ring_timeout_after_already_ended_is_a_noop():
    lifecycle, hangup_calls, notify_calls = _make_lifecycle()
    lifecycle.on_remote_terminated("remote")
    hangup_calls.clear()
    notify_calls.clear()

    lifecycle.on_ring_timeout()

    assert hangup_calls == []
    assert notify_calls == []


def test_remote_terminated_notifies_without_hangup():
    lifecycle, hangup_calls, notify_calls = _make_lifecycle()

    lifecycle.on_remote_terminated("remote")

    assert hangup_calls == []
    assert notify_calls == [("abc123", "remote")]
    assert lifecycle.is_ended is True


def test_remote_terminated_after_timeout_is_a_noop():
    lifecycle, hangup_calls, notify_calls = _make_lifecycle()
    lifecycle.on_ring_timeout()
    hangup_calls.clear()
    notify_calls.clear()

    lifecycle.on_remote_terminated("bye")

    assert hangup_calls == []
    assert notify_calls == []


def test_double_remote_terminated_only_notifies_once():
    lifecycle, _, notify_calls = _make_lifecycle()

    lifecycle.on_remote_terminated("cancel")
    lifecycle.on_remote_terminated("cancel")

    assert notify_calls == [("abc123", "cancel")]
