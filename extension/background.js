const DEFAULT_API = "http://localhost:5000";

async function getApiBase() {
  const { apiBase } = await chrome.storage.local.get({ apiBase: DEFAULT_API });
  return apiBase.replace(/\/$/, "");
}

const BADGE_DURATION_MS = 4000;
const BADGE_STYLES = {
  success: { text: "OK", color: "#2E7D32" },
  info: { text: "INFO", color: "#1565C0" },
  error: { text: "ERR", color: "#C62828" },
};

function badgeFallback(kind, title, message) {
  try {
    if (!chrome.action || !chrome.action.setBadgeText) {
      console.log(`[FilterJobs] ${title}: ${message}`);
      return;
    }
    const style = BADGE_STYLES[kind] || BADGE_STYLES.info;
    chrome.action.setBadgeBackgroundColor({ color: style.color });
    chrome.action.setBadgeText({ text: style.text });
    chrome.action.setTitle({ title: `${title} - ${message}` });
    setTimeout(() => {
      chrome.action.setBadgeText({ text: "" });
    }, BADGE_DURATION_MS);
  } catch (error) {
    console.log(`[FilterJobs] ${title}: ${message}`);
  }
}

function getNotificationPermissionLevel() {
  if (!chrome.notifications || !chrome.notifications.getPermissionLevel) {
    return Promise.resolve("unknown");
  }
  return new Promise((resolve) => {
    chrome.notifications.getPermissionLevel((level) => {
      if (chrome.runtime.lastError) {
        console.warn("FilterJobs: Notification permission check failed:", chrome.runtime.lastError);
        resolve("unknown");
        return;
      }
      resolve(level);
    });
  });
}

async function notify(title, message, kind = "info") {
  try {
    if (!chrome.notifications || !chrome.notifications.create) {
      console.warn("FilterJobs: Notifications API unavailable. Falling back to badge.");
      badgeFallback(kind, title, message);
      return null;
    }

    const level = await getNotificationPermissionLevel();
    if (level === "denied") {
      console.warn("FilterJobs: Notifications are denied. Enable in Chrome settings.");
      badgeFallback(kind, title, message);
      return null;
    }

    const notificationId = await new Promise((resolve) => {
      chrome.notifications.create(
        {
          type: "basic",
          iconUrl: "icons/icon128.png",
          title,
          message,
          requireInteraction: false,
        },
        (id) => {
          if (chrome.runtime.lastError) {
            console.warn("FilterJobs: Notification create failed:", chrome.runtime.lastError);
            resolve(null);
            return;
          }
          resolve(id);
        }
      );
    });

    if (!notificationId) {
      badgeFallback(kind, title, message);
      return null;
    }

    // Auto-close after 5 seconds
    setTimeout(() => {
      chrome.notifications.clear(notificationId, () => {});
    }, 5000);

    return notificationId;
  } catch (error) {
    console.error("FilterJobs: Notification error:", error);
    badgeFallback(kind, title, message);
    return null;
  }
}

