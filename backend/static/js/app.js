const API = {};

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

API.get = (p) => api(p);
API.post = (p, b) => api(p, { method: 'POST', body: JSON.stringify(b) });
API.patch = (p, b) => api(p, { method: 'PATCH', body: JSON.stringify(b) });
API.del = (p, opts = {}) => api(p, { method: 'DELETE', ...opts });
API.upload = async (p, fd) => {
  const res = await fetch(p, { method: 'POST', body: fd });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
};

let instances = [];
let selectedInstanceId = null;
let currentPage = 'models';
let sortColumn = 'name';
let sortDir = 'asc';

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function toast(msg, type = 'info') {
  const c = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function showPage(name) {
  currentPage = name;
  $$('.page').forEach(p => p.classList.remove('active'));
  const page = document.getElementById(`page-${name}`);
  if (page) page.classList.add('active');
  $$('header nav button').forEach(b => {
    b.classList.toggle('active', b.dataset.page === name);
  });
  if (name === 'models' && selectedInstanceId) loadModels();
  if (name === 'instances') loadInstances();
  if (name === 'gguf' && selectedInstanceId) loadGgufLibrary();
}

// --- Instance selector ---
async function loadInstanceSelector() {
  try {
    instances = await API.get('/api/instances');
  } catch { instances = []; }
  const sel = document.getElementById('instance-select');
  sel.innerHTML = '<option value="">-- Select instance --</option>' +
    instances.map(i => `<option value="${i.id}">${i.name} (${i.type})</option>`).join('');
  if (selectedInstanceId) sel.value = selectedInstanceId;
  sel.addEventListener('change', () => {
    selectedInstanceId = sel.value;
    if (selectedInstanceId) {
      loadModels();
      loadGgufLibrary();
    }
  });
  if (!selectedInstanceId && instances.length > 0) {
    selectedInstanceId = instances[0].id;
    sel.value = selectedInstanceId;
    loadModels();
    loadGgufLibrary();
  }
}

function parseParamSize(s) {
  if (!s || s === '—') return 0;
  const m = s.match(/^([\d.]+)\s*([BKMGTPE])/i);
  if (!m) return parseFloat(s) || 0;
  const units = { b: 1, k: 1024, m: 1024**2, g: 1024**3, t: 1024**4 };
  return parseFloat(m[1]) * (units[m[2].toLowerCase()] || 1);
}

function parseSize(s) {
  if (typeof s === 'number') return s;
  if (!s || s === '—') return 0;
  const m = s.match(/^([\d.]+)\s*([BKMGTPE])/i);
  if (!m) return parseFloat(s) || 0;
  const units = { b: 1, k: 1024, m: 1024**2, g: 1024**3, t: 1024**4 };
  return parseFloat(m[1]) * (units[m[2].toLowerCase()] || 1);
}

function sortModels(models) {
  const col = sortColumn;
  const dir = sortDir === 'asc' ? 1 : -1;
  const sorted = [...models].sort((a, b) => {
    let va, vb;
    if (col === 'name') { va = a.name || ''; vb = b.name || ''; return dir * va.localeCompare(vb); }
    if (col === 'family') { va = a.family || ''; vb = b.family || ''; return dir * va.localeCompare(vb); }
    if (col === 'param') { va = parseParamSize(a.parameter_size); vb = parseParamSize(b.parameter_size); return dir * (va - vb); }
    if (col === 'quant') { va = a.quantization_level || ''; vb = b.quantization_level || ''; return dir * va.localeCompare(vb); }
    if (col === 'size') { va = parseSize(a.size); vb = parseSize(b.size); return dir * (va - vb); }
    return 0;
  });
  return sorted;
}

function setSort(col) {
  if (sortColumn === col) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }
  else { sortColumn = col; sortDir = 'asc'; }
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.toggle('asc', th.dataset.sort === sortColumn && sortDir === 'asc');
    th.classList.toggle('desc', th.dataset.sort === sortColumn && sortDir === 'desc');
  });
  loadModels();
}

