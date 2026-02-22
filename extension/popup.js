const statusArea = document.getElementById("statusArea");

function setStatus(message, kind = "info") {
  statusArea.textContent = message;
  statusArea.className = `status ${kind}`;
}

function sendMessage(type) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type }, (response) => {
      if (chrome.runtime.lastError) {
        resolve({
          ok: false,
          message: chrome.runtime.lastError.message || "Extension error.",
          kind: "error",
        });
        return;
      }
      resolve(response || { ok: false, message: "No response from background.", kind: "error" });
    });
  });
}

async function handleAction(type, pendingMessage) {
  setStatus(pendingMessage, "info");
  const result = await sendMessage(type);
  setStatus(result.message || "Done.", result.kind || (result.ok ? "success" : "error"));
}

document.getElementById("captureBtn").addEventListener("click", () => {
  handleAction("CAPTURE_JOB", "Capturing job...");
});

document.getElementById("dashboardBtn").addEventListener("click", async () => {
  const result = await sendMessage("OPEN_DASHBOARD");
  if (!result.ok) {
    setStatus(result.message || "Could not open dashboard.", "error");
  }
});

document.getElementById("optionsBtn").addEventListener("click", () => {
  chrome.runtime.openOptionsPage();
});
