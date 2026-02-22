const apiInput = document.getElementById("apiBase");
const parseAllBtn = document.getElementById("parseAllBtn");
const parseSelectedBtn = document.getElementById("parseSelectedBtn");
const forceParseAllBtn = document.getElementById("forceParseAllBtn");
const cullAllBtn = document.getElementById("cullAllBtn");
const cullSelectedBtn = document.getElementById("cullSelectedBtn");
const bookmarkletBox = document.getElementById("bookmarkletBox");
const ingestBookmarkletBtn = document.getElementById("ingestBookmarkletBtn");
const bookmarkletStatus = document.getElementById("bookmarkletStatus");
const resumeFile = document.getElementById("resumeFile");
const uploadResumeBtn = document.getElementById("uploadResumeBtn");
const resumeStatus = document.getElementById("resumeStatus");
const analyzedOnlyToggle = document.getElementById("analyzedOnly");
const toast = document.getElementById("toast");
const jobList = document.getElementById("jobList");
const jobCount = document.getElementById("jobCount");
const apiStatus = document.getElementById("apiStatus");
const refreshBtn = document.getElementById("refreshBtn");
const selectionHint = document.getElementById("selectionHint");
const detailModal = document.getElementById("detailModal");
const closeModal = document.getElementById("closeModal");

const detailTitle = document.getElementById("detailTitle");
const detailMeta = document.getElementById("detailMeta");
const detailRecommendation = document.getElementById("detailRecommendation");
const detailReasoning = document.getElementById("detailReasoning");
const detailDownsides = document.getElementById("detailDownsides");
const detailRaw = document.getElementById("detailRaw");
const detailAnalysis = document.getElementById("detailAnalysis");
const detailStructured = document.getElementById("detailStructured");
const detailTitleInput = document.getElementById("detailTitleInput");
const detailCompanyInput = document.getElementById("detailCompanyInput");
const detailLocationInput = document.getElementById("detailLocationInput");
const detailUrlInput = document.getElementById("detailUrlInput");
const detailUrlLink = document.getElementById("detailUrlLink");
const saveJobBtn = document.getElementById("saveJobBtn");
const deleteJobBtn = document.getElementById("deleteJobBtn");

const state = {
  jobs: [],
  selected: new Set(),
  currentJobId: null,
};

const defaultApi = localStorage.getItem("filterjobs_api") || "http://localhost:8000";
apiInput.value = defaultApi;

function setToast(message, tone = "info") {
  toast.textContent = message;
  toast.dataset.tone = tone;
}

function setStatus(label, ok) {
  apiStatus.textContent = label;
  apiStatus.style.background = ok ? "rgba(16, 120, 90, 0.16)" : "rgba(255, 190, 140, 0.35)";
  apiStatus.style.color = ok ? "#0c5c4a" : "#8d3b22";
}

function apiBase() {
  const raw = apiInput.value.trim();
  if (!raw) {
    return "";
  }
  return raw.replace(/\/$/, "");
}

