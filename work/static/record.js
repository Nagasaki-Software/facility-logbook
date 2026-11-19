(function () {
  const root = document.getElementById("record-root");
  if (!root) return;
  const POLLING_MS = parseInt(root.dataset.pollingMs || "3000", 10);

  let state = {
    record: null,
    entries: [],
    groups: [],
    activeGroupId: null,
    buttons: [],
    manualMode: false,        // ボタン欄に運転マニュアル（手順表）を表示中か
    editingId: null,
    insertingAfterId: null,   // null=非挿入 / "top"=先頭 / N=entry N の直後
    copyBuffer: null,         // {time_text, content}=コピー中 / null=非コピー
    scrollToEntryId: null,    // 追記後にこの行へスクロール（一度だけ）
    appendTime: { mode: "now", a: "00:00", b: "00:00" },   // 通常追記の時刻
    insertTime: null,         // 行挿入の時刻（挿入中のみ）
    connectionLost: false,    // サーバとの通信が切れているか
    filterImportant: "all",   // 表示の絞り込み: all|colored|yellow|pink
    searchText: "",           // キーワード検索（記録内）
    suggestions: [],          // 入力履歴サジェスト
    resizing: false,          // 記録／ボタンの境界をドラッグ中
    photos: [],               // この記録に添付された写真
    photosMax: 3,             // 添付できる最大枚数
    pickingFile: false,       // ファイル選択ダイアログを開いている間は自動更新を止める
    readOnlyParam: !!root.dataset.readOnly,   // 履歴の閲覧専用表示(?ro)
    finalized: false,                          // 確定済み（サーバ共有のロック）
    readOnly: !!root.dataset.readOnly,         // 実際の編集ロック = readOnlyParam || finalized
    recordIdOverride: root.dataset.recordId ? parseInt(root.dataset.recordId, 10) : null,
  };

  // 表示中レコードの確定状態から編集ロックを再計算する
  function applyRecordLock() {
    state.finalized = !!(state.record && state.record.finalized);
    state.readOnly = state.readOnlyParam || state.finalized;
  }

  // --- Top-level render ---
  function render() {
    // 組み立て途中の入力（通常の内容・挿入の内容と時刻）を再描画でも保持する
    const ae = document.activeElement;
    const prevBottom = root.querySelector('[name="content"]');
    const prevInsContent = root.querySelector('.insert-content');
    const prevTitle = root.querySelector("input.title");
    const prevSearch = root.querySelector(".entry-search");
    // 添付エリア／ボタンエリアの高さをユーザーが変えていたら控えて保存（再描画で消えないように）
    const prevAtt = root.querySelector(".attachments");
    if (prevAtt && prevAtt.style.height) {
      const ah = parseInt(prevAtt.style.height, 10);
      if (ah) WR.saveAttAreaPx(ah);
    }
    const prevPanel = root.querySelector(".button-panel");
    if (prevPanel && prevPanel.style.height) {
      const bh = parseInt(prevPanel.style.height, 10);
      if (bh) WR.saveBtnAreaPx(bh);
    }
    const prevScroll = root.querySelector('.entries-scroll');
    const savedScrollTop = prevScroll ? prevScroll.scrollTop : null;
    // マニュアル表のスクロール位置も自動更新で戻らないように控える
    const prevManual = root.querySelector('.manual-scroll');
    const savedManualTop = prevManual ? prevManual.scrollTop : null;
    const saved = {
      bottom: prevBottom ? prevBottom.value : null,
      insContent: prevInsContent ? prevInsContent.value : null,
      // タイトルはフォーカス中（編集中）のみ保持。非編集時はサーバ値で上書きさせる
      title: (ae === prevTitle && prevTitle) ? prevTitle.value : null,
      focus: ae === prevBottom ? "bottom"
           : (ae === prevInsContent ? "insert"
           : (ae === prevTitle ? "title"
           : (ae === prevSearch ? "search" : null))),
    };

    const layout = WR.loadLayoutPref();
    document.body.classList.remove("layout-bottom", "layout-right");
    document.body.classList.add("layout-" + layout);
    // テーマ（明/暗）と文字サイズを body のクラスで適用
    document.body.classList.remove("theme-light", "theme-dark");
    document.body.classList.add("theme-" + WR.loadThemePref());
    document.body.classList.remove("font-normal", "font-large", "font-xlarge");
    document.body.classList.add("font-" + WR.loadFontPref());

    let areaInner;
    if (!state.record) {
      areaInner = "<p>運転記録を開いていません。<br>新しく始めるときは「新しい記録を作成」、<br>過去の記録を見るときはページ上部の「履歴」から開いてください。</p>";
    } else if (layout === "right") {
      // 右配置：左に タイトル/運転記録/入力欄、右に 入力ボタン/添付/テンキー
      areaInner = `<div class="main-col">${renderHeader()}${renderTable()}${renderInputBar()}</div>`
                + `<div class="side-col">${renderButtonPanel()}${renderAttachments()}${renderKeypad()}</div>`;
    } else {
      // 下配置：記録とボタンの間にドラッグ用ハンドル。添付はボタンエリアの下
      const handle = state.readOnly ? "" :
        `<div class="split-handle" title="上下にドラッグして記録とボタンの広さを変えられます"></div>`;
      areaInner = renderHeader() + renderTable() + handle + renderButtonPanel()
                + renderAttachments() + renderInputBar() + renderKeypad();
    }

    const connBanner = state.connectionLost
      ? `<div class="conn-banner">⚠ サーバーとの接続が切れています。記録が保存・更新できない可能性があります（自動で再接続を試みています）。</div>`
      : "";
    const finalizedBanner = (state.finalized && !state.readOnlyParam)
      ? `<div class="finalized-banner">🔒 この記録は確定済みです。編集できません。（修正が必要な場合は管理者へ依頼してください）</div>`
      : "";

    root.innerHTML = `
      ${connBanner}
      ${finalizedBanner}
      <div class="controls">
        <button id="new-record-btn" ${state.readOnlyParam ? "disabled" : ""}>新しい記録を作成</button>
        <label>配置:
          <select id="layout-select">
            <option value="bottom">下</option>
            <option value="right">右</option>
          </select>
        </label>
        <label>テンキー:
          <select id="keypad-select">
            <option value="off">OFF</option>
            <option value="on">ON</option>
          </select>
        </label>
        <label>テーマ:
          <select id="theme-select">
            <option value="light">明るい</option>
            <option value="dark">暗い</option>
          </select>
        </label>
        <label>文字:
          <select id="font-select">
            <option value="normal">標準</option>
            <option value="large">大</option>
            <option value="xlarge">特大</option>
          </select>
        </label>
        <button id="export-btn">エクセル出力</button>
        ${state.record ? `<button id="pdf-btn" title="この記録をPDFで出力します">PDF出力</button>` : ""}
        ${state.readOnly ? "" : `<button id="backup-btn" title="今のデータを今すぐバックアップ">バックアップ</button>`}
        ${state.record && !state.readOnly ? `<button id="finish-btn">終了</button>` : ""}
      </div>
      <div id="record-area" class="${state.readOnly ? "read-only" : ""}">
        ${areaInner}
      </div>
    `;
    document.getElementById("layout-select").value = WR.loadLayoutPref();
    document.getElementById("keypad-select").value = WR.loadKeypadPref() ? "on" : "off";
    document.getElementById("theme-select").value = WR.loadThemePref();
    document.getElementById("font-select").value = WR.loadFontPref();
    bindEvents();

    // 自動更新などの再描画後に、組み立て中の文字・時刻・カーソルを復元する
    const newBottom = root.querySelector('[name="content"]');
    const newInsContent = root.querySelector('.insert-content');
    const newTitle = root.querySelector("input.title");
    const newSearch = root.querySelector(".entry-search");
    if (newBottom && saved.bottom !== null) newBottom.value = saved.bottom;
    if (newInsContent && saved.insContent !== null) newInsContent.value = saved.insContent;
    if (newTitle && saved.title !== null) newTitle.value = saved.title;
    const focusEl = saved.focus === "bottom" ? newBottom
                  : (saved.focus === "insert" ? newInsContent
                  : (saved.focus === "title" ? newTitle
                  : (saved.focus === "search" ? newSearch : null)));
    if (focusEl) {
      focusEl.focus();
      const len = focusEl.value.length;
      focusEl.setSelectionRange(len, len);
    }

    // スクロール位置：追記直後はその行へ、それ以外は元の位置を保持
    const newScroll = root.querySelector(".entries-scroll");
    if (newScroll) {
      if (state.scrollToEntryId != null) {
        scrollRowIntoView(newScroll, state.scrollToEntryId);
        state.scrollToEntryId = null;
      } else if (savedScrollTop !== null) {
        newScroll.scrollTop = savedScrollTop;
      }
    }
    const newManual = root.querySelector(".manual-scroll");
    if (newManual && savedManualTop !== null) newManual.scrollTop = savedManualTop;

    // 保存済みのボタンエリアの高さを復元（下配置・右配置の両方）
    const panel = root.querySelector(".button-panel");
    const px = WR.loadBtnAreaPx();
    if (panel && px) panel.style.height = px + "px";
    // 添付エリアの高さを復元（両レイアウト共通）
    const newAtt = root.querySelector(".attachments");
    const attPx = WR.loadAttAreaPx();
    if (newAtt && attPx) newAtt.style.height = attPx + "px";
  }

  function scrollRowIntoView(container, id) {
    const tr = container.querySelector(`tr[data-id="${id}"]`);
    if (!tr) return;
    const cRect = container.getBoundingClientRect();
    const rRect = tr.getBoundingClientRect();
    // 行をスクロール領域の中央付近へ（ページ全体は動かさない）
    container.scrollTop += (rRect.top - cRect.top) - (container.clientHeight - rRect.height) / 2;
  }

  // --- 時刻ダイヤル（タブレット向け） ---
  function pad2(n) { return String(n).padStart(2, "0"); }

  // value="HH:MM" を受け取り、時・分を上下ボタンで操作できるダイヤルUIを返す
  function timePickerHtml(extraClass, value, opts) {
    const nameAttr = (opts && opts.name) ? ` name="${opts.name}"` : "";
    const [hh, mm] = value.split(":");
    return `<div class="time-picker">
      <input type="hidden" class="tp-value ${extraClass}"${nameAttr} value="${value}">
      <div class="tp-col">
        <button type="button" class="tp-step" data-unit="h" data-delta="1">▲</button>
        <div class="tp-num tp-hh">${hh}</div>
        <button type="button" class="tp-step" data-unit="h" data-delta="-1">▼</button>
        <div class="tp-label">時</div>
      </div>
      <div class="tp-colon">:</div>
      <div class="tp-col">
        <button type="button" class="tp-step" data-unit="m" data-delta="1">▲</button>
        <div class="tp-num tp-mm">${mm}</div>
        <button type="button" class="tp-step" data-unit="m" data-delta="-1">▼</button>
        <div class="tp-label">分</div>
      </div>
      <div class="tp-quick">
        <button type="button" class="tp-q" data-delta="-5">−5分</button>
        <button type="button" class="tp-q" data-delta="5">+5分</button>
        <button type="button" class="tp-now">今すぐ</button>
      </div>
    </div>`;
  }

  function syncTimePicker(picker) {
    const hidden = picker.querySelector(".tp-value");
    const [hh, mm] = (hidden.value || "00:00").split(":");
    picker.querySelector(".tp-hh").textContent = hh;
    picker.querySelector(".tp-mm").textContent = mm;
  }

  function bindOneTimePicker(picker, onChange) {
    const hidden = picker.querySelector(".tp-value");
    const setHM = (h, m) => {
      hidden.value = pad2(h) + ":" + pad2(m);
      syncTimePicker(picker);
      if (onChange) onChange(hidden.value);
    };
    picker.querySelectorAll(".tp-step").forEach(btn => {
      btn.onclick = () => {
        let [h, m] = hidden.value.split(":").map(Number);
        const delta = parseInt(btn.dataset.delta, 10);
        if (btn.dataset.unit === "h") h = (h + delta + 24) % 24;
        else m = (m + delta + 60) % 60;
        setHM(h, m);
      };
    });
    picker.querySelectorAll(".tp-q").forEach(btn => {
      btn.onclick = () => {
        let [h, m] = hidden.value.split(":").map(Number);
        const total = (h * 60 + m + parseInt(btn.dataset.delta, 10) + 1440) % 1440;
        setHM(Math.floor(total / 60), total % 60);
      };
    });
    const nowBtn = picker.querySelector(".tp-now");
    if (nowBtn) nowBtn.onclick = () => {
      const [h, m] = WR.nowHHMM().split(":").map(Number);
      setHM(h, m);
    };
  }

  // --- 時刻コントロール（今すぐ / 指定 / 範囲 / なし） ---
  const TIME_MODES = [["now", "今すぐ"], ["single", "指定"], ["range", "範囲"], ["blank", "なし"]];

  function timeControlHtml(cls, tc) {
    const modes = TIME_MODES.map(([m, l]) =>
      `<button type="button" class="tc-mode ${tc.mode === m ? "active" : ""}" data-mode="${m}">${l}</button>`
    ).join("");
    let body;
    if (tc.mode === "single") body = timePickerHtml("tc-a", tc.a);
    else if (tc.mode === "range") body = `${timePickerHtml("tc-a", tc.a)}<span class="tc-tilde">～</span>${timePickerHtml("tc-b", tc.b)}`;
    else if (tc.mode === "now") body = `<span class="now-time">🕒 <span class="now-time-val">${WR.nowHHMM()}</span></span>`;
    else body = `<span class="tc-blank">（時刻なし）</span>`;
    return `<div class="time-control ${cls}"><div class="tc-modes">${modes}</div><div class="tc-body">${body}</div></div>`;
  }

  function timeFromControl(tc) {
    if (tc.mode === "single") return tc.a;
    if (tc.mode === "range") return `${tc.a}～${tc.b}`;
    if (tc.mode === "blank") return "";
    return WR.nowHHMM();   // now
  }

  function bindTimeControl(container, tc) {
    container.querySelectorAll(".tc-mode").forEach(btn => {
      btn.onclick = () => {
        const m = btn.dataset.mode;
        // 「指定」「範囲」に切り替えた時は現在時刻で初期化（範囲は開始・終了の両方）
        if (m === "single") { tc.a = WR.nowHHMM(); }
        else if (m === "range") { tc.a = WR.nowHHMM(); tc.b = WR.nowHHMM(); }
        tc.mode = m;
        render();
      };
    });
    container.querySelectorAll(".time-picker").forEach(picker => {
      const hidden = picker.querySelector(".tp-value");
      const key = hidden.classList.contains("tc-b") ? "b" : "a";
      bindOneTimePicker(picker, (val) => { tc[key] = val; });
    });
  }

  // クイックボタンの入力先：行挿入中は挿入欄、それ以外は下部の入力欄
  function activeContentInput() {
    return root.querySelector(".insert-content") || root.querySelector('[name="content"]');
  }

  // --- テンプレートボタン（{ } の空欄を後から数値入力） ---
  const TEMPLATE_RE = /\{[^}]*\}/;

  function isTemplate(label) { return TEMPLATE_RE.test(label); }

  // template 内の {…} を values[] で順番に置き換える
  function fillTemplate(template, values) {
    let i = 0;
    return template.replace(/\{[^}]*\}/g, () => (values[i++] ?? ""));
  }

  function appendToActiveContent(text) {
    const ci = activeContentInput();
    if (!ci) return;
    ci.value += text;
    ci.focus();
  }

  // テンプレート入力ダイアログ（テンキー付き）を開く
  function openTemplateDialog(template) {
    const names = [];
    template.replace(/\{([^}]*)\}/g, (_m, n) => { names.push(n); return _m; });

    const overlay = document.createElement("div");
    overlay.className = "tpl-overlay";
    const fields = names.map((n, i) =>
      `<label class="tpl-field"><span>${escape(n || ("値" + (i + 1)))}</span>` +
      `<input class="tpl-input" data-idx="${i}" inputmode="decimal" autocomplete="off"></label>`
    ).join("");
    const keys = ["7","8","9","4","5","6","1","2","3","0",".","⌫"];
    overlay.innerHTML = `
      <div class="tpl-box">
        <div class="tpl-title">数値を入力してください</div>
        <div class="tpl-fields">${fields}</div>
        <div class="tpl-preview"></div>
        <div class="tpl-keypad">
          ${keys.map(k => `<button type="button" data-key="${k}">${k}</button>`).join("")}
        </div>
        <div class="tpl-actions">
          <button type="button" class="tpl-ok">確定</button>
          <button type="button" class="tpl-cancel">取消</button>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const inputs = Array.from(overlay.querySelectorAll(".tpl-input"));
    const preview = overlay.querySelector(".tpl-preview");
    let focused = inputs[0] || null;
    if (focused) focused.focus();

    const updatePreview = () => {
      preview.textContent = "→ " + fillTemplate(template, inputs.map(i => i.value));
    };
    updatePreview();

    const close = () => overlay.remove();
    const confirm = () => { appendToActiveContent(fillTemplate(template, inputs.map(i => i.value))); close(); };

    inputs.forEach(inp => {
      inp.addEventListener("focus", () => { focused = inp; });
      inp.addEventListener("input", updatePreview);
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); confirm(); }
        else if (e.key === "Escape") { e.preventDefault(); close(); }
      });
    });
    overlay.querySelectorAll(".tpl-keypad button").forEach(b => {
      b.onclick = () => {
        const tgt = focused || inputs[0];
        if (!tgt) return;
        if (b.dataset.key === "⌫") tgt.value = tgt.value.slice(0, -1);
        else tgt.value += b.dataset.key;
        tgt.focus();
        updatePreview();
      };
    });
    overlay.querySelector(".tpl-ok").onclick = confirm;
    overlay.querySelector(".tpl-cancel").onclick = close;
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) close(); });
  }

  function renderHeader() {
    const r = state.record;
    return `
      <div class="record-header">
        <span class="rec-id" title="記録ID（確定解除の際に使用）">ID:${r.id}</span>
        <input class="title" value="${escape(r.title)}" ${state.readOnly ? "disabled" : ""}>
        <span class="date" title="クリックで日付変更">${WR.formatJpDate(r.record_date)}📅</span>
      </div>
    `;
  }

  // ファイル全体への添付写真（最大3枚）。記録にはハイパーリンクだけ表示する
  function renderAttachments() {
    if (!state.record) return "";
    const photos = state.photos || [];
    const max = state.photosMax || 3;
    const items = photos.map(p => {
      const label = (p.memo && p.memo.trim()) ? p.memo : (p.original_name || "写真");
      const editMemo = state.readOnly ? "" : `<button class="att-memo" data-id="${p.id}">メモ編集</button>`;
      const del = state.readOnly ? "" : `<button class="att-del" data-id="${p.id}" title="削除">×</button>`;
      return `<li>
        🔗 <a class="att-link" href="${U(p.url)}" target="_blank" rel="noopener">${escape(label)}</a>
        <a class="att-dl" href="${U(p.download_url)}">⬇ ダウンロード</a>
        ${editMemo}${del}
      </li>`;
    }).join("");
    let adder = "";
    if (!state.readOnly && photos.length < max) {
      adder = `<div class="att-add">
        <input type="text" class="att-memo-input" placeholder="メモ（任意・先に入力可）" maxlength="100">
        <input type="file" class="att-file" accept="image/*">
        <span class="att-hint">ファイルを選ぶと自動で添付されます</span>
      </div>`;
    } else if (!state.readOnly) {
      adder = `<div class="att-full">添付は${max}枚までです。追加するには既存の写真を削除してください。</div>`;
    }
    return `<div class="attachments">
      <div class="att-title">📎 添付写真（${photos.length}/${max}）</div>
      <ul class="att-list">${items}</ul>
      ${adder}
    </div>`;
  }

  function renderInsertRow() {
    if (!state.insertTime) state.insertTime = { mode: "single", a: WR.nowHHMM(), b: WR.nowHHMM() };
    return `<tr class="inserting"><td colspan="3">
      <div class="insert-form">
        ${timeControlHtml("tc-insert", state.insertTime)}
        <textarea class="insert-content" rows="2" placeholder="作業内容（ボタンでも入力可。Shift+Enterで改行）" inputmode="${WR.loadKeypadPref() ? "none" : "text"}"></textarea>
        <button class="save-insert">挿入</button>
        <button class="cancel-insert">取消</button>
      </div>
    </td></tr>`;
  }

  // 絞り込み判定：色（重要度）＋キーワード検索の両方を満たすか
  function entryMatchesFilter(e) {
    const f = state.filterImportant;
    if (f === "colored" && !((e.is_important || 0) > 0)) return false;
    if (f === "yellow" && e.is_important !== 1) return false;
    if (f === "pink" && e.is_important !== 2) return false;
    const q = (state.searchText || "").trim().toLowerCase();
    if (q) {
      const hay = ((e.content || "") + " " + (e.time_text || "")).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  }

  function renderTable() {
    let body = "";
    if (!state.readOnly && state.insertingAfterId === "top") body += renderInsertRow();
    state.entries.forEach(e => {
      if (!entryMatchesFilter(e)) return;  // 絞り込みで対象外は表示しない
      const editing = e.id === state.editingId;
      const hl = e.is_important === 1 ? "important " : (e.is_important === 2 ? "important2 " : "");
      const cls = hl + (editing ? "editing" : "");
      if (editing) {
        body += `<tr class="${cls}">
          <td class="time"><input class="edit-time" value="${escape(e.time_text)}"></td>
          <td><textarea class="edit-content" rows="2">${escape(e.content)}</textarea></td>
          <td class="actions">
            <button class="save-edit" data-id="${e.id}">保存</button>
            <button class="cancel-edit">取消</button>
          </td>
        </tr>`;
      } else {
        body += `<tr class="${cls}" data-id="${e.id}">
          <td class="time">${escape(e.time_text)}</td>
          <td class="content">${escape(e.content)}</td>
          <td class="actions">
            <button class="action edit-btn"      data-id="${e.id}">✎</button>
            <button class="action important-btn" data-id="${e.id}">${e.is_important ? "★" : "☆"}</button>
            <button class="action copy-btn"      data-id="${e.id}" title="この行をコピー">📋</button>
            <button class="action insert-btn"    data-id="${e.id}" title="この行の下に挿入">⤵</button>
            <button class="action delete-btn"    data-id="${e.id}">×</button>
          </td>
        </tr>`;
      }
      if (!state.readOnly && state.insertingAfterId === e.id) body += renderInsertRow();
    });
    const topBar = state.readOnly ? "" :
      `<div class="insert-top-bar"><button id="insert-top-btn">＋ 先頭に行を挿入</button></div>`;
    let banner = "";
    if (!state.readOnly && state.copyBuffer) {
      const full = state.copyBuffer.content || "（内容なし）";
      const preview = full.slice(0, 30) + (full.length > 30 ? "…" : "");
      banner = `<div class="copy-banner">📋 コピー中：「${escape(preview)}」 — 挿入したい場所の <b>⤵</b> か「先頭に行を挿入」を押してください
        <button id="copy-cancel-btn">取消</button></div>`;
    }
    const f = state.filterImportant;
    const fbtn = (val, label) => `<button class="filter-btn ${f === val ? "active" : ""}" data-f="${val}">${label}</button>`;
    const sc = escape(state.searchText || "");
    const toolbar = `<div class="table-toolbar">
      <span class="ttl-label">表示:</span>
      ${fbtn("all", "すべて")}${fbtn("colored", "色付き")}${fbtn("yellow", "黄")}${fbtn("pink", "ピンク")}
      <span class="ttl-search">🔍 <input type="search" class="entry-search" placeholder="記録内をキーワード検索" value="${sc}">
        ${state.searchText ? `<button class="entry-search-clear" title="検索をクリア">×</button>` : ""}</span>
      ${state.readOnly ? "" : `<button id="sort-time-btn" title="時刻なしの行を境にして時刻順へ並べ替え">時刻順に並べ替え</button>`}
    </div>`;
    return `${banner}${topBar}${toolbar}<div class="entries-scroll"><table class="entries">
      <thead><tr><th>時刻</th><th>作業内容</th><th>操作</th></tr></thead>
      <tbody>${body}</tbody>
    </table></div>`;
  }

  function renderButtonPanel() {
    const hasManual = WRManual.hasFiles();
    // 確定済み・閲覧専用では入力ボタンは隠すが、マニュアルは進捗の確認用に見せる（押せない）
    if (state.readOnly) {
      if (!hasManual) return "";
      return `<div class="button-panel manual-open">
        <div class="group-tabs"><button class="group-tab manual-tab active">📋 マニュアル</button></div>
        ${WRManual.renderPanel(true)}
      </div>`;
    }
    const tabs = state.groups.map(g =>
      `<button class="group-tab ${(!state.manualMode && g.id === state.activeGroupId) ? "active" : ""}" data-id="${g.id}">${escape(g.name)}</button>`
    ).join("")
    + (hasManual ? `<button class="group-tab manual-tab ${state.manualMode ? "active" : ""}">📋 マニュアル</button>` : "");
    const body = (state.manualMode && hasManual)
      ? WRManual.renderPanel(false)
      : `<div class="grid">${state.buttons.map(b =>
          `<button class="quick-btn ${b.is_pinned ? "pinned" : ""}" data-id="${b.id}" data-label="${escape(b.label)}">${escape(b.label)}</button>`
        ).join("")}</div>`;
    return `<div class="button-panel ${(state.manualMode && hasManual) ? "manual-open" : ""}">
      <div class="group-tabs">${tabs}</div>
      ${body}
    </div>`;
  }

  // マニュアル側から記録の追加・再描画・トーストを使うための受け渡し口
  function manualCtx() {
    return {
      recordId: () => state.record ? state.record.id : null,
      readOnly: () => state.readOnly,
      render: () => render(),
      reloadEntries: () => reloadEntries(),
      showToast: (msg, label, fn) => showToast(msg, label, fn),
      scrollTo: (id) => { state.scrollToEntryId = id; },
      insertDateMarker: () => insertDateMarkerIfDayChanged(),
    };
  }

  function renderInputBar() {
    if (state.readOnly) return "";
    const sugg = (state.suggestions || []);
    const suggSel = sugg.length ? `<select class="suggest-select" title="過去の入力から選ぶ">
        <option value="">履歴から…</option>
        ${sugg.map(s => `<option value="${escape(s)}">${escape(s.length > 30 ? s.slice(0, 30) + "…" : s)}</option>`).join("")}
      </select>` : "";
    return `<div class="input-bar">
      ${timeControlHtml("tc-append", state.appendTime)}
      <textarea name="content" rows="2" placeholder="作業内容（ボタンでも入力可。Enterで追記 / Shift+Enterで改行 / Escで取消）" inputmode="${WR.loadKeypadPref() ? "none" : "text"}"></textarea>
      ${suggSel}
      <button id="append-btn">追記</button>
      <button id="clear-content-btn">消去</button>
    </div>`;
  }

  function renderKeypad() {
    const on = WR.loadKeypadPref();
    const keys = ["7","8","9","4","5","6","1","2","3","0",":","⌫"];
    return `<div class="keypad ${on ? "on" : ""}" id="keypad">
      ${keys.map(k => `<button data-key="${k}">${k}</button>`).join("")}
    </div>`;
  }

  function bindEvents() {
    document.getElementById("layout-select").onchange = e => {
      WR.saveLayoutPref(e.target.value); render();
    };
    document.getElementById("keypad-select").onchange = e => {
      WR.saveKeypadPref(e.target.value === "on"); render();
    };
    document.getElementById("theme-select").onchange = e => {
      WR.saveThemePref(e.target.value); render();
    };
    document.getElementById("font-select").onchange = e => {
      WR.saveFontPref(e.target.value); render();
    };
    document.getElementById("new-record-btn").onclick = onNewRecord;
    document.getElementById("export-btn").onclick = () => {
      if (state.record) window.location = U(`/api/records/${state.record.id}/export`);
    };
    // PDF出力：Excelと同じ体裁のPDFをサーバーで生成してダウンロードする
    const pdfBtn = document.getElementById("pdf-btn");
    if (pdfBtn) pdfBtn.onclick = () => {
      if (state.record) window.location = U(`/api/records/${state.record.id}/pdf`);
    };
    // 手動バックアップ：今のデータを即座に backup フォルダへ保存
    const backupBtn = document.getElementById("backup-btn");
    if (backupBtn) backupBtn.onclick = async () => {
      try {
        const res = await WR.api("POST", "/api/backup", {});
        alert("バックアップしました：" + (res && res.filename ? res.filename : "完了"));
      } catch {
        alert("バックアップに失敗しました。");
      }
    };
    // 終了：一連の作業が終わったら運転記録を閉じ、初期画面に戻る（記録は保存済み）
    const finishBtn = document.getElementById("finish-btn");
    if (finishBtn) finishBtn.onclick = async () => {
      if (!confirm("この運転記録を確定して終了しますか？\n確定すると全員の画面で編集できなくなります（修正が必要な場合は管理者のみ可能）。")) return;
      try {
        if (state.record) await WR.api("POST", `/api/records/${state.record.id}/finish`);
      } catch {
        alert("確定に失敗しました。通信状態を確認してください。");
        return;
      }
      state.record = null;
      state.entries = [];
      state.photos = [];
      state.editingId = null;
      state.insertingAfterId = null;
      state.insertTime = null;
      state.copyBuffer = null;
      applyRecordLock();
      render();
    };
    if (!state.record) return;

    const title = root.querySelector("input.title");
    if (title) title.onchange = () => updateHeader({ title: title.value });
    const date = root.querySelector(".record-header .date");
    if (date) date.onclick = () => {
      if (state.readOnly) return;
      const v = prompt("記録日 (YYYY-MM-DD):", state.record.record_date);
      if (v) updateHeader({ record_date: v });
    };

    // 絞り込み（色）と時刻順並べ替え
    root.querySelectorAll(".filter-btn").forEach(b => {
      b.onclick = () => { state.filterImportant = b.dataset.f; render(); };
    });
    const sortBtn = document.getElementById("sort-time-btn");
    if (sortBtn) sortBtn.onclick = () => sortEntriesByTime();

    // キーワード検索（記録内）
    const searchInput = root.querySelector(".entry-search");
    if (searchInput) searchInput.oninput = () => { state.searchText = searchInput.value; render(); };
    const searchClear = root.querySelector(".entry-search-clear");
    if (searchClear) searchClear.onclick = () => { state.searchText = ""; render(); };

    // 入力履歴サジェスト：選ぶと作業内容に追記
    const suggestSel = root.querySelector(".suggest-select");
    if (suggestSel) suggestSel.onchange = () => {
      if (suggestSel.value) { appendToActiveContent(suggestSel.value); suggestSel.value = ""; }
    };

    // 記録／ボタンの境界ドラッグ（下配置）
    bindSplitHandle();

    // 添付エリア／ボタンエリアの高さドラッグ中（リサイズ）は自動更新を止める
    const attBox = root.querySelector(".attachments");
    if (attBox) attBox.addEventListener("pointerdown", () => { state.resizing = true; });
    const panelBox = root.querySelector(".button-panel");
    if (panelBox) panelBox.addEventListener("pointerdown", () => { state.resizing = true; });

    // 添付写真（ファイル全体）：ファイルを選んだら自動アップロード
    const attFileInput = root.querySelector(".att-file");
    if (attFileInput) {
      attFileInput.onfocus = () => { state.pickingFile = true; };  // 選択ダイアログ中は自動更新を止める
      attFileInput.onchange = (e) => uploadRecordPhoto(e.target);
    }
    root.querySelectorAll(".att-del").forEach(b => {
      b.onclick = () => deleteRecordPhoto(parseInt(b.dataset.id, 10));
    });
    root.querySelectorAll(".att-memo").forEach(b => {
      b.onclick = () => editRecordPhotoMemo(parseInt(b.dataset.id, 10));
    });

    // 時刻コントロール（追記欄・挿入欄）
    const appendCtl = root.querySelector(".tc-append");
    if (appendCtl) bindTimeControl(appendCtl, state.appendTime);
    const insertCtl = root.querySelector(".tc-insert");
    if (insertCtl && state.insertTime) bindTimeControl(insertCtl, state.insertTime);

    root.querySelectorAll(".quick-btn").forEach(b => {
      // クイックボタン：{ } を含むテンプレートは数値入力ダイアログ、通常はそのまま追記
      b.onclick = () => {
        const label = b.dataset.label;
        if (isTemplate(label)) openTemplateDialog(label);
        else appendToActiveContent(label);
      };
      b.oncontextmenu = e => { e.preventDefault(); togglePin(parseInt(b.dataset.id, 10)); };
    });
    root.querySelectorAll(".group-tab").forEach(t => {
      if (t.classList.contains("manual-tab")) return;   // マニュアルタブは下で別に処理する
      t.onclick = () => {
        state.manualMode = false;
        state.activeGroupId = parseInt(t.dataset.id, 10);
        reloadButtons();
      };
    });
    // 運転マニュアル（手順表）タブ
    const manualTab = root.querySelector(".group-tab.manual-tab");
    if (manualTab && !state.readOnly) {
      manualTab.onclick = () => { state.manualMode = true; render(); };
    }
    if ((state.manualMode || state.readOnly) && WRManual.hasFiles()) {
      WRManual.bindPanel(root, manualCtx());
    }
    root.querySelectorAll(".edit-btn").forEach(b => {
      b.onclick = () => { state.editingId = parseInt(b.dataset.id, 10); render(); };
    });
    root.querySelectorAll(".important-btn").forEach(b => {
      b.onclick = () => toggleImportant(parseInt(b.dataset.id, 10));
    });
    root.querySelectorAll(".copy-btn").forEach(b => {
      b.onclick = () => copyEntry(parseInt(b.dataset.id, 10));
    });
    root.querySelectorAll(".delete-btn").forEach(b => {
      // 確認ダイアログの代わりに「元に戻す」トーストで取り消せるようにする
      b.onclick = () => deleteEntry(parseInt(b.dataset.id, 10));
    });
    root.querySelectorAll(".save-edit").forEach(b => {
      b.onclick = () => saveEdit(parseInt(b.dataset.id, 10));
    });
    root.querySelectorAll(".cancel-edit").forEach(b => {
      b.onclick = () => { state.editingId = null; render(); };
    });
    // 編集行: Enterで保存 / Escで取消
    root.querySelectorAll(".edit-time, .edit-content").forEach(inp => {
      inp.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); saveEdit(state.editingId); }  // Shift+Enterは改行 / IME変換中は確定しない
        else if (e.key === "Escape") { e.preventDefault(); state.editingId = null; render(); }
      };
    });

    // 行挿入（記入漏れの追記）
    const startInsert = (after) => {
      state.insertingAfterId = after;
      state.insertTime = { mode: "single", a: WR.nowHHMM(), b: WR.nowHHMM() };  // 既定は時刻指定
      render();
    };
    const cancelInsert = () => { state.insertingAfterId = null; state.insertTime = null; render(); };
    root.querySelectorAll(".insert-btn").forEach(b => {
      const id = parseInt(b.dataset.id, 10);
      // コピー中はこの行の直後に貼り付け、そうでなければ挿入フォームを開く
      b.onclick = () => state.copyBuffer ? pasteCopy(id) : startInsert(id);
    });
    const insertTopBtn = document.getElementById("insert-top-btn");
    if (insertTopBtn) insertTopBtn.onclick = () =>
      state.copyBuffer ? pasteCopy(0) : startInsert("top");
    const copyCancelBtn = document.getElementById("copy-cancel-btn");
    if (copyCancelBtn) copyCancelBtn.onclick = () => { state.copyBuffer = null; render(); };
    root.querySelectorAll(".save-insert").forEach(b => {
      b.onclick = () => saveInsert();
    });
    root.querySelectorAll(".cancel-insert").forEach(b => {
      b.onclick = () => cancelInsert();
    });
    // 挿入行: Enterで挿入 / Escで取消
    root.querySelectorAll(".insert-content").forEach(inp => {
      inp.onkeydown = (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); saveInsert(); }  // Shift+Enterは改行 / IME変換中は確定しない
        else if (e.key === "Escape") { e.preventDefault(); cancelInsert(); }
      };
    });

    const appendBtn = document.getElementById("append-btn");
    if (appendBtn) appendBtn.onclick = () => doAppend();

    // 追記前に、入力した作業内容を消去する
    const clearContentBtn = document.getElementById("clear-content-btn");
    if (clearContentBtn) clearContentBtn.onclick = () => {
      const ci = root.querySelector('[name="content"]');
      if (ci) { ci.value = ""; ci.focus(); }
    };

    // 通常入力欄: Enterで追記 / Escで内容クリア（取り消し）
    const bottomContent = root.querySelector('[name="content"]');
    if (bottomContent) bottomContent.onkeydown = (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); doAppend(); }   // Shift+Enterは改行 / IME変換中は確定しない
      else if (e.key === "Escape") { e.preventDefault(); bottomContent.value = ""; }
    };

    // Keypad
    root.querySelectorAll("#keypad button").forEach(b => {
      b.onclick = () => {
        const focused = document.activeElement;
        if (!focused || (focused.tagName !== "INPUT" && focused.tagName !== "TEXTAREA")) return;
        const k = b.dataset.key;
        if (k === "⌫") focused.value = focused.value.slice(0, -1);
        else focused.value += k;
      };
    });
  }

  // 記録とボタンエリアの境界をドラッグして広さを変える（下配置・マウス/タッチ対応）
  function bindSplitHandle() {
    const handle = root.querySelector(".split-handle");
    const panel = root.querySelector(".button-panel");
    if (!handle || !panel) return;
    handle.onpointerdown = (e) => {
      e.preventDefault();
      state.resizing = true;
      try { handle.setPointerCapture(e.pointerId); } catch (_) {}
      const startY = e.clientY;
      const startH = panel.getBoundingClientRect().height;
      const onMove = (ev) => {
        let h = startH + (startY - ev.clientY);   // 上にドラッグ→ボタン領域を広く（記録を狭く）
        h = Math.max(60, Math.min(h, window.innerHeight - 160));
        panel.style.height = h + "px";
      };
      const onUp = () => {
        handle.removeEventListener("pointermove", onMove);
        handle.removeEventListener("pointerup", onUp);
        handle.removeEventListener("pointercancel", onUp);
        state.resizing = false;
        WR.saveBtnAreaPx(parseInt(panel.style.height, 10) || Math.round(startH));
      };
      handle.addEventListener("pointermove", onMove);
      handle.addEventListener("pointerup", onUp);
      handle.addEventListener("pointercancel", onUp);
    };
  }

  async function reloadSuggestions() {
    try {
      const res = await WR.api("GET", "/api/content_suggestions");
      state.suggestions = res.suggestions || [];
    } catch (_) {}
  }

  // --- API actions ---
  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  async function onNewRecord() {
    const title = prompt("タイトル:", "");
    if (title === null) return;
    const date = prompt("記録日 (YYYY-MM-DD):", WR.todayISO());
    if (!date) return;
    const rec = await WR.api("POST", "/api/records", { title, record_date: date });
    state.record = rec;
    state.editingId = null;
    await reloadEntries();
    await reloadPhotos();
    await WRManual.refreshProgress(rec.id);   // 新しい記録なので進捗はゼロから
    render();
  }

  async function updateHeader(patch) {
    const merged = { title: state.record.title, record_date: state.record.record_date, ...patch };
    state.record = await WR.api("PATCH", `/api/records/${state.record.id}`, merged);
    render();
  }

  async function appendEntry(time_text, content) {
    const row = await WR.api("POST", `/api/records/${state.record.id}/entries`, { time_text, content });
    state.entries.push(row);
    if (row && row.id != null) state.scrollToEntryId = row.id;
    render();
  }

  async function doAppend() {
    const contentInput = root.querySelector('[name="content"]');
    if (!contentInput) return;
    const c = contentInput.value;
    if (!c) return;
    const t = timeFromControl(state.appendTime);   // 今すぐ / 指定 / 範囲 / なし
    contentInput.value = "";                         // 組み立てた文章をクリア
    state.appendTime = { mode: "now", a: WR.nowHHMM(), b: WR.nowHHMM() };  // 次に備えて「今すぐ」へ戻す
    await insertDateMarkerIfDayChanged();            // 記録中に日が変わったら年月日の行を先に入れる
    await appendEntry(t, c);
    reloadSuggestions();                             // 入力履歴を更新（次回の候補に反映）
  }

  // 直前の記録の日付と今日が違えば、新しい日の最初の記録の前に「年月日」の行を挿入する
  async function insertDateMarkerIfDayChanged() {
    const today = WR.todayISO();
    const last = state.entries[state.entries.length - 1];
    const prevDate = (last && last.created_at)
      ? last.created_at.slice(0, 10)
      : (state.record ? state.record.record_date : today);
    if (prevDate && prevDate !== today) {
      await appendEntry("", `―― ${WR.formatJpDate(today)} ――`);  // 時刻なし・年月日のみの区切り行
    }
  }

  async function saveInsert() {
    const contentEl = root.querySelector(".insert-content");
    if (!contentEl || !state.insertTime) return;
    const t = timeFromControl(state.insertTime);
    const c = contentEl.value;
    if (!c) { alert("作業内容を入力してください。"); return; }
    const after = state.insertingAfterId === "top" ? 0 : state.insertingAfterId;
    const newRow = await WR.api("POST", `/api/records/${state.record.id}/entries`,
                                { time_text: t, content: c, after_id: after });
    state.insertingAfterId = null;
    state.insertTime = null;
    if (newRow && newRow.id != null) state.scrollToEntryId = newRow.id;
    await reloadEntries();
    reloadSuggestions();
    render();
  }

  async function saveEdit(eid) {
    const t = root.querySelector(".edit-time").value;
    const c = root.querySelector(".edit-content").value;
    try {
      await WR.api("PATCH", `/api/entries/${eid}`, { time_text: t, content: c });
      state.editingId = null;
      await reloadEntries();
      render();
    } catch (e) {
      if (String(e.message) === "404") {
        // 行が見つからない＝他の人が削除した
        alert("この行は他の人が削除しました。");
        state.editingId = null;
        await reloadEntries();
        render();
      } else {
        // 通信エラーなどは編集状態を保持して再試行できるようにする
        alert("保存に失敗しました。通信状態を確認して、もう一度お試しください。");
      }
    }
  }

  async function toggleImportant(eid) {
    const row = state.entries.find(e => e.id === eid);
    if (!row) return;
    const next = ((row.is_important || 0) + 1) % 3;   // 白→黄→ピンク→白
    await WR.api("PATCH", `/api/entries/${eid}/important`, { level: next });
    row.is_important = next;
    render();
  }

  // 行をコピー：内容・時刻を控えておき、挿入位置はあとで選ばせる
  function copyEntry(eid) {
    const row = state.entries.find(e => e.id === eid);
    if (!row) return;
    state.copyBuffer = { time_text: row.time_text, content: row.content };
    state.insertingAfterId = null;   // 挿入フォームが開いていたら閉じる
    state.insertTime = null;
    render();
  }

  // コピーした行を任意の位置へ貼り付け（after: 0=先頭 / N=entry N の直後）
  async function pasteCopy(after) {
    if (!state.copyBuffer) return;
    const newRow = await WR.api("POST", `/api/records/${state.record.id}/entries`,
      { time_text: state.copyBuffer.time_text, content: state.copyBuffer.content, after_id: after });
    state.copyBuffer = null;
    if (newRow && newRow.id != null) state.scrollToEntryId = newRow.id;
    await reloadEntries();
    render();
  }

  // --- 削除の取り消し（トースト） ---
  let undoTimer = null;
  function showToast(message, actionLabel, onAction) {
    const old = document.getElementById("wr-toast");
    if (old) old.remove();
    if (undoTimer) { clearTimeout(undoTimer); undoTimer = null; }
    const toast = document.createElement("div");
    toast.id = "wr-toast";
    toast.className = "wr-toast";
    const span = document.createElement("span");
    span.textContent = message;
    toast.appendChild(span);
    if (actionLabel && onAction) {
      const btn = document.createElement("button");
      btn.textContent = actionLabel;
      btn.onclick = () => {
        toast.remove();
        if (undoTimer) { clearTimeout(undoTimer); undoTimer = null; }
        onAction();
      };
      toast.appendChild(btn);
    }
    document.body.appendChild(toast);
    undoTimer = setTimeout(() => { toast.remove(); undoTimer = null; }, 7000);
  }

  async function deleteEntry(eid) {
    const idx = state.entries.findIndex(e => e.id === eid);
    if (idx < 0) return;
    const row = state.entries[idx];
    // 復元のため、内容と「直前の行ID（先頭なら0）」を控えておく
    const snapshot = {
      time_text: row.time_text, content: row.content,
      is_important: row.is_important || 0,
      prevId: idx > 0 ? state.entries[idx - 1].id : 0,
    };
    await WR.api("DELETE", `/api/entries/${eid}`);
    state.entries = state.entries.filter(e => e.id !== eid);
    render();
    showToast("1件削除しました。", "元に戻す", () => undoDeleteEntry(snapshot));
  }

  async function undoDeleteEntry(snap) {
    // 元の位置（直前の行の後ろ）に同じ内容で作り直す
    const newRow = await WR.api("POST", `/api/records/${state.record.id}/entries`,
      { time_text: snap.time_text, content: snap.content, after_id: snap.prevId });
    if (snap.is_important && newRow && newRow.id != null) {
      await WR.api("PATCH", `/api/entries/${newRow.id}/important`, { level: snap.is_important });
    }
    if (newRow && newRow.id != null) state.scrollToEntryId = newRow.id;
    await reloadEntries();
    render();
  }

  // --- 時刻順に並べ替え（時刻なしの行を境界にして、その間だけ並べ替える） ---
  function parseStartMinutes(timeText) {
    const m = String(timeText || "").match(/^(\d{1,2}):(\d{2})/);  // 先頭の HH:MM（範囲は開始時刻）
    if (!m) return null;
    return parseInt(m[1], 10) * 60 + parseInt(m[2], 10);
  }

  async function sortEntriesByTime() {
    const list = state.entries;
    const order = list.map(e => e.id);
    let i = 0;
    while (i < list.length) {
      if (parseStartMinutes(list[i].time_text) === null) { i++; continue; }  // 境界はそのまま
      let j = i;
      const run = [];
      while (j < list.length && parseStartMinutes(list[j].time_text) !== null) {
        run.push({ id: list[j].id, key: parseStartMinutes(list[j].time_text), pos: j });
        j++;
      }
      run.sort((a, b) => (a.key - b.key) || (a.pos - b.pos));  // 同時刻は元の順を保つ（安定）
      for (let k = 0; k < run.length; k++) order[i + k] = run[k].id;
      i = j;
    }
    if (order.every((id, idx) => id === list[idx].id)) return;  // 変化なしなら送らない
    await WR.api("POST", `/api/records/${state.record.id}/entries/reorder`, { ordered_ids: order });
    await reloadEntries();
    render();
  }

  async function togglePin(bid) {
    const btn = state.buttons.find(b => b.id === bid);
    if (!btn) return;
    await WR.api("PATCH", `/api/buttons/${bid}/pin`, { pinned: !btn.is_pinned });
    await reloadButtons();
  }

  async function reloadEntries() {
    if (!state.record) return;
    const { entries } = await WR.api("GET", `/api/records/${state.record.id}/entries`);
    state.entries = entries;
  }

  // --- 添付写真（ファイル全体） ---
  async function reloadPhotos() {
    if (!state.record) { state.photos = []; return; }
    const res = await WR.api("GET", `/api/records/${state.record.id}/photos`);
    state.photos = res.photos || [];
    state.photosMax = res.max || 3;
  }

  // ファイル選択枠から直接読み取る（再描画で枠が差し替わっても確実に取得するため e.target を使う）
  async function uploadRecordPhoto(fileInput) {
    state.pickingFile = false;
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!file) return;
    const memoEl = root.querySelector(".att-memo-input");
    const fd = new FormData();
    fd.append("photo", file, file.name);
    fd.append("memo", memoEl ? memoEl.value : "");
    try {
      const res = await fetch(`/api/records/${state.record.id}/photos`, { method: "POST", body: fd });
      if (res.status === 400) { alert("追加できませんでした（最大3枚まで、画像ファイルのみ）。"); return; }
      if (!res.ok) throw new Error(String(res.status));
      await reloadPhotos();
      render();
    } catch {
      alert("写真の追加に失敗しました。");
    }
  }

  async function deleteRecordPhoto(pid) {
    if (!confirm("この添付写真を削除しますか？")) return;
    await WR.api("DELETE", `/api/photos/${pid}`);
    await reloadPhotos();
    render();
  }

  async function editRecordPhotoMemo(pid) {
    const p = (state.photos || []).find(x => x.id === pid);
    const memo = prompt("メモ（写真の説明）:", p ? (p.memo || "") : "");
    if (memo === null) return;
    await WR.api("PATCH", `/api/photos/${pid}`, { memo });
    await reloadPhotos();
    render();
  }

  async function reloadButtons() {
    if (!state.activeGroupId) return;
    const { buttons } = await WR.api("GET", `/api/button_groups/${state.activeGroupId}/buttons`);
    state.buttons = buttons;
    render();
  }

  // --- Init ---
  (async function init() {
    try {
      if (state.recordIdOverride) {
        state.record = await WR.api("GET", `/api/records/${state.recordIdOverride}`);
      } else {
        state.record = await WR.api("GET", "/api/records/current").catch(() => null);
      }
    } catch { state.record = null; }
    applyRecordLock();   // 確定済みなら閲覧専用にする
    const { groups } = await WR.api("GET", "/api/button_groups");
    state.groups = groups;
    state.activeGroupId = groups[0] ? groups[0].id : null;
    if (state.activeGroupId) {
      const { buttons } = await WR.api("GET", `/api/button_groups/${state.activeGroupId}/buttons`);
      state.buttons = buttons;
    }
    if (state.record) { await reloadEntries(); await reloadPhotos(); }
    await reloadSuggestions();
    await WRManual.load(state.record ? state.record.id : null);   // 手順表と進捗を読む
    render();

    // ファイル選択ダイアログを閉じる（選択 or キャンセル）と画面にフォーカスが戻る → 自動更新を再開
    window.addEventListener("focus", () => { state.pickingFile = false; });

    // ドラッグ終了で自動更新を再開し、添付エリア／ボタンエリアの高さを保存
    window.addEventListener("pointerup", () => {
      state.resizing = false;
      const att = root.querySelector(".attachments");
      if (att && att.style.height) {
        const h = parseInt(att.style.height, 10);
        if (h) WR.saveAttAreaPx(h);
      }
      const panel = root.querySelector(".button-panel");
      if (panel && panel.style.height) {
        const h = parseInt(panel.style.height, 10);
        if (h) WR.saveBtnAreaPx(h);
      }
    });

    // Polling（履歴の閲覧専用表示(?ro)以外では常に動かす。確定中でも解除を検知するため）
    if (!state.readOnlyParam) {
      setInterval(async () => {
        if (state.editingId !== null) return;  // pause polling while editing
        if (state.insertingAfterId !== null) return;  // pause while inserting a row
        if (state.resizing) return;  // 境界ドラッグ中は再描画しない
        // 配置/テンキーのドロップダウンを操作中は再描画しない（選択前に閉じるのを防ぐ）
        if (document.activeElement && document.activeElement.tagName === "SELECT") return;
        if (!state.record) return;
        // 作業内容を組み立て中（文字入力あり/フォーカス中）は再描画を止めて入力を妨げない
        const contentInput = root.querySelector('[name="content"]');
        if (contentInput && (contentInput.value !== "" || document.activeElement === contentInput)) return;
        // 写真の追加準備中（ファイル選択ダイアログ中・選択済み・メモ入力中）は再描画しない
        if (state.pickingFile) return;
        const attFile = root.querySelector(".att-file");
        if (attFile && attFile.files && attFile.files.length) return;
        const attMemo = root.querySelector(".att-memo-input");
        if (attMemo && (attMemo.value !== "" || document.activeElement === attMemo)) return;
        try {
          // 他ユーザーの「確定（終了）」や管理者の「確定解除」を反映する
          const fresh = await WR.api("GET", `/api/records/${state.record.id}`).catch(() => null);
          if (fresh) { state.record = fresh; applyRecordLock(); }
          await reloadEntries();
          await reloadPhotos();   // 他のユーザーが追加した写真も反映
          // 他のPCが進めたマニュアルの進捗も反映する
          if (state.manualMode || state.readOnly) await WRManual.refreshProgress(state.record.id);
          if (state.connectionLost) state.connectionLost = false;  // 復旧
          render();
        } catch {
          if (!state.connectionLost) { state.connectionLost = true; render(); }  // 接続切れを表示
        }
      }, POLLING_MS);

      // 通常入力の「現在時刻」表示を定期更新（記録は追記時の現在時刻を使用）
      setInterval(() => {
        const el = root.querySelector(".now-time-val");
        if (el) el.textContent = WR.nowHHMM();
      }, 10000);
    }
  })();
})();
