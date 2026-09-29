/**
 * Autonomous Research Outreach Agent — Frontend Controller
 * Handles chat streaming, SSE event rendering, interactive draft cards,
 * SMTP dispatch, model selection, and credentials management.
 */

let appState = {
  config: {},
  models: [],
  selectedModel: "nvidia/nemotron-3.5-lightning:free",
  resumes: [],
  selectedRegions: ["us", "singapore", "hong_kong"],
  messages: [],
  isStreaming: false,
  activeAbortController: null,
};

document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  setupEventListeners();
  await loadConfig();
  await loadFreeModels();
  await loadResumes();
}

/* ---------------- API CALLS ---------------- */
async function loadConfig() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    if (data.success) {
      appState.config = data;
      renderConfigStatus(data);
    }
  } catch (err) {
    console.error("Failed to load config:", err);
  }
}

async function loadFreeModels() {
  try {
    const res = await fetch("/api/free-models");
    const data = await res.json();
    if (data.success && data.models.length > 0) {
      appState.models = data.models;
      renderModelOptions(data.models);
    }
  } catch (err) {
    console.error("Failed to load free models:", err);
  }
}

async function loadResumes() {
  try {
    const res = await fetch("/api/resumes");
    const data = await res.json();
    if (data.success) {
      appState.resumes = data.resumes || [];
      renderResumes(appState.resumes);
    }
  } catch (err) {
    console.error("Failed to load resumes:", err);
  }
}

/* ---------------- RENDERING ---------------- */
function renderConfigStatus(cfg) {
  const orDot = document.querySelector("#status-openrouter .item-dot");
  const orVal = document.getElementById("val-openrouter");
  if (cfg.has_openrouter) {
    orDot.className = "item-dot ok";
    orVal.textContent = cfg.masked_openrouter || "Connected";
  } else {
    orDot.className = "item-dot warn";
    orVal.textContent = "Missing in .env";
  }

  const senderDot = document.querySelector("#status-sender .item-dot");
  const senderVal = document.getElementById("val-sender");
  if (cfg.sender_email) {
    senderDot.className = "item-dot ok";
    senderVal.textContent = cfg.sender_email;
  } else {
    senderDot.className = "item-dot warn";
    senderVal.textContent = "Not set";
  }

  const passDot = document.querySelector("#status-password .item-dot");
  const passVal = document.getElementById("val-password");
  if (cfg.has_app_password) {
    passDot.className = "item-dot ok";
    passVal.textContent = "Configured";
  } else {
    passDot.className = "item-dot warn";
    passVal.textContent = "Not set";
  }

  const ccDot = document.querySelector("#status-cc .item-dot");
  const ccVal = document.getElementById("val-cc");
  if (cfg.cc_email) {
    ccDot.className = "item-dot ok";
    ccVal.textContent = cfg.cc_email;
  } else {
    ccDot.className = "item-dot info";
    ccVal.textContent = "Optional (None)";
  }

  // Populate editor fields
  document.getElementById("input-cc").value = cfg.cc_email || "";
  document.getElementById("input-student-name").value = cfg.student_name || "";
  document.getElementById("input-friend-name").value = cfg.friend_name || "";
}

function renderModelOptions(models) {
  const sel = document.getElementById("model-select");
  sel.innerHTML = "";

  models.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m.id;
    opt.textContent = `${m.has_tools ? "⚡ " : ""}${m.name} ${m.has_tools ? "(Tools ✓)" : ""}`;
    sel.appendChild(opt);
  });

  // Default to first model with tools if available
  const toolModel = models.find(m => m.has_tools);
  if (toolModel) {
    sel.value = toolModel.id;
    appState.selectedModel = toolModel.id;
    updateModelTag(toolModel.name);
  }
}

function updateModelTag(name) {
  const tag = document.getElementById("current-model-tag");
  const clean = name.replace(":free", "").replace("(free)", "").trim();
  tag.textContent = clean.length > 22 ? clean.slice(0, 20) + "..." : clean;
}

function renderResumes(resumes) {
  const container = document.getElementById("resumes-list");
  container.innerHTML = "";

  if (resumes.length === 0) {
    container.innerHTML = `<div class="resumes-hint">No resumes uploaded yet. Click + Upload above.</div>`;
    return;
  }

  resumes.forEach(r => {
    const chip = document.createElement("div");
    chip.className = "resume-chip";
    chip.innerHTML = `
      <span class="resume-icon">📄</span>
      <span class="resume-name" title="${r}">${r}</span>
    `;
    container.appendChild(chip);
  });
}

