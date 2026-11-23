// colbert site: live numbers from the ledger, release details from GitHub, the download for
// this computer, and the two small interactive figures. The page works without any of it.
// Everything inserted from the network goes in as text, never as HTML.
"use strict";

const LEDGER = "https://colbert-ledger-214187368360.us-central1.run.app/v1/status";
const RELEASE = "https://api.github.com/repos/CadeRyan/colbert/releases/latest";
const fmt = (x) => (typeof x === "number" ? x.toLocaleString("en-US") : "–");
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));

// ------------------------------------------------------------------ live progress
async function loadLedger() {
  const state = $("#live-state"), dot = $(".live-src .dot");
  try {
    const r = await fetch(LEDGER, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    const s = await r.json();
    const c = s.counts || {};
    const settled = (c.done || 0) + (c.verified || 0) + (c.factored || 0);
    const values = {
      candidates: fmt(s.candidates), active_assignments: fmt(s.active_assignments), settled: fmt(settled),
      tests_last_24h: fmt(s.tests_last_24h), factors: fmt(s.factors || 0),
      tested_through_n: s.tested_through_n ? fmt(s.tested_through_n) : "–",
      range: s.range ? `n = ${fmt(s.range[0])} to ${fmt(s.range[1])}` : null,
    };
    for (const el of $$("[data-live]")) {
      const v = values[el.dataset.live];
      if (v != null) el.textContent = v;
    }
    const fill = $("#progress-fill");
    if (fill && s.candidates) fill.style.width = `${Math.max(0.2, (100 * settled) / s.candidates).toFixed(2)}%`;

    const owners = $("#top-owners");
    if (owners) {
      owners.replaceChildren();
      if ((s.top_owners || []).length) {
        for (const o of s.top_owners) {
          const li = document.createElement("li");
          const name = document.createElement("span"); name.textContent = o.name;
          const n = document.createElement("span"); n.className = "n"; n.textContent = `${fmt(o.results)} result${o.results === 1 ? "" : "s"}`;
          li.append(name, n); owners.append(li);
        }
      } else {
        const li = document.createElement("li"); li.className = "empty";
        li.textContent = s.active_assignments ? "No results yet. The first tests are running now." : "No results yet.";
        owners.append(li);
      }
    }
    const primes = $("#primes");
    if (primes) {
      primes.replaceChildren();
      if ((s.primes || []).length) {
        for (const p of s.primes) {
          const li = document.createElement("li");
          const what = document.createElement("span"); what.className = "n";
          what.textContent = `${p.k}·2^${fmt(p.n)}+1`;
          const st = document.createElement("span");
          st.textContent = p.status === "verified" ? "verified prime" : p.status === "refuted" ? "refuted" : "awaiting a double check";
          li.append(what, st); primes.append(li);
        }
      } else {
        const li = document.createElement("li"); li.className = "empty"; li.textContent = "None yet."; primes.append(li);
      }
    }
    if (state) state.textContent = s.paused ? "The project is paused" : "Live from the project ledger";
    if (dot) dot.classList.toggle("on", !s.paused);
  } catch (e) {
    if (state) state.textContent = "Live numbers unavailable right now";
    if (dot) dot.classList.remove("on");
  }
}

// ------------------------------------------------------------------ downloads
function detectOS() {
  const ua = navigator.userAgent || "";
  const touchMac = /Macintosh/.test(ua) && navigator.maxTouchPoints > 1;     // iPad asking for the desktop site
  if (/iPhone|iPad|Android/.test(ua) || touchMac) return "mobile";
  if (/Windows/.test(ua)) return "windows";
  if (/Macintosh|Mac OS X/.test(ua)) return "mac";
  if (/Linux|X11/.test(ua)) return "linux";
  return "";
}

function markDownloads() {
  const os = detectOS(), names = { mac: "Mac", windows: "Windows", linux: "Linux" };
  const hero = $("#hero-download"), note = $("#hero-note");
  if (os === "mobile") {
    if (note) note.textContent = "colbert runs on Mac, Windows and Linux computers. Open this page on one to download it.";
    return;
  }
  const card = $(`.dl[data-os="${os}"]`);
  if (!card) return;
  card.classList.add("mine");
  card.parentElement.prepend(card);
  if (hero) hero.textContent = `Download for ${names[os]}`;
}

async function loadRelease() {
  try {
    const r = await fetch(RELEASE, { headers: { Accept: "application/vnd.github+json" } });
    if (!r.ok) return;
    const rel = await r.json();
    for (const a of rel.assets || []) {
      const el = $(`[data-size="${CSS.escape(a.name)}"]`);
      if (el) el.textContent = `${Math.round(a.size / 1e6)} MB`;
    }
    const line = $("#release-line");
    if (line && rel.tag_name) {
      const when = rel.published_at ? new Date(rel.published_at).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }) : "";
      const lead = document.createElement("strong");
      lead.textContent = `Version ${rel.tag_name.replace(/^v/, "")}${when ? `, ${when}` : ""}. `;
      line.prepend(lead);
    }
  } catch (e) { /* the static links still work */ }
}

