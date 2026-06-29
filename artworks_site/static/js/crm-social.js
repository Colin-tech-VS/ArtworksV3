(function () {
  'use strict';

  var form = document.getElementById('crm-social-form');
  var aiForm = document.getElementById('crm-social-ai-form');
  var previewBox = document.getElementById('crm-social-preview');
  var debounceTimer;

  function qs(id) { return document.getElementById(id); }

  function toggleTargetFields() {
    var mode = (qs('social-target-mode') || {}).value || 'role';
    document.querySelectorAll('.crm-recipient-field').forEach(function (el) {
      el.style.display = el.getAttribute('data-mode') === mode ? '' : 'none';
    });
    updateTargetCount();
  }

  function payloadFromForm() {
    return {
      subject: (qs('social-subject') || {}).value || '',
      facebook_text: (qs('social-fb') || {}).value || '',
      instagram_text: (qs('social-ig') || {}).value || '',
      destination_url: (qs('social-dest') || {}).value || '',
      image_url: '',
    };
  }

  function updatePreview() {
    if (!form || !previewBox) return;
    var url = form.getAttribute('data-preview-url');
    if (!url) return;
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(payloadFromForm()),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.html) previewBox.innerHTML = data.html;
      })
      .catch(function () {});
  }

  function debouncedPreview() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(updatePreview, 280);
  }

  function updateTargetCount() {
    if (!form) return;
    var url = form.getAttribute('data-target-url');
    var hint = qs('social-target-hint');
    if (!url || !hint) return;
    var usersEl = qs('social-users');
    var userIds = usersEl ? Array.from(usersEl.selectedOptions).map(function (o) { return parseInt(o.value, 10); }) : [];
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_mode: (qs('social-target-mode') || {}).value,
        segment_id: (qs('social-segment') || {}).value,
        target_role: (qs('social-role') || {}).value,
        target_user_ids: userIds,
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var names = (data.names || []).join(', ');
        hint.innerHTML = '<span class="crm-badge crm-badge-live">' + (data.count || 0) + ' client(s)</span>' +
          (names ? ' — ' + names : '');
      })
      .catch(function () {});
  }

  if (form) {
    ['social-subject', 'social-fb', 'social-ig', 'social-dest'].forEach(function (id) {
      var el = qs(id);
      if (el) el.addEventListener('input', debouncedPreview);
    });
    var modeEl = qs('social-target-mode');
    if (modeEl) modeEl.addEventListener('change', toggleTargetFields);
    ['social-segment', 'social-role', 'social-users'].forEach(function (id) {
      var el = qs(id);
      if (el) el.addEventListener('change', updateTargetCount);
    });
    toggleTargetFields();
  }

  if (aiForm) {
    aiForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var status = qs('crm-social-ai-status');
      var url = aiForm.getAttribute('data-ai-url');
      var btn = qs('crm-social-ai-btn');
      if (btn) btn.disabled = true;
      if (status) status.textContent = 'Génération…';
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          subject: (qs('social-subject-ai') || {}).value,
          keywords: (qs('social-keywords-ai') || {}).value,
          tone: (qs('social-tone-ai') || {}).value,
          language: (qs('social-lang-ai') || {}).value,
          destination_url: (qs('social-dest') || {}).value,
        }),
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.error) throw new Error(data.error);
          if (qs('social-subject')) qs('social-subject').value = (qs('social-subject-ai') || {}).value || '';
          if (qs('social-fb')) qs('social-fb').value = data.facebook_text || '';
          if (qs('social-ig')) qs('social-ig').value = data.instagram_text || '';
          if (qs('social-pt')) qs('social-pt').value = data.pinterest_text || '';
          if (qs('social-da-title')) qs('social-da-title').value = data.deviantart_title || '';
          if (qs('social-da-desc')) qs('social-da-desc').value = data.deviantart_description || '';
          if (status) status.textContent = 'Textes générés — vérifiez l\'aperçu.';
          updatePreview();
        })
        .catch(function (err) {
          if (status) status.textContent = err.message || 'Erreur IA';
        })
        .finally(function () {
          if (btn) btn.disabled = false;
        });
    });
  }
})();
