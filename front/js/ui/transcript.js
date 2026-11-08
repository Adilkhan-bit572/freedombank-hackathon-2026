import { t } from '../i18n.js';
import { S } from '../state.js';
import { $, esc, fmt, relativeTimes } from '../utils.js';
import { hasAudio, playSegment } from './player.js';

/* Must match speaker_role() in the backend (evaluation/prompts.py) */
export function speakerRole(sp){
  sp = String(sp||'').toLowerCase();
  if(sp==='system') return 'system';
  if(/client|customer|user|caller|клиент|абонент|звонящ/.test(sp)) return 'caller';
  if(/^(bot|assistant|ai|aim|virtual)|бот|ассистент/.test(sp)) return 'bot';
  return 'operator';
}

/* No filtering: indexes must match the backend's, so evidence_turns point to the right line.
   `start`/`end` are seconds from the start of the dialogue (end = next turn's start). */
export function toUtterances(transcript){
  const times = relativeTimes(transcript);
  return transcript.map((tr,i)=>({
    role: speakerRole(tr.speaker),
    start: times[i],
    end: times.slice(i+1).find(x=>x!=null) ?? null,
    text: String(tr.text||''),
  }));
}

export function renderTranscript(){
  const box = $('transcript');
  if(!S.utterances.length){ box.innerHTML = `<div class="empty">${esc(t('transcript.empty'))}</div>`; return; }
  box.innerHTML = S.utterances.map((u,i)=>`
    <div class="msg ${u.role}" id="u${i}" data-turn="${i}">
      <div class="who">#${i+1} · ${esc(t('role.'+u.role))}${S.hasTime && u.start!=null ? ' · '+fmt(u.start) : ''}</div>
      ${esc(u.text)}
    </div>`).join('');
  // with audio, clicking a turn plays it
  box.querySelectorAll('.msg').forEach(el=>el.onclick=()=>{ if(hasAudio()) playSegment(+el.dataset.turn); });
}

/* Highlight a turn and scroll to it */
export function seekTo(i){
  if(!S.utterances[i]) return;
  document.querySelectorAll('.msg.hl').forEach(e=>e.classList.remove('hl'));
  const el = $('u'+i);
  if(el){ el.classList.add('hl'); el.scrollIntoView({behavior:'smooth',block:'center'}); }
}
