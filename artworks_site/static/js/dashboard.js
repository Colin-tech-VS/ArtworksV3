(function () {
  'use strict';

  document.querySelectorAll('.dash-nav-link[href*="#"], .dash-mobile-nav a[href*="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var hash = link.getAttribute('href').split('#')[1];
      if (!hash) return;
      var el = document.getElementById(hash);
      if (el) {
        e.preventDefault();
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + hash);
      }
    });
  });

  var sections = ['oeuvres', 'series'].map(function (id) { return document.getElementById(id); }).filter(Boolean);
  if (sections.length && 'IntersectionObserver' in window) {
    var navLinks = document.querySelectorAll('.dash-nav-link[href*="#oeuvres"], .dash-nav-link[href*="#series"]');
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var id = en.target.id;
        navLinks.forEach(function (a) {
          a.classList.toggle('is-active', a.getAttribute('href').endsWith('#' + id));
        });
      });
    }, { rootMargin: '-30% 0px -55% 0px', threshold: 0 });
    sections.forEach(function (s) { io.observe(s); });
  }
})();
