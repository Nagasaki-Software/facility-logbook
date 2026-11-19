function applyFilter(key){
  const p = new URLSearchParams();
  const f = document.getElementById('from').value;
  const t = document.getElementById('to').value;
  const w = document.getElementById('who').value;
  if (f) p.set('from', f);
  if (t) p.set('to', t);
  if (w) p.set('who', w);
  window.location = U(`/history/${key}?` + p.toString());
}

function bulkExportPdf(key){
  const p = new URLSearchParams();
  p.set('key', key);
  const f = document.getElementById('from').value;
  const t = document.getElementById('to').value;
  const w = document.getElementById('who').value;
  if (f) p.set('from', f);
  if (t) p.set('to', t);
  if (w) p.set('who', w);
  window.location = U('/api/inspections/bulk-pdf?' + p.toString());
}

function exportUsageCsv(key){
  const p = new URLSearchParams();
  p.set('key', key);
  const f = document.getElementById('from').value;
  const t = document.getElementById('to').value;
  if (f) p.set('from', f);
  if (t) p.set('to', t);
  window.location = U('/api/inspections/usage-csv?' + p.toString());
}