/* ---------------- EVENT LISTENERS ---------------- */
function setupEventListeners() {
  const chatInput = document.getElementById("chat-input");
  const sendBtn = document.getElementById("send-btn");
  const stopBtn = document.getElementById("stop-btn");
  const modelSelect = document.getElementById("model-select");
  const toggleConfigBtn = document.getElementById("toggle-config-btn");
  const saveConfigBtn = document.getElementById("save-config-btn");
  const clearChatBtn = document.getElementById("clear-chat-btn");
  const resumeUploadInput = document.getElementById("resume-upload-input");
  const chatFileInput = document.getElementById("chat-file-input");
  const inputAttachBtn = document.getElementById("input-attach-btn");

  // Input auto-height & enter key
  chatInput.addEventListener("input", () => {
    chatInput.style.height = "auto";
    chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
  });

  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  });

  sendBtn.addEventListener("click", handleSendMessage);
  stopBtn.addEventListener("click", stopStreaming);

  modelSelect.addEventListener("change", (e) => {
    appState.selectedModel = e.target.value;
    const selected = appState.models.find(m => m.id === e.target.value);
    if (selected) updateModelTag(selected.name);
    showToast(`Switched to ${selected ? selected.name : e.target.value}`, "info");
  });

  toggleConfigBtn.addEventListener("click", () => {
    const editor = document.getElementById("config-editor");
    editor.classList.toggle("hidden");
    toggleConfigBtn.textContent = editor.classList.contains("hidden") ? "Edit" : "Close";
  });

  saveConfigBtn.addEventListener("click", async () => {
    const cc = document.getElementById("input-cc").value.trim();
    const student = document.getElementById("input-student-name").value.trim();
    const friend = document.getElementById("input-friend-name").value.trim();

    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cc_email: cc, student_name: student, friend_name: friend }),
      });
      const data = await res.json();
      if (data.success) {
        showToast("Settings saved successfully!", "success");
        await loadConfig();
        document.getElementById("config-editor").classList.add("hidden");
        toggleConfigBtn.textContent = "Edit";
      }
    } catch (err) {
      showToast("Failed to save settings: " + err.message, "error");
    }
  });

  clearChatBtn.addEventListener("click", () => {
    if (confirm("Clear current conversation history?")) {
      appState.messages = [];
      const messagesContainer = document.getElementById("chat-messages");
      messagesContainer.innerHTML = "";
      document.getElementById("welcome-banner")?.classList.remove("hidden");
      showToast("Conversation cleared", "info");
    }
  });

  // Region pills toggle
  document.querySelectorAll(".region-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      pill.classList.toggle("active");
      const region = pill.getAttribute("data-region");
      if (pill.classList.contains("active")) {
        if (!appState.selectedRegions.includes(region)) {
          appState.selectedRegions.push(region);
        }
      } else {
        appState.selectedRegions = appState.selectedRegions.filter(r => r !== region);
      }
    });
  });

  // Prompt suggestions click
  document.querySelectorAll(".suggestion-card").forEach(card => {
    card.addEventListener("click", () => {
      const prompt = card.getAttribute("data-prompt");
      chatInput.value = prompt;
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + "px";
      handleSendMessage();
    });
  });

  // Resume file uploads
  inputAttachBtn.addEventListener("click", () => chatFileInput.click());
  resumeUploadInput.addEventListener("change", (e) => handleFileUpload(e.target.files[0]));
  chatFileInput.addEventListener("change", (e) => handleFileUpload(e.target.files[0]));
}

