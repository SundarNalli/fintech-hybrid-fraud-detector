"""Fence off attacker-controlled text before it goes into a prompt.

Memos, beneficiary names, KYB text and ticket text are written by people who
may be attacking us. They are shown to the model as labelled data blocks. The
real protection is structural (the agent is read-only and the policy wrapper
decides); this just makes the boundary hard to fake.
"""

from __future__ import annotations

import re

OPEN, CLOSE = "<<<", ">>>"
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_LABEL_BAD = re.compile(r"[^a-z0-9_]")


def wrap_untrusted(label: str, text: str, max_chars: int = 2000) -> str:
    """Return `text` inside a delimited block the prompt tells the model never to obey."""
    safe_label = _LABEL_BAD.sub("_", label.lower())
    cleaned = _CONTROL_CHARS.sub("", text)[:max_chars]
    # Text containing our delimiters could close the block early and pose as
    # instructions, so break them up.
    cleaned = cleaned.replace(OPEN, "<<_").replace(CLOSE, "_>>")
    return (
        f"{OPEN}UNTRUSTED_DATA {safe_label}{CLOSE}\n"
        f"{cleaned}\n"
        f"{OPEN}END_UNTRUSTED_DATA {safe_label}{CLOSE}"
    )
