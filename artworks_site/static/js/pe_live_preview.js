/* Délègue à pe_preview_modal.js — conservé pour compatibilité des imports */
(function () {
  'use strict';
  if (!window.PeLivePreview && window.PePagePreview) {
    window.PeLivePreview = {
      init: function (o) { PePagePreview.init(o); },
      render: function (l) { PePagePreview.render(l); },
      refresh: function () { return PePagePreview.refresh(); },
      refreshFromServer: function () { return PePagePreview.refreshFromServer(); },
      refreshFull: function () { PePagePreview.refreshPublic(); }
    };
  }
})();
