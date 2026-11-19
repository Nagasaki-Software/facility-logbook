const KEY = window.LAYOUT_KEY;
let DATA = null, curPage = 0, selected = null;
let imgEl, stageEl, listEl, panelEl;

async function init(){
  imgEl = document.getElementById('form-img');
  stageEl = document.getElementById('stage');
  listEl = document.getElementById('field-list');
  panelEl = document.getElementById('panel');
  const r = await fetch(`/api/layout/${KEY}/fields`);
  if(!r.ok){ stageEl.innerHTML = '<p class="err">読み込みに失敗しました</p>'; return; }
  DATA = await r.json();
  DATA.fields.forEach(f=>{
    if(f.placed && f.x!=null && f.y!=null){
      const [w,h]=pageSize(f.page); f.nx=f.x/w; f.ny=1-f.y/h;
    }
  });
  buildPageSelect();
  showPage(0);
  renderList();
}

function pageSize(p){
  const ps=(DATA.pages||[]).find(x=>x.page===p);
  return ps ? [ps.w_pt, ps.h_pt] : [595.0, 842.0];
}

function buildPageSelect(){
  const sel=document.getElementById('page-select'); sel.innerHTML='';
  (DATA.pages||[{page:0}]).forEach(p=>{
    const o=document.createElement('option'); o.value=p.page; o.textContent=(p.page+1)+'ページ目'; sel.appendChild(o);
  });
  sel.onchange=()=>showPage(parseInt(sel.value));
}

function showPage(p){
  curPage=p;
  imgEl.onload=renderMarkers;
  imgEl.onerror=()=>{
    stageEl.querySelectorAll('.marker, .err').forEach(e=>e.remove());
    const msg=document.createElement('p'); msg.className='err';
    msg.textContent='様式PDFを表示できません。form.pdf を確認してください。';
    stageEl.appendChild(msg);
  };
  imgEl.src=U(`/layout/${KEY}/page/${p}.png?ts=`+Date.now());
}

function renderMarkers(){
  stageEl.querySelectorAll('.marker').forEach(m=>m.remove());
  DATA.fields.forEach(f=>{ delete f._marker; }); // 古い参照をクリア
  const iw=imgEl.clientWidth, ih=imgEl.clientHeight;
  DATA.fields.filter(f=>f.placed && !f._delete && f.page===curPage && f.nx!=null).forEach(f=>{
    addMarker(f, f.nx*iw, f.ny*ih);
  });
}

// マーカー要素の位置だけを直接更新（DOM再構築なし）
function _updateMarkerPos(f){
  if(!f._marker) return;
  const iw=imgEl.clientWidth, ih=imgEl.clientHeight;
  f._marker.style.left=(f.nx*iw)+'px';
  f._marker.style.top=(f.ny*ih)+'px';
}

// パネルの座標入力欄だけを更新（再描画なし）
function _updatePanelCoords(f){
  const [pw,ph]=pageSize(f.page||0);
  const cx=document.getElementById('coord-x'), cy=document.getElementById('coord-y');
  if(cx && f.nx!=null) cx.value=Math.round(f.nx*pw);
  if(cy && f.ny!=null) cy.value=Math.round((1-f.ny)*ph);
}

