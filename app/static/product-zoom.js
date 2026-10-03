(() => {
  document.querySelectorAll('[data-product-zoom]').forEach((target) => {
    const preview = target.querySelector('[data-zoom-preview]');
    const detail = target.querySelector('[data-zoom-detail]');
    const help = document.querySelector('[data-zoom-help]');
    if (!preview || !detail) return;

    let hovering = false;
    let pinned = false;
    let requested = false;
    let ready = false;
    let fallback = false;
    let position = { x: 0.5, y: 0.4 };
    let drag = null;
    let suppressClick = false;
    const clamp = (value) => Math.max(0, Math.min(1, value));
    const scale = () => Math.max(1, Math.min(3, detail.naturalWidth / target.clientWidth));

    function render() {
      const active = ready && (hovering || pinned);
      target.classList.toggle('is-zoomed', active);
      target.setAttribute('aria-pressed', String(active));
      detail.style.transformOrigin = `${position.x * 100}% ${position.y * 100}%`;
      detail.style.transform = active ? `scale(${scale()})` : 'none';
    }

    function loadDetail() {
      if (requested) return;
      requested = true;
      const incoming = new Image();
      incoming.addEventListener('load', () => { detail.src = incoming.src; });
      incoming.src = target.dataset.zoomSrc || preview.currentSrc || preview.src;
    }

    function reset() {
      hovering = false;
      pinned = false;
      drag = null;
      position = { x: 0.5, y: 0.4 };
      render();
    }

    detail.addEventListener('load', () => {
      ready = true;
      detail.hidden = false;
      render();
    });
    detail.addEventListener('error', () => {
      if (!fallback) {
        fallback = true;
        detail.src = preview.currentSrc || preview.src;
      } else {
        reset();
        target.disabled = true;
        if (help) help.hidden = true;
      }
    });

    target.addEventListener('pointerenter', (event) => {
      if (event.pointerType !== 'mouse') return;
      hovering = true;
      loadDetail();
      render();
    });
    target.addEventListener('pointerleave', () => {
      hovering = false;
      render();
    });
    target.addEventListener('pointerdown', (event) => {
      suppressClick = false;
      if (event.pointerType === 'mouse' || !pinned || !ready) return;
      drag = { id: event.pointerId, x: event.clientX, y: event.clientY,
               origin: { ...position } };
      target.setPointerCapture(event.pointerId);
    });
    target.addEventListener('pointermove', (event) => {
      const bounds = target.getBoundingClientRect();
      if (drag && drag.id === event.pointerId) {
        const dx = event.clientX - drag.x;
        const dy = event.clientY - drag.y;
        if (Math.hypot(dx, dy) > 8) suppressClick = true;
        const magnification = Math.max(1, scale() - 1);
        position = { x: clamp(drag.origin.x - dx / (bounds.width * magnification)),
                     y: clamp(drag.origin.y - dy / (bounds.height * magnification)) };
      } else if (event.pointerType === 'mouse' && (hovering || pinned)) {
        position = { x: clamp((event.clientX - bounds.left) / bounds.width),
                     y: clamp((event.clientY - bounds.top) / bounds.height) };
      } else return;
      render();
    });
    const endDrag = () => { drag = null; };
    target.addEventListener('pointerup', endDrag);
    target.addEventListener('pointercancel', endDrag);
    target.addEventListener('lostpointercapture', endDrag);
    target.addEventListener('click', () => {
      if (suppressClick) { suppressClick = false; return; }
      pinned = !pinned;
      hovering = false;
      if (pinned) loadDetail();
      render();
    });
    target.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') { event.preventDefault(); reset(); return; }
      if (!(hovering || pinned)) return;
      const moves = { ArrowLeft: [-0.08, 0], ArrowRight: [0.08, 0],
                      ArrowUp: [0, -0.08], ArrowDown: [0, 0.08] };
      if (event.key === 'Home') {
        event.preventDefault(); position = { x: 0.5, y: 0.4 }; render();
      } else if (moves[event.key]) {
        event.preventDefault();
        position = { x: clamp(position.x + moves[event.key][0]),
                     y: clamp(position.y + moves[event.key][1]) };
        render();
      }
    });
    target.addEventListener('blur', reset);
    window.addEventListener('resize', render);
    if (detail.complete && detail.naturalWidth) {
      ready = true;
      detail.hidden = false;
    }
    target.disabled = false;
    if (help) help.hidden = false;
  });
})();