function extractJobFromPage() {
  // Helper to try multiple selectors
  const pick = (selectors) => {
    for (const selector of selectors) {
      try {
        const element = document.querySelector(selector);
        if (element) {
          const text = element.textContent?.trim();
          if (text && text.length > 0) return text;
        }
      } catch (e) {
        // Continue to next selector if querySelector fails
        continue;
      }
    }
    return "";
  };

  // Helper to pick from multiple elements and combine text
  const pickMultiple = (selectors) => {
    const texts = [];
    for (const selector of selectors) {
      try {
        const elements = document.querySelectorAll(selector);
        elements.forEach((el) => {
          const text = el.textContent?.trim();
          if (text && text.length > 0 && !texts.includes(text)) {
            texts.push(text);
          }
        });
      } catch (e) {
        continue;
      }
    }
    return texts.join(" ").trim();
  };

  // Expand "Show more" buttons to get full description
  const expandShowMore = () => {
    const showMoreButtons = [
      'button[aria-label*="Show more" i]',
      'button[aria-label*="more" i]',
      '.show-more-less-html__button--more',
      '[data-test-id="show-more-button"]',
      'button.show-more-less-html__button',
    ];
    
    for (const selector of showMoreButtons) {
      try {
        const buttons = Array.from(document.querySelectorAll(selector));
        buttons.forEach((btn) => {
          try {
            if (btn.offsetParent !== null && btn.textContent?.toLowerCase().includes('more')) {
              btn.click();
            }
          } catch (e) {
            // Ignore click errors
          }
        });
      } catch (e) {
        continue;
      }
    }
  };

  // Semantic word matching (regex on class) so we survive UI renames
  const classWordsRe = (words) => new RegExp(words.join("|"), "i");
  const findInScope = (scope, classWords, maxTextLen = 350) => {
    if (!scope) return "";
    const re = classWordsRe(classWords);
    const withClass = Array.from(scope.querySelectorAll("[class]")).filter((el) => re.test(el.getAttribute("class") || ""));
    for (const el of withClass) {
      const t = (el.textContent && el.textContent.trim()) || "";
      if (t.length > 0 && t.length <= maxTextLen) return t;
    }
    for (const el of withClass) {
      const t = (el.textContent && el.textContent.trim()) || "";
      if (t.length > 0) return t;
    }
    return "";
  };

  // True only if scope contains an element that looks like the job title (not a section heading)
  const scopeHasJobTitleLike = (scope) => {
    const jobTitleClassRe = classWordsRe(["job-title", "job_title", "topcard__title", "top-card__title", "topcard", "top-card-layout__title"]);
    const genericTitleRe = /title/i;
    return Array.from(scope.querySelectorAll("[class]")).some((el) => {
      const cls = el.getAttribute("class") || "";
      const t = (el.textContent && el.textContent.trim()) || "";
      if (t.length === 0 || t.length > 250) return false;
      if (jobTitleClassRe.test(cls)) return true;
      if (genericTitleRe.test(cls) && t.length < 150) return true;
      return false;
    });
  };

  // 1) Restrict to main content container, then find job-details wrapper via cascade:
  //    - Find nodes that contain "About the job" / "Responsibilities" (only in job details panel, not search list).
  //    - From that anchor, go UP the DOM to the wrapper that also contains the job title.
  const mainContent = document.querySelector("main") || document.querySelector('[role="main"]') || document.body;
  const jobDetailMarkers = /About the job|Responsibilities|Qualifications|Job description|What you'll do|Overview/i;
  const anchorCandidates = [];
  const walkForMarkers = (node) => {
    if (!node) return;
    const text = (node.textContent && node.textContent.trim()) || "";
    if (text.length > 0 && text.length < 600 && jobDetailMarkers.test(text)) {
      anchorCandidates.push(node);
    }
    for (const ch of node.children || []) walkForMarkers(ch);
  };
  walkForMarkers(mainContent);

  // For each anchor, find the nearest ancestor that has a job-title-like element (the job-details wrapper)
  const findWrapperForAnchor = (anchor) => {
    let up = anchor.parentElement;
    while (up && up !== document.body) {
      if (scopeHasJobTitleLike(up)) return up;
      up = up.parentElement;
    }
    return null;
  };

  // Prefer anchors that actually sit inside a job-details wrapper (have a title in the cascade); then by job-details-like container / content size
  const detailsContainerRe = classWordsRe(["job-details", "description", "jobs-description", "show-more-less", "content"]);
  const scoreAnchor = (el) => {
    let up = el.parentElement;
    let score = 0;
    while (up && up !== document.body) {
      const cls = up.getAttribute("class") || "";
      if (detailsContainerRe.test(cls)) score += 2;
      const textLen = (up.textContent && up.textContent.trim().length) || 0;
      if (textLen > 2000) score += 1;
      up = up.parentElement;
    }
    return score;
  };

  const anchorsWithWrapper = anchorCandidates
    .map((a) => ({ anchor: a, wrapper: findWrapperForAnchor(a), score: scoreAnchor(a) }))
    .filter((x) => x.wrapper != null);
  const best = anchorsWithWrapper.length > 0
    ? anchorsWithWrapper.sort((a, b) => b.score - a.score)[0]
    : anchorCandidates.length > 0 ? { anchor: anchorCandidates.sort((a, b) => scoreAnchor(b) - scoreAnchor(a))[0], wrapper: null } : null;

  const descriptionAnchor = best ? best.anchor : null;
  const jobDetailsWrapper = best ? best.wrapper : null;

  // 3) Extract title, company, location from the job-details wrapper only (so we don't read from search list)
  const findInContainers = (classWords, maxTextLen) => {
    if (jobDetailsWrapper) {
      const t = findInScope(jobDetailsWrapper, classWords, maxTextLen);
      if (t) return t;
    }
    const containerRe = classWordsRe(["topcard", "top-card", "job-details", "search-card", "job-card", "base-card"]);
    const containers = Array.from(document.querySelectorAll("[class]")).filter((el) => containerRe.test(el.getAttribute("class") || ""));
    for (const c of containers) {
      const t = findInScope(c, classWords, maxTextLen);
      if (t) return t;
    }
    return findInScope(document, classWords, maxTextLen);
  };

  const isFeedOrChromeTitle = (t) => {
    if (!t || t.length < 2) return true;
    const lower = t.toLowerCase();
    if (/^\(\d+\)\s*linkedin$/i.test(t) || /^linkedin\s*$/i.test(t) || lower === "linkedin") return true;
    if (/^\(\d+\)\s/.test(t)) return true;
    const feedTitles = ["top job picks for you", "jobs you might like", "recommended for you", "start your job search", "job search", "jobs home", "recommended", "saved jobs", "applied jobs", "collections"];
    if (feedTitles.some((f) => lower.includes(f) || lower === f)) return true;
    return false;
  };

  let titleFromSelectors = findInContainers(["job-title", "job_title", "topcard", "title"], 200);
  if (isFeedOrChromeTitle(titleFromSelectors)) titleFromSelectors = "";
  const docTitle = document.title.replace(/\s+\|\s+LinkedIn.*/i, "").trim();
  const ogTitle = (() => {
    const meta = document.querySelector('meta[property="og:title"]');
    return meta && meta.getAttribute("content") ? meta.getAttribute("content").trim() : "";
  })();
  const title = titleFromSelectors || (isFeedOrChromeTitle(docTitle) ? ogTitle : docTitle) || ogTitle || docTitle || "";

  const company = findInContainers(["company-name", "company", "subtitle"], 150);
  const jobLocation = findInContainers(["location", "bullet", "insight", "subline", "primary-description"], 150);

  // 4) Description: from the anchor section (the block that contains "About the job" / "Responsibilities")
  expandShowMore();
  let description = "";
  const minDescLen = 80;
  if (descriptionAnchor) {
    const section = descriptionAnchor.tagName && /^H[1-6]$/.test(descriptionAnchor.tagName) ? descriptionAnchor.parentElement : descriptionAnchor;
    if (section) {
      const t = (section.textContent && section.textContent.trim()) || "";
      if (t.length >= minDescLen) description = t.slice(0, 10000);
    }
    if (!description || description.length < minDescLen) {
      let up = descriptionAnchor.parentElement;
      while (up && up !== document.body) {
        const t = (up.textContent && up.textContent.trim()) || "";
        if (t.length >= minDescLen) {
          description = t.slice(0, 10000);
          break;
        }
        up = up.parentElement;
      }
    }
  }
  if (!description || description.length < minDescLen) {
    const descRe = classWordsRe(["description", "markup", "job-details", "html-content", "content"]);
    const descCandidates = Array.from(document.querySelectorAll("[class]")).filter((el) => descRe.test(el.getAttribute("class") || ""));
    for (const el of descCandidates) {
      const t = (el.textContent && el.textContent.trim()) || "";
      if (t.length >= minDescLen && t.length > (description || "").length) description = t.slice(0, 10000);
    }
  }
  if (!description || description.length < minDescLen) {
    const bodyClone = document.body.cloneNode(true);
    ["nav", "header", "footer", "aside", "button", "[role='banner']", "[role='navigation']", "[role='complementary']"].forEach((sel) => {
      try { bodyClone.querySelectorAll(sel).forEach((el) => el.remove()); } catch (e) {}
    });
    const t = (bodyClone.textContent && bodyClone.textContent.trim()) || "";
    if (t.length >= minDescLen) description = t.slice(0, 10000);
  }

  // Clean up description - remove excessive whitespace
  if (description) {
    description = description
      .replace(/\s+/g, " ")
      .replace(/\n\s*\n/g, "\n")
      .trim();
  }

  // Determine if this is a job page
  const isJobPage = Boolean(
    (description && description.length > 50) ||
    title ||
    company ||
    jobLocation ||
    window.location.href.includes("/jobs/view/") ||
    window.location.href.includes("/jobs/collections/")
  );

  // Prefer a job-specific URL so each capture is unique (avoids duplicate key on url when saving from collection pages)
  const pageUrl = window.location.href;
  let jobUrl = pageUrl;
  try {
    if (pageUrl.includes("/jobs/collections/") && pageUrl.includes("currentJobId=")) {
      const m = pageUrl.match(/currentJobId=(\d+)/);
      if (m && m[1]) jobUrl = `https://www.linkedin.com/jobs/view/${m[1]}`;
    } else if (pageUrl.includes("/jobs/view/")) {
      jobUrl = pageUrl.split("?")[0];
    }
  } catch (_) {}

  const rawText = description || title || "";
  return {
    isJobPage,
    payload: {
      title: title || "Untitled Position",
      company: company || "",
      location: jobLocation || "",
      url: jobUrl,
      raw_text: rawText,
      raw_data: {
        source: "linkedin",
        scraped_at: new Date().toISOString(),
        selectors_used: {
          title: title ? "found" : "not_found",
          company: company ? "found" : "not_found",
          location: jobLocation ? "found" : "not_found",
          description: description ? `found_${description.length}_chars` : "not_found",
        },
      },
    },
    // #region agent log
    debug: {
      titleLen: (title || "").length,
      companyLen: (company || "").length,
      locationLen: (jobLocation || "").length,
      rawTextLength: rawText.length,
      rawTextPreview: rawText.slice(0, 200),
      selectors_used: {
        title: title ? "found" : "not_found",
        company: company ? "found" : "not_found",
        location: jobLocation ? "found" : "not_found",
        description: description ? `found_${(description || "").length}_chars` : "not_found",
      },
    },
    // #endregion
  };
}

