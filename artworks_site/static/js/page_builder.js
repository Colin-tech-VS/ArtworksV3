/* Mode créateur — canvas freeform (glisser / éditer / enregistrer). */
(function () {
  'use strict';
  var root = document.getElementById('pe-builder');
  if (!root) return;

  var canvas = root.querySelector('[data-canvas]');
  var saveUrl = root.getAttribute('data-save-url');
  var saveBtn = root.querySelector('[data-save]');
  var clearBtn = root.querySelector('[data-clear]');
  var stateEl = root.querySelector('[data-save-state]');

  var seq = 0;
  var selected = null;
  var dirty = false;

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
  function markDirty() {
    dirty = true;
    setState('Non enregistré', 'is-dirty');
  }

  function uid() { return 'el' + (Date.now().toString(36)) + (seq++); }

  function clampNum(v, min, max) {
    v = parseFloat(v) || 0;
    if (v < min) v = min;
    if (max != null && v > max) v = max;
    return Math.round(v);
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
    del.addEventListener('click', function (e) {
      e.stopPropagation();
      removeEl(el);
    });
    el.appendChild(del);

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
      node.src = src;
      node.alt = '';
    } else {
      node = document.createElement('div');
      node.className = 'pe-img-ph';
      node.textContent = 'Double-cliquez pour ajouter une image (URL)';
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

  /* ----- Drag (pointer) ----- */
  function bindDrag(el) {
    var startX, startY, originLeft, originTop, moved;
    el.addEventListener('pointerdown', function (e) {
      if (e.target.isContentEditable) return;
      if (e.target.classList.contains('pe-el-del')) return;
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

  /* ----- Édition (double-clic) ----- */
  function bindEdit(el) {
    el.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      if (el.dataset.type === 'image') {
        var url = window.prompt('URL de l\'image :', el.dataset.src || '');
        if (url !== null) { renderImage(el, url.trim()); markDirty(); }
        return;
      }
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
  }

  function serialize() {
    var els = [];
    canvas.querySelectorAll('.pe-el').forEach(function (el) {
      var m = {
        id: el.dataset.id,
        type: el.dataset.type,
        x: clampNum(el.style.left, 0),
        y: clampNum(el.style.top, 0),
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
    var elements = serialize();
    setState('Enregistrement…');
    fetch(saveUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ elements: elements, canvas: {} })
    }).then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.ok) { dirty = false; setState('Enregistré', 'is-saved'); }
        else { setState((res.j && res.j.error) || 'Erreur', 'is-dirty'); }
      })
      .catch(function () { setState('Erreur réseau', 'is-dirty'); });
  }

  /* ----- Init ----- */
  function load() {
    var raw = root.getAttribute('data-layout');
    var data = null;
    try { data = raw && raw !== 'null' ? JSON.parse(raw) : null; } catch (_) {}
    if (data && Array.isArray(data.elements)) {
      data.elements.forEach(function (m) { if (m && m.type) makeEl(m); });
      setState('Enregistré', 'is-saved');
    } else {
      setState('Page vide', '');
    }
  }

  root.querySelectorAll('[data-add]').forEach(function (btn) {
    btn.addEventListener('click', function () { addElement(btn.getAttribute('data-add')); });
  });
  if (saveBtn) saveBtn.addEventListener('click', save);
  if (clearBtn) clearBtn.addEventListener('click', function () {
    if (!canvas.childElementCount) return;
    if (window.confirm('Effacer tous les éléments de la page ?')) {
      canvas.innerHTML = '';
      selected = null;
      markDirty();
    }
  });
  canvas.addEventListener('pointerdown', function (e) {
    if (e.target === canvas) select(null);
  });
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
