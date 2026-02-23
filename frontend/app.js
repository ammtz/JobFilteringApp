const apiInput = document.getElementById("apiBase");
const parseAllBtn = document.getElementById("parseAllBtn");
const cullAllBtn = document.getElementById("cullAllBtn");
const deleteSelectedBtn = document.getElementById("deleteSelectedBtn");
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
const abCompareBtn = document.getElementById("abCompareBtn");
const abModal = document.getElementById("abModal");
const abCloseBtn = document.getElementById("abCloseBtn");
const abSkipBtn = document.getElementById("abSkipBtn");
const abStatus = document.getElementById("abStatus");
const abComparison = document.getElementById("abComparison");

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
  abPair: null,
  rankMap: {},  // { job_id: rank }
};

const defaultApi = localStorage.getItem("filterjobs_api") || "http://localhost:5000";
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
    throw new Error("Set the API base URL first (⚙ Settings).");
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
  if (count > 0) {
    deleteSelectedBtn.classList.remove("hide");
  } else {
    deleteSelectedBtn.classList.add("hide");
  }
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
    jobList.innerHTML = `<div class="job-card">No jobs yet. Capture one via the extension.</div>`;
    jobCount.textContent = "0 jobs";
    return;
  }

  jobCount.textContent = `${state.jobs.length} job${state.jobs.length === 1 ? "" : "s"}`;
  jobList.innerHTML = state.jobs
    .map((job) => {
      const score = typeof job.score === "number" ? `${Math.round(job.score)}%` : "—";
      const rank = state.rankMap[job.id];
      const rankBadge = rank ? `<span class="tag accent">#${rank}</span>` : "";
      const title = job.title || "Untitled role";
      const meta = [job.company, job.location].filter(Boolean).join(" · ") || "Unknown source";
      const sourceLink = job.url
        ? `<a class="tag tag-link" href="${escapeHtml(job.url)}" target="_blank" rel="noreferrer">Source</a>`
        : "";
      const prefTag = typeof job.preference_score === "number"
        ? `<span class="tag">Pref: ${Math.round(job.preference_score)}</span>`
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
            ${rankBadge}
            <span class="tag">Score: ${score}</span>
            ${prefTag}
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

async function sortJobs() {
  try {
    const response = await apiFetch("/api/v1/sort", {
      method: "POST",
      body: JSON.stringify({}),
    });
    const result = await response.json();
    setToast(result.message || `Sorted ${result.sorted_count} job(s).`, "success");
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
  }
}

async function rankJobs() {
  try {
    const response = await apiFetch("/api/v1/rank");
    const result = await response.json();
    if (result.ranked && result.ranked.length) {
      state.rankMap = {};
      result.ranked.forEach((entry) => {
        state.rankMap[entry.job_id] = entry.rank;
      });
      const top = result.ranked[0];
      setToast(
        `Ranked ${result.ranked.length} jobs. #1: ${top.title || "Untitled"} @ ${top.company || "?"}`,
        "success"
      );
      renderJobs();
    } else {
      setToast("No ranked jobs returned.", "error");
    }
  } catch (error) {
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

function renderStructuredRequirements(structured) {
  if (!structured || Object.keys(structured).length === 0) {
    return "<p><em>Not yet sorted. Use 'Sort Things' to extract structured requirements.</em></p>";
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
  html += "</div>";
  return html;
}

function buildAbJobCard(job) {
  const title = escapeHtml(job.title || "Untitled role");
  const meta = escapeHtml([job.company, job.location].filter(Boolean).join(" · ") || "Unknown source");
  const about = job.about_summary
    ? `<p class="ab-summary">${escapeHtml(job.about_summary)}</p>`
    : "";
  const prefTag = typeof job.preference_score === "number"
    ? `<div class="job-tags"><span class="tag">ELO: ${Math.round(job.preference_score)}</span></div>`
    : "";
  return `
    <div class="ab-job">
      <div>
        <h3>${title}</h3>
        <div class="job-meta">${meta}</div>
        ${about}
        ${prefTag}
      </div>
      <button class="primary ab-choose" data-id="${job.id}" type="button">Choose this role</button>
    </div>
  `;
}

async function loadPair() {
  abModal.classList.remove("hidden");
  abModal.setAttribute("aria-hidden", "false");
  abStatus.textContent = "Loading comparison...";
  abComparison.innerHTML = "";
  try {
    const response = await apiFetch("/api/v1/preferences/pair");
    const data = await response.json();
    state.abPair = data;
    abStatus.textContent = "Which role fits you better?";
    abComparison.innerHTML = `
      ${buildAbJobCard(data.job_a)}
      <div class="ab-divider"></div>
      ${buildAbJobCard(data.job_b)}
    `;
  } catch (error) {
    abStatus.textContent = `Could not load pair: ${error.message}`;
  }
}

async function recordChoice(chosenId) {
  if (!state.abPair) return;
  abStatus.textContent = "Saving preference...";
  abComparison.innerHTML = "";
  try {
    await apiFetch("/api/v1/preferences", {
      method: "POST",
      body: JSON.stringify({
        job_a_id: state.abPair.job_a.id,
        job_b_id: state.abPair.job_b.id,
        chosen_job_id: chosenId,
      }),
    });
    await loadPair();
  } catch (error) {
    abStatus.textContent = `Error: ${error.message}`;
  }
}

function closeAbModal() {
  abModal.classList.add("hidden");
  abModal.setAttribute("aria-hidden", "true");
  state.abPair = null;
  loadJobs();
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
    detailReasoning.textContent = job.reasoning || job.guidance_3_sentences || "No reasoning yet.";
    detailDownsides.textContent = job.downsides || "—";
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

async function deleteSelected() {
  const ids = Array.from(state.selected);
  if (!ids.length) return;
  if (!window.confirm(`Delete ${ids.length} selected job${ids.length === 1 ? "" : "s"}? This cannot be undone.`)) return;
  try {
    await Promise.all(ids.map((id) => apiFetch(`/api/v1/jobs/${id}`, { method: "DELETE" })));
    setToast(`Deleted ${ids.length} job${ids.length === 1 ? "" : "s"}.`, "success");
    await loadJobs();
  } catch (error) {
    setToast(error.message, "error");
    await loadJobs();
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

uploadResumeBtn.addEventListener("click", uploadResume);
parseAllBtn.addEventListener("click", sortJobs);
cullAllBtn.addEventListener("click", rankJobs);
deleteSelectedBtn.addEventListener("click", deleteSelected);

analyzedOnlyToggle.addEventListener("change", loadJobs);
refreshBtn.addEventListener("click", async () => {
  const originalText = refreshBtn.textContent;
  refreshBtn.textContent = "Refreshing…";
  refreshBtn.classList.add("loading");
  try {
    const ok = await pingApi();
    await loadJobs();
    if (ok) {
      setToast("Refreshed. API healthy.", "success");
    } else {
      setToast("Refresh complete, API offline.", "error");
    }
  } finally {
    refreshBtn.classList.remove("loading");
    refreshBtn.textContent = originalText;
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
    closeAbModal();
  }
});

abCompareBtn.addEventListener("click", loadPair);
abCloseBtn.addEventListener("click", closeAbModal);
abSkipBtn.addEventListener("click", loadPair);
abComparison.addEventListener("click", (event) => {
  const btn = event.target.closest(".ab-choose");
  if (!btn || !state.abPair) return;
  recordChoice(btn.dataset.id);
});
abModal.addEventListener("click", (event) => {
  if (event.target === abModal) closeAbModal();
});

pingApi();
loadJobs();