// --- Models page ---
async function loadModels() {
  const tbody = document.getElementById('models-tbody');
  if (!selectedInstanceId) { tbody.innerHTML = '<tr><td colspan="6" class="empty">Select an instance</td></tr>'; return; }
  tbody.innerHTML = '<tr><td colspan="6" class="empty"><div class="spinner"></div></td></tr>';
  try {
    const raw = await API.get(`/api/models/${selectedInstanceId}`);
    if (!raw.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No models found</td></tr>';
      return;
    }
    const models = sortModels(raw);
    tbody.innerHTML = models.map(m => `
      <tr>
        <td><strong>${m.name}</strong></td>
        <td>${m.family || '—'}</td>
        <td>${m.parameter_size || '—'}</td>
        <td>${m.quantization_level || '—'}</td>
        <td>${formatSize(m.size)}</td>
        <td>
          <button class="btn btn-sm" onclick="inspectModel('${m.name}')">Inspect</button>
          <button class="btn btn-sm btn-danger" onclick="deleteModel('${m.name}')">Delete</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Error: ${e.message}</td></tr>`;
  }
}

async function inspectModel(name) {
  try {
    const data = await API.post('/api/models/inspect', { instance_id: selectedInstanceId, name });
    const modal = document.getElementById('modal');
    const body = document.getElementById('modal-body');
    body.innerHTML = `
      <h3>${name}</h3>
      <pre class="modelfile">${escapeHtml(data.modelfile || JSON.stringify(data, null, 2))}</pre>
      <div class="modal-actions">
        <button class="btn" onclick="closeModal()">Close</button>
      </div>
    `;
    modal.classList.add('open');
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function deleteModel(name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    await API.del('/api/models', { body: JSON.stringify({ instance_id: selectedInstanceId, name }) });
    toast(`Deleted "${name}"`, 'success');
    loadModels();
  } catch (e) {
    toast(e.message, 'error');
  }
}

// --- Import page ---
document.getElementById('import-form')?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fileInput = document.getElementById('import-file');
  const nameInput = document.getElementById('import-name');
  const file = fileInput.files[0];
  if (!file || !selectedInstanceId) { toast('Select a file and instance', 'error'); return; }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('instance_id', selectedInstanceId);
  fd.append('model_name', nameInput.value || file.name.replace(/\.gguf$/i, ''));
  try {
    const data = await API.upload('/api/import/upload', fd);
    fileInput.value = '';
    nameInput.value = '';
    pollTask(data.task_id, () => loadModels());
  } catch (e) {
    toast(e.message, 'error');
  }
});

document.getElementById('import-file')?.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (file) {
    const suggested = file.name.replace(/\.gguf$/i, '').toLowerCase().replace(/_/g, '');
    document.getElementById('import-name').value = suggested;
  }
});

// --- Pull page ---
async function pullRegistry() {
  const name = document.getElementById('pull-registry-name').value.trim();
  if (!name || !selectedInstanceId) { toast('Enter a model name and select an instance', 'error'); return; }
  try {
    const data = await API.post('/api/pull/registry', { instance_id: selectedInstanceId, name });
    document.getElementById('pull-registry-name').value = '';
    pollTask(data.task_id, () => loadModels());
  } catch (e) {
    toast(e.message, 'error');
  }
}

async function pullHuggingFace() {
  const url = document.getElementById('pull-hf-url').value.trim();
  const token = document.getElementById('pull-hf-token').value.trim() || null;
  if (!url || !selectedInstanceId) { toast('Enter a URL and select an instance', 'error'); return; }
  try {
    const data = await API.post('/api/pull/huggingface', { instance_id: selectedInstanceId, url, hf_token: token });
    document.getElementById('pull-hf-url').value = '';
    document.getElementById('pull-hf-token').value = '';
    pollTask(data.task_id, () => loadModels());
  } catch (e) {
    toast(e.message, 'error');
  }
}

