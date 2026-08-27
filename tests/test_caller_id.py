import pytest

from app.sip.caller_id import normalize_phone_number, parse_caller_id
from app.sip.raw_headers import extract_headers
from tests.fixtures.sip_messages import (
    INVITE_ANONYMOUS_CALLER,
    INVITE_DISCLOSED_CALLER,
    INVITE_FOLDED_HEADER,
    INVITE_NO_IDENTITY_HEADERS,
    INVITE_RPID_ONLY,
    INVITE_TEL_URI_CALLER,
)


def _caller_id_for(raw_msg: str):
    return parse_caller_id(extract_headers(raw_msg))


def test_disclosed_caller_prefers_pai_over_from():
    result = _caller_id_for(INVITE_DISCLOSED_CALLER)

    assert result.number == "0312345678"
    assert result.source == "pai"
    assert result.anonymous is False


def test_tel_uri_caller_normalizes_country_code():
    result = _caller_id_for(INVITE_TEL_URI_CALLER)

    assert result.number == "0312345678"
    assert result.source == "pai"


def test_anonymous_caller_from_marker_and_privacy_header():
    result = _caller_id_for(INVITE_ANONYMOUS_CALLER)

    assert result.number is None
    assert result.anonymous is True
    assert result.source == "from"


def test_rpid_used_when_from_is_anonymous_and_pai_absent():
    result = _caller_id_for(INVITE_RPID_ONLY)

    assert result.number == "0312345678"
    assert result.source == "rpid"
    assert result.anonymous is False


def test_folded_from_header_still_parses():
    result = _caller_id_for(INVITE_FOLDED_HEADER)

    assert result.number == "0312345678"
    assert result.display_name == "0312345678"
    assert result.source == "from"


def test_no_identity_headers_yields_none_source():
    result = _caller_id_for(INVITE_NO_IDENTITY_HEADERS)

    assert result.number is None
    assert result.anonymous is False
    assert result.source == "none"


def test_privacy_id_with_no_parseable_headers_marks_anonymous():
    headers = {"privacy": "id"}

    result = parse_caller_id(headers)

    assert result.number is None
    assert result.anonymous is True
    assert result.source == "none"


def test_privacy_none_does_not_force_anonymous():
    headers = {"privacy": "none"}

    result = parse_caller_id(headers)

    assert result.anonymous is False


@pytest.mark.parametrize(
    "user,expected",
    [
        ("0312345678", "0312345678"),
        ("+81312345678", "0312345678"),
        ("0081312345678", "0312345678"),
        ("0312345678;user=phone", "0312345678"),
    ],
)
def test_normalize_phone_number(user, expected):
    assert normalize_phone_number(user) == expected
