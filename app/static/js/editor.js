// Editor cliente. Dispara comandos al backend y refresca el preview.
// Toda la lógica pesada (Decorator/Prototype/Command) vive en el servidor.

const shell = document.getElementById("editor-shell");
const projectId = shell.dataset.projectId;

const preview = document.getElementById("preview");
const previewWrap = document.getElementById("preview-wrap");
const overlay = document.getElementById("overlay");
const renderingOverlay = document.getElementById("rendering");
const layersList = document.getElementById("layers-list");
const layerCount = document.getElementById("layer-count");
const shapeColorInput = document.getElementById("shape-color");

const undoBadge = document.querySelector('[data-history="undo"]');
const redoBadge = document.querySelector('[data-history="redo"]');

let state = { project: null, history: { undo_count: 0, redo_count: 0 } };
let selectedLayerId = null;
let renderToken = 0;
const debounceTimers = new Map();

// ---------- helpers ----------
function api(path, options = {}) {
  return fetch(`/api/projects/${projectId}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });
}

function refreshPreview() {
  const token = ++renderToken;
  renderingOverlay.style.display = "flex";
  const url = `/api/projects/${projectId}/render?_v=${token}`;
  const img = new Image();
  img.onload = () => {
    if (token !== renderToken) return;
    preview.src = url;
    renderingOverlay.style.display = "none";
  };
  img.onerror = () => {
    renderingOverlay.style.display = "none";
  };
  img.src = url;
}

function debounce(key, fn, ms = 220) {
  if (debounceTimers.has(key)) clearTimeout(debounceTimers.get(key));
  debounceTimers.set(
    key,
    setTimeout(() => {
      debounceTimers.delete(key);
      fn();
    }, ms),
  );
}

// ---------- state ----------
async function loadState() {
  const data = await api("");
  state = data;
  renderLayersList();
  renderSelectionOverlay();
  syncFilterSliders();
  updateHistoryBadges();
}

function updateHistoryBadges() {
  undoBadge.textContent = state.history.undo_count;
  redoBadge.textContent = state.history.redo_count;
}

function getBaseImageLayer() {
  return state.project.layers.find((l) => l.kind === "image");
}

function syncFilterSliders() {
  const base = getBaseImageLayer();
  const filters = (base && base.data && base.data.filters) || [];
  document.querySelectorAll(".filter-row").forEach((row) => {
    const name = row.dataset.filter;
    const def = parseFloat(row.dataset.default);
    const fmt = row.dataset.fmt;
    const found = filters.find((f) => f.name === name);
    const value = found ? found.value : def;
    const slider = row.querySelector("input[type=range]");
    const readout = row.querySelector("[data-readout]");
    slider.value = value;
    readout.textContent = formatValue(value, fmt);
  });
}

function formatValue(value, fmt) {
  if (fmt === "%") return `${Math.round(value * 100)}%`;
  if (fmt === "px") return `${(+value).toFixed(1)}px`;
  return `${(+value).toFixed(2)}×`;
}

const layerTpl = document.getElementById("layer-row-template");

// ---------- selection overlay + canvas drag ----------
let dragState = null;

function getCanvasMetrics() {
  const rect = preview.getBoundingClientRect();
  const naturalW = state.project?.width || preview.naturalWidth || 1;
  const naturalH = state.project?.height || preview.naturalHeight || 1;
  const scaleX = rect.width / naturalW;
  const scaleY = rect.height / naturalH;
  return { rect, naturalW, naturalH, scaleX, scaleY };
}

function imageCoords(clientX, clientY) {
  const { rect, scaleX, scaleY } = getCanvasMetrics();
  return {
    x: (clientX - rect.left) / scaleX,
    y: (clientY - rect.top) / scaleY,
  };
}

function hitTestShape(imgX, imgY) {
  const candidates = state.project.layers
    .filter((l) => l.kind === "shape" && l.visible !== false)
    .sort((a, b) => b.z_index - a.z_index);
  for (const layer of candidates) {
    const { x = 0, y = 0, width = 0, height = 0 } = layer.data || {};
    if (imgX >= x && imgX <= x + width && imgY >= y && imgY <= y + height) {
      return layer;
    }
  }
  return null;
}

function renderSelectionOverlay() {
  overlay.innerHTML = "";
  if (selectedLayerId == null || !state.project) return;
  const layer = state.project.layers.find((l) => l.id === selectedLayerId);
  if (!layer || layer.kind !== "shape") return;
  const { x = 0, y = 0, width = 0, height = 0 } = layer.data || {};
  const { scaleX, scaleY } = getCanvasMetrics();
  const box = document.createElement("div");
  box.className = "selection-box";
  box.style.left = `${x * scaleX}px`;
  box.style.top = `${y * scaleY}px`;
  box.style.width = `${width * scaleX}px`;
  box.style.height = `${height * scaleY}px`;
  box.appendChild(Object.assign(document.createElement("span"), { className: "tr" }));
  box.appendChild(Object.assign(document.createElement("span"), { className: "bl" }));
  overlay.appendChild(box);
}

preview.addEventListener("pointerdown", (event) => {
  if (event.button !== 0) return;
  const { x, y } = imageCoords(event.clientX, event.clientY);
  const hit = hitTestShape(x, y);
  if (!hit) {
    selectedLayerId = null;
    renderLayersList();
    renderSelectionOverlay();
    return;
  }
  selectedLayerId = hit.id;
  dragState = {
    layerId: hit.id,
    startClientX: event.clientX,
    startClientY: event.clientY,
    startX: hit.data.x ?? 0,
    startY: hit.data.y ?? 0,
    currentX: hit.data.x ?? 0,
    currentY: hit.data.y ?? 0,
  };
  preview.setPointerCapture(event.pointerId);
  preview.style.cursor = "grabbing";
  renderLayersList();
  renderSelectionOverlay();
  event.preventDefault();
});

preview.addEventListener("pointermove", (event) => {
  if (!dragState) {
    const { x, y } = imageCoords(event.clientX, event.clientY);
    preview.style.cursor = hitTestShape(x, y) ? "grab" : "default";
    return;
  }
  const { scaleX, scaleY } = getCanvasMetrics();
  const dx = (event.clientX - dragState.startClientX) / scaleX;
  const dy = (event.clientY - dragState.startClientY) / scaleY;
  dragState.currentX = Math.round(dragState.startX + dx);
  dragState.currentY = Math.round(dragState.startY + dy);
  const layer = state.project.layers.find((l) => l.id === dragState.layerId);
  if (layer) {
    layer.data.x = dragState.currentX;
    layer.data.y = dragState.currentY;
    renderSelectionOverlay();
  }
});

preview.addEventListener("pointerup", async (event) => {
  if (!dragState) return;
  const { layerId, startX, startY, currentX, currentY } = dragState;
  dragState = null;
  try { preview.releasePointerCapture(event.pointerId); } catch (_) {}
  preview.style.cursor = "grab";
  if (currentX === startX && currentY === startY) return;
  const res = await api("/commands/update_layer", {
    method: "POST",
    body: JSON.stringify({
      layer_id: layerId,
      changes: { x: currentX, y: currentY },
    }),
  });
  state.history = res.history;
  await loadState();
  refreshPreview();
});

preview.addEventListener("pointerleave", () => {
  if (!dragState) preview.style.cursor = "default";
});

window.addEventListener("resize", renderSelectionOverlay);
preview.addEventListener("load", renderSelectionOverlay);

// ---------- layers UI ----------
function renderLayersList() {
  layersList.innerHTML = "";
  const sorted = [...state.project.layers].sort((a, b) => b.z_index - a.z_index);
  for (const layer of sorted) {
    const node = layerTpl.content.cloneNode(true);
    const li = node.querySelector("li");
    li.dataset.layerId = layer.id;
    if (layer.id === selectedLayerId) li.style.borderColor = "var(--color-accent)";
    const thumb = node.querySelector("[data-thumb]");
    const name = node.querySelector("[data-name]");
    const sub = node.querySelector("[data-sub]");

    if (layer.kind === "image") {
      thumb.innerHTML = '<svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h3l2-3h6l2 3h3v12H4z"/><circle cx="12" cy="13" r="3.5"/></svg>';
      name.textContent = "Base · imagen";
      const filterCount = ((layer.data && layer.data.filters) || []).length;
      sub.textContent = `${filterCount} filtros · z${layer.z_index}`;
    } else {
      const c = layer.data?.color || "#7c3aed";
      thumb.innerHTML = `<span class="inline-block h-3.5 w-3.5 rounded" style="background:${c}"></span>`;
      name.textContent = `Forma · ${layer.data?.type || "rect"}`;
      sub.textContent = `${layer.data?.width || 0}×${layer.data?.height || 0} · z${layer.z_index}`;
    }

    node.querySelector('[data-action="select"]').addEventListener("click", () => {
      selectedLayerId = layer.id;
      renderLayersList();
      renderSelectionOverlay();
    });
    node.querySelector('[data-action="clone"]').addEventListener("click", () => cloneLayer(layer.id));
    node.querySelector('[data-action="delete"]').addEventListener("click", () => deleteLayer(layer.id));

    layersList.appendChild(node);
  }
  layerCount.textContent = state.project.layers.length;
}

// ---------- commands ----------
async function applyFilterCommand(filterName, value) {
  const base = getBaseImageLayer();
  if (!base) return;
  const res = await api("/commands/apply_filter", {
    method: "POST",
    body: JSON.stringify({ layer_id: base.id, filter: filterName, value }),
  });
  state.history = res.history;
  updateHistoryBadges();
  await loadState();
  refreshPreview();
}

async function addShape(shapeType) {
  const color = shapeColorInput.value;
  const canvasW = state.project.width;
  const canvasH = state.project.height;
  const baseSize = Math.round(Math.min(canvasW, canvasH) * 0.3);
  const shapeW = baseSize;
  const shapeH = baseSize;
  const x = Math.round((canvasW - shapeW) / 2);
  const y = Math.round((canvasH - shapeH) / 2);
  const res = await api("/commands/add_shape", {
    method: "POST",
    body: JSON.stringify({
      data: {
        type: shapeType,
        color,
        x,
        y,
        width: shapeW,
        height: shapeH,
        opacity: 0.92,
        radius: 32,
        filters: [],
      },
    }),
  });
  state.history = res.history;
  selectedLayerId = res.result.layer.id;
  await loadState();
  refreshPreview();
}

async function cloneLayer(layerId) {
  const res = await api("/commands/clone_layer", {
    method: "POST",
    body: JSON.stringify({ source_layer_id: layerId }),
  });
  state.history = res.history;
  selectedLayerId = res.result.layer.id;
  await loadState();
  refreshPreview();
}

async function deleteLayer(layerId) {
  const target = state.project.layers.find((l) => l.id === layerId);
  if (target?.kind === "image") {
    alert("La capa base no se puede eliminar (es la foto original).");
    return;
  }
  const res = await api("/commands/delete_layer", {
    method: "POST",
    body: JSON.stringify({ layer_id: layerId }),
  });
  state.history = res.history;
  if (selectedLayerId === layerId) selectedLayerId = null;
  await loadState();
  refreshPreview();
}

async function undo() {
  const res = await api("/undo", { method: "POST" });
  if (!res.ok) return;
  state.history = res.history;
  await loadState();
  refreshPreview();
}

async function redo() {
  const res = await api("/redo", { method: "POST" });
  if (!res.ok) return;
  state.history = res.history;
  await loadState();
  refreshPreview();
}

// ---------- events ----------
document.querySelectorAll(".filter-row").forEach((row) => {
  const slider = row.querySelector("input[type=range]");
  const readout = row.querySelector("[data-readout]");
  const fmt = row.dataset.fmt;
  const filterName = row.dataset.filter;
  slider.addEventListener("input", () => {
    readout.textContent = formatValue(slider.value, fmt);
  });
  slider.addEventListener("change", () => {
    debounce(filterName, () => applyFilterCommand(filterName, parseFloat(slider.value)), 50);
  });
});

document.querySelectorAll("[data-shape]").forEach((btn) => {
  btn.addEventListener("click", () => addShape(btn.dataset.shape));
});

document.querySelector('[data-action="undo"]').addEventListener("click", undo);
document.querySelector('[data-action="redo"]').addEventListener("click", redo);

document.addEventListener("keydown", (event) => {
  if (event.target instanceof HTMLInputElement) return;
  const meta = event.metaKey || event.ctrlKey;
  if (meta && event.key.toLowerCase() === "z") {
    event.preventDefault();
    event.shiftKey ? redo() : undo();
  } else if (meta && event.key.toLowerCase() === "d") {
    event.preventDefault();
    if (selectedLayerId !== null) cloneLayer(selectedLayerId);
  } else if (event.key === "Backspace" || event.key === "Delete") {
    if (selectedLayerId !== null) {
      event.preventDefault();
      deleteLayer(selectedLayerId);
    }
  }
});

loadState();
