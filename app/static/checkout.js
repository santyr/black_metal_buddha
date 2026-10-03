(async () => {
  const app = document.querySelector('[data-checkout-app]');
  if (!app || !window.BMBCart || !window.BMBCart.phase1) return;
  await window.BMBCart.ready;

  const cart = window.BMBCart.read();
  const form = app.querySelector('[data-checkout-form]');
  const itemsEl = app.querySelector('[data-checkout-items]');
  const subtotalEl = app.querySelector('[data-checkout-subtotal]');
  const shippingEl = app.querySelector('[data-checkout-shipping]');
  const shippingStep = app.querySelector('[data-shipping-step]');
  const shippingRatesEl = app.querySelector('[data-shipping-rates]');
  const squareButton = app.querySelector('[data-square-button]');
  const quoteButton = app.querySelector('[data-quote-button]');
  const statusEl = app.querySelector('[data-checkout-status]');

  let orderNumber = null;
  let selectedShipping = null;

  function updateAddressLabels() {
    const canada = form.elements.country_code.value === 'CA';
    form.querySelector('label[for="checkout-state"]').textContent = canada ? 'Province' : 'State';
    form.querySelector('label[for="checkout-postal"]').textContent = canada ? 'Postal code' : 'ZIP code';
    form.elements.state.placeholder = canada ? 'ON' : 'CO';
  }

  form.elements.country_code.addEventListener('change', updateAddressLabels);
  updateAddressLabels();

  function setStatus(message, isError = false) {
    statusEl.textContent = message || '';
    statusEl.classList.toggle('is-error', Boolean(isError));
  }

  function errorMessage(error, fallback) {
    if (error && typeof error.detail === 'string') return error.detail;
    if (Array.isArray(error?.detail)) {
      return error.detail.map((item) => item.msg).filter(Boolean).join(' ') || fallback;
    }
    return fallback;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    });
    let data = null;
    try { data = await response.json(); } catch (_) { data = null; }
    if (!response.ok) {
      const error = new Error(errorMessage(data, 'Request failed.'));
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function renderCartSummary() {
    itemsEl.innerHTML = '';
    if (!cart.length) {
      const message = document.createElement('p');
      message.textContent = 'Your cart is empty.';
      itemsEl.appendChild(message);
      form.querySelectorAll('input, select, button').forEach((control) => {
        control.disabled = true;
      });
      return;
    }

    let subtotal = 0;
    let currency = 'USD';
    cart.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'checkout-item';

      const name = document.createElement('span');
      name.textContent = item.name + ' · ' + item.size + ' × ' + String(item.quantity || 1);

      const lineTotal = (Number(item.priceCents) || 0) * (Number(item.quantity) || 1);
      subtotal += lineTotal;
      currency = item.currency || currency;

      const price = document.createElement('strong');
      price.textContent = window.BMBCart.formatMoney(lineTotal, currency);

      row.append(name, price);
      itemsEl.appendChild(row);
    });

    subtotalEl.textContent = window.BMBCart.formatMoney(subtotal, currency);
  }

  function orderPayload() {
    const data = new FormData(form);
    const recipient = {
      name: String(data.get('name') || '').trim(),
      email: String(data.get('email') || '').trim(),
      phone: String(data.get('phone') || '').trim() || null,
      address1: String(data.get('address1') || '').trim(),
      address2: String(data.get('address2') || '').trim() || null,
      city: String(data.get('city') || '').trim(),
      state: String(data.get('state') || '').trim().toUpperCase(),
      postal_code: String(data.get('postal_code') || '').trim(),
      country_code: String(data.get('country_code') || 'US').trim().toUpperCase()
    };
    return {
      recipient,
      items: cart.map((item) => ({
        sku: item.sku,
        printful_variant_id: item.variantId || null,
        quantity: Math.max(1, Math.min(10, Number(item.quantity) || 1))
      }))
    };
  }

  function renderShippingRates(rates) {
    shippingRatesEl.innerHTML = '';
    selectedShipping = null;
    squareButton.disabled = true;

    if (!rates.length) {
      const message = document.createElement('p');
      message.textContent = 'No shipping methods are currently available for this address.';
      shippingRatesEl.appendChild(message);
      return;
    }

    rates.forEach((rate, index) => {
      const label = document.createElement('label');
      label.className = 'shipping-option';

      const radio = document.createElement('input');
      radio.type = 'radio';
      radio.name = 'shipping_method';
      radio.value = rate.shipping;
      radio.required = true;

      const copy = document.createElement('span');
      const title = document.createElement('strong');
      title.textContent = rate.name || rate.shipping;
      const detail = document.createElement('small');
      let eta = '';
      if (rate.min_delivery_days != null && rate.max_delivery_days != null) {
        eta = ' · estimated ' + rate.min_delivery_days + '–' + rate.max_delivery_days + ' business days';
      }
      detail.textContent = window.BMBCart.formatMoney(rate.rate_cents, rate.currency) + eta;
      copy.append(title, detail);

      radio.addEventListener('change', () => {
        selectedShipping = rate;
        squareButton.disabled = false;
        shippingEl.textContent = window.BMBCart.formatMoney(rate.rate_cents, rate.currency);
      });

      if (index === 0) {
        radio.checked = true;
        selectedShipping = rate;
        squareButton.disabled = false;
        shippingEl.textContent = window.BMBCart.formatMoney(rate.rate_cents, rate.currency);
      }

      label.append(radio, copy);
      shippingRatesEl.appendChild(label);
    });
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!cart.length) return;
    if (!form.reportValidity()) return;

    quoteButton.disabled = true;
    setStatus('Verifying cart and requesting current shipping rates…');

    try {
      const order = await api('/api/v1/orders', {
        method: 'POST',
        body: JSON.stringify(orderPayload())
      });
      orderNumber = order.order_number;
      subtotalEl.textContent = window.BMBCart.formatMoney(order.subtotal_cents, order.currency);

      const rates = await api('/api/v1/orders/' + encodeURIComponent(orderNumber) + '/shipping-rates');
      renderShippingRates(rates);
      shippingStep.hidden = false;
      form.querySelectorAll('input, select, button').forEach((control) => {
        control.disabled = true;
      });
      setStatus('Choose a shipping method, then continue to Square.');
      shippingStep.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      quoteButton.disabled = false;
      setStatus(error.message || 'Unable to prepare checkout.', true);
    }
  });

  squareButton.addEventListener('click', async () => {
    if (!orderNumber || !selectedShipping) return;
    squareButton.disabled = true;
    setStatus('Preparing secure Square checkout…');

    try {
      await api('/api/v1/orders/' + encodeURIComponent(orderNumber) + '/shipping', {
        method: 'POST',
        body: JSON.stringify({ shipping: selectedShipping.shipping })
      });
      const checkout = await api('/api/v1/orders/' + encodeURIComponent(orderNumber) + '/square-checkout', {
        method: 'POST',
        body: '{}'
      });
      if (!checkout.square_checkout_url) throw new Error('Square checkout URL was not returned.');
      try { sessionStorage.setItem('bmb-active-order', orderNumber); } catch (_) { /* Payment must work without browser storage. */ }
      window.location.assign(checkout.square_checkout_url);
    } catch (error) {
      squareButton.disabled = false;
      setStatus(error.message || 'Unable to start Square checkout.', true);
    }
  });

  renderCartSummary();
})();
