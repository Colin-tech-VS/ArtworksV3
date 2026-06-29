(function () {
  'use strict';

  var root = document.getElementById('aria-widget');
  if (!root) return;

  var apiUrl = root.dataset.apiUrl;
  var siteUrl = (root.dataset.siteUrl || '').replace(/\/$/, '');

  var fab = root.querySelector('[data-aria-fab]');
  var overlay = root.querySelector('[data-aria-overlay]');
  var panel = root.querySelector('[data-aria-panel]');
  var messagesEl = root.querySelector('[data-aria-messages]');
  var welcomeEl = root.querySelector('[data-aria-welcome]');
  var form = root.querySelector('[data-aria-form]');
  var input = root.querySelector('[data-aria-input]');
  var sendBtn = root.querySelector('[data-aria-send]');
  var closeBtns = root.querySelectorAll('[data-aria-close]');
  var resetBtn = root.querySelector('[data-aria-reset]');
  var suggestions = root.querySelectorAll('[data-aria-suggestion]');

  var busy = false;

  function openPanel() {
    panel.classList.add('is-open');
    overlay.classList.add('is-open');
    fab.classList.add('is-open');
    document.body.classList.add('aria-open');
    setTimeout(function () { input.focus(); }, 400);
  }

  function closePanel() {
    panel.classList.remove('is-open');
    overlay.classList.remove('is-open');
    fab.classList.remove('is-open');
    document.body.classList.remove('aria-open');
  }

  function scrollBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function mdToHtml(text) {
    var lines = text.split('\n');
    var html = [];
    var listTag = null;

    function closeList() {
      if (listTag) {
        html.push('</' + listTag + '>');
        listTag = null;
      }
    }

    function openList(tag) {
      if (listTag !== tag) {
        closeList();
        html.push('<' + tag + '>');
        listTag = tag;
      }
    }

    function inline(s) {
      s = escapeHtml(s);
      s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
      s = s.replace(/_([^_\n]+)_/g, '<em>$1</em>');
      s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, href) {
        var url = href.charAt(0) === '/' ? siteUrl + href : href;
        return '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + label + '</a>';
      });
      return s;
    }

    for (var i = 0; i < lines.length; i++) {
      var raw = lines[i];
      var line = raw.trim();
      if (!line) {
        closeList();
        continue;
      }
      if (/^-{3,}$/.test(line)) {
        closeList();
        html.push('<hr class="aria-hr">');
        continue;
      }
      if (/^###\s+/.test(line)) {
        closeList();
        html.push('<h4 class="aria-h">' + inline(line.replace(/^###\s+/, '')) + '</h4>');
        continue;
      }
      if (/^##\s+/.test(line)) {
        closeList();
        html.push('<h3 class="aria-h">' + inline(line.replace(/^##\s+/, '')) + '</h3>');
        continue;
      }
      if (/^#\s+/.test(line)) {
        closeList();
        html.push('<h3 class="aria-h aria-h-lg">' + inline(line.replace(/^#\s+/, '')) + '</h3>');
        continue;
      }
      if (/^[-*•]\s+/.test(line)) {
        openList('ul');
        html.push('<li>' + inline(line.replace(/^[-*•]\s+/, '')) + '</li>');
        continue;
      }
      if (/^\d+\.\s+/.test(line)) {
        openList('ol');
        html.push('<li>' + inline(line.replace(/^\d+\.\s+/, '')) + '</li>');
        continue;
      }
      closeList();
      html.push('<p>' + inline(line) + '</p>');
    }
    closeList();
    return html.join('');
  }

  function hideWelcome() {
    if (welcomeEl) welcomeEl.style.display = 'none';
  }

  function appendUser(text) {
    hideWelcome();
    var wrap = document.createElement('div');
    wrap.className = 'aria-msg aria-msg-user';
    wrap.innerHTML = '<div class="aria-bubble">' + escapeHtml(text) + '</div>';
    messagesEl.appendChild(wrap);
    scrollBottom();
  }

  function showTyping() {
    hideWelcome();
    var wrap = document.createElement('div');
    wrap.className = 'aria-msg aria-msg-assistant';
    wrap.dataset.typing = '1';
    wrap.innerHTML =
      '<div class="aria-label">Aria</div>' +
      '<div class="aria-typing"><span></span><span></span><span></span></div>';
    messagesEl.appendChild(wrap);
    scrollBottom();
    return wrap;
  }

  function typewriter(el, html, done) {
    var plain = el.textContent || '';
    var temp = document.createElement('div');
    temp.innerHTML = html;
    var fullText = temp.textContent || '';
    var speed = Math.max(8, Math.min(22, 1200 / Math.max(fullText.length, 1)));
    var idx = 0;
    var cursor = document.createElement('span');
    cursor.className = 'aria-cursor';
    el.innerHTML = '';
    el.appendChild(cursor);

    function tick() {
      idx += 1;
      if (idx >= fullText.length) {
        el.innerHTML = html;
        scrollBottom();
        if (done) done();
        return;
      }
      var partial = fullText.slice(0, idx);
      el.textContent = partial;
      el.appendChild(cursor);
      scrollBottom();
      setTimeout(tick, speed);
    }
    setTimeout(tick, speed);
  }

  function revealContent(el, html) {
    el.innerHTML = html;
    el.classList.add('aria-reveal');
    scrollBottom();
  }

  function appendAssistant(text, useTypewriter) {
    var typing = messagesEl.querySelector('[data-typing="1"]');
    if (typing) typing.remove();

    var wrap = document.createElement('div');
    wrap.className = 'aria-msg aria-msg-assistant';
    wrap.innerHTML =
      '<div class="aria-label">Aria</div>' +
      '<div class="aria-content"></div>';
    messagesEl.appendChild(wrap);
    var content = wrap.querySelector('.aria-content');
    var html = mdToHtml(text);
    var hasMarkdown = /[#*_\[\]`]/.test(text);

    if (useTypewriter && !hasMarkdown && text.length < 900) {
      typewriter(content, html, function () {
        content.classList.add('aria-reveal-done');
      });
    } else {
      revealContent(content, html);
    }
  }

  function setBusy(on) {
    busy = on;
    sendBtn.disabled = on;
    input.disabled = on;
  }

  function sendMessage(text) {
    text = (text || '').trim();
    if (!text || busy) return;

    appendUser(text);
    input.value = '';
    input.style.height = 'auto';
    setBusy(true);
    showTyping();

    fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ message: text }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var typing = messagesEl.querySelector('[data-typing="1"]');
        if (typing) typing.remove();
        if (res.ok && res.data.reply) {
          appendAssistant(res.data.reply, true);
        } else {
          appendAssistant(
            res.data.error || 'Aria rencontre une difficulté. Réessayez dans un instant.',
            false
          );
        }
      })
      .catch(function () {
        var typing = messagesEl.querySelector('[data-typing="1"]');
        if (typing) typing.remove();
        appendAssistant('Connexion impossible — vérifiez votre réseau et réessayez.', false);
      })
      .finally(function () {
        setBusy(false);
        input.focus();
      });
  }

  fab.addEventListener('click', openPanel);
  overlay.addEventListener('click', closePanel);
  closeBtns.forEach(function (btn) {
    btn.addEventListener('click', closePanel);
  });

  if (resetBtn) {
    resetBtn.addEventListener('click', function () {
      fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ reset: true }),
      }).catch(function () {});
      messagesEl.innerHTML = '';
      if (welcomeEl) welcomeEl.style.display = '';
    });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    sendMessage(input.value);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input.value);
    }
  });

  input.addEventListener('input', function () {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  suggestions.forEach(function (btn) {
    btn.addEventListener('click', function () {
      sendMessage(btn.dataset.ariaSuggestion || btn.textContent);
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('is-open')) {
      closePanel();
    }
  });
})();
