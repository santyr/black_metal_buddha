"""PayPal refund reservations, reconciliation and provider isolation."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Order,Refund,Job,PaymentEvent
from app.refunds import request_refund,RefundError,submit_refund_request
from app.payments.paypal import PayPalRetryableError,cents_to_decimal
from app.payments.paypal_capture import capture_paypal_order
from app.payments.paypal_refunds import reconcile_paypal_refund,apply_paypal_reversal
from test_paypal_checkout import checkout_database
from test_paypal_reconcile import frozen


def paid(factory,identity):
    provider=frozen(factory,identity);provider.remote['status']='APPROVED'
    with factory() as session: capture_paypal_order(session,session.get(Order,identity),config=provider.config,client=provider)
    provider.refund_keys=[];provider.refunds={};provider.refund_status='COMPLETED'
    def refund(capture_id,*,amount_cents,currency,request_id):
        assert capture_id=='CAPTURE' and currency=='USD'
        provider.refund_keys.append(request_id)
        identity=next((key for key,value in provider.refunds.items() if value['custom_id']==request_id),None) or 'REFUND'+str(len(provider.refunds)+1)
        data={'id':identity,'status':provider.refund_status,'amount':{'currency_code':'USD','value':cents_to_decimal(amount_cents)},
              'custom_id':request_id,'links':[{'rel':'up','href':provider.config.paypal_api_base+'/v2/payments/captures/CAPTURE'}]}
        provider.refunds[identity]=data
        provider.remote['purchase_units'][0]['payments']['refunds']=list(provider.refunds.values())
        return deepcopy(data)
    provider.refund_capture=refund
    provider.get_refund=lambda identity:deepcopy(provider.refunds[identity])
    return provider


def test_partial_then_remaining_full_refund(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    with factory() as session:
        order=session.get(Order,identity)
        first=request_refund(session,order,amount_cents=500,reason='partial',client=provider)
        assert first.payment_provider=='paypal' and first.paypal_refund_id=='REFUND1'
        assert first.square_refund_id is None and order.refunded_cents==500 and order.refund_state=='PARTIAL'
        second=request_refund(session,order,amount_cents=None,reason='remaining',client=provider)
        assert second.amount_cents==3608 and order.order_state=='REFUNDED'
        assert order.payment_state=='COMPLETED' and len(provider.refund_keys)==2
        assert len(session.scalars(select(Job).where(Job.job_type.like('SEND_REFUND_CONFIRMATION:%'))).all())==2


def test_over_refund_and_wrong_provider_never_call_remote(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    with factory() as session:
        order=session.get(Order,identity)
        with pytest.raises(RefundError): request_refund(session,order,amount_cents=4109,reason='x',client=provider)
        with pytest.raises(RefundError): request_refund(session,order,amount_cents=100,reason='x',client=object())
        order.square_payment_id='WRONG';session.commit()
        with pytest.raises(RefundError): request_refund(session,order,amount_cents=100,reason='x',client=provider)
        assert provider.refund_keys==[]


def test_lost_refund_response_reconciles_exact_request(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity);original=provider.refund_capture
    def lost(*args,**kwargs):
        original(*args,**kwargs);raise PayPalRetryableError('lost')
    provider.refund_capture=lost
    with factory() as session:
        with pytest.raises(PayPalRetryableError): request_refund(session,session.get(Order,identity),amount_cents=100,reason='x',client=provider)
        refund=session.scalar(select(Refund));key=refund.paypal_request_id
        assert refund.status=='REQUESTED'
    provider.refund_capture=original
    with factory() as session:
        refund=session.scalar(select(Refund));order=session.get(Order,identity)
        submit_refund_request(session,refund,order,client=provider)
        assert refund.status=='COMPLETED' and order.refunded_cents==100
    assert provider.refund_keys==[key]


@pytest.mark.parametrize('status,expected',[('PENDING','PENDING'),('FAILED','FAILED')])
def test_noncompleted_refund_preserves_receipts_and_jobs(checkout_database,status,expected):
    factory,identity=checkout_database;provider=paid(factory,identity);provider.refund_status=status
    with factory() as session:
        order=session.get(Order,identity);refund=request_refund(session,order,amount_cents=100,reason='x',client=provider)
        assert refund.status==expected and order.refunded_cents==0 and order.payment_state=='COMPLETED'
        assert session.scalars(select(Job).where(Job.job_type.like('SEND_REFUND_CONFIRMATION:%'))).all()==[]
        if status=='PENDING':
            provider.refunds[refund.paypal_refund_id]['status']='COMPLETED'
            reconcile_paypal_refund(session,order,refund.paypal_refund_id,client=provider)
            assert order.refunded_cents==100


def test_concurrent_unknown_refunds_share_one_reservation(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    def lost(*args,**kwargs):
        provider.refund_keys.append(kwargs['request_id']);raise PayPalRetryableError('lost')
    provider.refund_capture=lost
    def run():
        with factory() as session:
            with pytest.raises(PayPalRetryableError): request_refund(session,session.get(Order,identity),amount_cents=100,reason='x',client=provider)
    with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(lambda _:run(),range(2)))
    with factory() as session: assert len(session.scalars(select(Refund)).all())==1
    assert len(set(provider.refund_keys))==1


def test_dashboard_refund_is_imported_once_without_second_fulfillment(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    provider.refund_capture('CAPTURE',amount_cents=4108,currency='USD',request_id='dashboard')
    with factory() as session:
        order=session.get(Order,identity)
        for _ in range(2): reconcile_paypal_refund(session,order,'REFUND1',client=provider)
        assert order.refunded_cents==4108 and order.order_state=='REFUNDED'
        capture_paypal_order(session,order,config=provider.config,client=provider)
        assert order.order_state=='REFUNDED'
        assert len(session.scalars(select(Refund)).all())==1
        assert len(session.scalars(select(Job).where(Job.job_type=='SUBMIT_PRINTFUL_ORDER')).all())==1


def test_reversal_blocks_old_completion_and_flags_owner_attention(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    with factory() as session:
        order=session.get(Order,identity);order.fulfillment_state='INPROCESS';session.commit()
        session.add(PaymentEvent(provider='paypal',provider_event_id='REVERSE',provider_payment_id='CAPTURE',event_type='PAYMENT.CAPTURE.REVERSED',payload_hash='a'*64,processing_result='REVERSAL_QUEUED'));session.commit()
        apply_paypal_reversal(session,order,client=provider)
        assert order.payment_state=='REVERSED' and order.order_state=='PAYMENT_REVERSED'
        assert capture_paypal_order(session,order,config=provider.config,client=provider)=='REVERSED'
        assert len(session.scalars(select(Job).where(Job.job_type=='SUBMIT_PRINTFUL_ORDER')).all())==1


def test_unknown_refund_expiry_requires_review(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    def lost(*_,**kwargs): raise PayPalRetryableError('lost')
    provider.refund_capture=lost
    with factory() as session:
        order=session.get(Order,identity)
        with pytest.raises(PayPalRetryableError): request_refund(session,order,amount_cents=100,reason='x',client=provider)
        refund=session.scalar(select(Refund));refund.paypal_requested_at=datetime.now(timezone.utc)-timedelta(hours=7);session.commit()
        with pytest.raises(RefundError,match='reconciliation'): submit_refund_request(session,refund,order,client=provider)


@pytest.mark.parametrize('case',['amount','currency','capture'])
def test_refund_mismatch_never_alters_aggregate(checkout_database,case):
    factory,identity=checkout_database;provider=paid(factory,identity)
    provider.refund_capture('CAPTURE',amount_cents=100,currency='USD',request_id='dashboard')
    data=provider.refunds['REFUND1']
    if case=='amount':data['amount']['value']='100.00'
    elif case=='currency':data['amount']['currency_code']='CAD'
    else:data['links'][0]['href']=provider.config.paypal_api_base+'/v2/payments/captures/FOREIGN'
    with factory() as session:
        order=session.get(Order,identity)
        with pytest.raises(RefundError): reconcile_paypal_refund(session,order,'REFUND1',client=provider)
        session.rollback();session.refresh(order)
        assert order.refunded_cents==0


def test_reversal_without_verified_event_cannot_mutate_payment(checkout_database):
    factory,identity=checkout_database;provider=paid(factory,identity)
    with factory() as session:
        order=session.get(Order,identity)
        with pytest.raises(RefundError,match='verified'): apply_paypal_reversal(session,order,client=provider)
        assert order.payment_state=='COMPLETED'


def test_timer_imports_dashboard_refund_without_callback(checkout_database):
    from app.reconcile import reconcile_orders
    factory,identity=checkout_database;provider=paid(factory,identity)
    provider.refund_capture('CAPTURE',amount_cents=4108,currency='USD',request_id='dashboard')
    with factory() as session:
        result=reconcile_orders(session,paypal_client=provider)
        assert result['refund_errors']==0
        assert session.get(Order,identity).refunded_cents==4108
