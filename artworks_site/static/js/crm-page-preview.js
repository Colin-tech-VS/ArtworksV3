/** Aperçu live des pages CMS pendant l'édition */
(function () {
  const form = document.getElementById('crm-page-form');
  const bodyEl = form ? form.querySelector('textarea[name="body"]') : null;
  const titleEl = form ? form.querySelector('input[name="title"]') : null;
  let panel = document.getElementById('crm-page-preview-panel');

  if (!form || !bodyEl) return;

  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'crm-page-preview-panel';
    panel.className = 'crm-panel crm-email-preview-panel';
    panel.innerHTML = `
      <div class="crm-panel-head">
        <div><h2>Aperçu page</h2><p class="sub">Rendu tel qu'affiché sur le site</p></div>
        <span class="crm-badge crm-badge-live"><span class="crm-dot"></span> Live</span>
      </div>
      <div id="crm-page-preview-body" class="crm-page-preview-body"></div>
    `;
    form.closest('.crm-split')?.parentNode?.appendChild(panel);
  }

  const previewBody = document.getElementById('crm-page-preview-body');

  function refresh() {
    if (!previewBody) return;
    const title = titleEl ? titleEl.value : '';
    let html = bodyEl.value;
    if (window.crmWysiwyg) {
      html = window.crmWysiwyg.getHtml(bodyEl);
    }
    previewBody.innerHTML = (title ? `<h1 style="font-family:Georgia,serif;font-weight:400;margin:0 0 20px">${title}</h1>` : '') + (html || '<p style="color:#999"><em>Contenu vide</em></p>');
  }

  bodyEl.addEventListener('input', refresh);
  if (titleEl) titleEl.addEventListener('input', refresh);
  setTimeout(refresh, 700);
})();
