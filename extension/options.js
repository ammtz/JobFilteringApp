const DEFAULT_API = "http://localhost:5000";

const apiBaseInput = document.getElementById("apiBase");
const dashboardUrlInput = document.getElementById("dashboardUrl");
const resumeNameInput = document.getElementById("resumeName");
const resumeText = document.getElementById("resumeText");
const saveBtn = document.getElementById("saveBtn");
const bookmarkletBtn = document.getElementById("bookmarkletBtn");
const status = document.getElementById("status");

async function loadSettings() {
  const { apiBase, dashboardUrl, resumeText: savedResume, resumeName: savedName } = await chrome.storage.local.get({ 
    apiBase: DEFAULT_API,
    dashboardUrl: "",
    resumeText: "",
    resumeName: ""
  });
  apiBaseInput.value = apiBase;
  dashboardUrlInput.value = dashboardUrl || "";
  resumeText.value = savedResume || "";
  resumeNameInput.value = savedName || "";
}

async function saveSettings() {
  const apiBase = apiBaseInput.value.trim() || DEFAULT_API;
  const dashboardUrl = dashboardUrlInput.value.trim();
  const resumeName = resumeNameInput.value.trim();
  const resumeTextValue = resumeText.value.trim();

  // Save to extension storage first (always, even if empty)
  await chrome.storage.local.set({
    apiBase,
    dashboardUrl,
    resumeText: resumeTextValue,
    resumeName: resumeName
  });

  // If resume text exists, also save to backend
  if (resumeTextValue) {
    try {
      const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: resumeTextValue }),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      status.textContent = `Settings saved.${resumeName ? ` Resume "${resumeName}" saved.` : " Resume saved."}`;
    } catch (error) {
      // Still show success for local storage, but warn about backend
      status.textContent = `Settings saved locally. Backend save failed: ${error.message || error}`;
      status.style.color = "#d32f2f";
      setTimeout(() => {
        status.style.color = "";
      }, 5000);
      return;
    }
  } else {
    status.textContent = "Settings saved.";
  }
}

saveBtn.addEventListener("click", saveSettings);
bookmarkletBtn.addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "REINSTALL_BOOKMARKLET" });
  status.textContent = "Bookmarklet reinstalled.";
});

loadSettings();
