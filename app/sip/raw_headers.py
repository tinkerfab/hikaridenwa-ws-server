from __future__ import annotations


def extract_headers(whole_msg: str) -> dict[str, str]:
    """Parse a raw SIP message (e.g. pjsua2's SipRxData.wholeMsg) into a
    case-insensitive-keyed dict of header name (lowercased) -> value.

    Handles RFC 3261 header folding (continuation lines starting with a space
    or tab belong to the previous header) and repeated headers (RFC 3261
    §7.3.1: multiple instances of the same header are equivalent to one
    comma-joined instance).
    """
    # Header block ends at the first blank line (CRLF CRLF, but be lenient
    # about LF-only line endings too).
    normalized = whole_msg.replace("\r\n", "\n")
    header_block = normalized.split("\n\n", 1)[0]
    lines = header_block.split("\n")

    # First line is the request/status line, not a header.
    raw_lines = lines[1:] if lines else []

    unfolded: list[str] = []
    for line in raw_lines:
        if not line:
            continue
        if line[0] in (" ", "\t") and unfolded:
            unfolded[-1] += " " + line.strip()
        else:
            unfolded.append(line)

    headers: dict[str, str] = {}
    for line in unfolded:
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        key = name.strip().lower()
        value = value.strip()
        if key in headers:
            headers[key] = headers[key] + ", " + value
        else:
            headers[key] = value

    return headers
