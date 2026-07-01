/* Mode intelligent — Aria embarquée + aperçu live + brouillon Enregistrer/Annuler */
(function () {
  'use strict';
  var shell = document.getElementById('pe-intelligent');
  var root = document.getElementById('pe-aria');
  if (!root) return;

  var apiUrl = root.getAttribute('data-api-url');
  var previewUrl = shell ? shell.getAttribute('data-preview-url') : '';
  var layoutApiUrl = shell ? shell.getAttribute('data-layout-api') : '';
  var draftApplyUrl = shell ? shell.getAttribute('data-draft-apply') : '';
  var draftDiscardUrl = shell ? shell.getAttribute('data-draft-discard') : '';
  var draftStatusUrl = shell ? shell.getAttribute('data-draft-status') : '';
  var publicUrl = shell ? shell.getAttribute('data-public-url') : '';
  var log = root.querySelector('[data-aria-log]');
  var form = root.querySelector('[data-aria-form]');
  var input = root.querySelector('[data-aria-input]');
  var busy = false;
  var chatContext = [];
  var signupState = null;
  var loginState = null;

  function pushContext(role, content) {
    chatContext.push({ role: role, content: content });
    if (chatContext.length > 14) chatContext = chatContext.slice(-14);
  }

  function refreshPreview() {
    if (window.PePagePreview) {
      if (PePagePreview.refreshFromServer) PePagePreview.refreshFromServer();
      else PePagePreview.refresh();
    }
  }

  function refreshPreviewWhenReady(expectedCount, attempt) {
    attempt = attempt || 0;
    var url = layoutApiUrl || draftStatusUrl;
    if (!url) {
      refreshPreview();
      return;
    }
    fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        var count = d.element_count || 0;
        if (window.PePagePreview && PePagePreview.render && d.layout) {
          PePagePreview.render(d.layout);
        }
        if (count >= expectedCount || attempt >= 5 || !expectedCount) {
          refreshPreview();
        } else {
          setTimeout(function () { refreshPreviewWhenReady(expectedCount, attempt + 1); }, 150);
        }
      })
      .catch(function () { refreshPreview(); });
  }

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

  function showDraftBar() {
    if (!shell) return;
    var bar = shell.querySelector('[data-draft-bar]');
    if (bar) { bar.hidden = false; return; }
    bar = document.createElement('div');
    bar.className = 'pe-draft-bar';
    bar.setAttribute('data-draft-bar', '');
    bar.innerHTML =
      '<span>Modifications en attente — validez pour publier ou annulez.</span>' +
      '<div class="pe-draft-actions">' +
      '<button type="button" class="pe-tool" data-draft-discard>Annuler</button>' +
      '<button type="button" class="btn-solid" data-draft-apply>Enregistrer</button>' +
      '</div>';
    shell.insertBefore(bar, shell.firstChild);
    bindDraftButtons(bar);
  }

  function hideDraftBar() {
    var bar = shell && shell.querySelector('[data-draft-bar]');
    if (bar) bar.hidden = true;
  }

  function applyDraft() {
    if (!draftApplyUrl) return;
    fetch(draftApplyUrl, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          hideDraftBar();
          refreshPreview();
          bubble('bot', '<p><strong>Page enregistrée.</strong> Vos modifications sont en ligne.</p>');
        } else {
          bubble('err', escapeHtml(d.error || 'Échec de l\'enregistrement.'));
        }
      })
      .catch(function () { bubble('err', 'Erreur réseau.'); });
  }

  function discardDraft() {
    if (!draftDiscardUrl) return;
    fetch(draftDiscardUrl, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          hideDraftBar();
          refreshPreview();
          bubble('bot', '<p>Modifications annulées — retour à la version enregistrée.</p>');
        }
      })
      .catch(function () { bubble('err', 'Erreur réseau.'); });
  }

  function bindDraftButtons(scope) {
    var rootScope = scope || shell;
    if (!rootScope) return;
    var applyBtn = rootScope.querySelector('[data-draft-apply]');
    var discardBtn = rootScope.querySelector('[data-draft-discard]');
    if (applyBtn) applyBtn.addEventListener('click', applyDraft);
    if (discardBtn) discardBtn.addEventListener('click', discardDraft);
  }

  function applyActions(actions) {
    if (!actions || !actions.length) return;
    var preview = false;
    var draft = false;
    var expectedCount = 0;
    var redirectUrl = null;
    actions.forEach(function (a) {
      if (a.type === 'redirect' && a.url) redirectUrl = a.url;
      else if (a.type === 'login') redirectUrl = redirectUrl || '/dashboard';
      else if (a.type === 'page_preview' || a.type === 'page_updated') {
        preview = true;
        if (a.draft) draft = true;
        if (a.element_count) expectedCount = a.element_count;
      }
    });
    if (redirectUrl) {
      window.location.href = redirectUrl;
      return;
    }
    actions.forEach(function (a) {
      if (a.type === 'reload') {
        setTimeout(function () { window.location.reload(); }, 900);
      }
    });
    if (preview) {
      setTimeout(function () {
        if (draft && expectedCount) refreshPreviewWhenReady(expectedCount, 0);
        else refreshPreview();
      }, 80);
      if (draft) showDraftBar();
    }
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
      body: JSON.stringify({
        message: text,
        context: chatContext,
        signup_state: signupState,
        login_state: loginState,
      })
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        typing.remove();
        if (res.data.reply) {
          bubble('bot', mdToHtml(res.data.reply));
          pushContext('user', text);
          pushContext('assistant', res.data.reply);
          if (res.data.signup_state) signupState = res.data.signup_state;
          else if (res.data.actions && res.data.actions.some(function (a) {
            return a.type === 'redirect' || a.type === 'login';
          })) signupState = null;
          if (res.data.login_state) loginState = res.data.login_state;
          else if (res.data.actions && res.data.actions.some(function (a) {
            return a.type === 'redirect' || a.type === 'login';
          })) loginState = null;
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

  bindDraftButtons(shell);
})();