async function captureActiveTab() {
  // #region agent log
  const debugLog = (location, message, data, hypothesisId) => {
    fetch("http://127.0.0.1:7242/ingest/738ca3a2-0e63-4f3a-8b85-4e8775500b2b", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ location, message, data: data || {}, timestamp: Date.now(), sessionId: "debug-session", hypothesisId }),
    }).catch(() => {});
  };
  // #endregion
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      const message = "No active tab found.";
      await notify("FilterJobs", message, "error");
      return { ok: false, message, kind: "error" };
    }

    if (!tab.url || !tab.url.includes("linkedin.com")) {
      const message = "Open a LinkedIn job page first.";
      await notify("FilterJobs", message, "info");
      return { ok: false, message, kind: "info" };
    }

    // #region agent log
    debugLog("background.js:captureActiveTab", "capture started", { tabUrl: tab.url }, "H3");
    // #endregion

    let result;
    try {
      const [{ result: scriptResult }] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extractJobFromPage,
      });
      result = scriptResult;
    } catch (scriptError) {
      console.error("FilterJobs: Script execution error:", scriptError);
      // #region agent log
      debugLog("background.js:captureActiveTab", "script execution error", { error: String(scriptError?.message || scriptError) }, "H3");
      // #endregion
      const message = `Error extracting job: ${scriptError.message || scriptError}`;
      await notify("FilterJobs", message, "error");
      return { ok: false, message, kind: "error" };
    }

    // #region agent log
    debugLog("background.js:captureActiveTab", "extract result", {
      isJobPage: result?.isJobPage,
      title: result?.payload?.title,
      company: result?.payload?.company,
      location: result?.payload?.location,
      rawTextLength: result?.payload?.raw_text?.length ?? 0,
      debug: result?.debug || null,
    }, "H1,H2,H3");
    // #endregion

    if (!result || !result.isJobPage) {
      const message = "This doesn't look like a job page.";
      await notify("FilterJobs", message, "info");
      return { ok: false, message, kind: "info" };
    }

    // Log what we captured for debugging
    console.log("FilterJobs: Captured job data:", {
      title: result.payload.title,
      company: result.payload.company,
      location: result.payload.location,
      description_length: result.payload.raw_text?.length || 0,
      url: result.payload.url,
    });

    // #region agent log
    debugLog("background.js:captureActiveTab", "payload before send", {
      title: result.payload.title,
      company: result.payload.company,
      rawTextLength: result.payload.raw_text?.length ?? 0,
    }, "H4");
    // #endregion

    const apiBase = await getApiBase();
    const response = await fetch(`${apiBase}/api/v1/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(result.payload),
    });
    if (!response.ok) {
      const errorText = await response.text();
      console.error("FilterJobs: API error:", response.status, errorText);
      let msg = errorText;
      try {
        const err = JSON.parse(errorText);
        if (err.detail) msg = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
      } catch (_) {}
      throw new Error(msg);
    }
    const job = await response.json();

    // #region agent log
    debugLog("background.js:captureActiveTab", "ingest response", {
      status: response.status,
      jobId: job?.id,
      jobTitle: job?.title,
      jobRawTextLength: job?.raw_text?.length ?? null,
    }, "H4,H5");
    // #endregion

    // Check if this is a duplicate using the is_new flag from backend
    // Fallback: if is_new is undefined (old backend), assume it's new
    const isDuplicate = job.is_new === false;
    
    if (isDuplicate) {
      const duplicateMsg = `Already saved: ${job.title || "Untitled role"}`;
      console.log("FilterJobs: Duplicate job detected:", job.id);
      await notify("FilterJobs", duplicateMsg, "info");
      return { ok: true, message: duplicateMsg, kind: "info" };
    } else {
      const successMsg = `Saved: ${job.title || "Untitled role"}`;
      console.log("FilterJobs: Successfully saved new job:", job.id, "is_new:", job.is_new);
      await notify("FilterJobs", successMsg, "success");
      return { ok: true, message: successMsg, kind: "success" };
    }
  } catch (error) {
    console.error("FilterJobs: Capture error:", error);
    const message = `Failed to save job: ${error.message || error}`;
    await notify("FilterJobs", message, "error");
    return { ok: false, message, kind: "error" };
  }
}

async function beginCull() {
  try {
    const apiBase = await getApiBase();
    const response = await fetch(`${apiBase}/api/v1/cull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      const errorText = await response.text();
      console.error("FilterJobs: Cull API error:", response.status, errorText);

      let errorMsg = "Cull failed";
      if (response.status === 400) {
        errorMsg = "No resume found. Please add your resume in Settings.";
      } else if (response.status === 422) {
        try {
          const err = JSON.parse(errorText);
          const details = err.detail;
          if (Array.isArray(details) && details.length) {
            const first = details[0];
            const loc = (first.loc || []).join(".");
            errorMsg = first.msg ? `Invalid request: ${loc} – ${first.msg}` : "Invalid request. Check Options and resume.";
          } else if (typeof details === "string") {
            errorMsg = details;
          } else {
            errorMsg = "Invalid request. Add resume in Settings and try again.";
          }
        } catch (_) {
          errorMsg = "Invalid request. Add resume in Settings and try again.";
        }
      } else if (response.status === 502) {
        errorMsg = "LLM service error. Check backend logs.";
      } else {
        errorMsg = `Cull failed: ${errorText.substring(0, 100)}`;
      }
      throw new Error(errorMsg);
    }
    const result = await response.json();
    const topCount = result.top_jobs?.length || 0;
    console.log("FilterJobs: Cull complete:", topCount, "jobs");
    const message = `Cull complete. Top ${topCount} jobs.`;
    await notify("FilterJobs", message, "success");
    return { ok: true, message, kind: "success" };
  } catch (error) {
    console.error("FilterJobs: Cull error:", error);
    const message = error.message || `Cull failed: ${error}`;
    await notify("FilterJobs", message, "error");
    return { ok: false, message, kind: "error" };
  }
}

