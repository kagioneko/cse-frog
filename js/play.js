// ブラウザ体験ページ。表示はすべて textContent で入れる（入力やコードの出力を HTML として解釈しない）
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  var el = function (tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  // ---------------------------------------------------------------- お手本
  var PRESETS = {
    rrd: { mode: "chars", prefix: "右右", data: "右右下右右下右右下\n右右下右右下\n右右下" },
    weather: { mode: "words", prefix: "晴れ 曇り",
      data: "晴れ 晴れ 曇り 雨 雨 曇り 晴れ\n晴れ 曇り 雨 雨 曇り 晴れ 晴れ\n曇り 雨 雨 雨 曇り 晴れ\n晴れ 晴れ 晴れ 曇り 雨 曇り 晴れ" },
    machine: { mode: "words", prefix: "正常 温度上昇",
      data: "正常 正常 温度上昇 警告 停止\n正常 温度上昇 警告 停止\n正常 正常 正常 温度上昇 警告 冷却 正常\n正常 温度上昇 警告 冷却 正常 正常" },
    words: { mode: "chars", prefix: "いい",
      data: "きょうはいいてんきですね。\nあしたもいいてんきだといいですね。\nいいねこですね。" }
  };

  // つまみ（Frog() の素直な設定がそのまま初期値）
  var KNOBS = [
    { key: "temperature", label: "temperature", note: "下げると自信満々、上げると迷いがち", min: 0.05, max: 3, step: 0.05, value: 0.8 },
    { key: "top_k_edges", label: "top_k_edges", note: "確率にする候補・広げるつながりの本数", min: 1, max: 20, step: 1, value: 3, int: true },
    { key: "refractory_steps", label: "refractory_steps", note: "不応期：直前に出た記号をしばらく出さない", min: 0, max: 5, step: 1, value: 0, int: true },
    { key: "history_boost", label: "history_boost", note: "少し前の記号の「残り香」で点数を盛る", min: 0, max: 2, step: 0.05, value: 0 },
    { key: "pair_context_boost", label: "pair_context_boost", note: "直前2つの並びの効き方。0 で「右右→下」が覚えにくくなる", min: 0, max: 3, step: 0.1, value: 1 },
    { key: "learning_rate", label: "learning_rate", note: "1回で結びつきをどれだけ強めるか", min: 0.01, max: 1, step: 0.01, value: 0.1 },
    { key: "activation_decay", label: "activation_decay", note: "活性の残り方（文脈の持ち越し）", min: 0, max: 1, step: 0.05, value: 0.6 },
    { key: "probability_mode", label: "probability_mode", note: "点数を確率に変える方法", choices: ["softmax", "linear"], value: "softmax" }
  ];

  var EXAMPLES = {
    basic: '# ここでは f という名前で新しい 🐸 を作ります（つまみの 🐸 は frog のまま）\nf = Frog()                          # 🐸 を1匹つくる\nf.learn([["右", "右", "下"]] * 10)   # 系列を覚えさせる\nprint(f.predict(["右", "右"]))       # -> 下\nprint(f.top(["右"], k=2))           # 確率の高い順に2つ\nf.show(["右", "右", "下"])           # 点数の内訳を表で見る\n',
    break: 'data = [["右", "右", "下"] * 5]\n\nprint(Frog().learn(data).top(["右", "右", "下"]))                          # 素直\nprint(Frog(refractory_steps=2).learn(data).top(["右", "右", "下"]))        # 不応期\nprint(Frog(probability_mode="linear").learn(data).top(["右", "右", "下"])) # 確率の出し方を変える\nprint(Frog(temperature=2.0).learn(data).top(["右", "右", "下"]))          # 温度を上げる\n',
    topp: 'import random\n\ndef top_p(frog, prefix, p=0.9):\n    items = sorted(frog.probabilities(prefix).items(), key=lambda kv: -kv[1])\n    keep, total = [], 0.0\n    for tok, prob in items:\n        keep.append((tok, prob)); total += prob\n        if total >= p:\n            break\n    tokens, weights = zip(*keep)\n    return random.choices(tokens, weights=weights)[0]\n\nf = Frog(top_k_edges=10).learn("きょうはいいてんきですね。あしたもいいてんきだといいですね。", epochs=5)\nprint([top_p(f, "いい", p=0.9) for _ in range(10)])\n',
    save: 'f = Frog().learn([["右", "右", "下"]] * 10)\nf.save("my_frog.cse")              # ブラウザの中の仮のファイルに保存\ng = Frog.load("my_frog.cse")       # 読み込むと、続きから学習も予測もできる\nprint(g, g.predict(["右", "右"]))\n',
    shared: '# 「つまみで遊ぶ」で覚えさせた 🐸 は frog という名前で入っています\nprint(frog)\nprint(frog.config.temperature, frog.config.refractory_steps)\nfrog.show([])   # 何も渡さないと「最初の記号」の候補\n'
  };

  // ---------------------------------------------------------------- ワーカー
  var worker = null, ready = false, seq = 0, pending = {}, running = null;

  function setStatus(text, kind) {
    $("status-text").textContent = text;
    $("status").className = "status" + (kind ? " " + kind : "");
  }

  function setBusy(busy) {
    ["learn", "ask", "gen", "run"].forEach(function (id) { $(id).disabled = busy || !ready; });
    $("stop").disabled = !running;
  }

  function startWorker() {
    ready = false;
    setBusy(true);
    worker = new Worker("js/worker.js");
    worker.onmessage = function (ev) {
      var m = ev.data;
      if (m.type === "status") setStatus(m.text);
      else if (m.type === "ready") { ready = true; setStatus("🐸 の準備ができました（Python " + m.python + "）", "ok"); setBusy(false); if (!trained) learn(); }
      else if (m.type === "fatal") setStatus("読み込みに失敗しました：" + m.text + "（通信環境を確認して、ページを再読み込みしてください）", "bad");
      else if (m.type === "out" || m.type === "err") { if (running === m.id) appendOut(m.text, m.type === "err"); }
      else if (m.type === "done" || m.type === "error") {
        var p = pending[m.id]; delete pending[m.id];
        if (p) (m.type === "done" ? p.resolve(m.result) : p.reject(new Error(m.text)));
      }
    };
    worker.onerror = function () {
      setStatus("Python の起動でエラーが起きました。ページを再読み込みしてください。", "bad");
      Object.keys(pending).forEach(function (id) { pending[id].reject(new Error("Python でエラーが起きました。")); delete pending[id]; });
      running = null;
      setBusy(true);
    };
  }

  function send(msg) {
    var id = ++seq;
    msg.id = id;
    return new Promise(function (resolve, reject) {
      pending[id] = { resolve: resolve, reject: reject };
      worker.postMessage(msg);
    });
  }
  var call = function (fn, arg) { return send({ op: "call", fn: fn, arg: arg }); };

  // ---------------------------------------------------------------- つまみ
  var knobInputs = {};
  function buildKnobs() {
    var box = $("knobs");
    KNOBS.forEach(function (k) {
      var row = el("div", "knob-row");
      var head = el("div", "knob-head");
      var name = el("label", "kname", k.label);
      var id = "k-" + k.key;
      name.htmlFor = id;
      var val = el("output", "kval");
      head.appendChild(name); head.appendChild(val);
      row.appendChild(head);
      var input;
      if (k.choices) {
        input = el("select");
        k.choices.forEach(function (c) { var o = el("option", null, c); o.value = c; input.appendChild(o); });
      } else {
        input = el("input");
        input.type = "range"; input.min = k.min; input.max = k.max; input.step = k.step;
      }
      input.id = id;
      input.value = k.value;
      var sync = function () { val.textContent = k.choices ? "" : (k.int ? String(parseInt(input.value, 10)) : Number(input.value).toFixed(2)); };
      input.addEventListener("input", function () { sync(); scheduleRelearn(); });
      sync();
      row.appendChild(input);
      row.appendChild(el("p", "knote", k.note));
      box.appendChild(row);
      knobInputs[k.key] = { input: input, sync: sync, def: k };
    });
  }
  function config() {
    var c = {};
    Object.keys(knobInputs).forEach(function (key) {
      var k = knobInputs[key];
      c[key] = k.def.choices ? k.input.value : (k.def.int ? parseInt(k.input.value, 10) : Number(k.input.value));
    });
    return c;
  }
  var relearnTimer = null;
  function scheduleRelearn() {
    if (!trained) return;
    clearTimeout(relearnTimer);
    relearnTimer = setTimeout(function () { learn(true); }, 280);
  }

  // ---------------------------------------------------------------- 1. えさ
  var trained = false;
  function checked(name, fallback) { var r = document.querySelector('input[name="' + name + '"]:checked'); return r ? r.value : fallback; }
  function mode() { return checked("mode", "chars"); }
  function loadPreset(name) {
    var p = PRESETS[name];
    $("data").value = p.data;
    document.querySelector('input[name="mode"][value="' + p.mode + '"]').checked = true;
    $("prefix").value = p.prefix;
    $("prefix").placeholder = "例: " + p.prefix;
    document.querySelectorAll("[data-preset]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-preset") === name ? "true" : "false"); });
  }

  function showErr(msg) { var b = $("knob-err"); b.hidden = !msg; b.textContent = msg ? "🐸💦 " + msg : ""; }

  function learn(thenAsk) {
    if (!ready) return;
    showErr("");
    setBusy(true);
    var epochs = Math.max(1, Math.min(50, parseInt($("epochs").value, 10) || 3));
    $("epochs").value = epochs;
    return call("setup", { data: $("data").value, mode: mode(), epochs: epochs, config: config() })
      .then(function (r) {
        trained = true;
        $("learned").textContent = "覚えた記号：" + r.count + " 個（押すと、その記号から出ているつながりが見られます）";
        var box = $("symbols");
        box.textContent = "";
        r.symbols.forEach(function (s) {
          var b = el("button", "sym", s === " " ? "␣" : s);
          b.type = "button";
          b.addEventListener("click", function () { showEdges(s); });
          box.appendChild(b);
        });
        $("edge-view").hidden = true;
        setBusy(false);
        if (thenAsk !== false) return ask();
      })
      .catch(function (e) { setBusy(false); showErr(e.message); });
  }

  // ---------------------------------------------------------------- 3. のぞく
  function barRow(tok, parts, max, right, blocked) {
    var row = el("div", "bar-row" + (blocked ? " blocked" : ""));
    row.appendChild(el("span", "tok", tok === " " ? "␣" : tok));
    var track = el("div", "bar-track");
    parts.forEach(function (p) {
      var s = el("span", p[0]);
      s.style.width = (max > 0 ? Math.max(0, p[1]) / max * 100 : 0).toFixed(2) + "%";
      track.appendChild(s);
    });
    row.appendChild(track);
    row.appendChild(el("span", "prob", right));
    if (blocked) row.appendChild(el("span", "blocked-note", "← 不応期で消された"));
    return row;
  }

  function ask() {
    if (!trained) return learn();
    showErr("");
    setBusy(true);
    return call("explain", { prefix: $("prefix").value, k: 6 }).then(function (r) {
      setBusy(false);
      $("answer").hidden = false;
      $("predict-tok").textContent = r.predict;
      var bars = $("bars");
      bars.textContent = "";
      var max = 0;
      r.rows.forEach(function (x) { max = Math.max(max, x.direct + x.history + x.pair + x.trace); });
      if (!r.rows.length) bars.appendChild(el("p", "hint", "点数がプラスの候補が1つもありません → <END> を確率1で返します。"));
      r.rows.forEach(function (x) {
        bars.appendChild(barRow(x.token, [["seg-direct", x.direct], ["seg-history", x.history], ["seg-pair", x.pair], ["seg-trace", x.trace]],
          max, x.prob.toFixed(3), x.blocked));
      });
      var t = $("explain-table");
      t.textContent = "";
      var head = el("tr");
      ["候補", "直接", "履歴", "並び", "痕跡", "合計点", "確率", ""].forEach(function (h) { head.appendChild(el("th", null, h)); });
      t.appendChild(head);
      r.rows.forEach(function (x) {
        var tr = el("tr");
        [x.token, x.direct, x.history, x.pair, x.trace, x.score, x.prob].forEach(function (v, i) {
          tr.appendChild(el("td", i ? "num" : null, i ? v.toFixed(3) : v));
        });
        tr.appendChild(el("td", "flag", x.blocked ? "不応期" : ""));
        t.appendChild(tr);
      });
    }).catch(function (e) { setBusy(false); showErr(e.message); });
  }

  function generate() {
    if (!trained) return;
    showErr("");
    setBusy(true);
    var how = checked("how", "greedy");
    call("generate", { prefix: $("prefix").value, n: parseInt($("gen-n").value, 10) || 20, how: how, seed: parseInt($("gen-seed").value, 10) || 0 })
      .then(function (r) {
        setBusy(false);
        var out = $("gen-out");
        out.textContent = "";
        out.appendChild(el("span", "given", $("prefix").value));
        r.tokens.forEach(function (t) {
          out.appendChild(el("span", t === "<END>" ? "end" : "made", mode() === "words" && t !== "<END>" ? " " + t : t));
        });
      })
      .catch(function (e) { setBusy(false); showErr(e.message); });
  }

  function showEdges(tok) {
    call("edges", { token: tok }).then(function (r) {
      $("edge-view").hidden = false;
      $("edge-tok").textContent = tok === " " ? "␣" : tok;
      var box = $("edge-bars");
      box.textContent = "";
      var max = 0;
      r.edges.forEach(function (e) { max = Math.max(max, e[1]); });
      if (!r.edges.length) box.appendChild(el("p", "hint", "まだどこにもつながっていません。"));
      r.edges.forEach(function (e) { box.appendChild(barRow(e[0], [["seg-direct", e[1]]], max, e[1].toFixed(3), false)); });
      $("edge-view").scrollIntoView({ behavior: "smooth", block: "nearest" });
    }).catch(function (e) { showErr(e.message); });
  }

  // ---------------------------------------------------------------- コード
  function appendOut(text, isErr) {
    var out = $("out");
    var s = el("span", isErr ? "e" : null, text);
    out.appendChild(s);
    out.scrollTop = out.scrollHeight;
  }

  function runCode() {
    if (!ready || running) return;
    var code = $("code").value;
    var msgId = seq + 1;
    running = msgId;
    setBusy(true);
    $("stop").disabled = false;
    appendOut("▶ 実行\n", false);
    send({ op: "exec", code: code }).then(function (repr) {
      if (repr !== null && repr !== undefined) {
        var cur = $("out").textContent;
        appendOut((cur && cur.slice(-1) !== "\n" ? "\n" : "") + repr + "\n", false);
      }
    }).catch(function (e) {
      appendOut(e.message + "\n", true);
    }).then(function () { running = null; setBusy(false); });
  }

  function stopPython() {
    if (!worker) return;
    worker.terminate();
    Object.keys(pending).forEach(function (id) { pending[id].reject(new Error("止めました。")); delete pending[id]; });
    running = null;
    trained = false;
    appendOut("■ 止めました。Python を起動し直します（つまみの 🐸 も作り直します）。\n", true);
    startWorker();
  }

  // ---------------------------------------------------------------- タブ
  function selectTab(which) {
    ["knobs", "code"].forEach(function (name) {
      var on = name === which;
      var tab = $("tab-" + name);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      $("panel-" + name).hidden = !on;
    });
  }

  // ---------------------------------------------------------------- 起動
  document.addEventListener("DOMContentLoaded", function () {
    buildKnobs();
    loadPreset("rrd");
    $("code").value = EXAMPLES.basic;

    document.querySelectorAll("[data-preset]").forEach(function (b) {
      b.addEventListener("click", function () { loadPreset(b.getAttribute("data-preset")); if (ready) learn(); });
    });
    document.querySelectorAll('input[name="mode"]').forEach(function (r) { r.addEventListener("change", function () { trained = false; }); });
    $("data").addEventListener("input", function () { trained = false; });
    $("learn").addEventListener("click", function () { learn(); });
    $("ask").addEventListener("click", ask);
    $("prefix").addEventListener("keydown", function (e) { if (e.key === "Enter") ask(); });
    $("gen").addEventListener("click", generate);
    $("reset-knobs").addEventListener("click", function () {
      Object.keys(knobInputs).forEach(function (key) { var k = knobInputs[key]; k.input.value = k.def.value; k.sync(); });
      scheduleRelearn();
    });

    $("tab-knobs").addEventListener("click", function () { selectTab("knobs"); });
    $("tab-code").addEventListener("click", function () { selectTab("code"); });
    document.querySelector(".tabs").addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        var next = $("tab-knobs").getAttribute("aria-selected") === "true" ? "code" : "knobs";
        selectTab(next); $("tab-" + next).focus();
      }
    });

    $("example").addEventListener("change", function () { $("code").value = EXAMPLES[$("example").value]; });
    $("run").addEventListener("click", runCode);
    $("stop").addEventListener("click", stopPython);
    $("clear").addEventListener("click", function () { $("out").textContent = ""; });
    $("code").addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); runCode(); return; }
      if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        var t = e.target, s = t.selectionStart;
        t.setRangeText("    ", s, t.selectionEnd, "end");
      }
    });

    if (!window.Worker || !window.WebAssembly) {
      setStatus("このブラウザでは Python を動かせません（Web Worker / WebAssembly が必要です）。", "bad");
      return;
    }
    startWorker();
  });
})();
