"""Shared timestamp column helpers.

All timestamps are generated in Python as timezone-aware UTC rather than
relying on the database's ``NOW()``, because MySQL's ``NOW()`` returns the
server's *local* time (its DATETIME type has no offset). Stamping UTC here
makes the value unambiguous, so the API can safely serialize it with a
trailing ``Z`` per the spec's ISO 8601 rule (섹션 3.3).

``server_default`` is kept as a fallback for rows inserted outside the ORM
(manual SQL, migrations).
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
