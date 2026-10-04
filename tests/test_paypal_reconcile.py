"""Mocked authoritative capture recovery; no live financial requests."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models import Order, Job
from app.orders import OrderError
from app.payments.paypal import PayPalRetryableError
from app.payments.paypal_checkout import prepare_paypal_checkout
from app.payments.paypal_capture import capture_paypal_order, apply_paypal_capture
from test_paypal_checkout import checkout_database, CheckoutProvider, EstimateProvider, checkout_config


class CaptureProvider(CheckoutProvider):
    def __init__(self,order):
        super().__init__(order)
        self.capture_keys=[]
        self.capture={'id':'CAPTURE','status':'COMPLETED', 'final_capture':True,
            'amount':{'currency_code':'USD','value':'41.08'},
            'payee':{'merchant_id':'MERCHANT'},
            'supplementary_data':{'related_ids':{'order_id':'PPORDER'}}}
    def capture_order(self,identity,*,request_id):
        assert identity=='PPORDER'
        self.capture_keys.append(request_id)
        self.remote['status']='COMPLETED'
        self.remote['purchase_units'][0]['payments']={'captures':[deepcopy(self.capture)]}
        return self.remote
    def get_capture(self,identity):
        assert identity=='CAPTURE'
        return deepcopy(self.capture)


def frozen(factory,identity):
    with factory() as session:
        order=session.get(Order,identity); provider=CaptureProvider(order)
        prepare_paypal_checkout(session,order,config=provider.config,client=provider,printful_client=EstimateProvider())
    return provider


def test_approval_only_never_fulfills(checkout_database):
    factory,identity=checkout_database; provider=frozen(factory,identity)
    with factory() as session:
        order=session.get(Order,identity)
        assert capture_paypal_order(session,order,config=provider.config,client=provider) == 'CREATED'
        assert order.payment_state=='PENDING' and session.scalars(select(Job)).all()==[]
        assert provider.capture_keys==[]


def test_completed_capture_pays_and_enqueues_exactly_once(checkout_database):
    factory,identity=checkout_database; provider=frozen(factory,identity)
    provider.remote['status']='APPROVED'
    with factory() as session:
        order=session.get(Order,identity)
        for _ in range(2):
            assert capture_paypal_order(session,order,config=provider.config,client=provider)=='COMPLETED'
        assert order.payment_state=='COMPLETED' and order.paypal_capture_id=='CAPTURE'
        assert order.square_payment_id is None and len(provider.capture_keys)==1
        assert {job.job_type for job in session.scalars(select(Job)).all()}=={'SUBMIT_PRINTFUL_ORDER','SEND_ORDER_CONFIRMATION'}


def test_lost_capture_response_reconciles_without_second_capture(checkout_database):
    factory,identity=checkout_database; provider=frozen(factory,identity); provider.remote['status']='APPROVED'
    original=provider.capture_order
    def lost(identity,*,request_id):
        original(identity,request_id=request_id)
        raise PayPalRetryableError('lost')
    provider.capture_order=lost
    with factory() as session:
        with pytest.raises(PayPalRetryableError):
            capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
    with factory() as session:
        assert capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)=='COMPLETED'
        assert len(session.scalars(select(Job)).all())==2
    assert len(provider.capture_keys)==1


@pytest.mark.parametrize('status',['PENDING','DECLINED'])
def test_noncompleted_capture_never_enqueues(checkout_database,status):
    factory,identity=checkout_database; provider=frozen(factory,identity); provider.remote['status']='APPROVED'
    provider.capture['status']=status
    with factory() as session:
        order=session.get(Order,identity)
        assert capture_paypal_order(session,order,config=provider.config,client=provider)==status
        assert order.payment_state!='COMPLETED' and session.scalars(select(Job)).all()==[]


@pytest.mark.parametrize('case',['merchant','amount','currency','order','reference','shipping','membership'])
def test_authoritative_mismatch_is_not_paid(checkout_database,case):
    factory,identity=checkout_database; provider=frozen(factory,identity); provider.remote['status']='APPROVED'
    provider.capture_order('PPORDER',request_id='fixture')
    if case=='merchant': provider.capture['payee']['merchant_id']='OTHER'
    elif case=='amount': provider.capture['amount']['value']='0.01'
    elif case=='currency': provider.capture['amount']['currency_code']='CAD'
    elif case=='order': provider.capture['supplementary_data']['related_ids']['order_id']='FOREIGN'
    elif case=='reference': provider.remote['purchase_units'][0]['custom_id']='FOREIGN'
    elif case=='shipping': provider.remote['purchase_units'][0]['shipping']['address']['country_code']='CA'
    else: provider.capture['id']='FOREIGN'
    with factory() as session:
        order=session.get(Order,identity)
        with pytest.raises(OrderError): capture_paypal_order(session,order,config=provider.config,client=provider)
        session.refresh(order)
        assert order.payment_state=='PENDING' and session.scalars(select(Job)).all()==[]


def test_concurrent_captures_have_one_key_and_fulfillment_job(checkout_database):
    factory,identity=checkout_database; provider=frozen(factory,identity); provider.remote['status']='APPROVED'
    def run():
        with factory() as session:
            return capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
    with ThreadPoolExecutor(max_workers=2) as pool: assert set(pool.map(lambda _:run(),range(2)))=={'COMPLETED'}
    with factory() as session: assert len(session.scalars(select(Job)).all())==2
    assert len(set(provider.capture_keys))==1


def test_authoritative_completion_repairs_missing_jobs(checkout_database):
    factory,identity=checkout_database; provider=frozen(factory,identity); provider.remote['status']='APPROVED'
    with factory() as session:
        capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
        for job in session.scalars(select(Job)).all(): session.delete(job)
        session.commit()
        capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
        assert len(session.scalars(select(Job)).all())==2

from app.reconcile import reconcile_orders


def test_timer_completes_captured_order_without_browser_or_webhook(checkout_database):
    factory,identity=checkout_database;provider=frozen(factory,identity);provider.remote['status']='APPROVED'
    provider.capture_order('PPORDER',request_id='fixture')
    with factory() as session:
        result=reconcile_orders(session,paypal_client=provider)
        assert result['paypal_checked']==1 and result['paypal_errors']==0
        assert session.get(Order,identity).payment_state=='COMPLETED'
        assert len(session.scalars(select(Job)).all())==2


def test_uncertain_capture_cannot_repeat_after_retention_but_can_recover(checkout_database):
    from datetime import datetime,timedelta,timezone
    factory,identity=checkout_database;provider=frozen(factory,identity);provider.remote['status']='APPROVED'
    with factory() as session:
        order=session.get(Order,identity)
        order.paypal_capture_request_id='original-key'
        order.paypal_capture_requested_at=datetime.now(timezone.utc)-timedelta(hours=7)
        session.commit()
        with pytest.raises(OrderError,match='reconciliation'):
            capture_paypal_order(session,order,config=provider.config,client=provider)
        assert provider.capture_keys==[]
        provider.capture_order('PPORDER',request_id='original-key')
        assert capture_paypal_order(session,order,config=provider.config,client=provider)=='COMPLETED'


def test_actual_provider_receipt_fee_and_net_survive_restart(checkout_database):
    factory,identity=checkout_database;provider=frozen(factory,identity);provider.remote['status']='APPROVED'
    provider.capture['seller_receivable_breakdown']={
        'gross_amount':{'currency_code':'USD','value':'41.08'},
        'paypal_fee':{'currency_code':'USD','value':'1.50'},
        'net_amount':{'currency_code':'USD','value':'39.58'}}
    with factory() as session:
        capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
    with factory() as session:
        order=session.get(Order,identity)
        assert order.paypal_fee_cents==150 and order.paypal_net_cents==3958
        assert order.paypal_capture_json is not None and order.total_cents==4108
