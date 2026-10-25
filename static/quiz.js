// The quiz: vote on real bills, then rank every current member of Congress by how often they
// voted the same way. Everything runs in the browser; answers live only in the page address
// (after the #), so they are never sent anywhere unless the visitor shares the link.
(function () {
  "use strict";
  var root = document.getElementById("quiz");
  if (!root) return;
  var base = root.getAttribute("data-base");
  var MIN = +root.getAttribute("data-min") || 5;
  var MIN_SHARED = +root.getAttribute("data-minshared") || 5;
  var site = root.getAttribute("data-site") || location.href.split("#")[0];
  var quiz, matrix, items = [], answers = {}, pos = 0, chamber = "House", stateSel = "", ballotOnly = false;

  function track(name) {
    try { if (window.goatcounter && window.goatcounter.count) window.goatcounter.count({ path: name, title: name, event: true }); } catch (e) {}
  }
  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    for (var k in attrs || {}) e.setAttribute(k, attrs[k]);
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function pct(x) { return Math.round(x * 100) + "%"; }

  // ---------------------------------------------------------------- answers <-> address
  function readHash() {
    var m = /(?:^|[#&])a=([^&]*)/.exec(location.hash);
    var out = {};
    if (m) decodeURIComponent(m[1]).split(",").forEach(function (p) {
      var kv = p.split(":");
      if (kv.length === 2 && /^[yns]$/.test(kv[1])) out[kv[0]] = kv[1];
    });
    return out;
  }
  function hashFor(ans) {
    var parts = [];
    items.forEach(function (it) { if (ans[it.id]) parts.push(it.id + ":" + ans[it.id]); });
    return parts.length ? "#a=" + parts.join(",") : "";
  }
  function writeHash() {
    var h = hashFor(answers);
    try { history.replaceState(null, "", h || location.pathname + location.search); } catch (e) { location.hash = h; }
  }
  function answeredCount() {
    return items.filter(function (it) { return answers[it.id] === "y" || answers[it.id] === "n"; }).length;
  }

  // ---------------------------------------------------------------- one question at a time
  var card = root.querySelector(".q-card");
  var progress = root.querySelector(".q-progress");
  var nav = root.querySelector(".q-nav");

  function voteLine(it) {
    return Object.keys(it.votes).map(function (ch) {
      var v = it.votes[ch];
      var parties = Object.keys(v.party).map(function (p) { return p + " " + v.party[p][0] + "–" + v.party[p][1]; }).join(", ");
      return "<div><strong>" + esc(ch) + "</strong>: " + esc(v.result) + " " + v.yea + "–" + v.nay +
        " on " + esc(v.date_text) + " (" + esc(parties) + "). <a href=\"" + esc(v.url) + "\" rel=\"noopener\" data-out=\"clerk\">Official record</a></div>";
    }).join("");
  }

  function renderQuestion() {
    var it = items[pos];
    var a = answers[it.id];
    var n = answeredCount();
    progress.innerHTML = "<span>Bill " + (pos + 1) + " of " + items.length + "</span><span class=\"track\"><i style=\"width:" +
      ((pos + 1) / items.length * 100).toFixed(1) + "%\"></i></span><span>" + n + " answered</span>";
    var chambers = Object.keys(it.votes).map(function (ch) { return ch + " " + it.votes[ch].date_text; }).join(" · ");
    card.innerHTML =
      "<div class=\"q-meta\">" + esc(it.label) + " · " + esc(it.policy_area) + " · final vote" + (Object.keys(it.votes).length > 1 ? "s" : "") + ": " + esc(chambers) + "</div>" +
      "<h2 class=\"q-title\">" + esc(it.title) + "</h2>" +
      "<p class=\"q-headline\">" + esc(it.headline) + "</p>" +
      "<details><summary>Full summary from the Congressional Research Service</summary><div class=\"q-summary\">" + esc(it.summary) +
      "</div><p class=\"tiny\"><a href=\"" + esc(it.congress_gov) + "\" rel=\"noopener\" data-out=\"congress\">Bill text and history on Congress.gov</a> · <a href=\"" + esc(it.page) + "\">How every member voted</a></p></details>" +
      "<p class=\"q-ask\">How would you have voted?</p>" +
      "<div class=\"q-buttons\" role=\"group\" aria-label=\"Your vote\">" +
      "<button class=\"btn\" data-a=\"y\" aria-pressed=\"" + (a === "y") + "\">Yea</button>" +
      "<button class=\"btn\" data-a=\"n\" aria-pressed=\"" + (a === "n") + "\">Nay</button>" +
      "<button class=\"btn\" data-a=\"s\" aria-pressed=\"" + (a === "s") + "\">Skip</button></div>" +
      "<div class=\"q-reveal\"" + (a ? "" : " hidden") + "><div class=\"small muted\">How Congress voted</div>" + voteLine(it) + "</div>";
    card.querySelectorAll("[data-a]").forEach(function (b) {
      b.addEventListener("click", function () {
        if (answeredCount() === 0) track("quiz-start");
        answers[it.id] = b.getAttribute("data-a");
        writeHash();
        renderQuestion();
        if (pos < items.length - 1) setTimeout(function () { /* stay to let the reader see the reveal */ }, 0);
      });
    });
    nav.innerHTML = "";
    var prev = el("button", { "class": "btn" }, "← Previous");
    prev.disabled = pos === 0;
    prev.addEventListener("click", function () { pos--; renderQuestion(); card.scrollIntoView({ block: "nearest" }); });
    var next = el("button", { "class": "btn" }, pos === items.length - 1 ? "Last bill" : "Next bill →");
    next.disabled = pos === items.length - 1;
    next.addEventListener("click", function () { pos++; renderQuestion(); card.scrollIntoView({ block: "nearest" }); });
    var res = el("button", { "class": "btn primary" }, n >= MIN ? "See who votes like you (" + n + " answered)" : "Answer " + (MIN - n) + " more to see matches");
    res.disabled = n < MIN;
    res.addEventListener("click", showResults);
    nav.appendChild(prev); nav.appendChild(next); nav.appendChild(res);
  }

  // ---------------------------------------------------------------- matching
  function scores(ch) {
    var M = matrix[ch];
    var out = [];
    M.members.forEach(function (m, i) {
      var same = 0, shared = 0, rows = [];
      items.forEach(function (it) {
        var a = answers[it.id];
        var s = M.votes[it.id];
        if (!s || (a !== "y" && a !== "n")) return;
        var v = s.charAt(i);
        if (v !== "Y" && v !== "N") { rows.push([it, a, v]); return; }
        shared++;
        if ((v === "Y") === (a === "y")) same++;
        rows.push([it, a, v]);
      });
      out.push({ m: m, same: same, shared: shared, score: shared ? same / shared : null, rows: rows });
    });
    return out;
  }

  var results = document.getElementById("results");

  function memberLine(r, rank) {
    var m = r.m; // [bioguide, name, party, state, district, slug, ballot2026]
    var where = m[3] + (m[4] ? "-" + m[4] : "");
    var ballot = m[6] ? " <span class=\"chip plain\" title=\"Filed with the FEC as a 2026 candidate\">on 2026 ballot</span>" : "";
    var detail = r.rows.map(function (x) {
      var it = x[0], a = x[1], v = x[2];
      var theirs = v === "Y" ? "<span class=\"yea\">Yea</span>" : v === "N" ? "<span class=\"nay\">Nay</span>" : "<span class=\"muted\">did not vote</span>";
      var mine = a === "y" ? "Yea" : "Nay";
      var cls = v === "Y" || v === "N" ? (((v === "Y") === (a === "y")) ? "agree" : "disagree") : "";
      return "<tr class=\"" + cls + "\"><td><a href=\"" + esc(it.page) + "\">" + esc(it.label) + "</a> " + esc(it.title) + "</td><td>" + mine + "</td><td>" + theirs + "</td></tr>";
    }).join("");
    return "<div class=\"res-row\"><span class=\"rank\">" + rank + "</span><span class=\"who\"><a href=\"" + base + "../members/" + esc(m[5]) + "/\">" + esc(m[1]) +
      "</a> <span class=\"chip " + esc(m[2]) + "\">" + esc(m[2] + "-" + where) + "</span>" + ballot + "</span>" +
      "<span class=\"score\"><strong>" + (r.score == null ? "n/a" : pct(r.score)) + "</strong><div class=\"tiny\">" + r.same + " of " + r.shared + " votes</div></span>" +
      "<details class=\"res-detail\"><summary>Vote by vote</summary><div class=\"table-wrap\"><table><thead><tr><th>Bill</th><th>You</th><th>" + esc(m[1]) + "</th></tr></thead><tbody>" + detail + "</tbody></table></div></details></div>";
  }

  function renderResults() {
    var list = scores(chamber).filter(function (r) {
      return (!stateSel || r.m[3] === stateSel) && (!ballotOnly || r.m[6]);
    });
    var ranked = list.filter(function (r) { return r.shared >= (stateSel ? 1 : MIN_SHARED); });
    ranked.sort(function (a, b) { return (b.score - a.score) || (b.shared - a.shared) || a.m[1].localeCompare(b.m[1]); });
    var n = answeredCount();
    var html = "";
    if (!ranked.length) {
      html = "<p class=\"note\">None of the bills you answered had a " + chamber + " vote, or no member here shares enough of them. Answer more bills, or switch chamber.</p>";
    } else {
      var top = ranked[0].score;
      var tied = ranked.filter(function (r) { return r.score === top; }).length;
      var best = ranked[0];
      html += "<p class=\"lede\">" + (tied > 1
        ? tied + " " + (chamber === "House" ? "representatives" : "senators") + " tie for the closest match, agreeing with you on " + pct(top) + " of shared votes."
        : "Closest match: <strong>" + esc(best.m[1]) + "</strong> (" + esc(best.m[2] + "-" + best.m[3]) + "), who voted your way on " + best.same + " of " + best.shared + " bills.") + "</p>";
      var parties = {};
      ranked.forEach(function (r) { var p = r.m[2]; (parties[p] = parties[p] || []).push(r.score); });
      html += "<p class=\"small muted\">Average agreement by party: " + Object.keys(parties).sort().map(function (p) {
        var a = parties[p]; return p + " " + pct(a.reduce(function (x, y) { return x + y; }, 0) / a.length) + " (" + a.length + ")";
      }).join(" · ") + "</p>";
      var limit = stateSel ? ranked.length : Math.min(ranked.length, 25);
      var rows = "";
      var rank = 0, lastScore = null;
      for (var i = 0; i < limit; i++) {
        if (ranked[i].score !== lastScore) { rank = i + 1; lastScore = ranked[i].score; }
        rows += memberLine(ranked[i], rank);
      }
      html += "<div class=\"card\" style=\"padding:0\">" + rows + "</div>";
      if (!stateSel && ranked.length > limit) html += "<p class=\"small muted\">Showing the top " + limit + " of " + ranked.length + ". Pick a state to see your own delegation.</p>";
      // least aligned, for contrast
      if (!stateSel && ranked.length > 50) {
        var low = ranked.slice(-5).reverse();
        html += "<details><summary>Least aligned with you</summary><div class=\"card\" style=\"padding:0\">" + low.map(function (r) { return memberLine(r, "·"); }).join("") + "</div></details>";
      }
    }
    results.querySelector(".res-body").innerHTML = html;
    results.querySelector(".res-count").textContent = n;
    shareSetup(ranked);
  }

  function showResults() {
    track("results-view");
    results.hidden = false;
    renderResults();
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------------------------------------------------------------- share
  function shareSetup(ranked) {
    var url = site + hashFor(answers);
    var top = ranked.slice(0, 3).map(function (r) { return r.m[1] + " " + pct(r.score); }).join(", ");
    var text = "I voted on " + answeredCount() + " bills Congress actually voted on. Closest " + (chamber === "House" ? "House" : "Senate") + " matches: " + top + ". Who votes like you?";
    var box = results.querySelector(".res-share");
    box.innerHTML = "";
    var share = el("button", { "class": "btn primary" }, "Share my results");
    share.addEventListener("click", function () {
      track("share");
      if (navigator.share) navigator.share({ title: document.title, text: text, url: url }).catch(function () {});
      else copy(url, share);
    });
    var copyBtn = el("button", { "class": "btn" }, "Copy link");
    copyBtn.addEventListener("click", function () { track("share-copy"); copy(url, copyBtn); });
    var x = el("a", { "class": "btn", href: "https://twitter.com/intent/tweet?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(site), rel: "noopener", target: "_blank" }, "X");
    var bs = el("a", { "class": "btn", href: "https://bsky.app/intent/compose?text=" + encodeURIComponent(text + " " + site), rel: "noopener", target: "_blank" }, "Bluesky");
    var img = el("button", { "class": "btn" }, "Download result card");
    img.addEventListener("click", function () { track("card-download"); drawCard(ranked); });
    [share, copyBtn, x, bs, img].forEach(function (b) { box.appendChild(b); });
  }

  function copy(text, btn) {
    var old = btn.textContent;
    function ok() { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = old; }, 1500); }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, function () {});
  }

  function drawCard(ranked) {
    var c = document.createElement("canvas");
    c.width = 1200; c.height = 630;
    var g = c.getContext("2d");
    g.fillStyle = "#0b1f26"; g.fillRect(0, 0, 1200, 630);
    g.fillStyle = "#5cc8dc"; g.font = "700 30px system-ui, -apple-system, Segoe UI, sans-serif"; g.fillText("Who Votes Like Me", 64, 84);
    g.fillStyle = "#ffffff"; g.font = "800 58px system-ui, -apple-system, Segoe UI, sans-serif";
    g.fillText("Who in Congress votes like me?", 64, 170);
    g.font = "500 28px system-ui, -apple-system, Segoe UI, sans-serif"; g.fillStyle = "#b9d4da";
    g.fillText("I voted on " + answeredCount() + " real bills. Closest " + chamber + " matches:", 64, 225);
    ranked.slice(0, 4).forEach(function (r, i) {
      var y = 300 + i * 70;
      g.fillStyle = "#12303a"; g.fillRect(64, y - 44, 1072, 58);
      g.fillStyle = "#ffffff"; g.font = "650 32px system-ui, -apple-system, Segoe UI, sans-serif";
      g.fillText(r.m[1] + "  (" + r.m[2] + "-" + r.m[3] + ")", 88, y);
      g.textAlign = "right"; g.fillText(pct(r.score) + "  ·  " + r.same + "/" + r.shared, 1112, y); g.textAlign = "left";
    });
    g.fillStyle = "#8fb3bb"; g.font = "500 22px system-ui, -apple-system, Segoe UI, sans-serif";
    g.fillText("Every vote sourced to the official roll call · " + site.replace(/^https?:\/\//, ""), 64, 600);
    c.toBlob(function (blob) {
      var a = el("a", { href: URL.createObjectURL(blob), download: "who-votes-like-me.png" });
      document.body.appendChild(a); a.click(); a.remove();
    });
  }

  // ---------------------------------------------------------------- controls and start
  function setup() {
    var tabs = results.querySelectorAll("[data-chamber]");
    tabs.forEach(function (t) {
      t.addEventListener("click", function () {
        chamber = t.getAttribute("data-chamber");
        tabs.forEach(function (x) { x.setAttribute("aria-selected", String(x === t)); });
        renderResults();
      });
    });
    var sel = results.querySelector("[data-state]");
    var states = {};
    ["House", "Senate"].forEach(function (ch) { matrix[ch].members.forEach(function (m) { states[m[3]] = 1; }); });
    Object.keys(states).sort().forEach(function (s) { sel.appendChild(el("option", { value: s }, s)); });
    sel.addEventListener("change", function () { stateSel = sel.value; renderResults(); });
    var bal = results.querySelector("[data-ballot]");
    bal.addEventListener("change", function () { ballotOnly = bal.checked; renderResults(); });
  }

  Promise.all([fetch(base + "quiz.json").then(function (r) { return r.json(); }),
               fetch(base + "matrix.json").then(function (r) { return r.json(); })]).then(function (d) {
    quiz = d[0]; matrix = d[1]; items = quiz.items;
    answers = readHash();
    var fallback = document.getElementById("quiz-static");
    if (fallback) fallback.hidden = true;
    root.hidden = false;
    var first = items.findIndex(function (it) { return !answers[it.id]; });
    pos = first < 0 ? items.length - 1 : first;
    setup();
    renderQuestion();
    if (answeredCount() >= MIN) {
      // Opened from a shared link (or a reload): show those results, and offer a fresh start.
      showResults();
      var fresh = el("button", { "class": "btn" }, "Start my own quiz");
      fresh.addEventListener("click", function () {
        answers = {}; pos = 0; writeHash(); results.hidden = true; renderQuestion();
        root.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      results.querySelector(".res-fresh").appendChild(fresh);
    }
  }).catch(function () {
    root.innerHTML = "<p class=\"note\">The quiz data could not load. The bill pages below still work.</p>";
    root.hidden = false;
  });
})();
