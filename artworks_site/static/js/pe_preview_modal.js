/* Aperçu plein écran — rendu live (canvas) + page visiteur (iframe) */
(function () {
  'use strict';

  var modal = null;
  var canvasHost = null;
  var blocksFrame = null;
  var publicFrame = null;
  var previewUrl = '';
  var publicUrl = '';
  var layoutUrl = '';
  var previewMode = 'canvas';
  var viewMode = 'live';
  var device = 'desktop';
  var beforeOpen = null;

  var DEVICES = { desktop: '100%', tablet: '768px', mobile: '390px' };

  function ensure() {
    modal = document.getElementById('pe-preview-modal');
    if (!modal) return false;
    canvasHost = modal.querySelector('[data-preview-canvas]');
    blocksFrame = modal.querySelector('[data-preview-blocks-frame]');
    publicFrame = modal.querySelector('[data-preview-public-frame]');
    return true;
  }

  function setDevice(d) {
    if (!ensure()) return;
    device = DEVICES[d] ? d : 'desktop';
    var vp = modal.querySelector('[data-preview-viewport]');
    if (vp) vp.style.maxWidth = DEVICES[device];
    modal.querySelectorAll('[data-device]').forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-device') === device);
    });
  }

  function setView(v) {
    if (!ensure()) return;
    if (previewMode === 'full') {
      viewMode = 'public';
      if (canvasHost) canvasHost.hidden = true;
      if (blocksFrame) blocksFrame.hidden = true;
      if (publicFrame) { publicFrame.hidden = false; refreshPublic(); }
      return;
    }
    viewMode = v === 'public' ? 'public' : 'live';
    modal.querySelectorAll('[data-preview-view]').forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-preview-view') === viewMode);
    });
    if (canvasHost) canvasHost.hidden = viewMode !== 'live';
    if (blocksFrame) blocksFrame.hidden = true;
    if (publicFrame) publicFrame.hidden = viewMode !== 'public';
    if (viewMode === 'public') refreshPublic();
    else refreshBlocksFrame();
  }

  function render(layout) {
    if (!ensure() || !window.PePageRenderer || !canvasHost) return;
    PePageRenderer.render(canvasHost, layout);
    modal.classList.add('is-updated');
    setTimeout(function () { modal.classList.remove('is-updated'); }, 400);
  }

  function refreshBlocksFrame() {
    if (!blocksFrame || !previewUrl) return;
    blocksFrame.src = previewUrl + (previewUrl.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  function refreshPublic() {
    if (!publicFrame || !publicUrl) return;
    publicFrame.src = publicUrl + (publicUrl.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  function refreshFromServer() {
    if (!layoutUrl) return Promise.resolve();
    return fetch(layoutUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok && d.layout) render(d.layout);
        updateStatus(d.published, d.has_draft);
      })
      .catch(function () {});
  }

  function updateStatus(published, hasDraft) {
    if (!modal) return;
    var label = published ? 'Publiée' : (hasDraft ? 'Brouillon' : 'Non publiée');
    var key = published ? 'live' : (hasDraft ? 'draft' : 'off');
    document.querySelectorAll('[data-preview-status]').forEach(function (el) {
      el.textContent = label;
      el.className = 'pe-state is-' + key;
    });
  }

  function refresh() {
    if (previewMode === 'full') {
      refreshPublic();
      return Promise.resolve();
    }
    refreshBlocksFrame();
    return refreshFromServer();
  }

  function open() {
    if (!ensure()) return Promise.resolve();
    var chain = Promise.resolve();
    if (typeof beforeOpen === 'function') chain = Promise.resolve(beforeOpen());
    return chain.then(function () {
      return refresh();
    }).then(function () {
      if (previewMode === 'full') setView('public');
      else setView(viewMode);
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('pe-preview-open');
      var closeBtn = modal.querySelector('.pe-preview-close');
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
    if (!ensure()) return;
    modal.querySelectorAll('[data-preview-close]').forEach(function (el) {
      el.addEventListener('click', close);
    });
    modal.querySelectorAll('[data-device]').forEach(function (btn) {
      btn.addEventListener('click', function () { setDevice(btn.getAttribute('data-device')); });
    });
    modal.querySelectorAll('[data-preview-view]').forEach(function (btn) {
      btn.addEventListener('click', function () { setView(btn.getAttribute('data-preview-view')); });
    });
    var refreshBtn = modal.querySelector('[data-preview-refresh]');
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal && !modal.hidden) close();
    });
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-open-preview]');
      if (btn) { e.preventDefault(); open(); }
    });
    setDevice('desktop');
  }

  window.PePagePreview = {
    init: function (opts) {
      opts = opts || {};
      previewUrl = opts.previewUrl || '';
      publicUrl = opts.publicUrl || '';
      layoutUrl = opts.layoutUrl || '';
      previewMode = opts.mode === 'full' ? 'full' : 'canvas';
      beforeOpen = opts.beforeOpen || null;
      if (opts.publicUrl && ensure()) {
        var link = modal.querySelector('[data-preview-public-link]');
        if (link) link.href = opts.publicUrl;
      }
      bind();
      if (previewMode === 'full') {
        setView('public');
        refreshPublic();
      } else if (opts.initialLayout) {
        render(opts.initialLayout);
        refreshBlocksFrame();
      } else {
        refreshFromServer();
      }
      var viewTabs = modal.querySelector('.pe-preview-view-tabs');
      if (viewTabs) viewTabs.hidden = previewMode === 'full';
    },
    open: open,
    close: close,
    refresh: refresh,
    render: render,
    refreshFromServer: refreshFromServer,
    refreshPublic: refreshPublic
  };

  window.PeLivePreview = {
    init: function (opts) { PePagePreview.init(opts); },
    render: function (layout) { PePagePreview.render(layout); },
    refresh: function () { return PePagePreview.refresh(); },
    refreshFromServer: function () { return PePagePreview.refreshFromServer(); },
    refreshFull: function () { PePagePreview.refreshPublic(); }
  };
})();
