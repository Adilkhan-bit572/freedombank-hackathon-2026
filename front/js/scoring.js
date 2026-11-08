import { t } from './i18n.js';

/* Text and colour of one criterion's verdict. Type and max come from the backend with the result. */
export function verdict(c){
  if(c.value==null) return [t('verdict.na'),'na'];
  if(c.kind==='scale'){ const p=c.value/c.max; return [t('verdict.of', {v:c.value, max:c.max}), p>=.7?'good':p>=.4?'na':'bad']; }
  if(c.kind==='critical') return c.value===true ? [t('verdict.critYes'),'bad'] : [t('verdict.critNo'),'good'];
  if(c.negative) return c.value===true ? [t('verdict.negYes'),'bad'] : [t('verdict.negNo'),'good'];
  return c.value===true ? [t('verdict.yes'),'good'] : [t('verdict.no'),'bad'];
}

/* A gross violation that must be shown in red: the critical criterion, or a "negative" one, found */
export const isViolation = c => c.value===true && (c.kind==='critical' || c.negative);

export const fmtScore = s => s==null ? '—' : Number(s).toFixed(2).replace(/\.?0+$/,'');
