document.addEventListener('DOMContentLoaded', () => {
  // Mobile nav
  const toggle = document.querySelector('[data-crm-menu-toggle]');
  const aside = document.querySelector('.crm-aside');
  const backdrop = document.querySelector('[data-crm-backdrop]');
  if (toggle && aside) {
    const close = () => {
      aside.classList.remove('is-open');
      backdrop?.classList.remove('is-open');
      document.body.style.overflow = '';
    };
    toggle.addEventListener('click', () => {
      const open = aside.classList.toggle('is-open');
      backdrop?.classList.toggle('is-open', open);
      document.body.style.overflow = open ? 'hidden' : '';
    });
    backdrop?.addEventListener('click', close);
    aside.querySelectorAll('.crm-nav-link').forEach((link) => {
      link.addEventListener('click', () => { if (window.innerWidth < 900) close(); });
    });
  }

  // Count-up KPIs
  document.querySelectorAll('[data-count]').forEach((el) => {
    const target = parseInt(el.dataset.count, 10);
    if (Number.isNaN(target) || target <= 0) return;
    let cur = 0;
    const step = Math.max(1, Math.ceil(target / 30));
    const tick = () => {
      cur = Math.min(target, cur + step);
      el.textContent = cur;
      if (cur < target) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  // Intersection reveal
  const obs = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('is-visible');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.08 });
  document.querySelectorAll('.crm-panel, .crm-table-wrap').forEach((el) => obs.observe(el));
});
