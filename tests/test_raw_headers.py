from app.sip.raw_headers import extract_headers
from tests.fixtures.sip_messages import (
    INVITE_DISCLOSED_CALLER,
    INVITE_FOLDED_HEADER,
    INVITE_NO_IDENTITY_HEADERS,
)


def test_extract_headers_parses_simple_headers():
    headers = extract_headers(INVITE_DISCLOSED_CALLER)

    assert headers["call-id"] == "abc123@203.0.113.5"
    assert headers["cseq"] == "1 INVITE"
    assert headers["p-asserted-identity"] == "<sip:0312345678@203.0.113.5>"


def test_extract_headers_is_case_insensitive_by_key():
    headers = extract_headers(INVITE_DISCLOSED_CALLER)

    assert "from" in headers
    assert "From" not in headers  # keys are normalized to lowercase


def test_extract_headers_unfolds_continuation_lines():
    headers = extract_headers(INVITE_FOLDED_HEADER)

    assert headers["via"] == "SIP/2.0/UDP 203.0.113.5:5060 ;branch=z9hG4bK-5"
    assert headers["from"] == '"0312345678" <sip:0312345678@203.0.113.5>;tag=folded1'


def test_extract_headers_stops_at_body_boundary():
    msg = INVITE_DISCLOSED_CALLER.replace(
        "Content-Length: 0\r\n\r\n", "Content-Length: 4\r\n\r\nv=0\n"
    )

    headers = extract_headers(msg)

    assert "v=0" not in headers
    assert headers["content-length"] == "4"


def test_extract_headers_handles_missing_optional_headers():
    headers = extract_headers(INVITE_NO_IDENTITY_HEADERS)

    assert "from" not in headers
    assert "p-asserted-identity" not in headers
    assert headers["call-id"] == "pqr678@203.0.113.5"


def test_extract_headers_returns_empty_dict_for_empty_message():
    assert extract_headers("") == {}
