"""Errors the user reads, in the language they chose.

The API answered in Uzbek. The app speaks three languages and a Russian
speaker was being handed Uzbek the moment anything went wrong — usually
while holding a photo that wouldn't scan, which is the worst moment to be
told something you can't read.

So a user-facing failure carries a code the client translates, plus any
numbers the sentence needs, plus the Uzbek as a fallback: an old client, a
code the frontend hasn't got a string for yet, and anything reading the API
directly all still get a sentence rather than a key.

Errors nobody but a developer sees — "Session not found", "Only the host
can…" — stay plain strings. Translating them would be work for an audience
of one, and the status code already carries the meaning.
"""

from typing import Any

from fastapi import HTTPException


def api_error(
    status: int, code: str, message: str, **params: Any
) -> HTTPException:
    """A failure the client should say in its own words.

    `code` names the string to look up, `params` fills its placeholders, and
    `message` is what to show when the lookup finds nothing.
    """
    detail: dict[str, Any] = {"code": code, "message": message}
    if params:
        detail["params"] = params
    return HTTPException(status, detail)
