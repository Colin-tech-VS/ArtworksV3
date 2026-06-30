/* Mode intelligent — Aria embarquée dans l'éditeur de page. */
(function () {
  'use strict';
  var root = document.getElementById('pe-aria');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url');
  var log = root.querySelector('[data-aria-log]');
  var form = root.querySelector('[data-aria-form]');
  var input = root.querySelector('[data-aria-input]');
  var busy = false;

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function mdToHtml(text) {
    var lines = String(text || '').split(/\n/);
    var html = '';
    var inList = false;
    function inline(s) {
      s = escapeHtml(s);
      s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, function (_, alt, url) {
        return '<img src="' + url + '" alt="' + alt + '">';
      });
      s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (_, label, href) {
        return '<a href="' + href + '" target="_blank" rel="noopener">' + label + '</a>';
      });
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
      return s;
    }
    lines.forEach(function (ln) {
      var t = ln.trim();
      if (/^[-*]\s+/.test(t)) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += '<li>' + inline(t.replace(/^[-*]\s+/, '')) + '</li>';
        return;
      }
      if (inList) { html += '</ul>'; inList = false; }
      if (!t) return;
      if (/^###\s+/.test(t)) html += '<h4>' + inline(t.replace(/^###\s+/, '')) + '</h4>';
      else if (/^##\s+/.test(t)) html += '<h3>' + inline(t.replace(/^##\s+/, '')) + '</h3>';
      else html += '<p>' + inline(t) + '</p>';
    });
    if (inList) html += '</ul>';
    return html;
  }

  function bubble(cls, html) {
    var div = document.createElement('div');
    div.className = 'pe-aria-msg ' + cls;
    div.innerHTML = html;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function applyActions(actions) {
    if (!actions || !actions.length) return;
    actions.forEach(function (a) {
      if (a.type === 'redirect' && a.url) window.location.href = a.url;
      else if (a.type === 'reload' || a.type === 'login') {
        setTimeout(function () { window.location.reload(); }, 900);
      }
    });
  }

  function send(text) {
    if (!text || busy) return;
    busy = true;
    bubble('user', escapeHtml(text).replace(/\n/g, '<br>'));
    var typing = bubble('bot is-typing', 'Aria réfléchit…');

    fetch(apiUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ message: text })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        typing.remove();
        if (res.data.reply) {
          bubble('bot', mdToHtml(res.data.reply));
          applyActions(res.data.actions);
        } else {
          bubble('err', escapeHtml(res.data.error || 'Aria rencontre une difficulté. Réessayez.'));
        }
      })
      .catch(function () {
        typing.remove();
        bubble('err', 'Connexion impossible — vérifiez votre réseau et réessayez.');
      })
      .finally(function () { busy = false; input.focus(); });
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var text = input.value.trim();
    input.value = '';
    send(text);
  });
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  root.querySelectorAll('[data-prompt]').forEach(function (chip) {
    chip.addEventListener('click', function () {
      send(chip.getAttribute('data-prompt'));
    });
  });
})();