async function apiFetch(path, options = {}) {
  const base = apiBase();
  if (!base) {
    throw new Error("Set the API base URL first.");
  }
  const response = await fetch(`${base}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response;
}

async function pingApi() {
  try {
    const response = await apiFetch("/health");
    const body = await response.json();
    setStatus(`API: ${body.status || "ok"}`, true);
    return true;
  } catch (error) {
    setStatus("API: offline", false);
    return false;
  }
}

function updateSelectionHint() {
  const count = state.selected.size;
  selectionHint.textContent = `${count} selected`;
}

function ensurePdfWorker() {
  if (!window.pdfjsLib) {
    throw new Error("PDF parser not loaded. Check your internet connection.");
  }
  if (!window.pdfjsLib.GlobalWorkerOptions.workerSrc) {
    window.pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  }
}

async function extractPdfText(file) {
  ensurePdfWorker();
  const data = new Uint8Array(await file.arrayBuffer());
  const pdf = await window.pdfjsLib.getDocument({ data }).promise;
  let combinedText = "";
  for (let pageIndex = 1; pageIndex <= pdf.numPages; pageIndex += 1) {
    const page = await pdf.getPage(pageIndex);
    const content = await page.getTextContent();
    const pageText = content.items.map((item) => item.str).join(" ");
    combinedText += `${pageText}\n`;
  }
  return { text: combinedText.trim(), pages: pdf.numPages };
}

async function loadJobs() {
  try {
    state.selected.clear();
    updateSelectionHint();
    const params = new URLSearchParams();
    if (analyzedOnlyToggle.checked) {
      params.set("analyzed_only", "true");
    }
    const response = await apiFetch(`/api/v1/jobs?${params.toString()}`);
    state.jobs = await response.json();
    renderJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

function renderJobs() {
  if (!state.jobs.length) {
    jobList.innerHTML = `<div class="job-card">No jobs yet. Ingest the first one!</div>`;
    jobCount.textContent = "0 jobs";
    return;
  }

  jobCount.textContent = `${state.jobs.length} job${state.jobs.length === 1 ? "" : "s"}`;
  jobList.innerHTML = state.jobs
    .map((job) => {
      const score = typeof job.score === "number" ? `${Math.round(job.score)}%` : "—";
      const title = job.title || "Untitled role";
      const meta = [job.company, job.location].filter(Boolean).join(" · ") || "Unknown source";
      const sourceLink = job.url
        ? `<a class="tag tag-link" href="${escapeHtml(job.url)}" target="_blank" rel="noreferrer">Source</a>`
        : "";
      return `
        <article class="job-card" data-id="${job.id}">
          <header>
            <div>
              <h3>${escapeHtml(title)}</h3>
              <div class="job-meta">${escapeHtml(meta)}</div>
            </div>
            <label class="job-checkbox">
              <input type="checkbox" class="select-job" data-id="${job.id}" />
              Select
            </label>
          </header>
          <div class="job-tags">
            <span class="tag">Score: ${score}</span>
            ${sourceLink}
          </div>
          <div class="job-actions">
            <button class="ghost" data-action="edit">Edit</button>
            <button class="danger" data-action="delete">Delete</button>
          </div>
        </article>
      `;
    })
    .join("");
}

async function parseJobs(jobIds, force = false) {
  try {
    const payload = jobIds ? { job_ids: jobIds, force: force } : { force: force };
    const response = await apiFetch("/api/v1/parse", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    setToast(result.message || `Parsed ${result.parsed_count} job(s).`);
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

async function analyzeJobs(jobIds) {
  try {
    const payload = jobIds ? { job_ids: jobIds } : {};
    const response = await apiFetch("/api/v1/analyze", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    setToast(result.message || "Analysis complete.");
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

function isBookmarkletPayload(obj) {
  return obj && typeof obj === "object" && "v" in obj && "url" in obj && "description_text" in obj;
}

async function ingestBookmarklet() {
  const raw = bookmarkletBox?.value?.trim();
  if (!raw) {
    setToast("Paste bookmarklet JSON first.", "error");
    return;
  }
  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_) {
    setToast("Invalid JSON.", "error");
    return;
  }
  if (!isBookmarkletPayload(payload)) {
    setToast("Expected bookmarklet shape: v, url, page_title, description_text.", "error");
    return;
  }
  const v1Body = {
    title: payload.page_title || null,
    url: payload.url || null,
    raw_text: (payload.description_text || "").trim() || "(no description)",
    raw_data: payload,
  };
  bookmarkletStatus.textContent = "Ingesting...";
  try {
    await apiFetch("/api/v1/ingest", { method: "POST", body: JSON.stringify(v1Body) });
    bookmarkletStatus.textContent = "Saved.";
    bookmarkletBox.value = "";
    setToast("Job ingested.");
    await loadJobs();
  } catch (error) {
    bookmarkletStatus.textContent = "Failed.";
    setToast(error.message, "error");
  }
}

async function uploadResume() {
  try {
    const file = resumeFile.files?.[0];
    if (!file) {
      setToast("Select a PDF resume first.", "error");
      return;
    }
    if (file.type !== "application/pdf") {
      setToast("Resume must be a PDF file.", "error");
      return;
    }
    resumeStatus.textContent = `Reading ${file.name}...`;
    const { text, pages } = await extractPdfText(file);
    if (!text) {
      setToast("Could not extract text from this PDF.", "error");
      resumeStatus.textContent = "No text extracted.";
      return;
    }
    await apiFetch("/api/v1/resume", {
      method: "POST",
      body: JSON.stringify({ text }),
    });
    resumeStatus.textContent = `Uploaded ${file.name} (${pages} page${pages === 1 ? "" : "s"}).`;
    setToast("Resume saved.", "success");
  } catch (error) {
    resumeStatus.textContent = "Upload failed.";
    setToast(error.message, "error");
  }
}

async function beginCull(jobIds) {
  try {
    const payload = jobIds ? { job_ids: jobIds } : {};
    const response = await apiFetch("/api/v1/cull", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (result.top_jobs && result.top_jobs.length) {
      setToast(`Cull complete. Top ${result.top_jobs.length} returned.`);
    } else {
      setToast("Cull complete. No jobs returned.");
    }
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

function renderStructuredRequirements(structured) {
  if (!structured || Object.keys(structured).length === 0) {
    return "<p><em>Not yet parsed. Use 'Parse Jobs' to extract structured requirements.</em></p>";
  }
  
  const sections = [
    { key: "about_summary", label: "About the Job" },
    { key: "experience_requirements", label: "Experience Requirements" },
    { key: "expertise_requirements", label: "Expertise & Skills" },
    { key: "business_cultural_requirements", label: "Business & Cultural Fit" },
    { key: "sponsorship_requirements", label: "Sponsorship & International" },
    { key: "work_location_requirements", label: "Work Location" },
    { key: "education_requirements", label: "Education & Certifications" },
  ];
  
  let html = '<div class="structured-requirements">';
  for (const section of sections) {
    const value = structured[section.key];
    if (value && value.trim()) {
      html += `
        <div class="requirement-section">
          <h5>${section.label}</h5>
          <p>${value}</p>
        </div>
      `;
    }
  }
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  if (text == null) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function showDetailModalPlaceholder() {
  state.currentJobId = null;
  detailTitle.textContent = "Job details";
  detailMeta.textContent = "Loading…";
  detailTitleInput.value = "";
  detailCompanyInput.value = "";
  detailLocationInput.value = "";
  detailUrlInput.value = "";
  detailUrlLink.href = "#";
  detailUrlLink.textContent = "Open posting";
  detailRecommendation.textContent = "—";
  detailReasoning.textContent = "—";
  detailDownsides.textContent = "—";
  detailRaw.textContent = "";
  detailAnalysis.textContent = "";
  detailStructured.innerHTML = "<p><em>Loading…</em></p>";
  detailModal.classList.remove("hidden");
  detailModal.setAttribute("aria-hidden", "false");
}

async function openDetails(jobId) {
  showDetailModalPlaceholder();
  state.currentJobId = jobId;
  try {
    const response = await apiFetch(`/api/v1/jobs/${jobId}`);
    const job = await response.json();
    state.currentJobId = job.id;
    detailTitle.textContent = job.title || "Untitled role";
    const meta = [job.company, job.location, job.url].filter(Boolean).join(" · ");
    detailMeta.textContent = meta || "No meta data";
    detailTitleInput.value = job.title || "";
    detailCompanyInput.value = job.company || "";
    detailLocationInput.value = job.location || "";
    detailUrlInput.value = job.url || "";
    if (job.url) {
      detailUrlLink.href = job.url;
      detailUrlLink.textContent = "Open posting";
    } else {
      detailUrlLink.href = "#";
      detailUrlLink.textContent = "No source link";
    }
    detailRecommendation.textContent = job.resume_recommendation || "No recommendation yet.";
    detailReasoning.textContent = job.reasoning || "No reasoning yet.";
    detailDownsides.textContent = job.downsides || "No downsides yet.";
    detailRaw.textContent = job.raw_text || "";
    detailAnalysis.textContent = job.analysis ? JSON.stringify(job.analysis, null, 2) : "No analysis payload.";
    detailStructured.innerHTML = renderStructuredRequirements(job.structured_requirements);
  } catch (error) {
    setToast(error.message, "error");
    detailMeta.textContent = "Failed to load job.";
    detailStructured.innerHTML = `<p><em>Could not load details: ${escapeHtml(error.message)}</em></p>`;
  }
}

async function saveJobEdits() {
  if (!state.currentJobId) {
    setToast("No job selected.", "error");
    return;
  }
  try {
    const payload = {
      title: detailTitleInput.value.trim(),
      company: detailCompanyInput.value.trim(),
      location: detailLocationInput.value.trim(),
      url: detailUrlInput.value.trim(),
    };
    const response = await apiFetch(`/api/v1/jobs/${state.currentJobId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    const job = await response.json();
    detailTitle.textContent = job.title || "Untitled role";
    const meta = [job.company, job.location, job.url].filter(Boolean).join(" · ");
    detailMeta.textContent = meta || "No meta data";
    setToast("Job updated.", "success");
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

async function deleteJob(jobId) {
  try {
    await apiFetch(`/api/v1/jobs/${jobId}`, { method: "DELETE" });
    setToast("Job deleted.", "success");
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

function closeDetails() {
  detailModal.classList.add("hidden");
  detailModal.setAttribute("aria-hidden", "true");
}

apiInput.addEventListener("change", () => {
  localStorage.setItem("filterjobs_api", apiBase());
  pingApi();
  loadJobs();
});

ingestBookmarkletBtn.addEventListener("click", ingestBookmarklet);
uploadResumeBtn.addEventListener("click", uploadResume);
parseAllBtn.addEventListener("click", () => parseJobs(null, false));
forceParseAllBtn.addEventListener("click", () => parseJobs(null, true));
parseSelectedBtn.addEventListener("click", () => {
  const selected = Array.from(state.selected);
  if (!selected.length) {
    setToast("Select jobs first.", "error");
    return;
  }
  parseJobs(selected, false);
});
cullAllBtn.addEventListener("click", () => beginCull(null));
cullSelectedBtn.addEventListener("click", () => {
  const selected = Array.from(state.selected);
  if (!selected.length) {
    setToast("Select jobs first.", "error");
    return;
  }
  beginCull(selected);
});

analyzedOnlyToggle.addEventListener("change", loadJobs);
refreshBtn.addEventListener("click", async () => {
  const ok = await pingApi();
  await loadJobs();
  if (ok) {
    setToast("Refreshed. API healthy.", "success");
  } else {
    setToast("Refresh complete, API offline.", "error");
  }
});
jobList.addEventListener("change", (event) => {
  const target = event.target;
  if (target.matches(".select-job")) {
    const jobId = target.dataset.id;
    if (target.checked) {
      state.selected.add(jobId);
    } else {
      state.selected.delete(jobId);
    }
    updateSelectionHint();
  }
});

jobList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const card = button.closest(".job-card");
  if (!card) return;
  const jobId = card.dataset.id;
  if (button.dataset.action === "edit") {
    openDetails(jobId);
    detailTitleInput.focus();
  }
  if (button.dataset.action === "delete") {
    if (window.confirm("Delete this job? This cannot be undone.")) {
      deleteJob(jobId);
    }
  }
});

closeModal.addEventListener("click", closeDetails);
saveJobBtn.addEventListener("click", saveJobEdits);
deleteJobBtn.addEventListener("click", () => {
  if (state.currentJobId && window.confirm("Delete this job? This cannot be undone.")) {
    deleteJob(state.currentJobId);
    closeDetails();
  }
});
detailModal.addEventListener("click", (event) => {
  if (event.target === detailModal) {
    closeDetails();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeDetails();
  }
});

pingApi();
loadJobs();
