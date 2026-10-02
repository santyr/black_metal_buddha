(() => {
  if (document.querySelector('[data-order-pending]')) {
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
    }
  } catch (_) { /* The order remains viewable when browser storage is disabled. */ }
})();
