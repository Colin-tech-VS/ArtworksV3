/* Modal plein écran — aperçu live page publique (modes créateur & intelligent) */
(function () {
  'use strict';

  var modal = null;
  var frame = null;
  var publicLink = null;
  var previewUrl = '';
  var beforeOpen = null;

  function ensureModal() {
    modal = document.getElementById('pe-preview-modal');
    if (!modal) return false;
    frame = modal.querySelector('[data-preview-modal-frame]');
    publicLink = modal.querySelector('[data-preview-public-link]');
    return true;
  }

  function frameSrc() {
    return previewUrl + (previewUrl.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  function refresh() {
    if (!frame || !previewUrl) return;
    frame.src = frameSrc();
  }

  function open() {
    if (!ensureModal()) return Promise.resolve();
    var chain = Promise.resolve();
    if (typeof beforeOpen === 'function') {
      chain = Promise.resolve(beforeOpen());
    }
    return chain.then(function () {
      refresh();
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('pe-preview-open');
      var closeBtn = modal.querySelector('.pe-preview-modal-close');
      if (closeBtn) closeBtn.focus();
    });
  }

  function close() {
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('pe-preview-open');
  }

  function bind() {
    if (!ensureModal()) return;
    modal.querySelectorAll('[data-preview-close]').forEach(function (el) {
      el.addEventListener('click', close);
    });
    var refreshBtn = modal.querySelector('[data-preview-refresh]');
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal && !modal.hidden) close();
    });
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-open-preview]');
      if (btn) {
        e.preventDefault();
        open();
      }
    });
  }

  window.PePagePreview = {
    init: function (opts) {
      opts = opts || {};
      previewUrl = opts.previewUrl || '';
      beforeOpen = opts.beforeOpen || null;
      if (opts.publicUrl && ensureModal() && publicLink) {
        publicLink.href = opts.publicUrl;
      }
      bind();
    },
    open: open,
    close: close,
    refresh: refresh
  };
})();
