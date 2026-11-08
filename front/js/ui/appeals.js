/* Windows 4/5 (and the reviewer's buttons in Window 2).
   Operator: «Оспорить» in Window 3 adds a card (square with the item number + explanation);
   «Сохранить обращение» saves a draft, «Сохранить и отправить» sends it to the reviewer.
   Reviewer: sees the operator's comments, writes replies; «Подтвердить оценку» rejects the
   appeal, «Пересмотреть оценку» has the AI re-evaluate only the items with a reply. */
import { confirmAppeal, reviseAppeal, saveAppealDraft, saveReview, submitAppeal } from '../api/backend.js';
import { criterionTitle, t } from '../i18n.js';
import { fmtScore, verdict } from '../scoring.js';
import { S, setStatus } from '../state.js';
import { $, esc } from '../utils.js';
import { renderResults } from './results.js';
import { showScore } from './scoreModal.js';

const unsaved = new Map(); // evaluation id -> operator's unsaved disputes Map (kept while the page is open)

const criterion = id => S.evaluation?.criteria.find(c=>c.criterion_id===id);
const itemNo = id => S.evaluation.criteria.findIndex(c=>c.criterion_id===id) + 1;

/* The appeal that belongs to the evaluation on screen (made against it, or it is the revision) */
export function currentAppeal(){
  const a = S.appeal, e = S.evaluation;
  return a && e && (a.evaluation_id===e.id || a.revised_evaluation_id===e.id) ? a : null;
}
/* Sent appeals can't be edited by the operator */
export const appealLocked = () => !!currentAppeal() && currentAppeal().status!=='draft';

/* Called when a record / evaluation / appeal is loaded */
export function resetAppealState(){
  const a = currentAppeal(), e = S.evaluation;
  if(a && (a.status!=='draft' || !unsaved.has(e.id))) S.disputes = new Map(a.items.map(i=>[i.criterion_id, i.operator_comment]));
  else S.disputes = (e && unsaved.get(e.id)) || new Map();
  if(e && !appealLocked()) unsaved.set(e.id, S.disputes);
  S.reviews = new Map((a?.items||[]).map(i=>[i.criterion_id, i.reviewer_comment||'']));
}

export function toggleDispute(id){
  if(appealLocked()) return;
  if(S.disputes.has(id)) S.disputes.delete(id); else S.disputes.set(id,'');
  renderResults(); renderAppeals();
}

const note = (text, err) => { $('sendNote').textContent = text || ''; $('sendNote').style.color = err ? 'var(--bad)' : ''; };

function card(id, body){
  const c = criterion(id), [txt] = verdict(c);
  return `<div class="d-card"><div class="sq">3.${itemNo(id)}</div><div class="col">
    <div class="t"><b>${esc(criterionTitle(c))}</b> · ${esc(t('w4.ai'))}: ${esc(txt)}</div>${body}</div></div>`;
}

export function renderAppeals(){
  const box = $('disputes'), a = currentAppeal(), e = S.evaluation;
  for(const id of [...S.disputes.keys()]) if(!criterion(id)) S.disputes.delete(id);
  $('w4title').textContent = t(S.reviewer ? 'w4.titleReviewer' : 'w4.title');
  $('appealStatus').textContent = a ? t('appeal.status', {s: t('appeal.'+a.status)}) : '';
  $('appealStatus').className = a?.status==='submitted' ? 'st-open' : '';

  if(S.reviewer){
    const items = a && a.status!=='draft' ? a.items.filter(i=>criterion(i.criterion_id)) : [];
    const editable = a?.status==='submitted';
    box.innerHTML = items.length ? items.map(i=>card(i.criterion_id, `
        <div class="op-comment"><b>${esc(t('w4.operator'))}</b> ${esc(i.operator_comment)}</div>
        <textarea data-r="${esc(i.criterion_id)}" placeholder="${esc(t('w4.reply.ph'))}" ${editable?'':'readonly'}>${esc(S.reviews.get(i.criterion_id)||'')}</textarea>`)).join('')
      : `<div class="empty">${esc(t('w4.emptyReviewer'))}</div>`;
    box.querySelectorAll('textarea[data-r]').forEach(el=>el.oninput=()=>S.reviews.set(el.dataset.r, el.value));
    $('saveReview').disabled = $('confirmScore').disabled = $('reviseScore').disabled = !editable;
    $('decideNote').textContent = a && a.status!=='submitted' && a.status!=='draft' ? t('appeal.'+a.status) : items.length ? '' : t('w2.noAppeal');
    return;
  }

  const locked = appealLocked();
  if(!e || e.status!=='ok' || !S.disputes.size){
    box.innerHTML = `<div class="empty">${esc(t('w4.empty'))}</div>`;
  }else{
    const order = e.criteria.map(c=>c.criterion_id);
    const ids = [...S.disputes.keys()].sort((x,y)=>order.indexOf(x)-order.indexOf(y));
    box.innerHTML = ids.map(id=>card(id,
      `<textarea data-t="${esc(id)}" placeholder="${esc(t('w4.why.ph'))}" ${locked?'readonly':''}>${esc(S.disputes.get(id))}</textarea>`
      + (locked && S.reviews.get(id) ? `<div class="op-comment"><b>${esc(t('w3.reviewerReply'))}</b> ${esc(S.reviews.get(id))}</div>` : ''))).join('');
    box.querySelectorAll('textarea[data-t]').forEach(el=>el.oninput=()=>S.disputes.set(el.dataset.t, el.value));
  }
  $('saveAppeal').disabled = $('send').disabled = locked || !e || e.status!=='ok' || (!S.disputes.size && !a);
}

