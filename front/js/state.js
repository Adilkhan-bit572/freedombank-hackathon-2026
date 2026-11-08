import { $ } from './utils.js';

export const S = {
  list: [],            // ConversationSummary[] from GET /conversations
  current: null,       // conversation_id shown on screen
  convo: null,         // the current conversation (with transcript, audio_url, language)
  utterances: [],      // transcript of the current conversation, as rendered
  hasTime: false,
  evaluation: null,    // latest EvaluationRead of the current conversation (or null)
  appeal: null,        // latest AppealRead of the current conversation (or null)
  disputes: new Map(), // operator's unsaved appeal: criterion_id -> comment
  reviews: new Map(),  // reviewer's unsaved replies: criterion_id -> comment
  selected: null,      // criterion_id selected in Window 3 (shown in Window 6)
  checklist: null,     // active checklist (GET /checklist)
  reviewer: false,     // reviewer mode
  filter: 'all',       // record filter: all | evaluated | pending | error | appeal (see FILTERS in ui/records.js)
  batch: false,
  batchStopping: false, // stop was clicked; the loop is still finishing its current request
};

export const setStatus = (text, err) => {
  $('status').textContent = text;
  $('status').style.color = err ? 'var(--bad)' : 'var(--muted)';
};
