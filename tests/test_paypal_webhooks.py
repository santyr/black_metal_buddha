"""Verified events durably schedule authoritative capture, even without return."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api_phase1 as api
from app.main import app
from app.models import Order, Job, PaymentEvent
from app.jobs import process_paypal_capture_job
from app.payments.paypal import PayPalRetryableError
from test_paypal_checkout import checkout_database, checkout_config
from test_paypal_reconcile import frozen


@pytest.fixture
def webhook_app(checkout_database,monkeypatch):
    factory,identity=checkout_database; provider=frozen(factory,identity)
    def db():
        with factory() as session: yield session
    app.dependency_overrides[api.db_session]=db
    monkeypatch.setattr(api,'settings',checkout_config(phase1_api_enabled=False))
    monkeypatch.setattr(api,'PayPalClient',lambda *_:provider)
    provider.verify_webhook=lambda *_:True
    provider.close=lambda:None
    yield factory,identity,provider
    app.dependency_overrides.clear()


def event(kind='CHECKOUT.ORDER.APPROVED', identity='EV1'):
    resource={'id':'PPORDER'} if kind.startswith('CHECKOUT.') else {
        'id':'CAPTURE','supplementary_data':{'related_ids':{'order_id':'PPORDER'}}}
    # Spoofed event amount is ignored in favor of authoritative provider calls.
    resource['amount']={'currency_code':'USD','value':'0.01'}
    return {'id':identity,'event_type':kind,'resource':resource}


def test_verified_approval_queues_durable_capture_with_checkout_closed(webhook_app):
    factory,identity,provider=webhook_app
    with TestClient(app) as browser:
        for _ in range(2): assert browser.post('/api/phase1/webhooks/paypal',json=event()).status_code==200
    with factory() as session:
        assert session.get(Order,identity).payment_state=='PENDING'
        assert [job.job_type for job in session.scalars(select(Job)).all()]==['CAPTURE_PAYPAL_ORDER']
        assert len(session.scalars(select(PaymentEvent)).all())==1


@pytest.mark.parametrize('outage',[False,True])
def test_unverified_or_outage_events_do_not_persist(webhook_app,outage):
    factory,identity,provider=webhook_app
    def verify(*_):
        if outage: raise PayPalRetryableError('outage')
        return False
    provider.verify_webhook=verify
    with TestClient(app) as browser:
        result=browser.post('/api/phase1/webhooks/paypal',json=event())
    assert result.status_code==(503 if outage else 401)
    with factory() as session:
        assert session.scalars(select(PaymentEvent)).all()==[]
        assert session.scalars(select(Job)).all()==[]
        assert session.get(Order,identity).payment_state=='PENDING'


def test_closed_browser_is_completed_by_capture_job(webhook_app):
    factory,identity,provider=webhook_app; provider.remote['status']='APPROVED'
    with TestClient(app) as browser: assert browser.post('/api/phase1/webhooks/paypal',json=event()).status_code==200
    with factory() as session:
        job=session.scalar(select(Job));process_paypal_capture_job(session,job,config=provider.config,client=provider)
        assert job.state=='COMPLETED' and session.get(Order,identity).payment_state=='COMPLETED'
        assert len(session.scalars(select(Job).where(Job.job_type=='SUBMIT_PRINTFUL_ORDER')).all())==1


def test_pending_capture_job_waits_without_fulfillment(webhook_app):
    factory,identity,provider=webhook_app; provider.remote['status']='APPROVED';provider.capture['status']='PENDING'
    with TestClient(app) as browser: browser.post('/api/phase1/webhooks/paypal',json=event())
    with factory() as session:
        job=session.scalar(select(Job));process_paypal_capture_job(session,job,config=provider.config,client=provider)
        assert job.state=='PENDING' and session.get(Order,identity).payment_state=='PENDING'
        assert session.scalars(select(Job).where(Job.job_type=='SUBMIT_PRINTFUL_ORDER')).all()==[]


def test_capture_event_reawakens_waiting_or_failed_job(webhook_app):
    factory,identity,provider=webhook_app;provider.remote['status']='APPROVED'
    with TestClient(app) as browser: browser.post('/api/phase1/webhooks/paypal',json=event())
    with factory() as session:
        job=session.scalar(select(Job));job.state='FAILED';job.attempt_count=8;session.commit()
    with TestClient(app) as browser:
        assert browser.post('/api/phase1/webhooks/paypal',json=event('PAYMENT.CAPTURE.COMPLETED','EV2')).status_code==200
    with factory() as session: assert session.scalar(select(Job)).state=='PENDING'


def test_event_and_job_are_atomic_on_insertion_failure(webhook_app,monkeypatch):
    factory,identity,provider=webhook_app
    def fail(*_): raise RuntimeError('database failure')
    monkeypatch.setattr(api,'enqueue_job',fail)
    with TestClient(app,raise_server_exceptions=False) as browser:
        assert browser.post('/api/phase1/webhooks/paypal',json=event()).status_code>=500
    with factory() as session:
        assert session.scalars(select(PaymentEvent)).all()==[]
        assert session.scalars(select(Job)).all()==[]


def test_completed_capture_without_related_ids_is_resolved_authoritatively(webhook_app):
    factory,identity,provider=webhook_app;provider.remote['status']='APPROVED'
    payload=event('PAYMENT.CAPTURE.COMPLETED');del payload['resource']['supplementary_data']
    with TestClient(app) as browser:
        assert browser.post('/api/phase1/webhooks/paypal',json=payload).status_code==200
    with factory() as session: assert session.scalar(select(Job)).job_type=='CAPTURE_PAYPAL_ORDER'


def test_verified_reversal_never_recreates_fulfillment_job(webhook_app):
    from test_paypal_refunds import paid
    from app.payments.paypal_capture import capture_paypal_order
    factory,identity,_=webhook_app;provider=paid(factory,identity)
    provider.verify_webhook=lambda *_:True;provider.close=lambda:None
    import app.api_phase1 as api
    original=api.PayPalClient;api.PayPalClient=lambda *_:provider
    try:
        with TestClient(app) as browser:
            assert browser.post('/api/phase1/webhooks/paypal',json=event('PAYMENT.CAPTURE.REVERSED')).status_code==200
        with factory() as session:
            assert capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)=='REVERSED'
            assert session.get(Order,identity).payment_state=='REVERSED'
    finally: api.PayPalClient=original


def test_dashboard_refund_callback_queues_exact_refund_reconciliation(webhook_app):
    from test_paypal_refunds import paid
    from app.models import Refund
    from app.jobs import process_paypal_refund_job
    factory,identity,_=webhook_app;provider=paid(factory,identity)
    provider.refund_capture('CAPTURE',amount_cents=4108,currency='USD',request_id='dashboard')
    provider.verify_webhook=lambda *_:True;provider.close=lambda:None
    original=api.PayPalClient;api.PayPalClient=lambda *_:provider
    payload=event('PAYMENT.CAPTURE.REFUNDED');payload['resource']['id']='REFUND1'
    try:
        with TestClient(app) as browser:
            assert browser.post('/api/phase1/webhooks/paypal',json=payload).status_code==200
        with factory() as session:
            job=session.scalar(select(Job).where(Job.job_type.like('RECONCILE_PAYPAL_REFUND:%')))
            assert job is not None
            process_paypal_refund_job(session,job,config=provider.config,client=provider)
            assert job.state=='COMPLETED' and session.get(Order,identity).refunded_cents==4108
    finally: api.PayPalClient=original


def test_provider_verification_does_not_block_the_event_loop(webhook_app):
    import asyncio
    factory,identity,provider=webhook_app
    def verify(*_):
        try: asyncio.get_running_loop()
        except RuntimeError: return True
        pytest.fail('Synchronous provider HTTP is running on the ASGI event loop')
    provider.verify_webhook=verify
    with TestClient(app) as browser:
        assert browser.post('/api/phase1/webhooks/paypal',json=event()).status_code==200