const items = () => [...S.disputes].map(([criterion_id, operator_comment])=>({criterion_id, operator_comment}));
const reviewItems = () => [...S.reviews].map(([criterion_id, reviewer_comment])=>({criterion_id, reviewer_comment}));

async function saveDraft(){
  S.appeal = await saveAppealDraft(S.current, S.evaluation.id, items());
  return S.appeal;
}

export async function onSaveAppeal(){
  try{ await saveDraft(); note(t('w5.saved')); renderAppeals(); }
  catch(err){ note(err.message, true); }
}

export async function onSendAppeal(){
  const empty = [...S.disputes].filter(([,v])=>!v.trim()).map(([k])=>'3.'+itemNo(k));
  if(empty.length){ note(t('w5.fill', {list: empty.join(', ')}), true); return; }
  try{
    const draft = await saveDraft();
    S.appeal = await submitAppeal(draft.id);
    unsaved.delete(S.evaluation.id);
    markListAppeal(S.appeal.status);
    note(t('w5.sent')); renderResults(); renderAppeals();
  }catch(err){ note(err.message, true); }
}

export async function onSaveReview(){
  try{ S.appeal = await saveReview(currentAppeal().id, reviewItems()); note(t('w5.reviewSaved')); renderAppeals(); }
  catch(err){ note(err.message, true); }
}

/* Reviewer, Window 2, button 1: the appeal isn't upheld — the score stands; show it */
export async function onConfirm(){
  try{
    S.appeal = await confirmAppeal(currentAppeal().id, reviewItems());
    markListAppeal(S.appeal.status);
    $('decideNote').textContent = t('w2.confirmed');
    renderResults(); renderAppeals(); showScore();
  }catch(err){ $('decideNote').textContent = err.message; }
}

/* Reviewer, Window 2, button 2: the AI re-evaluates the items the reviewer replied to */
export async function onRevise(onRevised){
  if(![...S.reviews.values()].some(v=>v.trim())){ $('decideNote').textContent = t('w2.needComment'); return; }
  const id = S.current, appealId = currentAppeal().id;
  $('reviseScore').disabled = $('confirmScore').disabled = true;
  $('decideNote').textContent = t('w2.revising'); setStatus(t('w2.revising'));
  try{
    const revised = await reviseAppeal(appealId, reviewItems());
    S.appeal = {...S.appeal, status:'revised', revised_evaluation_id: revised.id,
      items: S.appeal.items.map(i=>({...i, reviewer_comment: S.reviews.get(i.criterion_id) ?? i.reviewer_comment}))};
    markListAppeal('revised');
    if(S.current===id) onRevised(revised);
    $('decideNote').textContent = t('w2.revised', {score: fmtScore(revised.final_score)});
    setStatus(t('w2.revised', {score: fmtScore(revised.final_score)}));
  }catch(err){
    $('decideNote').textContent = err.message; setStatus(err.message, true);
    renderAppeals();
  }
}

function markListAppeal(status){
  const r = S.list.find(x=>x.conversation_id===S.current);
  if(r) r.appeal_status = status;
}
