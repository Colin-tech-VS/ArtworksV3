/* Panneau d'aperçu unifié — rendu instantané (canvas) ou page complète (iframe) */
(function () {
  'use strict';

  var panel = null;
  var canvasHost = null;
  var fullFrame = null;
  var mode = 'canvas';
  var publicUrl = '';
  var layoutUrl = '';
  var device = 'desktop';
  var deviceBtns = [];

  var DEVICES = {
    desktop: { width: '100%', label: 'Bureau' },
    tablet: { width: '768px', label: 'Tablette' },
    mobile: { width: '390px', label: 'Mobile' }
  };

  function ensure() {
    panel = document.getElementById('pe-preview-panel');
    if (!panel) return false;
    canvasHost = panel.querySelector('[data-preview-canvas]');
    fullFrame = panel.querySelector('[data-preview-full]');
    deviceBtns = panel.querySelectorAll('[data-device]');
    return true;
  }

  function setDevice(d) {
    device = DEVICES[d] ? d : 'desktop';
    var viewport = panel.querySelector('[data-preview-viewport]');
    if (viewport) viewport.style.maxWidth = DEVICES[device].width;
    deviceBtns.forEach(function (btn) {
      btn.classList.toggle('is-active', btn.getAttribute('data-device') === device);
    });
  }

  function setMode(m) {
    mode = m === 'full' ? 'full' : 'canvas';
    if (canvasHost) canvasHost.hidden = mode !== 'canvas';
    if (fullFrame) fullFrame.hidden = mode !== 'full';
    panel.setAttribute('data-preview-mode', mode);
  }

  function flashUpdated() {
    panel.classList.add('is-live');
    setTimeout(function () { panel.classList.remove('is-live'); }, 500);
  }

  function render(layout) {
    if (!ensure() || mode !== 'canvas' || !window.PePageRenderer) return;
    PePageRenderer.render(canvasHost, layout);
    flashUpdated();
  }

  function refreshFull() {
    if (!fullFrame || !publicUrl) return;
    fullFrame.src = publicUrl + (publicUrl.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
    flashUpdated();
  }

  function refreshFromServer() {
    if (!layoutUrl) return Promise.resolve();
    return fetch(layoutUrl, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok && d.layout) render(d.layout);
        if (d.published != null && panel) {
          var dot = panel.querySelector('[data-preview-status]');
          if (dot) {
            dot.textContent = d.published ? 'Publiée' : (d.has_draft ? 'Brouillon' : 'Non publiée');
            dot.className = 'pe-preview-status is-' + (d.published ? 'live' : (d.has_draft ? 'draft' : 'off'));
          }
        }
      })
      .catch(function () {});
  }

  function refresh() {
    if (mode === 'full') refreshFull();
    else return refreshFromServer();
    return Promise.resolve();
  }

  function bind() {
    if (!ensure()) return;
    deviceBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        setDevice(btn.getAttribute('data-device'));
      });
    });
    var refreshBtn = panel.querySelector('[data-preview-refresh]');
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    setDevice('desktop');
  }

  window.PeLivePreview = {
    init: function (opts) {
      opts = opts || {};
      publicUrl = opts.publicUrl || '';
      layoutUrl = opts.layoutUrl || '';
      setMode(opts.mode || 'canvas');
      bind();
      if (mode === 'full') refreshFull();
      else if (opts.initialLayout) render(opts.initialLayout);
      else refreshFromServer();
    },
    render: render,
    refresh: refresh,
    refreshFull: refreshFull,
    refreshFromServer: refreshFromServer,
    setMode: setMode,
    setDevice: setDevice
  };
})();
