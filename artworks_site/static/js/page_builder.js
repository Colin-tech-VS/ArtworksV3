/* Mode créateur — canvas freeform + propriétés + aperçu live */
(function () {
  'use strict';
  var root = document.getElementById('pe-builder');
  if (!root) return;

  var canvas = root.querySelector('[data-canvas]');
  var propsEl = root.querySelector('[data-props]');
  var saveUrl = root.getAttribute('data-save-url');
  var previewPushUrl = root.getAttribute('data-preview-url');
  var previewFrameUrl = root.getAttribute('data-preview-frame');
  var uploadUrl = root.getAttribute('data-upload-url');
  var saveBtn = root.querySelector('[data-save]');
  var cancelBtn = root.querySelector('[data-cancel]');
  var clearBtn = root.querySelector('[data-clear]');
  var pubBtn = root.querySelector('[data-publish]');
  var stateEl = root.querySelector('[data-save-state]');
  var fileInput = root.querySelector('[data-upload-input]');
  var previewFrame = root.querySelector('[data-preview-frame]');

  var seq = 0;
  var selectedId = null;
  var dirty = false;
  var published = root.getAttribute('data-published') === '1';
  var uploadTargetId = null;
  var elements = [];
  var savedSnapshot = null;
  var previewTimer = null;

  var DEFAULTS = {
    heading: { text: 'Votre titre', w: 420, style: { size: 36, weight: 600, font: 'serif' } },
    text: { text: 'Double-cliquez pour écrire votre texte.', w: 480, style: { size: 16 } },
    button: { text: 'Découvrir', w: 0, href: '#', style: { bg: '#b8734a', color: '#ffffff' } },
    image: { src: '', w: 280, h: 180 },
    slider: { images: [], w: 520, h: 280 },
    gallery: { images: [], w: 520, h: 320 },
    divider: { w: 520, h: 2, style: { color: '#1a2832' } }
  };

  var FONT_OPTS = [
    ['sans', 'Sans-serif'],
    ['serif', 'Serif'],
    ['display', 'Display'],
    ['mono', 'Mono']
  ];

  function uid() { return 'el' + Date.now().toString(36) + (seq++); }

  function clampNum(v, min, max) {
    v = parseFloat(v) || 0;
    if (v < min) v = min;
    if (max != null && v > max) v = max;
    return Math.round(v);
  }

  function findEl(id) {
    for (var i = 0; i < elements.length; i++) {
      if (elements[i].id === id) return elements[i];
    }
    return null;
  }

  function setState(label, cls) {
    if (!stateEl) return;
    stateEl.textContent = label || '';
    stateEl.className = 'pe-save-state' + (cls ? ' ' + cls : '');
  }

  function markDirty() {
    dirty = true;
    if (cancelBtn) cancelBtn.hidden = !savedSnapshot;
    setState('Non enregistré', 'is-dirty');
    schedulePreview();
  }

  function styleToInline(style) {
    if (!style) return '';
    var parts = [];
    if (style.color) parts.push('color:' + style.color);
    if (style.bg) parts.push('background:' + style.bg);
    if (style.font === 'serif') parts.push('font-family:Georgia,serif');
    else if (style.font === 'display') parts.push('font-family:Georgia,serif');
    else if (style.font === 'mono') parts.push('font-family:monospace');
    if (style.size) parts.push('font-size:' + style.size + 'px');
    if (style.weight) parts.push('font-weight:' + style.weight);
    if (style.align) parts.push('text-align:' + style.align);
    return parts.join(';');
  }

  function renderPubBtn() {
    if (!pubBtn) return;
    pubBtn.classList.toggle('is-published', published);
    pubBtn.setAttribute('aria-pressed', published ? 'true' : 'false');
    pubBtn.textContent = published ? 'Publiée ✓ — masquer' : 'Publier sur ma page';
  }

  function renderStrip(type, images) {
    var wrap = document.createElement('div');
    wrap.className = 'pe-strip pe-strip-' + type;
    if (!images || !images.length) {
      var ph = document.createElement('div');
      ph.className = 'pe-img-ph';
      ph.textContent = 'Ajoutez des images dans le panneau →';
      wrap.appendChild(ph);
      return wrap;
    }
    images.forEach(function (src) {
      var img = document.createElement('img');
      img.src = src;
      img.alt = '';
      wrap.appendChild(img);
    });
    return wrap;
  }

  function domForModel(model) {
    var el = document.createElement('div');
    el.className = 'pe-el';
    el.dataset.type = model.type;
    el.dataset.id = model.id;
    el.style.left = (model.x || 0) + 'px';
    el.style.top = (model.y || 0) + 'px';
    if (model.w) el.style.width = model.w + 'px';
    var inline = styleToInline(model.style);
    if (inline) el.style.cssText += ';' + inline;

    if (model.type === 'image') {
      if (model.h) el.style.height = model.h + 'px';
      if (model.src) {
        var img = document.createElement('img');
        img.src = model.src;
        img.alt = '';
        el.appendChild(img);
      } else {
        var ph = document.createElement('div');
        ph.className = 'pe-img-ph';
        ph.textContent = 'Double-cliquez pour choisir une image';
        el.appendChild(ph);
      }
    } else if (model.type === 'slider' || model.type === 'gallery') {
      if (model.h) el.style.height = model.h + 'px';
      el.appendChild(renderStrip(model.type, model.images));
    } else if (model.type === 'divider') {
      if (model.h) el.style.height = model.h + 'px';
      var line = document.createElement('span');
      line.className = 'pe-divider-line';
      el.appendChild(line);
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
      removeElement(model.id);
    });
    el.appendChild(del);

    var grip = document.createElement('span');
    grip.className = 'pe-el-resize';
    grip.setAttribute('aria-hidden', 'true');
    el.appendChild(grip);
    bindResize(el, grip, model.id);
    bindDrag(el, model.id);
    bindEdit(el, model.id);

    el.addEventListener('pointerdown', function (e) {
      if (!e.target.classList.contains('pe-el-del') && !e.target.classList.contains('pe-el-resize')) {
        select(model.id);
      }
    });

    if (model.id === selectedId) el.classList.add('is-selected');
    return el;
  }

  function renderCanvas() {
    canvas.innerHTML = '';
    elements.forEach(function (m) {
      canvas.appendChild(domForModel(m));
    });
    renderProps();
  }

  function select(id) {
    selectedId = id;
    canvas.querySelectorAll('.pe-el').forEach(function (node) {
      node.classList.toggle('is-selected', node.dataset.id === id);
    });
    renderProps();
  }

  function removeElement(id) {
    elements = elements.filter(function (m) { return m.id !== id; });
    if (selectedId === id) selectedId = null;
    renderCanvas();
    markDirty();
  }

  function updateModel(id, patch) {
    var m = findEl(id);
    if (!m) return;
    Object.keys(patch).forEach(function (k) { m[k] = patch[k]; });
    renderCanvas();
    markDirty();
  }

  function bindDrag(el, id) {
    var startX, startY, originLeft, originTop, moved;
    el.addEventListener('pointerdown', function (e) {
      if (e.target.isContentEditable) return;
      if (e.target.classList.contains('pe-el-del')) return;
      if (e.target.classList.contains('pe-el-resize')) return;
      select(id);
      moved = false;
      startX = e.clientX;
      startY = e.clientY;
      originLeft = parseFloat(el.style.left) || 0;
      originTop = parseFloat(el.style.top) || 0;
      el.setPointerCapture(e.pointerId);
      el.classList.add('is-dragging');
    });
    el.addEventListener('pointermove', function (e) {
      if (!el.classList.contains('is-dragging')) return;
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) moved = true;
      var rect = canvas.getBoundingClientRect();
      var left = clampNum(originLeft + dx, 0, rect.width - 20);
      var top = clampNum(originTop + dy, 0, rect.height - 20);
      el.style.left = left + 'px';
      el.style.top = top + 'px';
      var m = findEl(id);
      if (m) { m.x = left; m.y = top; }
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

  function bindResize(el, grip, id) {
    var startX, startY, startW, startH;
    grip.addEventListener('pointerdown', function (e) {
      e.stopPropagation();
      select(id);
      startX = e.clientX;
      startY = e.clientY;
      startW = el.offsetWidth;
      startH = el.offsetHeight;
      grip.setPointerCapture(e.pointerId);
      el.classList.add('is-resizing');
    });
    grip.addEventListener('pointermove', function (e) {
      if (!el.classList.contains('is-resizing')) return;
      var w = clampNum(startW + (e.clientX - startX), 40, 4000);
      el.style.width = w + 'px';
      var m = findEl(id);
      if (m) m.w = w;
      if (el.dataset.type === 'image' || el.dataset.type === 'slider' || el.dataset.type === 'gallery') {
        var h = clampNum(startH + (e.clientY - startY), 40, 4000);
        el.style.height = h + 'px';
        if (m) m.h = h;
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

  function bindEdit(el, id) {
    el.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      var m = findEl(id);
      if (!m) return;
      if (m.type === 'image') { pickImage(id); return; }
      if (m.type === 'slider' || m.type === 'gallery') { pickImage(id, true); return; }
      var body = el.querySelector('.pe-el-body');
      if (!body) return;
      body.setAttribute('contenteditable', 'true');
      body.focus();
      function done() {
        body.removeAttribute('contenteditable');
        body.removeEventListener('blur', done);
        m.text = body.textContent;
        markDirty();
      }
      body.addEventListener('blur', done);
    });
  }

  function pickImage(id, multi) {
    uploadTargetId = id;
    if (fileInput) {
      fileInput.multiple = !!multi;
      fileInput.value = '';
      fileInput.click();
      return;
    }
    var url = window.prompt('URL de l\'image :', '');
    if (url === null) return;
    applyImage(id, url.trim(), multi);
  }

  function applyImage(id, url, append) {
    var m = findEl(id);
    if (!m || !url) return;
    if (m.type === 'image') {
      m.src = url;
    } else if (m.type === 'slider' || m.type === 'gallery') {
      if (!m.images) m.images = [];
      if (append) m.images.push(url);
      else m.images = [url];
    }
    renderCanvas();
    markDirty();
  }

  if (fileInput) {
    fileInput.addEventListener('change', function () {
      var files = fileInput.files;
      if (!files || !files.length || !uploadTargetId) return;
      var targetId = uploadTargetId;
      var m = findEl(targetId);
      var multi = m && (m.type === 'slider' || m.type === 'gallery');
      setState('Téléversement…');
      var chain = Promise.resolve();
      Array.prototype.forEach.call(files, function (file) {
        chain = chain.then(function () {
          var fd = new FormData();
          fd.append('image', file);
          return fetch(uploadUrl, { method: 'POST', body: fd, credentials: 'same-origin' })
            .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
            .then(function (res) {
              if (res.ok && res.j.url) applyImage(targetId, res.j.url, multi);
            });
        });
      });
      chain.then(function () { markDirty(); }).catch(function () { setState('Erreur upload', 'is-dirty'); });
    });
  }

  function addElement(type) {
    var d = DEFAULTS[type] || {};
    var model = {
      id: uid(),
      type: type,
      x: 32 + (elements.length % 5) * 18,
      y: 32 + (elements.length % 5) * 18,
      w: d.w || 0,
      h: d.h || 0,
      text: d.text || '',
      src: d.src || '',
      href: d.href || '',
      images: (d.images || []).slice(),
      style: d.style ? JSON.parse(JSON.stringify(d.style)) : {}
    };
    elements.push(model);
    select(model.id);
    renderCanvas();
    markDirty();
    if (type === 'image') pickImage(model.id);
  }

  function serialize() {
    return elements.map(function (m) {
      var out = {
        id: m.id,
        type: m.type,
        x: m.x || 0,
        y: m.y || 0,
        w: m.w || 0
      };
      if (m.h) out.h = m.h;
      if (m.text) out.text = m.text;
      if (m.src) out.src = m.src;
      if (m.href) out.href = m.href;
      if (m.images && m.images.length) out.images = m.images.slice();
      if (m.style && Object.keys(m.style).length) out.style = m.style;
      return out;
    });
  }

  function schedulePreview() {
    if (!previewPushUrl || !previewFrame) return;
    clearTimeout(previewTimer);
    previewTimer = setTimeout(pushPreview, 400);
  }

  function refreshPreviewFrame() {
    if (!previewFrame || !previewFrameUrl) return;
    previewFrame.src = previewFrameUrl + (previewFrameUrl.indexOf('?') >= 0 ? '&' : '?') + 't=' + Date.now();
  }

  function pushPreview() {
    if (!previewPushUrl) return refreshPreviewFrame();
    fetch(previewPushUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ elements: serialize(), canvas: {} })
    }).then(function () { refreshPreviewFrame(); }).catch(function () { refreshPreviewFrame(); });
  }

  function save() {
    setState('Enregistrement…');
    return fetch(saveUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ elements: serialize(), canvas: {}, published: published })
    })
      .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.ok) {
          dirty = false;
          published = !!res.j.published;
          savedSnapshot = JSON.stringify(elements);
          if (cancelBtn) cancelBtn.hidden = true;
          renderPubBtn();
          setState(published ? 'Enregistré · publié' : 'Enregistré', 'is-saved');
          refreshPreviewFrame();
        } else {
          setState((res.j && res.j.error) || 'Erreur', 'is-dirty');
        }
      })
      .catch(function () { setState('Erreur réseau', 'is-dirty'); });
  }

  function cancelEdits() {
    if (!savedSnapshot) return;
    try {
      elements = JSON.parse(savedSnapshot);
    } catch (_) { return; }
    selectedId = null;
    dirty = false;
    if (cancelBtn) cancelBtn.hidden = true;
    renderCanvas();
    setState('Modifications annulées', '');
    pushPreview();
  }

  function load() {
    var raw = root.getAttribute('data-layout');
    var data = null;
    try { data = raw && raw !== 'null' ? JSON.parse(raw) : null; } catch (_) {}
    if (data && Array.isArray(data.elements)) {
      elements = data.elements.map(function (m) {
        return {
          id: m.id || uid(),
          type: m.type,
          x: m.x || 0,
          y: m.y || 0,
          w: m.w || 0,
          h: m.h || 0,
          text: m.text || '',
          src: m.src || '',
          href: m.href || '',
          images: (m.images || []).slice(),
          style: m.style || {}
        };
      });
      savedSnapshot = JSON.stringify(elements);
      setState(published ? 'Publié' : 'Enregistré', 'is-saved');
    } else {
      elements = [];
      setState('Page vide', '');
    }
    renderPubBtn();
    renderCanvas();
    pushPreview();
  }

  /* ----- Panneau propriétés ----- */
  function field(label, html) {
    return '<div class="pe-prop"><label>' + label + '</label>' + html + '</div>';
  }

  function renderProps() {
    if (!propsEl) return;
    var m = selectedId ? findEl(selectedId) : null;
    if (!m) {
      propsEl.innerHTML = '<p class="pe-prop-empty">Sélectionnez un élément pour modifier son style, texte ou images.</p>';
      return;
    }

    var html = '<h4 class="pe-prop-title">' + m.type.charAt(0).toUpperCase() + m.type.slice(1) + '</h4>';

    if (m.type === 'heading' || m.type === 'text' || m.type === 'button') {
      html += field('Texte', '<input type="text" data-prop="text" value="' + esc(m.text || '') + '">');
    }
    if (m.type === 'button') {
      html += field('Lien', '<input type="text" data-prop="href" value="' + esc(m.href || '') + '" placeholder="https://…">');
    }
    if (m.type === 'image') {
      html += field('Image', '<input type="text" data-prop="src" value="' + esc(m.src || '') + '"><button type="button" class="pe-prop-add" data-pick-image>Choisir un fichier</button>');
    }
    if (m.type === 'slider' || m.type === 'gallery') {
      html += '<div class="pe-prop"><label>Images</label><div class="pe-prop-imgs" data-prop-imgs>';
      (m.images || []).forEach(function (src, i) {
        html += '<div class="pe-prop-img"><img src="' + esc(src) + '" alt=""><button type="button" data-rm-img="' + i + '">×</button></div>';
      });
      html += '</div><button type="button" class="pe-prop-add" data-add-img>Ajouter une image</button></div>';
    }

    if (m.type !== 'divider' && m.type !== 'image' && m.type !== 'slider' && m.type !== 'gallery') {
      var st = m.style || {};
      html += field('Couleur texte', colorInput('color', st.color || '#1a2832'));
      if (m.type === 'button') {
        html += field('Fond', colorInput('bg', st.bg || '#b8734a'));
      }
      html += field('Police', selectInput('font', st.font || 'sans', FONT_OPTS));
      html += field('Taille <span class="pe-prop-val" data-val-size>' + (st.size || 16) + 'px</span>', rangeInput('size', st.size || 16, 10, 72));
      html += field('Alignement', alignButtons(st.align || 'left'));
    }

    if (m.type === 'divider') {
      var dst = m.style || {};
      html += field('Couleur', colorInput('color', dst.color || '#1a2832'));
      html += field('Épaisseur', rangeInput('h', m.h || 2, 1, 12));
    }

    html += field('Largeur', rangeInput('w', m.w || 200, 60, 900));

    propsEl.innerHTML = html;
    bindProps(m);
  }

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function colorInput(key, val) {
    return '<div class="pe-prop-color"><input type="color" data-style="' + key + '" value="' + esc(val) + '"><input type="text" data-style-text="' + key + '" value="' + esc(val) + '"></div>';
  }

  function rangeInput(key, val, min, max) {
    return '<input type="range" data-key="' + key + '" min="' + min + '" max="' + max + '" value="' + val + '">';
  }

  function selectInput(key, val, opts) {
    var h = '<select data-style="' + key + '">';
    opts.forEach(function (o) {
      h += '<option value="' + o[0] + '"' + (val === o[0] ? ' selected' : '') + '>' + o[1] + '</option>';
    });
    return h + '</select>';
  }

  function alignButtons(val) {
  var dirs = [['left', '⬅'], ['center', '⬌'], ['right', '➡']];
    var h = '<div class="pe-prop-align">';
    dirs.forEach(function (d) {
      h += '<button type="button" data-align="' + d[0] + '" class="' + (val === d[0] ? 'is-on' : '') + '">' + d[1] + '</button>';
    });
    return h + '</div>';
  }

  function bindProps(m) {
    propsEl.querySelectorAll('[data-prop]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        updateModel(m.id, { [inp.getAttribute('data-prop')]: inp.value });
      });
    });
    propsEl.querySelectorAll('[data-style]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var key = inp.getAttribute('data-style');
        if (!m.style) m.style = {};
        m.style[key] = inp.value;
        var txt = propsEl.querySelector('[data-style-text="' + key + '"]');
        if (txt) txt.value = inp.value;
        renderCanvas();
        markDirty();
      });
    });
    propsEl.querySelectorAll('[data-style-text]').forEach(function (inp) {
      inp.addEventListener('change', function () {
        var key = inp.getAttribute('data-style-text');
        if (!m.style) m.style = {};
        m.style[key] = inp.value;
        renderCanvas();
        markDirty();
      });
    });
    propsEl.querySelectorAll('[data-key]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var key = inp.getAttribute('data-key');
        var v = parseInt(inp.value, 10);
        if (key === 'w' || key === 'h') {
          updateModel(m.id, { [key]: v });
        } else if (key === 'size') {
          if (!m.style) m.style = {};
          m.style.size = v;
          var valEl = propsEl.querySelector('[data-val-size]');
          if (valEl) valEl.textContent = v + 'px';
          renderCanvas();
          markDirty();
        }
      });
    });
    propsEl.querySelectorAll('[data-align]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!m.style) m.style = {};
        m.style.align = btn.getAttribute('data-align');
        renderProps();
        renderCanvas();
        markDirty();
      });
    });
    var pick = propsEl.querySelector('[data-pick-image]');
    if (pick) pick.addEventListener('click', function () { pickImage(m.id); });
    var addImg = propsEl.querySelector('[data-add-img]');
    if (addImg) addImg.addEventListener('click', function () { pickImage(m.id, true); });
    propsEl.querySelectorAll('[data-rm-img]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var i = parseInt(btn.getAttribute('data-rm-img'), 10);
        m.images.splice(i, 1);
        renderProps();
        renderCanvas();
        markDirty();
      });
    });
  }

  root.querySelectorAll('[data-add]').forEach(function (btn) {
    btn.addEventListener('click', function () { addElement(btn.getAttribute('data-add')); });
  });
  if (saveBtn) saveBtn.addEventListener('click', save);
  if (cancelBtn) cancelBtn.addEventListener('click', cancelEdits);
  if (pubBtn) pubBtn.addEventListener('click', function () {
    published = !published;
    renderPubBtn();
    save();
  });
  if (clearBtn) clearBtn.addEventListener('click', function () {
    if (!elements.length) return;
    if (window.confirm('Effacer tous les éléments de la page ?')) {
      elements = [];
      selectedId = null;
      renderCanvas();
      markDirty();
    }
  });
  canvas.addEventListener('pointerdown', function (e) {
    if (e.target === canvas) select(null);
  });
  canvas.addEventListener('keydown', function (e) {
    if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId && !e.target.isContentEditable) {
      e.preventDefault();
      removeElement(selectedId);
    }
  });
  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  load();
})();
