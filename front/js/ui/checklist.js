import { getChecklist, resetChecklist, saveChecklist } from '../api/backend.js';
import { t } from '../i18n.js';
import { S, setStatus } from '../state.js';
import { $, esc } from '../utils.js';
import { renderCriteriaPanel } from './criteriaPanel.js';

/* Editor for the checklist definitions (texts, scales, new criteria) and the general rules.
   Each save creates a new version on the backend; it applies to new evaluations only.
   Which criteria are listed/evaluated and their weights are also set in Settings / the "+" list. */

const KINDS = ['bool','scale','critical'];
let draft = null; // {criteria:[...], general_rules}

const parseLevels = s => [...new Set(String(s).split(/[\s,;]+/).filter(Boolean).map(Number))]
  .filter(Number.isInteger).sort((a,b)=>a-b);

function weightSummary(){
  const w = draft.criteria.filter(c=>c.kind!=='critical' && c.enabled!==false).reduce((s,c)=>s+(+c.weight||0),0);
  return t('ed.sum', {w}) + (w!==100 ? t('ed.sumNot100') : '');
}

function levelsHTML(c, i){
  if(c.kind!=='scale') return '';
  const levels = c.levels||[];
  return `<label>${esc(t('ed.levels'))}</label>
    <input data-i="${i}" data-f="levels" value="${esc(levels.join(', '))}">
    ${[...levels].reverse().map(lv=>`<div class="lv"><span>${lv}</span>
      <input data-i="${i}" data-lv="${lv}" placeholder="${esc(t('ed.levelPh', {lv}))}" value="${esc(c.level_descriptions?.[lv]||'')}"></div>`).join('')}`;
}

function cardHTML(c, i){
  const n = draft.criteria.length;
  return `<div class="ck-card">
    <div class="ck-head">
      <b>${i+1}.</b>
      <input class="ck-title" data-i="${i}" data-f="title" value="${esc(c.title)}" placeholder="${esc(t('ed.titlePh'))}">
      <button class="icon" data-move="${i}:-1" ${i?'':'disabled'} title="${esc(t('ed.up'))}">↑</button>
      <button class="icon" data-move="${i}:1" ${i<n-1?'':'disabled'} title="${esc(t('ed.down'))}">↓</button>
      <button class="icon" data-del="${i}" title="${esc(t('ed.del'))}">✕</button>
    </div>
    <div class="ck-row">
      <div><label>${esc(t('ed.code'))}</label><input data-i="${i}" data-f="id" value="${esc(c.id)}" placeholder="contact"></div>
      <div><label>${esc(t('ed.kind'))}</label><select data-i="${i}" data-f="kind">${KINDS.map(k=>
        `<option value="${k}" ${c.kind===k?'selected':''}>${esc(t('ed.kind.'+k))}</option>`).join('')}</select></div>
      ${c.kind==='critical' ? '' : `
      <div><label>${esc(t('ed.weight'))}</label><input type="number" min="0" max="50" step="1" data-i="${i}" data-f="weight" value="${esc(c.weight)}"></div>
      <div class="ck-check">
        <label><input type="checkbox" data-i="${i}" data-f="nullable" ${c.nullable?'checked':''}> ${esc(t('ed.nullable'))}</label>
        ${c.kind==='bool' ? `<label><input type="checkbox" data-i="${i}" data-f="negative" ${c.negative?'checked':''}> ${esc(t('ed.negative'))}</label>` : ''}
      </div>`}
    </div>
    <label>${esc(t('ed.desc'))}</label>
    <textarea data-i="${i}" data-f="description">${esc(c.description||'')}</textarea>
    ${levelsHTML(c, i)}
  </div>`;
}

function render(){
  const box = $('ckList');
  box.innerHTML = draft.criteria.map(cardHTML).join('');
  $('ckRules').value = draft.general_rules;
  $('ckSum').textContent = weightSummary();
  $('ckErr').textContent = '';

  box.querySelectorAll('[data-f]').forEach(el=>{
    const c = draft.criteria[+el.dataset.i], f = el.dataset.f;
    const update = () => {
      if(f==='nullable' || f==='negative') c[f] = el.checked;
      else if(f==='levels') c.levels = parseLevels(el.value);
      else c[f] = el.value;
      $('ckSum').textContent = weightSummary();
    };
    el.oninput = update;
    if(f==='kind' || f==='levels') el.onchange = () => { update(); render(); }; // re-draw scale fields
  });
  box.querySelectorAll('[data-lv]').forEach(el=>el.oninput=()=>{
    const c = draft.criteria[+el.dataset.i];
    c.level_descriptions = {...(c.level_descriptions||{}), [el.dataset.lv]: el.value};
  });
  box.querySelectorAll('[data-del]').forEach(b=>b.onclick=()=>{
    const i = +b.dataset.del;
    if(confirm(t('ed.confirmDel', {t: draft.criteria[i].title||draft.criteria[i].id}))){ draft.criteria.splice(i,1); render(); }
  });
  box.querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>{
    const [i,d] = b.dataset.move.split(':').map(Number);
    [draft.criteria[i], draft.criteria[i+d]] = [draft.criteria[i+d], draft.criteria[i]]; render();
  });
}

function load(checklist){
  draft = {criteria: structuredClone(checklist.criteria), general_rules: checklist.general_rules||''};
  $('ckVersion').textContent = t('ed.version', {v: checklist.id}) + ' · ' + t(checklist.is_default ? 'ed.default' : 'ed.changed');
  render();
}

function applySaved(checklist){
  S.checklist = checklist;
  renderCriteriaPanel();
  load(checklist);
}

export async function openChecklistEditor(){
  try{ load(await getChecklist()); $('ckDlg').showModal(); }
  catch(err){ setStatus(err.message, true); }
}

async function onSave(){
  draft.general_rules = $('ckRules').value;
  try{
    const saved = await saveChecklist(draft);
    applySaved(saved); $('ckDlg').close();
    setStatus(t('ed.saved', {v: saved.id}));
  }catch(err){ $('ckErr').textContent = err.message; }
}

async function onReset(){
  if(!confirm(t('ed.confirmReset'))) return;
  try{ applySaved(await resetChecklist()); setStatus(t('ed.resetDone')); }
  catch(err){ $('ckErr').textContent = err.message; }
}

export function initChecklistEditor(){
  $('criteria').onclick = openChecklistEditor;
  $('ckAdd').onclick = () => {
    // a new criterion is listed in Window 1 but not evaluated until "+" is pressed
    draft.criteria.push({id:'', title:'', kind:'bool', nullable:false, negative:false, weight:10, description:'',
      visible:true, enabled:false, comment:''});
    render(); $('ckList').lastElementChild?.scrollIntoView({behavior:'smooth'});
  };
  $('ckSave').onclick = onSave;
  $('ckReset').onclick = onReset;
  $('ckCancel').onclick = () => $('ckDlg').close();
}
