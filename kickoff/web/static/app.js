/* KICKOFF Mini App */
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { try { tg.ready(); tg.expand(); tg.setHeaderColor && tg.setHeaderColor('#07090d'); tg.setBackgroundColor && tg.setBackgroundColor('#07090d'); tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) {} }
const DEV = new URLSearchParams(location.search).get('dev');

const S = { view: 'home', tab: 'team', sub: 'squad', profile: null, team: null, match: null, table: null,
  market: null, club: null, mfilter: 'ALL', mpage: 0, mq: '', league: null, draft: null, draftLeague: 1, live: null };

/* ---------------- utils */
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
function money(v) {
  const s = v < 0 ? '-' : ''; v = Math.abs(v);
  if (v >= 1e9) return `${s}€${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `${s}€${(v / 1e6).toFixed(v >= 1e8 ? 0 : 1)}M`;
  if (v >= 1e3) return `${s}€${Math.round(v / 1e3)}K`;
  return `${s}€${v}`;
}
const initials = n => n.split(/[\s-]+/).filter(Boolean).slice(0, 2).map(x => x[0]).join('').toUpperCase();
const haptic = (t = 'light') => { try { tg && tg.HapticFeedback && (t === 'success' || t === 'error' || t === 'warning' ? tg.HapticFeedback.notificationOccurred(t) : tg.HapticFeedback.impactOccurred(t)); } catch (e) {} };
const POS = { GK: 'ВР', DF: 'ЗХ', MF: 'ПЗ', FW: 'НП' };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(path, data) {
  const headers = { 'Content-Type': 'application/json', 'X-Init-Data': tg ? tg.initData : '' };
  if (DEV) headers['X-Dev-User'] = DEV;
  const r = await fetch(path, data === undefined ? { headers } : { method: 'POST', headers, body: JSON.stringify(data) });
  let j = {};
  try { j = await r.json(); } catch (e) {}
  if (!r.ok || j.ok === false) { const err = new Error(j.error || 'Помилка з’єднання'); err.status = r.status; throw err; }
  return j;
}
async function call(path, data, { toastOk = true } = {}) {
  try {
    const j = await api(path, data);
    if (j.message && toastOk) toast(j.message, j.message.startsWith('+') ? 'coins' : 'good');
    return j;
  } catch (e) { toast(e.message, 'bad'); haptic('error'); throw e; }
}
function toast(text, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind; el.innerHTML = esc(text);
  $('#toast-root').appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .3s'; el.style.opacity = 0; setTimeout(() => el.remove(), 300); }, 2600);
}

/* ---------------- crest */
function shade(hex, f) {
  const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16);
  let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  r = Math.round(Math.min(255, Math.max(0, r * f))); g = Math.round(Math.min(255, Math.max(0, g * f))); b = Math.round(Math.min(255, Math.max(0, b * f)));
  return `rgb(${r},${g},${b})`;
}
function badgeSVG(c) {
  const [a, b] = c.colors || ['#6366f1', '#ffffff'];
  const id = 'g' + c.id + Math.random().toString(36).slice(2, 6);
  const txt = initials(c.name).slice(0, 3);
  return `<svg viewBox="0 0 100 116" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="${shade(a, 1.15)}"/><stop offset="1" stop-color="${shade(a, .7)}"/></linearGradient></defs>
  <path d="M50 3 L94 16 V58 C94 86 74 104 50 113 C26 104 6 86 6 58 V16 Z" fill="url(#${id})" stroke="${b}" stroke-width="5"/>
  <path d="M50 3 L50 113" stroke="${b}" stroke-opacity=".35" stroke-width="14"/>
  <text x="50" y="72" text-anchor="middle" font-family="Oswald,Inter,sans-serif" font-weight="800" font-size="${txt.length > 2 ? 26 : 32}" fill="${b}" stroke="${shade(a, .5)}" stroke-width="1.2">${esc(txt)}</text></svg>`;
}
function crest(c, size = 56) {
  const inner = c.crest ? `<img src="${esc(c.crest)}" alt="" loading="lazy" onerror="this.outerHTML=window.__badge(${c.id})">` : badgeSVG(c);
  window.__clubs = window.__clubs || {}; window.__clubs[c.id] = c;
  return `<div class="crest" style="width:${size}px;height:${size}px;border-radius:${Math.round(size * .3)}px">${inner}</div>`;
}
window.__badge = id => badgeSVG(window.__clubs[id]);

/* ---------------- confetti */
function confetti(n = 140) {
  const cv = $('#confetti'), ctx = cv.getContext('2d');
  cv.width = innerWidth * devicePixelRatio; cv.height = innerHeight * devicePixelRatio; ctx.scale(devicePixelRatio, devicePixelRatio);
  const cols = ['#e3b54a', '#f5d78e', '#ffffff', '#b8862b', '#2fbf71', '#d9dde5'];
  const ps = Array.from({ length: n }, () => ({ x: innerWidth / 2 + (Math.random() - .5) * 80, y: innerHeight * .35,
    vx: (Math.random() - .5) * 14, vy: -Math.random() * 14 - 4, s: 4 + Math.random() * 6, c: cols[Math.random() * cols.length | 0],
    r: Math.random() * 6, vr: (Math.random() - .5) * .4 }));
  let t = 0;
  (function frame() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    ps.forEach(p => { p.vy += .35; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.fillRect(-p.s / 2, -p.s / 2, p.s, p.s * .6); ctx.restore(); });
    if (++t < 160) requestAnimationFrame(frame); else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })();
}

/* ---------------- icons */
const IC = {
  user: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/></svg>',
  shop: '<svg viewBox="0 0 24 24"><path d="M6 7h12l-1 13H7L6 7z"/><path d="M9 7a3 3 0 0 1 6 0"/></svg>',
  coin: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M14.8 9.2c-.5-.8-1.6-1.3-2.8-1.3-1.7 0-3 .9-3 2.1 0 2.8 6 1.4 6 4.2 0 1.2-1.3 2.1-3 2.1-1.3 0-2.4-.5-2.9-1.4M12 6v1.9M12 16.3V18"/></svg>',
  home: '<svg viewBox="0 0 24 24"><path d="M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-4v-6H9v6H5a1 1 0 0 1-1-1z"/></svg>',
  ball: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7l4 3-1.5 4.5h-5L8 10z"/><path d="M12 7V3M16 10l4-1M14.5 14.5l2.5 3.5M9.5 14.5L7 18M8 10L4 9"/></svg>',
  swap: '<svg viewBox="0 0 24 24"><path d="M4 8h14l-4-4M20 16H6l4 4"/></svg>',
  list: '<svg viewBox="0 0 24 24"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/></svg>',
  club: '<svg viewBox="0 0 24 24"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/></svg>',
  back: '<svg viewBox="0 0 24 24"><path d="M15 5l-7 7 7 7"/></svg>',
  play: '<svg viewBox="0 0 24 24" style="fill:currentColor;stroke:none"><path d="M7 4.5v15l13-7.5z"/></svg>',
};
const gradDefs = '<svg width="0" height="0" style="position:absolute"><defs><linearGradient id="gradNav" x1="0" x2="1"><stop offset="0" stop-color="#f5d78e"/><stop offset="1" stop-color="#c9952f"/></linearGradient></defs></svg>';

/* ---------------- stadium hero art */
function stadiumSVG() {
  let lights = '';
  [80, 200, 320, 440].forEach((x, i) => {
    lights += `<g><rect x="${x - 18}" y="${18 + (i % 2) * 6}" width="36" height="10" rx="3" fill="#fff8d6"/>
    <polygon points="${x - 18},${28 + (i % 2) * 6} ${x + 18},${28 + (i % 2) * 6} ${x + 120},300 ${x - 120},300" fill="url(#beam)" opacity=".55"/></g>`;
  });
  let crowd = '';
  for (let i = 0; i < 160; i++) crowd += `<circle cx="${(i * 37) % 520}" cy="${118 + ((i * 13) % 34)}" r="${1 + (i % 3) * .5}" fill="${['#e3b54a', '#9aa3b5', '#ffffff', '#c9952f', '#5b6475'][i % 5]}" opacity="${.25 + (i % 4) * .12}"/>`;
  return `<svg class="stadium" viewBox="0 0 520 300" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
  <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#14161c"/><stop offset=".55" stop-color="#0b0e14"/><stop offset="1" stop-color="#07090d"/></linearGradient>
  <linearGradient id="beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff3b0" stop-opacity=".8"/><stop offset="1" stop-color="#fff3b0" stop-opacity="0"/></linearGradient>
  <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#156a3f"/><stop offset="1" stop-color="#0a3a23"/></linearGradient></defs>
  <rect width="520" height="300" fill="url(#sky)"/>
  <path d="M0 105 Q260 70 520 105 L520 160 L0 160Z" fill="#11141b"/>${crowd}
  <path d="M-40 300 L70 165 L450 165 L560 300Z" fill="url(#grass)"/>
  <g stroke="#bff5d6" stroke-opacity=".55" stroke-width="2" fill="none"><path d="M70 165 L450 165 L560 300 L-40 300Z"/>
  <path d="M260 165 L260 300"/><ellipse cx="260" cy="225" rx="60" ry="22"/><path d="M180 165 L170 190 L350 190 L340 165"/></g>
  ${lights}</svg>`;
}

/* ---------------- render root */
function nav() {
  if (S.view === 'career') {
    const t = [['team', 'Команда', IC.home], ['match', 'Матч', IC.ball], ['transfer', 'Трансфер', IC.swap], ['table', 'Таблиця', IC.list], ['club', 'Клуб', IC.club]];
    const offers = S.team && S.team.offers;
    return `<nav class="nav">${t.map(([k, l, i]) => `<button class="${S.tab === k ? 'on' : ''}" onclick="go('${k}')">${i}${l}${k === 'transfer' && offers ? '<span class="dot"></span>' : ''}</button>`).join('')}</nav>`;
  }
  const t = [['home', 'Профіль', IC.user], ['shop', 'Магазин', IC.shop], ['earn', 'Заробіток', IC.coin]];
  const dot = S.profile && (S.profile.daily.available || S.profile.claimable);
  return `<nav class="nav">${t.map(([k, l, i]) => `<button class="${S.view === k ? 'on' : ''}" onclick="show('${k}')">${i}${l}${k === 'earn' && dot ? '<span class="dot"></span>' : ''}</button>`).join('')}</nav>`;
}
function render(html) { $('#app').innerHTML = gradDefs + html + nav(); }
function loading() { render('<div class="spinner"></div>'); }

async function show(view) {
  haptic();
  S.view = view;
  if (['home', 'shop', 'earn'].includes(view)) { await loadProfile(); }
  draw();
}
function draw() {
  ({ home: drawHome, shop: drawShop, earn: drawEarn, career: drawCareer, newcareer: drawNewCareer }[S.view] || drawHome)();
  window.scrollTo && S.keepScroll !== true && window.scrollTo(0, 0);
  S.keepScroll = false;
}
async function loadProfile() { const j = await call('/api/profile'); S.profile = j.data; }

/* ---------------- HOME */
function avatarHTML(p) {
  const u = p.user;
  const img = u.photo ? `<img src="${esc(u.photo)}" alt="">` : `<div>${esc(initials(u.name || 'Т'))}</div>`;
  return `<div class="avatar">${img}<div class="lvl">${p.level}</div></div>`;
}
function drawHome() {
  const p = S.profile;
  const active = p.slots.find(s => s.slot === p.active && s.state === 'career');
  const others = p.slots.filter(s => !(active && s.slot === active.slot));
  const rewardAmt = p.daily.available ? p.daily.amount : p.tasks.filter(t => t.done && !t.claimed).reduce((a, t) => a + t.reward, 0);
  let html = `<div class="hero">${stadiumSVG()}<div class="fade"></div>
    <div class="top"><div class="brand">KICKOFF</div><div class="coin-pill"><span class="coin"></span><span id="coins">${p.coins}</span></div></div>
    <div class="who">${avatarHTML(p)}<div class="grow"><div class="uname ellipsis">${esc(p.user.name)}</div>
      ${p.user.username ? `<div class="muted" style="font-weight:700;margin-top:4px">@${esc(p.user.username)}</div>` : ''}
      <div class="rank">${esc(p.rank)} <div class="bar" style="width:90px"><i style="width:${Math.min(100, p.xpIn / p.xpNeed * 100)}%"></i></div> ${p.xpIn}/${p.xpNeed}</div></div></div></div>`;
  html += `<div class="section-title">Поточна кар’єра</div>`;
  if (active) {
    const c = active.career;
    html += `<div class="card glow career m16 fadein">
      <div class="bg" style="background:radial-gradient(80% 90% at 0% 0%,${c.club.colors[0]}55,transparent 60%)"></div>
      <div class="row" style="gap:16px;position:relative">${crest(c.club, 78)}<div class="grow">
        <div class="club-name ellipsis">${esc(c.club.name)}</div>
        <div class="stat-line">${esc(c.club.leagueShort)} · Сезон ${c.season} · 🏆 ${c.trophies}</div>
        <div class="stat-line"><span class="hl">${c.position}</span> місце з ${c.of} · ${c.points} очок</div></div></div>
      <button class="btn tap" style="margin-top:18px" onclick="openCareer()">${c.fired ? 'Тебе звільнено' : 'Продовжити'} <span style="font-size:22px">→</span></button></div>`;
  } else {
    html += `<div class="card glow career m16"><div class="h" style="font-size:20px;font-weight:800">Почни свою історію</div>
      <div class="muted" style="margin:8px 0 16px;font-weight:600">Обери будь-який клуб з 7 ліг: УПЛ, АПЛ, Ла Ліга, Бундесліга, Серія А, Ліга 1 або Перша ліга.</div>
      <button class="btn tap" onclick="newCareer(${(p.slots.find(s => s.state === 'empty') || { slot: 0 }).slot})">Почати кар’єру →</button></div>`;
  }
  if (rewardAmt > 0) {
    html += `<div class="reward m16 tap" style="margin-top:14px" onclick="${p.daily.available ? 'claimDaily()' : "show('earn')"}">
      <div class="ico">🎁</div><div class="grow"><b style="font-size:17px">Нагорода чекає</b>
      <div class="muted" style="font-weight:700;font-size:14px;margin-top:2px">${p.daily.available ? `Щоденний бонус · серія ${p.daily.streak} дн.` : 'Завдання виконано, забери'}</div></div>
      <div class="plus">+${rewardAmt} <span class="coin"></span></div></div>`;
  }
  html += `<div class="section-title">Інші кар’єри <small>зайнято ${p.slots.filter(s => s.state === 'career').length} з ${p.slots.length} слотів</small></div><div class="card m16">`;
  if (!others.length) html += `<div class="empty">Усі слоти вже використано</div>`;
  others.forEach(s => {
    if (s.state === 'career') {
      const c = s.career;
      html += `<div class="slot tap" onclick="selectSlot(${s.slot})">${crest(c.club, 56)}<div class="grow"><b style="font-size:17px">${esc(c.club.name)}</b>
        <div class="muted" style="font-weight:700;font-size:14px">${esc(c.club.leagueShort)} · ${c.season} · ${c.position} місце</div></div><span class="muted">›</span></div>`;
    } else if (s.state === 'empty') {
      html += `<div class="slot tap" onclick="newCareer(${s.slot})"><div class="box">+</div><div class="grow"><b style="font-size:17px">Нова кар’єра</b>
        <div class="muted" style="font-weight:700;font-size:14px">Вільний слот: будь-який клуб</div></div><span class="muted">›</span></div>`;
    } else {
      html += `<div class="slot tap" onclick="unlockSlot()"><div class="box lock">🔒</div><div class="grow"><b style="font-size:17px">${s.slot === 2 ? 'Третій' : 'Додатковий'} слот</b>
        <div class="muted" style="font-weight:700;font-size:14px">Ще одна кар’єра</div></div><div class="price"><span class="coin"></span>${s.price}</div></div>`;
    }
  });
  html += `</div>`;
  if (p.hall && p.hall.length) {
    html += `<div class="section-title">Зала слави</div><div class="card m16 list">` + p.hall.slice(0, 5).map((h, i) =>
      `<div class="item"><div class="big-num" style="width:28px;color:${['#e3b54a', '#c7ccd6', '#c27a3a'][i] || 'var(--muted)'}">${i + 1}</div>
      <div class="grow"><b>${esc(h.manager)}</b><div class="muted" style="font-size:13px;font-weight:700">${esc(h.club)} · 🏆${h.titles} · ${h.seasons} сез.</div></div>
      <b class="big-num" style="color:var(--cyan)">${h.score}</b></div>`).join('') + `</div>`;
  }
  render(html);
}
async function claimDaily() {
  const j = await call('/api/daily', {}); S.profile = j.data; haptic('success'); confetti(90); draw();
}
async function unlockSlot() {
  const s = S.profile.slots.find(x => x.state === 'locked');
  sheet(`<div class="h" style="font-size:22px;font-weight:800">Відкрити слот?</div>
    <p class="muted" style="font-weight:600">Ще одна паралельна кар’єра з будь-яким клубом.</p>
    <button class="btn gold tap" onclick="doUnlock()">Відкрити за ${s.price} <span class="coin"></span></button>`);
}
async function doUnlock() { closeSheet(); const j = await call('/api/slot/unlock', {}); S.profile = j.data; confetti(); haptic('success'); draw(); }
async function selectSlot(slot) { const j = await call('/api/career/select', { slot }); S.profile = j.data; openCareer(); }

/* ---------------- SHOP */
function drawShop() {
  const p = S.profile;
  let html = `<div class="chead"><div class="grow h" style="font-size:20px;font-weight:800">Магазин</div><div class="coin-pill"><span class="coin"></span>${p.coins}</div></div>
  <p class="muted pad" style="font-weight:600">Монети заробляються в матчах, завданнях і щоденних бонусах. Покупки діють на активну кар’єру.</p>
  <div class="shop-grid">` + p.shop.map(it => `<div class="card shop-item"><div class="ic">${it.icon}</div><b style="font-size:16px">${esc(it.title)}</b>
    <div class="muted" style="font-size:13px;font-weight:600;flex:1">${esc(it.desc)}</div>
    <button class="btn small gold tap" onclick="buyItem('${it.id}')">${it.price} <span class="coin"></span></button></div>`).join('') + `</div>`;
  const locked = p.slots.find(s => s.state === 'locked');
  if (locked) html += `<div class="section-title">Слоти</div><div class="card m16 slot tap" onclick="unlockSlot()"><div class="box lock">🔒</div><div class="grow"><b>Слот кар’єри</b><div class="muted" style="font-size:13px;font-weight:700">Веди дві-три команди одночасно</div></div><div class="price"><span class="coin"></span>${locked.price}</div></div>`;
  render(html);
}
async function buyItem(id) { const j = await call('/api/shop', { item: id }); S.profile = j.data; haptic('success'); confetti(60); draw(); }

/* ---------------- EARN */
function drawEarn() {
  const p = S.profile;
  const streak = p.daily.streak;
  let days = '';
  for (let i = 1; i <= 7; i++) {
    const done = i <= streak && !p.daily.available ? true : i < (p.daily.available ? streak + 1 : streak + 1) && i <= streak;
    const next = p.daily.available && i === Math.min(7, streak + 1);
    days += `<div class="${done ? 'done' : ''} ${next ? 'next' : ''}"><span class="coin" style="width:18px;height:18px"></span>+${5 + i * 2}<span>${i} д</span></div>`;
  }
  let html = `<div class="chead"><div class="grow h" style="font-size:20px;font-weight:800">Заробіток</div><div class="coin-pill"><span class="coin"></span>${p.coins}</div></div>
  <div class="card glow m16" style="padding:18px;margin-top:14px"><div class="row between"><div><b class="h" style="font-size:18px">Щоденний бонус</b>
  <div class="muted" style="font-weight:700;font-size:13px;margin-top:4px">Заходь щодня, серія збільшує нагороду</div></div><div class="plus">+${p.daily.amount}<span class="coin"></span></div></div>
  <div class="streak">${days}</div>
  <button class="btn ${p.daily.available ? 'gold' : 'ghost'} tap" style="margin-top:16px" ${p.daily.available ? '' : 'disabled'} onclick="claimDailyEarn()">${p.daily.available ? 'Забрати бонус' : 'Повертайся завтра'}</button></div>`;
  const daily = p.tasks.filter(t => t.kind === 'daily'), ach = p.tasks.filter(t => t.kind === 'achievement');
  const icons = { play3: '⚽', win1: '🏅', clean1: '🧤', score3: '🎯', first_win: '🥇', first_season: '📅', target_met: '🎯', promotion: '🚀', title: '🏆', unbeaten5: '🛡' };
  const taskRow = t => `<div class="task"><div class="tic">${icons[t.id] || '⭐'}</div><div class="grow"><b>${esc(t.title)}</b>
    <div class="row" style="margin-top:6px"><div class="bar green grow"><i style="width:${t.progress / t.goal * 100}%"></i></div><span class="muted" style="font-size:12px;font-weight:800">${t.progress}/${t.goal}</span></div></div>
    ${t.claimed ? '<span class="chip">✓</span>' : t.done ? `<button class="btn small gold tap" onclick="claimTask('${t.id}')">+${t.reward}</button>` : `<span class="price" style="font-size:13px">+${t.reward}<span class="coin" style="width:16px;height:16px"></span></span>`}</div>`;
  html += `<div class="section-title">Завдання дня</div><div class="card m16">${daily.map(taskRow).join('')}</div>`;
  html += `<div class="section-title">Досягнення</div><div class="card m16">${ach.map(taskRow).join('')}</div>`;
  render(html);
}
async function claimDailyEarn() { const j = await call('/api/daily', {}); S.profile = j.data; haptic('success'); confetti(90); draw(); }
async function claimTask(id) { const j = await call('/api/task', { id }); S.profile = j.data; haptic('success'); confetti(70); draw(); }

/* ---------------- NEW CAREER */
async function newCareer(slot) {
  haptic(); S.view = 'newcareer'; loading();
  const j = await call('/api/career/draft', { slot }); S.draft = j.data; S.draftLeague = S.draft.leagues[0].id; draw();
}
function drawNewCareer() {
  const d = S.draft; const L = d.leagues.find(l => l.id === S.draftLeague);
  let html = `<div class="chead"><button class="iconbtn" onclick="show('home')">${IC.back}</button><div class="grow"><div class="h" style="font-weight:800;font-size:18px">Обери клуб</div>
    <div class="muted" style="font-size:13px;font-weight:700">Сезон 2026/27 · ${L.clubs.length} клубів</div></div></div>
    <div class="chips" style="margin-top:12px">${d.leagues.map(l => `<button class="chip ${l.id === S.draftLeague ? 'on' : ''}" onclick="S.draftLeague=${l.id};draw()">${l.flag} ${esc(l.short)}</button>`).join('')}</div>
    <div class="card m16 list" style="margin-top:8px">` + L.clubs.map(c => `<div class="item tap" onclick="pickClub(${c.id})">${crest(c, 50)}<div class="grow">
      <b style="font-size:16px">${esc(c.name)}</b><div class="muted" style="font-size:13px;font-weight:700">${esc(c.city)} · бюджет ${money(c.budget)}</div></div>
      <div class="ovr"><b class="${sc(c.rating)}">${c.rating}</b></div></div>`).join('') + `</div>`;
  render(html);
}
const LINE_UA = { GK: 'Воротар', DF: 'Захист', MF: 'Півзахист', FW: 'Атака' };
const DIFF_UA = ['', 'Легко', 'Нормально', 'Складно', 'Дуже складно', 'Виживання'];
function pickClub(id) {
  const c = S.draft.leagues.flatMap(l => l.clubs).find(x => x.id === id); const P = c.profile || {};
  const col = (c.colors && c.colors[0]) || '#3b82f6';
  const lines = Object.entries(P.lines || {}).map(([k, v]) => `<div class="cp-line"><span>${LINE_UA[k]}</span>
    <div class="cp-bar"><i style="width:${Math.max(6, Math.min(100, (v - 40) / 55 * 100))}%"></i></div><b class="${sc(v)}">${v}</b></div>`).join('');
  const stars = (P.stars || []).map(p => `<div class="cp-star"><div class="cp-ovr ${sc(p.skill)}">${p.skill}</div>
    <div class="grow"><b class="ellipsis" style="display:block">${esc(p.name)}</b><span class="muted">${p.flag} ${p.age} р.${p.number ? ' · №' + p.number : ''}</span></div>
    <span class="role">${esc(p.role || '')}</span></div>`).join('');
  const euro = P.euro ? `<div class="cp-euro ${P.euro.code.slice(0, 3).toLowerCase()}">${P.euro.icon} ${esc(P.euro.name)}</div>` : `<div class="cp-euro none">Без єврокубків</div>`;
  const diff = P.difficulty || 3;
  sheet(`<div class="cp" style="--club:${col}">
  <div class="cp-head">${crest(c, 84)}<div class="grow"><div class="club-name">${esc(c.name)}</div>
    ${P.nick ? `<div class="cp-nick">«${esc(P.nick)}»</div>` : ''}
    <div class="muted" style="font-weight:700">${c.flag} ${esc(c.leagueShort)} · ${esc(c.city)}</div></div></div>
  ${euro}
  <p class="cp-story">${esc(P.story || '')}</p>
  <div class="kv"><div><b>${c.rating}</b><span>Сила складу</span></div><div><b>${P.rank || '–'}<small>/${P.of || ''}</small></b><span>Ранг у лізі</span></div><div><b>${money(c.budget)}</b><span>Бюджет</span></div></div>
  <div class="cp-sec">Лінії команди</div><div class="cp-lines">${lines}</div>
  <div class="cp-sec">Зірки команди</div><div class="cp-stars">${stars}</div>
  <div class="cp-sec">Клуб</div>
  <div class="cp-grid">
    <div><span>Вартість складу</span><b>${money(P.value || 0)}</b></div>
    <div><span>Зарплати / рік</span><b>${money(P.wages || 0)}</b></div>
    <div><span>Стадіон</span><b>${(P.stadium || 0).toLocaleString('uk-UA')}</b></div>
    <div><span>Середній вік</span><b>${P.avgAge || '–'}</b></div>
    <div><span>Гравців / легіонерів</span><b>${P.size || 0} / ${P.foreign || 0}</b></div>
    <div><span>Репутація</span><b>${c.rep}</b></div>
  </div>
  <div class="cp-board"><div><span>Ціль правління</span><b>Топ-${P.target || '–'}</b></div>
    <div><span>Складність</span><b class="diff d${diff}">${'●'.repeat(diff)}${'○'.repeat(5 - diff)} ${DIFF_UA[diff]}</b></div></div>
  <button class="btn tap" onclick="createCareer(${id})">Очолити ${esc(c.name)} →</button></div>`);
}
async function createCareer(id) {
  closeSheet(); loading();
  const j = await call('/api/career/create', { slot: S.draft.slot, club_id: id });
  S.profile = j.data; confetti(160); haptic('success'); openCareer();
}

/* ---------------- CAREER */
async function openCareer() { haptic(); S.view = 'career'; S.tab = 'team'; S.sub = 'xi'; S.lineup = null; loading(); await loadTab(); }
async function loadTab() {
  if (S.tab === 'team') { S.team = (await call('/api/team')).data; S.lineup = null; }
  if (S.tab === 'match') { S.match = (await call('/api/match')).data; S.team = S.team || (await call('/api/team')).data; }
  if (S.tab === 'transfer') S.market = (await call(`/api/market?f=${S.mfilter}&page=${S.mpage}&q=${encodeURIComponent(S.mq)}`)).data;
  if (S.tab === 'table') S.table = (await call('/api/table' + (S.league ? `?league=${S.league}` : ''))).data;
  if (S.tab === 'club') S.club = (await call('/api/club')).data;
  if (!S.team) S.team = (await call('/api/team')).data;
  draw();
}
async function go(tab) { if (S.live && !S.live.done) return; S.live = null; haptic(); S.tab = tab; loading(); await loadTab(); }
function careerHead() {
  const t = S.team, p = S.profile;
  const ava = p && p.user.photo ? `<img src="${esc(p.user.photo)}" style="width:24px;height:24px;border-radius:50%;position:absolute;right:-6px;bottom:-6px;border:2px solid var(--bg)">` : '';
  return `<div class="chead"><button class="iconbtn" onclick="show('home')">${IC.back}</button>
  <div style="position:relative">${crest(t.club, 44)}${ava}</div><div class="grow"><div class="h ellipsis" style="font-weight:800;font-size:18px">${esc(t.club.name)}</div>
  <div class="muted" style="font-size:13px;font-weight:700">Сезон ${t.season}</div></div><div class="money">${money(t.budget)}</div></div>`;
}
function drawCareer() {
  const body = { team: teamTab, match: matchTab, transfer: transferTab, table: tableTab, club: clubTab }[S.tab]();
  render(careerHead() + body);
}
const sc = s => s >= 80 ? 's80' : s >= 70 ? 's70' : s >= 55 ? 's60' : 's0';

function teamTab() {
  const t = S.team, st = t.stats;
  let html = `<div class="card glow m16 fadein" style="padding:18px;margin-top:14px">
    <div class="bg" style="position:absolute;inset:0;background:radial-gradient(70% 80% at 100% 0%,${t.club.colors[0]}40,transparent 60%)"></div>
    <div class="row" style="gap:16px;position:relative">${crest(t.club, 76)}<div class="grow"><div class="club-name ellipsis">${esc(t.club.name)}</div>
    <div class="muted" style="font-weight:700;margin-top:4px">${t.club.flag} ${esc(t.club.leagueShort)} · ${st.position} місце · ${st.points} оч.</div></div></div>
    <div class="stats"><div><b>${st.rating}</b><span>Рейтинг</span></div><div><b style="color:var(--green)">${st.wins}</b><span>Перемог</span></div>
    <div><b>${st.played}/${st.rounds}</b><span>Матчів</span></div><div><b style="color:var(--gold);font-size:16px">${money(st.value)}</b><span>Вартість</span></div></div>
    <div class="row" style="margin-top:14px;flex-wrap:wrap;gap:8px"><span class="muted" style="font-size:12px;font-weight:800;letter-spacing:.12em">ТРОФЕЇ:</span>
      ${t.trophies.league ? `<span class="trophy gold">🏆 Ліга ×${t.trophies.league}</span>` : ''}${t.trophies.promo ? `<span class="trophy green">🚀 Підвищення ×${t.trophies.promo}</span>` : ''}
      ${!t.trophies.league && !t.trophies.promo ? '<span class="dim" style="font-weight:700;font-size:13px">ще попереду</span>' : ''}</div>
    <div class="conf">Довіра правління <div class="bar ${t.confidence > 60 ? 'green' : t.confidence > 30 ? '' : 'violet'}"><i style="width:${t.confidence}%"></i></div>${t.confidence}% · ціль топ-${t.target}</div></div>
  <div class="tabs">${[['xi', 'Основа'], ['squad', 'Гравці'], ['academy', 'Академія'], ['tactics', 'Тактика']].map(([k, l]) => `<button class="${S.sub === k ? 'on' : ''}" onclick="S.sub='${k}';S.keepScroll=true;draw()">${l}</button>`).join('')}</div>`;
  if (S.sub === 'squad') {
    html += `<div class="row between pad" style="margin-top:16px"><div class="h" style="font-size:18px;font-weight:800">Склад: сезон ${t.season}</div><span class="chip">${t.count}/${t.max}</span></div>`;
    t.groups.forEach(g => { html += `<div class="card group"><div class="ghead"><b>${g.title.toUpperCase()}</b><span class="count">${g.players.length}</span></div>${g.players.map(playerRow).join('')}</div>`; });
  } else if (S.sub === 'xi') html += lineupView();
  else if (S.sub === 'academy') html += academyView();
  else html += tacticsView();
  return html;
}
function playerRow(p) {
  const fit = p.fitness >= 85 ? '' : p.fitness >= 65 ? 'mid' : 'low';
  const exp = p.contractYears <= 1;
  return `<div class="prow tap" onclick="openPlayer(${p.id})"><div class="pava ${p.pos}">${esc(initials(p.name))}<span class="pp">${esc(p.role || POS[p.pos])}</span></div>
  <div class="grow"><div class="pname ellipsis">${p.flag} ${esc(p.name)}</div><div class="tags"><span>${p.age}р</span>
  <span class="tag fit ${fit}">⚡${p.fitness}%</span><span class="tag ${exp ? 'warn' : ''}">📋 ${p.contract}</span>
  ${p.xi ? '<span class="tag xi">XI</span>' : ''}${p.yellows ? `<span class="tag yel">🟨 ${p.yellows}</span>` : ''}
  ${p.injured ? `<span class="tag bad">🤕 ${p.injured}</span>` : ''}${p.suspended ? '<span class="tag bad">🟥</span>' : ''}
  ${p.listed ? '<span class="tag warn">🏷</span>' : ''}${p.resting ? '<span class="tag">💤</span>' : ''}</div></div>
  <div class="ovr"><b class="${sc(p.skill)}">${p.skill}</b><small>${money(p.value)}</small></div></div>`;
}
function academyView() {
  const t = S.team; const young = t.groups.flatMap(g => g.players).filter(p => p.age <= 21).sort((a, b) => b.pot - a.pot);
  let html = `<div class="card m16" style="padding:16px;margin-top:16px"><div class="row between"><div><b class="h" style="font-size:17px">Академія · рівень ${t.academyLevel}/5</b>
    <div class="muted" style="font-size:13px;font-weight:700;margin-top:4px">Щосезону 2-4 вихованці. Вищий рівень = більший талант.</div></div></div>
    ${t.academyCost ? `<button class="btn small violet tap" style="margin-top:12px" onclick="upgrade('academy')">Покращити · ${money(t.academyCost)}</button>` : ''}</div>
    <div class="section-title">Молоді гравці (до 21)</div><div class="card m16">`;
  html += young.length ? young.map(p => playerRow(p).replace('</small></div></div>', `</small><small style="color:var(--pink)">пот. ${p.pot}</small></div></div>`)).join('') : '<div class="empty">Поки немає молоді</div>';
  return html + '</div>';
}
function tacticsView() {
  const tc = S.team.tactics;
  const styleDesc = { attacking: 'Більше моментів, але оборона слабша', balanced: 'Надійний баланс', defensive: 'Міцно позаду, менше гостроти', counter: 'Віддаємо м’яч і б’ємо швидко', pressing: 'Перевага в центрі, сильна втома' };
  const trDesc = { balanced: 'Рівномірний розвиток', attack: 'ПЗ і НП ростуть швидше', defense: 'ЗХ і ВР ростуть швидше', fitness: 'Краще відновлення', youth: 'Молодь до 21 росте значно швидше' };
  return `<div class="section-title">Схема</div><div class="chips">${tc.formations.map(f => `<button class="chip ${f === tc.formation ? 'on' : ''}" onclick="setTac({formation:'${f}'})">${f}</button>`).join('')}</div>
  <div class="section-title">Стиль гри</div><div class="grid2 pad">${Object.entries(tc.styles).map(([k, v]) => `<button class="opt tap ${k === tc.style ? 'on' : ''}" onclick="setTac({style:'${k}'})"><b>${esc(v)}</b><span>${styleDesc[k]}</span></button>`).join('')}</div>
  <div class="section-title">Тренування <small>база ${S.team.trainingLevel}/5</small></div><div class="grid2 pad">${Object.entries(tc.trainings).map(([k, v]) => `<button class="opt tap ${k === tc.training ? 'on' : ''}" onclick="setTac({training:'${k}'})"><b>${esc(v)}</b><span>${trDesc[k]}</span></button>`).join('')}</div>`;
}
/* ---------------- opponent dossier */
function dossierHTML(m) {
  const d = m.dossier; if (!d) return '';
  const opp = m.isHome ? m.away : m.home;
  const cmp = ['GK', 'DF', 'MF', 'FW'].map(k => { const a = d.mine[k], b = d.lines[k], t = a + b || 1;
    return `<div class="dz-row"><b class="${a >= b ? 'up' : ''}">${a}</b><div class="dz-bars"><i style="width:${a / t * 100}%"></i><i></i></div><b class="${b > a ? 'dn' : ''}">${b}</b><span>${LINE_UA[k]}</span></div>`; }).join('');
  return `<div class="section-title">Досьє суперника <small>${esc(opp.name)}</small></div>
  <div class="card m16 dz">
    <div class="dz-head">${crest(opp, 46)}<div class="grow"><b class="h" style="font-size:20px;text-transform:uppercase">${esc(opp.name)}</b>
      <div class="muted" style="font-size:12.5px;font-weight:700">${d.formation} · ${esc(m.styles[d.style] || '')}${d.played ? ` · голи ${d.gf}:${d.ga} за ${d.played} матч.` : ""}</div></div></div>
    <div class="dz-legend"><span>Ми</span><span>Вони</span></div>${cmp}
    <div class="cp-sec" style="margin-top:14px">Ключові гравці</div>
    ${d.keys.map(p => `<div class="cp-star"><div class="cp-ovr ${sc(p.skill)}">${p.skill}</div><div class="grow"><b class="ellipsis" style="display:block">${p.flag} ${esc(p.name)}</b>
      <span class="muted">${p.goals ? `⚽ ${p.goals} голів` : 'Небезпечний гравець'}</span></div><span class="role">${esc(p.role)}</span></div>`).join('')}
    ${d.h2h.length ? `<div class="cp-sec" style="margin-top:14px">Особисті зустрічі</div><div class="dz-h2h">${d.h2h.map(r => `<span>${esc(r.home)} <b>${r.hg}:${r.ag}</b> ${esc(r.away)}</span>`).join('')}</div>` : ''}
    <div class="dz-tip">🧠 <b>Порада асистента:</b> ${d.tips.map(esc).join(' ')}${d.missing ? ` У суперника ${d.missing} гравц. не зіграють.` : ''}</div>
  </div>`;
}

/* ---------------- lineup editor */
const fitCol = f => f >= 85 ? '#3fd98a' : f >= 65 ? '#e3b54a' : '#e5484d';
function pcCard(p, opts = {}) {
  if (!p) return `<div class="pc empty" style="${opts.pos || ''}" onclick="${opts.click || ''}"><div class="card-p"><div class="r">–</div><div class="ro">${esc(opts.slot || '')}</div></div><div class="nm">Пусто</div></div>`;
  const off = opts.slot && opts.slot !== p.role;
  return `<div class="pc ${sc(p.skill)} ${opts.cls || ''}" style="${opts.pos || ''}" onclick="${opts.click || ''}">
    <div class="card-p"><div class="r">${opts.eff ?? p.skill}</div><div class="fl">${p.flag}</div><div class="ro ${off ? 'off' : ''}">${esc(p.role)}</div>
    <div class="fit"><i style="width:${p.fitness}%;background:${fitCol(p.fitness)}"></i></div>
    ${opts.cap ? '<span class="cap">C</span>' : ''}${off ? `<span class="slotlbl">${esc(opts.slot)}</span>` : ''}</div>
    <div class="nm">${p.number ? p.number + ' ' : ''}${esc(p.short)}</div></div>`;
}
const FIELD_LINES = `<svg class="lines" viewBox="0 0 100 140" preserveAspectRatio="none"><g fill="none" stroke="rgba(255,255,255,.28)" stroke-width=".5">
  <rect x="3" y="3" width="94" height="134"/><line x1="3" y1="70" x2="97" y2="70"/><circle cx="50" cy="70" r="11"/>
  <rect x="24" y="3" width="52" height="20"/><rect x="37" y="3" width="26" height="7"/><rect x="24" y="117" width="52" height="20"/><rect x="37" y="130" width="26" height="7"/>
  <path d="M41 23 A10 10 0 0 0 59 23"/><path d="M41 117 A10 10 0 0 1 59 117"/></g><circle cx="50" cy="70" r=".9" fill="rgba(255,255,255,.4)"/></svg>`;
async function loadLineup() { S.lineup = (await call('/api/lineup')).data; }
function lineupView() {
  const L = S.lineup;
  if (!L) { loadLineup().then(() => { S.keepScroll = true; draw(); }); return '<div class="spinner"></div>'; }
  const chemC = L.chemistry >= 75 ? '#3fd98a' : L.chemistry >= 50 ? '#e3b54a' : '#e5484d';
  let html = `<div class="xi-top"><div class="seg">${[1, 2].map(n => `<button class="${L.set === n ? 'on' : ''}" onclick="lineupAct({action:'set',n:${n},copy:true})">Склад ${n}${L.sets[n] ? '' : ' <small>авто</small>'}</button>`).join('')}</div>
    <div class="grow"></div><button class="btn small ghost tap" onclick="lineupAct({action:'auto'})">⚡ Авто</button></div>
    <div class="xi-meta"><div><span>Сила основи</span><b class="${sc(L.rating)}" style="color:${L.rating >= 80 ? 'var(--goldL)' : '#fff'}">${L.rating}</b></div>
    <div><span>Зіграність</span><b style="color:${chemC}">${L.chemistry}%</b><div class="chem"><i style="width:${L.chemistry}%;background:${chemC}"></i></div></div></div>
    <div class="chips" style="margin-top:12px">${L.formations.map(f => `<button class="chip ${f === L.formation ? 'on' : ''}" onclick="lineupAct({action:'formation',formation:'${f}'})">${f}</button>`).join('')}</div>
    <div class="field">${FIELD_LINES}${L.slots.map(sl => pcCard(sl.player, { pos: `left:${sl.x}%;top:${sl.y}%`, slot: sl.role, eff: sl.player ? sl.player.eff : null, cap: sl.player && sl.player.id === L.captain, click: `slotTap(${sl.i})`, cls: S.selBench ? 'sel' : '' })).join('')}</div>
    <div class="muted" style="margin:8px 16px 0;font-size:12px;font-weight:700">Торкнись гравця на полі, щоб замінити. Червона позиція = гравець грає не на своєму місці.</div>
    <div class="section-title">Запасні та резерв <small>${L.bench.length}</small></div>
    <div class="bench">${L.bench.map(p => pcCard(p, { cls: (p.ok ? '' : 'na') + (S.selBench === p.id ? ' sel' : ''), click: `benchTap(${p.id})` })).join('')}</div>
    <div class="section-title">Стиль гри</div><div class="chips">${Object.entries(L.styles).map(([k, v]) => `<button class="chip ${k === L.style ? 'on' : ''}" onclick="lineupAct({action:'style',style:'${k}'})">${esc(v)}</button>`).join('')}</div>`;
  return html;
}
async function lineupAct(d) { haptic(); const j = await call('/api/lineup', d); S.lineup = j.data; S.keepScroll = true; closeSheet(); draw(); }
function benchTap(id) {
  const p = S.lineup.bench.find(x => x.id === id);
  if (!p.ok) { openPlayer(id); return; }
  S.selBench = S.selBench === id ? null : id; haptic();
  if (S.selBench) toast(`Обери позицію для ${p.short}`);
  S.keepScroll = true; draw();
}
function slotTap(i) {
  if (S.selBench) { const id = S.selBench; S.selBench = null; lineupAct({ action: 'assign', slot: i, player: id }); return; }
  const L = S.lineup, sl = L.slots[i], cur = sl.player;
  const fam = (r) => (L.fam[r] || {})[sl.role] ?? .6;
  const starters = L.slots.filter(x => x.player && x.i !== i).map(x => ({ ...x.player, where: x.role }));
  const cands = [...starters, ...L.bench.filter(p => p.ok)].map(p => ({ ...p, f: fam(p.role), e: Math.round(p.skill * fam(p.role)) })).sort((a, b) => b.e - a.e);
  const famLbl = f => f >= .97 ? ['f1', 'Рідна'] : f >= .85 ? ['f2', 'Знайома'] : ['f3', 'Чужа'];
  sheet(`<div class="row between"><div><div class="h" style="font-size:24px;font-weight:800;text-transform:uppercase">${esc(sl.role)} · ${esc(L.roles[sl.role] || '')}</div>
    <div class="muted" style="font-weight:700;font-size:13px">${cur ? `Зараз: ${esc(cur.name)} · ${cur.eff}` : 'Позиція вільна'}</div></div></div>
    ${cur ? `<div class="btns"><button class="btn small ghost tap" onclick="lineupAct({action:'captain',player:${cur.id}})">${cur.id === L.captain ? '© Капітан' : '© Зробити капітаном'}</button>
    <button class="btn small ghost tap" onclick="closeSheet();openPlayer(${cur.id})">ℹ️ Профіль</button></div>` : ''}
    <div class="cp-sec">Хто зіграє на позиції ${esc(sl.role)}</div>
    ${cands.map(p => { const [fc, fl] = famLbl(p.f); return `<div class="cand tap" onclick="lineupAct({action:'assign',slot:${i},player:${p.id}})">
      <span class="role">${esc(p.role)}</span><div class="grow"><b class="ellipsis" style="display:block">${p.flag} ${esc(p.name)}</b>
      <span class="muted" style="font-size:12px;font-weight:700">${p.where ? 'в основі · ' + esc(p.where) : 'запасний'} · ⚡${p.fitness}% · <span class="fam ${fc}">${fl}</span></span></div>
      <div style="text-align:right"><div class="eff ${sc(p.e)}" style="color:${p.e >= 80 ? 'var(--goldL)' : p.e >= 70 ? '#3fd98a' : '#c8cdd6'}">${p.e}</div><div class="dim" style="font-size:11px;font-weight:700">база ${p.skill}</div></div></div>`; }).join('')}`);
}
async function setTac(d) { haptic(); const j = await call('/api/tactics', d); S.team = j.data; S.lineup = null; S.keepScroll = true; draw(); }

/* player sheet */
async function openPlayer(id) {
  haptic();
  const p = (await call('/api/player?id=' + id)).data;
  let acts = '';
  if (p.mine) acts = `<div class="btns"><button class="btn small ghost tap" onclick="pAct(${id},'rest')">${p.resting ? '✅ Повернути' : '💤 Не ставити'}</button>
    <button class="btn small ghost tap" onclick="pAct(${id},'list')">${p.listed ? '🏷 Зняти з продажу' : '🏷 На продаж'}</button>
    <button class="btn small ghost tap" onclick="pAct(${id},'renew')">📝 Продовжити</button><button class="btn small ghost tap" onclick="pAct(${id},'quicksell')">⚡ Продати</button></div>
    <button class="btn small danger tap" style="width:100%;margin-top:10px" onclick="pAct(${id},'release')">Розірвати контракт</button>`;
  else acts = `<button class="btn tap" style="margin-top:14px" onclick="pAct(${id},'buy')">${p.clubInfo ? `Купити за ${money(p.price)}` : `Підписати · бонус ${money(p.signBonus)}`}</button>
    <p class="muted" style="text-align:center;font-weight:700;font-size:13px">Зарплата ${money(p.wageDemand)}/тиж</p>`;
  sheet(`<div class="row" style="gap:16px"><div class="pava ${p.pos}" style="width:72px;height:72px;font-size:22px;border-radius:22px">${esc(initials(p.name))}<span class="pp">${esc(p.role || POS[p.pos])}</span></div>
    <div class="grow"><div class="h" style="font-size:21px;font-weight:800">${p.flag} ${esc(p.name)}</div>
    <div class="muted" style="font-weight:700;margin-top:4px">${p.age} років · ${p.clubInfo ? esc(p.clubInfo.name) : 'Вільний агент'}${p.number ? ' · №' + p.number : ''}</div></div>
    <div class="ovr"><b class="${sc(p.skill)}" style="min-width:58px;height:50px;font-size:24px">${p.skill}</b></div></div>
    <div class="kv"><div><b style="color:var(--pink)">${p.pot}</b><span>Потенціал</span></div><div><b>${money(p.value)}</b><span>Вартість</span></div><div><b>${money(p.wage)}</b><span>Зарплата/тиж</span></div>
    <div><b style="color:var(--green)">${p.fitness}%</b><span>Форма</span></div><div><b>${p.morale}</b><span>Настрій</span></div><div><b>${p.contract}</b><span>Контракт до</span></div>
    <div><b>${p.apps}</b><span>Матчів</span></div><div><b>${p.goals}</b><span>Голів</span></div><div><b>${p.rating || '-'}</b><span>Сер. оцінка</span></div></div>${acts}`);
}
async function pAct(id, action) {
  if (action === 'release' && !confirm('Розірвати контракт? Доведеться виплатити компенсацію.')) return;
  const j = await call('/api/player', { id, action }); haptic('success');
  closeSheet(); if (action === 'buy') confetti(100);
  await loadTab();
}

/* ---------------- MATCH */
function formHTML(f) { return `<div class="form">${(f || []).map(x => `<i class="${x}">${{ W: 'В', D: 'Н', L: 'П' }[x]}</i>`).join('') || '<span class="dim" style="font-size:12px">—</span>'}</div>`; }
function matchTab() {
  const m = S.match;
  if (S.live) return liveView();
  if (m.seasonOver) return `<div class="card glow m16" style="padding:22px;margin-top:16px;text-align:center"><div style="font-size:56px">🏁</div>
    <div class="h" style="font-size:22px;font-weight:800;margin:8px 0">Сезон завершено!</div><p class="muted" style="font-weight:700">Підсумки, призові, підвищення і нові вихованці академії чекають.</p>
    <button class="btn gold tap" onclick="endSeason()">Підсумки сезону</button></div>`;
  const h = m.home, a = m.away; const tot = h.rating + a.rating;
  let html = `<div class="card glow vs m16" style="margin-top:16px"><div class="muted" style="font-weight:800;letter-spacing:.14em;font-size:12px">ТУР ${m.round} / ${m.rounds}</div>
    <div class="teams" style="margin-top:14px"><div class="t">${crest(h, 74)}<span>${esc(h.name)}</span><span class="dim" style="font-size:12px">${h.pos} місце</span>${formHTML(h.form)}</div>
    <div class="h" style="font-size:22px;color:var(--dim)">VS</div>
    <div class="t">${crest(a, 74)}<span>${esc(a.name)}</span><span class="dim" style="font-size:12px">${a.pos} місце</span>${formHTML(a.form)}</div></div>
    <div class="cmp" style="margin-top:16px"><b>${h.rating}</b><div class="bars"><i style="width:${h.rating / tot * 100}%"></i><i style="flex:1"></i></div><b>${a.rating}</b></div>
    <div class="muted" style="font-size:12px;font-weight:700">Рейтинг стартових складів</div>
    <button class="btn tap" style="margin-top:18px" onclick="playMatch()">${IC.play.replace('<svg', '<svg width="20" height="20"')} Грати матч</button>
    <button class="btn ghost small tap" style="width:100%;margin-top:10px" onclick="playMatch(true)">⏩ Одразу результат</button></div>`;
  if (m.last) html += `<div class="card m16 row" style="padding:12px 16px;margin-top:12px;justify-content:center;gap:12px"><span class="muted" style="font-weight:800;font-size:12px">МИНУЛИЙ:</span>
    ${crest(m.last.home, 28)}<b class="big-num">${m.last.hg}:${m.last.ag}</b>${crest(m.last.away, 28)}</div>`;
  html += dossierHTML(m);
  html += `<div class="section-title">Стартовий склад <small>${m.formation} · ${esc(m.styles[m.style])}</small></div><div class="field" onclick="S.tab='team';S.sub='xi';S.lineup=null;draw()">${FIELD_LINES}${m.xi.slots.map(sl => pcCard(sl.player, { pos: `left:${sl.x}%;top:${sl.y}%`, slot: sl.role, eff: sl.player ? sl.player.eff : null, cap: sl.player && sl.player.id === m.xi.captain })).join('')}</div>
    <div class="muted" style="margin:8px 16px 0;font-size:12px;font-weight:700">Зіграність ${m.xi.chemistry}% · торкнись поля, щоб змінити склад</div>`;
  if (m.unavailable.length) html += `<div class="section-title">Не зіграють</div><div class="card m16">${m.unavailable.map(playerRow).join('')}</div>`;
  html += `<div class="pad" style="margin-top:12px"><button class="btn ghost small tap" style="width:100%" onclick="S.tab='team';S.sub='xi';S.lineup=null;draw()">⚽ Змінити склад і тактику</button></div>`;
  return html;
}
function pitchHTML(lineup, formation) {
  const lines = { GK: [], DF: [], MF: [], FW: [] };
  lineup.forEach(p => lines[p.slot].push(p));
  const ys = { GK: 90, DF: 70, MF: 46, FW: 20 };
  let dots = '';
  Object.entries(lines).forEach(([k, ps]) => ps.forEach((p, i) => {
    const x = (i + 1) / (ps.length + 1) * 100;
    dots += `<div class="dot" style="left:${x}%;top:${ys[k]}%"><b style="${p.skill >= 80 ? 'background:linear-gradient(135deg,#f5d78e,#c9952f)' : ''}">${p.skill}</b><span>${esc(p.name.split(' ').slice(-1)[0])}</span></div>`;
  }));
  return `<div class="pitch"><svg class="lines" viewBox="0 0 100 140" preserveAspectRatio="none"><g stroke="rgba(255,255,255,.35)" stroke-width=".5" fill="none">
  <rect x="3" y="3" width="94" height="134"/><line x1="3" y1="70" x2="97" y2="70"/><circle cx="50" cy="70" r="11"/><rect x="25" y="3" width="50" height="18"/><rect x="25" y="119" width="50" height="18"/></g></svg>${dots}</div>`;
}
async function playMatch(fast) {
  haptic('medium');
  let res;
  try { res = (await api('/api/match/play', {})).data; } catch (e) { toast(e.message, 'bad'); return; }
  S.live = { res, minute: fast ? 90 : 0, shown: fast ? res.events.length : 0, done: !!fast, speed: 1 };
  draw();
  if (!fast) await runLive(); else finishLive();
}
async function runLive() {
  const L = S.live;
  while (L.minute < 90 && S.live === L) {
    await sleep(L.speed > 1 ? 40 : 125);
    L.minute++;
    const evs = L.res.events.filter(e => e.min <= L.minute);
    if (evs.length !== L.shown) {
      const fresh = evs.slice(L.shown); L.shown = evs.length;
      if (fresh.some(e => e.type === 'goal')) { const g = fresh.find(e => e.type === 'goal'); const mine = (g.side === 0) === L.res.isHome; haptic(mine ? 'success' : 'warning'); if (mine) confetti(70); }
    }
    if (L.minute === 45 && L.speed === 1) await sleep(700);
    updateLive();
  }
  finishLive();
}
function finishLive() {
  const L = S.live; if (!L) return;
  L.minute = 90; L.shown = L.res.events.length; L.done = true;
  const r = L.res; const my = r.isHome ? r.hg : r.ag, op = r.isHome ? r.ag : r.hg;
  if (my > op) { confetti(180); haptic('success'); toast(`Перемога! +${r.xp} XP`, 'coins'); }
  else if (my === op) toast(`Нічия. +${r.xp} XP`); else { haptic('error'); toast(`Поразка. +${r.xp} XP`, 'bad'); }
  updateLive();
}
function liveScore(L) {
  let hg = 0, ag = 0;
  L.res.events.forEach(e => { if (e.type === 'goal' && e.min <= L.minute) { e.side === 0 ? hg++ : ag++; } });
  return [hg, ag];
}
function evHTML(e, r) {
  const icon = { goal: '⚽', yellow: '🟨', red: '🟥', injury: '🤕', sub: '🔄', save: '🧤', miss: '💨' }[e.type] || '•';
  let t = '';
  if (e.type === 'goal') t = `<b>ГОЛ! ${esc(e.playerName)}</b>${e.assistName ? `<div class="muted" style="font-size:12px;font-weight:700">пас: ${esc(e.assistName)}</div>` : ''}`;
  else if (e.type === 'sub') t = `<span>${esc(e.inName)} ↔ ${esc(e.outName)}</span>`;
  else if (e.type === 'save') t = `<span>Сейв! ${esc(e.gkName || 'Воротар')} відбиває удар ${esc(e.playerName)}</span>`;
  else if (e.type === 'miss') t = `<span>${esc(e.playerName)} б’є повз</span>`;
  else if (e.type === 'injury') t = `<span>${esc(e.playerName)} травмувався (${e.weeks} т.)</span>`;
  else if (e.type === 'red') t = `<b style="color:var(--red)">${esc(e.playerName)} вилучений!</b>`;
  else t = `<span>${esc(e.playerName)}</span>`;
  return `<div class="ev ${e.type} ${e.side === 1 ? 'away' : ''}"><span class="m">${e.min}'</span><span style="font-size:20px">${icon}</span><div class="grow">${t}</div></div>`;
}
function liveView() {
  const L = S.live, r = L.res; const [hg, ag] = liveScore(L);
  const evs = r.events.filter(e => e.min <= L.minute && (e.type !== 'sub' || L.done)).slice().reverse();
  let html = `<div class="card glow vs m16" style="margin-top:16px"><div class="teams"><div class="t">${crest(r.home, 64)}<span>${esc(r.home.name)}</span></div>
    <div><div class="score" id="score">${hg}:${ag}</div><div class="clock" id="clock">${L.done ? 'Фінал' : `<i></i>${L.minute}'`}</div></div>
    <div class="t">${crest(r.away, 64)}<span>${esc(r.away.name)}</span></div></div>
    <div class="bar green" style="margin-top:16px"><i id="lbar" style="width:${L.minute / 90 * 100}%"></i></div>
    ${!L.done ? `<div class="row" style="justify-content:center;margin-top:12px;gap:8px"><button class="chip spd ${L.speed === 1 ? 'on' : ''}" data-s="1" onclick="S.live.speed=1;updateLive()">×1</button><button class="chip spd ${L.speed > 1 ? 'on' : ''}" data-s="3" onclick="S.live.speed=3;updateLive()">×3</button><button class="chip" onclick="finishLive()">⏭ Пропустити</button></div>` : ''}</div>`;
  if (L.done) {
    html += `<div class="card m16" style="padding:16px;margin-top:12px">${[['Володіння', r.possession + '%', (100 - r.possession) + '%', r.possession, 100 - r.possession],
      ['Удари', r.shots[0], r.shots[1], r.shots[0], r.shots[1]], ['У площину', r.onTarget[0], r.onTarget[1], r.onTarget[0], r.onTarget[1]],
      ['xG', r.xg[0], r.xg[1], r.xg[0], r.xg[1]]].map(([n, a, b, x, y]) => `<div class="muted" style="text-align:center;font-size:12px;font-weight:800;margin-top:6px">${n}</div>
      <div class="cmp" style="margin:4px 0"><b>${a}</b><div class="bars"><i style="width:${x / ((x + y) || 1) * 100}%"></i><i style="flex:1"></i></div><b style="text-align:right">${b}</b></div>`).join('')}
      <div class="muted" style="text-align:center;font-weight:700;font-size:13px;margin-top:8px">👥 ${r.attendance.toLocaleString('uk')} глядачів</div></div>`;
    if (r.motm) html += `<div class="reward m16" style="margin-top:12px"><div class="ico">🌟</div><div class="grow"><b>Гравець матчу</b><div class="muted" style="font-weight:700">${esc(r.motm.name)}</div></div><div class="plus">${r.motm.rating}</div></div>`;
    html += `<div class="pad" style="margin-top:14px">${r.fired ? '<button class="btn danger tap" onclick="show(\'home\')">Тебе звільнено</button>' : r.seasonOver ? '<button class="btn gold tap" onclick="S.live=null;endSeason()">🏁 Підсумки сезону</button>' : '<button class="btn tap" onclick="nextMatch()">Далі →</button>'}</div>`;
  }
  html += `<div class="feed" id="${L.done ? 'feedDone' : 'feed'}" data-n="${evs.length}">${evs.map(e => evHTML(e, r)).join('') || '<div class="empty">Матч почався…</div>'}</div>`;
  if (L.done && r.ratings.length) html += `<div class="section-title">Оцінки гравців</div><div class="card m16 list">${r.ratings.slice(0, 14).map(p => `<div class="item"><span class="ptag">${esc(p.role || POS[p.pos])}</span><b class="grow">${esc(p.name)}${p.goals ? ' ' + '⚽'.repeat(p.goals) : ''}</b><b class="big-num" style="color:${p.rating >= 7.5 ? 'var(--green)' : p.rating >= 6.5 ? 'var(--text)' : 'var(--red)'}">${p.rating}</b></div>`).join('')}</div>`;
  return html;
}
function updateLive() {
  if (!(S.view === 'career' && S.tab === 'match')) return;
  const L = S.live;
  if (!L || L.done || !$('#feed')) { S.keepScroll = true; draw(); return; }
  const [hg, ag] = liveScore(L);
  $('#score').textContent = `${hg}:${ag}`;
  $('#clock').innerHTML = `<i></i>${L.minute}'`;
  $('#lbar').style.width = (L.minute / 90 * 100) + '%';
  const evs = L.res.events.filter(e => e.min <= L.minute && e.type !== 'sub');
  const feed = $('#feed');
  if (+feed.dataset.n !== evs.length) {
    const fresh = evs.slice(+feed.dataset.n || 0);
    if (!(+feed.dataset.n)) feed.innerHTML = '';
    fresh.forEach(e => feed.insertAdjacentHTML('afterbegin', evHTML(e, L.res)));
    feed.dataset.n = evs.length;
  }
  document.querySelectorAll('.spd').forEach(b => b.classList.toggle('on', (+b.dataset.s > 1) === (L.speed > 1)));
}
async function nextMatch() { S.live = null; loading(); S.team = (await call('/api/team')).data; S.match = (await call('/api/match')).data; draw(); }
async function endSeason() {
  loading();
  const s = (await call('/api/season/end', {})).data;
  const good = s.position <= s.target;
  if (good) confetti(220);
  S.team = (await call('/api/team')).data; S.match = (await call('/api/match')).data; draw();
  sheet(`<div style="text-align:center"><div style="font-size:60px">${s.position === 1 ? '🏆' : good ? '🎉' : '📉'}</div>
    <div class="h" style="font-size:24px;font-weight:800">Сезон ${s.season} завершено</div>
    <p class="muted" style="font-weight:700">${s.position}-е місце в ${esc(s.league)} · ціль була топ-${s.target}</p></div>
    <div class="kv"><div><b style="color:var(--green)">${money(s.prize)}</b><span>Призові</span></div><div><b style="color:var(--gold)">+${s.xp}</b><span>Досвід</span></div><div><b>${s.confidence}%</b><span>Довіра</span></div></div>
    ${s.champions.map(c => `<div class="row" style="padding:6px 0"><span class="ptag">${esc(c.league)}</span><b>👑 ${esc(c.club)}</b></div>`).join('')}
    ${s.promoted.length ? `<p style="font-weight:700">🔺 ${s.promoted.map(esc).join(', ')}<br>🔻 ${s.relegated.map(esc).join(', ')}</p>` : ''}
    ${s.youth.length ? `<p style="font-weight:700">🎓 Вихованці: ${s.youth.map(esc).join(', ')}</p>` : ''}
    ${s.retired.length ? `<p class="muted" style="font-weight:700">👋 Завершили кар’єру: ${s.retired.map(esc).join(', ')}</p>` : ''}
    ${s.fired ? '<button class="btn danger" onclick="closeSheet();show(\'home\')">Тебе звільнено</button>' : `<button class="btn tap" onclick="closeSheet()">Новий сезон · ціль топ-${s.newTarget}</button>`}`);
}

