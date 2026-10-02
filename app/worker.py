from __future__ import annotations

import time

from .db import SessionLocal, init_db
from .jobs import process_pending_jobs
from .settings import settings


def main() -> None:
    if settings.app_env != "production":
        init_db()
    while True:
        with SessionLocal() as session:
            process_pending_jobs(session)
        time.sleep(10)


if __name__ == "__main__":
    main()
