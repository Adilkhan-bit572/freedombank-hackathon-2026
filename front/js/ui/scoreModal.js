/* Window 2 → the final score in the middle of the screen, with the gross-error mark next to it */
import { t } from '../i18n.js';
import { fmtScore } from '../scoring.js';
import { S } from '../state.js';
import { $ } from '../utils.js';

export function showScore(){
  const e = S.evaluation; if(!e) return;
  $('scoreNum').textContent = fmtScore(e.final_score);
  $('modal').classList.toggle('crit-fail', !!e.critical_flag);
  const na = e.criteria.filter(c=>c.kind!=='critical' && c.value==null).length;
  $('scoreSub').textContent = e.status!=='ok' ? t('modal.error', {e: e.error||''})
    : (e.parent_evaluation_id ? t('modal.revised')+' ' : '')
      + (e.final_score==null ? t('modal.noScore') : na ? t('modal.na', {n:na}) : t('modal.all'));
  $('scoreCrit').hidden = !e.critical_flag;
  $('modal').classList.add('open');
}

export const closeModal = () => $('modal').classList.remove('open');
