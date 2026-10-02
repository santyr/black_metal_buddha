from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.jobs as jobs
from app.db import Base
from app.models import Job, Order, Refund
from app.refunds import RefundError, apply_refund_status, request_refund
from test_reconcile import create_test_order


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "backend.db"}',
                           connect_args={'check_same_thread': False, 'timeout': 10})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    with Session() as session:
        order = create_test_order(session)
        order.payment_state = 'COMPLETED'
        order.order_state = 'PAID'
        order.square_payment_id = 'PAY-DURABLE'
        session.commit()
        order_id = order.id
    yield Session, order_id
    engine.dispose()


def test_workers_cannot_process_an_active_job_twice(database, monkeypatch):
    Session, order_id = database
    with Session() as session:
        session.add(Job(order_id=order_id, job_type='SEND_ORDER_CONFIRMATION'))
        session.commit()
    entered, release = Event(), Event()
    def handler(session, job, **_):
        entered.set()
        assert release.wait(5)
        job.state = 'COMPLETED'
        session.commit()
    monkeypatch.setattr(jobs, 'process_email_job', handler)
    def run():
        with Session() as session:
            return jobs.process_pending_jobs(session)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run)
        assert entered.wait(5)
        try:
            assert pool.submit(run).result(timeout=5) == 0
        finally:
            release.set()
        assert first.result(timeout=5) == 1


def test_crashed_job_is_reclaimed_but_live_lease_is_not(database, monkeypatch):
    Session, order_id = database
    now = datetime.now(timezone.utc)
    with Session() as session:
        session.add_all([
            Job(order_id=order_id, job_type='SEND_STALE', state='RUNNING', locked_at=now - timedelta(minutes=16)),
            Job(order_id=order_id, job_type='SEND_LIVE', state='RUNNING', locked_at=now),
            Job(order_id=order_id, job_type='UNSUPPORTED', state='PENDING'),
        ])
        session.commit()
    def handler(session, job, **_):
        job.state = 'COMPLETED'
        session.commit()
    monkeypatch.setattr(jobs, 'process_email_job', handler)
    with Session() as session:
        assert jobs.process_pending_jobs(session) == 2
        state = {j.job_type: j for j in session.scalars(select(Job)).all()}
        assert state['SEND_STALE'].state == 'COMPLETED'
        assert state['SEND_STALE'].locked_at is None
        assert state['SEND_LIVE'].state == 'RUNNING'
        assert state['UNSUPPORTED'].state == 'FAILED'


def test_failed_db_transaction_does_not_kill_worker_batch(database, monkeypatch):
    Session, order_id = database
    with Session() as session:
        session.add_all([Job(order_id=order_id, job_type='SEND_BROKEN'),
                         Job(order_id=order_id, job_type='SEND_HEALTHY')])
        session.commit()
    def handler(session, job, **_):
        if job.job_type == 'SEND_BROKEN':
            session.add(Job(order_id=order_id, job_type='SEND_BROKEN'))
            session.commit()  # Force an actual failed SQL transaction.
        job.state = 'COMPLETED'
        session.commit()
    monkeypatch.setattr(jobs, 'process_email_job', handler)
    with Session() as session:
        assert jobs.process_pending_jobs(session) == 2
        state = {j.job_type: j for j in session.scalars(select(Job)).all()}
        assert state['SEND_BROKEN'].state == 'PENDING'
        assert state['SEND_BROKEN'].attempt_count == 1
        assert state['SEND_HEALTHY'].state == 'COMPLETED'


