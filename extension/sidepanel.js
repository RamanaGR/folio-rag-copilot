const API = "http://localhost:8000";
const $ = (id) => document.getElementById(id);
let activeTab;
let currentContext = {};
let currentMissing = [];

async function getTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs[0];
}

function renderContext(context) {
  currentContext = context || {};
  $("hostname").textContent = context.hostname || "Current page";
  $("roleTitle").textContent = context.title || "No role title found";
  $("roleCompany").textContent = context.company || "";
  $("roleDescription").textContent = context.description || "No visible description found.";
}

function renderMissing(fields = []) {
  currentMissing = fields;
  $("missingCount").textContent = `${fields.length} field${fields.length === 1 ? "" : "s"}`;
  $("missingEmpty").hidden = fields.length > 0;
  $("readinessTitle").textContent = fields.length ? `${fields.length} field${fields.length === 1 ? " needs" : " need"} your review` : "No human review needed yet";
  $("missingFields").replaceChildren(...fields.map((field) => {
    const item = document.createElement("li");
    const text = document.createElement("span"); text.textContent = field.label;
    const button = document.createElement("button"); button.textContent = "Jump"; button.type = "button";
    button.onclick = async () => {
      try {
        await sendToContent({ type: "JUMP_TO_FIELD", selector: field.selector }, true);
      } catch {
        $("readinessTitle").textContent = "This page cannot be controlled by the extension";
      }
    };
    item.append(text, button); return item;
  }));
}

function setTab(tabName) {
  ["Overview", "Assistant", "Profile"].forEach((name) => {
    const button = $(`tab${name}`);
    const panel = $(`${name.toLowerCase()}Panel`);
    const selected = name === tabName;
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-selected", String(selected));
    panel.hidden = !selected;
    panel.classList.toggle("is-visible", selected);
  });
  persist({ activePanel: tabName });
}

function persist(values) {
  return chrome.storage.local.set(values).catch(() => undefined);
}

function renderEnabled(enabled) {
  $("extensionEnabled").checked = enabled;
  $("enableState").textContent = enabled ? "ON" : "OFF";
  $("enableRow").classList.toggle("is-on", enabled);
  $("readApply").disabled = !enabled;
}

function setProgress(staged) {
  $("progressBar").style.width = staged ? "100%" : currentContext.title ? "50%" : "18%";
  $("workflowLabel").textContent = staged ? "Complete review" : currentContext.title ? "Step 2 of 2" : "Step 1 of 2";
  $("stepRead").classList.toggle("is-current", !staged);
  $("stepStage").classList.toggle("is-current", Boolean(staged));
}

async function send(type) {
  activeTab = await getTab();
  return sendToContent({ type, extensionEnabled: $("extensionEnabled").checked }, true);
}

async function sendToContent(message, injectIfMissing = false) {
  if (!activeTab?.id) throw new Error("No active tab");
  try {
    return await chrome.tabs.sendMessage(activeTab.id, message);
  } catch (error) {
    if (!injectIfMissing) throw error;
    try {
      await chrome.scripting.executeScript({ target: { tabId: activeTab.id }, files: ["content.js"] });
      return await chrome.tabs.sendMessage(activeTab.id, message);
    } catch (injectionError) {
      throw new Error("The active page does not allow Folio content scripts", { cause: injectionError });
    }
  }
}

async function refresh() {
  activeTab = await getTab();
  if (!activeTab?.id) return;
  try {
    const response = await sendToContent({ type: "GET_CONTEXT" });
    renderContext(response.context);
    renderMissing(response.missing);
  } catch { $("roleDescription").textContent = "Open a normal web page to read its visible context."; }
}

$("readApply").onclick = async () => { $("readApply").disabled = true; $("readApply").querySelector("strong").textContent = "Opening application..."; try { const result = await send("READ_AND_APPLY"); renderContext(result.context); setProgress(false); setTab("Assistant"); } catch { $("roleDescription").textContent = "Open a supported job page first."; } finally { $("readApply").disabled = false; $("readApply").querySelector("strong").textContent = "Apply with Folio"; } };
$("stageForm").onclick = async () => { $("stageForm").disabled = true; try { const result = await send("STAGE_FORM"); renderMissing(result.missing); setProgress(true); setTab("Assistant"); } catch { $("readinessTitle").textContent = "Open a supported form page first"; } finally { $("stageForm").disabled = false; } };
$("extensionEnabled").onchange = () => { const enabled = $("extensionEnabled").checked; renderEnabled(enabled); persist({ extensionEnabled: enabled, applyRequested: false }); };
$("autoStage").onchange = () => persist({ autoStage: $("autoStage").checked });

$("askQuestion").onclick = async () => {
  const question = $("questionInput").value.trim();
  if (!question) { $("helperStatus").textContent = "Enter a question first"; $("questionInput").focus(); return; }
  $("askQuestion").disabled = true; $("helperStatus").textContent = "Writing..."; $("answerOutput").value = "";
  try {
    const response = await fetch(`${API}/api/resolve-form`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: [{ label: question, field_type: "textarea", selector_hint: "manual-question" }], context: currentContext }) });
    if (!response.ok) throw new Error("Answer service unavailable");
    const result = await response.json(); const answer = result.answers?.[0]?.answer;
    $("answerOutput").value = answer?.value || "Folio could not ground an answer from the profile. Please answer this one manually.";
    $("helperStatus").textContent = answer?.needs_human ? "Review manually" : "Answer ready";
  } catch { $("helperStatus").textContent = "Backend unavailable"; $("answerOutput").value = "Start the local backend and try again."; }
  finally { $("askQuestion").disabled = false; }
};
$("copyAnswer").onclick = async () => { if (!$("answerOutput").value) return; await navigator.clipboard.writeText($("answerOutput").value); $("helperStatus").textContent = "Copied"; };

["Overview", "Assistant", "Profile"].forEach((name) => { $(`tab${name}`).onclick = () => setTab(name); });

chrome.storage.local.get(["autoStage", "activePanel", "extensionEnabled"]).then((value) => { $("autoStage").checked = value.autoStage !== false; renderEnabled(value.extensionEnabled === true); if (value.activePanel) setTab(value.activePanel); }).catch(() => { renderEnabled(false); });
fetch(`${API}/api/health`).then((response) => response.json()).then((health) => { $("statusDot").style.background = "#18794e"; $("backendStatus").textContent = `Backend ready · ${health.memory_count} learned`; }).catch(() => { $("statusDot").style.background = "#f59e0b"; $("backendStatus").textContent = "Backend offline · local staging unavailable"; });
chrome.tabs.onActivated.addListener(() => { void refresh().catch(() => undefined); });
chrome.tabs.onUpdated.addListener(() => { void refresh().catch(() => undefined); });
void refresh().catch(() => undefined);
