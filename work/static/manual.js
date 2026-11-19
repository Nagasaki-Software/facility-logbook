// 運転マニュアル（手順表）。ボタン欄の「📋 マニュアル」タブに表示し、
// 行を押すと「現在時刻＋記録内容」が運転記録に追加され、その行が実施済みの色になる。
window.WRManual = (function () {
  const st = {
    files: [],      // manuals フォルダにある CSV の一覧
    name: null,     // 表示中のマニュアル
    steps: [],      // 手順（CSVの1行＝1手順）
    progress: {},   // 実施済み {作業内容: {done_time, entry_id}}
    error: "",      // CSVの書き方の誤り（画面に赤字で出す）
    busy: false,    // 連打による二重記録を防ぐ
  };

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  // WR.api と違い、サーバーが返すエラー文（CSVのどこが悪いか）をそのまま受け取る
  async function apiJson(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const r = await fetch(url, opts);
    let data = null;
    try { data = await r.json(); } catch (_) {}
    if (!r.ok) {
      let msg = (data && data.error) ? data.error : `通信エラー (${r.status})`;
      if (r.status === 403) msg = "確定済みの記録のため記録できません。";
      const err = new Error(msg);
      err.status = r.status;
      throw err;
    }
    return data;
  }

  function q(name) { return encodeURIComponent(name); }

  async function loadFiles() {
    try {
      const res = await apiJson("GET", "/api/manuals");
      st.files = res.manuals || [];
    } catch (_) {
      st.files = [];
    }
    // 前に見ていたマニュアルが無くなっていたら先頭のものに切り替える
    if (st.files.length && (!st.name || st.files.indexOf(st.name) < 0)) st.name = st.files[0];
    if (!st.files.length) { st.name = null; st.steps = []; }
  }

  async function loadSteps() {
    st.error = "";
    if (!st.name) { st.steps = []; return; }
    try {
      const res = await apiJson("GET", `/api/manual_steps?manual=${q(st.name)}`);
      st.steps = res.steps || [];
    } catch (e) {
      st.steps = [];
      st.error = e.message;
    }
  }

  async function loadProgress(recordId) {
    if (!recordId || !st.name) { st.progress = {}; return; }
    try {
      const res = await apiJson("GET", `/api/records/${recordId}/manual_progress?manual=${q(st.name)}`);
      st.progress = res.progress || {};
    } catch (_) {
      // 進捗が取れなくても手順表は表示する
    }
  }

  function renderPanel(readOnly) {
    if (!st.files.length) {
      return `<div class="manual-empty">手順表のCSVがありません。<br>
        <code>work\\manuals\\</code> フォルダに CSV を置いてください
        （1行目は <b>区分,手順,作業内容,備考,記録内容</b>）。</div>`;
    }
    const picker = st.files.length > 1
      ? `<select class="manual-select">${st.files.map(f =>
          `<option value="${esc(f)}" ${f === st.name ? "selected" : ""}>${esc(f.replace(/\.csv$/i, ""))}</option>`
        ).join("")}</select>`
      : `<span class="manual-name">${esc((st.name || "").replace(/\.csv$/i, ""))}</span>`;

    if (st.error) {
      return `<div class="manual-panel">
        <div class="manual-head">${picker}</div>
        <div class="manual-error">⚠ マニュアルCSVを読み込めません<br>${esc(st.error)}</div>
      </div>`;
    }

    const done = st.steps.filter(s => st.progress[s.key]).length;
    const resetBtn = readOnly ? "" :
      `<button class="manual-reset" title="色と実施時刻だけを消します（記録した行は消えません）">進捗をリセット</button>`;
    const head = `<div class="manual-head">${picker}
      <span class="manual-count">${done} / ${st.steps.length} 実施済み</span>${resetBtn}</div>`;

    let body = "";
    let lastSection = null;
    st.steps.forEach((s, i) => {
      if (s.section && s.section !== lastSection) {
        body += `<tr class="manual-section"><td colspan="3">${esc(s.section)}</td></tr>`;
        lastSection = s.section;
      }
      const p = st.progress[s.key];
      const note = s.note ? `<div class="mstep-note">${esc(s.note)}</div>` : "";
      body += `<tr class="manual-step ${p ? "done" : ""}" data-idx="${i}"
        ${readOnly ? "" : `title="押すと運転記録に追加されます"`}>
        <td class="mstep-no">${esc(s.step_no)}</td>
        <td class="mstep-content">${esc(s.content)}${note}</td>
        <td class="mstep-time">${p ? esc(p.done_time) || "済" : ""}</td>
      </tr>`;
    });

    return `<div class="manual-panel ${readOnly ? "read-only-manual" : ""}">${head}
      <div class="manual-scroll"><table class="manual-table">
        <thead><tr><th>手順</th><th>作業内容</th><th>実施</th></tr></thead>
        <tbody>${body}</tbody>
      </table></div></div>`;
  }

  function bindPanel(root, ctx) {
    const sel = root.querySelector(".manual-select");
    if (sel) sel.onchange = async () => {
      st.name = sel.value;
      await loadSteps();
      await loadProgress(ctx.recordId());
      ctx.render();
    };

    if (ctx.readOnly()) return;   // 確定済み・閲覧専用は見るだけ

    const resetBtn = root.querySelector(".manual-reset");
    if (resetBtn) resetBtn.onclick = () => reset(ctx);

    root.querySelectorAll(".manual-step").forEach(tr => {
      tr.onclick = () => {
        const step = st.steps[parseInt(tr.dataset.idx, 10)];
        if (step) press(step, ctx);
      };
    });
  }

  async function press(step, ctx) {
    if (st.busy) return;
    const rid = ctx.recordId();
    if (!rid) { alert("先に運転記録を作成してください。"); return; }
    st.busy = true;
    try {
      await ctx.insertDateMarker();   // 日をまたいだら年月日の区切り行を先に入れる
      const res = await apiJson("POST", `/api/records/${rid}/manual_steps`,
        { manual: st.name, step_key: step.key, time_text: WR.nowHHMM() });
      st.progress = res.progress || st.progress;
      await ctx.reloadEntries();
      if (res.entry && res.entry.id != null) ctx.scrollTo(res.entry.id);
      ctx.render();
      const t = step.record_text || step.content;
      const label = t.length > 20 ? t.slice(0, 20) + "…" : t;
      ctx.showToast(`「${label}」を記録しました。`, "元に戻す",
        () => undo(step, res.entry ? res.entry.id : null, ctx));
    } catch (e) {
      alert("記録できませんでした。\n" + e.message);
    } finally {
      st.busy = false;
    }
  }

  async function undo(step, entryId, ctx) {
    const rid = ctx.recordId();
    if (!rid) return;
    try {
      const res = await apiJson("POST", `/api/records/${rid}/manual_steps/undo`,
        { manual: st.name, step_key: step.key, entry_id: entryId });
      st.progress = res.progress || {};
      await ctx.reloadEntries();
      ctx.render();
    } catch (e) {
      alert("元に戻せませんでした。\n" + e.message);
    }
  }

  async function reset(ctx) {
    const rid = ctx.recordId();
    if (!rid) return;
    if (!confirm("この記録のマニュアル進捗（色と実施時刻）を消しますか？\n運転記録に追加済みの行は消えません。")) return;
    try {
      await apiJson("POST", `/api/records/${rid}/manual_progress/reset`, { manual: st.name });
      st.progress = {};
      ctx.render();
    } catch (e) {
      alert("リセットできませんでした。\n" + e.message);
    }
  }

  return {
    hasFiles() { return st.files.length > 0; },
    async load(recordId) {
      await loadFiles();
      await loadSteps();
      await loadProgress(recordId);
    },
    refreshProgress: loadProgress,
    renderPanel,
    bindPanel,
  };
})();
