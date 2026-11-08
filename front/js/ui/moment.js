/* Window 6: where in the dialogue the selected item happened — the mistake, the turn after which
   a missing action should have been, or a good example — with timecode, speaker and the text.
   Voice calls: ▶ plays that segment in the player; chats: jump to the turn in Window 1. */
import { criterionTitle, t } from '../i18n.js';
import { S } from '../state.js';
import { $, esc, fmt } from '../utils.js';
import { hasAudio, playSegment } from './player.js';
import { seekTo } from './transcript.js';

const LABEL = {error:'w6.error', missing:'w6.missing', good:'w6.good'};

export function renderMoment(){
  const box = $('moment');
  const c = S.evaluation?.status==='ok' ? S.evaluation.criteria.find(x=>x.criterion_id===S.selected) : null;
  if(!c){ box.innerHTML = `<div class="empty">${esc(t('w6.empty'))}</div>`; return; }
  const n = S.evaluation.criteria.indexOf(c) + 1;
  const turns = (c.evidence_turns||[]).filter(k=>S.utterances[k-1]);
  const label = t(LABEL[c.evidence_kind] || 'w6.ref');
  const kind = c.evidence_kind==='good' ? 'good' : ['error','missing'].includes(c.evidence_kind) ? 'bad' : '';
  const audio = hasAudio();

  box.innerHTML = `<div class="m-head"><span class="num">3.${n}</span> ${esc(criterionTitle(c))}</div>
    <div class="m-kind ${kind}">${esc(label)}</div>`
    + (turns.length ? turns.map(k=>{
      const u = S.utterances[k-1];
      return `<div class="m-turn ${u.role}">
        <div class="who">#${k} · ${esc(t('role.'+u.role))}${S.hasTime && u.start!=null ? ' · <b>'+fmt(u.start)+(u.end!=null?'–'+fmt(u.end):'')+'</b>' : ''}</div>
        <q>${esc(u.text)}</q>
        <div class="m-actions">
          ${audio && u.start!=null ? `<button class="link" data-play="${k-1}">${esc(t('w6.play'))}</button>` : ''}
          <button class="link" data-goto="${k-1}">${esc(t('w6.goto'))}</button>
        </div>
      </div>`;
    }).join('') : `<div class="empty">${esc(t('w6.none'))}</div>`);

  box.querySelectorAll('[data-play]').forEach(b=>b.onclick=()=>playSegment(+b.dataset.play));
  box.querySelectorAll('[data-goto]').forEach(b=>b.onclick=()=>seekTo(+b.dataset.goto));
}
