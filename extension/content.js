(() => {
  const API = "http://localhost:8000";
  const state = { context: null, missing: [], processed: false, applying: false, learned: new WeakMap() };
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const event = (type) => new Event(type, { bubbles: true, cancelable: true });
  const visible = (element) => { const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0; };
  const labelFor = (element) => { const explicit = element.id ? document.querySelector(`label[for="${CSS.escape(element.id)}"]`) : null; const labelled = element.getAttribute("aria-labelledby") ? document.getElementById(element.getAttribute("aria-labelledby")) : null; const parent = element.closest("label, fieldset"); const nearby = element.previousElementSibling || element.parentElement?.previousElementSibling; const text = explicit?.innerText || labelled?.innerText || element.closest("label")?.innerText || parent?.querySelector("legend")?.innerText || nearby?.innerText || element.getAttribute("aria-label") || element.placeholder || element.name || "Unknown field"; return text.replace(/\s+/g, " ").trim(); };
  const selectorFor = (element) => element.id ? `#${CSS.escape(element.id)}` : `${element.tagName.toLowerCase()}[name="${CSS.escape(element.name || "")}"]`;
  const nativeSetter = (element, value) => { const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, value); };
  const outline = (element, color) => { element.style.outline = `2px solid ${color}`; element.style.outlineOffset = "2px"; };
  const context = () => { const heading = document.querySelector("h1, [role=heading]")?.innerText?.trim() || document.title; const company = document.querySelector("[class*=company i], [class*=employer i]")?.innerText?.trim() || ""; const root = document.querySelector("main, article, .job-description") || document.body; return { title: heading, company, description: (root.innerText || "").slice(0, 8000), url: location.href, hostname: location.hostname }; };
  const controls = () => [...document.querySelectorAll("input, textarea, select")].filter((element) => visible(element) && !["submit", "button", "hidden", "file"].includes(element.type));
  const applyLink = () => [...document.querySelectorAll("a, button")].find((element) => /apply|apply now|i'm interested|jetzt bewerben/i.test(element.innerText || element.getAttribute("aria-label") || ""));
  const groupKey = (element) => `${element.type}:${element.name || element.id || selectorFor(element)}`;
  const currentValue = (elements) => elements.map((element) => element.type === "checkbox" || element.type === "radio" ? (element.checked ? labelFor(element) : "") : element.value).filter(Boolean).join(" | ");
  const hasValue = (elements) => elements.some((element) => element.type === "checkbox" || element.type === "radio" ? element.checked : element.value.trim() !== "");

  function questions() {
    const result = []; const seen = new Set();
    for (const element of controls()) {
      if (element.type === "radio" || element.type === "checkbox") {
        const key = groupKey(element); if (seen.has(key)) continue; seen.add(key);
        const group = controls().filter((candidate) => candidate.type === element.type && groupKey(candidate) === key);
        result.push({ key, elements: group, label: group.length > 1 ? `${labelFor(element)} options` : labelFor(element), field_type: group.length > 1 ? `${element.type}_group` : element.type, options: group.map(labelFor), selector_hint: selectorFor(element), required: group.some((candidate) => candidate.required) });
      } else result.push({ key: selectorFor(element), elements: [element], label: labelFor(element), field_type: element.tagName === "SELECT" ? "select" : element.type || element.tagName.toLowerCase(), options: element.tagName === "SELECT" ? [...element.options].map((option) => option.textContent.trim()).filter(Boolean) : [], selector_hint: selectorFor(element), required: element.required });
    }
    return result;
  }

  async function learn(question, suggested) {
    const value = currentValue(question.elements); if (!value || value === suggested || state.learned.get(question.elements[0]) === value) return;
    state.learned.set(question.elements[0], value);
    try { await fetch(`${API}/api/learn`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_label: question.label, field_type: question.field_type, options: question.options, user_value: value, domain: location.hostname, selector_hint: question.selector_hint }) }); } catch { /* learning must not interrupt the user */ }
  }

  function watch(question, suggested) { for (const element of question.elements) { const handler = () => { void learn(question, suggested); }; element.addEventListener("change", handler); element.addEventListener("blur", handler); } }
  async function typeValue(element, value) {
    if (hasValue([element])) return;
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    element.focus();
    element.dispatchEvent(event("focus"));
    if (element.type === "date") {
      const dateValue = value.match(/^\d{4}-\d{2}-\d{2}$/)?.[0];
      if (!dateValue) return;
      nativeSetter(element, dateValue);
      element.dispatchEvent(event("input"));
      element.dispatchEvent(event("change"));
    } else if (["number", "tel", "email", "url"].includes(element.type)) {
      nativeSetter(element, value);
      element.dispatchEvent(event("input"));
      element.dispatchEvent(event("change"));
    } else {
      nativeSetter(element, "");
      for (const character of value) {
        nativeSetter(element, `${element.value}${character}`);
        element.dispatchEvent(event("input"));
        await sleep(25 + Math.random() * 30);
      }
      element.dispatchEvent(event("change"));
    }
    element.blur();
    await sleep(600 + Math.random() * 800);
  }
  function choose(question, answer) { const wanted = answer.split("|").map((value) => value.trim().toLowerCase()).filter(Boolean); for (const element of question.elements) { const label = labelFor(element).toLowerCase(); if ((element.type === "radio" || element.type === "checkbox") && wanted.some((value) => value === label || value.includes(label) || label.includes(value)) && !element.checked) element.click(); } const select = question.elements[0]; if (select?.tagName === "SELECT" && !hasValue(question.elements)) { const option = [...select.options].find((candidate) => wanted.some((value) => { const label = candidate.textContent.trim().toLowerCase(); return value === label || value.includes(label) || label.includes(value); })); if (option) { select.value = option.value; select.dispatchEvent(event("input")); select.dispatchEvent(event("change")); } } }
  async function uploadResume() { const input = [...document.querySelectorAll('input[type="file"]')].find((element) => /resume|cv|curriculum/i.test(labelFor(element))) || document.querySelector('input[type="file"]'); if (!input) return; try { const response = await fetch(`${API}/api/files/resume`); if (!response.ok) return; const transfer = new DataTransfer(); transfer.items.add(new File([await response.blob()], "Ramana_Gangarao_CV.pdf", { type: "application/pdf" })); input.files = transfer.files; input.dispatchEvent(event("input")); input.dispatchEvent(event("change")); await sleep(location.hostname === "jobs.lever.co" ? 2500 : 800); } catch { outline(input, "#f59e0b"); } }

  async function stage() {
    if (state.processed || state.applying) return { missing: state.missing, alreadyProcessed: true };
    state.applying = true; state.missing = []; const formQuestions = questions(); let answers = [];
    try { const response = await fetch(`${API}/api/resolve-form`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fields: formQuestions.map(({ elements, ...question }) => question), context: state.context || context() }) }); answers = (await response.json()).answers || []; } catch { answers = []; }
    const lever = location.hostname === "jobs.lever.co"; if (lever) await uploadResume();
    for (const question of formQuestions) { const answer = answers.find((item) => item.label === question.label)?.answer; const existing = hasValue(question.elements); if (!existing && answer?.value && !answer.needs_human) { if (["radio", "checkbox", "radio_group", "checkbox_group", "select"].includes(question.field_type)) choose(question, answer.value); else await typeValue(question.elements[0], answer.value); outline(question.elements[0], "#16a34a"); } watch(question, existing ? "" : answer?.value || ""); if (!existing && (!answer?.value || answer.needs_human)) state.missing.push({ label: question.label, selector: question.selector_hint }); }
    if (!lever) await uploadResume(); state.processed = true; state.applying = false; return { missing: state.missing, alreadyProcessed: false };
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => { (async () => { if (message.type === "GET_CONTEXT") sendResponse({ context: state.context || context(), missing: state.missing, processed: state.processed }); if (message.type === "READ_AND_APPLY") { if (message.extensionEnabled !== true) { sendResponse({ blocked: true }); return; } state.context = context(); await chrome.storage.local.set({ [`jd:${location.hostname}`]: state.context, extensionEnabled: true, applyRequested: true }); const hasForm = Boolean(document.querySelector("input, textarea, select")); const link = applyLink(); if (link && !hasForm) { link.click(); sendResponse({ context: state.context, missing: state.missing }); } else sendResponse(await stage()); } if (message.type === "STAGE_FORM" && message.extensionEnabled === true) sendResponse(await stage()); if (message.type === "JUMP_TO_FIELD") document.querySelector(message.selector)?.scrollIntoView({ behavior: "smooth", block: "center" }); if (message.type === "PAGE_READY") { const stored = await chrome.storage.local.get([`jd:${location.hostname}`, "extensionEnabled", "applyRequested"]); if (stored[`jd:${location.hostname}`]) state.context = stored[`jd:${location.hostname}`]; if (stored.extensionEnabled === true && stored.applyRequested === true) { await chrome.storage.local.set({ applyRequested: false }); sendResponse(await stage()); } } })(); return true; });
})();