function buildBookmarklet(apiBase) {
  const base = apiBase.replace(/\/$/, "");
  const snippet = `(()=>{const e=t=>{for(const n of t){const t=document.querySelector(n);if(t&&t.textContent){const n=t.textContent.trim();if(n)return n}}return""},t=e(["h1",".jobs-unified-top-card__job-title",".top-card-layout__title"])||document.title.replace(/\\s+\\|\\s+LinkedIn.*/i,"");const n=e([".jobs-unified-top-card__company-name a",".jobs-unified-top-card__company-name",".top-card-layout__company-name","[data-company-name]"]),o=e([".jobs-unified-top-card__bullet",".top-card-layout__first-subline","[data-test-job-location]"]),a=e([".jobs-description__content",".show-more-less-html__markup","[data-test-job-description]"]),r=a||document.body.innerText.slice(0,8000)||t;if(!r){alert("FilterJobs: not a job page.");return}const i={title:t,company:n,location:o,url:window.location.href,raw_text:r,raw_data:{source:"linkedin",scraped_at:new Date().toISOString()}};fetch("${base}/api/v1/ingest",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(i)}).then(s=>s.ok?s.json():Promise.reject(s)).then(s=>alert("FilterJobs: saved "+(s.title||"job"))).catch(()=>alert("FilterJobs: failed to save job"))})();`;
  return `javascript:${snippet}`;
}

