(() => {
  const phase1 = document.body.dataset.phase1Enabled === 'true';
  const key = phase1 ? 'bmb-cart-v2' : 'bmb-preview-cart-v1';
  let memoryCart = [];

  function normalizeCart(value) {
    if (!Array.isArray(value)) return [];
    return value.filter((item) => item && typeof item === 'object'
      && typeof item.slug === 'string' && typeof item.name === 'string'
      && (!phase1 || (typeof item.sku === 'string'
        && /^[A-Z]{3}$/.test(item.currency || 'USD'))))
      .map((item) => ({ ...item, quantity: Math.max(1, Math.min(10, Math.floor(Number(item.quantity) || 1))) }));
  }

  function readCart() {
    try {
      const value = JSON.parse(localStorage.getItem(key) || '[]');
      memoryCart = normalizeCart(value);
      return memoryCart;
    } catch (_) {
      return memoryCart;
    }
  }

  function writeCart(cart) {
    memoryCart = normalizeCart(cart);
    try { localStorage.setItem(key, JSON.stringify(memoryCart)); } catch (_) { /* Storage may be unavailable. */ }
    updateCount(memoryCart);
  }

  function formatMoney(cents, currency = 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD'
    }).format((Number(cents) || 0) / 100);
  }

  function itemCount(cart = readCart()) {
    if (!phase1) return cart.length;
    return cart.reduce((total, item) => total + Math.max(1, Number(item.quantity) || 1), 0);
  }

  function updateCount(cart = readCart()) {
    const count = itemCount(cart);
    document.querySelectorAll('[data-cart-count]').forEach((el) => {
      el.textContent = String(count);
    });
  }

  function addPreview(slug, name) {
    const cart = readCart();
    if (!cart.some((item) => item.slug === slug)) cart.push({ slug, name });
    writeCart(cart);
  }

  function addVariant(panel) {
    const variantSelect = panel.querySelector('[data-variant-select]');
    const quantitySelect = panel.querySelector('[data-quantity-select]');
    if (!variantSelect || !variantSelect.selectedOptions.length) return;

    const option = variantSelect.selectedOptions[0];
    const sku = option.value;
    const quantity = Math.max(1, Math.min(10, Number(quantitySelect?.value || 1)));
    const cart = readCart();
    const existing = cart.find((item) => item.sku === sku);

    if (existing) {
      existing.quantity = Math.min(10, (Number(existing.quantity) || 1) + quantity);
    } else {
      cart.push({
        sku,
        variantId: option.dataset.variantId || null,
        slug: panel.dataset.productSlug,
        name: panel.dataset.productName,
        image: panel.dataset.productImage,
        size: option.dataset.size || '',
        color: option.dataset.color || '',
        priceCents: Number(option.dataset.priceCents || 0),
        currency: option.dataset.currency || 'USD',
        quantity
      });
    }
    writeCart(cart);
  }

  function removeItem(identifier) {
    const cart = readCart().filter((item) => (phase1 ? item.sku : item.slug) !== identifier);
    writeCart(cart);
    renderCart();
  }

  function changeQuantity(sku, quantity) {
    const cart = readCart();
    const item = cart.find((entry) => entry.sku === sku);
    if (!item) return;
    item.quantity = Math.max(1, Math.min(10, Number(quantity) || 1));
    writeCart(cart);
    renderCart();
  }

  function makeButton(label, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', handler);
    return button;
  }

  async function refreshCatalog() {
    try {
      const response = await fetch('/catalog.json', { cache: 'no-store', credentials: 'same-origin' });
      if (!response.ok) return;
      const data = await response.json();
      if (!Array.isArray(data.products) || data.products.some((product) => !product
        || typeof product.slug !== 'string' || typeof product.name !== 'string'
        || typeof product.image !== 'string' || !Array.isArray(product.variants))) return;
      const products = new Map(data.products.map((product) => [product.slug, product]));
      const cart = readCart().flatMap((item) => {
        const product = products.get(item.slug);
        if (!product) return [];
        if (!phase1) return [{ ...item, name: product.name, image: product.image }];
        const variant = product.variants.find((entry) => entry.available &&
          (item.variantId ? entry.variantId === item.variantId : entry.sku === item.sku));
        if (!variant || !Number.isInteger(variant.priceCents) || variant.priceCents <= 0
          || variant.currency !== 'USD' || variant.size !== item.size || variant.color !== item.color) return [];
        return [{ ...item, sku: variant.sku, variantId: variant.variantId,
          name: product.name, image: product.image, size: variant.size,
          color: variant.color, currency: variant.currency, priceCents: variant.priceCents }];
      });
      writeCart(cart);
      renderCart();
    } catch (_) { /* Keep the previous cart when the current catalog cannot be fetched. */ }
  }

  function renderCart() {
    const panel = document.querySelector('[data-cart-panel]');
    if (!panel) return;

    const cart = readCart();
    const items = panel.querySelector('[data-cart-items]');
    const empty = panel.querySelector('[data-cart-empty]');
    const checkout = panel.querySelector('[data-cart-checkout]');
    const totalEl = panel.querySelector('[data-cart-total]');

    items.innerHTML = '';
    if (!cart.length) {
      empty.hidden = false;
      checkout.hidden = true;
      return;
    }

    empty.hidden = true;
    checkout.hidden = false;

    let subtotal = 0;
    let currency = 'USD';

    cart.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'cart-row';

      const details = document.createElement('div');
      details.className = 'cart-row-details';

      const link = document.createElement('a');
      link.href = '/products/' + encodeURIComponent(item.slug);
      link.textContent = item.name;
      details.appendChild(link);

      if (phase1) {
        const meta = document.createElement('p');
        meta.className = 'microcopy';
        meta.textContent = [item.size, item.color].filter(Boolean).join(' · ');
        details.appendChild(meta);

        const quantity = document.createElement('select');
        quantity.className = 'cart-quantity';
        quantity.setAttribute('aria-label', 'Quantity for ' + item.name);
        for (let i = 1; i <= 10; i += 1) {
          const option = document.createElement('option');
          option.value = String(i);
          option.textContent = String(i);
          option.selected = i === Number(item.quantity || 1);
          quantity.appendChild(option);
        }
        quantity.addEventListener('change', () => changeQuantity(item.sku, quantity.value));
        details.appendChild(quantity);

        const lineTotal = (Number(item.priceCents) || 0) * (Number(item.quantity) || 1);
        subtotal += lineTotal;
        currency = item.currency || currency;

        const price = document.createElement('strong');
        price.className = 'cart-line-price';
        price.textContent = formatMoney(lineTotal, currency);
        row.append(details, price, makeButton('Remove', () => removeItem(item.sku)));
      } else {
        row.append(details, makeButton('Remove', () => removeItem(item.slug)));
      }

      items.appendChild(row);
    });

    if (phase1 && totalEl) totalEl.textContent = formatMoney(subtotal, currency);
  }

  document.querySelectorAll('[data-add-preview]').forEach((button) => {
    button.addEventListener('click', () => {
      addPreview(button.dataset.productSlug, button.dataset.productName);
      const original = button.textContent;
      button.textContent = 'Added to preview cart';
      setTimeout(() => { button.textContent = original; }, 1200);
    });
  });

  document.querySelectorAll('[data-product-purchase]').forEach((panel) => {
    const select = panel.querySelector('[data-variant-select]');
    const price = panel.querySelector('[data-purchase-price]');
    const button = panel.querySelector('[data-add-variant]');

    function updatePrice() {
      const option = select?.selectedOptions?.[0];
      if (option && price) {
        price.textContent = formatMoney(option.dataset.priceCents, option.dataset.currency);
      }
    }

    select?.addEventListener('change', updatePrice);
    button?.addEventListener('click', () => {
      addVariant(panel);
      const original = button.textContent;
      button.textContent = 'Added to cart';
      setTimeout(() => { button.textContent = original; }, 1200);
    });
    updatePrice();
  });

  window.BMBCart = {
    read: readCart,
    clear() {
      writeCart([]);
      renderCart();
    },
    formatMoney,
    phase1,
    ready: refreshCatalog()
  };

  updateCount();
  renderCart();
})();