/* ---------------- TRANSFER */
function transferTab() {
  const m = S.market;
  const f = [['ALL', 'Усі'], ['GK', 'ВР'], ['DF', 'ЗХ'], ['MF', 'ПЗ'], ['FW', 'НП'], ['FA', '🆓 Вільні'], ['YT', '🌟 Таланти']];
  let html = `<div class="card m16 row between" style="padding:14px 16px;margin-top:14px"><div><b>${m.window ? '🟢 Трансферне вікно відкрите' : '🔴 Вікно закрите'}</b>
    <div class="muted" style="font-size:12px;font-weight:700;margin-top:3px">${m.window ? 'Купуй і продавай' : 'Можна підписати лише вільних агентів'}</div></div><span class="chip">${m.count}/${m.max}</span></div>`;
  if (m.offers.length) html += `<div class="section-title">📨 Пропозиції за твоїх гравців</div><div class="card m16 list">${m.offers.map(o => `<div class="item">${crest(o.club, 40)}<div class="grow"><b>${esc(o.player.name)}</b>
    <div class="muted" style="font-size:12px;font-weight:700">${esc(o.club.name)} · вартість ${money(o.player.value)}</div></div><div class="col" style="gap:6px;align-items:flex-end"><b style="color:var(--green)">${money(o.fee)}</b>
    <div class="row" style="gap:6px"><button class="chip on" onclick="offer(${o.id},true)">✓</button><button class="chip" onclick="offer(${o.id},false)">✕</button></div></div></div>`).join('')}</div>`;
  html += `<div class="search">🔎<input id="q" placeholder="Пошук гравця або клубу" value="${esc(S.mq)}" onkeydown="if(event.key==='Enter'){S.mq=this.value;S.mpage=0;go('transfer')}"></div>
    <div class="chips">${f.map(([k, l]) => `<button class="chip ${S.mfilter === k ? 'on' : ''}" onclick="S.mfilter='${k}';S.mpage=0;go('transfer')">${l}</button>`).join('')}</div>
    <div class="card m16" style="margin-top:8px">${m.items.map(p => `<div class="prow tap" onclick="openPlayer(${p.id})"><div class="pava ${p.pos}">${esc(initials(p.name))}<span class="pp">${esc(p.role || POS[p.pos])}</span></div>
    <div class="grow"><div class="pname ellipsis">${p.flag} ${esc(p.name)}</div><div class="tags"><span>${p.age}р</span>${p.clubInfo ? `<span class="row" style="gap:4px">${crest(p.clubInfo, 18)}${esc(p.clubInfo.name)}</span>` : '<span class="tag fit">вільний</span>'}
    <span class="tag" style="color:var(--pink)">пот. ${p.pot}</span></div></div><div class="ovr"><b class="${sc(p.skill)}">${p.skill}</b><small>${p.clubInfo ? money(p.price) : 'free'}</small></div></div>`).join('') || '<div class="empty">Нікого не знайдено</div>'}</div>
    <div class="row pad" style="justify-content:center;margin-top:12px;gap:12px">${m.page > 0 ? `<button class="chip" onclick="S.mpage--;go('transfer')">◀</button>` : ''}<span class="muted" style="font-weight:800">${m.page + 1}/${m.pages}</span>${m.page < m.pages - 1 ? `<button class="chip" onclick="S.mpage++;go('transfer')">▶</button>` : ''}</div>`;
  return html;
}
async function offer(id, accept) { const j = await call('/api/offer', { id, accept }); S.market = j.data; if (accept) { confetti(80); haptic('success'); } S.team = (await call('/api/team')).data; draw(); }

