/* voice.js — in-app voice call for the Wilson PWA.
   Press "Start Call", speak; your words are transcribed in the browser (Web
   Speech API, free) and POSTed to  /voice  on your API. Wilson's reply is
   spoken back via the browser (premium Google voice on Chrome). No keys in the
   client. Honors prefers-reduced-motion. Graceful toast if the API isn't set. */
(() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const SS = window.speechSynthesis;
  const supported = !!(SR && SS);

  const $ = (id) => document.getElementById(id);
  const buzz = (ms) => {
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && 'vibrate' in navigator)
      try { navigator.vibrate(ms); } catch (e) {}
  };
  const toast = (html, ms) => {
    const t = $('toast');
    if (!t) return;
    t.innerHTML = html;
    t.classList.add('show');
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), ms || 6000);
  };

  let apiOrigin = null;
  let recognizing = false;
  let recognition = null;
  let history = [];

  async function loadConfig() {
    try {
      const r = await fetch('data/api-config.json', { cache: 'no-store' });
      if (r.ok) {
        const c = await r.json();
        apiOrigin = (c.voice_api || '').replace(/\/+$/, '') || null;
      }
    } catch (e) { apiOrigin = null; }
  }

  function addLine(meta, body) {
    const feed = $('callFeed'); if (!feed) return;
    const div = document.createElement('div');
    div.className = 'card rise';
    div.innerHTML = '<div class="meta">' + meta + '</div><div class="body">' +
      String(body).replace(/[&<>]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m])) + '</div>';
    feed.prepend(div);
  }

  function speak(text) {
    if (!SS) return;
    const utter = new SpeechSynthesisUtterance(text);
    const voices = (typeof SS.getVoices === 'function') ? SS.getVoices() : [];
    const pick = voices.find(v => /google/i.test(v.name) && /en-us/i.test(v.lang)) ||
                 voices.find(v => /google/i.test(v.name)) ||
                 voices.find(v => /en-us/i.test(v.lang)) || voices[0];
    if (pick) utter.voice = pick;
    utter.rate = 1.0; utter.pitch = 1.0; utter.volume = 1.0;
    SS.cancel(); SS.speak(utter);
  }

  async function replyFor(text) {
    if (!apiOrigin) throw new Error('api-origin-missing');
    const payload = { message: text, history: history.slice(-6) };
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), 20000);
    const r = await fetch(apiOrigin + '/voice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: ctrl.signal
    });
    clearTimeout(to);
    if (!r.ok) throw new Error('http ' + r.status);
    const d = await r.json();
    return d.reply || '';
  }

  function startRecognition() {
    const r = new SR();
    r.continuous = false;           // one utterance per activation — mobile-friendly
    r.interim = false;
    r.lang = navigator.language || 'en-US';
    r.onresult = (e) => {
      const res = e.results[0];
      const q = res && res[0] && res[0].transcript ? res[0].transcript.trim() : '';
      if (!q) return;
      addLine('you', q);
      history.push({ role: 'user', content: q });
      handleTurn(q);
    };
    r.onerror = () => {};
    r.onend = () => { if (recognizing) startRecognition(); };  // re-arm → call feel
    try { r.start(); recognition = r; } catch (e) { setStatus('error'); }
  }

  async function handleTurn(text) {
    recognizing = false;
    const cb = $('startCallBtn'); if (cb) cb.disabled = true;
    setStatus('Wilson is replying…');
    try {
      const reply = await replyFor(text);
      addLine('Wilson', reply);
      history.push({ role: 'assistant', content: reply });
      speak(reply);
      buzz(30);
    } catch (err) {
      if (err.name === 'AbortError') toast('Wilson is taking too long. Try again.');
      else if (err.message === 'api-origin-missing')
        toast('Set voice_api in data/api-config.json to your API origin (e.g. https://wilson-jarvis-api.up.railway.app).');
      else toast('Voice error: ' + err.message);
    }
    recognizing = true;
    if (cb) cb.disabled = false;
    setStatus('listening…');
  }

  function startCall() {
    loadConfig().then(() => {
      if (!apiOrigin) toast('Set voice_api in data/api-config.json to your API origin.');
      buzz(15);
      history = [];
      const feed = $('callFeed'); if (feed) feed.innerHTML = '';
      addLine('ready', 'Listening… speak after the tone.');
      setStatus('listening…');
      recognizing = true;
      const cb = $('startCallBtn'); const eb = $('endCallBtn');
      if (cb) cb.disabled = true;
      if (eb) eb.disabled = false;
      startRecognition();
    });
  }

  function endCall() {
    recognizing = false;
    if (recognition) { try { recognition.abort(); } catch (e) {} recognition = null; }
    try { SS.cancel(); } catch (e) {}
    const cb = $('startCallBtn'); const eb = $('endCallBtn');
    if (cb) cb.disabled = false;
    if (eb) eb.disabled = true;
    setStatus('call ended');
  }

  function setStatus(t) { const s = $('callStatus'); if (s) s.textContent = t; }

  function bind() {
    if ($('startCallBtn')) $('startCallBtn').addEventListener('click', startCall);
    if ($('endCallBtn')) $('endCallBtn').addEventListener('click', endCall);
    if (!supported) {
      const cb = $('startCallBtn');
      if (cb) { cb.disabled = true; cb.textContent = '🎙️ Voice unavailable'; }
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
  // Some browsers populate voices asynchronously.
  if (SS) setTimeout(() => { try { SS.getVoices(); } catch (e) {} }, 300);
})();
