// Number animation engine - slot machine style rolling
const NumberAnim = (() => {
  const active = new Map();

  // Animate a number from current to target with easing
  function animateTo(el, target, duration = 1200, suffix = '') {
    const id = el.id || Math.random().toString(36);
    if (active.has(id)) cancelAnimationFrame(active.get(id));

    const current = parseFloat(el.textContent.replace(/[^0-9.-]/g, '')) || 0;
    const start = performance.now();
    const isFloat = target % 1 !== 0;

    function update(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic for natural deceleration
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = current + (target - current) * eased;

      if (isFloat) {
        el.textContent = value.toFixed(1) + suffix;
      } else {
        el.textContent = Math.round(value).toLocaleString() + suffix;
      }

      if (progress < 1) {
        active.set(id, requestAnimationFrame(update));
      } else {
        active.delete(id);
        // Pulse effect on completion
        el.closest('.stat-card')?.classList.add('pulse');
        setTimeout(() => {
          el.closest('.stat-card')?.classList.remove('pulse');
        }, 600);
      }
    }

    active.set(id, requestAnimationFrame(update));
  }

  // Increment by a random amount (for live updates)
  function increment(el, min, max, suffix = '') {
    const current = parseFloat(el.textContent.replace(/[^0-9.-]/g, '')) || 0;
    const delta = Math.floor(Math.random() * (max - min + 1)) + min;
    animateTo(el, current + delta, 800, suffix);
    return current + delta;
  }

  // Format large numbers (1.2K, 3.4M)
  function formatCompact(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
  }

  return { animateTo, increment, formatCompact };
})();
