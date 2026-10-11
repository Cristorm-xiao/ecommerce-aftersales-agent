import test from 'node:test';
import assert from 'node:assert/strict';
import { loadSession, newSession, saveSession, SESSION_KEY } from '../web/session.mjs';

function store() {
  const data = new Map();
  return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) };
}

test('first visit gets a fresh namespaced ID; reload preserves the session', () => {
  const storage = store();
  const first = loadSession(storage);
  assert.match(first.threadId, /^web-aftersales-v1-[0-9a-f-]{36}$/);
  assert.notEqual(first.threadId, '1');
  first.messages.push({ role: 'user', text: 'DEMO1001' });
  saveSession(storage, first);
  assert.deepEqual(loadSession(storage), first);
});

test('new conversation isolates earlier history', () => {
  const storage = store();
  const first = loadSession(storage);
  first.messages.push({ role: 'user', text: 'earlier question' });
  saveSession(storage, first);
  const next = newSession(storage);
  assert.notEqual(first.threadId, next.threadId);
  assert.deepEqual(next.messages, []);
  assert.deepEqual(loadSession(storage), next);
});

test('legacy IDs and corrupted storage never reuse old history', () => {
  const storage = store();
  storage.setItem(SESSION_KEY, JSON.stringify({ threadId: '1', messages: [{ role: 'user', text: 'old' }] }));
  assert.deepEqual(loadSession(storage).messages, []);
  storage.setItem(SESSION_KEY, 'invalid-json');
  assert.notEqual(loadSession(storage).threadId, '1');
});

test('blocked browser storage still allows an in-memory session', () => {
  const storage = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); } };
  const session = loadSession(storage);
  assert.ok(session.threadId);
  assert.doesNotThrow(() => saveSession(storage, session));
});

test('refresh during a pending reply marks it interrupted instead of silently losing it', () => {
  const storage = store();
  const session = loadSession(storage);
  session.messages.push({ role: 'user', text: 'DEMO1001', pending: true });
  saveSession(storage, session);
  const restored = loadSession(storage);
  assert.equal(restored.threadId, session.threadId);
  assert.equal(restored.messages[0].pending, undefined);
  assert.equal(restored.messages[0].failed, true);
  assert.equal(restored.messages[0].interrupted, true);
});