/* ---------------- TABLE */
function tableTab() {
  const t = S.table;
  let html = `<div class="chips" style="margin-top:14px">${t.leagues.map(l => `<button class="chip ${l.id === t.league ? 'on' : ''}" onclick="S.league=${l.id};go('table')">${l.flag} ${esc(l.short)}</button>`).join('')}</div>
  <div class="card m16" style="padding:6px 8px;margin-top:8px"><div class="h" style="font-weight:800;padding:10px 6px">${esc(t.name)}</div><table class="lt"><tr><th>#</th><th style="text-align:left">Клуб</th><th>І</th><th>РМ</th><th>Форма</th><th>О</th></tr>`;
  const n = t.rows.length;
  t.rows.forEach(r => {
    const cls = r.pos === 1 ? 'top' : (t.zones.up && r.pos <= t.zones.up) ? 'up' : (t.zones.down && r.pos > n - t.zones.down) ? 'down' : '';
    html += `<tr class="${r.me ? 'me' : ''}"><td><span class="pos ${cls}">${r.pos}</span></td><td class="c"><div class="row" style="gap:8px">${crest(r.club, 26)}<span class="ellipsis" style="max-width:120px">${esc(r.club.name)}</span></div></td>
      <td>${r.p}</td><td style="color:${r.gf - r.ga > 0 ? 'var(--green)' : r.gf - r.ga < 0 ? 'var(--red)' : 'inherit'}">${r.gf - r.ga > 0 ? '+' : ''}${r.gf - r.ga}</td><td>${formHTML(r.form.slice(-3))}</td><td><b class="pts">${r.pts}</b></td></tr>`;
  });
  html += `</table></div>`;
  if (t.scorers.length) html += `<div class="section-title">Бомбардири</div><div class="card m16 list">${t.scorers.map((s, i) => `<div class="item"><b class="big-num" style="width:24px;color:${i < 3 ? 'var(--gold)' : 'var(--muted)'}">${i + 1}</b><div class="grow"><b>${s.flag} ${esc(s.name)}</b><div class="muted" style="font-size:12px;font-weight:700">${esc(s.club)} · 🅰️ ${s.assists}</div></div><b class="big-num" style="color:var(--lime)">${s.goals}</b></div>`).join('')}</div>`;
  return html;
}

