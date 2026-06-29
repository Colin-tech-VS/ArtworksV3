/* ============================================================
   Artworks V3 — shared interactions (vanilla JS)
   ============================================================ */
(function(){
  'use strict';

  /* ---- Sticky header discreet on scroll ---- */
  const head = document.querySelector('.site-head');
  if(head){
    const onScroll = () => head.classList.toggle('scrolled', window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, {passive:true});
  }

  /* ---- Favourite hearts (local state) ---- */
  const FAV_KEY = 'artworks_favs';
  let favs = [];
  try{ favs = JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); }catch(e){ favs = []; }

  function syncCount(){
    const el = document.querySelector('[data-fav-count]');
    if(el){ el.textContent = favs.length; el.style.display = favs.length ? '' : 'none'; }
  }

  document.querySelectorAll('.fav').forEach(btn => {
    const id = btn.getAttribute('data-id') || btn.closest('.art')?.getAttribute('data-id') || '';
    if(id && favs.includes(id)) btn.classList.add('is-fav');
    btn.addEventListener('click', e => {
      e.preventDefault(); e.stopPropagation();
      btn.classList.toggle('is-fav');
      if(btn.classList.contains('is-fav')){
        if(id && !favs.includes(id)) favs.push(id);
      } else {
        favs = favs.filter(f => f !== id);
      }
      try{ localStorage.setItem(FAV_KEY, JSON.stringify(favs)); }catch(e){}
      syncCount();
    });
  });
  syncCount();

  /* ---- Scroll reveal ---- */
  const reveals = document.querySelectorAll('.reveal');
  if(reveals.length){
    // Fallback that can never leave content stuck hidden: reveal anything whose
    // top has entered (or passed) the viewport. Idempotent and cheap.
    const showInView = () => {
      const vh = window.innerHeight || document.documentElement.clientHeight;
      reveals.forEach(r => {
        if(r.classList.contains('in')) return;
        if(r.getBoundingClientRect().top < vh * 0.92) r.classList.add('in');
      });
    };
    if('IntersectionObserver' in window){
      const io = new IntersectionObserver((entries) => {
        entries.forEach(en => {
          if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); }
        });
      }, {threshold:.08, rootMargin:'0px 0px -8% 0px'});
      reveals.forEach(r => io.observe(r));
    }
    window.addEventListener('scroll', showInView, {passive:true});
    window.addEventListener('resize', showInView, {passive:true});
    window.addEventListener('load', showInView);
    showInView();
  }

  /* ---- Mobile drawer ---- */
  const drawer = document.querySelector('.drawer');
  const openBtn = document.querySelector('.burger');
  const closeBtn = document.querySelector('[data-close-drawer]');
  if(drawer && openBtn){
    openBtn.addEventListener('click', () => { drawer.classList.add('open'); document.body.style.overflow='hidden'; });
    closeBtn && closeBtn.addEventListener('click', () => { drawer.classList.remove('open'); document.body.style.overflow=''; });
  }

  /* ---- Explorer: filters + sort ---- */
  const grid = document.querySelector('[data-filter-grid]');
  if(grid){
    const chips = document.querySelectorAll('[data-filter]');
    const countEl = document.querySelector('[data-result-count]');
    const active = {}; // group -> Set of values

    function apply(){
      const items = grid.querySelectorAll('[data-tags]');
      let shown = 0;
      items.forEach(it => {
        const tags = (it.getAttribute('data-tags') || '').split(' ');
        let ok = true;
        for(const g in active){
          if(active[g].size === 0) continue;
          const hit = [...active[g]].some(v => tags.includes(v));
          if(!hit){ ok = false; break; }
        }
        it.style.display = ok ? '' : 'none';
        if(ok) shown++;
      });
      if(countEl) countEl.textContent = shown;
    }

    chips.forEach(chip => {
      chip.addEventListener('click', () => {
        const g = chip.getAttribute('data-group');
        const v = chip.getAttribute('data-filter');
        active[g] = active[g] || new Set();
        chip.classList.toggle('on');
        if(chip.classList.contains('on')) active[g].add(v); else active[g].delete(v);
        apply();
      });
    });

    const clearBtn = document.querySelector('[data-clear-filters]');
    clearBtn && clearBtn.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('on'));
      for(const g in active) active[g].clear();
      apply();
    });

    /* Sort */
    const sortSel = document.querySelector('[data-sort]');
    if(sortSel){
      sortSel.addEventListener('change', () => {
        const v = sortSel.value;
        const items = [...grid.querySelectorAll('[data-tags]')];
        items.sort((a,b) => {
          if(v==='price-asc')  return (+a.dataset.price) - (+b.dataset.price);
          if(v==='price-desc') return (+b.dataset.price) - (+a.dataset.price);
          if(v==='new')        return (+b.dataset.new) - (+a.dataset.new);
          return (+a.dataset.rank) - (+b.dataset.rank); // pertinence
        });
        items.forEach(it => grid.appendChild(it));
      });
    }

    /* mobile filter toggle */
    const fToggle = document.querySelector('[data-filter-toggle]');
    const sidebar = document.querySelector('[data-filter-sidebar]');
    if(fToggle && sidebar){
      fToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
  }

  /* ---- Lightbox (oeuvre page) ---- */
  const lb = document.querySelector('[data-lightbox]');
  if(lb){
    const lbImg = lb.querySelector('img');
    const triggers = document.querySelectorAll('[data-zoom]');
    function open(src){ lbImg.src = src; lb.classList.add('open'); document.body.style.overflow='hidden'; }
    function close(){ lb.classList.remove('open'); document.body.style.overflow=''; }
    triggers.forEach(t => t.addEventListener('click', () => open(t.getAttribute('data-zoom') || t.querySelector('img')?.src)));
    lb.addEventListener('click', e => { if(e.target === lb || e.target.hasAttribute('data-lb-close')) close(); });
    document.addEventListener('keydown', e => { if(e.key === 'Escape') close(); });

    /* thumbnail swap on detail page */
    const mainImg = document.querySelector('[data-main-art]');
    document.querySelectorAll('[data-thumb]').forEach(th => {
      th.addEventListener('click', () => {
        const src = th.getAttribute('data-thumb');
        if(mainImg){ mainImg.src = src; mainImg.closest('[data-zoom]')?.setAttribute('data-zoom', src); }
        document.querySelectorAll('[data-thumb]').forEach(t => t.classList.remove('active'));
        th.classList.add('active');
      });
    });
  }

  /* ---- Tabs (artiste page) ---- */
  document.querySelectorAll('[data-tabs]').forEach(tabset => {
    const btns = tabset.querySelectorAll('[data-tab]');
    btns.forEach(b => b.addEventListener('click', () => {
      btns.forEach(x => x.classList.remove('active'));
      b.classList.add('active');
      const target = b.getAttribute('data-tab');
      document.querySelectorAll('[data-panel]').forEach(p => {
        p.style.display = p.getAttribute('data-panel') === target ? '' : 'none';
      });
    }));
  });

})();
