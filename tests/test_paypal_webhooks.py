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
