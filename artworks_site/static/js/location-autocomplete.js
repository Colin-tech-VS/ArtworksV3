(function(){
  'use strict';

  var CITIES = [
    'Paris, France','Lyon, France','Marseille, France','Bordeaux, France','Lille, France',
    'Toulouse, France','Nice, France','Nantes, France','Strasbourg, France','Montpellier, France',
    'Rennes, France','Grenoble, France','Rouen, France','Toulon, France','Dijon, France',
    'Angers, France','Nîmes, France','Aix-en-Provence, France','Saint-Étienne, France',
    'Le Havre, France','Reims, France','Metz, France','Perpignan, France','Besançon, France',
    'Orléans, France','Mulhouse, France','Caen, France','Avignon, France','Poitiers, France',
    'La Rochelle, France','Cannes, France','Antibes, France','Arles, France','Biarritz, France',
    'Bruxelles, Belgique','Anvers, Belgique','Gand, Belgique','Liège, Belgique','Charleroi, Belgique',
    'Genève, Suisse','Zurich, Suisse','Lausanne, Suisse','Bâle, Suisse','Berne, Suisse',
    'Luxembourg, Luxembourg','Montréal, Canada','Québec, Canada','Toronto, Canada','Vancouver, Canada',
    'New York, États-Unis','Los Angeles, États-Unis','Chicago, États-Unis','Miami, États-Unis',
    'San Francisco, États-Unis','London, Royaume-Uni','Berlin, Allemagne','Munich, Allemagne',
    'Madrid, Espagne','Barcelone, Espagne','Rome, Italie','Milan, Italie','Florence, Italie',
    'Venise, Italie','Naples, Italie','Lisbonne, Portugal','Porto, Portugal','Amsterdam, Pays-Bas',
    'Vienne, Autriche','Prague, République tchèque','Copenhague, Danemark','Stockholm, Suède',
    'Oslo, Norvège','Helsinki, Finlande','Athènes, Grèce','Istanbul, Turquie','Dubai, Émirats arabes unis',
    'Tokyo, Japon','Séoul, Corée du Sud','Hong Kong, Chine','Singapour, Singapour','Shanghai, Chine',
    'Pékin, Chine','Bangkok, Thaïlande','Mexico, Mexique','Buenos Aires, Argentine','São Paulo, Brésil',
    'Rio de Janeiro, Brésil','Sydney, Australie','Melbourne, Australie','Le Caire, Égypte',
    'Casablanca, Maroc','Marrakech, Maroc','Tunis, Tunisie','Dakar, Sénégal','Abidjan, Côte d\'Ivoire',
    'Johannesburg, Afrique du Sud','Le Cap, Afrique du Sud'
  ];

  function norm(s){ return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }

  function formatGoogleCity(place){
    if (!place || !place.address_components) return place && place.formatted_address ? place.formatted_address : '';
    var city = '', country = '';
    place.address_components.forEach(function(c){
      if (c.types.indexOf('locality') >= 0) city = c.long_name;
      if (c.types.indexOf('postal_town') >= 0 && !city) city = c.long_name;
      if (c.types.indexOf('administrative_area_level_2') >= 0 && !city) city = c.long_name;
      if (c.types.indexOf('country') >= 0) country = c.long_name;
    });
    if (city && country) return city + ', ' + country;
    return place.formatted_address || place.name || '';
  }

  function setupLocal(input, dropdown){
    var idx = -1, results = [];
    function hide(){ dropdown.hidden = true; dropdown.innerHTML = ''; idx = -1; results = []; }
    function pick(city){ input.value = city; hide(); input.dispatchEvent(new Event('change', {bubbles:true})); }
    function render(list){
      results = list;
      idx = -1;
      if (!list.length){ hide(); return; }
      dropdown.innerHTML = list.slice(0, 12).map(function(c, i){
        return '<button type="button" class="location-item" data-i="'+i+'">'+c+'</button>';
      }).join('');
      dropdown.hidden = false;
    }
    input.addEventListener('input', function(){
      var q = norm(input.value.trim());
      if (q.length < 2){ hide(); return; }
      render(CITIES.filter(function(c){ return norm(c).indexOf(q) >= 0; }));
    });
    input.addEventListener('keydown', function(e){
      if (dropdown.hidden) return;
      var items = dropdown.querySelectorAll('.location-item');
      if (e.key === 'ArrowDown'){ e.preventDefault(); idx = Math.min(idx + 1, items.length - 1); }
      else if (e.key === 'ArrowUp'){ e.preventDefault(); idx = Math.max(idx - 1, 0); }
      else if (e.key === 'Enter' && idx >= 0){ e.preventDefault(); pick(results[idx]); return; }
      else if (e.key === 'Escape'){ hide(); return; }
      else return;
      items.forEach(function(el, i){ el.classList.toggle('is-active', i === idx); });
    });
    dropdown.addEventListener('mousedown', function(e){
      var btn = e.target.closest('.location-item');
      if (!btn) return;
      e.preventDefault();
      pick(results[+btn.getAttribute('data-i')]);
    });
    document.addEventListener('click', function(e){
      if (!input.contains(e.target) && !dropdown.contains(e.target)) hide();
    });
  }

  function setupGoogle(input, key){
    if (!window.google || !google.maps || !google.maps.places) return false;
    var ac = new google.maps.places.Autocomplete(input, {
      types: ['(cities)'],
      fields: ['address_components', 'formatted_address', 'name']
    });
    ac.addListener('place_changed', function(){
      var val = formatGoogleCity(ac.getPlace());
      if (val) input.value = val;
    });
    input.setAttribute('autocomplete', 'off');
    return true;
  }

  function boot(){
    document.querySelectorAll('[data-location-input]').forEach(function(input){
      if (input.dataset.locationReady) return;
      input.dataset.locationReady = '1';
      var wrap = input.closest('.location-wrap');
      var dropdown = wrap && wrap.querySelector('.location-dropdown');
      var key = document.body.getAttribute('data-google-places-key');
      if (key && window.google && google.maps && google.maps.places){
        setupGoogle(input, key);
      } else if (dropdown) {
        setupLocal(input, dropdown);
      }
    });
  }

  window.ArtworksLocation = { boot: boot };

  var key = document.body.getAttribute('data-google-places-key');
  if (key){
    var s = document.createElement('script');
    s.src = 'https://maps.googleapis.com/maps/api/js?key='+encodeURIComponent(key)+'&libraries=places&callback=__artworksPlacesReady';
    s.async = true; s.defer = true;
    window.__artworksPlacesReady = boot;
    document.head.appendChild(s);
  } else {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})();
