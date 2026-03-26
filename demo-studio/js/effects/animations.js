// Animation utilities
const Anim = (() => {
  // Create particle burst at element position
  function particleBurst(el, color = '#22c55e', count = 8) {
    const rect = el.getBoundingClientRect();
    const container = document.createElement('div');
    container.className = 'particle-burst';
    container.style.left = rect.left + rect.width / 2 + 'px';
    container.style.top = rect.top + rect.height / 2 + 'px';
    document.body.appendChild(container);

    for (let i = 0; i < count; i++) {
      const p = document.createElement('div');
      p.className = 'particle';
      p.style.background = color;
      const angle = (Math.PI * 2 * i) / count;
      const dist = 20 + Math.random() * 30;
      p.style.setProperty('--dx', Math.cos(angle) * dist + 'px');
      p.style.setProperty('--dy', Math.sin(angle) * dist + 'px');
      container.appendChild(p);
    }

    setTimeout(() => container.remove(), 1000);
  }

  // Typewriter effect for text
  function typewriter(el, text, speed = 30) {
    return new Promise(resolve => {
      el.textContent = '';
      let i = 0;
      const timer = setInterval(() => {
        el.textContent += text[i];
        i++;
        if (i >= text.length) {
          clearInterval(timer);
          resolve();
        }
      }, speed);
    });
  }

  // Flash border effect
  function flashBorder(el, color = 'var(--primary)') {
    el.style.transition = 'box-shadow 0.3s';
    el.style.boxShadow = `0 0 0 2px ${color}, 0 0 20px ${color}40`;
    setTimeout(() => {
      el.style.boxShadow = 'none';
    }, 800);
  }

  // Smooth scroll to bottom of container
  function scrollToBottom(container) {
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth'
    });
  }

  // Stagger animation for multiple elements
  function stagger(elements, className, delay = 100) {
    elements.forEach((el, i) => {
      setTimeout(() => el.classList.add(className), i * delay);
    });
  }

  return { particleBurst, typewriter, flashBorder, scrollToBottom, stagger };
})();
