"""Shared timestamp column helpers.

All timestamps are generated in Python as KST (Asia/Seoul, UTC+9) rather
than relying on the database's ``NOW()``, because MySQL's ``NOW()``
returns the *server's* local time -- and this app's MySQL is a remote
Railway instance whose server timezone isn't controlled by us. Stamping
KST here (and pinning the MySQL session timezone to +09:00 in
core/database.py for the ``server_default`` fallback) makes every
``DATETIME`` column -- and any row inserted directly via SQL, e.g. mock
data -- unambiguously KST, so it reads correctly at a glance in a MySQL
client. ``schemas/common.py``'s ``_to_utc_iso8601`` reverses this back to
real UTC before serializing API responses, so the ``...Z`` wire format
(섹션 3.3) is unaffected by where the DB stores its wall-clock digits.

``server_default`` is kept as a fallback for rows inserted outside the ORM
(manual SQL, migrations, mock data).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)
