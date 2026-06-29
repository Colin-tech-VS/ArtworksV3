document.addEventListener('DOMContentLoaded', () => {
  const chart = document.getElementById('crm-traffic-chart');
  if (!chart) return;
  let labels = [];
  let values = [];
  try {
    labels = JSON.parse(chart.dataset.labels || '[]');
    values = JSON.parse(chart.dataset.values || '[]');
  } catch (_) { return; }
  const wrap = chart.querySelector('.crm-chart-bars');
  if (!wrap || !values.length) {
    wrap.innerHTML = '<p style="padding:24px;color:var(--crm-muted)">Pas de trafic enregistré sur cette période.</p>';
    return;
  }
  const max = Math.max(...values, 1);
  wrap.innerHTML = '';
  values.forEach((v, i) => {
    const bar = document.createElement('div');
    bar.className = 'crm-chart-bar';
    bar.style.animationDelay = `${i * 0.03}s`;
    const pct = Math.max(4, (v / max) * 100);
    bar.innerHTML = `
      <span class="crm-chart-bar-val">${v}</span>
      <div class="crm-chart-bar-fill" style="height:${pct}%;animation-delay:${i * 0.04}s"></div>
      <span class="crm-chart-bar-label">${labels[i] || ''}</span>
    `;
    wrap.appendChild(bar);
  });
});
