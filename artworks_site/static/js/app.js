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

  /* ---- Favourite hearts (compte connecté, enregistré en base) ---- */
  const body = document.body;
  const loggedIn = body.getAttribute('data-user-authenticated') === '1';
  const loginUrl = body.getAttribute('data-login-url') || '/login';
  const toggleTpl = body.getAttribute('data-favorite-toggle') || '/api/favorites/0';
  let favs = [];
  try {
    favs = JSON.parse(body.getAttribute('data-favorite-ids') || '[]').map(String);
  } catch (e) { favs = []; }

  function toggleUrl(id) {
    return toggleTpl.replace(/\/0$/, '/' + id);
  }

  function loginRedirect() {
    const next = window.location.pathname + window.location.search;
    window.location.href = loginUrl + (loginUrl.indexOf('?') >= 0 ? '&' : '?') + 'next=' + encodeURIComponent(next);
  }

  function syncCount() {
    const el = document.querySelector('[data-fav-count]');
    if (el) {
      el.textContent = favs.length;
      el.style.display = favs.length ? '' : 'none';
    }
  }

  function setFavState(btn, on) {
    btn.classList.toggle('is-fav', on);
    btn.setAttribute('aria-label', on ? 'Retirer des favoris' : 'Ajouter aux favoris');
  }

  document.querySelectorAll('.fav').forEach(btn => {
    const id = btn.getAttribute('data-id') || btn.closest('.art')?.getAttribute('data-id') || '';
    if (id && favs.includes(String(id))) setFavState(btn, true);
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      if (!id) return;
      if (!loggedIn) {
        loginRedirect();
        return;
      }
      const wasFav = btn.classList.contains('is-fav');
      setFavState(btn, !wasFav);
      fetch(toggleUrl(id), {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' }
      })
        .then(r => r.json().then(d => ({ ok: r.ok, d: d })))
        .then(res => {
          if (!res.ok || !res.d.ok) throw new Error('toggle failed');
          const sid = String(res.d.artwork_id);
          if (res.d.liked) {
            if (!favs.includes(sid)) favs.push(sid);
          } else {
            favs = favs.filter(f => f !== sid);
          }
          document.querySelectorAll('.fav[data-id="' + sid + '"]').forEach(b => setFavState(b, res.d.liked));
          syncCount();
        })
        .catch(() => setFavState(btn, wasFav));
    });
  });
  syncCount();

  /* ---- Scroll reveal ---- */
  const reveals = document.querySelectorAll('.reveal');
  if(reveals.length){
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
      }, {threshold:.08, rootMargin:'0px 0px -6% 0px'});
      reveals.forEach(r => io.observe(r));
    }
    window.addEventListener('scroll', showInView, {passive:true});
    window.addEventListener('resize', showInView, {passive:true});
    window.addEventListener('load', showInView);
    showInView();
  }

  /* ---- Subtle scroll parallax ---- */
  const parallaxEls = document.querySelectorAll('[data-parallax]');
  if(parallaxEls.length && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    let ticking = false;
    const updateParallax = () => {
      const vh = window.innerHeight;
      parallaxEls.forEach(el => {
        const rate = parseFloat(el.getAttribute('data-parallax')) || 0.05;
        const rect = el.getBoundingClientRect();
        const center = rect.top + rect.height * 0.5 - vh * 0.5;
        el.style.transform = `translateY(${center * rate}px)`;
      });
      ticking = false;
    };
    const onParallaxScroll = () => {
      if(!ticking){ ticking = true; requestAnimationFrame(updateParallax); }
    };
    window.addEventListener('scroll', onParallaxScroll, {passive:true});
    window.addEventListener('resize', onParallaxScroll, {passive:true});
    updateParallax();
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

  /* ---- Animated count-up for stat numbers ---- */
  const fmt = n => n.toLocaleString('fr-FR').replace(/ |,/g, ' ');
  const counters = document.querySelectorAll('[data-count]');
  if(counters.length){
    const run = el => {
      const target = parseInt(el.getAttribute('data-count'), 10) || 0;
      const dur = 1100, t0 = performance.now();
      const tick = now => {
        const p = Math.min((now - t0) / dur, 1);
        const eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
        el.textContent = fmt(Math.round(target * eased));
        if(p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    };
    if('IntersectionObserver' in window){
      const co = new IntersectionObserver((entries) => {
        entries.forEach(en => { if(en.isIntersecting){ run(en.target); co.unobserve(en.target); } });
      }, {threshold:.4});
      counters.forEach(c => co.observe(c));
    } else {
      counters.forEach(run);
    }
  }

  /* ---- Role selector (register) — fallback for :has + nicer toggle ---- */
  document.querySelectorAll('.role-card input').forEach(input => {
    const sync = () => {
      document.querySelectorAll('.role-card').forEach(c => c.classList.remove('selected'));
      document.querySelectorAll('.role-card input:checked').forEach(i => i.closest('.role-card').classList.add('selected'));
    };
    input.addEventListener('change', sync);
    sync();
  });

  /* ---- Toast notifications ---- */
  const TOAST_DUR = { success: 5000, error: 7000, warning: 6500, info: 5500 };
  document.querySelectorAll('[data-toast]').forEach((toast, i) => {
    const kind = [...toast.classList].find(c => c.startsWith('toast-'))?.slice(6) || 'info';
    const dur = TOAST_DUR[kind] || 5500;
    toast.style.setProperty('--toast-dur', dur + 'ms');
    toast.style.animationDelay = (i * 80) + 'ms';

    let timer;
    const dismiss = () => {
      if(toast.classList.contains('is-leaving')) return;
      toast.classList.add('is-leaving');
      toast.addEventListener('animationend', () => toast.remove(), { once: true });
    };
    const arm = () => {
      clearTimeout(timer);
      timer = setTimeout(dismiss, dur);
    };
    arm();

    toast.querySelector('[data-toast-close]')?.addEventListener('click', dismiss);
    toast.addEventListener('mouseenter', () => clearTimeout(timer));
    toast.addEventListener('mouseleave', arm);
  });

})();
