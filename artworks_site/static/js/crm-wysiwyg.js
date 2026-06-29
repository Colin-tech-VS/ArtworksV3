/** WYSIWYG Quill pour tous les textarea CRM (.crm-wysiwyg) */
(function () {
  const editors = new Map();

  function syncEditor(ta, editor) {
    ta.value = editor.root.innerHTML;
  }

  function initTextarea(ta) {
    if (ta.dataset.quillInit === '1') return;
    ta.dataset.quillInit = '1';
    ta.style.display = 'none';

    const wrap = document.createElement('div');
    wrap.className = 'crm-quill-wrap' + (ta.classList.contains('tall') ? ' crm-quill-tall' : '');
    ta.parentNode.insertBefore(wrap, ta);

    const editorEl = document.createElement('div');
    editorEl.className = 'crm-quill-editor';
    wrap.appendChild(editorEl);

    const editor = new Quill(editorEl, {
      theme: 'snow',
      modules: {
        toolbar: [
          [{ header: [1, 2, 3, false] }],
          ['bold', 'italic', 'underline', 'strike'],
          [{ list: 'ordered' }, { list: 'bullet' }],
          [{ align: [] }],
          ['link'],
          ['clean'],
        ],
      },
    });

    if (ta.value && ta.value.trim()) {
      editor.clipboard.dangerouslyPasteHTML(ta.value);
    }

    editors.set(ta, editor);
    editor.on('text-change', () => {
      syncEditor(ta, editor);
      ta.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const form = ta.closest('form');
    if (form) {
      form.addEventListener('submit', () => syncEditor(ta, editor));
    }
  }

  function initAll() {
    document.querySelectorAll('textarea.crm-wysiwyg').forEach(initTextarea);
  }

  window.crmWysiwyg = {
    getHtml(ta) {
      const ed = editors.get(ta);
      return ed ? ed.root.innerHTML : (ta ? ta.value : '');
    },
    setHtml(ta, html) {
      const ed = editors.get(ta);
      if (ed) {
        ed.clipboard.dangerouslyPasteHTML(html || '');
        syncEditor(ta, ed);
      } else if (ta) {
        ta.value = html || '';
      }
    },
    refresh: initAll,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
