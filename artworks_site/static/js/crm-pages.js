document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('crm-ai-form');
  const btn = document.getElementById('crm-ai-btn');
  const status = document.getElementById('crm-ai-status');
  const pageForm = document.getElementById('crm-page-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btn?.classList.add('is-loading');
    if (status) status.textContent = 'Génération SEO en cours via Mistral…';
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      const data = await res.json();
      if (!data.ok) {
        if (status) status.textContent = data.error || 'Erreur de génération';
        return;
      }
      const p = data.page;
      const set = (name, val) => {
        const el = pageForm?.querySelector(`[name="${name}"]`);
        if (el && val != null) el.value = val;
      };
      set('title', p.title);
      set('slug', p.slug);
      set('excerpt', p.excerpt);
      set('meta_title', p.meta_title);
      set('meta_description', p.meta_description);
      set('body', p.body);
      if (status) status.textContent = 'Page SEO générée — vérifiez et enregistrez.';
      pageForm?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      if (status) status.textContent = 'Erreur réseau — réessayez.';
    } finally {
      btn?.classList.remove('is-loading');
    }
  });
});