async function handleFileUpload(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);

  showToast(`Uploading ${file.name}...`, "info");
  try {
    const res = await fetch("/api/upload-resume", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Attached ${data.filename}!`, "success");
      await loadResumes();
    } else {
      showToast(`Upload failed: ${data.error}`, "error");
    }
  } catch (err) {
    showToast("Upload failed: " + err.message, "error");
  }
}

/* ---------------- CHAT STREAMING ---------------- */
async function handleSendMessage() {
  const chatInput = document.getElementById("chat-input");
  const text = chatInput.value.trim();
  if (!text || appState.isStreaming) return;

  // Hide welcome banner
  const welcome = document.getElementById("welcome-banner");
  if (welcome) welcome.classList.add("hidden");

  // Append user message
  appendUserMessage(text);
  chatInput.value = "";
  chatInput.style.height = "auto";

  appState.messages.push({ role: "user", content: text });

  // Create assistant message container
  const assistantRow = createAssistantMessageContainer();
  const messageBody = assistantRow.querySelector(".message-body");
  const textBubble = assistantRow.querySelector(".message-bubble");

  setStreamingState(true);

  appState.activeAbortController = new AbortController();

  try {
    const regions = appState.selectedRegions;
    const augmentedMessages = [...appState.messages];

    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: augmentedMessages,
        model: appState.selectedModel,
        regions: regions,
      }),
      signal: appState.activeAbortController.signal,
    });

    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.error || `HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let accumulatedText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop(); // keep remainder

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const jsonStr = line.replace("data: ", "").trim();
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr);
          handleAgentEvent(event, messageBody, textBubble, (chunk) => {
            accumulatedText += chunk;
          });
        } catch (e) {
          console.warn("Error parsing event:", e, jsonStr);
        }
      }
    }

    if (accumulatedText) {
      appState.messages.push({ role: "assistant", content: accumulatedText });
    }

  } catch (err) {
    if (err.name === "AbortError") {
      showToast("Generation stopped.", "info");
    } else {
      showToast("Agent error: " + err.message, "error");
      const errDiv = document.createElement("div");
      errDiv.className = "tool-step-badge";
      errDiv.style.borderColor = "var(--accent-rose)";
      errDiv.style.color = "#fecdd3";
      errDiv.innerHTML = `⚠️ ${err.message}`;
      messageBody.appendChild(errDiv);
    }
  } finally {
    setStreamingState(false);
    scrollToBottom();
  }
}

function handleAgentEvent(event, container, textBubble, textAccumulator) {
  if (event.type === "message") {
    textAccumulator(event.content);
    textBubble.innerHTML = formatMarkdown(textBubble.dataset.raw = (textBubble.dataset.raw || "") + event.content);
    scrollToBottom();
  } else if (event.type === "tool_start") {
    const badge = document.createElement("div");
    badge.className = "tool-step-badge";
    badge.id = `tool-${event.name}`;
    let label = `Executing ${event.name}...`;
    if (event.name === "search_professors") {
      label = `🔍 Searching faculty in ${event.args?.regions?.join(", ").toUpperCase() || "US/Asia"} for "${event.args?.query || "topics"}"...`;
    } else if (event.name === "scrape_professor_email") {
      label = `📧 Finding contact email for Prof. ${event.args?.professor_name || "candidate"}...`;
    } else if (event.name === "create_email_draft") {
      label = `📝 Generating personalized cold email draft for ${event.args?.professor_name || "professor"}...`;
    }
    badge.innerHTML = `<span class="spinner-icon"></span> ${label}`;
    container.insertBefore(badge, textBubble.nextSibling);
    scrollToBottom();
  } else if (event.type === "tool_result") {
    const badge = container.querySelector(`#tool-${event.name}`);
    if (badge) {
      badge.innerHTML = `✓ ${badge.textContent.replace("...", "")} (Complete)`;
      badge.style.color = "var(--accent-emerald)";
      badge.style.borderColor = "rgba(16, 185, 129, 0.3)";
    }
  } else if (event.type === "draft") {
    // Render the Interactive Email Draft Card!
    const draftCard = createDraftCard(event.draft);
    container.appendChild(draftCard);
    scrollToBottom();
  } else if (event.type === "error") {
    showToast(event.content, "error");
  }
}

