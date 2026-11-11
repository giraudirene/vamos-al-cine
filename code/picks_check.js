process.on("unhandledRejection", e => console.log("NODE REJ", String(e && e.stack || e).split("\n").slice(0, 4).join(" | ")));
// Irene's picks: anon sees badge/strip/filter but no editor; admin can add/edit/remove (mock Supabase)
const { JSDOM } = require("jsdom");
const fs = require("fs");
const [, , htmlPath, mode] = process.argv;           // mode: anon | admin | missing
let html = fs.readFileSync(htmlPath, "utf8");
html = html.replace(/<script type="application\/json" id="config">[\s\S]*?<\/script>/, '<script type="application/json" id="config">{"supabase_url":"https://x.supabase.co","supabase_anon_key":"k"}</script>');
const data = JSON.parse(html.match(/<script type="application\/json" id="data"[^>]*>([\s\S]*?)<\/script>/)[1].replace(/<\\\//g, "</"));
const errors = [], db = { picks: [], reviews: [], replies: [] };
const shown = data.films.find((f, i) => f.imdb && data.shows.some(x => x[0] === i && x[2] === data.today)), up = data.upcoming.find(u => u.imdb && u.date >= data.today);
db.picks.push({ film_key: shown.imdb, film_title: shown.t, film_year: shown.y, imdb: shown.imdb, note: "Imprescindible en VOSE", updated_at: "2026-11-10" });
function q(table) {
  const st = { table, op: "select", filters: [] };
  const api = {
    select() { return api; }, order() { return api; }, limit() { return api; },
    eq(k, v) { st.filters.push([k, v]); return api; },
    maybeSingle() { st.single = true; return api; },
    upsert(row) { st.op = "upsert"; st.row = row; return api; },
    delete() { st.op = "delete"; return api; },
    insert(row) { st.op = "insert"; st.row = row; return api; },
    then(res, rej) {
      if (table === "picks" && mode === "missing") return Promise.resolve({ data: null, error: { message: "relation does not exist" } }).then(res, rej);
      if (table === "profiles") return Promise.resolve({ data: { id: "u1", display_name: "Irene", is_admin: mode === "admin" }, error: null }).then(res, rej);
      if (table === "user_state") return Promise.resolve({ data: null, error: null }).then(res, rej);
      const rows = db[table] || [];
      if (st.op === "upsert") { const i = rows.findIndex(r => r.film_key === st.row.film_key); i >= 0 ? rows[i] = st.row : rows.push(st.row); return Promise.resolve({ error: null }).then(res, rej); }
      if (st.op === "delete") { db[table] = rows.filter(r => !st.filters.every(([k, v]) => r[k] === v)); return Promise.resolve({ error: null }).then(res, rej); }
      return Promise.resolve({ data: rows.slice(), error: null }).then(res, rej);
    } };
  return api;
}
const dom = new JSDOM("<!doctype html><html><head></head><body>" + html + "</body></html>", {
  runScripts: "dangerously", pretendToBeVisual: true,
  beforeParse(w) {
    w.Element.prototype.scrollIntoView = function () {}; w.addEventListener("error", e => errors.push(e.message)); w.addEventListener("unhandledrejection", e => errors.push("rej: " + (e.reason && e.reason.stack || e.reason)));
    w.supabase = { createClient: () => ({ from: q, rpc: async () => ({}),
      auth: { onAuthStateChange(cb) { setTimeout(() => { try { cb("SIGNED_IN", mode === "anon" ? null : { user: { id: "u1", email: "x@y" } }); } catch (e) { console.log("CB ERR", e.stack); } }, 0); return { data: { subscription: { unsubscribe() {} } } }; } } }) };
  }
});
const w = dom.window, d = w.document, $ = id => d.getElementById(id);
const click = el => el && el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const log = (k, v) => console.log(k.padEnd(30), v);
const wait = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  await wait(+process.env.W || 400);
  log("mode", mode); log("acct", $("acct").textContent + " hidden " + $("acct").hidden); log("errs so far", errors.join(" / ").slice(0,600));
  log("strip visible", !$("picks").hidden + " | " + $("picks").textContent.replace(/\s+/g, " ").slice(0, 90));
  click(d.querySelector('#days [data-d="all"]')); log("badges on cards", d.querySelectorAll("article.film .badge.pick").length);
  log("note on card", d.querySelector("article.film .picknote")?.textContent);
  log("filter pill hidden", $("fPicks").hidden);
  click($("fPicks")); log("only picks -> films", d.querySelectorAll("article.film").length); click($("fPicks"));
  log("upcoming admin buttons", d.querySelectorAll("[data-upick]").length);
  const idx = data.films.indexOf(shown);
  click(d.querySelector(`.pk[data-film="${idx}"]`)); log("strip -> film panel", $("panelTitle").textContent.slice(0, 50));
  log("editor in panel", !!$("pickForm"));
  if (mode === "admin") {
    $("pickText").value = "Nueva nota";
    $("pickForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true })); await wait(50);
    log("after edit", db.picks.map(p => p.film_key + "=" + p.note).join(" ; ") + " | msg " + d.querySelector("#panelBody .okmsg")?.textContent);
    click($("pickDel")); await wait(50);
    log("after remove", db.picks.length + " picks | strip hidden " + $("picks").hidden + " | msg " + d.querySelector("#panelBody .okmsg")?.textContent);
    click($("close"));
    click(d.querySelector(`[data-upick="${up.uidx ?? data.upcoming.indexOf(up)}"]`)); log("upcoming editor", $("panelTitle").textContent.slice(0, 50) + " form " + !!$("pickForm"));
    $("pickText").value = "Ojo a esta"; $("pickForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true })); await wait(50);
    log("upcoming picked", JSON.stringify(db.picks.map(p => [p.film_key, p.film_title, p.ec])));
    click($("close"));
    log("strip now", $("picks").textContent.replace(/\s+/g, " ").slice(0, 90));
    log("badge in Próximamente", d.querySelectorAll("#soonSec .badge.pick").length);
    click(d.querySelector(".pk[data-pkup]")); log("strip upcoming click ok", true);
  }
  if (mode === "missing") log("no crash, strip hidden", $("picks").hidden);
  for (const L of ["en", "fr", "es"]) { click(d.querySelector(`[data-lang="${L}"]`)); log("lang " + L, $("picks").querySelector("h3")?.textContent + " / " + $("fPicks").textContent); }
  log("ERRORS", errors.length ? errors : "none");
})();
