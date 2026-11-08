/* Window 1, top: the criteria available for evaluation (those ticked in Settings).
   "+" switches a criterion into the evaluation; an included criterion gets a comment field
   that is passed to the AI. Every change is saved as a new checklist version. */
import { getChecklist, saveChecklist } from '../api/backend.js';
import { criterionTitle, t } from '../i18n.js';
import { S, setStatus } from '../state.js';
import { $, debounce, esc } from '../utils.js';

const STANDARD = ['contact','discovery','identification','consultation','empathy','dialogue','closure','critical'];

export async function loadChecklist(){
  S.checklist = await getChecklist();
  renderCriteriaPanel();
}

/* Save the whole checklist (criteria + rules); the backend validates and versions it */
export async function persistChecklist(criteria, quiet, rerender = true){
  try{
    S.checklist = await saveChecklist({criteria, general_rules: S.checklist.general_rules});
    if(rerender) renderCriteriaPanel(); // not while the user is typing a comment (would drop focus)
    if(!quiet) setStatus(t('cp.saved'));
    return true;
  }catch(err){ setStatus(err.message, true); renderCriteriaPanel(); return false; }
}

const isStandardSet = criteria => {
  const on = criteria.filter(c=>c.enabled).map(c=>c.id).sort();
  return on.length===STANDARD.length && [...STANDARD].sort().every((id,i)=>on[i]===id);
};

/* Comments are applied locally at once (so typing in two fields loses nothing) and saved after a pause */
const persistComments = debounce(async () => {
  await persistChecklist(S.checklist.criteria, true, false);
  // typing may have continued during the request: re-apply what is in the fields now
  let changed = false;
  $('cpList').querySelectorAll('.cp-comment').forEach(el => {
    const c = S.checklist.criteria.find(x=>x.id===el.dataset.id);
    if(c && (c.comment||'') !== el.value.trim()){ c.comment = el.value; changed = true; }
  });
  if(changed) persistComments();
}, 800);
const saveComment = (id, value) => {
  S.checklist.criteria = S.checklist.criteria.map(c => c.id===id ? {...c, comment:value} : c);
  persistComments();
};

export function renderCriteriaPanel(){
  const ck = S.checklist; if(!ck) return;
  const shown = ck.criteria.filter(c=>c.visible);
  $('cpCount').textContent = '· ' + t('cp.count', {n: ck.criteria.filter(c=>c.enabled).length});
  $('cpWarn').hidden = isStandardSet(ck.criteria);
  $('cpList').innerHTML = shown.map(c=>`
    <div class="cp-item ${c.enabled?'on':''}">
      <div class="cp-row">
        <button class="cp-toggle" data-id="${esc(c.id)}" title="${esc(t(c.enabled?'cp.remove':'cp.add'))}" aria-pressed="${c.enabled}">${c.enabled?'✓':'+'}</button>
        <span class="cp-name">${esc(criterionTitle(c))}</span>
        <span class="muted cp-w">${c.kind==='critical' ? esc(t('cp.noWeight')) : esc(t('cp.weight', {w:c.weight}))}</span>
      </div>
      ${c.enabled ? `<textarea class="cp-comment" data-id="${esc(c.id)}" rows="1" placeholder="${esc(t('cp.comment.ph'))}">${esc(c.comment||'')}</textarea>` : ''}
    </div>`).join('');
  $('cpList').querySelectorAll('.cp-toggle').forEach(b=>b.onclick=()=>{
    const criteria = ck.criteria.map(c => c.id===b.dataset.id ? {...c, enabled:!c.enabled} : c);
    persistChecklist(criteria);
  });
  $('cpList').querySelectorAll('.cp-comment').forEach(el=>el.oninput=()=>saveComment(el.dataset.id, el.value));
}
