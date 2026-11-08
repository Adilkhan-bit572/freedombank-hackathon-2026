import { csvExportUrl, evaluateConversation, fetchResults, uploadConversations } from './api/backend.js';
import { BATCH_PAUSE_MS, RATE_LIMIT_RETRIES, RATE_LIMIT_WAIT_MS } from './config.js';
import { applyI18n, getLang, onLangChange, setLang, t } from './i18n.js';
import { S, setStatus } from './state.js';
import { onConfirm, onRevise, onSaveAppeal, onSaveReview, onSendAppeal, renderAppeals } from './ui/appeals.js';
import { initChecklistEditor } from './ui/checklist.js';
import { loadChecklist, renderCriteriaPanel } from './ui/criteriaPanel.js';
import { applyMode, initMode } from './ui/mode.js';
import { initPlayer } from './ui/player.js';
import { FILTERS, loadRecord, markEvaluated, matchesFilter, needsEvaluation, refreshOptions, reloadList, showEvaluation } from './ui/records.js';
import { renderResults } from './ui/results.js';
import { closeModal, showScore } from './ui/scoreModal.js';
import { initSettings } from './ui/settings.js';
import { renderTranscript } from './ui/transcript.js';
import { $, downloadBlob, sleep } from './utils.js';

/* ===================== ЗАГРУЗКА JSON → БД ===================== */
async function onFileChosen(e){
  const f = e.target.files[0]; if(!f) return;
  e.target.value = '';
  try{
    setStatus(t('status.uploading'));
    const res = await uploadConversations(JSON.parse(await f.text()));
    await reloadList();
    setStatus(t('status.uploaded', {f: f.name, c: res.created.length, s: res.skipped.length}));
  }catch(err){ setStatus(err instanceof SyntaxError ? t('status.badJson') : err.message, true); }
}

/* ===================== ОЦЕНКА (на бэкенде) ===================== */
async function startEvaluation(){
  const id = S.current; if(!id) return;
  $('start').disabled = true;
  setStatus(t('status.analyzing'));
  $('results').innerHTML = `<div class="empty">${t('w3.analyzing')}</div>`;
  try{
    const evaluation = await evaluateConversation(id);
    markEvaluated(evaluation);
    if(S.current===id) showEvaluation(evaluation);
    if(evaluation.status==='ok') setStatus(t('status.done'));
    else setStatus(t('status.failed', {e: evaluation.error||''}), true);
  }catch(err){
    if(S.current===id) showEvaluation(S.evaluation); // restore the previous result, if any
    setStatus(err.message, true);
  }
  $('start').disabled = false;
}

async function evaluateAll(){
  if(S.batch){ S.batch = false; S.batchStopping = true; refreshOptions(); return; }
  if(S.batchStopping) return; // the previous batch is still finishing its current request
  const todo = S.list.filter(needsEvaluation).map(r=>r.conversation_id);
  if(!todo.length){ setStatus(t('status.allDone')); return; }
  S.batch = true; refreshOptions(); $('start').disabled = true;
  let n = 0, errors = 0, failed = false;
  for(const id of todo){
    if(!S.batch) break;
    setStatus(t('status.batch', {n: ++n, t: todo.length, id}));
    try{
      const evaluation = await evaluateWithRateLimitRetry(id);
      markEvaluated(evaluation);
      if(evaluation.status!=='ok') errors++;
      if(S.current===id) showEvaluation(evaluation);
    }catch(err){ setStatus(t('status.stoppedAt', {id, e: err.message}), true); failed = true; break; }
    if(n<todo.length) await sleep(BATCH_PAUSE_MS);
  }
  const stopped = !S.batch;
  S.batch = false; S.batchStopping = false; refreshOptions(); $('start').disabled = false;
  if(!failed) setStatus(t(stopped && n<todo.length ? 'status.batchStopped' : 'status.batchDone')
    + (errors ? ' ' + t('status.batchErrors', {n: errors}) : ''), errors>0);
}

/* The backend answers 429 when the LLM is rate limited: wait and retry a couple of times */
async function evaluateWithRateLimitRetry(id){
  for(let a=0;;a++){
    try{ return await evaluateConversation(id); }
    catch(err){
      if(err.status!==429 || a>=RATE_LIMIT_RETRIES || !S.batch) throw err;
      setStatus(t('status.rateLimit', {s: RATE_LIMIT_WAIT_MS/1000, id}));
      await sleep(RATE_LIMIT_WAIT_MS);
    }
  }
}

/* results.json: download, and warn about records that can't be submitted as they are */
async function downloadResults(){
  try{
    const {blob, problems, nonStandard} = await fetchResults();
    downloadBlob(blob, 'results.json');
    if(nonStandard) setStatus(t('status.nonStandard', {n: nonStandard}), true);
    else if(problems) setStatus(t('status.validation', {n: problems}), true);
    else setStatus(t('status.downloaded'));
  }catch(err){ setStatus(err.message, true); }
}

/* ===================== ОБРАБОТЧИКИ ===================== */
$('pick').onclick = () => $('file').click();
$('file').onchange = onFileChosen;
$('rec').onchange = e => e.target.value && loadRecord(e.target.value);
$('filter').onchange = e => {
  S.filter = e.target.value;
  try{ localStorage.setItem('recFilter', S.filter); }catch{}
  const cur = S.list.find(r=>r.conversation_id===S.current);
  const first = S.list.find(matchesFilter);
  if(cur && !matchesFilter(cur) && first) loadRecord(first.conversation_id); // jump to the first matching record
  else refreshOptions();
};
$('start').onclick = startEvaluation;
$('all').onclick = evaluateAll;
$('csv').onclick = () => { window.location.href = csvExportUrl(); };
$('results-json').onclick = downloadResults;
$('saveAppeal').onclick = onSaveAppeal;
$('send').onclick = onSendAppeal;
$('saveReview').onclick = onSaveReview;
$('confirmScore').onclick = onConfirm;
$('reviseScore').onclick = () => onRevise(revised => { markEvaluated(revised); showEvaluation(revised); });
$('showScore').onclick = showScore;
$('closeModal').onclick = closeModal;
$('modal').onclick = e => { if(e.target.id==='modal') closeModal(); };
$('lang').value = getLang();
$('lang').onchange = e => setLang(e.target.value);
initChecklistEditor();
initSettings();
initPlayer();

/* Language switch: re-render everything that is built in JS */
onLangChange(() => {
  refreshOptions(); renderCriteriaPanel(); renderTranscript();
  if(S.evaluation) renderResults(); else showEvaluation(null);
  renderAppeals(); applyMode();
});

/* ===================== СТАРТ ===================== */
try{ const f = localStorage.getItem('recFilter'); if(f in FILTERS) S.filter = f; }catch{}
applyI18n();
initMode();
setStatus(t('status.loading'));
loadChecklist().catch(err => setStatus(err.message, true));
reloadList()
  .then(() => setStatus(S.list.length ? t('status.count', {n: S.list.length}) : t('status.empty')))
  .catch(err => setStatus(err.message, true));
