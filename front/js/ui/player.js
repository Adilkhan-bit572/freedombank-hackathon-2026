/* Audio player in Window 1 for voice calls: plays the record's audio_url, or a file the user
   attached (kept for this browser session). playSegment(i) plays turn i up to the next turn. */
import { S } from '../state.js';
import { $ } from '../utils.js';

const attached = new Map(); // conversation_id -> object URL of an attached file
let stopAt = null;          // seconds at which the current segment ends
let failedSrc = null;

const audio = () => $('audio');
export const hasAudio = () => !$('player').hidden && !!audio().src && audio().src !== failedSrc;

/* Show the player for the current record (only when it has audio or timestamps worth listening to) */
export function setupPlayer(){
  const c = S.convo, el = audio();
  const src = (c && attached.get(c.conversation_id)) || c?.audio_url || '';
  const voice = !!c && (!!src || /voice|call|звон/i.test(c.channel||''));
  $('player').hidden = !voice;
  $('audioErr').hidden = true;
  failedSrc = null;
  stopAt = null;
  if(el.getAttribute('src') !== src){ el.pause(); if(src) el.src = src; else el.removeAttribute('src'); }
}

export function playSegment(i){
  const u = S.utterances[i], el = audio();
  if(!u || u.start==null || !hasAudio()) return false;
  // dialogue offsets map onto the recording; a recording that starts later than the transcript can't be known here
  el.currentTime = u.start;
  stopAt = u.end != null && u.end > u.start ? u.end : null;
  el.play().catch(()=>{});
  document.querySelectorAll('.msg.hl').forEach(e=>e.classList.remove('hl'));
  const m = $('u'+i); if(m){ m.classList.add('hl'); m.scrollIntoView({behavior:'smooth',block:'center'}); }
  return true;
}

export function initPlayer(){
  const el = audio();
  el.addEventListener('timeupdate', ()=>{ if(stopAt!=null && el.currentTime >= stopAt){ el.pause(); stopAt = null; } });
  el.addEventListener('seeking', ()=>{ if(stopAt!=null && Math.abs(el.currentTime - stopAt) > 0.5 && el.paused) stopAt = null; });
  el.addEventListener('error', ()=>{ if(el.src){ failedSrc = el.src; $('audioErr').hidden = false; } });
  $('attachAudio').onclick = () => $('audioFile').click();
  $('audioFile').onchange = e => {
    const f = e.target.files[0]; e.target.value = '';
    if(!f || !S.current) return;
    if(attached.has(S.current)) URL.revokeObjectURL(attached.get(S.current));
    attached.set(S.current, URL.createObjectURL(f));
    setupPlayer();
  };
}