// ------------------------------------------------------------------ covering strip
const SUP = { 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const sup = (n) => String(n).split("").map((d) => SUP[d]).join("");

function covering() {
  const fig = $("#covering");
  if (!fig || typeof BigInt === "undefined") return;
  const cells = $$(".cell", fig), keys = $$(".key", fig), tip = $("#covering-tip");
  const term = (n) => 78557n * 2n ** BigInt(n) + 1n;
  const divides = (p, n) => term(n) % BigInt(p) === 0n;
  let pinned = null;

  const show = (p) => {
    for (const c of cells) {
      const on = p != null && divides(p, c.dataset.n);
      c.classList.toggle("hl", on);
      c.classList.toggle("dim", p != null && !on);
    }
    for (const k of keys) k.setAttribute("aria-pressed", String(k.dataset.p === String(p)));
    if (tip && p != null) {
      const count = cells.filter((c) => divides(p, c.dataset.n)).length;
      tip.textContent = `${p} divides ${count} of these 36 terms, and the same ones in every later block of 36.`;
    }
  };
  for (const k of keys) {
    k.addEventListener("mouseenter", () => { if (pinned == null) show(k.dataset.p); });
    k.addEventListener("mouseleave", () => { if (pinned == null) show(null); });
    k.addEventListener("focus", () => { if (pinned == null) show(k.dataset.p); });
    k.addEventListener("blur", () => { if (pinned == null) show(null); });
    k.addEventListener("click", () => { pinned = pinned === k.dataset.p ? null : k.dataset.p; show(pinned); });
  }
  for (const c of cells) {
    c.tabIndex = 0;
    const describe = () => {
      const n = Number(c.dataset.n), p = BigInt(c.dataset.p), t = term(n);
      cells.forEach((x) => x.classList.toggle("focus", x === c));
      if (tip) tip.textContent = `n = ${n}:  78557·2${sup(n)}+1 = ${t.toLocaleString("en-US")} = ${c.dataset.p} × ${(t / p).toLocaleString("en-US")}`;
    };
    c.addEventListener("mouseenter", describe);
    c.addEventListener("focus", describe);
    c.addEventListener("click", describe);
  }
}

// ------------------------------------------------------------------ bar chart
function barTips() {
  const tip = $("#chart-tip");
  if (!tip) return;
  for (const row of $$(".bar-row")) {
    const on = () => { tip.textContent = row.dataset.tip; };
    row.addEventListener("mouseenter", on);
    row.addEventListener("focus", on);
    row.addEventListener("mouseleave", () => { tip.textContent = ""; });
    row.addEventListener("blur", () => { tip.textContent = ""; });
  }
}

markDownloads();
covering();
barTips();
loadLedger();
loadRelease();
setInterval(loadLedger, 60000);
