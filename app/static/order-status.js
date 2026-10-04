(() => {
  const pending = document.querySelector('[data-order-pending]');
  if (pending) {
    const params = new URLSearchParams(window.location.search);
    if (params.has('PayerID') && params.has('token')) {
      try {
        const token = sessionStorage.getItem('bmb-order-token-' + pending.dataset.orderNumber);
        if (token) fetch('/api/phase1/orders/' + encodeURIComponent(pending.dataset.orderNumber) + '/paypal-capture', {
          method: 'POST', headers: {'X-BMB-Order-Token': token, 'Content-Type': 'application/json'}, body: '{}'
        }).then((response) => response.ok ? response.json() : null).then((order) => {
          if (order?.payment_state === 'COMPLETED') window.location.reload();
        }).catch(() => {});
      } catch (_) { /* Verified webhook processing confirms without storage. */ }
    }
    let attempts = 0;
    async function checkPayment() {
      attempts += 1;
      try {
        const response = await fetch(window.location.href, { cache: 'no-store' });
        if (response.ok) {
          const page = new DOMParser().parseFromString(await response.text(), 'text/html');
          if (page.querySelector('main') && !page.querySelector('[data-order-pending]')) {
            window.location.reload();
            return;
          }
        }
      } catch (_) { /* A temporary connection failure can be retried. */ }
      if (attempts < 24) setTimeout(checkPayment, 5000);
    }
    setTimeout(checkPayment, 5000);
  }
  const marker = document.querySelector('[data-order-complete]');
  if (!marker || !window.BMBCart) return;
  try {
    const active = sessionStorage.getItem('bmb-active-order');
    if (active && active === marker.dataset.orderNumber) {
      window.BMBCart.clear();
      sessionStorage.removeItem('bmb-active-order');
      sessionStorage.removeItem('bmb-order-token-' + active);
    }
  } catch (_) { /* The order remains viewable when browser storage is disabled. */ }
})();
