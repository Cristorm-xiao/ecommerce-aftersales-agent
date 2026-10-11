import { loadSession, newSession, saveSession } from './session.mjs';

const $ = id => document.getElementById(id);
let storage;
try { storage = window.sessionStorage; } catch { /* Private browser restrictions. */ }
let session = loadSession(storage);
let busy = false;
let image = null;
let readingImage = false;
let fileVersion = 0;
const allowedTypes = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif']);

function notice(text = '') { $('notice').textContent = text; $('notice').hidden = !text; }
function scrollBottom() { $('conversation').scrollTop = $('conversation').scrollHeight; }
function syncState() {
  $('welcome').hidden = session.messages.length > 0;
  $('message-count').textContent = String(session.messages.filter(m => m.role === 'user').length);
  $('send-button').disabled = busy || readingImage || (! $('query').value.trim() && !image);
  $('new-chat').disabled = busy || readingImage;
  $('upload-button').disabled = busy || readingImage;
  $('remove-image').disabled = busy;
  $('query').disabled = busy;
}
function renderMessage(message, imageURL) {
  const row = document.createElement('article');
  row.className = `message ${message.role}`;
  const avatar = document.createElement('span'); avatar.className = 'avatar'; avatar.textContent = '✳'; avatar.setAttribute('aria-hidden', 'true');
  const content = document.createElement('div'); content.className = 'message-content';
  const label = document.createElement('div'); label.className = 'message-label'; label.textContent = message.role === 'user' ? '你' : '星云售后';
  content.append(label);
  if (imageURL) {
    const preview = document.createElement('img'); preview.className = 'message-image'; preview.src = imageURL; preview.alt = '本轮发送的商品图片'; content.append(preview);
  } else if (message.imageName) {
    const label = document.createElement('div'); label.className = 'image-label'; label.textContent = `已发送图片：${message.imageName}`; content.append(label);
  }
  const text = document.createElement('div'); text.className = 'message-text'; text.textContent = message.text; content.append(text);
  if (message.failed) {
    const failed = document.createElement('div'); failed.className = 'failed-label'; failed.textContent = '未收到回复，请重试'; content.append(failed);
  }
  row.append(avatar, content); $('messages').append(row);
  return row;
}
function persist() { saveSession(storage, session); syncState(); }
function resizeInput() { $('query').style.height = 'auto'; $('query').style.height = Math.min($('query').scrollHeight, 140) + 'px'; }
function clearImage() {
  image = null; fileVersion += 1; $('image-input').value = ''; $('attachment').hidden = true; $('attachment-preview').removeAttribute('src'); syncState();
}

session.messages.forEach(m => renderMessage(m)); syncState(); scrollBottom();
if (session.messages.at(-1)?.interrupted) {
  $('query').value = session.messages.at(-1).text;
  notice('刷新后未收到上一条请求的结果，输入已恢复。可重试，或新建会话；有图片时请重新选择。');
  resizeInput(); syncState();
}

$('query').addEventListener('input', () => { resizeInput(); syncState(); });
$('query').addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault(); if (!busy && !readingImage) $('chat-form').requestSubmit();
  }
});
$('new-chat').addEventListener('click', () => {
  if (busy || readingImage) return;
  session = newSession(storage); $('messages').replaceChildren(); $('query').value = ''; clearImage(); notice(); resizeInput(); syncState(); $('query').focus();
});
document.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => {
  $('query').value = button.dataset.query; resizeInput(); syncState(); $('query').focus();
}));
$('upload-button').addEventListener('click', () => $('image-input').click());
$('remove-image').addEventListener('click', clearImage);
$('image-input').addEventListener('change', async () => {
  const file = $('image-input').files[0];
  if (!file) return;
  if (!allowedTypes.has(file.type)) { notice('请上传 PNG、JPEG、WebP 或 GIF 图片。'); $('image-input').value = ''; return; }
  if (file.size > 3_500_000) { notice('图片不能超过 3.5 MB，请压缩后重试。'); $('image-input').value = ''; return; }
  readingImage = true; syncState();
  const version = ++fileVersion;
  try {
    const dataURL = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error('读取图片失败，请重新选择。')); reader.readAsDataURL(file);
    });
    if (version !== fileVersion) return;
    image = { name: file.name, dataURL }; $('attachment-preview').src = dataURL;
    $('attachment-name').textContent = file.name; $('attachment').hidden = false; notice();
  } catch (error) { notice(error.message); } finally { readingImage = false; syncState(); }
});

$('chat-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy || readingImage) return;
  const typed = $('query').value.trim();
  if (!typed && !image) return;
  const submittedImage = image;
  const query = typed || '请描述图片中商品的可见情况，帮助我整理售后问题。';
  const message = { role: 'user', text: query, pending: true, ...(submittedImage ? { imageName: submittedImage.name } : {}) };
  busy = true; notice(); session.messages.push(message); const row = renderMessage(message, submittedImage?.dataURL);
  $('query').value = ''; clearImage(); resizeInput(); persist();
  const waiting = document.createElement('div'); waiting.className = 'message'; waiting.setAttribute('role', 'status');
  waiting.innerHTML = '<span class="avatar" aria-hidden="true">✳</span><div class="message-content"><div class="message-label">星云正在处理</div><div class="thinking" aria-hidden="true"><i></i><i></i><i></i></div></div>';
  $('messages').append(waiting); scrollBottom();
  try {
    const response = await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, thread_id: session.threadId, ...(submittedImage ? { image_base64: submittedImage.dataURL } : {}) }) });
    const payload = await response.json();
    if (!response.ok) {
      const detail = typeof payload.detail === 'string' ? payload.detail : '请求未能完成，请检查输入并重试。';
      throw new Error(detail);
    }
    if (typeof payload.response !== 'string' || !payload.response.trim()) throw new Error('暂时没有收到有效答复，请重试。');
    const answer = { role: 'assistant', text: payload.response }; session.messages.push(answer); renderMessage(answer);
  } catch (error) {
    message.failed = true;
    const label = document.createElement('div'); label.className = 'failed-label'; label.textContent = '未收到回复，请重试'; row.querySelector('.message-content').append(label);
    notice(error.message === 'Failed to fetch' ? '无法连接服务，请确认本地服务仍在运行。' : error.message);
    $('query').value = typed;
    if (submittedImage) { image = submittedImage; $('attachment-preview').src = image.dataURL; $('attachment-name').textContent = image.name; $('attachment').hidden = false; }
  } finally { delete message.pending; waiting.remove(); busy = false; persist(); resizeInput(); scrollBottom(); $('query').focus(); }
});

fetch('/health').then(response => { if (!response.ok) throw new Error(); return response.json(); }).then(() => {
  $('connection').classList.add('ready'); $('connection').replaceChildren();
  const dot = document.createElement('span'); $('connection').append(dot, document.createTextNode('服务已连接'));
}).catch(() => { $('connection').replaceChildren(); const dot = document.createElement('span'); $('connection').append(dot, document.createTextNode('服务未连接')); });
