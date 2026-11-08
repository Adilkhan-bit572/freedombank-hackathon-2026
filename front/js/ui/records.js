import { getAppeal, getConversation, getEvaluation, listConversations } from '../api/backend.js';
import { t } from '../i18n.js';
import { fmtScore } from '../scoring.js';
import { S, setStatus } from '../state.js';
import { $, esc } from '../utils.js';
import { renderAppeals, resetAppealState } from './appeals.js';
import { setupPlayer } from './player.js';
import { renderResults } from './results.js';
import { renderTranscript, toUtterances } from './transcript.js';

function recLabel(r,i){
  const sc = !r.evaluated ? '' : r.status!=='ok' ? ' · '+t('rec.error')
    : (r.final_score==null ? ' · —' : ' · '+fmtScore(r.final_score)+'/100') + (r.critical_flag ? ' · '+t('rec.critical') : '');
  const ap = r.appeal_status==='submitted' ? ' · '+t('rec.appeal') : '';
  return `${i+1}. ${r.conversation_id}${r.channel?' · '+r.channel:''} · ${r.transcript_length} ${t('rec.turns')}${sc}${ap}`;
}

/* Record filter: which records the selector shows */
export const FILTERS = {
  all:       r => true,
  evaluated: r => r.evaluated && r.status==='ok',
  pending:   r => !r.evaluated,
  error:     r => r.evaluated && r.status!=='ok',
  appeal:    r => r.appeal_status==='submitted', // sent and waiting for the reviewer
};
export const matchesFilter = r => FILTERS[S.filter](r);

function refreshFilter(){
  const f = $('filter');
  f.innerHTML = Object.entries(FILTERS).map(([k,match])=>
    `<option value="${k}">${esc(t('filter.'+k))} (${S.list.filter(match).length})</option>`).join('');
  f.value = S.filter;
}

export function refreshOptions(){
  refreshFilter();
  const sel = $('rec');
  // numbering stays the position in the full list; the open record is always listed
  const rows = S.list.map((r,i)=>[r,i]).filter(([r])=>matchesFilter(r) || r.conversation_id===S.current);
  sel.innerHTML = rows.length
    ? rows.map(([r,i])=>`<option value="${esc(r.conversation_id)}">${esc(recLabel(r,i))}${matchesFilter(r)?'':' '+esc(t('rec.offFilter'))}</option>`).join('')
    : `<option value="">${esc(t(S.list.length ? 'rec.noneFilter' : 'rec.none'))}</option>`;
  sel.value = S.current ?? '';
  const todo = S.list.filter(needsEvaluation).length;
  $('all').textContent = S.batch ? t('bar.stop') : S.batchStopping ? t('bar.stopping') : t('bar.all', {n: todo});
  $('all').disabled = S.batchStopping || (!S.batch && !todo);
  $('csv').disabled = $('results-json').disabled = !S.list.some(r=>r.evaluated);
}

/* Not evaluated yet, or the last attempt failed */
export const needsEvaluation = r => !r.evaluated || r.status!=='ok';

/* Reload the conversation list from the backend; keep the current selection if it still exists */
export async function reloadList(){
  S.list = await listConversations();
  if(!S.list.some(r=>r.conversation_id===S.current)) S.current = null;
  refreshOptions();
  if(S.current==null && S.list.length) await loadRecord((S.list.find(matchesFilter) ?? S.list[0]).conversation_id);
}

/* Update one row of the list after an evaluation, without refetching everything */
export function markEvaluated(evaluation){
  const r = S.list.find(x=>x.conversation_id===evaluation.conversation_id);
  if(r){
    r.evaluated = true; r.status = evaluation.status;
    r.final_score = evaluation.final_score; r.critical_flag = evaluation.critical_flag;
  }
  refreshOptions();
}

/* Show an evaluation (or "not evaluated yet") in Windows 3/4/6 and enable Window 2 */
export function showEvaluation(evaluation){
  S.evaluation = evaluation;
  resetAppealState();
  if(evaluation) renderResults();
  else{
    $('results').innerHTML = `<div class="empty">${esc(t('w3.notEvaluated'))}</div>`;
    S.selected = null; renderResults();
  }
  renderAppeals();
  $('showScore').disabled = !evaluation;
  if(evaluation?.status==='ok') $('cpanel').open = false; // keep the criteria list out of the way once evaluated
}

export async function loadRecord(id){
  S.current = id;
  $('start').disabled = true; $('sendNote').textContent = ''; $('decideNote').textContent = '';
  refreshOptions();
  try{
    const [convo, evaluation, appeal] = await Promise.all([getConversation(id), getEvaluation(id), getAppeal(id)]);
    if(S.current!==id) return; // another record was selected meanwhile
    S.convo = convo; S.appeal = appeal; S.selected = null;
    $('fname').textContent = `${convo.conversation_id} · ${convo.channel} · ${convo.language}`;
    S.utterances = toUtterances(convo.transcript);
    S.hasTime = S.utterances.some(u=>u.start!=null);
    setupPlayer();
    renderTranscript();
    showEvaluation(evaluation);
  }catch(err){ setStatus(err.message, true); }
  $('start').disabled = S.batch;
}
