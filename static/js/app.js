/**
 * SCALE Emergy Calculator — Frontend JavaScript
 * Consome a API REST FastAPI e atualiza a interface dinamicamente.
 */

'use strict';

// ── Estado global ─────────────────────────────────────────────────────────────
let allProcesses = [];
let flowChart = null;

// ── Inicialização ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadProcesses();
});

// ── API helpers ───────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
  };
  const res = await fetch(path, { ...defaults, ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Erro desconhecido');
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── Processos LCI ─────────────────────────────────────────────────────────────

async function loadProcesses() {
  try {
    allProcesses = await apiFetch('/api/processes');
    renderProcessList(allProcesses);
    populateTargetSelect(allProcesses);
    log('info', `${allProcesses.length} processos carregados`);
  } catch (e) {
    log('error', `Erro ao carregar processos: ${e.message}`);
  }
}

function renderProcessList(processes) {
  const list = document.getElementById('process-list');
  const sources = processes.filter(p => p.type === 'source').length;

  document.getElementById('process-count').textContent = `${processes.length} processos`;
  document.getElementById('source-count').textContent = `${sources} fontes`;

  if (processes.length === 0) {
    list.innerHTML = '<div class="text-center text-secondary p-4">Nenhum processo cadastrado</div>';
    return;
  }

  list.innerHTML = processes.map(p => `
    <div class="process-item d-flex justify-content-between align-items-center"
         id="proc-${p.id}" onclick="selectProcess('${p.id}')">
      <div style="min-width:0">
        <span class="badge ${p.type === 'source' ? 'badge-source' : 'badge-process'} me-2">
          ${p.type === 'source' ? 'FONTE' : 'PROC'}
        </span>
        <span class="proc-name">${escHtml(p.name)}</span>
        <div class="proc-sub" style="font-size:0.72rem; margin-left:46px;">
          ${escHtml(p.id)} · UEV: ${p.uev.toExponential(2)} sej/${p.unit}
        </div>
      </div>
      <button class="btn btn-outline-danger btn-sm flex-shrink-0" style="font-size:0.7rem; padding:1px 6px;"
              onclick="event.stopPropagation(); deleteProcess('${p.id}')">
        <i class="bi bi-trash"></i>
      </button>
    </div>
  `).join('');
}

function filterProcesses() {
  const q = document.getElementById('search-input').value.toLowerCase();
  const filtered = allProcesses.filter(p =>
    p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q)
  );
  renderProcessList(filtered);
}

function populateTargetSelect(processes) {
  const sel = document.getElementById('target-select');
  const prev = sel.value;
  sel.innerHTML = '<option value="">Selecione um processo...</option>' +
    processes.map(p =>
      `<option value="${p.id}" ${p.id === prev ? 'selected' : ''}>
        ${escHtml(p.name)} (${p.id})
      </option>`
    ).join('');
}

function selectProcess(id) {
  document.querySelectorAll('.process-item').forEach(el => el.classList.remove('selected'));
  const el = document.getElementById(`proc-${id}`);
  if (el) el.classList.add('selected');
  document.getElementById('target-select').value = id;
}

async function deleteProcess(id) {
  if (!confirm(`Remover processo "${id}"?`)) return;
  try {
    await apiFetch(`/api/processes/${id}`, { method: 'DELETE' });
    showToast(`Processo "${id}" removido`, 'success');
    log('warn', `Processo removido: ${id}`);
    await loadProcesses();
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

// ── Modal: Adicionar processo ─────────────────────────────────────────────────

let inputRowCount = 0;

function openAddModal() {
  document.getElementById('new-id').value = '';
  document.getElementById('new-name').value = '';
  document.getElementById('new-unit').value = '';
  document.getElementById('new-uev').value = '';
  document.getElementById('new-description').value = '';
  document.getElementById('new-output').value = '1.0';
  document.getElementById('new-type').value = 'source';
  document.getElementById('inputs-list').innerHTML = '';
  inputRowCount = 0;
  toggleInputsSection();
  new bootstrap.Modal(document.getElementById('addModal')).show();
}

function toggleInputsSection() {
  const type = document.getElementById('new-type').value;
  document.getElementById('inputs-section').style.display =
    type === 'process' ? 'block' : 'none';
}

function addInputRow() {
  inputRowCount++;
  const row = document.createElement('div');
  row.className = 'input-row';
  row.id = `input-row-${inputRowCount}`;
  row.innerHTML = `
    <select class="form-select bg-dark text-light border-secondary form-select-sm input-proc">
      ${allProcesses.map(p => `<option value="${p.id}">${escHtml(p.name)}</option>`).join('')}
    </select>
    <input type="number" step="any" value="1.0" min="0.001"
           class="form-control bg-dark text-light border-secondary form-control-sm input-amount"
           style="max-width:100px;" placeholder="Quantidade" />
    <button class="btn btn-outline-danger btn-sm"
            onclick="document.getElementById('input-row-${inputRowCount}').remove()">
      <i class="bi bi-x"></i>
    </button>
  `;
  document.getElementById('inputs-list').appendChild(row);
}

async function submitNewProcess() {
  const id = document.getElementById('new-id').value.trim();
  const name = document.getElementById('new-name').value.trim();
  const type = document.getElementById('new-type').value;
  const unit = document.getElementById('new-unit').value.trim();
  const uev = parseFloat(document.getElementById('new-uev').value);
  const description = document.getElementById('new-description').value.trim();
  const output_amount = parseFloat(document.getElementById('new-output').value) || 1.0;

  if (!id || !name || !unit || isNaN(uev)) {
    showToast('Preencha todos os campos obrigatórios', 'warning');
    return;
  }

  const inputs = [];
  if (type === 'process') {
    document.querySelectorAll('.input-row').forEach(row => {
      const proc_id = row.querySelector('.input-proc').value;
      const amount = parseFloat(row.querySelector('.input-amount').value);
      if (proc_id && amount > 0) inputs.push({ process_id: proc_id, amount });
    });
  }

  try {
    await apiFetch('/api/processes', {
      method: 'POST',
      body: JSON.stringify({ id, name, type, unit, uev, description, inputs, output_amount })
    });
    bootstrap.Modal.getInstance(document.getElementById('addModal')).hide();
    showToast(`Processo "${name}" adicionado`, 'success');
    log('ok', `Processo criado: ${id}`);
    await loadProcesses();
  } catch (e) {
    showToast(e.message, 'danger');
  }
}

// ── Simulação ─────────────────────────────────────────────────────────────────

async function runSimulation() {
  const target = document.getElementById('target-select').value;
  if (!target) {
    showToast('Selecione um processo alvo', 'warning');
    return;
  }

  const strategy = document.getElementById('strategy-select').value;
  const minflow = parseFloat(document.getElementById('minflow-select').value);

  const btn = document.getElementById('btn-simulate');
  btn.classList.add('btn-loading');
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Calculando...';

  log('info', `Simulando: ${target} (${strategy}, minflow=${minflow.toExponential()})`);

  try {
    const result = await apiFetch('/api/simulate', {
      method: 'POST',
      body: JSON.stringify({ target_process_id: target, strategy, minflow })
    });
    displayResult(result);
    log('ok', `Emergia total: ${result.total_emergy_sej.toExponential(4)} sej`);
  } catch (e) {
    showToast(e.message, 'danger');
    log('error', e.message);
  } finally {
    btn.classList.remove('btn-loading');
    btn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Executar Simulação';
  }
}

function displayResult(result) {
  document.getElementById('result-card').style.display = 'block';
  document.getElementById('chart-placeholder').style.display = 'none';

  document.getElementById('res-total-emergy').textContent =
    `${result.total_emergy_sej.toExponential(4)} sej`;

  document.getElementById('res-eyr').textContent =
    result.emergy_yield_ratio != null ? result.emergy_yield_ratio.toFixed(3) : 'N/A';
  document.getElementById('res-elr').textContent =
    result.environmental_load_ratio != null ? result.environmental_load_ratio.toFixed(3) : '∞';
  document.getElementById('res-esi').textContent =
    result.sustainability_index != null ? result.sustainability_index.toFixed(3) : 'N/A';

  const pct = (result.renewable_fraction * 100).toFixed(1);
  document.getElementById('res-renewable-pct').textContent = `${pct}%`;
  document.getElementById('res-renewable-bar').style.width = `${pct}%`;

  // Tabela de contribuições
  const tbody = document.getElementById('contributions-table');
  tbody.innerHTML = result.contributions.map(c => `
    <tr>
      <td>${escHtml(c.process_name)}</td>
      <td class="text-end font-monospace">${c.emergy_sej.toExponential(3)}</td>
      <td class="text-end">
        <span class="badge bg-secondary">${c.percentage.toFixed(1)}%</span>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="3" class="text-center text-secondary">Sem dados</td></tr>';

  // Gráfico de pizza
  renderChart(result.contributions);
}

function renderChart(contributions) {
  const ctx = document.getElementById('flow-chart').getContext('2d');
  if (flowChart) flowChart.destroy();

  const top = contributions.slice(0, 7);
  const others = contributions.slice(7);
  const othersTotal = others.reduce((s, c) => s + c.emergy_sej, 0);
  const data = [...top];
  if (othersTotal > 0) data.push({ process_name: 'Outros', emergy_sej: othersTotal });

  const colors = [
    '#ffc107','#0d6efd','#198754','#dc3545','#0dcaf0',
    '#fd7e14','#6f42c1','#6c757d'
  ];

  flowChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.process_name),
      datasets: [{
        data: data.map(d => d.emergy_sej),
        backgroundColor: colors.slice(0, data.length),
        borderColor: '#1a1d21',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#adb5bd', font: { size: 11 }, boxWidth: 14 }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const val = ctx.raw;
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              return ` ${val.toExponential(3)} sej (${(val/total*100).toFixed(1)}%)`;
            }
          }
        }
      }
    }
  });
}

function copyResult() {
  const eyr = document.getElementById('res-eyr').textContent;
  const elr = document.getElementById('res-elr').textContent;
  const esi = document.getElementById('res-esi').textContent;
  const em  = document.getElementById('res-total-emergy').textContent;
  const text = `Emergia Total: ${em}\nEYR: ${eyr} | ELR: ${elr} | ESI: ${esi}`;
  navigator.clipboard.writeText(text).then(() => showToast('Copiado!', 'success'));
}

function copyExampleJson() {
  const text = document.getElementById('example-json').textContent;
  navigator.clipboard.writeText(text).then(() => showToast('JSON copiado!', 'success'));
}

// ── Import / Export ───────────────────────────────────────────────────────────

async function exportLCI() {
  window.open('/api/export', '_blank');
  log('info', 'Exportando base LCI...');
}

async function importLCI(input) {
  const file = input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/import', { method: 'POST', body: formData });
    if (!res.ok) throw new Error((await res.json()).detail);
    const data = await res.json();
    showToast(data.message, 'success');
    log('ok', data.message);
    await loadProcesses();
  } catch (e) {
    showToast(e.message, 'danger');
  }
  input.value = '';
}

// ── Utilitários ───────────────────────────────────────────────────────────────

function log(level, message) {
  const panel = document.getElementById('log-panel');
  const ts = new Date().toLocaleTimeString('pt-BR');
  const span = document.createElement('div');
  span.className = `log-${level}`;
  span.textContent = `[${ts}] ${message}`;
  panel.appendChild(span);
  panel.scrollTop = panel.scrollHeight;
}

function clearLog() {
  document.getElementById('log-panel').innerHTML =
    '<span class="text-secondary">Log limpo.</span>';
}

function showToast(message, type = 'success') {
  const toast = document.getElementById('feedback-toast');
  toast.className = `toast align-items-center text-bg-${type} border-0`;
  document.getElementById('toast-message').textContent = message;
  bootstrap.Toast.getOrCreateInstance(toast, { delay: 3000 }).show();
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
