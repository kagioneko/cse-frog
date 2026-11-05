// 魔法実験室。表示はすべて textContent で入れる（詠唱を HTML として解釈しない）
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var el = function (tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  var KEY = "cse-magic-taught";
  var MAX_TAUGHT = 200;
  var VERDICT_CLASS = { "正常発動": "v-ok", "変異発動": "v-mut", "ファンブル": "v-fumble", "特殊発動": "v-special", "不発": "v-fizzle" };

  // ---------------------------------------------------------------- 教えた詠唱（このブラウザにだけ保存）
  var taught = [];
  function loadTaught() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || "[]");
      if (Array.isArray(v)) taught = v.filter(function (x) { return typeof x === "string" && x.length <= 60; }).slice(-MAX_TAUGHT);
    } catch (e) { taught = []; }
  }
  function saveTaught() {
    try { localStorage.setItem(KEY, JSON.stringify(taught)); } catch (e) { /* 保存できなくても遊べる */ }
  }
  function renderTaught() {
    var box = $("taught");
    box.textContent = "";
    if (!taught.length) { box.appendChild(el("p", "hint", "まだ何も教えていません。")); return; }
    taught.forEach(function (t, i) {
      var chip = el("span", "spell-chip");
      chip.appendChild(el("span", "", t));
      var x = el("button", "chip-x", "×");
      x.type = "button";
      x.setAttribute("aria-label", "「" + t + "」を忘れさせる");
      x.addEventListener("click", function () { taught.splice(i, 1); saveTaught(); renderTaught(); });
      chip.appendChild(x);
      box.appendChild(chip);
    });
  }

  // ---------------------------------------------------------------- ワーカー
  var worker = null, ready = false, busy = false, seq = 0, pending = {};
  function setStatus(text, kind) {
    $("status-text").textContent = text;
    $("status").className = "status" + (kind ? " " + kind : "");
  }
  // 処理中フラグ。ボタンの無効化だけでなく、Enter キーからの呼び出しもここで止める
  function setBusy(b) {
    busy = b;
    ["teach", "summon", "cast"].forEach(function (id) { $(id).disabled = b || !ready; });
  }
  function canStart() { return ready && !busy; }
  function call(fn, arg) {
    return new Promise(function (resolve, reject) {
      var id = ++seq;
      pending[id] = { resolve: resolve, reject: reject };
      worker.postMessage({ id: id, fn: fn, arg: arg });
    });
  }
  function startWorker() {
    worker = new Worker("js/magic-worker.js");
    worker.onmessage = function (ev) {
      var m = ev.data;
      if (m.type === "status") setStatus(m.text);
      else if (m.type === "ready") {
        ready = true; setStatus("🐸 召喚の準備ができました", "ok"); setBusy(false);
        call("seeds", {}).then(function (list) {
          $("seed-count").textContent = String(list.length);
          var ul = $("seed-list");
          list.forEach(function (s) { ul.appendChild(el("li", "", s)); });
        });
      }
      else if (m.type === "fatal") setStatus("読み込みに失敗しました：" + m.text + "（通信環境を確認して、ページを再読み込みしてください）", "bad");
      else if (m.type === "done" || m.type === "error") {
        var p = pending[m.id]; delete pending[m.id];
        if (p) (m.type === "done" ? p.resolve(m.result) : p.reject(new Error(m.text)));
      }
    };
    worker.onerror = function () {
      setStatus("Python の起動でエラーが起きました。ページを再読み込みしてください。", "bad");
      Object.keys(pending).forEach(function (id) { pending[id].reject(new Error("Python でエラーが起きました。")); delete pending[id]; });
      ready = false; setBusy(true);
    };
  }

  function showErr(msg) {
    var e = $("err");
    e.textContent = msg || "";
    e.hidden = !msg;
  }

  // ---------------------------------------------------------------- 教える
  function teach() {
    if (!canStart()) return;
    var t = $("teach-text").value.trim();
    if (!t) return;
    if (taught.indexOf(t) >= 0) { $("teach-msg").textContent = "🐸 もう覚えています。"; return; }
    if (taught.length >= MAX_TAUGHT) { $("teach-msg").textContent = "🐸💦 覚えられるのは " + MAX_TAUGHT + " 個までです。"; return; }
    setBusy(true);
    call("check", { text: t }).then(function (r) {
      if (r.reason) { $("teach-msg").textContent = "🐸💦 " + r.reason; return; }
      if (taught.indexOf(t) >= 0 || taught.length >= MAX_TAUGHT) { $("teach-msg").textContent = "🐸💦 覚えられませんでした（重複か上限）。"; return; }
      taught.push(t); saveTaught(); renderTaught();
      $("teach-text").value = "";
      $("teach-msg").textContent = "🐸 覚えました（教えた詠唱 " + taught.length + " 個）";
    }).catch(function (e) { $("teach-msg").textContent = "🐸💦 " + e.message; })
      .then(function () { setBusy(false); });
  }

  // ---------------------------------------------------------------- 召喚
  var summonNo = 0;
  function goal() {
    var g = document.querySelector('input[name="goal"]:checked');
    return g ? g.value : "attack";
  }
  function randomSeed() {
    var a = new Uint32Array(1);
    (self.crypto || window.crypto).getRandomValues(a);
    return a[0] % 2147483647;
  }
  function renderResult(rec, title) {
    var card = el("article", "cast-card " + (VERDICT_CLASS[rec.verdict] || ""));
    var head = el("div", "cast-meta");
    head.appendChild(el("span", "verdict", rec.verdict));
    head.appendChild(el("span", "", title));
    card.appendChild(head);
    (rec.lines || []).forEach(function (line, i) {
      if (/^判定：/.test(line)) return;
      card.appendChild(el("p", i === 0 ? "spell" : "line", line));
    });
    return card;
  }
  function summon() {
    if (!canStart()) return;
    showErr("");
    var raw = $("seed").value.trim();
    var base = raw === "" ? randomSeed() : Number(raw);
    if (!Number.isInteger(base) || base < 0 || base > 2147483647) { showErr("くじの種は 0〜2147483647 の整数にしてください。"); return; }
    var n = Number($("count").value) || 1;
    var useSeeds = $("use-seeds").checked;
    var g = goal();
    setBusy(true);
    var chain = Promise.resolve();
    var cards = [];
    for (var i = 0; i < n; i++) {
      (function (s) {
        chain = chain.then(function () {
          return call("summon", { taught: taught, use_seeds: useSeeds, seed: s % 2147483648, goal: g });
        }).then(function (rec) {
          summonNo += 1;
          var title = "召喚 #" + summonNo + " ・ 種 " + rec.seed + " ・ 学習した詠唱 " + rec.count + " 個" +
            (rec.copied ? " ・ 覚えた詠唱そのまま" : "");
          cards.push(renderResult(rec, title));
        });
      })(base + i);
    }
    chain.then(function () {
      var log = $("log");
      var empty = $("log-empty");
      if (empty) empty.remove();
      var group = el("div", "summon-group");
      cards.forEach(function (c) { group.appendChild(c); });
      group.appendChild(el("p", "vanish", "🐸 …（使い魔たちは消えた）"));
      log.insertBefore(group, log.firstChild);
    }).catch(function (e) { showErr(e.message); })
      .then(function () { setBusy(false); });
  }

  // ---------------------------------------------------------------- 自分で唱える
  function castSelf() {
    if (!canStart()) return;
    var t = $("cast-text").value.trim();
    if (!t) return;
    var g = goal();                         // 送信と表示で同じ目的を使う
    setBusy(true);
    call("cast", { text: t, goal: g, seed: 0 }).then(function (r) {
      var out = $("cast-out");
      out.textContent = "";
      out.appendChild(renderResult(r, "カエルなし ・ 目的：" + (g === "heal" ? "回復" : "攻撃")));
    }).catch(function (e) {
      var out = $("cast-out");
      out.textContent = "";
      out.appendChild(el("p", "err-box", e.message));
    }).then(function () { setBusy(false); });
  }

  // ---------------------------------------------------------------- 起動
  loadTaught();
  renderTaught();
  $("teach").addEventListener("click", teach);
  $("teach-text").addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.isComposing) teach(); });
  $("summon").addEventListener("click", summon);
  $("cast").addEventListener("click", castSelf);
  $("cast-text").addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.isComposing) castSelf(); });
  $("clear").addEventListener("click", function () {
    var log = $("log");
    log.textContent = "";
    log.appendChild(el("p", "hint", "まだ誰も召喚されていません。")).id = "log-empty";
    summonNo = 0;
  });
  startWorker();
})();