function addMarker(f, ax, ay){
  const m=document.createElement('div');
  m.className='marker'+(f.source===selected?' sel':'');
  m.textContent=f.label;
  m.style.left=ax+'px'; m.style.top=ay+'px';
  f._marker=m; // DOM参照を保持（位置直接更新用）

  m.addEventListener('click',(e)=>{ e.stopPropagation(); selectField(f.source); });

  let sx,sy,ol,ot;
  m.addEventListener('pointerdown',(e)=>{
    e.preventDefault();
    // ポインターキャプチャを先に確保（この後のDOM操作で解放されないよう）
    m.setPointerCapture(e.pointerId);
    sx=e.clientX; sy=e.clientY; ol=parseFloat(m.style.left); ot=parseFloat(m.style.top);
    // renderMarkers()を呼ばず選択状態だけ更新（呼ぶとmがDOM削除されキャプチャ消失）
    selected=f.source;
    stageEl.querySelectorAll('.marker').forEach(el=>el.classList.toggle('sel', el===m));
    renderList(); renderPanel();
    const move=(ev)=>{
      const iw=imgEl.clientWidth, ih=imgEl.clientHeight;
      let nl=Math.max(0,Math.min(iw, ol+(ev.clientX-sx)));
      let nt=Math.max(0,Math.min(ih, ot+(ev.clientY-sy)));
      m.style.left=nl+'px'; m.style.top=nt+'px';
      f.nx=nl/iw; f.ny=nt/ih; f.placed=true; f.page=curPage;
      _updatePanelCoords(f); // ドラッグ中も座標表示を更新
    };
    const up=()=>{
      m.removeEventListener('pointermove',move);
      m.removeEventListener('pointerup',up);
      m.removeEventListener('pointercancel',up);
    };
    m.addEventListener('pointermove',move);
    m.addEventListener('pointerup',up);
    m.addEventListener('pointercancel',up);
  });
  stageEl.appendChild(m);
}

function renderList(){
  listEl.innerHTML='';
  // 孤立項目を削除したものだけ一覧から消す（通常項目は「未配置」として残し置き直せる）
  DATA.fields.filter(f=>!(f._delete && f.orphan)).forEach(f=>{
    const row=document.createElement('div');
    const removed = f._delete && !f.orphan;   // 配置を消した通常項目
    row.className='fl-row'+(f.source===selected?' sel':'')+(f.orphan?' orphan':'');
    const status=f.orphan?'孤立':((f.placed && !removed)?(f.page+1)+'P':'未配置');
    const lab=document.createElement('span'); lab.textContent=f.label;
    const st=document.createElement('span'); st.className='fl-status'; st.textContent=status;
    row.appendChild(lab); row.appendChild(st);
    row.onclick=()=>{
      if(!f.placed || f._delete){ f.placed=true; f._delete=false; f.page=curPage; f.nx=0.1; f.ny=0.1; }
      if(f.page!==curPage){ document.getElementById('page-select').value=f.page; showPage(f.page); }
      selectField(f.source);
    };
    listEl.appendChild(row);
  });
}

function selectField(src){ selected=src; renderMarkers(); renderList(); renderPanel(); }