/* ---------------- INTERACTIVE DRAFT CARD BUILDER ---------------- */
function createDraftCard(draft) {
  const card = document.createElement("div");
  card.className = "draft-card";

  const profName = draft.professor_name || "Faculty Member";
  const email = draft.professor_email || "";
  const affiliation = draft.affiliation || "University";
  const hIndex = draft.h_index || 25;
  const subject = draft.subject || "Research Collaboration Inquiry";
  const body = draft.body || "";
  const cc = draft.cc_email || appState.config.cc_email || "";
  const attachments = draft.attachments || appState.resumes;
  const papers = draft.key_papers || [];

  const wordCount = body.trim().split(/\s+/).filter(Boolean).length;

  card.innerHTML = `
    <div class="draft-header">
      <div class="draft-title-group">
        <h4>🎓 ${profName}</h4>
        <div class="draft-meta-chips">
          <span class="meta-chip affiliation">🏛️ ${affiliation}</span>
          <span class="meta-chip hindex">📊 H-Index: ~${hIndex}</span>
        </div>
      </div>
      <span class="draft-status-pill">Ready to Review</span>
    </div>

    <div class="draft-fields">
      <div class="field-row">
        <span class="field-label">To (Email):</span>
        <div class="field-input-wrapper">
          <input type="email" class="field-input input-to" value="${escapeHtml(email)}" placeholder="professor@university.edu">
          ${email ? '<span class="verified-badge">Auto-filled</span>' : ''}
        </div>
      </div>

      <div class="field-row">
        <span class="field-label">CC (Friend):</span>
        <div class="field-input-wrapper">
          <input type="email" class="field-input input-cc" value="${escapeHtml(cc)}" placeholder="friend@gmail.com">
        </div>
      </div>

      <div class="field-row">
        <span class="field-label">Subject:</span>
        <div class="field-input-wrapper">
          <input type="text" class="field-input input-subject" value="${escapeHtml(subject)}">
        </div>
      </div>

      <div class="field-row">
        <span class="field-label">Attachments:</span>
        <div class="attachments-wrapper">
          ${attachments.map(att => `
            <span class="attachment-pill" data-att="${escapeHtml(att)}">
              📄 ${escapeHtml(att)}
              <button class="remove-att-btn" title="Remove attachment">&times;</button>
            </span>
          `).join("")}
        </div>
      </div>

      <div class="body-field">
        <div class="body-header">
          <span class="field-label">Personalized Email Body:</span>
          <span class="word-count">${wordCount} words (Ideal for cold outreach)</span>
        </div>
        <textarea class="draft-textarea">${escapeHtml(body)}</textarea>
      </div>

      ${papers.length > 0 ? `
        <div class="papers-referenced">
          <strong>📚 Cited Research Papers:</strong>
          <ul>
            ${papers.map(p => `<li>${escapeHtml(p)}</li>`).join("")}
          </ul>
        </div>
      ` : ""}
    </div>

    <div class="draft-actions">
      <button class="btn btn-primary btn-send-draft">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        Send Cold Email
      </button>
      <button class="btn btn-secondary btn-copy-draft">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
        Copy Email
      </button>
      <button class="btn btn-secondary btn-revise-draft">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
        Revise with Agent
      </button>
    </div>
  `;

  // Dynamic word count listener
  const textarea = card.querySelector(".draft-textarea");
  const countSpan = card.querySelector(".word-count");
  textarea.addEventListener("input", () => {
    const count = textarea.value.trim().split(/\s+/).filter(Boolean).length;
    countSpan.textContent = `${count} words`;
  });

  // Remove attachment pill
  card.querySelectorAll(".remove-att-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.target.closest(".attachment-pill").remove();
    });
  });

  // Copy Email button
  const copyBtn = card.querySelector(".btn-copy-draft");
  copyBtn.addEventListener("click", () => {
    const subj = card.querySelector(".input-subject").value;
    const txt = card.querySelector(".draft-textarea").value;
    navigator.clipboard.writeText(`Subject: ${subj}\n\n${txt}`);
    showToast("Email text copied to clipboard!", "success");
  });

  // Revise with Agent button
  const reviseBtn = card.querySelector(".btn-revise-draft");
  reviseBtn.addEventListener("click", () => {
    const chatInput = document.getElementById("chat-input");
    chatInput.value = `Please revise the email draft for Prof. ${profName} (${affiliation}) to make it even more compelling and focused on their newest work.`;
    handleSendMessage();
  });

  // Send Email button
  const sendBtn = card.querySelector(".btn-send-draft");
  sendBtn.addEventListener("click", () => {
    const toEmail = card.querySelector(".input-to").value.trim();
    const ccEmail = card.querySelector(".input-cc").value.trim();
    const subj = card.querySelector(".input-subject").value.trim();
    const mailBody = card.querySelector(".draft-textarea").value.trim();
    const atts = Array.from(card.querySelectorAll(".attachment-pill")).map(p => p.getAttribute("data-att"));

    if (!toEmail) {
      showToast("Please enter the professor's email address.", "error");
      card.querySelector(".input-to").focus();
      return;
    }

    // Open confirmation modal
    openConfirmModal({
      professor: profName,
      to: toEmail,
      cc: ccEmail,
      subject: subj,
      body: mailBody,
      attachments: atts,
      onConfirm: async () => {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `<span class="spinner-icon"></span> Sending...`;

        try {
          const res = await fetch("/api/draft/send", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              to_email: toEmail,
              cc_email: ccEmail,
              subject: subj,
              body: mailBody,
              attachments: atts,
            }),
          });
          const result = await res.json();
          if (result.success) {
            showToast(`Cold email successfully sent to ${toEmail}!`, "success");
            const pill = card.querySelector(".draft-status-pill");
            pill.className = "draft-status-pill sent";
            pill.textContent = "Sent ✓";
            sendBtn.className = "btn btn-success";
            sendBtn.innerHTML = `✓ Sent Successfully`;
          } else {
            showToast(`Failed to send: ${result.error}`, "error");
            sendBtn.disabled = false;
            sendBtn.innerHTML = `Send Cold Email`;
          }
        } catch (e) {
          showToast(`Error: ${e.message}`, "error");
          sendBtn.disabled = false;
          sendBtn.innerHTML = `Send Cold Email`;
        }
      }
    });
  });

  return card;
}

