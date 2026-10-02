import os
from pathlib import Path
import sqlite3
import subprocess
import sys


def test_refund_migration_preserves_rows_and_blocks_unsafe_downgrade(tmp_path):
    path = tmp_path / 'migration.db'
    env = {**os.environ, 'APP_ENV': 'development', 'DATABASE_URL': f'sqlite:///{path}',
           'PHASE1_API_ENABLED': 'false', 'PRINTFUL_MODE': 'disabled'}
    root = Path(__file__).resolve().parents[1]
    def alembic(*args, check=True):
        return subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root,
                              env=env, check=check, capture_output=True, text=True, timeout=30)
    alembic('upgrade', '0006_canary_marker')
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO refunds (id,order_id,square_refund_id,amount_cents,currency,status,reason,created_at,updated_at) VALUES (1,'order','REF-OLD',1000,'USD','COMPLETED','Test','2026-09-20','2026-09-20')")
    alembic('upgrade', 'head')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT square_refund_id,idempotency_key FROM refunds WHERE id=1').fetchone() == ('REF-OLD', None)
        db.execute("INSERT INTO refunds (id,order_id,amount_cents,currency,status,reason,created_at,updated_at,idempotency_key) VALUES (2,'order',1000,'USD','REQUESTED','Test','2026-09-20','2026-09-20','durable-key')")
    result = alembic('downgrade', '0006_canary_marker', check=False)
    assert result.returncode != 0
    assert 'Resolve outstanding refund requests' in result.stderr
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM refunds WHERE id=2')
    alembic('downgrade', '0006_canary_marker')
    alembic('upgrade', 'head')
