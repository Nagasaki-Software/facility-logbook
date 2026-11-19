(function () {
  const root = document.getElementById("history-root");
  if (!root) return;

  let state = { year: 0, month: 0, monthRecords: [], selectedDate: null,
                searchQuery: "", searchResults: null };
  const now = new Date();
  state.year = now.getFullYear();
  state.month = now.getMonth() + 1;

  async function loadMonth() {
    const { records } = await WR.api("GET", `/api/records?year=${state.year}&month=${state.month}`);
    state.monthRecords = records;
  }

  function render() {
    const days = new Date(state.year, state.month, 0).getDate();
    const firstDow = new Date(state.year, state.month - 1, 1).getDay();
    const datesWithRecords = new Set(state.monthRecords.map(r => r.record_date));

    let cells = "";
    for (let i = 0; i < firstDow; i++) cells += `<td></td>`;
    for (let d = 1; d <= days; d++) {
      const iso = `${state.year}-${String(state.month).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
      const has = datesWithRecords.has(iso);
      cells += `<td class="${has ? "has-record" : ""}" data-iso="${iso}">${d}${has ? " ●" : ""}</td>`;
    }

    const dayRecords = state.selectedDate
      ? state.monthRecords.filter(r => r.record_date === state.selectedDate)
      : [];

    let searchHtml = "";
    if (state.searchResults !== null) {
      const rs = state.searchResults;
      const items = rs.length
        ? rs.map(r => `<li><span class="rec-id">ID:${r.id}</span> ${escape(r.record_date)}　${escape(r.title || "(無題)")}${r.finalized ? ` <span class="rec-lock">🔒確定済</span>` : ""} <a href="${U(`/?record_id=${r.id}&ro=1`)}">[開く]</a></li>`).join("")
        : `<li>該当する記録は見つかりませんでした。</li>`;
      searchHtml = `<div class="search-results"><h3>検索結果（${rs.length}件）</h3><ul>${items}</ul></div>`;
    }

    root.innerHTML = `
      <div class="record-search">
        <input id="rec-search" type="search" placeholder="キーワードで過去記録を検索（タイトル・作業内容）" value="${escape(state.searchQuery || "")}">
        <button id="rec-search-btn">検索</button>
        ${state.searchResults !== null ? `<button id="rec-search-clear">クリア</button>` : ""}
      </div>
      ${searchHtml}
      <div class="cal-controls">
        <button id="prev">◀</button>
        <span>${state.year}年${state.month}月</span>
        <button id="next">▶</button>
      </div>
      <table class="calendar">
        <thead><tr><th>日</th><th>月</th><th>火</th><th>水</th><th>木</th><th>金</th><th>土</th></tr></thead>
        <tbody>${chunkRows(cells)}</tbody>
      </table>
      <div class="day-records">
        ${state.selectedDate ? `<h3>${state.selectedDate} の記録:</h3>` : ""}
        <ul>
          ${dayRecords.map(r => `<li><span class="rec-id">ID:${r.id}</span> ${escape(r.title)}${r.finalized ? ` <span class="rec-lock">🔒確定済</span>` : ""} <a href="${U(`/?record_id=${r.id}&ro=1`)}">[開く]</a> <button class="rec-delete" data-id="${r.id}">削除</button></li>`).join("")}
        </ul>
      </div>
      <div class="range-export">
        <label>期間一括: <input id="from-date" type="date"> 〜 <input id="to-date" type="date"></label>
        <button id="range-dl">ダウンロード</button>
      </div>
    `;

    const doSearch = async () => {
      const q = document.getElementById("rec-search").value.trim();
      state.searchQuery = q;
      if (!q) { state.searchResults = null; render(); return; }
      const { records } = await WR.api("GET", `/api/search?q=${encodeURIComponent(q)}`);
      state.searchResults = records;
      render();
    };
    document.getElementById("rec-search-btn").onclick = doSearch;
    document.getElementById("rec-search").onkeydown = (e) => {
      if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); doSearch(); }
    };
    const clearBtn = document.getElementById("rec-search-clear");
    if (clearBtn) clearBtn.onclick = () => { state.searchQuery = ""; state.searchResults = null; render(); };

    document.getElementById("prev").onclick = () => { shiftMonth(-1); };
    document.getElementById("next").onclick = () => { shiftMonth(1); };
    root.querySelectorAll("td[data-iso]").forEach(c => {
      c.onclick = () => { state.selectedDate = c.dataset.iso; render(); };
    });
    document.getElementById("range-dl").onclick = () => {
      const f = document.getElementById("from-date").value;
      const t = document.getElementById("to-date").value;
      if (f && t) window.location = U(`/api/export?from=${f}&to=${t}`);
    };
    root.querySelectorAll(".rec-delete").forEach(b => b.onclick = async () => {
      const rec = state.monthRecords.find(r => r.id == b.dataset.id);
      const t = rec ? rec.title : "この記録";
      if (!confirm(`「${t}」を削除します。\n記録内のすべての行も消え、元に戻せません。よろしいですか？`)) return;
      await WR.api("DELETE", `/api/records/${b.dataset.id}`);
      await loadMonth();
      render();
    });
  }

  function chunkRows(cellsHtml) {
    const tds = cellsHtml.match(/<td[^>]*>.*?<\/td>/g) || [];
    let out = "";
    for (let i = 0; i < tds.length; i += 7) {
      out += "<tr>" + tds.slice(i, i + 7).join("") + "</tr>";
    }
    return out;
  }

  async function shiftMonth(delta) {
    state.month += delta;
    if (state.month < 1) { state.month = 12; state.year -= 1; }
    if (state.month > 12) { state.month = 1; state.year += 1; }
    state.selectedDate = null;
    await loadMonth();
    render();
  }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  (async function init() {
    await loadMonth();
    render();
  })();
})();
