/* Window 3: the total out of 100 and items 3.1…3.N, each with its verdict and the AI's short
   rationale. Gross violations are red. Operator mode: «Оспорить» under each item. Reviewer
   mode: appealed items are red with the operator's comment beneath. Clicking an item shows
   its moment in Window 6. */
import { criterionTitle, t } from '../i18n.js';
import { fmtScore, isViolation, verdict } from '../scoring.js';
import { S } from '../state.js';
import { $, esc } from '../utils.js';
import { appealLocked, currentAppeal, toggleDispute } from './appeals.js';
import { renderMoment } from './moment.js';

const appealItem = id => {
  const a = currentAppeal();
  return a && a.status!=='draft' ? a.items.find(i=>i.criterion_id===id) : null;
};

/* Default selection for Window 6: the first item that points at a mistake or a missing action */
function defaultSelection(e){
  const pick = e.criteria.find(c=>['error','missing'].includes(c.evidence_kind) && c.evidence_turns?.length)
    || e.criteria.find(c=>c.evidence_turns?.length);
  return pick?.criterion_id ?? null;
}

function renderTotal(e){
  const box = $('w3total');
  if(!e || e.status!=='ok'){ box.innerHTML = ''; return; }
  const na = e.criteria.filter(c=>c.kind!=='critical' && c.value==null).length;
  box.innerHTML = `<span class="total">${esc(t('w3.total'))}: <b>${esc(fmtScore(e.final_score))}</b>/100</span>`
    + (e.critical_flag ? ` <span class="crit-badge">${esc(t('w3.critical'))}</span>` : '')
    + (e.final_score==null ? ` <span class="muted">${esc(t('w3.noScore'))}</span>` : na ? ` <span class="muted">${esc(t('w3.na', {n:na}))}</span>` : '');
}

export function renderResults(){
  const e = S.evaluation;
  renderTotal(e);
  if(!e){ renderMoment(); return; }
  const meta = `<div class="meta">${esc(t('w3.meta'))}: ${esc(new Date(e.created_at).toLocaleString())} · ${esc(e.provider)} / ${esc(e.model)}`
    + (e.checklist_id!=null ? ' · '+esc(t('w3.checklist', {v:e.checklist_id})) : '')
    + (e.parent_evaluation_id ? ' · '+esc(t('w3.revisedMeta')) : '') + '</div>';
  if(e.status!=='ok'){
    $('results').innerHTML = `<div class="err-box"><b>${esc(t('w3.error'))}</b><br>${esc(e.error||'')}<br>${esc(t('w3.errorHint'))}</div>` + meta;
    S.selected = null; renderMoment();
    return;
  }
  if(!e.criteria.some(c=>c.criterion_id===S.selected)) S.selected = defaultSelection(e);

  $('results').innerHTML = e.criteria.map((c,i)=>{
    const [txt,cls] = verdict(c);
    const ap = appealItem(c.criterion_id);
    const classes = ['crit', isViolation(c)?'violation':'', S.reviewer && ap?'appealed':'', S.selected===c.criterion_id?'selected':''].join(' ');
    return `<div class="${classes}" data-sel="${esc(c.criterion_id)}" tabindex="0">
      <div class="head"><span class="num">3.${i+1}</span><span class="title">${esc(criterionTitle(c))}</span>
        ${c.revised ? `<span class="tag">${esc(t('w3.revisedItem'))}</span>` : ''}<span class="badge ${cls}">${esc(txt)}</span></div>
      <div class="reason">${esc(c.rationale||'')}</div>
      ${S.reviewer && ap ? `<div class="appeal-note"><b>${esc(t('w3.appealed'))}</b> ${esc(ap.operator_comment)}`
          + (ap.reviewer_comment ? `<br><b>${esc(t('w3.reviewerReply'))}</b> ${esc(ap.reviewer_comment)}` : '') + '</div>' : ''}
      ${S.reviewer ? '' : `<button class="dispute" data-d="${esc(c.criterion_id)}" ${appealLocked()?'disabled':''}>${esc(S.disputes.has(c.criterion_id) ? t('w3.undispute') : t('w3.dispute'))}</button>`}
    </div>`;
  }).join('') + meta;

  $('results').querySelectorAll('[data-sel]').forEach(el=>{
    const select = () => { S.selected = el.dataset.sel; renderResults(); };
    el.onclick = ev => { if(!ev.target.closest('.dispute')) select(); };
    el.onkeydown = ev => { if(ev.key==='Enter' && ev.target===el) select(); };
  });
  $('results').querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>toggleDispute(b.dataset.d));
  renderMoment();
}
