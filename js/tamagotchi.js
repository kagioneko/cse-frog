// 自動生成: cse-frog-tamagotchi/tools/export_site.py（手で編集しない）
(() => {
  const STORAGE_KEY = "cse_frog_tamagotchi_v2";
  const STAGE_NAMES = ["おたまじゃくし", "足生えおたま", "子ガエル", "親ガエル"];
  const STAGE_EMOJIS = ["🫧", "🐟", "🐸", "👑🐸"];
  const STAGE_LRS = [0.60, 0.45, 0.30, 0.18];
  const STAGE_CAPS = [3, 5, 8, 12];

  const LAMBDA_BASE = 0.03;
  const MEMORY_ALPHA = 1.5;
  const PRUNE_THRESHOLD = 0.05;

  const hasSegmenter = typeof Intl !== "undefined" && typeof Intl.Segmenter === "function";
  const jaSegmenter = hasSegmenter ? new Intl.Segmenter("ja", { granularity: "word" }) : null;

  function clamp(v, lo = 0, hi = 1) {
    return Math.max(lo, Math.min(hi, v));
  }

  function tokenizeJa(text) {
    const cleaned = text.trim();
    if (!cleaned) return [];
    if (jaSegmenter) {
      const tokens = [];
      for (const seg of jaSegmenter.segment(cleaned)) {
        const s = seg.segment.trim();
        if (!s) continue;
        if (/^[、。！？!?,.\s]+$/.test(s)) continue;
        tokens.push(s);
      }
      if (tokens.length > 0) return tokens;
    }
    // Fallback regex tokenizer
    const m = cleaned.match(/[A-Za-z0-9_]+|[一-龥々]+|[ァ-ヶー]+|[ぁ-ん]+/g);
    return m ? m : [cleaned];
  }

  function joinJapanese(tokens) {
    if (!tokens.length) return "…";
    let res = tokens[0];
    for (let i = 1; i < tokens.length; i++) {
      const prev = tokens[i - 1];
      const cur = tokens[i];
      const asciiBoundary = /[A-Za-z0-9]$/.test(prev) && /^[A-Za-z0-9]/.test(cur);
      res += (asciiBoundary ? " " : "") + cur;
    }
    return res;
  }

  // 単語をキーにする辞書はプロトタイプを持たせない（"__proto__" 等の入力で
  // Object.prototype を汚染しないため）。
  function newDict() {
    return Object.create(null);
  }

  function defaultState() {
    return {
      vitals: {
        energy: 1.0,
        mood: 0.7,
        boredom: 0.0,
        stage: 0,
        total_turns: 0,
        last_interaction: Date.now(),
      },
      weights: newDict(),
      recent_tokens: [],
      logs: [
        { type: "system", text: "🐸 たまごっち型 cse-frog が生まれたよ！普通に日本語で話しかけて育ててみてな。" }
      ],
      last_tokens: [],
      last_trace: [],
      last_boost: 0,
    };
  }

  // ---- 外部データ（localStorage / インポートJSON）の検証 ----
  // どちらも信頼できない入力として扱い、型・範囲・件数を確かめて作り直す。
  // 上限は「学習時・読込時・エクスポート時」で同じ値を使う。
  // 最悪ケースのセーブサイズ見積もり（JSONエスケープ最大6バイト/文字）:
  //   リンク 5000 × (遷移先キー 64×6 + 数値 ≈ 410B) + 遷移元キー 5000 × 390B ≈ 4.0MB
  //   + ログ 60×500×6 ≈ 0.2MB + トークン・トレース ≈ 0.1MB  → 合計 < 4.5MB < IMPORT_BYTES
  const LIMITS = {
    TOKEN_LEN: 64,
    TOTAL_LINKS: 5000,
    LINKS_PER_SRC: 200,
    MAX_WEIGHT: 1e6,
    RECENT: 24,
    INPUT_CHARS: 2000,
    LAST_TOKENS: 200,
    LOGS: 60,
    LOG_TEXT: 500,
    TRACE: 12,
    CANDIDATES: 3,
    IMPORT_BYTES: 8 * 1024 * 1024,
  };
  const LOG_TYPES = new Set(["system", "user", "frog", "evolution"]);

  function isObj(v) {
    return v !== null && typeof v === "object" && !Array.isArray(v);
  }
  function num(v, lo, hi, fallback) {
    return typeof v === "number" && Number.isFinite(v) ? Math.max(lo, Math.min(hi, v)) : fallback;
  }
  function isToken(v) {
    return typeof v === "string" && v.length > 0 && v.length <= LIMITS.TOKEN_LEN;
  }
  function tokenList(v, max) {
    return Array.isArray(v) ? v.filter(isToken).slice(-max) : [];
  }

  function sanitizeState(raw) {
    if (!isObj(raw) || !isObj(raw.vitals) || !isObj(raw.weights)) return null;
    const now = Date.now();
    const s = defaultState();
    const v = raw.vitals;
    s.vitals.energy = num(v.energy, 0, 1, 1.0);
    s.vitals.mood = num(v.mood, 0, 1, 0.7);
    s.vitals.boredom = num(v.boredom, 0, 1, 0.0);
    s.vitals.stage = Math.floor(num(v.stage, 0, STAGE_NAMES.length - 1, 0));
    s.vitals.total_turns = Math.floor(num(v.total_turns, 0, Number.MAX_SAFE_INTEGER, 0));
    s.vitals.last_interaction = num(v.last_interaction, 0, now, now);

    let total = 0;
    for (const src of Object.keys(raw.weights)) {
      if (total >= LIMITS.TOTAL_LINKS) break;
      const links = raw.weights[src];
      if (!isToken(src) || !isObj(links)) continue;
      const dict = newDict();
      let n = 0;
      for (const dst of Object.keys(links)) {
        if (n >= LIMITS.LINKS_PER_SRC || total >= LIMITS.TOTAL_LINKS) break;
        const w = links[dst];
        if (!isToken(dst) || typeof w !== "number" || !Number.isFinite(w) || w <= 0) continue;
        dict[dst] = Math.min(w, LIMITS.MAX_WEIGHT);
        n++;
        total++;
      }
      if (n > 0) s.weights[src] = dict;
    }

    s.recent_tokens = tokenList(raw.recent_tokens, LIMITS.RECENT);
    s.last_tokens = tokenList(raw.last_tokens, LIMITS.LAST_TOKENS);
    s.last_boost = num(raw.last_boost, 0, 1, 0);

    if (Array.isArray(raw.logs)) {
      s.logs = raw.logs
        .filter(m => isObj(m) && LOG_TYPES.has(m.type) && typeof m.text === "string")
        .slice(-LIMITS.LOGS)
        .map(m => ({ type: m.type, text: m.text.slice(0, LIMITS.LOG_TEXT), lowEnergy: m.lowEnergy === true }));
    }

    s.last_trace = [];
    if (Array.isArray(raw.last_trace)) {
      for (const step of raw.last_trace.slice(0, LIMITS.TRACE)) {
        if (!isObj(step) || !isToken(step.from) || !isToken(step.to) || !Array.isArray(step.candidates)) continue;
        const candidates = [];
        for (const c of step.candidates.slice(0, LIMITS.CANDIDATES)) {
          if (!isObj(c) || !isToken(c.word)) continue;
          const base = num(c.base, 0, LIMITS.MAX_WEIGHT, NaN);
          const boost = num(c.boost, 0, LIMITS.MAX_WEIGHT, NaN);
          if (Number.isNaN(base) || Number.isNaN(boost)) continue;
          candidates.push({ word: c.word, base, boost, total: base + boost, chosen: c.chosen === true });
        }
        s.last_trace.push({ from: step.from, to: step.to, candidates });
      }
    }
    return s;
  }

  let state = loadState();

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = sanitizeState(JSON.parse(raw));
        if (parsed) return parsed;
      }
    } catch (e) {}
    return defaultState();
  }

  // ログ追加は必ずここを通す（全経路で件数・文字数の上限を守る）
  function addLog(entry) {
    state.logs.push({ ...entry, text: String(entry.text).slice(0, LIMITS.LOG_TEXT) });
    if (state.logs.length > LIMITS.LOGS) state.logs = state.logs.slice(-LIMITS.LOGS);
  }

  let saveWarned = false;
  function saveState() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      saveWarned = false;
    } catch (e) {
      // 容量超過やプライベートモード等。黙って失わないよう一度だけ知らせる。
      if (!saveWarned) {
        saveWarned = true;
        addLog({ type: "system", text: "⚠️ ブラウザへの自動保存に失敗しました。「セーブ」でJSONに書き出しておいてください。" });
      }
    }
  }

  function totalLinks() {
    let c = 0;
    for (const src of Object.keys(state.weights)) c += Object.keys(state.weights[src]).length;
    return c;
  }

  function vocabSize() {
    const s = new Set(Object.keys(state.weights));
    for (const src of Object.keys(state.weights)) {
      for (const dst of Object.keys(state.weights[src])) s.add(dst);
    }
    return s.size;
  }

  function strongLinksCount(threshold = 1.0) {
    let c = 0;
    for (const src of Object.keys(state.weights)) {
      for (const w of Object.values(state.weights[src])) {
        if (w >= threshold) c++;
      }
    }
    return c;
  }

  function applyTimePassage(elapsedHours) {
    if (elapsedHours <= 0) return [];
    const forgotten = [];
    for (const src of Object.keys(state.weights)) {
      const nxt = state.weights[src];
      for (const dst of Object.keys(nxt)) {
        const w = nxt[dst];
        const lam = LAMBDA_BASE / (1.0 + MEMORY_ALPHA * w);
        const newW = w * Math.exp(-lam * elapsedHours);
        if (newW < PRUNE_THRESHOLD) {
          delete nxt[dst];
          forgotten.push([src, dst]);
        } else {
          nxt[dst] = newW;
        }
      }
      if (Object.keys(nxt).length === 0) delete state.weights[src];
    }

    state.vitals.energy = clamp(state.vitals.energy + 0.15 * elapsedHours);
    if (elapsedHours > 6.0) {
      state.vitals.mood = clamp(state.vitals.mood - 0.02 * (elapsedHours - 6.0));
    }
    state.vitals.boredom = clamp(state.vitals.boredom - 0.1 * elapsedHours);
    return forgotten;
  }

  function maxGenLen() {
    const cap = STAGE_CAPS[Math.min(state.vitals.stage, 3)];
    const scale = 0.3 + 0.7 * state.vitals.energy;
    return Math.max(1, Math.round(cap * scale));
  }

  // 上限方針: 既存の連鎖は強化し続ける（MAX_WEIGHT で頭打ち）。上限に達したら
  // 新しい連鎖は覚えない（時間経過で忘れると空きができる）。読込時と同じ上限なので
  // 保存した記憶が再読み込みで消えることはない。
  function hebbianUpdate(tokens, lr) {
    let total = totalLinks();
    for (let i = 0; i < tokens.length - 1; i++) {
      const a = tokens[i];
      const b = tokens[i + 1];
      if (!isToken(a) || !isToken(b)) continue;
      const links = state.weights[a];
      if (links && links[b] !== undefined) {
        links[b] = Math.min(links[b] + lr, LIMITS.MAX_WEIGHT);
        continue;
      }
      if (total >= LIMITS.TOTAL_LINKS) continue;
      if (links && Object.keys(links).length >= LIMITS.LINKS_PER_SRC) continue;
      if (!links) state.weights[a] = newDict();
      state.weights[a][b] = Math.min(lr, LIMITS.MAX_WEIGHT);
      total++;
    }
    state.recent_tokens = state.recent_tokens.concat(tokens.filter(isToken)).slice(-LIMITS.RECENT);
  }

  function weightedChoice(items, weights) {
    const total = weights.reduce((a, b) => a + b, 0);
    let r = Math.random() * total;
    for (let i = 0; i < items.length; i++) {
      r -= weights[i];
      if (r <= 0) return items[i];
    }
    return items[items.length - 1];
  }

  function generateReply(promptTokens, maxLen, temperature, boredomBoost) {
    if (!promptTokens.length) return { out: ["…"], trace: [] };
    // Pick a seed token from prompt that has outgoing links (prefer later tokens)
    let cur = promptTokens[promptTokens.length - 1];
    for (let i = promptTokens.length - 1; i >= 0; i--) {
      if (state.weights[promptTokens[i]]) {
        cur = promptTokens[i];
        break;
      }
    }

    const out = [];
    const trace = [];
    const visited = new Set();

    for (let step = 0; step < maxLen; step++) {
      const candMap = state.weights[cur];
      if (!candMap) break;
      const words = Object.keys(candMap);
      if (!words.length) break;

      const rawScores = words.map(w => candMap[w]);
      const maxS = Math.max(...rawScores);
      const boostDeltas = rawScores.map(s => boredomBoost > 0 ? boredomBoost * (maxS - s) : 0);
      const adjScores = rawScores.map((s, i) => {
        const penalty = visited.has(words[i]) ? 0.45 : 1.0;
        return (s + boostDeltas[i]) * penalty;
      });

      // 数値安定化 softmax（最大値を引いてから exp。大きな重みでも Infinity にならない）
      const temp = Math.max(0.12, temperature);
      const maxAdj = Math.max(...adjScores);
      const exps = adjScores.map(s => Math.exp((s - maxAdj) / temp));
      const chosen = weightedChoice(words, exps);

      const ranked = words.map((w, i) => ({
        word: w,
        base: rawScores[i],
        boost: boostDeltas[i],
        total: rawScores[i] + boostDeltas[i],
        chosen: w === chosen,
      })).sort((a, b) => b.total - a.total).slice(0, 3);

      trace.push({ from: cur, to: chosen, candidates: ranked });
      out.push(chosen);
      visited.add(chosen);
      cur = chosen;
    }

    if (out.length === 0) {
      out.push(promptTokens[promptTokens.length - 1] + "…？");
    }
    return { out, trace };
  }

  function checkEvolution() {
    const v = state.vitals;
    const vocab = vocabSize();
    const strong = strongLinksCount(1.0);
    const oldStage = v.stage;

    if (v.stage === 0 && v.total_turns >= 4 && vocab >= 6) v.stage = 1;
    else if (v.stage === 1 && v.total_turns >= 12 && strong >= 4) v.stage = 2;
    else if (v.stage === 2 && v.total_turns >= 28 && strong >= 12) v.stage = 3;

    return v.stage > oldStage;
  }

  function handleChat(text) {
    const trimmed = text.trim().slice(0, LIMITS.INPUT_CHARS);
    if (!trimmed) return;

    const now = Date.now();
    const elapsedHours = Math.max(0, (now - state.vitals.last_interaction) / 3600000);
    const forgotten = applyTimePassage(elapsedHours);
    if (forgotten.length > 0) {
      const sample = forgotten.slice(0, 2).map(p => `「${p[0]}→${p[1]}」`).join(" ");
      addLog({ type: "system", text: `💨 時間経過で ${sample}${forgotten.length > 2 ? ` ほか${forgotten.length - 2}件` : ""} を忘れた…` });
    }

    const tokens = tokenizeJa(trimmed).filter(isToken).slice(0, LIMITS.LAST_TOKENS);
    state.last_tokens = tokens;

    // Update mood & boredom
    if (tokens.length > 0) {
      const novel = tokens.filter(t => !state.recent_tokens.includes(t)).length / tokens.length;
      if (novel > 0.3) {
        state.vitals.mood = clamp(state.vitals.mood + 0.08);
        state.vitals.boredom = clamp(state.vitals.boredom - 0.20);
      } else {
        state.vitals.boredom = clamp(state.vitals.boredom + 0.16);
        state.vitals.mood = clamp(state.vitals.mood - 0.04);
      }
    }

    const temp = 0.25 + 1.1 * state.vitals.mood;
    const boredomBoost = state.vitals.boredom > 0.6 ? 0.35 : 0.0;
    const maxLen = maxGenLen();
    const { out, trace } = generateReply(tokens, maxLen, temp, boredomBoost);

    state.last_trace = trace;
    state.last_boost = boredomBoost;

    const lr = STAGE_LRS[Math.min(state.vitals.stage, 3)];
    hebbianUpdate(tokens.concat(out.map(t => t.replace(/…？$/, ""))), lr);

    state.vitals.energy = clamp(state.vitals.energy - 0.04 * out.length);
    state.vitals.total_turns += 1;
    state.vitals.last_interaction = now;

    const lowEnergy = state.vitals.energy < 0.25;
    let replyStr = joinJapanese(out);
    if (lowEnergy) replyStr += " …ねむ";

    addLog({ type: "user", text: trimmed.slice(0, LIMITS.LOG_TEXT) });
    addLog({ type: "frog", text: replyStr, lowEnergy });

    const evolved = checkEvolution();
    if (evolved) {
      const s = state.vitals.stage;
      addLog({
        type: "evolution",
        text: `✨ 進化した！ Stage ${s}: ${STAGE_NAMES[s]}（LR=${STAGE_LRS[s].toFixed(2)}, 最大生成=${STAGE_CAPS[s]}語）`
      });
      const card = document.getElementById("frogCard");
      card.classList.add("evolved");
      setTimeout(() => card.classList.remove("evolved"), 2200);
    }

    saveState();
    render();
  }

  function simulateTimeJump(hours) {
    const forgotten = applyTimePassage(hours);
    state.vitals.last_interaction = Date.now();
    let msg = `⏱ ${hours}時間経過！（体力回復: ${Math.round(state.vitals.energy * 100)}%）`;
    if (forgotten.length > 0) {
      const sample = forgotten.slice(0, 3).map(p => `「${p[0]}→${p[1]}」`).join(" ");
      msg += ` / 忘却: ${sample}${forgotten.length > 3 ? ` ほか${forgotten.length - 3}件` : ""}`;
    } else {
      msg += " / 消滅した記憶なし";
    }
    addLog({ type: "system", text: msg });
    saveState();
    render();
  }

  // DOM組み立てヘルパー。文字列は必ず textContent で入れる（innerHTML は使わない）。
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function showEmpty(container, message) {
    container.replaceChildren(el("span", "empty-state", message));
  }

  function render() {
    const v = state.vitals;
    const temp = 0.25 + 1.1 * v.mood;
    const lr = STAGE_LRS[Math.min(v.stage, 3)];

    document.getElementById("stageBadge").textContent = `Stage ${v.stage}: ${STAGE_NAMES[v.stage]}`;
    document.getElementById("turnBadge").textContent = `Turn: ${v.total_turns}`;
    document.getElementById("vocabBadge").textContent = `語彙: ${vocabSize()}`;
    document.getElementById("lrInfo").textContent = `学習率 LR: ${lr.toFixed(2)} / 現在最大生成: ${maxGenLen()}語`;

    // Frog Avatar & Mood Text
    const emojiEl = document.getElementById("frogEmoji");
    const moodTextEl = document.getElementById("frogMoodText");
    emojiEl.textContent = STAGE_EMOJIS[Math.min(v.stage, 3)];
    emojiEl.className = "frog-emoji";
    if (v.energy < 0.3) {
      emojiEl.classList.add("sleepy");
      moodTextEl.textContent = "Zzz… ちょっと眠いかも";
    } else if (v.boredom > 0.6) {
      emojiEl.classList.add("bored");
      moodTextEl.textContent = "ソワソワ（ボケたい気分）";
    } else if (v.mood > 0.78) {
      emojiEl.classList.add("happy");
      moodTextEl.textContent = "ごきげん！連想が広がるよ";
    } else {
      moodTextEl.textContent = "きょろきょろしてる";
    }

    // Vitals Bars
    const ePct = Math.round(v.energy * 100);
    const mPct = Math.round(v.mood * 100);
    const bPct = Math.round(v.boredom * 100);
    document.getElementById("energyVal").textContent = `${ePct}%`;
    document.getElementById("energyBar").style.width = `${ePct}%`;
    document.getElementById("energyBar").style.background = ePct < 30 ? "var(--danger)" : ePct < 60 ? "var(--mood)" : "var(--energy)";

    document.getElementById("moodVal").textContent = `${mPct}% (T=${temp.toFixed(2)})`;
    document.getElementById("moodBar").style.width = `${mPct}%`;

    document.getElementById("boredomVal").textContent = bPct > 60 ? `${bPct}% ⚡ボケ発動中` : `${bPct}%`;
    document.getElementById("boredomBar").style.width = `${bPct}%`;

    // Chat Log
    const logEl = document.getElementById("chatLog");
    logEl.replaceChildren();
    for (const m of state.logs) {
      const div = document.createElement("div");
      div.className = `msg ${m.type}` + (m.lowEnergy ? " low-energy" : "");
      div.textContent = m.type === "frog" ? `🐸 ${m.text}` : m.text;
      logEl.appendChild(div);
    }
    logEl.scrollTop = logEl.scrollHeight;

    // Token Preview
    const tokEl = document.getElementById("tokenPreview");
    if (!state.last_tokens.length) {
      showEmpty(tokEl, "話しかけると、ここに切り出された単語が表示されます");
    } else {
      tokEl.replaceChildren(...state.last_tokens.map(t => el("span", "token-pill", t)));
    }

    // Spike Trace
    const spikeEl = document.getElementById("spikeContainer");
    const boostNote = document.getElementById("boostNote");
    boostNote.textContent = state.last_boost > 0 ? `⚡ 退屈ブースト発動 (+${state.last_boost.toFixed(2)})` : "通常モード";
    boostNote.style.color = state.last_boost > 0 ? "var(--boredom)" : "var(--text-muted)";

    if (!state.last_trace.length) {
      showEmpty(spikeEl, "まだ連鎖がありません。何度か話しかけて記憶を育ててみて！");
    } else {
      spikeEl.replaceChildren();
      for (const step of state.last_trace) {
        const card = el("div", "spike-card");
        const maxVal = Math.max(0.01, ...step.candidates.map(c => c.total));
        card.appendChild(el("div", "spike-from", `「${step.from}」からの次トークン予測:`));
        for (const c of step.candidates) {
          const baseW = clamp((c.base / maxVal) * 100, 0, 100);
          const boostW = clamp((c.boost / maxVal) * 100, 0, 100);
          const row = el("div", "cand-row");
          row.appendChild(el("div", c.chosen ? "cand-word chosen" : "cand-word", `${c.chosen ? "★ " : ""}${c.word}`));
          const barBg = el("div", "cand-bar-bg");
          const barBase = el("div", "cand-bar-base");
          barBase.style.width = `${baseW.toFixed(1)}%`;
          const barBoost = el("div", "cand-bar-boost");
          barBoost.style.width = `${boostW.toFixed(1)}%`;
          barBg.append(barBase, barBoost);
          row.append(barBg, el("div", "cand-score", c.total.toFixed(2)));
          card.appendChild(row);
        }
        spikeEl.appendChild(card);
      }
    }

    // Fading Memories (< 0.40) & Strong Memories (>= 1.0)
    const fading = [];
    const strong = [];
    for (const src of Object.keys(state.weights)) {
      for (const [dst, w] of Object.entries(state.weights[src])) {
        if (w < 0.45) fading.push({ src, dst, w });
        if (w >= 1.0) strong.push({ src, dst, w });
      }
    }
    fading.sort((a, b) => a.w - b.w);
    strong.sort((a, b) => b.w - a.w);

    const fadingEl = document.getElementById("fadingList");
    fadingEl.replaceChildren();
    if (!fading.length) {
      showEmpty(fadingEl, "忘れかけの連鎖はありません");
    } else {
      for (const item of fading.slice(0, 10)) {
        const div = el("div", "mem-item");
        const op = Math.max(0.38, Math.min(1.0, (item.w - PRUNE_THRESHOLD) / 0.35 + 0.38));
        div.style.opacity = op.toFixed(2);
        const isDanger = item.w < 0.16;
        div.append(
          el("span", "", `${item.src} → ${item.dst}`),
          el("span", `mem-tag ${isDanger ? "danger" : "warn"}`, `${item.w.toFixed(2)} ${isDanger ? "危険" : "薄れ中"}`)
        );
        div.title = "クリックして話しかけることで記憶を回復できます";
        div.addEventListener("click", () => {
          const inp = document.getElementById("userInput");
          inp.value = `${item.src}${item.dst}`;
          inp.focus();
        });
        fadingEl.appendChild(div);
      }
    }

    const strongEl = document.getElementById("strongList");
    strongEl.replaceChildren();
    if (!strong.length) {
      showEmpty(strongEl, "まだ定着した口癖はありません（同じ話題を繰り返すと定着します）");
    } else {
      for (const item of strong.slice(0, 8)) {
        const div = el("div", "mem-item");
        div.append(
          el("span", "", `🔒 ${item.src} → ${item.dst}`),
          el("span", "mem-tag lock", item.w.toFixed(2))
        );
        div.addEventListener("click", () => {
          const inp = document.getElementById("userInput");
          inp.value = item.src;
          inp.focus();
        });
        strongEl.appendChild(div);
      }
    }
  }

  // Event Listeners
  const inputEl = document.getElementById("userInput");
  document.getElementById("sendBtn").addEventListener("click", () => {
    handleChat(inputEl.value);
    inputEl.value = "";
  });
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.isComposing) {
      handleChat(inputEl.value);
      inputEl.value = "";
    }
  });
  document.querySelectorAll(".chip").forEach(ch => {
    ch.addEventListener("click", () => {
      handleChat(ch.textContent);
    });
  });
  document.querySelectorAll(".tm-btns button").forEach(btn => {
    btn.addEventListener("click", () => {
      simulateTimeJump(Number(btn.dataset.hours));
    });
  });

  document.getElementById("exportBtn").addEventListener("click", () => {
    // インデントなしで書き出す（サイズ上限を読込側と揃えるため）
    const blob = new Blob([JSON.stringify(state)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `cse_frog_save_stage${state.vitals.stage}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  const fileInput = document.getElementById("importFile");
  document.getElementById("importBtn").addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > LIMITS.IMPORT_BYTES) {
      alert("ファイルが大きすぎます（8MBまで）。");
      fileInput.value = "";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      let parsed = null;
      try {
        parsed = sanitizeState(JSON.parse(reader.result));
      } catch (err) {
        parsed = null;
      }
      if (!parsed) {
        alert("セーブデータとして読み込めませんでした。");
        return;
      }
      state = parsed;
      saveState();
      render();
    };
    reader.readAsText(file);
    fileInput.value = "";
  });

  document.getElementById("resetBtn").addEventListener("click", () => {
    if (confirm("育てた🐸の記憶をリセットして最初から始めますか？")) {
      state = defaultState();
      saveState();
      render();
    }
  });

  // Initial real-time passage check on load
  const initElapsed = Math.max(0, (Date.now() - state.vitals.last_interaction) / 3600000);
  if (initElapsed > 0.2) {
    const forgotten = applyTimePassage(initElapsed);
    if (forgotten.length > 0) {
      addLog({ type: "system", text: `🌅 おかえり！${initElapsed.toFixed(1)}時間ぶりに起動したよ（${forgotten.length}件の薄い記憶が薄れた）` });
    }
    state.vitals.last_interaction = Date.now();
    saveState();
  }
  render();
})();
