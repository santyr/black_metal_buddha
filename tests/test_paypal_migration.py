import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models import Order, Refund


def test_provider_migration_preserves_square_and_unbound_orders(tmp_path):
    path = tmp_path / 'provider.db'
    env = {**os.environ, 'APP_ENV':'development', 'DATABASE_URL':f'sqlite:///{path}',
           'PHASE1_API_ENABLED':'false', 'PRINTFUL_MODE':'disabled',
           'PRINTFUL_CATALOG_SYNC_ENABLED':'false'}
    root = Path(__file__).resolve().parents[1]
    def alembic(*args, check=True):
        return subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root,
            env=env, check=check, capture_output=True, text=True, timeout=30)
    alembic('upgrade', '0008_printful_catalog')
    with sqlite3.connect(path) as db:
        for identity, square_order, square_payment in [('square','SQ-ORDER','SQ-PAYMENT'), ('unbound',None,None)]:
            db.execute('''INSERT INTO orders (id,order_number,email,customer_name,ship_address1,
                ship_city,ship_state,ship_postal_code,ship_country,currency,subtotal_cents,
                discount_cents,shipping_cents,tax_cents,total_cents,payment_state,fulfillment_state,
                order_state,is_canary,refunded_cents,refund_state,created_at,updated_at,
                square_order_id,square_payment_id) VALUES (?,?, 'buyer@example.com','Buyer','Main',
                'Boston','MA','02108','US','USD',3500,0,0,0,3500,'PENDING','NOT_STARTED',
                'PENDING_PAYMENT',0,0,'NONE','2026-10-04','2026-10-04',?,?)''',
                (identity,'BMB-'+identity,square_order,square_payment))
        db.execute("""INSERT INTO refunds (id,order_id,square_refund_id,amount_cents,currency,status,
            created_at,updated_at,idempotency_key) VALUES (1,'square','SQ-REFUND',100,'USD',
            'COMPLETED','2026-10-04','2026-10-04','old-key')""")
    alembic('upgrade','head')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT payment_provider,square_order_id,square_payment_id,paypal_order_id FROM orders WHERE id="square"').fetchone() == ('square','SQ-ORDER','SQ-PAYMENT',None)
        assert db.execute('SELECT payment_provider FROM orders WHERE id="unbound"').fetchone() == (None,)
        assert db.execute('SELECT payment_provider,square_refund_id,idempotency_key,paypal_refund_id FROM refunds').fetchone() == ('square','SQ-REFUND','old-key',None)
        db.execute("UPDATE orders SET payment_provider='paypal',paypal_order_id='PP-ORDER',paypal_create_request_id='create-key',paypal_create_requested_at='2026-10-04' WHERE id='unbound'")
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE orders SET paypal_order_id='PP-ORDER' WHERE id='square'")
        db.execute("UPDATE orders SET paypal_capture_id='PP-CAPTURE',paypal_capture_request_id='capture-key',paypal_capture_requested_at='2026-10-04' WHERE id='unbound'")
        db.execute("UPDATE refunds SET paypal_refund_id='PP-REFUND',paypal_request_id='refund-key',paypal_requested_at='2026-10-04' WHERE id=1")
    engine = create_engine(f'sqlite:///{path}')
    with Session(engine) as session:
        saved = session.get(Order, 'unbound')
        assert saved.paypal_capture_id == 'PP-CAPTURE'
        assert saved.paypal_create_request_id == 'create-key'
        assert saved.paypal_create_requested_at is not None
    for model in (Order, Refund):
        actual = {column['name'] for column in inspect(engine).get_columns(model.__tablename__)}
        assert set(model.__table__.columns.keys()) == actual
    engine.dispose()
    result = alembic('downgrade','0008_printful_catalog',check=False)
    assert result.returncode != 0
    assert 'PayPal history' in result.stderr
    with sqlite3.connect(path) as db:
        for table in ('orders','refunds'):
            names = [column[1] for column in db.execute(f'PRAGMA table_info({table})') if column[1].startswith('paypal_')]
            db.execute(f'UPDATE {table} SET payment_provider=NULL, '+', '.join(f'{name}=NULL' for name in names))
    alembic('downgrade','0008_printful_catalog')
    alembic('upgrade','head')
