/* Settings: which criteria are listed in Window 1 (checkbox) and each criterion's weight (slider).
   The share of 100 is recalculated live over the criteria currently in the evaluation. */
import { criterionTitle, t } from '../i18n.js';
import { S, setStatus } from '../state.js';
import { $, esc } from '../utils.js';
import { persistChecklist } from './criteriaPanel.js';

const MAX_WEIGHT = 50; // matches MAX_WEIGHT in evaluation/criteria.py
let draft = null;

function shares(){
  const total = draft.filter(c=>c.enabled && c.kind!=='critical').reduce((s,c)=>s+(+c.weight||0), 0);
  return c => (!c.enabled || c.kind==='critical' || !total) ? null : Math.round((+c.weight||0)/total*1000)/10;
}

function updateShares(){
  const share = shares();
  draft.forEach((c,i)=>{
    const el = $('setList').querySelector(`[data-share="${i}"]`);
    if(el) el.textContent = c.kind==='critical' ? t('cp.noWeight') : share(c)==null ? t('settings.off') : t('settings.share', {p: share(c)});
  });
}

function render(){
  $('setList').innerHTML = draft.map((c,i)=>`
    <div class="set-row">
      <label class="set-name"><input type="checkbox" data-vis="${i}" ${c.visible?'checked':''}> ${esc(criterionTitle(c))}
        <span class="muted">${esc(c.id)}</span></label>
      ${c.kind==='critical' ? '<span></span><span></span>' : `
      <input type="range" min="0" max="${MAX_WEIGHT}" step="1" value="${+c.weight||0}" data-w="${i}" aria-label="${esc(criterionTitle(c))}">
      <output data-wv="${i}">${+c.weight||0}</output>`}
      <span class="muted set-share" data-share="${i}"></span>
    </div>`).join('');
  $('setList').querySelectorAll('[data-vis]').forEach(el=>el.onchange=()=>{ draft[+el.dataset.vis].visible = el.checked; });
  $('setList').querySelectorAll('[data-w]').forEach(el=>el.oninput=()=>{
    const i = +el.dataset.w; draft[i].weight = +el.value;
    $('setList').querySelector(`[data-wv="${i}"]`).textContent = el.value;
    updateShares();
  });
  updateShares();
  $('setErr').textContent = '';
}

export function openSettings(){
  if(!S.checklist) return;
  draft = structuredClone(S.checklist.criteria);
  render();
  $('setDlg').showModal();
}

async function onSave(){
  // a criterion hidden from the list can't stay in the evaluation
  const criteria = draft.map(c => c.visible ? c : {...c, enabled:false});
  if(await persistChecklist(criteria, true)){ $('setDlg').close(); setStatus(t('settings.saved')); }
  else $('setErr').textContent = $('status').textContent;
}

export function initSettings(){
  $('settings').onclick = openSettings;
  $('setSave').onclick = onSave;
  $('setCancel').onclick = () => $('setDlg').close();
}
