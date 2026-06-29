/** CRM emails — aperçu live + génération IA + sélecteur destinataires */
(function () {
  const previewFrame = document.getElementById('crm-email-preview-frame');
  const previewUrl = document.querySelector('[data-preview-url]')?.dataset.previewUrl;
  const aiForm = document.getElementById('crm-email-ai-form');
  const aiBtn = document.getElementById('crm-email-ai-btn');
  const aiStatus = document.getElementById('crm-email-ai-status');
  const subjectEl = document.getElementById('email-subject');
  const preheaderEl = document.getElementById('email-preview-text');
  const bodyEl = document.getElementById('email-body');
  const modeEl = document.getElementById('recipient-mode');

  let previewTimer = null;

  function getBodyHtml() {
    if (bodyEl && window.crmWysiwyg) {
      return window.crmWysiwyg.getHtml(bodyEl);
    }
    return bodyEl ? bodyEl.value : '';
  }

  function setBodyHtml(html) {
    if (bodyEl && window.crmWysiwyg) {
      window.crmWysiwyg.setHtml(bodyEl, html);
    } else if (bodyEl) {
      bodyEl.value = html;
    }
  }

  function updatePreviewFrame(html) {
    if (!previewFrame || !html) return;
    previewFrame.srcdoc = html;
  }

  function csrfToken() {
    return document.querySelector('input[name="csrf_token"]')?.value || '';
  }

  function refreshPreview() {
    if (!previewUrl) return;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(async () => {
      try {
        const res = await fetch(previewUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            subject: subjectEl ? subjectEl.value : '',
            preview_text: preheaderEl ? preheaderEl.value : '',
            body_html: getBodyHtml(),
          }),
        });
        const data = await res.json();
        if (data.ok) updatePreviewFrame(data.html);
      } catch (_) { /* ignore */ }
    }, 400);
  }

  [subjectEl, preheaderEl, bodyEl].forEach((el) => {
    if (el) el.addEventListener('input', refreshPreview);
  });

  if (bodyEl) {
    bodyEl.addEventListener('input', refreshPreview);
    setTimeout(refreshPreview, 600);
  }

  function toggleRecipientFields() {
    if (!modeEl) return;
    const mode = modeEl.value;
    document.querySelectorAll('.crm-recipient-field').forEach((el) => {
      el.style.display = el.dataset.mode === mode ? '' : 'none';
    });
  }

  if (modeEl) {
    modeEl.addEventListener('change', toggleRecipientFields);
    toggleRecipientFields();
  }

  if (aiForm && aiBtn) {
    aiForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const url = aiForm.dataset.aiUrl;
      if (!url) return;
      aiBtn.classList.add('is-loading');
      aiBtn.disabled = true;
      if (aiStatus) aiStatus.textContent = 'Génération en cours…';

      const fd = new FormData(aiForm);
      try {
        const res = await fetch(url, { method: 'POST', body: fd });
        const data = await res.json();
        if (!data.ok) {
          if (aiStatus) aiStatus.textContent = data.error || 'Erreur IA';
          return;
        }
        if (subjectEl && data.data.subject) subjectEl.value = data.data.subject;
        if (preheaderEl && data.data.preview_text) preheaderEl.value = data.data.preview_text;
        setBodyHtml(data.data.body_html || '');
        updatePreviewFrame(data.preview_html);
        if (aiStatus) aiStatus.textContent = 'Contenu généré — aperçu mis à jour.';
      } catch (err) {
        if (aiStatus) aiStatus.textContent = 'Erreur réseau.';
      } finally {
        aiBtn.classList.remove('is-loading');
        aiBtn.disabled = false;
      }
    });
  }
})();