/* ---------------- CLUB */
function clubTab() {
  const c = S.club, f = c.finances;
  const up = { stadium: ['🏟', 'Стадіон +2 500 місць'], training: ['🏋️', `Тренувальна база · ${c.training}/5`], academy: ['🎓', `Академія · ${c.academy}/5`] };
  let html = `<div class="card glow m16" style="padding:18px;margin-top:14px"><div class="muted" style="font-weight:800;font-size:12px;letter-spacing:.12em">БЮДЖЕТ</div>
    <div class="big-num" style="font-size:34px;color:var(--green);margin-top:4px">${money(c.budget)}</div>
    <div class="grid2" style="margin-top:14px"><div class="opt"><b style="color:var(--red)">-${money(c.wages)}</b><span>Зарплати/тиж</span></div><div class="opt"><b style="color:var(--green)">+${money(c.sponsor)}</b><span>Спонсори/тиж</span></div>
    <div class="opt"><b>${money(f.income)}</b><span>Доходи сезону</span></div><div class="opt"><b>${money(f.transfers_in - f.transfers_out)}</b><span>Баланс трансферів</span></div></div></div>
    <div class="section-title">Квитки</div><div class="card m16 row between" style="padding:14px 16px"><div><b>🏟 ${c.stadium.toLocaleString('uk')} місць</b><div class="muted" style="font-size:12px;font-weight:700">рекомендовано €${c.fairTicket}</div></div>
    <div class="stepper"><button onclick="clubAct({ticket:-1})">−</button><b class="big-num">€${c.ticket}</b><button onclick="clubAct({ticket:1})">+</button></div></div>
    <div class="section-title">Інфраструктура</div><div class="card m16 list">${Object.entries(up).map(([k, [i, l]]) => `<div class="item"><span style="font-size:26px">${i}</span><b class="grow">${l}</b>${c.upgrades[k] ? `<button class="btn small violet tap" onclick="clubAct({upgrade:'${k}'})">${money(c.upgrades[k])}</button>` : '<span class="chip">MAX</span>'}</div>`).join('')}</div>
    <div class="section-title">Правління</div><div class="card m16" style="padding:16px"><div class="row between"><b>Ціль: топ-${c.target}</b><b>${c.confidence}%</b></div><div class="bar ${c.confidence > 60 ? 'green' : ''}" style="margin-top:10px"><i style="width:${c.confidence}%"></i></div></div>`;
  if (c.trophies.length) html += `<div class="section-title">Трофеї</div><div class="card m16 list">${c.trophies.map(t => `<div class="item"><b>${esc(t)}</b></div>`).join('')}</div>`;
  if (c.history.length) html += `<div class="section-title">Історія</div><div class="card m16 list">${c.history.map(h => `<div class="item"><span class="ptag">${h.season}</span><b class="grow">${esc(h.clubName)} · ${esc(h.league)}</b><b>${h.pos} місце</b></div>`).join('')}</div>`;
  html += `<div class="section-title">Новини</div><div class="card m16 list">${c.news.map(n => `<div class="item" style="font-weight:600;font-size:14px">${esc(n)}</div>`).join('') || '<div class="empty">Тиша</div>'}</div>`;
  return html;
}
async function clubAct(d) { haptic(); const j = await call('/api/club', d); S.club = j.data; S.team.budget = S.club.budget; S.keepScroll = true; draw(); }
async function upgrade(kind) { const j = await call('/api/club', { upgrade: kind }); haptic('success'); confetti(60); S.team = (await call('/api/team')).data; S.keepScroll = true; draw(); }

/* ---------------- sheet */
function sheet(html) {
  $('#sheet-root').innerHTML = `<div class="overlay" onclick="closeSheet()"></div><div class="sheet"><div class="grab"></div>${html}</div>`;
}
function closeSheet() { $('#sheet-root').innerHTML = ''; }

/* ---------------- boot */
(async function boot() {
  loading();
  try {
    await loadProfile();
    const p = S.profile;
    if (p.active !== null && p.active !== undefined && new URLSearchParams(location.search).get('screen') === 'career') { await openCareer(); return; }
    draw();
  } catch (e) {
    render(`<div class="empty" style="margin-top:80px"><div style="font-size:48px">⚽</div><b>Не вдалося завантажити гру</b><p>${esc(e.message)}</p>
      <button class="btn small violet" onclick="location.reload()">Спробувати ще</button></div>`);
  }
})();
