/* Rendu client des blocs page publique — miroir de page_blocks.py + _pubpage_canvas.html */
(function () {
  'use strict';

  var FONT_STACKS = {
    sans: "'Outfit', 'Helvetica Neue', Arial, sans-serif",
    serif: "'Cormorant Garamond', Georgia, 'Times New Roman', serif",
    display: "'Cormorant Garamond', Georgia, serif",
    mono: "'SFMono-Regular', Consolas, monospace"
  };

  var DEFAULT_H = { heading: 60, button: 48, divider: 24, text: 44 };

  function resolveImg(ref) {
    if (!ref) return '';
    ref = String(ref).trim();
    if (ref.indexOf('http://') === 0 || ref.indexOf('https://') === 0) {
      if (ref.indexOf('/static/uploads/') >= 0) {
        var k = ref.split('/static/uploads/').pop().split('?')[0];
        var c = window.__IMG_CFG__ || {};
        return (c.uploadBase || '/static/uploads/') + k;
      }
      return ref;
    }
    var cfg = window.__IMG_CFG__ || { uploadBase: '/static/uploads/', staticPrefix: '/static/' };
    if (ref.indexOf('demo/') === 0) return cfg.staticPrefix + ref;
    if (ref.indexOf('/') >= 0 && ref.indexOf('uploads/') !== 0) {
      return cfg.staticPrefix + ref.replace(/^\//, '');
    }
    return cfg.uploadBase + ref.replace(/^uploads\//, '');
  }

  function styleToCss(style) {
    if (!style || typeof style !== 'object') return '';
    var parts = [];
    if (style.color) parts.push('color:' + style.color);
    if (style.bg) parts.push('background:' + style.bg);
    if (FONT_STACKS[style.font]) parts.push('font-family:' + FONT_STACKS[style.font]);
    if (style.size) {
      parts.push('font-size:' + style.size + 'px');
      parts.push((style.font === 'serif' || style.font === 'display') ? 'line-height:1.45' : 'line-height:1.6');
    }
    if (style.weight) parts.push('font-weight:' + style.weight);
    if (style.align) parts.push('text-align:' + style.align);
    if (style.radius) parts.push('border-radius:' + style.radius + 'px;overflow:hidden');
    return parts.join(';');
  }

  function layoutHeight(elements) {
    var bottom = 0;
    (elements || []).forEach(function (el) {
      var y = parseFloat(el.y) || 0;
      var h = parseFloat(el.h) || 0;
      if (!h) h = DEFAULT_H[el.type] || 44;
      bottom = Math.max(bottom, y + h);
    });
    return Math.max(320, Math.round(bottom) + 60);
  }

  function esc(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function posStyle(el) {
    return 'left:' + (el.x || 0) + 'px;top:' + (el.y || 0) + 'px;';
  }

  function renderElement(el) {
    var node = document.createElement('div');
    var css = styleToCss(el.style || {});
    var type = el.type;

    if (type === 'image' && el.src) {
      node.className = 'pubpage-el t-image';
      node.style.cssText = posStyle(el) + 'width:' + (el.w || 240) + 'px;height:' + (el.h || 160) + 'px;' + css;
      node.innerHTML = '<img src="' + esc(resolveImg(el.src)) + '" alt="" loading="lazy">';
      return node;
    }
    if (type === 'heading') {
      node.className = 'pubpage-el t-heading';
      node.style.cssText = posStyle(el) + (el.w ? 'width:' + el.w + 'px;' : '') + css;
      node.textContent = el.text || '';
      return node;
    }
    if (type === 'button') {
      var tag = el.href ? 'a' : 'span';
      node = document.createElement(tag);
      node.className = 'pubpage-el t-button';
      node.style.cssText = posStyle(el) + css;
      if (el.href) {
        node.href = el.href;
        node.target = '_blank';
        node.rel = 'noopener';
      }
      node.textContent = el.text || 'Bouton';
      return node;
    }
    if (type === 'divider') {
      node.className = 'pubpage-el t-divider';
      node.style.cssText = posStyle(el) + 'width:' + (el.w || 600) + 'px;' + css;
      var span = document.createElement('span');
      span.style.height = (el.h || 2) + 'px';
      node.appendChild(span);
      return node;
    }
    if (type === 'slider') {
      node.className = 'pubpage-el t-slider';
      node.style.cssText = posStyle(el) + 'width:' + (el.w || 860) + 'px;height:' + (el.h || 380) + 'px;' + css;
      (el.images || []).forEach(function (src) {
        var slide = document.createElement('div');
        slide.className = 'pubpage-slide';
        slide.innerHTML = '<img src="' + esc(resolveImg(src)) + '" alt="" loading="lazy">';
        node.appendChild(slide);
      });
      return node;
    }
    if (type === 'gallery') {
      node.className = 'pubpage-el t-gallery';
      node.style.cssText = posStyle(el) + 'width:' + (el.w || 860) + 'px;' + (el.h ? 'height:' + el.h + 'px;' : '') + css;
      (el.images || []).forEach(function (src) {
        var cell = document.createElement('div');
        cell.className = 'pubpage-cell';
        cell.innerHTML = '<img src="' + esc(resolveImg(src)) + '" alt="" loading="lazy">';
        node.appendChild(cell);
      });
      return node;
    }
    node.className = 'pubpage-el t-text';
    node.style.cssText = posStyle(el) + (el.w ? 'width:' + el.w + 'px;' : '') + css;
    node.textContent = el.text || '';
    return node;
  }

  function render(container, layout) {
    if (!container) return;
    var elements = [];
    if (Array.isArray(layout)) elements = layout;
    else if (layout && Array.isArray(layout.elements)) elements = layout.elements;

    container.innerHTML = '';
    if (!elements.length) {
      var empty = document.createElement('div');
      empty.className = 'pe-preview-empty';
      empty.innerHTML = '<p>Votre page est vide</p><span>Ajoutez des blocs ou demandez à Aria de structurer votre contenu.</span>';
      container.appendChild(empty);
      return;
    }

    var height = layoutHeight(elements);
    var wrap = document.createElement('div');
    wrap.className = 'pubpage';
    wrap.style.height = height + 'px';
    elements.forEach(function (el) {
      if (el && el.type) wrap.appendChild(renderElement(el));
    });
    container.appendChild(wrap);
  }

  window.PePageRenderer = {
    render: render,
    styleToCss: styleToCss,
    layoutHeight: layoutHeight,
    resolveImg: resolveImg
  };
})();
