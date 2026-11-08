/* Operator / reviewer mode. The side tab switches it; the choice is remembered in this browser. */
import { t } from '../i18n.js';
import { S, setStatus } from '../state.js';
import { $ } from '../utils.js';
import { renderAppeals } from './appeals.js';
import { renderResults } from './results.js';

export function applyMode(){
  document.body.classList.toggle('reviewer', S.reviewer);
  const tab = $('modeTab');
  tab.setAttribute('aria-pressed', String(S.reviewer));
  tab.firstElementChild.textContent = t(S.reviewer ? 'mode.operator' : 'mode.reviewer');
  if(S.evaluation) renderResults();
  renderAppeals();
}

export function initMode(){
  try{ S.reviewer = localStorage.getItem('reviewer')==='1'; }catch{}
  $('modeTab').onclick = () => {
    S.reviewer = !S.reviewer;
    try{ localStorage.setItem('reviewer', S.reviewer ? '1' : '0'); }catch{}
    $('sendNote').textContent = ''; $('decideNote').textContent = '';
    applyMode();
    if(S.reviewer) setStatus(t('mode.on'));
  };
  applyMode();
}
