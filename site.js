import { parseInvitation } from './remote-profile.js';
import { measureTextRegions } from './text-fit.js';

function openInvitation() {
  if (!parseInvitation(location.href)) return false;
  location.replace(`./remote.html${location.hash}`);
  return true;
}

if (!openInvitation()) {
  window.addEventListener('hashchange', openInvitation);
  measureTextRegions().catch(() => { document.documentElement.dataset.pretextFit = 'unavailable'; });
}
