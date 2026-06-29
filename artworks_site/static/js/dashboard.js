(function(){
  'use strict';

  /* ---- View toggle: table / grid ---- */
  document.querySelectorAll('[data-dash-view]').forEach(toggle => {
    const target = toggle.getAttribute('data-dash-view');
    const table = document.querySelector('[data-dash-table="' + target + '"]');
    const grid = document.querySelector('[data-dash-grid="' + target + '"]');
    if(!table || !grid) return;

    const btns = toggle.querySelectorAll('button');
    const setView = mode => {
      const isGrid = mode === 'grid';
      table.classList.toggle('is-hidden', isGrid);
      grid.classList.toggle('is-hidden', !isGrid);
      btns.forEach(b => b.classList.toggle('is-on', b.getAttribute('data-view') === mode));
      try{ localStorage.setItem('dash-view-' + target, mode); }catch(e){}
    };

    const saved = (() => { try{ return localStorage.getItem('dash-view-' + target); }catch(e){ return null; }})();
    setView(saved === 'grid' ? 'grid' : 'table');

    btns.forEach(b => b.addEventListener('click', () => setView(b.getAttribute('data-view'))));
  });

  /* ---- Smooth scroll for in-page anchors ---- */
  document.querySelectorAll('.dash-nav-link[href*="#"], .dash-mobile-nav a[href*="#"]').forEach(link => {
    link.addEventListener('click', e => {
      const hash = link.getAttribute('href').split('#')[1];
      if(!hash) return;
      const el = document.getElementById(hash);
      if(el){
        e.preventDefault();
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        history.replaceState(null, '', '#' + hash);
      }
    });
  });

  /* ---- Highlight section on scroll ---- */
  const sections = ['oeuvres', 'series'].map(id => document.getElementById(id)).filter(Boolean);
  if(sections.length && 'IntersectionObserver' in window){
    const navLinks = document.querySelectorAll('.dash-nav-link[href*="#oeuvres"], .dash-nav-link[href*="#series"]');
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if(!en.isIntersecting) return;
        const id = en.target.id;
        navLinks.forEach(a => {
          a.classList.toggle('is-active', a.getAttribute('href').endsWith('#' + id));
        });
      });
    }, { rootMargin: '-30% 0px -55% 0px', threshold: 0 });
    sections.forEach(s => io.observe(s));
  }

})();
