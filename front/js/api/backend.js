import { CONFIG } from '../config.js';
import { t } from '../i18n.js';

const url = path => CONFIG.apiBaseUrl.replace(/\/$/, '') + path;
const enc = encodeURIComponent;

async function request(path, options = {}){
  let r;
  try{ r = await fetch(url(path), options); }
  catch(e){ throw new Error(t('net.down', {url: CONFIG.apiBaseUrl})); }
  const body = (r.headers.get('content-type')||'').includes('json') ? await r.json() : await r.text();
  if(!r.ok){
    let detail = typeof body === 'object' ? body.detail : body;
    if(Array.isArray(detail)) // FastAPI validation errors: [{loc:[...], msg}]
      detail = t('net.badData') + detail.slice(0,3).map(d=>`${(d.loc||[]).slice(1).join('.')} — ${d.msg}`).join('; ');
    const err = new Error(typeof detail === 'string' && detail ? detail : t('net.status', {s: r.status}));
    err.status = r.status;
    throw err;
  }
  return body;
}

const send = (method, path, data) =>
  request(path, {method, headers:{'content-type':'application/json'}, body: data === undefined ? undefined : JSON.stringify(data)});
const postJson = (path, data) => send('POST', path, data);
const putJson = (path, data) => send('PUT', path, data);
const orNull = p => p.catch(e => { if(e.status === 404) return null; throw e; });

export const listConversations = () => request('/conversations');
export const getConversation = id => request(`/conversations/${enc(id)}`);
export const uploadConversations = json => postJson('/conversations', json);
export const evaluateConversation = id => postJson(`/conversations/${enc(id)}/evaluate`);
export const getEvaluation = id => orNull(request(`/conversations/${enc(id)}/evaluation`));

export const csvExportUrl = () => url('/evaluations/export.csv');
/* results.json is fetched (not just opened) so the UI can read the validation headers */
export async function fetchResults(){
  let r;
  try{ r = await fetch(url('/evaluations/results.json')); }
  catch(e){ throw new Error(t('net.down', {url: CONFIG.apiBaseUrl})); }
  if(!r.ok) throw new Error(t('net.status', {s: r.status}));
  return {blob: await r.blob(), problems: +(r.headers.get('X-Validation-Problems')||0), nonStandard: +(r.headers.get('X-Non-Standard')||0)};
}

export const getChecklist = () => request('/checklist');
export const saveChecklist = checklist => putJson('/checklist', checklist);
export const resetChecklist = () => postJson('/checklist/reset');

/* Appeals: items = [{criterion_id, operator_comment, reviewer_comment}] */
export const getAppeal = id => orNull(request(`/conversations/${enc(id)}/appeal`));
export const saveAppealDraft = (id, evaluationId, items) => putJson(`/conversations/${enc(id)}/appeal`, {evaluation_id: evaluationId, items});
export const submitAppeal = appealId => postJson(`/appeals/${appealId}/submit`);
export const saveReview = (appealId, items) => putJson(`/appeals/${appealId}/review`, {items});
export const confirmAppeal = (appealId, items) => postJson(`/appeals/${appealId}/confirm`, {items});
export const reviseAppeal = (appealId, items) => postJson(`/appeals/${appealId}/revise`, {items});
