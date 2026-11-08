export const $ = id => document.getElementById(id);
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const fmt = t => {
  t = Math.max(0, Math.floor(t));
  const h = Math.floor(t/3600), m = String(Math.floor(t/60)%60).padStart(2,'0'), s = String(t%60).padStart(2,'0');
  return h ? `${h}:${m}:${s}` : `${m}:${s}`;
};
export const sleep = ms => new Promise(r=>setTimeout(r,ms));

/* Timestamp -> seconds. "mm:ss" / "hh:mm:ss" are offsets; ISO datetimes (voice calls) are absolute. */
export function toSec(v){
  if(typeof v==='number') return v;
  const s = String(v ?? '').trim();
  if(!s) return null;
  if(/^\d+(:\d+){1,2}(\.\d+)?$/.test(s)) return s.split(':').reduce((acc,p)=>acc*60+Number(p), 0);
  const ms = Date.parse(s);
  return Number.isNaN(ms) ? null : ms/1000;
}

/* Seconds from the start of the dialogue for each turn (null when unknown) */
export function relativeTimes(transcript){
  const secs = transcript.map(t=>toSec(t.timestamp));
  const start = secs.find(s=>s!=null);
  return secs.map(s => s==null || start==null ? null : Math.max(0, s-start));
}

export function downloadBlob(blob, filename){
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename; a.click();
  setTimeout(()=>URL.revokeObjectURL(a.href), 5000);
}

export function debounce(fn, ms){
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(()=>fn(...args), ms); };
}