/* ---------------- CONFIRMATION MODAL ---------------- */
function openConfirmModal({ professor, to, cc, subject, body, attachments, onConfirm }) {
  const modal = document.getElementById("confirm-modal");
  const title = document.getElementById("modal-title");
  const details = document.getElementById("modal-details");
  const confirmBtn = document.getElementById("modal-confirm-btn");
  const cancelBtn = document.getElementById("modal-cancel-btn");

  title.textContent = `Send Email to ${professor}?`;
  details.innerHTML = `
    <div><strong>Recipient (To):</strong> ${escapeHtml(to)}</div>
    ${cc ? `<div><strong>CC'd Partner:</strong> ${escapeHtml(cc)}</div>` : ''}
    <div><strong>Subject:</strong> ${escapeHtml(subject)}</div>
    <div><strong>Attachments:</strong> ${attachments.length > 0 ? attachments.join(", ") : "None"}</div>
  `;

  modal.classList.remove("hidden");

  const cleanup = () => {
    modal.classList.add("hidden");
    confirmBtn.onclick = null;
    cancelBtn.onclick = null;
  };

  cancelBtn.onclick = cleanup;
  confirmBtn.onclick = () => {
    cleanup();
    onConfirm();
  };
}

/* ---------------- UI HELPERS ---------------- */
function appendUserMessage(text) {
  const messagesContainer = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "message-row user-row";
  row.innerHTML = `
    <div class="message-avatar">👤</div>
    <div class="message-body">
      <div class="message-bubble">${escapeHtml(text)}</div>
    </div>
  `;
  messagesContainer.appendChild(row);
  scrollToBottom();
}

function createAssistantMessageContainer() {
  const messagesContainer = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "message-row assistant-row";
  row.innerHTML = `
    <div class="message-avatar">✨</div>
    <div class="message-body">
      <div class="message-bubble"></div>
    </div>
  `;
  messagesContainer.appendChild(row);
  scrollToBottom();
  return row;
}

function setStreamingState(isStreaming) {
  appState.isStreaming = isStreaming;
  document.getElementById("send-btn").classList.toggle("hidden", isStreaming);
  document.getElementById("stop-btn").classList.toggle("hidden", !isStreaming);
}

function stopStreaming() {
  if (appState.activeAbortController) {
    appState.activeAbortController.abort();
    appState.activeAbortController = null;
  }
}

function scrollToBottom() {
  const container = document.getElementById("chat-messages");
  container.scrollTop = container.scrollHeight;
}

function formatMarkdown(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Italic
  html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");
  // Lists
  html = html.replace(/^[\*\-] (.*)$/gm, "<li>$1</li>");
  // Headers
  html = html.replace(/^### (.*)$/gm, "<h4 style='margin: 8px 0 4px;'>$1</h4>");
  html = html.replace(/^## (.*)$/gm, "<h3 style='margin: 10px 0 6px;'>$1</h3>");
  // Paragraphs
  html = html.replace(/\n\n/g, "<br><br>");
  return html;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
