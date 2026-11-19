(function () {
  const root = document.getElementById("buttons-root");
  if (!root) return;

  let state = { groups: [], buttonsByGroup: {} };

  async function load() {
    const { groups } = await WR.api("GET", "/api/button_groups");
    state.groups = groups;
    state.buttonsByGroup = {};
    for (const g of groups) {
      const { buttons } = await WR.api("GET", `/api/button_groups/${g.id}/buttons`);
      // 管理ページは並び順（sort_order）で表示し、◀▶での並べ替えを見た目通りにする
      buttons.sort((a, b) => (a.sort_order - b.sort_order) || (a.id - b.id));
      state.buttonsByGroup[g.id] = buttons;
    }
  }

  function render() {
    root.innerHTML = `
      <div class="bm-controls">
        <button id="add-group">+ グループ追加</button>
      </div>
      ${state.groups.map((g, gi) => `
        <fieldset class="bm-group" data-id="${g.id}">
          <legend>
            <button class="g-up" data-id="${g.id}" title="グループを上へ" ${gi === 0 ? "disabled" : ""}>▲</button>
            <button class="g-down" data-id="${g.id}" title="グループを下へ" ${gi === state.groups.length - 1 ? "disabled" : ""}>▼</button>
            <span class="g-name">${escape(g.name)}</span>
            <button class="g-rename" data-id="${g.id}">名前変更</button>
            <button class="g-delete" data-id="${g.id}">削除</button>
          </legend>
          <ul>
            ${state.buttonsByGroup[g.id].map((b, bi, arr) => `
              <li>
                <button class="b-left"  data-id="${b.id}" data-gid="${g.id}" title="前へ" ${bi === 0 ? "disabled" : ""}>◀</button>
                <button class="b-right" data-id="${b.id}" data-gid="${g.id}" title="後ろへ" ${bi === arr.length - 1 ? "disabled" : ""}>▶</button>
                ${b.is_pinned ? "★" : "☆"}
                <button class="b-pin" data-id="${b.id}" data-cur="${b.is_pinned}">${b.is_pinned ? "ピン解除" : "ピン止め"}</button>
                <span>${escape(b.label)}</span>
                <button class="b-rename" data-id="${b.id}">名前変更</button>
                <button class="b-delete" data-id="${b.id}">削除</button>
              </li>
            `).join("")}
          </ul>
          <button class="b-add" data-gid="${g.id}">+ ボタン追加</button>
        </fieldset>
      `).join("")}
    `;

    document.getElementById("add-group").onclick = async () => {
      const name = prompt("グループ名:");
      if (!name) return;
      await WR.api("POST", "/api/button_groups", { name });
      await refresh();
    };
    root.querySelectorAll(".g-rename").forEach(b => b.onclick = async () => {
      const cur = state.groups.find(g => g.id == b.dataset.id);
      const name = prompt("新しい名前:", cur.name);
      if (!name) return;
      await WR.api("PATCH", `/api/button_groups/${b.dataset.id}`, { name });
      await refresh();
    });
    root.querySelectorAll(".g-delete").forEach(b => b.onclick = async () => {
      if (!confirm("グループとボタンをすべて削除します。よろしいですか？")) return;
      await WR.api("DELETE", `/api/button_groups/${b.dataset.id}`);
      await refresh();
    });
    const TPL_HINT = "ボタン名（＝作業内容）\n※あとで数値を入れたい箇所は { } で囲みます\n  例: 塩分濃度を{変更前}%から{変更後}%に変更した";
    root.querySelectorAll(".b-add").forEach(b => b.onclick = async () => {
      const label = prompt(TPL_HINT);
      if (!label) return;
      await WR.api("POST", "/api/buttons", { group_id: parseInt(b.dataset.gid, 10), label });
      await refresh();
    });
    root.querySelectorAll(".b-rename").forEach(b => b.onclick = async () => {
      // 元の名前を初期値として表示し、そこから修正できるようにする
      const cur = Object.values(state.buttonsByGroup).flat().find(x => x.id == b.dataset.id);
      const label = prompt("新しい名前\n※あとで数値を入れたい箇所は { } で囲みます", cur ? cur.label : "");
      if (!label) return;
      await WR.api("PATCH", `/api/buttons/${b.dataset.id}`, { label });
      await refresh();
    });
    root.querySelectorAll(".b-delete").forEach(b => b.onclick = async () => {
      if (!confirm("削除しますか？")) return;
      await WR.api("DELETE", `/api/buttons/${b.dataset.id}`);
      await refresh();
    });
    root.querySelectorAll(".b-pin").forEach(b => b.onclick = async () => {
      const cur = b.dataset.cur === "1";
      await WR.api("PATCH", `/api/buttons/${b.dataset.id}/pin`, { pinned: !cur });
      await refresh();
    });

    // 並べ替え（移動ボタン）
    root.querySelectorAll(".g-up").forEach(b => b.onclick = () => moveGroup(parseInt(b.dataset.id, 10), -1));
    root.querySelectorAll(".g-down").forEach(b => b.onclick = () => moveGroup(parseInt(b.dataset.id, 10), 1));
    root.querySelectorAll(".b-left").forEach(b => b.onclick = () =>
      moveButton(parseInt(b.dataset.gid, 10), parseInt(b.dataset.id, 10), -1));
    root.querySelectorAll(".b-right").forEach(b => b.onclick = () =>
      moveButton(parseInt(b.dataset.gid, 10), parseInt(b.dataset.id, 10), 1));
  }

  async function moveGroup(gid, dir) {
    const ids = state.groups.map(g => g.id);
    const i = ids.indexOf(gid);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    await WR.api("POST", "/api/button_groups/reorder", { ordered_ids: ids });
    await refresh();
  }

  async function moveButton(gid, bid, dir) {
    const ids = state.buttonsByGroup[gid].map(b => b.id);
    const i = ids.indexOf(bid);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    await WR.api("POST", `/api/button_groups/${gid}/buttons/reorder`, { ordered_ids: ids });
    await refresh();
  }

  async function refresh() { await load(); render(); }

  function escape(s) {
    return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  }

  refresh();
})();
