"""Centralized logging setup so every request/warning/error printed to the
terminal (and ``.dev-logs/backend.log``) carries a timestamp and is readable.

Without this, ``logging.basicConfig(level=...)`` with no format string falls
back to Python's bare default (``LEVEL:logger.name:message`` — no time at
all), which makes it impossible to tell *when* a request came in or line up
a burst of errors against what the user was doing at that moment.

Call ``configure_logging()`` once, as early as possible (before any other
module logs anything) — ``main.py`` does this immediately after imports.
"""

from __future__ import annotations

import logging
import sys

from core.config import settings

LOG_FORMAT = "%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _use_utf8_console() -> None:
    """Windows 콘솔(cp949 등)에서 한글 로그가 깨져 보이는 걸 막는다.

    ``.dev-logs/backend.log`` 로 리다이렉트해서 봐도, 에디터로 열어도 항상
    올바른 UTF-8 텍스트가 나오게 한다. 콘솔이 reconfigure를 지원하지 않는
    (드문) 환경이면 조용히 무시한다.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def configure_logging() -> None:
    _use_utf8_console()

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    # SQLAlchemy가 DEBUG일 때만 실행 SQL을 찍게 한다 -- INFO에서는 너무
    # 시끄러워서 실제 요청/에러 로그가 묻힌다.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if level <= logging.DEBUG else logging.WARNING
    )

    # uvicorn 자체 로거들(uvicorn / uvicorn.error / uvicorn.access)은 자기
    # 핸들러를 따로 붙이므로, 여기서도 같은 포맷을 강제로 씌워 시간이 찍히게
    # 한다. uvicorn이 나중에 다시 설정하더라도(REPLACE) 매 요청마다 결국
    # 이 핸들러를 거치도록 propagate는 그대로 True 유지.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
