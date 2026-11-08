export const CONFIG = {
  // адрес бэкенда (FastAPI); апелляции тоже хранятся там. Для отладки можно указать ?api=http://host:port
  apiBaseUrl: new URLSearchParams(location.search).get('api') || 'http://localhost:8000',
};

/* Пакетная оценка: пауза между запросами к бэкенду, чтобы не упираться в лимиты облачной LLM */
export const BATCH_PAUSE_MS = 3000;
export const RATE_LIMIT_RETRIES = 2;     // повторы при ответе 429 (лимит LLM)
export const RATE_LIMIT_WAIT_MS = 40000;
