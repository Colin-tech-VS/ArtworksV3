(function () {
  const plansByRole = window.__AUTH_PLANS__;
  const planInput = document.getElementById('plan');
  const planRoot = document.getElementById('auth-plans');
  const roleInputs = document.querySelectorAll('.auth-roles .role-card input[type="radio"]');
  const googleBtn = document.querySelector('[data-google-register]');

  function selectedRole() {
    const checked = document.querySelector('.auth-roles .role-card input[type="radio"]:checked');
    return checked ? checked.value : 'collectionneur';
  }

  function renderPlans(role) {
    if (!planRoot || !plansByRole) return;
    const plans = plansByRole[role] || [];
    const current = planInput ? planInput.value : 'free';
    let hasCurrent = plans.some((p) => p.slug === current);
    const pick = hasCurrent ? current : (plans.find((p) => p.highlight) || plans[0] || {}).slug || 'free';
    if (planInput) planInput.value = pick;

    planRoot.innerHTML = plans.map((p) => {
      const sel = p.slug === pick ? ' is-selected' : '';
      const feat = p.price_cents > 0 ? p.price + ' / mois' : 'Gratuit';
      const badge = p.badge ? `<span class="auth-plan-badge">${p.badge}</span>` : '';
      return `<button type="button" class="auth-plan-card${sel}${p.highlight ? ' is-featured' : ''}" data-plan="${p.slug}">
        <span class="auth-plan-top">
          <strong>${p.name}</strong>${badge}
          <em>${feat}</em>
        </span>
        <span class="auth-plan-tag">${p.tagline}</span>
      </button>`;
    }).join('');

    planRoot.querySelectorAll('.auth-plan-card').forEach((btn) => {
      btn.addEventListener('click', () => {
        planRoot.querySelectorAll('.auth-plan-card').forEach((b) => b.classList.remove('is-selected'));
        btn.classList.add('is-selected');
        if (planInput) planInput.value = btn.dataset.plan;
        syncGoogleHref();
      });
    });
    syncGoogleHref();
  }

  function syncGoogleHref() {
    if (!googleBtn) return;
    const base = googleBtn.getAttribute('data-google-base');
    const role = selectedRole();
    const plan = planInput ? planInput.value : 'free';
    googleBtn.href = `${base}&role=${encodeURIComponent(role)}&plan=${encodeURIComponent(plan)}`;
  }

  roleInputs.forEach((input) => {
    input.addEventListener('change', () => renderPlans(input.value));
  });

  if (plansByRole) {
    renderPlans(selectedRole());
  }

  if (googleBtn) {
    googleBtn.addEventListener('click', (e) => {
      if (!document.querySelector('.auth-roles .role-card input:checked')) {
        e.preventDefault();
        alert('Choisissez d\'abord votre profil.');
      }
    });
  }
})();