def test_uncertain_refund_survives_restart_and_reuses_key(database):
    Session, order_id = database
    class Provider:
        keys = []
        def refund_payment(self, **kwargs):
            self.keys.append(kwargs['idempotency_key'])
            if len(self.keys) == 1:
                raise httpx.ReadTimeout('Response lost after provider accepted refund')
            return {'id': 'REF-RECOVERED', 'status': 'COMPLETED',
                    'payment_id': 'PAY-DURABLE', 'amount_money': {'amount': 1000, 'currency': 'USD'}}
    provider = Provider()
    with Session() as session:
        with pytest.raises(httpx.ReadTimeout):
            request_refund(session, session.get(Order, order_id), amount_cents=1000, reason='Test', client=provider)
    with Session() as session:
        assert session.scalar(select(Refund)).status == 'REQUESTED'
        assert session.get(Order, order_id).refund_state == 'PENDING'
        refund = request_refund(session, session.get(Order, order_id), amount_cents=1000, reason='Test', client=provider)
        assert refund.status == 'COMPLETED'
        assert session.get(Order, order_id).refunded_cents == 1000
        assert len(session.scalars(select(Refund)).all()) == 1
    assert len(provider.keys) == 2
    assert len(set(provider.keys)) == 1


def test_pending_refund_blocks_second_request_and_rejection_releases_it(database):
    Session, order_id = database
    class Provider:
        calls = 0
        def refund_payment(self, **kwargs):
            self.calls += 1
            return {'id': f'REF-{self.calls}', 'status': 'PENDING'}
    provider = Provider()
    with Session() as session:
        order = session.get(Order, order_id)
        refund = request_refund(session, order, amount_cents=1000, reason='Test', client=provider)
        with pytest.raises(RefundError, match='already pending'):
            request_refund(session, order, amount_cents=1000, reason='Test', client=provider)
        session.rollback()
        assert provider.calls == 1
        apply_refund_status(session, refund, order, status='REJECTED')
        assert order.refund_state == 'FAILED'
        apply_refund_status(session, refund, order, status='PENDING')
        assert refund.status == 'REJECTED'
        replacement = request_refund(session, order, amount_cents=1000, reason='Test', client=provider)
        assert replacement.idempotency_key != refund.idempotency_key
        assert provider.calls == 2


def test_concurrent_refund_completions_are_counted_once(database):
    Session, order_id = database
    with Session() as session:
        refund = Refund(order_id=order_id, square_refund_id='REF-RACE', amount_cents=1000,
                        currency='USD', status='PENDING')
        session.add(refund)
        session.commit()
        refund_id = refund.id
    def complete():
        with Session() as session:
            apply_refund_status(session, session.get(Refund, refund_id), session.get(Order, order_id), status='COMPLETED')
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(complete) for _ in range(2)]
        for future in futures:
            future.result(timeout=10)
    with Session() as session:
        assert session.get(Order, order_id).refunded_cents == 1000
        assert len(session.scalars(select(Job)).all()) == 1


def test_pending_refund_pauses_fulfillment(database):
    Session, order_id = database
    with Session() as session:
        order = session.get(Order, order_id)
        order.refund_state = 'PENDING'
        job = Job(order_id=order_id, job_type='SUBMIT_PRINTFUL_ORDER')
        session.add(job)
        session.commit()
        jobs.process_submit_printful_job(session, job)
        assert job.state == 'PENDING'
        assert 'refund' in job.last_error
        assert order.printful_order_id is None


def test_reconciliation_rotates_beyond_first_batch(database):
    from app.reconcile import reconcile_orders
    Session, order_id = database
    with Session() as session:
        original = session.get(Order, order_id)
        # Keep the fixture outside the three oldest records under test.
        original.updated_at = datetime.now(timezone.utc)
        for index in range(3):
            number = f'BMB-ROTATE-{index}'
            session.add(Order(id=number, order_number=number, email='audit@example.com',
                              customer_name='Audit', ship_address1='1 Test St', ship_city='Denver',
                              ship_state='CO', ship_postal_code='80202', ship_country='US',
                              currency='USD', subtotal_cents=0, total_cents=0,
                              square_order_id=number,
                              updated_at=datetime.now(timezone.utc) - timedelta(days=3-index)))
        session.commit()
    class Provider:
        checked = []
        def get_order(self, order_id):
            self.checked.append(order_id)
            return {'reference_id': order_id, 'line_items': [], 'total_money': {'amount': 0, 'currency': 'USD'}}
        def payment_id_from_order(self, _):
            return None
    provider = Provider()
    for _ in range(3):
        with Session() as session:
            assert reconcile_orders(session, square_client=provider, limit=1)['square_checked'] == 1
    assert len(set(provider.checked)) == 3


