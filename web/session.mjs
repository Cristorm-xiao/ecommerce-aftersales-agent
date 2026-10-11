export const SESSION_KEY = 'xingyun-aftersales-web-v1';
const PREFIX = 'web-aftersales-v1-';
const ID_PATTERN = /^web-aftersales-v1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function saveSession(storage, session) {
  try { storage?.setItem(SESSION_KEY, JSON.stringify(session)); } catch { /* Storage may be disabled or full. */ }
}

export function newSession(storage) {
  const session = { version: 1, threadId: PREFIX + crypto.randomUUID(), messages: [] };
  saveSession(storage, session);
  return session;
}

export function loadSession(storage) {
  try {
    const saved = JSON.parse(storage?.getItem(SESSION_KEY) ?? 'null');
    if (saved?.version === 1 && ID_PATTERN.test(saved.threadId) && Array.isArray(saved.messages)
        && saved.messages.every(m => ['user', 'assistant'].includes(m.role) && typeof m.text === 'string')) {
      for (const message of saved.messages) {
        if (message.pending) {
          delete message.pending;
          message.failed = true;
          message.interrupted = true;
        }
      }
      saveSession(storage, saved);
      return saved;
    }
  } catch { /* Corrupt or legacy history starts a clean session. */ }
  return newSession(storage);
}
