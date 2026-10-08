import { parseInvitation } from './remote-profile.js';
import { measureTextRegions } from './text-fit.js';

function openInvitation() {
  if (!parseInvitation(location.href)) return false;
  location.replace(`./remote.html${location.hash}`);
  return true;
}

if (!openInvitation()) {
  window.addEventListener('hashchange', openInvitation);
  const markerList = document.querySelector('#marker-list');
  if (markerList) {
    const search = document.querySelector('#marker-search');
    const family = document.querySelector('#marker-family');
    const rows = [...markerList.children];
    const filter = () => {
      const term = search.value.trim().toLocaleLowerCase('en');
      let visible = 0;
      for (const row of rows) {
        row.hidden = (family.value && row.dataset.markerGroup !== family.value)
          || !row.textContent.toLocaleLowerCase('en').includes(term);
        if (!row.hidden) visible++;
      }
      document.querySelector('#marker-count').textContent = `${visible} of ${rows.length} current marker types`;
      document.querySelector('#marker-empty').hidden = visible !== 0;
    };
    const reset = () => { search.value = ''; family.value = ''; filter(); };
    search.addEventListener('input', filter);
    family.addEventListener('change', filter);
    document.querySelector('#marker-reset').addEventListener('click', reset);
    window.addEventListener('hashchange', () => {
      const target = document.getElementById(location.hash.slice(1));
      if (target?.parentElement === markerList && target.hidden) { reset(); target.scrollIntoView(); }
    });
    document.querySelector('#marker-filters').hidden = false;
    filter();
  }
  measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
}
