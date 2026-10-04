// ブラウザの中で Python(Pyodide) と本物の cse-frog を動かすワーカー。何も外へ送信しない。
const PYODIDE_VERSION = "0.28.3";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
importScripts(INDEX_URL + "pyodide.js");

let py = null;
let play = null;
let reprFn = null;
let currentId = null;

async function fetchText(rel) {
  const res = await fetch(new URL(rel, self.location), { cache: "no-cache" });
  if (!res.ok) throw new Error(`${rel} を読み込めませんでした (${res.status})`);
  return res.text();
}

async function init() {
  self.postMessage({ type: "status", text: "Python を起こしています…" });
  py = await loadPyodide({ indexURL: INDEX_URL });
  self.postMessage({ type: "status", text: "numpy を読み込んでいます…" });
  await py.loadPackage("numpy");
  self.postMessage({ type: "status", text: "🐸 を連れてきています…" });
  const base = "/home/pyodide";
  py.FS.mkdirTree(base + "/cse");
  for (const f of ["__init__.py", "_engine.py"]) {
    py.FS.writeFile(`${base}/cse/${f}`, await fetchText(`../py/cse/${f}`));
  }
  py.FS.writeFile(`${base}/_play.py`, await fetchText("../py/_play.py"));
  py.runPython(`import sys\nif "${base}" not in sys.path: sys.path.insert(0, "${base}")\nimport os\nos.chdir("${base}")`);
  play = py.pyimport("_play");
  reprFn = py.runPython("repr");
  // 改行で終わらない出力も届くよう、行単位ではなく書き込み単位で受け取る
  const outDec = new TextDecoder(), errDec = new TextDecoder();
  py.setStdout({ write: (buf) => { self.postMessage({ type: "out", id: currentId, text: outDec.decode(buf, { stream: true }) }); return buf.length; } });
  py.setStderr({ write: (buf) => { self.postMessage({ type: "err", id: currentId, text: errDec.decode(buf, { stream: true }) }); return buf.length; } });
  self.postMessage({ type: "ready", python: py.runPython("import sys; sys.version.split()[0]") });
}

function lastLine(err) {
  const msg = String(err && err.message ? err.message : err).trim();
  const lines = msg.split("\n").filter(Boolean);
  return lines.length ? lines[lines.length - 1] : msg;
}

const ready = init().catch((e) => {
  self.postMessage({ type: "fatal", text: String(e && e.message ? e.message : e) });
  throw e;
});

// 依頼は届いた順に1件ずつ処理する（実行中の print の出力先が混ざらないように）
let queue = Promise.resolve();
self.onmessage = (ev) => { queue = queue.then(() => handle(ev.data || {})).catch(() => {}); };

async function handle({ id, op, fn, arg, code }) {
  currentId = id;
  try {
    await ready;
    if (op === "call") {
      if (!["setup", "explain", "generate", "edges"].includes(fn)) throw new Error("unknown function");
      const result = play[fn](JSON.stringify(arg));
      self.postMessage({ type: "done", id, result: JSON.parse(result) });
    } else if (op === "exec") {
      const ns = play.user_ns;
      await py.loadPackagesFromImports(code);
      let value;
      try {
        value = await py.runPythonAsync(code, { globals: ns, filename: "<🐸>" });
      } finally {
        // 改行で終わらない出力も、この実行の出力として書き出してから次へ進む
        py.runPython("import sys; sys.stdout.flush(); sys.stderr.flush()");
      }
      let repr = null;
      if (value !== undefined && value !== null) {
        try { repr = reprFn(value); } catch (_) { repr = String(value); }
        if (value && typeof value.destroy === "function") value.destroy();
      }
      self.postMessage({ type: "done", id, result: repr });
    } else {
      throw new Error("unknown op");
    }
  } catch (e) {
    let full = String(e && e.message ? e.message : e);
    // Pyodide 内部の行は省いて、利用者のコード(<🐸>)からのトレースバックだけ見せる
    const at = full.indexOf('File "<🐸>"');
    if (op === "exec" && at > 0) full = "Traceback (most recent call last):\n  " + full.slice(at);
    self.postMessage({ type: "error", id, text: op === "exec" ? full : lastLine(e) });
  } finally {
    currentId = null;
  }
}
