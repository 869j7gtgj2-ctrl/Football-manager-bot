/* KICKOFF live 2D match: players run, pass, tackle and shoot on a canvas pitch; a ticker narrates every action. */
(function () {
  const PASS = ['{a} віддає на {b}', '{a} переводить гру на {b}', 'Короткий пас від {a} на {b}', '{a} шукає {b} довгою передачею',
    '{a} розганяє атаку через {b}', '{a} в одне торкання на {b}', 'Діагональ від {a} на {b}', '{a} знаходить {b} між лініями',
    '{a} підключає {b}', 'Розіграш у стіночку: {a} і {b}', '{a} відкриває {b} на фланзі', '{a} пасом під удар на {b}'];
  const DRIBBLE = ['{a} проходить суперника', '{a} йде в обводку', '{a} прискорюється по флангу', '{a} протягує м’яч уперед',
    '{a} крутить захисника', 'Фінт від {a}!', '{a} вривається в центр', '{a} тримає м’яч під тиском'];
  const TACKLE = ['{b} відбирає м’яч у {a}', '{b} перехоплює передачу', 'Підкат від {b}!', '{b} читає пас і забирає м’яч',
    '{b} виграє єдиноборство у {a}', 'Пресинг! {b} накриває {a}', '{a} втрачає м’яч, підбирає {b}'];
  const KEEPER = ['{a} спокійно розігрує від воріт', '{a} вибиває м’яч у поле', '{a} починає атаку з воріт'];
  const BUILD = ['{a} входить у штрафний…', '{a} на ударній позиції!', '{a} замахується…', 'Небезпечно! {a} біля воріт',
    '{a} залишається сам на сам!'];
  const GOAL = ['ГОЛ! {a} розстрілює ворота!', 'ГОЛ! {a} кладе м’яч у дев’ятку!', 'ГОЛ! {a} не залишає шансів воротарю!',
    'ГОЛ! Удар {a} і сітка тремтить!'];
  const SAVE = ['{a} б’є, але {b} рятує!', 'Сейв! {b} витягує удар {a}', '{b} в стрибку забирає удар {a}',
    'Удар {a}… {b} на місці!'];
  const MISS = ['{a} б’є… повз ворота', '{a} пробиває вище воріт', 'Штанга! {a} був так близько', '{a} не влучає у площину'];
  const pick = a => a[Math.random() * a.length | 0];
  const fill = (t, o) => t.replace(/\{(\w)\}/g, (_, k) => o[k] || '');

  function hex2rgb(h) {
    h = (h || '#888').replace('#', ''); if (h.length === 3) h = h.split('').map(c => c + c).join('');
    const n = parseInt(h, 16); return [n >> 16, (n >> 8) & 255, n & 255];
  }
  const lum = c => { const [r, g, b] = hex2rgb(c); return (0.299 * r + 0.587 * g + 0.114 * b) / 255; };
  const dist = (a, b) => { const [r1, g1, b1] = hex2rgb(a), [r2, g2, b2] = hex2rgb(b); return Math.hypot(r1 - r2, g1 - g2, b1 - b2); };

  class Viz {
    constructor(L) {
      this.L = L; this.canvas = document.createElement('canvas'); this.canvas.className = 'viz';
      this.ctx = this.canvas.getContext('2d'); this.ticker = []; this.seen = new Set(); this.flash = null;
      this.acc = 0; this.last = performance.now(); this.script = null; this.load(L.res);
      this.ball = { x: 50, y: 50, fx: 50, fy: 50, tx: 50, ty: 50, t: 1, dur: .4 };
      this.kickoff(0);
      this.loop = this.loop.bind(this); requestAnimationFrame(this.loop);
    }
    load(res) {
      const P = res.pitch; if (!P) return;
      this.extra = P.extra || {};
      const c0 = (P.colors[0] || ['#e3b54a'])[0], a = P.colors[1] || ['#4c8dff', '#ffffff'];
      let c1 = a[0]; if (dist(c0, c1) < 110) c1 = a[1] && dist(c0, a[1]) >= 110 ? a[1] : (lum(c0) > .5 ? '#1d2433' : '#e9ecf2');
      this.colors = [c0, c1];
      const keep = {}; (this.players || []).forEach(p => keep[p.id] = p);
      this.players = [];
      P.sides.forEach((ps, side) => ps.forEach(p => {
        // depth from own goal, compressed so each team starts in its own half; home attacks to the right
        const depth = 4 + (8 + (100 - p.y - 8) * .6) * .92, fy = side === 0 ? p.x : 100 - p.x;
        const bx = side === 0 ? depth : 100 - depth, by = 6 + fy * .88;
        const old = keep[p.id];
        this.players.push({ ...p, side, bx, by, x: old ? old.x : bx, y: old ? old.y : by, tx: bx, ty: by, off: false });
      }));
      // replay subs / reds that already happened (e.g. restoring at half-time)
      res.events.forEach((e, i) => { if (e.min <= this.L.minute && (e.type === 'sub' || e.type === 'red')) { this.apply(e); this.seen.add(i); } });
    }
    apply(e) {
      if (e.type === 'sub') {
        const p = this.players.find(x => x.id === e.out); const n = this.extra[String(e.in)];
        if (p && n) Object.assign(p, { id: n.id, name: n.name, short: n.short, skill: n.skill });
      } else if (e.type === 'red') { const p = this.players.find(x => x.id === e.player); if (p) p.off = true; }
    }
    team(side) { return this.players.filter(p => p.side === side && !p.off); }
    byId(id) { return this.players.find(p => p.id === id && !p.off); }
    kickoff(side) {
      const st = this.team(side).filter(p => !p.gk).sort((a, b) => Math.abs(a.bx - 50) - Math.abs(b.bx - 50))[0];
      this.owner = st || this.team(side)[0]; this.side = side;
      this.players.forEach(p => { p.tx = p.bx; p.ty = p.by; });
      if (this.owner) { this.owner.tx = 50; this.owner.ty = 50; }
      this.moveBall(50, 50, .2);
    }
    say(text, kind) {
      this.ticker.unshift({ text, kind, min: this.L.minute });
      this.ticker.length = Math.min(this.ticker.length, 4);
      this.renderTicker();
    }
    renderTicker() {
      const box = document.getElementById('ticker');
      if (box) box.innerHTML = this.ticker.map((t, i) => `<div class="tk ${t.kind || ''} ${i ? 'old' : 'new'}"><span>${t.min}'</span><b>${window.esc ? esc(t.text) : t.text}</b></div>`).join('');
    }
    moveBall(x, y, dur) { const b = this.ball; b.fx = b.x; b.fy = b.y; b.tx = x; b.ty = y; b.t = 0; b.dur = dur; }
    dir(side) { return side === 0 ? 1 : -1; }
    shape() {
      const bx = this.ball.tx, by = this.ball.ty;
      this.players.forEach(p => {
        if (p.off) return;
        const att = p.side === this.side, d = this.dir(p.side);
        const k = p.gk ? .06 : .33;
        let tx = p.bx + (bx - 50) * k + (p.gk ? 0 : (att ? 11 : -3) * d);
        let ty = p.by + (by - 50) * (p.gk ? .25 : .22) + (Math.random() - .5) * 6;
        if (p === this.owner) { tx = bx; ty = by; }
        p.tx = Math.max(3, Math.min(97, tx)); p.ty = Math.max(5, Math.min(95, ty));
      });
    }
    pendingEvent() {
      const evs = this.L.res.events;
      for (let i = 0; i < evs.length; i++) {
        const e = evs[i];
        if (!this.seen.has(i) && e.min <= this.L.minute + 1 && (this.L.half ? e.min <= 45 : true)) return [i, e];
      }
      return null;
    }
    act() {
      if (this.script) return this.runScript();
      const pe = this.pendingEvent();
      if (pe) {
        const [i, e] = pe; this.seen.add(i);
        const nm = id => { const p = this.byId(id) || this.players.find(x => x.id === id); return p ? p.short : ''; };
        if (['goal', 'save', 'miss'].includes(e.type)) {
          const shooter = this.byId(e.player) || this.team(e.side).filter(p => !p.gk).sort((a, b) => (b.bx - a.bx) * this.dir(e.side))[0];
          const d = this.dir(e.side);
          this.side = e.side; this.owner = shooter;
          const x = 50 + d * (28 + Math.random() * 10), y = 34 + Math.random() * 32;
          this.moveBall(x, y, .45); this.shape();
          this.say(fill(pick(BUILD), { a: shooter.short }), 'hot');
          this.script = { e, shooter }; return;
        }
        if (e.type === 'yellow') this.say(`🟨 ${nm(e.player)} отримує жовту картку`, 'card');
        else if (e.type === 'red') { this.say(`🟥 ${nm(e.player)} вилучений з поля!`, 'red'); this.apply(e); }
        else if (e.type === 'injury') this.say(`🤕 ${nm(e.player)} травмувався`, 'card');
        else if (e.type === 'sub') { const n = this.extra[String(e.in)]; this.say(`🔄 Заміна: ${n ? n.short : ''} замість ${nm(e.out)}`, 'sub'); this.apply(e); }
      }
      this.normal();
    }
    runScript() {
      const { e, shooter } = this.script; this.script = null;
      const d = this.dir(e.side), gx = d > 0 ? 99.5 : .5;
      const gk = this.team(1 - e.side).find(p => p.gk);
      if (e.type === 'goal') {
        this.moveBall(gx + d * 1.2, 44 + Math.random() * 12, .3);
        this.say(fill(pick(GOAL), { a: shooter.short }), 'goal');
        this.flash = { t: 0, side: e.side, name: shooter.short };
        this.afterGoal = 1 - e.side;
      } else if (e.type === 'save') {
        const gy = 42 + Math.random() * 16; this.moveBall(gx - d * 2.5, gy, .3);
        if (gk) { gk.tx = gx - d * 2.5; gk.ty = gy; }
        this.say(fill(pick(SAVE), { a: shooter.short, b: gk ? gk.short : 'воротар' }), 'save');
        this.owner = gk || null; this.side = 1 - e.side;
      } else {
        this.moveBall(gx + d * 2, Math.random() < .5 ? 30 + Math.random() * 8 : 62 + Math.random() * 8, .35);
        this.say(fill(pick(MISS), { a: shooter.short }), 'miss');
        this.owner = gk || null; this.side = 1 - e.side;
      }
    }
    normal() {
      if (this.afterGoal !== undefined) { const s = this.afterGoal; this.afterGoal = undefined; this.kickoff(s); this.say('Розіграш з центру поля', ''); return; }
      let o = this.owner;
      if (!o || o.off || o.side !== this.side) { o = this.owner = this.team(this.side)[0]; if (!o) return; }
      const mates = this.team(this.side).filter(p => p !== o), opps = this.team(1 - this.side);
      const r = Math.random(), d = this.dir(this.side);
      if (o.gk) {
        const t = pick(mates.filter(p => !p.gk)); if (!t) return;
        this.say(fill(pick(KEEPER), { a: o.short }), ''); this.owner = t; this.moveBall(t.x, t.y, .55);
      } else if (r < .2 && opps.length) {
        const thief = opps.filter(p => !p.gk).sort((a, b) => Math.hypot(a.x - o.x, a.y - o.y) - Math.hypot(b.x - o.x, b.y - o.y))[0];
        this.say(fill(pick(TACKLE), { a: o.short, b: thief.short }), 'tackle');
        this.owner = thief; this.side = thief.side; this.moveBall(thief.x, thief.y, .25);
      } else if (r < .36) {
        const nx = Math.max(6, Math.min(94, o.x + d * (6 + Math.random() * 9))), ny = Math.max(8, Math.min(92, o.y + (Math.random() - .5) * 14));
        this.say(fill(pick(DRIBBLE), { a: o.short }), ''); this.moveBall(nx, ny, .7);
      } else {
        const w = mates.filter(p => !p.gk).map(p => ({ p, w: Math.max(.15, 1 + (p.x - o.x) * d / 25) / (1 + Math.hypot(p.x - o.x, p.y - o.y) / 30) }));
        let s = Math.random() * w.reduce((a, b) => a + b.w, 0), t = w[0] && w[0].p;
        for (const it of w) { s -= it.w; if (s <= 0) { t = it.p; break; } }
        if (!t) return;
        this.say(fill(pick(PASS), { a: o.short, b: t.short }), ''); this.owner = t;
        this.moveBall(t.x + d * 3, t.y, .5);
      }
      this.shape();
    }
    loop(now) {
      if (!this.alive) return;
      const dt = Math.min(.05, (now - this.last) / 1000); this.last = now;
      const L = this.L, running = !L.done && !L.ht && L.minute < (L.half ? 45 : 90);
      if (running) {
        this.acc += dt;
        const step = L.speed > 1 ? .2 : .62, pe = this.pendingEvent();
        const behind = pe && pe[1].min < L.minute - 1 && ['goal', 'save', 'miss'].includes(pe[1].type);
        if (this.acc > step || (behind && this.acc > step / 2)) { this.acc = 0; this.act(); }
      }
      const b = this.ball; b.t = Math.min(1, b.t + dt / b.dur);
      const e = 1 - Math.pow(1 - b.t, 2.2); b.x = b.fx + (b.tx - b.fx) * e; b.y = b.fy + (b.ty - b.fy) * e;
      this.players.forEach(p => { const k = Math.min(1, dt * (p === this.owner ? 5 : 1.8)); p.x += (p.tx - p.x) * k; p.y += (p.ty - p.y) * k; });
      if (this.owner && b.t >= 1) { this.owner.tx = Math.max(3, Math.min(97, b.x)); this.owner.ty = Math.max(5, Math.min(95, b.y)); }
      if (this.flash) this.flash.t += dt;
      this.draw();
      requestAnimationFrame(this.loop);
    }
    draw() {
      const cv = this.canvas, par = cv.parentElement; if (!par) return;
      const W = par.clientWidth, H = Math.round(W * .64), dpr = window.devicePixelRatio || 1;
      if (cv.width !== W * dpr || cv.height !== H * dpr) { cv.width = W * dpr; cv.height = H * dpr; cv.style.height = H + 'px'; }
      const c = this.ctx; c.setTransform(dpr, 0, 0, dpr, 0, 0);
      const X = x => x / 100 * W, Y = y => y / 100 * H;
      // turf
      for (let i = 0; i < 12; i++) { c.fillStyle = i % 2 ? '#0e2619' : '#10291c'; c.fillRect(i * W / 12, 0, W / 12 + 1, H); }
      const g = c.createRadialGradient(W / 2, H / 2, W * .1, W / 2, H / 2, W * .75); g.addColorStop(0, 'rgba(255,255,255,.03)'); g.addColorStop(1, 'rgba(0,0,0,.45)');
      c.fillStyle = g; c.fillRect(0, 0, W, H);
      // lines
      c.strokeStyle = 'rgba(235,240,255,.2)'; c.lineWidth = 1.2;
      const m = 4, mt = 6;
      c.strokeRect(X(m), Y(mt), X(100 - 2 * m), Y(100 - 2 * mt));
      c.beginPath(); c.moveTo(X(50), Y(mt)); c.lineTo(X(50), Y(100 - mt)); c.stroke();
      c.beginPath(); c.arc(X(50), Y(50), H * .14, 0, 7); c.stroke();
      c.fillStyle = 'rgba(235,240,255,.3)'; c.beginPath(); c.arc(X(50), Y(50), 2, 0, 7); c.fill();
      [[m, 1], [100 - m, -1]].forEach(([gx, d]) => {
        c.strokeRect(Math.min(X(gx), X(gx + d * 14)), Y(26), X(14), Y(48));
        c.strokeRect(Math.min(X(gx), X(gx + d * 5)), Y(39), X(5), Y(22));
        c.beginPath(); c.arc(X(gx + d * 14), Y(50), H * .09, d > 0 ? -1.2 : 1.94, d > 0 ? 1.2 : 4.34); c.stroke();
        c.fillStyle = 'rgba(235,240,255,.08)'; c.fillRect(Math.min(X(gx), X(gx - d * 1.6)), Y(44), X(1.6), Y(12));
        c.strokeRect(Math.min(X(gx), X(gx - d * 1.6)), Y(44), X(1.6), Y(12));
      });
      // players
      const R = Math.max(9, W / 34);
      this.players.forEach(p => {
        if (p.off) return;
        const x = X(p.x), y = Y(p.y), col = this.colors[p.side];
        c.fillStyle = 'rgba(0,0,0,.35)'; c.beginPath(); c.ellipse(x, y + R * .9, R * .8, R * .3, 0, 0, 7); c.fill();
        if (p === this.owner) { c.shadowColor = '#f5d78e'; c.shadowBlur = 14; c.strokeStyle = '#f5d78e'; c.lineWidth = 2.5; c.beginPath(); c.arc(x, y, R + 3, 0, 7); c.stroke(); c.shadowBlur = 0; }
        const gr = c.createRadialGradient(x - R * .4, y - R * .4, 1, x, y, R); gr.addColorStop(0, shadeC(col, 1.3)); gr.addColorStop(1, shadeC(col, .8));
        c.fillStyle = p.gk ? (p.side ? '#5b4a8a' : '#2d7d5a') : gr; c.beginPath(); c.arc(x, y, R, 0, 7); c.fill();
        c.strokeStyle = 'rgba(0,0,0,.45)'; c.lineWidth = 1.2; c.stroke();
        c.fillStyle = p.gk || lum(col) < .6 ? '#fff' : '#0b0e14'; c.font = `800 ${Math.round(R * .82)}px Inter,sans-serif`; c.textAlign = 'center'; c.textBaseline = 'middle';
        c.fillText(p.skill, x, y + .5);
      });
      // owner name tag
      const o = this.owner;
      if (o && !o.off) {
        const x = X(o.x), y = Y(o.y) - R - 14; c.font = `700 ${Math.round(R * .95)}px Inter,sans-serif`;
        const tw = c.measureText(o.short).width + 14;
        c.fillStyle = 'rgba(8,10,16,.85)'; roundRect(c, x - tw / 2, y - 10, tw, 20, 8); c.fill();
        c.strokeStyle = 'rgba(245,215,142,.5)'; c.lineWidth = 1; c.stroke();
        c.fillStyle = '#f2f3f5'; c.fillText(o.short, x, y + .5);
      }
      // ball
      let bx = X(this.ball.x), by = Y(this.ball.y);
      if (o && !o.off && this.ball.t >= 1 && Math.hypot(X(o.x) - bx, Y(o.y) - by) < R * 1.2) { bx = X(o.x) + R * .95 * this.dir(o.side); by = Y(o.y) + R * .55; }
      const arc = Math.sin(Math.PI * this.ball.t) * (this.ball.dur > .45 ? 5 : 2);
      c.fillStyle = 'rgba(0,0,0,.4)'; c.beginPath(); c.ellipse(bx, by + 3, 3.6, 1.6, 0, 0, 7); c.fill();
      c.shadowColor = '#fff'; c.shadowBlur = 8; c.fillStyle = '#fff'; c.beginPath(); c.arc(bx, by - arc, 3.6, 0, 7); c.fill(); c.shadowBlur = 0;
      // goal flash
      const f = this.flash;
      if (f && f.t < 2.2) {
        const a = f.t < .2 ? f.t / .2 : f.t > 1.6 ? Math.max(0, (2.2 - f.t) / .6) : 1;
        c.fillStyle = `rgba(5,7,12,${.55 * a})`; c.fillRect(0, 0, W, H);
        c.globalAlpha = a; c.textAlign = 'center';
        c.font = `700 ${Math.round(W / 6.5)}px Oswald,Inter,sans-serif`; c.shadowColor = this.colors[f.side]; c.shadowBlur = 28;
        c.fillStyle = '#f5d78e'; c.fillText('ГОЛ!', W / 2, H / 2 - 6 + (1 - Math.min(1, f.t * 4)) * 20); c.shadowBlur = 0;
        c.font = `700 ${Math.round(W / 22)}px Inter,sans-serif`; c.fillStyle = '#f2f3f5'; c.fillText(f.name, W / 2, H / 2 + W / 12);
        c.globalAlpha = 1;
      }
    }
  }
  function shadeC(hex, f) { const [r, g, b] = hex2rgb(hex); const k = v => Math.round(Math.min(255, Math.max(0, v * f))); return `rgb(${k(r)},${k(g)},${k(b)})`; }
  function roundRect(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }

  window.MatchViz = {
    start(L) { this.stop(); if (!L.res.pitch) return; const v = new Viz(L); v.alive = true; window.__viz = v; this.mount(); },
    stop() { if (window.__viz) window.__viz.alive = false; window.__viz = null; },
    reload(L) { const v = window.__viz; if (!v) return this.start(L); v.L = L; v.load(L.res); v.seen = new Set(L.res.events.map((e, i) => e.min <= L.minute ? i : -1).filter(i => i >= 0)); },
    mount() {
      const v = window.__viz, box = document.getElementById('vizbox'); if (!v || !box) return;
      if (v.canvas.parentElement !== box) box.appendChild(v.canvas);
      v.renderTicker();
    },
  };
})();