def test_reconciliation_resolves_persisted_refund_request(database):
    from app.reconcile import reconcile_orders
    Session, order_id = database
    with Session() as session:
        session.add(Refund(order_id=order_id, amount_cents=1000, currency='USD', status='REQUESTED',
                           idempotency_key='persisted-key', reason='Test'))
        session.commit()
    class Provider:
        def refund_payment(self, **kwargs):
            assert kwargs['idempotency_key'] == 'persisted-key'
            return {'id': 'REF-RECONCILED', 'status': 'COMPLETED'}
    with Session() as session:
        result = reconcile_orders(session, square_client=Provider())
        assert result['refunds_checked'] == 1
        assert result['refund_errors'] == 0
        assert session.get(Order, order_id).refunded_cents == 1000


def test_refund_webhook_imports_external_refund_and_retries_unresolved_requests(database, monkeypatch):
    from fastapi.testclient import TestClient
    import app.api_phase1 as api
    from app.main import app
    Session, order_id = database
    def dependency():
        with Session() as session:
            yield session
    app.dependency_overrides[api.db_session] = dependency
    monkeypatch.setattr(api, 'verify_square_webhook', lambda *_: True)
    event = {'event_id': 'EXTERNAL-REFUND', 'type': 'refund.updated',
             'data': {'object': {'refund': {'id': 'REF-EXTERNAL', 'payment_id': 'PAY-DURABLE',
                      'status': 'COMPLETED', 'amount_money': {'amount': 1000, 'currency': 'USD'}}}}}
    try:
        with Session() as session:
            session.add(Refund(order_id=order_id, amount_cents=1000, currency='USD', status='REQUESTED',
                               idempotency_key='unresolved-key'))
            session.commit()
        with TestClient(app) as client:
            response = client.post('/api/v1/webhooks/square', json=event)
            assert response.status_code == 503
            with Session() as session:
                refund = session.scalar(select(Refund))
                refund.status = 'FAILED'
                session.commit()
            response = client.post('/api/v1/webhooks/square', json=event)
            assert response.status_code == 200, response.text
            assert client.post('/api/v1/webhooks/square', json=event).json()['duplicate'] is True
        with Session() as session:
            assert session.get(Order, order_id).refunded_cents == 1000
    finally:
        app.dependency_overrides.pop(api.db_session, None)


def test_admin_refund_validation_and_uncertain_response(database, monkeypatch):
    from dataclasses import replace
    from urllib.parse import unquote_plus
    from fastapi.testclient import TestClient
    import app.admin as admin
    from app.main import app
    Session, order_id = database
    with Session() as session:
        number = session.get(Order, order_id).order_number
    def dependency():
        with Session() as session:
            yield session
    class Provider:
        def refund_payment(self, **kwargs):
            raise httpx.ReadTimeout('Uncertain provider outcome')
    monkeypatch.setattr(admin, 'settings', replace(admin.settings, admin_refunds_enabled=True))
    monkeypatch.setattr(admin, 'verify_csrf', lambda *_: None)
    monkeypatch.setattr(admin, 'SquareClient', Provider)
    app.dependency_overrides[admin.db_session] = dependency
    app.dependency_overrides[admin.require_admin] = lambda: 'audit-owner'
    try:
        with TestClient(app) as client:
            path = f'/admin/orders/{number}/refund'
            assert client.post(path, data={'amount': 'Infinity'}, follow_redirects=False).status_code == 400
            response = client.post(path, data={'amount': '10', 'reason': 'Test'}, follow_redirects=False)
            assert response.status_code == 303
            assert 'awaiting confirmation' in unquote_plus(response.headers['location'])
        with Session() as session:
            assert session.scalar(select(Refund)).status == 'REQUESTED'
    finally:
        app.dependency_overrides.pop(admin.db_session, None)
        app.dependency_overrides.pop(admin.require_admin, None)