// --- Instances page ---
async function loadInstances() {
  const container = document.getElementById('instances-container');
  try {
    const list = await API.get('/api/instances');
    container.innerHTML = list.map(i => `
      <div class="instance-card">
        <div class="info">
          <span class="status-badge ${i.type}">${i.type}</span>
          <div>
            <strong>${i.name}</strong>
            <div style="font-size:11px;color:#8b949e;">${i.url}</div>
            ${i.container_gguf_dir ? `<div style="font-size:11px;color:#58a6ff;">GGUF mount: ${i.container_gguf_dir}</div>` : ''}
          </div>
        </div>
        <div class="actions">
          <button class="btn btn-sm" onclick="editInstance('${i.id}')">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteInstance('${i.id}')">Delete</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

async function discoverInstances() {
  try {
    const found = await API.get('/api/instances/discover');
    for (const inst of found) {
      try {
        await API.post('/api/instances', inst);
      } catch {}
    }
    toast(`Discovered ${found.length} instance(s)`, 'success');
    loadInstances();
    loadInstanceSelector();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function showAddInstance() {
  const modal = document.getElementById('modal');
  const body = document.getElementById('modal-body');
  const types = ['local', 'docker', 'remote'].map(t =>
    `<option value="${t}">${t.charAt(0).toUpperCase() + t.slice(1)}</option>`
  ).join('');
  body.innerHTML = `
    <h3>Add Instance</h3>
    <form id="add-instance-form">
      <div class="form-group"><label>Name</label><input id="ai-name" required></div>
      <div class="form-group"><label>Type</label><select id="ai-type">${types}</select></div>
      <div class="form-group"><label>URL</label><input id="ai-url" value="http://localhost:11434"></div>
      <div class="form-group"><label>API Key (optional)</label><input id="ai-key" type="password"></div>
      <div class="form-group"><label>Container ID (for docker)</label><input id="ai-cid"></div>
      <div class="form-group"><label>Host GGUF Directory</label><input id="ai-gguf-dir"></div>
      <div class="form-group"><label>Container GGUF Mount Path</label><input id="ai-gguf-container" placeholder="/GGUF"></div>
      <div class="modal-actions">
        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  `;
  modal.classList.add('open');
  document.getElementById('add-instance-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
      name: document.getElementById('ai-name').value,
      type: document.getElementById('ai-type').value,
      url: document.getElementById('ai-url').value,
      api_key: document.getElementById('ai-key').value || null,
      container_id: document.getElementById('ai-cid').value || null,
      gguf_dir: document.getElementById('ai-gguf-dir').value || null,
      container_gguf_dir: document.getElementById('ai-gguf-container').value || null,
    };
    try {
      await API.post('/api/instances', data);
      toast('Instance added', 'success');
      closeModal();
      loadInstances();
      loadInstanceSelector();
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

async function editInstance(id) {
  const inst = instances.find(i => i.id === id);
  if (!inst) return;
  const modal = document.getElementById('modal');
  const body = document.getElementById('modal-body');
  const types = ['local', 'docker', 'remote'].map(t =>
    `<option value="${t}" ${inst.type === t ? 'selected' : ''}>${t.charAt(0).toUpperCase() + t.slice(1)}</option>`
  ).join('');
  body.innerHTML = `
    <h3>Edit Instance</h3>
    <form id="edit-instance-form">
      <div class="form-group"><label>Name</label><input id="ei-name" value="${escapeHtml(inst.name)}" required></div>
      <div class="form-group"><label>Type</label><select id="ei-type">${types}</select></div>
      <div class="form-group"><label>URL</label><input id="ei-url" value="${escapeHtml(inst.url)}"></div>
      <div class="form-group"><label>API Key (leave blank to keep)</label><input id="ei-key" type="password"></div>
      <div class="form-group"><label>Container ID</label><input id="ei-cid" value="${escapeHtml(inst.container_id || '')}"></div>
      <div class="form-group"><label>Host GGUF Directory</label><input id="ei-gguf-dir" value="${escapeHtml(inst.gguf_dir || '')}"></div>
      <div class="form-group"><label>Container GGUF Mount Path</label><input id="ei-gguf-container" value="${escapeHtml(inst.container_gguf_dir || '')}"></div>
      <div class="modal-actions">
        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  `;
  modal.classList.add('open');
  document.getElementById('edit-instance-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = {
      name: document.getElementById('ei-name').value,
      type: document.getElementById('ei-type').value,
      url: document.getElementById('ei-url').value,
      container_id: document.getElementById('ei-cid').value || null,
      gguf_dir: document.getElementById('ei-gguf-dir').value || null,
      container_gguf_dir: document.getElementById('ei-gguf-container').value || null,
    };
    const key = document.getElementById('ei-key').value;
    if (key) data.api_key = key;
    try {
      await API.patch(`/api/instances/${id}`, data);
      toast('Instance updated', 'success');
      closeModal();
      loadInstances();
      loadInstanceSelector();
    } catch (e) {
      toast(e.message, 'error');
    }
  });
}

async function deleteInstance(id) {
  if (!confirm('Delete this instance?')) return;
  try {
    await API.del(`/api/instances/${id}`);
    toast('Instance deleted', 'success');
    loadInstances();
    loadInstanceSelector();
  } catch (e) {
    toast(e.message, 'error');
  }
}

// --- GGUF Library ---
async function loadGgufLibrary() {
  const container = document.getElementById('gguf-container');
  if (!selectedInstanceId) {
    container.innerHTML = '<div class="empty">Select an instance to browse GGUF files</div>';
    return;
  }
  container.innerHTML = '<div class="empty"><div class="spinner"></div></div>';
  try {
    const files = await API.get(`/api/gguf-library/${selectedInstanceId}`);
    if (!files.length) {
      container.innerHTML = '<div class="empty">No GGUF files found in the configured directory</div>';
      return;
    }
    container.innerHTML = '<div class="gguf-grid">' + files.map(f => {
      const size = formatSize(f.size);
      const suggested = f.name.replace(/\.gguf$/i, '').toLowerCase().replace(/_/g, '');
      const ctx = f.context_length ? (f.context_length >= 1000 ? `${(f.context_length / 1000).toFixed(0)}K` : `${f.context_length}`) : null;
      const cols = [];
      if (f.parameter_size) cols.push(f.parameter_size);
      if (f.quantization) cols.push(f.quantization);
      if (ctx) cols.push(ctx);
      const infoLine = cols.join(' · ');
      return `
        <div class="gguf-card">
          <div class="gguf-card-top">
            <span class="gguf-card-filename">${escapeHtml(f.name)}</span>
            <span class="gguf-card-size">${size}</span>
          </div>
          <div class="gguf-card-mid">
            <span class="gguf-card-model">${f.label ? escapeHtml(f.label) : '—'}</span>
            <span class="gguf-card-family">${f.family || '—'}</span>
          </div>
          <div class="gguf-card-info">
            <span class="ginfo-left">${f.parameter_size || '—'}</span>
            <span class="ginfo-center">${f.quantization || '—'}</span>
            <span class="ginfo-right">${ctx || '—'}</span>
          </div>
          <div class="actions">
            <button class="btn btn-sm btn-primary" onclick="importGgufFromLibrary('${escapeHtml(f.path)}', '${escapeHtml(suggested)}')">Import</button>
          </div>
        </div>
      `;
    }).join('') + '</div>';
  } catch (e) {
    container.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
  }
}

async function importGgufFromLibrary(path, suggested) {
  const name = prompt('Model name:', suggested);
  if (!name) return;
  try {
    const data = await API.post('/api/gguf-library/import', { instance_id: selectedInstanceId, gguf_path: path, model_name: name });
    pollTask(data.task_id, () => { loadModels(); loadGgufLibrary(); });
  } catch (e) {
    toast(e.message, 'error');
  }
}

// --- Utilities ---
async function pollTask(taskId, onDone) {
  const toastEl = document.createElement('div');
  toastEl.className = 'toast';
  toastEl.textContent = 'Operation started...';
  document.getElementById('toast-container').appendChild(toastEl);

  const iv = setInterval(async () => {
    try {
      const t = await API.get(`/api/tasks/${taskId}`);
      if (t.status === 'completed') {
        clearInterval(iv);
        toastEl.remove();
        toast('Operation completed', 'success');
        onDone();
      } else if (t.status === 'failed') {
        clearInterval(iv);
        toastEl.remove();
        toast(t.error || 'Operation failed', 'error');
      } else {
        toastEl.textContent = `Running... (${t.status})`;
      }
    } catch {
      clearInterval(iv);
      toastEl.remove();
    }
  }, 2000);
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return '—';
  if (typeof bytes === 'string') return bytes;
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
  return `${size.toFixed(1)} ${units[i]}`;
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('header nav button[data-page]').forEach(btn => {
    btn.addEventListener('click', () => showPage(btn.dataset.page));
  });
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => setSort(th.dataset.sort));
  });
  document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target === e.currentTarget) closeModal();
  });
  loadInstanceSelector();
  showPage('models');
  const defaultTh = document.querySelector('th.sortable[data-sort="name"]');
  if (defaultTh) defaultTh.classList.add('asc');
});
