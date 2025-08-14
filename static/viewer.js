import * as pdfjs from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.5.136/build/pdf.mjs";

// Configure worker (required)
pdfjs.GlobalWorkerOptions.workerSrc =
  "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.5.136/build/pdf.worker.mjs";

const canvas = document.getElementById("pdfCanvas");
const ctx = canvas.getContext("2d");

// Controls
const prevBtn = document.getElementById("prevBtn");
const nextBtn = document.getElementById("nextBtn");
const zoomInBtn = document.getElementById("zoomInBtn");
const zoomOutBtn = document.getElementById("zoomOutBtn");
const fitBtn = document.getElementById("fitBtn");
const pageNumEl = document.getElementById("pageNum");
const pageCountEl = document.getElementById("pageCount");

// State
let pdf = null;
let pageNum = 1;
let scale = 1.25;  // default zoom
let baseViewportWidth = null;

async function fetchArrayBuffer(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.arrayBuffer();
}

async function loadDocument() {
  const url = `/pdf/${window.__DOC_ID__}`;
  const buffer = await fetchArrayBuffer(url);

  const loadingTask = pdfjs.getDocument({ data: buffer });
  pdf = await loadingTask.promise;

  pageCountEl.textContent = pdf.numPages;
  await renderPage(pageNum, true);
}

async function renderPage(num, fit = false) {
  const page = await pdf.getPage(num);

  // Determine scale to fit canvas-shell width if requested
  const canvasShell = document.querySelector(".canvas-shell");
  let viewport = page.getViewport({ scale: 1 });
  if (fit) {
    const targetWidth = canvasShell.clientWidth;
    scale = targetWidth / viewport.width;
  }
  viewport = page.getViewport({ scale });

  // Resize canvas
  canvas.width = Math.floor(viewport.width);
  canvas.height = Math.floor(viewport.height);

  // Render
  await page.render({
    canvasContext: ctx,
    viewport
  }).promise;

  pageNumEl.textContent = num;
}

// Controls handlers
prevBtn.addEventListener("click", async () => {
  if (pageNum <= 1) return;
  pageNum--;
  await renderPage(pageNum);
});

nextBtn.addEventListener("click", async () => {
  if (pageNum >= pdf.numPages) return;
  pageNum++;
  await renderPage(pageNum);
});

zoomInBtn.addEventListener("click", async () => {
  scale *= 1.15;
  await renderPage(pageNum);
});

zoomOutBtn.addEventListener("click", async () => {
  scale = Math.max(0.2, scale / 1.15);
  await renderPage(pageNum);
});

fitBtn.addEventListener("click", async () => {
  await renderPage(pageNum, true);
});

// Auto-fit on first load and on resize
window.addEventListener("resize", () => renderPage(pageNum, true));
loadDocument().catch(err => {
  console.error(err);
  alert("Failed to load PDF.");
});
