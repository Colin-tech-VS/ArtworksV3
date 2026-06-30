/* Mode créateur — canvas freeform (glisser / redimensionner / éditer / uploader / publier). */
(function () {
  'use strict';
  var root = document.getElementById('pe-builder');
  if (!root) return;

  var canvas = root.querySelector('[data-canvas]');
  var saveUrl = root.getAttribute('data-save-url');
  var uploadUrl = root.getAttribute('data-upload-url');
  var saveBtn = root.querySelector('[data-save]');
  var clearBtn = root.querySelector('[data-clear]');
  var pubBtn = root.querySelector('[data-publish]');
  var stateEl = root.querySelector('[data-save-state]');
  var fileInput = root.querySelector('[data-upload-input]');

  var seq = 0;
  var selected = null;
  var dirty = false;
  var published = root.getAttribute('data-published') === '1';
  var uploadTarget = null;

  var DEFAULTS = {
    heading: { text: 'Votre titre', w: 320 },
    text: { text: 'Cliquez deux fois pour écrire votre texte ici.', w: 420 },
    button: { text: 'Découvrir', w: 0 },
    image: { src: '', w: 240, h: 160 }
  };

  function setState(label, cls) {
    if (!stateEl) return;
    stateEl.textContent = label || '';
    stateEl.className = 'pe-save-state' + (cls ? ' ' + cls : '');
  }
  function markDirty() { dirty = true; setState('Non enregistré', 'is-dirty'); }
  function uid() { return 'el' + (Date.now().toString(36)) + (seq++); }

  function clampNum(v, min, max) {
    v = parseFloat(v) || 0;
    if (v < min) v = min;
    if (max != null && v > max) v = max;
    return Math.round(v);
  }

  function renderPubBtn() {
    if (!pubBtn) return;
    pubBtn.classList.toggle('is-published', published);
    pubBtn.setAttribute('aria-pressed', published ? 'true' : 'false');
    pubBtn.textContent = published ? 'Publiée ✓ — masquer' : 'Publier sur ma page';
  }

  function makeEl(model) {
    var el = document.createElement('div');
    el.className = 'pe-el';
    el.dataset.type = model.type;
    el.dataset.id = model.id;
    el.style.left = (model.x || 0) + 'px';
    el.style.top = (model.y || 0) + 'px';
    if (model.w) el.style.width = model.w + 'px';
    if (model.type === 'image' && model.h) el.style.height = model.h + 'px';

    if (model.type === 'image') {
      renderImage(el, model.src || '');
    } else {
      var span = document.createElement('span');
      span.className = 'pe-el-body';
      span.textContent = model.text != null ? model.text : '';
      el.appendChild(span);
    }

    var del = document.createElement('button');
    del.type = 'button';
    del.className = 'pe-el-del';
    del.setAttribute('aria-label', 'Supprimer');
    del.textContent = '×';
    del.addEventListener('click', function (e) { e.stopPropagation(); removeEl(el); });
    el.appendChild(del);

    var grip = document.createElement('span');
    grip.className = 'pe-el-resize';
    grip.setAttribute('aria-hidden', 'true');
    el.appendChild(grip);
    bindResize(el, grip);

    bindDrag(el);
    bindEdit(el);
    canvas.appendChild(el);
    return el;
  }

  function renderImage(el, src) {
    var existing = el.querySelector('img, .pe-img-ph');
    if (existing) existing.remove();
    var node;
    if (src) {
      node = document.createElement('img');
      node.src = src; node.alt = '';
    } else {
      node = document.createElement('div');
      node.className = 'pe-img-ph';
      node.textContent = 'Double-cliquez pour choisir une image';
    }
    el.insertBefore(node, el.firstChild);
    el.dataset.src = src || '';
  }

  function select(el) {
    if (selected && selected !== el) selected.classList.remove('is-selected');
    selected = el;
    if (el) el.classList.add('is-selected');
  }
  function removeEl(el) {
    if (selected === el) selected = null;
    el.remove();
    markDirty();
  }

  /* ----- Drag ----- */
  function bindDrag(el) {
    var startX, startY, originLeft, originTop, moved;
    el.addEventListener('pointerdown', function (e) {
      if (e.target.isContentEditable) return;
      if (e.target.classList.contains('pe-el-del')) return;
      if (e.target.classList.contains('pe-el-resize')) return;
      select(el);
      moved = false;
      startX = e.clientX; startY = e.clientY;
      originLeft = parseFloat(el.style.left) || 0;
      originTop = parseFloat(el.style.top) || 0;
      el.setPointerCapture(e.pointerId);
      el.classList.add('is-dragging');
    });
    el.addEventListener('pointermove', function (e) {
      if (!el.classList.contains('is-dragging')) return;
      var dx = e.clientX - startX, dy = e.clientY - startY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
      var rect = canvas.getBoundingClientRect();
      el.style.left = clampNum(originLeft + dx, 0, rect.width - 20) + 'px';
      el.style.top = clampNum(originTop + dy, 0, rect.height - 20) + 'px';
    });
    function end(e) {
      if (!el.classList.contains('is-dragging')) return;
      el.classList.remove('is-dragging');
      try { el.releasePointerCapture(e.pointerId); } catch (_) {}
      if (moved) markDirty();
    }
    el.addEventListener('pointerup', end);
    el.addEventListener('pointercancel', end);
  }

  /* ----- Resize ----- */
  function bindResize(el, grip) {
    var startX, startY, startW, startH;
    grip.addEventListener('pointerdown', function (e) {
      e.stopPropagation();
      select(el);
      startX = e.clientX; startY = e.clientY;
      startW = el.offsetWidth; startH = el.offsetHeight;
      grip.setPointerCapture(e.pointerId);
      el.classList.add('is-resizing');
    });
    grip.addEventListener('pointermove', function (e) {
      if (!el.classList.contains('is-resizing')) return;
      var w = clampNum(startW + (e.clientX - startX), 40, 4000);
      el.style.width = w + 'px';
      if (el.dataset.type === 'image') {
        var h = clampNum(startH + (e.clientY - startY), 40, 4000);
        el.style.height = h + 'px';
      }
    });
    function end(e) {
      if (!el.classList.contains('is-resizing')) return;
      el.classList.remove('is-resizing');
      try { grip.releasePointerCapture(e.pointerId); } catch (_) {}
      markDirty();
    }
    grip.addEventListener('pointerup', end);
    grip.addEventListener('pointercancel', end);
  }

  /* ----- Édition (double-clic) ----- */
  function bindEdit(el) {
    el.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      if (el.dataset.type === 'image') { pickImage(el); return; }
      var body = el.querySelector('.pe-el-body');
      if (!body) return;
      body.setAttribute('contenteditable', 'true');
      body.focus();
      document.execCommand && document.execCommand('selectAll', false, null);
      function done() {
        body.removeAttribute('contenteditable');
        body.removeEventListener('blur', done);
        markDirty();
      }
      body.addEventListener('blur', done);
    });
  }

  /* ----- Upload image ----- */
  function pickImage(el) {
    if (!fileInput || !uploadUrl) {
      var url = window.prompt('URL de l\'image :', el.dataset.src || '');
      if (url !== null) { renderImage(el, url.trim()); markDirty(); }
      return;
    }
    uploadTarget = el;
    fileInput.value = '';
    fileInput.click();
  }
  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var file = fileInput.files && fileInput.files[0];
      if (!file || !uploadTarget) return;
      var target = uploadTarget;
      setState('Téléversement…');
      var fd = new FormData();
      fd.append('image', file);
      fetch(uploadUrl, { method: 'POST', body: fd, credentials: 'same-origin' })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok && res.j.url) { renderImage(target, res.j.url); markDirty(); }
          else { setState((res.j && res.j.error) || 'Échec upload', 'is-dirty'); }
        })
        .catch(function () { setState('Erreur upload', 'is-dirty'); });
    });
  }

  function addElement(type) {
    var d = DEFAULTS[type] || {};
    var model = {
      id: uid(), type: type,
      x: 40 + (canvas.childElementCount % 6) * 16,
      y: 40 + (canvas.childElementCount % 6) * 16,
      w: d.w || 0, h: d.h || 0,
      text: d.text || '', src: d.src || ''
    };
    var el = makeEl(model);
    select(el);
    markDirty();
    if (type === 'image') pickImage(el);
  }

  function serialize() {
    var els = [];
    canvas.querySelectorAll('.pe-el').forEach(function (el) {
      var m = {
        id: el.dataset.id, type: el.dataset.type,
        x: clampNum(el.style.left, 0), y: clampNum(el.style.top, 0),
        w: clampNum(el.style.width, 0)
      };
      if (el.dataset.type === 'image') {
        m.h = clampNum(el.style.height, 0);
        m.src = el.dataset.src || '';
      } else {
        var body = el.querySelector('.pe-el-body');
        m.text = body ? body.textContent : '';
      }
      els.push(m);
    });
    return els;
  }

  function save() {
    setState('Enregistrement…');
    return fetch(saveUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ elements: serialize(), canvas: {}, published: published })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.ok) {
          dirty = false;
          published = !!res.j.published;
          renderPubBtn();
          setState(published ? 'Enregistré · publié' : 'Enregistré', 'is-saved');
        } else {
          setState((res.j && res.j.error) || 'Erreur', 'is-dirty');
        }
      })
      .catch(function () { setState('Erreur réseau', 'is-dirty'); });
  }

  function load() {
    var raw = root.getAttribute('data-layout');
    var data = null;
    try { data = raw && raw !== 'null' ? JSON.parse(raw) : null; } catch (_) {}
    if (data && Array.isArray(data.elements)) {
      data.elements.forEach(function (m) { if (m && m.type) makeEl(m); });
      setState(published ? 'Publié' : 'Enregistré', 'is-saved');
    } else {
      setState('Page vide', '');
    }
    renderPubBtn();
  }

  root.querySelectorAll('[data-add]').forEach(function (btn) {
    btn.addEventListener('click', function () { addElement(btn.getAttribute('data-add')); });
  });
  if (saveBtn) saveBtn.addEventListener('click', save);
  if (pubBtn) pubBtn.addEventListener('click', function () {
    published = !published;
    renderPubBtn();
    save();
  });
  if (clearBtn) clearBtn.addEventListener('click', function () {
    if (!canvas.childElementCount) return;
    if (window.confirm('Effacer tous les éléments de la page ?')) {
      canvas.innerHTML = '';
      selected = null;
      markDirty();
    }
  });
  canvas.addEventListener('pointerdown', function (e) { if (e.target === canvas) select(null); });
  canvas.addEventListener('keydown', function (e) {
    if ((e.key === 'Delete' || e.key === 'Backspace') && selected && !e.target.isContentEditable) {
      e.preventDefault();
      removeEl(selected);
    }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  load();
})();
