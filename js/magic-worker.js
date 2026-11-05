// 魔法実験室: ブラウザの中で Python(Pyodide) と本物の cse-frog ＋ 判定エンジン(familiar) を動かす。
// 入力した詠唱は外へ送らない。信頼の境界: Pyodide 本体と numpy は jsDelivr（版を固定）から読み込み、そのコードは信頼する。
// このワーカーにはページの meta CSP が効かない（GitHub Pages ではワーカー用の CSP ヘッダーを付けられない）ので、
// ワーカー内で外部に通信するのは Pyodide の読み込みだけ・自前の fetch は同一オリジンの py/ だけ、という作りで守る。
const PYODIDE_VERSION = "0.28.3";
const INDEX_URL = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;
importScripts(INDEX_URL + "pyodide.js");

const FAMILIAR = ["__init__.py", "lexicon.py", "chunks.py", "seeds.py", "magic.py", "summon.py", "memory.py", "lab.py"];
const FNS = ["seeds", "check", "summon", "cast"];
let py = null;
let mod = null;

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
  self.postMessage({ type: "status", text: "🐸 と魔法の辞書を連れてきています…" });
  const base = "/home/pyodide";
  py.FS.mkdirTree(base + "/cse");
  py.FS.mkdirTree(base + "/familiar");
  for (const f of ["__init__.py", "_engine.py"]) {
    py.FS.writeFile(`${base}/cse/${f}`, await fetchText(`../py/cse/${f}`));
  }
  for (const f of FAMILIAR) {
    py.FS.writeFile(`${base}/familiar/${f}`, await fetchText(`../py/familiar/${f}`));
  }
  py.FS.writeFile(`${base}/_magic.py`, await fetchText("../py/_magic.py"));
  py.runPython(`import sys\nif "${base}" not in sys.path: sys.path.insert(0, "${base}")\nimport os\nos.chdir("${base}")`);
  mod = py.pyimport("_magic");
  self.postMessage({ type: "ready" });
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

let queue = Promise.resolve();
self.onmessage = (ev) => { queue = queue.then(() => handle(ev.data || {})).catch(() => {}); };

async function handle({ id, fn, arg }) {
  try {
    await ready;
    if (!FNS.includes(fn)) throw new Error("unknown function");
    const result = mod[fn](JSON.stringify(arg || {}));
    self.postMessage({ type: "done", id, result: JSON.parse(result) });
  } catch (e) {
    self.postMessage({ type: "error", id, text: lastLine(e).replace(/^ValueError: /, "") });
  }
}
