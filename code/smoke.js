const { JSDOM } = require("jsdom");
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const errors = [];
const dom = new JSDOM("<!doctype html><html><head></head><body>" + html + "</body></html>", {
  runScripts: "dangerously", pretendToBeVisual: true,
  beforeParse(w) { w.addEventListener("error", e => errors.push(e.message)); }
});
const w = dom.window, d = w.document, $ = id => d.getElementById(id);
const click = el => el && el.dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
const films = () => d.querySelectorAll("article.film").length;
const log = (k, v) => console.log(k.padEnd(28), v);
setTimeout(() => {
  log("films (default)", films() + " | " + $("count").textContent);
  log("first film", d.querySelector("article.film h2")?.textContent);
  click(d.querySelector('#src [data-s="im"]')); log("IMDb source", films() + " first: " + d.querySelector("article.film h2")?.textContent);
  click(d.querySelector('#src [data-s="lb"]')); log("Letterboxd", films() + " stub: " + d.querySelector(".stub .n")?.textContent);
  click(d.querySelector('#src [data-s="av"]')); log("Media", films() + " badges split: " + d.querySelectorAll(".badge.split").length);
  click(d.querySelector('#days [data-d="all"]')); log("whole week", films());
  click($("vose")); log("VOSE only", films()); click($("vose"));
  click($("filt")); log("filters open", !$("moreFilters").hidden);
  const g = $("fGenre"); log("genres", g.options.length - 1);
  g.value = g.options[1]?.value; g.dispatchEvent(new w.Event("change")); log("genre " + g.value, films()); g.value = ""; g.dispatchEvent(new w.Event("change"));
  const n = $("fNear"); n.value = "Sol"; n.dispatchEvent(new w.Event("change")); log("near Sol 2km", films() + " dist: " + d.querySelector(".dist")?.textContent);
  n.value = ""; n.dispatchEvent(new w.Event("change"));
  click($("fWomen")); log("by women", films()); click($("fWomen"));
  click($("fQueer")); log("LGTBIQ+", films()); click($("fQueer"));
  click($("fClassic")); log("classics", films()); click($("fClassic"));
  const u = $("fUntil"); u.value = "22:00"; u.dispatchEvent(new w.Event("change")); log("ends before 22:00", films()); click($("fReset"));
  click(d.querySelector("[data-fav]")); log("fav marked", $("favs").textContent);
  click($("favs")); log("favs only", films()); click($("favs"));
  click(d.querySelector("[data-cine]")); log("cinema panel", $("panelTitle").textContent.slice(0, 60));
  log("  map svg", !!d.querySelector("#panelBody svg") + " paths " + d.querySelectorAll("#panelBody svg path").length);
  log("  films there", d.querySelectorAll(".pfilm").length);
  click(d.querySelector('[data-z="1"]')); log("  zoom out ok", !!d.querySelector("#panelBody svg"));
  click($("close")); log("panel closed", $("panel").hidden);
  click($("openDir")); log("directory rows", d.querySelectorAll(".dir .row").length);
  click($("openDisc"));
  $("dName").value = "Carnet Joven"; $("dScope").value = "all"; $("dKind").value = "price"; $("dValue").value = "5";
  $("discForm").dispatchEvent(new w.Event("submit", { cancelable: true, bubbles: true }));
  log("discounts saved", d.querySelectorAll(".disc").length + " | " + $("openDisc").textContent);
  click($("close"));
  log("deal prices shown", d.querySelectorAll(".price .deal").length);
  click(d.querySelector(".more")); log("expand cinemas", "ok");
  $("q").value = "verdi"; $("q").dispatchEvent(new w.Event("input")); log("search verdi", films());
  log("festival rows", d.querySelectorAll(".ev").length);
  log("ERRORS", errors.length ? errors : "none");
}, 300);
