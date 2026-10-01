"""
The MIT License (MIT)

Copyright (c) 2026-present DA-344 (aka Developer Anonymous)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

from fastapi import Request

LOCALES_DIR = Path(__file__).resolve().parents[2] / "locales"
SUPPORTED = ("es", "en")
DEFAULT_LANGUAGE = "es"
LANGUAGE_COOKIE = "assignment-language"


def _unquote(fragment: str) -> str:
    try:
        return ast.literal_eval(fragment)
    except (ValueError, SyntaxError):
        return fragment.strip('"')


@lru_cache(maxsize=len(SUPPORTED))
def load_catalog(language: str) -> dict[str, str]:
    """Parse a ``.po`` file into ``{msgid: msgstr}`` (header and empty msgstr skipped)."""
    path = LOCALES_DIR / language / "LC_MESSAGES" / "messages.po"
    if language not in SUPPORTED or not path.is_file():
        return {}
    catalog: dict[str, str] = {}
    msgid: str | None = None
    msgstr: str | None = None
    target = None

    def flush() -> None:
        if msgid and msgstr:
            catalog[msgid] = msgstr

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("msgid "):
            flush()
            msgid, msgstr, target = _unquote(line[6:]), None, "id"
        elif line.startswith("msgstr "):
            msgstr, target = _unquote(line[7:]), "str"
        elif line.startswith('"'):
            if target == "id" and msgid is not None:
                msgid += _unquote(line)
            elif target == "str" and msgstr is not None:
                msgstr += _unquote(line)
    flush()
    return catalog


def request_language(request: Request) -> str:
    language = request.cookies.get(LANGUAGE_COOKIE, DEFAULT_LANGUAGE)
    return language if language in SUPPORTED else DEFAULT_LANGUAGE


def ui_catalog(request: Request) -> dict[str, str]:
    """Only entries that differ from the source (Spanish) text need shipping."""
    catalog = load_catalog(request_language(request))
    return {source: target for source, target in catalog.items() if source != target}


def translate(request: Request, message: str) -> str:
    return load_catalog(request_language(request)).get(message, message)