function renderPanel(){
  const f=DATA.fields.find(x=>x.source===selected);
  if(!f){ panelEl.innerHTML='<p class="lo-muted">項目を選んでください</p>'; return; }
  panelEl.innerHTML='';
  const title=document.createElement('h3'); title.textContent=f.label; panelEl.appendChild(title);

  const [pw,ph]=pageSize(f.page||0);
  const cur_x = f.nx!=null ? Math.round(f.nx*pw) : '';
  const cur_y = f.ny!=null ? Math.round((1-f.ny)*ph) : '';

  const box=document.createElement('div');
  let html='';
  html+=`<p class="lo-muted" style="font-size:11px;margin:2px 0 8px">↑↓←→キーで1pt微調整 / Shift+矢印で5pt</p>`;
  html+=`<label>X座標(pt) <input type="number" id="coord-x" min="0" max="${Math.round(pw)}" value="${cur_x}" style="width:80px"></label>`;
  html+=`<label>Y座標(pt) <input type="number" id="coord-y" min="0" max="${Math.round(ph)}" value="${cur_y}" style="width:80px"></label>`;
  html+=`<label>文字サイズ <input type="number" id="fs" min="6" max="40" value="${f.font_size||DATA.default_font_size}"></label>`;
  html+=`<label>文字色 <input type="color" id="col" value="${f.color||'#000000'}"></label>`;
  if(f.kind==='number'){
    html+=`<label><input type="checkbox" id="ngon" ${f.ng_color?'checked':''}> NG時に色を変える</label>`;
    html+=`<label>NG時の色 <input type="color" id="ngcol" value="${f.ng_color||'#ff0000'}"></label>`;
  }
  const canRemove = f.orphan || (f.placed && !f._delete);
  if(canRemove){ html+=`<button id="del">${f.orphan ? 'この項目を削除' : '配置を消す'}</button>`; }
  box.innerHTML=html;
  panelEl.appendChild(box);

  // 座標入力 → マーカーをリアルタイム移動
  document.getElementById('coord-x').oninput=(e)=>{
    const v=parseFloat(e.target.value);
    if(!isNaN(v)){ f.nx=Math.max(0,Math.min(1,v/pw)); f.placed=true; _updateMarkerPos(f); }
  };
  document.getElementById('coord-y').oninput=(e)=>{
    const v=parseFloat(e.target.value);
    if(!isNaN(v)){ f.ny=Math.max(0,Math.min(1,1-v/ph)); f.placed=true; _updateMarkerPos(f); }
  };

  document.getElementById('fs').onchange=(e)=>{ f.font_size=parseInt(e.target.value); };
  document.getElementById('col').oninput=(e)=>{ f.color=e.target.value; };
  if(f.kind==='number'){
    const ngon=document.getElementById('ngon'), ngcol=document.getElementById('ngcol');
    ngon.onchange=()=>{ f.ng_color = ngon.checked ? ngcol.value : null; };
    ngcol.oninput=()=>{ if(ngon.checked) f.ng_color=ngcol.value; };
  }
  const delBtn=document.getElementById('del');
  if(delBtn){
    delBtn.onclick=()=>{
      f._delete=true;                 // 保存時に mapping.json から消える
      if(!f.orphan){ f.placed=false; f.nx=null; f.ny=null; }  // 通常項目は一覧に「未配置」で残す
      selected=null; renderMarkers(); renderList(); renderPanel();
    };
  }
}

async function save(){
  const fields=DATA.fields.filter(f=>f.placed && !f._delete && f.nx!=null).map(f=>{
    const o={source:f.source, page:f.page, nx:f.nx, ny:f.ny, font_size:f.font_size, color:f.color||'#000000'};
    if(f.kind==='number') o.ng_color=f.ng_color||null;
    return o;
  });
  const deletes=DATA.fields.filter(f=>f._delete).map(f=>f.source);
  const r=await fetch(`/api/layout/${KEY}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({fields,deletes})});
  if(r.ok){ alert('保存しました'); }
  else { let e={}; try{e=await r.json();}catch(_){ } alert('保存に失敗: '+(e.error||r.status)); }
}

window.addEventListener('DOMContentLoaded',()=>{
  document.getElementById('save-btn').onclick=save;
  document.getElementById('stage').addEventListener('click',()=>{
    selected=null; renderPanel(); renderList(); renderMarkers();
  });

  // 矢印キーで選択中マーカーを微調整（入力欄にフォーカス中は無効）
  document.addEventListener('keydown',(e)=>{
    if(!selected || !DATA) return;
    if(e.target.tagName==='INPUT' || e.target.tagName==='SELECT' || e.target.tagName==='TEXTAREA') return;
    const dirs={ArrowLeft:[-1,0], ArrowRight:[1,0], ArrowUp:[0,-1], ArrowDown:[0,1]};
    if(!dirs[e.key]) return;
    e.preventDefault();
    const f=DATA.fields.find(x=>x.source===selected);
    if(!f || f.nx==null) return;
    const step=e.shiftKey ? 5 : 1; // Shift+矢印で5pt、通常は1pt
    const [pw,ph]=pageSize(f.page||0);
    const [dx,dy]=dirs[e.key];
    f.nx=Math.max(0,Math.min(1, f.nx+dx*step/pw));
    f.ny=Math.max(0,Math.min(1, f.ny+dy*step/ph));
    f.placed=true;
    _updateMarkerPos(f);
    _updatePanelCoords(f);
  });

  init();
});
