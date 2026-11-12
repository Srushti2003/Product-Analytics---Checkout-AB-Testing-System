"use strict";

const byId = (id) => document.getElementById(id);
const { pages, metrics, stages } = JSON.parse(byId("portfolio-data").textContent);
const repository = "Srushti2003/Product-Analytics---Checkout-AB-Testing-System";
const original = "https://github.com/" + repository + "/blob/main/";
const raw = "https://raw.githubusercontent.com/" + repository + "/main/";
const pagesHost = "https://srushti2003.github.io/Product-Analytics---Checkout-AB-Testing-System/";

function updatePressed(buttons, selected) {
  buttons.forEach((button) => button.setAttribute("aria-pressed", String(button === selected)));
}

const metricButtons = document.querySelectorAll("[data-metric]");
const comparisonBars = document.querySelectorAll("#comparison-bars .bar-row");
metricButtons.forEach((button) => button.addEventListener("click", () => {
  const metric = metrics[Number(button.dataset.metric)];
  updatePressed(metricButtons, button);
  byId("comparison-name").textContent = metric.name;
  byId("comparison-difference").textContent = metric.detail;
  byId("comparison-note").textContent = metric.note;
  byId("comparison-source").href = metric.url;
  comparisonBars.forEach((bar, index) => {
    bar.querySelector("strong").textContent = metric.values[index];
    bar.querySelector(".track i").style.setProperty("--fill", metric.widths[index] + "%");
  });
}));

const stageButtons = document.querySelectorAll("[data-stage]");
stageButtons.forEach((button) => button.addEventListener("click", () => {
  const stage = stages[Number(button.dataset.stage)];
  updatePressed(stageButtons, button);
  byId("stage-tool").textContent = stage.tool;
  byId("stage-name").textContent = stage.name;
  byId("stage-description").textContent = stage.description;
  byId("stage-source").href = stage.url;
}));

// A detached image prevents an outdated request from changing the selected page.
async function loadFirst(sources, stillSelected) {
  for (const source of sources) {
    if (!stillSelected()) return null;
    const image = new Image();
    image.decoding = "async";
    image.src = source;
    try {
      await image.decode();
      return image.currentSrc || image.src;
    } catch {
      // Try the next copy of the same original screenshot.
    }
  }
  return null;
}

const thumbs = document.querySelectorAll("[data-page]");
const gallery = document.querySelector(".gallery");
const reportImage = byId("report-image");
const display = byId("report-display");
const enlarge = byId("enlarge");
const viewer = byId("viewer");
const viewerImage = byId("viewer-img");
const zoom = byId("viewer-zoom");
let current = 0;
let previewRequest = 0;
let viewerRequest = 0;

function originals(page) {
  return [page.path, raw + page.path, pagesHost + page.path];
}

function resetZoom() {
  viewerImage.parentElement.classList.remove("zoomed");
  zoom.setAttribute("aria-pressed", "false");
  zoom.textContent = "Zoom";
  viewerImage.parentElement.scrollTo(0, 0);
}

async function renderViewer() {
  const request = ++viewerRequest;
  const page = pages[current];
  byId("viewer-title").textContent = page.name;
  byId("viewer-source").href = original + page.path;
  byId("viewer-error").hidden = true;
  viewerImage.hidden = true;
  zoom.disabled = true;
  resetZoom();
  const active = () => request === viewerRequest && viewer.open;
  const src = await loadFirst(originals(page), active);
  if (!active()) return;
  if (src) {
    viewerImage.width = page.width;
    viewerImage.height = page.height;
    viewerImage.src = src;
    viewerImage.alt = "Power BI " + page.name + ". " + page.description;
    viewerImage.hidden = false;
    zoom.disabled = false;
  } else {
    byId("viewer-error").hidden = false;
  }
}

async function selectPage(index, initial = false) {
  current = (index + pages.length) % pages.length;
  const request = ++previewRequest;
  const page = pages[current];
  byId("page-count").textContent = "Page " + (current + 1) + " of " + pages.length;
  byId("page-title").textContent = page.name;
  display.style.aspectRatio = page.width + " / " + page.height;
  byId("page-description").textContent = page.description;
  byId("image-source").href = byId("error-source").href = original + page.path;
  updatePressed(thumbs, thumbs[current]);
  if (viewer.open) void renderViewer();

  if (initial && reportImage.complete && reportImage.naturalWidth) {
    enlarge.disabled = false;
    return;
  }
  display.setAttribute("aria-busy", "true");
  reportImage.hidden = true;
  byId("report-error").hidden = true;
  byId("report-loading").hidden = false;
  enlarge.disabled = true;
  const active = () => request === previewRequest;
  const src = await loadFirst(["portfolio-assets/report-" + (current + 1) + ".webp", ...originals(page)], active);
  if (!active()) return;
  display.setAttribute("aria-busy", "false");
  byId("report-loading").hidden = true;
  if (src) {
    reportImage.width = page.width;
    reportImage.height = page.height;
    reportImage.src = src;
    reportImage.alt = "Power BI " + page.name + ". " + page.description;
    reportImage.hidden = false;
    enlarge.disabled = false;
  } else {
    byId("report-error").hidden = false;
  }
}

thumbs.forEach((button) => {
  button.addEventListener("click", () => selectPage(Number(button.dataset.page)));
  const thumbnail = button.querySelector("img");
  const fallback = () => { thumbnail.hidden = true; };
  thumbnail.addEventListener("error", fallback);
  if (thumbnail.complete && !thumbnail.naturalWidth) fallback();
});

for (const id of ["prev-page", "viewer-prev"]) {
  byId(id).addEventListener("click", () => selectPage(current - 1));
}
for (const id of ["next-page", "viewer-next"]) {
  byId(id).addEventListener("click", () => selectPage(current + 1));
}
function handleArrows(event) {
  if (event.altKey || event.ctrlKey || event.metaKey) return;
  if (viewer.open && zoom.getAttribute("aria-pressed") === "true" &&
      event.target === viewerImage.parentElement) return;
  const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
  if (!step) return;
  event.preventDefault();
  void selectPage(current + step);
}
gallery.addEventListener("keydown", handleArrows);
viewer.addEventListener("keydown", handleArrows);
enlarge.addEventListener("click", () => {
  viewer.showModal();
  void renderViewer();
});
byId("viewer-close").addEventListener("click", () => viewer.close());
viewer.addEventListener("close", () => {
  ++viewerRequest;
  if (!enlarge.disabled) enlarge.focus();
  else byId("next-page").focus();
});
zoom.addEventListener("click", () => {
  if (zoom.getAttribute("aria-pressed") === "true") {
    resetZoom();
  } else {
    viewerImage.parentElement.classList.add("zoomed");
    zoom.setAttribute("aria-pressed", "true");
    zoom.textContent = "Fit image";
    viewerImage.parentElement.focus();
  }
});

const initialObserver = new IntersectionObserver(([entry]) => {
  if (!entry.isIntersecting) return;
  initialObserver.disconnect();
  if (!previewRequest) void selectPage(0, true);
});
initialObserver.observe(display);

if (!matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const revealObserver = new IntersectionObserver((entries) => {
    entries.filter((entry) => entry.isIntersecting).forEach(({ target }) => {
      target.animate([{ opacity: .65, transform: "translateY(8px)" }, { opacity: 1, transform: "none" }],
        { duration: 360, easing: "ease-out" });
      revealObserver.unobserve(target);
    });
  }, { threshold: .15 });
  document.querySelectorAll(".section .intro").forEach((element) => revealObserver.observe(element));
}
