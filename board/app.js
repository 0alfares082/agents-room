// Agents board client: polls /api/board every 2 s, keeps cards keyed by session id,
// ticks every "ago" each second, and says plainly when the feed stops.
(() => {
  "use strict";

  const POLL_MS = 2000;
  const STALE_MS = 8000;
  // ?show=1: show mode for recordings; the server swaps client names and drops private text
  const SHOW = new URLSearchParams(location.search).get("show") === "1" ? "&show=1" : "";

  const $ = (id) => document.getElementById(id);
  const lists = { waiting: $("list-waiting"), working: $("list-working"), rest: $("list-rest") };
  const nodes = new Map(); // id -> { el, sig, zone, action }
  let lastOk = 0;
  let skew = 0; // server clock minus browser clock, ms
  let firstPaint = true;

  const kuwaitClock = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kuwait", hour: "2-digit", minute: "2-digit" });

  function ago(iso) {
    if (!iso) return "";
    const s = Math.max(0, Math.round((Date.now() + skew - Date.parse(iso)) / 1000));
    if (s < 10) return "الحين";
    if (s < 60) return `قبل ${s} ث`;
    const m = Math.round(s / 60);
    if (m < 60) return `قبل ${m} د`;
    const h = Math.round(m / 60);
    return h === 1 ? "قبل ساعة" : `قبل ${h} س`;
  }

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) {
      n.textContent = text;
      n.dir = "auto"; // English replies sit left-to-right inside the Arabic page
    }
    return n;
  }

  function agoEl(iso, cls = "ago") {
    const t = el("time", cls, ago(iso));
    t.dataset.ts = iso || "";
    t.dateTime = iso || "";
    return t;
  }

  function nameEl(a, cls) {
    const n = el(a.link ? "a" : "span", cls, a.title);
    n.dir = "auto";
    if (a.link) {
      n.href = a.link; // claude:// opens that session in the Claude app
      n.title = "افتح القعدة";
    }
    return n;
  }

  function prChips(a, into) {
    for (const pr of a.prs || []) {
      const link = el("a", "pr", `#${pr.split("/").pop()}`);
      link.href = `https://${pr}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.dir = "ltr";
      into.append(link);
    }
  }

  function checksEl(led) {
    if (!led || !led.total) return null;
    const box = el("span", "checks");
    const bar = el("span", "bar");
    bar.setAttribute("aria-hidden", "true");
    const ok = el("i", "ok");
    ok.style.width = `${(100 * led.passed) / led.total}%`;
    const bad = el("i", "bad");
    bad.style.width = `${(100 * led.failed) / led.total}%`;
    bar.append(ok, bad);
    const label = el("span", null, `الفحوص ${led.passed} من ${led.total}`);
    box.append(bar, label);
    return box;
  }

  function waitingNode(a) {
    const row = el("article", "wait");
    const who = el("div", "wait-who");
    who.append(nameEl(a, "wait-name"));
    const meta = el("div", "wait-meta");
    meta.append(el("span", "tag", a.project), agoEl(a.latestTs || a.lastTs));
    prChips(a, meta);
    who.append(meta);
    const body = el("div", "wait-body");
    const items = (a.waiting || []).slice();
    const q = items.length ? items.shift() : a.latest;
    body.append(el("p", "wait-q", q));
    if (items.length) {
      const ul = el("ul", "wait-items");
      for (const it of items) ul.append(el("li", null, it));
      body.append(ul);
    }
    row.append(who, body);
    return row;
  }

  function workingNode(a) {
    const card = el("article", "card");
    const head = el("div", "card-head");
    const titleBox = el("div");
    titleBox.append(nameEl(a, "card-name"));
    const sub = el("div", "card-sub");
    sub.append(el("span", "tag", a.project));
    if (a.startedTs) sub.append(el("span", null, "بدا"), agoEl(a.startedTs, "ago"));
    titleBox.append(sub);
    head.append(titleBox, agoEl(a.actionTs || a.lastTs));
    card.append(head);

    const now = el("div", "now");
    now.append(el("span", "now-label", "الحين"), el("span", "now-text", a.action || a.latest || "يفكر…"));
    if (a.recent && a.recent.length) now.append(el("span", "trail", `قبلها: ${a.recent.join(" · ")}`));
    card.append(now);

    if (a.done && a.done.length) {
      const f = el("div", "field");
      f.append(el("span", "field-label", "خلص"));
      const ul = el("ul", "done-list");
      for (const d of a.done.slice(0, 4)) ul.append(el("li", null, d));
      f.append(ul);
      card.append(f);
    }
    if (a.latest) {
      const f = el("div", "field");
      f.append(el("span", "field-label", "اخر كلامه"), el("p", "latest", a.latest));
      card.append(f);
    }
    if (a.ask) card.append(el("p", "ask", `طلبك: ${a.ask}`));

    const foot = el("div", "card-foot");
    const checks = checksEl(a.ledger);
    if (checks) foot.append(checks);
    prChips(a, foot);
    if (foot.childNodes.length) card.append(foot);
    return card;
  }

  function restNode(a) {
    const li = el("li", `row${a.status === "done" ? " is-done" : ""}`);
    li.append(el("span", "dot"));
    const name = el("span", "row-name");
    name.append(nameEl(a, "row-link"), el("span", "tag", a.project));
    li.append(name);
    const latest = el("span", "row-latest");
    if (a.status === "done") latest.append(el("span", "row-state", "خلص دوره"));
    const line = el("bdi", null, a.latest || a.action || "");
    latest.append(line);
    li.append(latest, agoEl(a.lastTs));
    return li;
  }

  const ZONE = { waiting: "waiting", working: "working", done: "rest", quiet: "rest" };
  const BUILD = { waiting: waitingNode, working: workingNode, rest: restNode };

  function signature(a) {
    const { ageS, ...rest } = a;
    return JSON.stringify(rest);
  }

  function render(data) {
    const counts = data.counts || {};
    $("c-waiting").textContent = counts.waiting || 0;
    $("c-working").textContent = counts.working || 0;
    $("c-rest").textContent = (counts.done || 0) + (counts.quiet || 0);

    const seen = new Set();
    const order = { waiting: [], working: [], rest: [] };
    for (const a of data.agents || []) {
      const zone = ZONE[a.status] || "rest";
      seen.add(a.id);
      const sig = signature(a);
      let rec = nodes.get(a.id);
      if (!rec || rec.zone !== zone || rec.sig !== sig) {
        const node = BUILD[zone](a);
        if (!firstPaint && (!rec || rec.zone !== zone)) node.classList.add("enter");
        if (rec && rec.zone === zone && zone === "working" && rec.action !== a.action) {
          const now = node.querySelector(".now");
          if (now) {
            now.classList.add("flash");
            requestAnimationFrame(() => requestAnimationFrame(() => now.classList.remove("flash")));
          }
          node.classList.add("is-fresh");
          setTimeout(() => node.classList.remove("is-fresh"), 1500);
        }
        if (rec) rec.el.replaceWith(node);
        rec = { el: node, sig, zone, action: a.action };
        nodes.set(a.id, rec);
      }
      order[zone].push(rec.el);
    }
    for (const [id, rec] of nodes) {
      if (!seen.has(id)) { rec.el.remove(); nodes.delete(id); }
    }
    for (const zone of Object.keys(order)) {
      const list = lists[zone];
      order[zone].forEach((node, i) => {
        if (list.children[i] !== node) list.insertBefore(node, list.children[i] || null);
      });
    }
    $("zone-waiting").hidden = order.waiting.length === 0;
    $("empty-working").hidden = order.working.length > 0;
    $("empty-rest").hidden = order.rest.length > 0;
    firstPaint = false;
  }

  function tick() {
    for (const t of document.querySelectorAll("time[data-ts]")) {
      const v = ago(t.dataset.ts);
      if (t.textContent !== v) t.textContent = v;
    }
    $("clock").textContent = kuwaitClock.format(new Date(Date.now() + skew));
    const live = $("live");
    const since = Date.now() - lastOk;
    const stale = !lastOk || since > STALE_MS;
    live.classList.toggle("is-stale", stale && lastOk > 0);
    if (!lastOk) {
      $("live-text").textContent = "يتصل…";
    } else if (stale) {
      $("live-text").textContent = "الاتصال واقف";
    } else {
      const s = Math.round(since / 1000);
      $("live-text").textContent = s < 2 ? "مباشر، تحدث الحين" : `مباشر، تحدث قبل ${s} ث`;
    }
    $("stale").hidden = !(stale && lastOk > 0);
    if (stale && lastOk) $("stale-age").textContent = ago(new Date(lastOk + skew).toISOString());
  }

  let roomText = "";
  async function pollRoom() {
    try {
      const w = Math.max(360, Math.min(1600, Math.round($("room").clientWidth || 960)));
      const res = await fetch(`/api/room.svg?w=${w}&links=1${SHOW}`, { cache: "no-store" });
      if (!res.ok) return;
      const text = await res.text();
      if (text !== roomText) {
        roomText = text;
        $("room").innerHTML = text; // our own server's SVG; every title in it is escaped there
      }
    } catch (err) {
      // the stale banner covers a dead feed
    }
  }

  async function poll() {
    try {
      const res = await fetch(`/api/board?t=0${SHOW}`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      if (data.generatedAt) skew = Date.parse(data.generatedAt) - Date.now();
      lastOk = Date.now();
      render(data);
      await pollRoom();
      document.documentElement.dataset.ready = "1";
    } catch (err) {
      // keep the last picture; tick() marks it stale after STALE_MS
    } finally {
      setTimeout(poll, POLL_MS);
    }
  }

  setInterval(tick, 1000);
  tick();
  poll();
})();