async function installBookmarklet() {
  const apiBase = await getApiBase();
  const url = buildBookmarklet(apiBase);
  const title = "FilterJobs";
  const bar = await chrome.bookmarks.getTree();
  const barNode = bar?.[0]?.children?.find((node) => node.id === "1");
  const parentId = barNode ? barNode.id : "1";

  // Remove existing FilterJobs bookmarklets
  const existing = await chrome.bookmarks.search({ title });
  for (const item of existing) {
    if (item.url && item.url.startsWith("javascript:")) {
      await chrome.bookmarks.remove(item.id);
    }
  }

  await chrome.bookmarks.create({ parentId, title, url });
}

chrome.runtime.onInstalled.addListener(() => {
  installBookmarklet().catch(() => {});
  chrome.runtime.openOptionsPage();
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "CAPTURE_JOB") {
    captureActiveTab()
      .then((result) => sendResponse(result || { ok: false, message: "No response from capture.", kind: "error" }))
      .catch((error) =>
        sendResponse({
          ok: false,
          message: error?.message || "Capture failed.",
          kind: "error",
        })
      );
    return true;
  }
  if (message?.type === "BEGIN_CULL") {
    beginCull()
      .then((result) => sendResponse(result || { ok: false, message: "No response from cull.", kind: "error" }))
      .catch((error) =>
        sendResponse({
          ok: false,
          message: error?.message || "Cull failed.",
          kind: "error",
        })
      );
    return true;
  }
  if (message?.type === "REINSTALL_BOOKMARKLET") {
    installBookmarklet().then(() => sendResponse({ ok: true }));
    return true;
  }
  if (message?.type === "OPEN_DASHBOARD") {
    (async () => {
      const { apiBase, dashboardUrl } = await chrome.storage.local.get({
        apiBase: DEFAULT_API,
        dashboardUrl: "",
      });
      const url = (dashboardUrl && dashboardUrl.trim()) ? dashboardUrl.trim().replace(/\/$/, "") : apiBase.replace(/\/$/, "");
      if (!url || !url.startsWith("http")) {
        sendResponse({ ok: false, message: "Set API base or Dashboard URL in Settings." });
        return;
      }
      try {
        await chrome.tabs.create({ url });
        sendResponse({ ok: true });
      } catch (e) {
        sendResponse({ ok: false, message: e?.message || "Could not open tab." });
      }
    })();
    return true;
  }
  return false;
});
