const views = {
  loading: document.getElementById("loadingView"),
  init: document.getElementById("initView"),
  unlock: document.getElementById("unlockView"),
  home: document.getElementById("homeView"),
};

const statusBadge = document.getElementById("statusBadge");
const lockButton = document.getElementById("lockButton");
const settingsButton = document.getElementById("settingsButton");
const fullPageSettingsButton = document.getElementById("fullPageSettingsButton");
const trashButton = document.getElementById("trashButton");
const toast = document.getElementById("toast");
const tokenKey = "lifegraph_session_token";
const frontendBuildVersion = "0.0.6";
console.info(`[LifeGraph] frontend build ${frontendBuildVersion}`);
const buildBadge = document.querySelector(".build-badge");
if (buildBadge) buildBadge.textContent = `v${frontendBuildVersion} · JS`;

let currentProfile = null;
let currentProgress = null;
let contentStatus = {};
let monthContentStatus = {};
let yearContentStatus = {};
let contentStatusRevision = 0;
let lifeGridSignature = "";
let resizeTimer = null;
let selectedDate = null;
let selectedScope = null;
let selectedPeriodKey = null;
let drawerRequestSequence = 0;
let activeLifeMapView = "life";
let navigatorYear = null;
let navigatorMonth = null;
let navigatorDate = null;
let openContentMenu = null;
let openContentMenuTrigger = null;
let fullPageLifeOpen = false;
let fullPageGridSignature = "";
let fullPageReturnFocus = null;

const lifeMapViewTitle = document.getElementById("lifeMapViewTitle");
const lifeMapViewSubtitle = document.getElementById("lifeMapViewSubtitle");
const lifeMapTabs = Array.from(document.querySelectorAll("[data-life-view]"));
const lifeMapViewNodes = {
  life: document.getElementById("lifeMapLifeView"),
  year: document.getElementById("lifeMapYearView"),
  month: document.getElementById("lifeMapMonthView"),
};
const hierarchyPointerTooltip = document.getElementById("hierarchyPointerTooltip");
const hierarchyPointerTitle = document.getElementById("hierarchyPointerTitle");
const hierarchyPointerMeta = document.getElementById("hierarchyPointerMeta");
const openFullPageViewButton = document.getElementById("openFullPageView");
const fullPageLifeView = document.getElementById("fullPageLifeView");
const closeFullPageViewButton = document.getElementById("closeFullPageView");
const fullPageLocateTodayButton = document.getElementById("fullPageLocateToday");
const fullPageLifeSummary = document.getElementById("fullPageLifeSummary");
const fullPageLifeCanvasWrap = document.getElementById("fullPageLifeCanvasWrap");
const fullPageLifeCanvas = document.getElementById("fullPageLifeCanvas");
const fullPageDateTooltip = document.getElementById("fullPageDateTooltip");
const fullPageDateTooltipTitle = document.getElementById("fullPageDateTooltipTitle");
const fullPageDateTooltipMeta = document.getElementById("fullPageDateTooltipMeta");
const quickMemoryHomeButton = document.getElementById("quickMemoryHomeButton");
const quickMemoryFullPageButton = document.getElementById("quickMemoryFullPageButton");
const memorySearchHomeButton = document.getElementById("memorySearchHomeButton");
const memorySearchFullPageButton = document.getElementById("memorySearchFullPageButton");
const memorySearchModal = document.getElementById("memorySearchModal");
const memorySearchForm = document.getElementById("memorySearchForm");
const memorySearchQuery = document.getElementById("memorySearchQuery");
const memorySearchDateFrom = document.getElementById("memorySearchDateFrom");
const memorySearchDateTo = document.getElementById("memorySearchDateTo");
const memorySearchTagOptions = document.getElementById("memorySearchTagOptions");
const memorySearchResults = document.getElementById("memorySearchResults");
const memorySearchSummary = document.getElementById("memorySearchSummary");
const memorySearchLimitHint = document.getElementById("memorySearchLimitHint");
const closeMemorySearchButton = document.getElementById("closeMemorySearch");
const resetMemorySearchButton = document.getElementById("resetMemorySearch");
const memoryMapFilterHomeButton = document.getElementById("memoryMapFilterHomeButton");
const memoryMapFilterFullPageButton = document.getElementById("memoryMapFilterFullPageButton");
const memoryMapFilterModal = document.getElementById("memoryMapFilterModal");
const memoryMapFilterForm = document.getElementById("memoryMapFilterForm");
const memoryMapFilterTagOptions = document.getElementById("memoryMapFilterTagOptions");
const memoryMapFilterSummary = document.getElementById("memoryMapFilterSummary");
const closeMemoryMapFilterButton = document.getElementById("closeMemoryMapFilter");
const clearMemoryMapFilterButton = document.getElementById("clearMemoryMapFilter");
let memorySearchReturnFocus = null;
let memorySearchRequestSequence = 0;
const selectedMemorySearchTagIds = new Set();
let memoryMapFilterReturnFocus = null;
let memoryMapFilterRequestSequence = 0;
let memoryMapFilterRevision = 0;
const selectedMemoryMapTagIds = new Set();
const draftMemoryMapTagIds = new Set();
let memoryMapTagMatches = { dates: new Set(), months: new Set(), years: new Set(), memoryCount: 0 };
const quickMemoryModal = document.getElementById("quickMemoryModal");
const quickMemoryForm = document.getElementById("quickMemoryForm");
const quickMemoryDateText = document.getElementById("quickMemoryDateText");
const closeQuickMemoryButton = document.getElementById("closeQuickMemory");
const cancelQuickMemoryButton = document.getElementById("cancelQuickMemory");
let quickMemoryReturnFocus = null;
let quickMemorySnapshot = "";
let availableMemoryTags = [];
let memoryTagsLoadPromise = null;
const selectedMemoryTagIds = {
  quick: new Set(),
  drawer: new Set(),
};

updateMemoryMapFilterEntryButtons();

function token() {
  return sessionStorage.getItem(tokenKey);
}

function setToken(value) {
  value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey);
}

function showView(name) {
  Object.entries(views).forEach(([key, node]) => node.classList.toggle("hidden", key !== name));
  lockButton.classList.toggle("hidden", name !== "home");
  settingsButton.classList.toggle("hidden", name !== "home");
  trashButton.classList.toggle("hidden", name !== "home");
  if (name !== "home") {
    closeDateDrawerNow();
    closeFullPageLifeViewNow();
    closeSettingsModalNow();
    closeMemoryMapFilterModalNow({ restoreFocus: false });
  }
}

function showToast(message, tone = "info") {
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    toast.classList.add("hidden");
    delete toast.dataset.tone;
  }, tone === "error" ? 4800 : 3200);
}

function friendlyErrorMessage(error) {
  const messages = {
    REVISION_CONFLICT: "内容已经发生变化，请重新打开后再操作。",
    CONTENT_NOT_FOUND: "内容不存在，或已经被其他操作处理。",
    SESSION_EXPIRED: "解锁会话已过期，请重新解锁。",
    AUTH_REQUIRED: "请先解锁加密仓库。",
    VAULT_LOCKED: "加密仓库已锁定，请重新解锁。",
    PLAN_DATE_IN_PAST: "过去的时间范围不能新增未来计划。",
    INVALID_CURRENT_PIN: "当前 PIN 不正确。",
    INVALID_RECOVERY_CREDENTIAL: "恢复密钥不正确。",
    PROFILE_UPDATE_FAILED: "个人档案保存失败。",
    PIN_CHANGE_FAILED: "PIN 修改失败。",
    PIN_RESET_FAILED: "PIN 重置失败。",
    RECOVERY_CREDENTIAL_CHANGE_FAILED: "恢复密钥修改失败。",
    BACKUP_CHECK_FAILED: "仓库完整性检查失败。",
    BACKUP_EXPORT_FAILED: "备份导出失败。",
    INVALID_BACKUP_FILE: "请选择有效的 .lifevault 备份文件。",
    INVALID_BACKUP_CREDENTIAL: "备份 PIN 或恢复密钥不正确。",
    BACKUP_IMPORT_CHECK_FAILED: "备份包验证或恢复演练失败。",
    BACKUP_RESTORE_FAILED: "备份恢复失败，当前仓库未被替换。",
    BACKUP_TOO_LARGE: "备份文件超过 512 MB 限制。",
    AUTO_BACKUP_VERIFY_FAILED: "最近备份验证失败。",
    INVALID_SEARCH_RANGE: "搜索开始日期不能晚于结束日期。",
    TAG_NAME_CONFLICT: "已经存在同名标签，请换一个名称。",
  };
  return messages[error?.code] || error?.message || "操作失败，请稍后重试。";
}

function showOperationError(error) {
  showToast(friendlyErrorMessage(error), "error");
}

function setButtonBusy(button, busy, busyLabel = "处理中…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.idleLabel) button.dataset.idleLabel = button.textContent;
    button.disabled = true;
    button.classList.add("is-busy");
    button.textContent = busyLabel;
    button.setAttribute("aria-busy", "true");
    return;
  }
  button.disabled = false;
  button.classList.remove("is-busy");
  button.textContent = button.dataset.idleLabel || button.textContent;
  button.removeAttribute("aria-busy");
  delete button.dataset.idleLabel;
}

const confirmModal = document.getElementById("confirmModal");
const confirmEyebrow = document.getElementById("confirmEyebrow");
const confirmTitle = document.getElementById("confirmTitle");
const confirmMessage = document.getElementById("confirmMessage");
const confirmCancel = document.getElementById("confirmCancel");
const confirmAccept = document.getElementById("confirmAccept");
let confirmResolver = null;
let confirmReturnFocus = null;

function closeConfirmation(result = false) {
  if (confirmModal.classList.contains("hidden")) return;
  confirmModal.classList.add("hidden");
  confirmModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("confirm-open");
  const resolver = confirmResolver;
  confirmResolver = null;
  resolver?.(result);
  if (confirmReturnFocus instanceof HTMLElement && document.contains(confirmReturnFocus)) {
    confirmReturnFocus.focus();
  }
  confirmReturnFocus = null;
}

function askConfirmation({
  eyebrow = "请确认",
  title = "确认操作",
  message,
  confirmLabel = "确认",
  tone = "danger",
} = {}) {
  if (confirmResolver) closeConfirmation(false);
  confirmReturnFocus = document.activeElement;
  confirmEyebrow.textContent = eyebrow;
  confirmTitle.textContent = title;
  confirmMessage.textContent = message || "确定继续吗？";
  confirmAccept.textContent = confirmLabel;
  confirmAccept.dataset.tone = tone;
  confirmModal.dataset.tone = tone;
  confirmModal.classList.remove("hidden");
  confirmModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("confirm-open");
  window.requestAnimationFrame(() => confirmCancel.focus());
  return new Promise((resolve) => {
    confirmResolver = resolve;
  });
}

confirmCancel.addEventListener("click", () => closeConfirmation(false));
confirmAccept.addEventListener("click", () => closeConfirmation(true));
confirmModal.addEventListener("click", (event) => {
  if (event.target === confirmModal) closeConfirmation(false);
});

const memoryRichEditorIds = {
  quick: "quickMemoryContent",
  drawer: "memoryContent",
};

function richEditorAvailable() {
  return Boolean(window.tinymce?.init);
}

function getRichEditor(editorId) {
  return window.tinymce?.get?.(editorId) || null;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function plainTextToRichHtml(value) {
  const normalized = String(value || "").replace(/\r\n?/g, "\n").trim();
  if (!normalized) return "";
  return normalized
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("");
}

function richHtmlToPlainText(value) {
  const container = document.createElement("div");
  container.innerHTML = String(value || "");
  return (container.textContent || container.innerText || "").replace(/\u00a0/g, " ").trim();
}

function isRichHtmlEmpty(value) {
  return !richHtmlToPlainText(value);
}

function sanitizeRichMemoryHtml(value) {
  const template = document.createElement("template");
  template.innerHTML = String(value || "");
  const allowedTags = new Set(["P", "BR", "STRONG", "B", "EM", "I", "U", "UL", "OL", "LI", "BLOCKQUOTE", "A", "HR", "CODE", "PRE", "SPAN"]);
  const allowedLinkSchemes = new Set(["http:", "https:", "mailto:"]);

  function sanitizeNode(node) {
    if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.textContent || "");
    if (node.nodeType !== Node.ELEMENT_NODE) return document.createTextNode("");
    const tag = node.tagName;
    const children = Array.from(node.childNodes).map(sanitizeNode);
    if (!allowedTags.has(tag)) {
      const fragment = document.createDocumentFragment();
      children.forEach((child) => fragment.appendChild(child));
      return fragment;
    }
    const element = document.createElement(tag.toLowerCase());
    if (tag === "A") {
      const href = node.getAttribute("href") || "";
      try {
        const parsed = new URL(href, window.location.origin);
        if (allowedLinkSchemes.has(parsed.protocol)) {
          element.setAttribute("href", href);
          element.setAttribute("target", "_blank");
          element.setAttribute("rel", "noopener noreferrer");
          const title = node.getAttribute("title");
          if (title) element.setAttribute("title", title);
        }
      } catch (_error) {
        // Drop invalid links.
      }
    }
    children.forEach((child) => element.appendChild(child));
    return element;
  }

  const output = document.createElement("div");
  Array.from(template.content.childNodes).forEach((node) => output.appendChild(sanitizeNode(node)));
  return output.innerHTML.trim();
}

function memoryEditorConfig(editorId, { fallback = false } = {}) {
  const textarea = document.getElementById(editorId);
  const isQuickEditor = editorId === memoryRichEditorIds.quick;
  return {
    target: textarea,
    base_url: "/static/tinymce",
    skin_url: "/static/tinymce/skins/ui/oxide",
    content_css: "/static/tinymce/skins/content/default/content.min.css",
    suffix: ".min",
    license_key: "gpl",
    icons: "default",
    theme: "silver",
    menubar: false,
    branding: false,
    promotion: false,
    statusbar: false,
    resize: false,
    height: isQuickEditor ? 320 : 280,
    min_height: isQuickEditor ? 320 : 280,
    plugins: fallback ? "" : "lists link code",
    toolbar: fallback
      ? "undo redo | bold italic underline | removeformat"
      : "undo redo | bold italic underline | bullist numlist | link blockquote | removeformat code",
    toolbar_mode: "sliding",
    toolbar_location: "top",
    placeholder: textarea?.getAttribute("placeholder") || "写下这段记忆……",
    content_style: `
      body {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 16px;
        line-height: 1.8;
        color: #25352d;
        padding: 10px 12px;
      }
      p { margin: 0 0 0.8em; }
      blockquote {
        margin: 0.8em 0;
        padding-left: 1em;
        border-left: 3px solid #b9cdbf;
        color: #4f6458;
      }
      code, pre {
        font-family: "Cascadia Code", Consolas, monospace;
        background: #f3f6ef;
        border-radius: 8px;
      }
      pre { padding: 10px 12px; white-space: pre-wrap; }
    `,
    setup(editor) {
      const sync = () => editor.save();
      editor.on("change input undo redo SetContent NodeChange", sync);
      editor.on("init", () => {
        editor.setContent(textarea?.value || "");
        editor.save();
        editor.getContainer()?.classList.add("lifegraph-rich-editor-ready");
      });
    },
  };
}

async function initMemoryRichEditor(editorId, initialHtml = "") {
  const textarea = document.getElementById(editorId);
  if (!textarea) return;
  textarea.value = initialHtml || "";
  const existing = getRichEditor(editorId);
  if (existing) {
    existing.setContent(initialHtml || "");
    existing.save();
    return;
  }
  if (!richEditorAvailable()) return;
  try {
    await window.tinymce.init(memoryEditorConfig(editorId));
  } catch (error) {
    console.warn("TinyMCE 完整工具栏初始化失败，已切换为基础工具栏。", error);
    try {
      await window.tinymce.init(memoryEditorConfig(editorId, { fallback: true }));
    } catch (fallbackError) {
      console.warn("TinyMCE 基础工具栏初始化失败，已保留普通文本输入框。", fallbackError);
    }
  }
}

function destroyMemoryRichEditor(editorId) {
  const editor = getRichEditor(editorId);
  if (editor) {
    editor.save();
    editor.remove();
  }
}

function getMemoryRichEditorContent(editorId) {
  const editor = getRichEditor(editorId);
  if (editor) {
    editor.save();
    return editor.getContent() || "";
  }
  return document.getElementById(editorId)?.value || "";
}

function focusMemoryRichEditor(editorId) {
  const editor = getRichEditor(editorId);
  if (editor) {
    editor.focus();
    return;
  }
  document.getElementById(editorId)?.focus();
}

function contentToEditableMemoryHtml(item) {
  if (item?.content_format === "html") return item.content || "";
  return plainTextToRichHtml(item?.content || "");
}

function memoryTagElements(mode) {
  const isQuick = mode === "quick";
  return {
    selected: document.getElementById(isQuick ? "quickMemorySelectedTags" : "memorySelectedTags"),
    picker: document.getElementById(isQuick ? "quickMemoryTagPicker" : "memoryTagPicker"),
    options: document.getElementById(isQuick ? "quickMemoryTagOptions" : "memoryTagOptions"),
    toggle: document.getElementById(isQuick ? "toggleQuickMemoryTagPicker" : "toggleMemoryTagPicker"),
    input: document.getElementById(isQuick ? "quickMemoryNewTagName" : "memoryNewTagName"),
    create: document.getElementById(isQuick ? "createQuickMemoryTag" : "createMemoryTag"),
  };
}

function memoryTagNameKey(value) {
  return String(value || "").trim().toLocaleLowerCase("zh-CN");
}

function renderMemoryTagSelector(mode) {
  const elements = memoryTagElements(mode);
  if (!elements.selected || !elements.options) return;
  const selectedIds = selectedMemoryTagIds[mode];
  elements.selected.replaceChildren();

  const selectedTags = availableMemoryTags.filter((tag) => selectedIds.has(tag.id));
  if (!selectedTags.length) {
    const empty = document.createElement("span");
    empty.className = "memory-tag-empty";
    empty.textContent = "尚未添加标签";
    elements.selected.appendChild(empty);
  } else {
    selectedTags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "memory-tag-chip is-selected";
      chip.textContent = `#${tag.name} ×`;
      chip.title = `移除标签：${tag.name}`;
      chip.addEventListener("click", () => {
        selectedIds.delete(tag.id);
        renderMemoryTagSelector(mode);
      });
      elements.selected.appendChild(chip);
    });
  }

  elements.options.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("p");
    empty.className = "memory-tag-picker-empty";
    empty.textContent = "还没有标签，可以在下方新建。";
    elements.options.appendChild(empty);
    return;
  }

  availableMemoryTags.forEach((tag) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "memory-tag-option";
    option.classList.toggle("is-selected", selectedIds.has(tag.id));
    option.setAttribute("aria-pressed", selectedIds.has(tag.id) ? "true" : "false");
    option.textContent = `#${tag.name}`;
    option.addEventListener("click", () => {
      if (selectedIds.has(tag.id)) selectedIds.delete(tag.id);
      else selectedIds.add(tag.id);
      renderMemoryTagSelector(mode);
    });
    elements.options.appendChild(option);
  });
}

function setMemoryTagSelection(mode, tags = []) {
  selectedMemoryTagIds[mode] = new Set((tags || []).map((tag) => typeof tag === "string" ? tag : tag.id).filter(Boolean));
  renderMemoryTagSelector(mode);
}

function resetMemoryTagSelector(mode) {
  const elements = memoryTagElements(mode);
  selectedMemoryTagIds[mode] = new Set();
  if (elements.picker) elements.picker.classList.add("hidden");
  if (elements.toggle) elements.toggle.setAttribute("aria-expanded", "false");
  if (elements.input) elements.input.value = "";
  renderMemoryTagSelector(mode);
}

function pruneUnavailableMemoryTagSelections() {
  const validIds = new Set(availableMemoryTags.map((tag) => tag.id));
  for (const selectedIds of [
    selectedMemoryTagIds.quick,
    selectedMemoryTagIds.drawer,
    selectedMemorySearchTagIds,
    selectedMemoryMapTagIds,
    draftMemoryMapTagIds,
  ]) {
    for (const tagId of [...selectedIds]) {
      if (!validIds.has(tagId)) selectedIds.delete(tagId);
    }
  }
}

function renderAllMemoryTagControls() {
  pruneUnavailableMemoryTagSelections();
  renderMemoryTagSelector("quick");
  renderMemoryTagSelector("drawer");
  renderMemorySearchTagOptions();
  renderMemoryMapFilterTagOptions();
  updateMemoryMapFilterEntryButtons();
  updateMemoryMapFilterSummary();
  renderTagManagement();
}

async function loadMemoryTags({ force = false } = {}) {
  if (!force && availableMemoryTags.length) return availableMemoryTags;
  if (!force && memoryTagsLoadPromise) return memoryTagsLoadPromise;
  memoryTagsLoadPromise = api("/api/v1/tags", {}, true)
    .then((tags) => {
      availableMemoryTags = Array.isArray(tags) ? tags : [];
      renderAllMemoryTagControls();
      return availableMemoryTags;
    })
    .finally(() => {
      memoryTagsLoadPromise = null;
    });
  return memoryTagsLoadPromise;
}

function toggleMemoryTagPicker(mode) {
  const elements = memoryTagElements(mode);
  if (!elements.picker || !elements.toggle) return;
  const shouldOpen = elements.picker.classList.contains("hidden");
  elements.picker.classList.toggle("hidden", !shouldOpen);
  elements.toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
  if (shouldOpen) {
    loadMemoryTags().catch(showOperationError);
    requestAnimationFrame(() => elements.input?.focus());
  }
}

async function createAndSelectMemoryTag(mode) {
  const elements = memoryTagElements(mode);
  const name = String(elements.input?.value || "").trim();
  if (!name) {
    showToast("请输入标签名称。", "error");
    elements.input?.focus();
    return;
  }
  const existing = availableMemoryTags.find((tag) => memoryTagNameKey(tag.name) === memoryTagNameKey(name));
  if (existing) {
    selectedMemoryTagIds[mode].add(existing.id);
    if (elements.input) elements.input.value = "";
    renderMemoryTagSelector(mode);
    showToast(`已选中标签 #${existing.name}`, "success");
    return;
  }

  setButtonBusy(elements.create, true, "新建中…");
  try {
    const tag = await api("/api/v1/tags", {
      method: "POST",
      body: JSON.stringify({ name }),
    }, true);
    availableMemoryTags.push(tag);
    availableMemoryTags.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
    selectedMemoryTagIds[mode].add(tag.id);
    if (elements.input) elements.input.value = "";
    renderAllMemoryTagControls();
    showToast(`标签 #${tag.name} 已创建`, "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(elements.create, false);
  }
}

async function syncMemoryTags(memoryId, selectedIds) {
  const currentTags = await api(`/api/v1/memories/${encodeURIComponent(memoryId)}/tags`, {}, true);
  const currentIds = new Set((currentTags || []).map((tag) => tag.id));
  const desiredIds = new Set(selectedIds || []);
  const toAttach = [...desiredIds].filter((tagId) => !currentIds.has(tagId));
  const toDetach = [...currentIds].filter((tagId) => !desiredIds.has(tagId));

  for (const tagId of toAttach) {
    await api(`/api/v1/memories/${encodeURIComponent(memoryId)}/tags/${encodeURIComponent(tagId)}`, {
      method: "POST",
    }, true);
  }
  for (const tagId of toDetach) {
    await api(`/api/v1/memories/${encodeURIComponent(memoryId)}/tags/${encodeURIComponent(tagId)}`, {
      method: "DELETE",
    }, true);
  }
}

function appendMemoryTagBadges(article, tags = []) {
  if (!tags?.length) return;
  const wrap = document.createElement("div");
  wrap.className = "memory-tag-readonly-list";
  tags.forEach((tag) => {
    const badge = document.createElement("span");
    badge.className = "memory-tag-readonly";
    badge.textContent = `#${tag.name}`;
    wrap.appendChild(badge);
  });
  article.appendChild(wrap);
}

function quickMemoryState() {
  if (!quickMemoryForm) return { title: "", content: "" };
  const form = new FormData(quickMemoryForm);
  return {
    title: String(form.get("title") || "").trim(),
    content: getMemoryRichEditorContent(memoryRichEditorIds.quick),
    tagIds: [...selectedMemoryTagIds.quick].sort(),
  };
}

function captureQuickMemorySnapshot() {
  quickMemorySnapshot = JSON.stringify(quickMemoryState());
}

function isQuickMemoryOpen() {
  return Boolean(quickMemoryModal && !quickMemoryModal.classList.contains("hidden"));
}

function isQuickMemoryDirty() {
  if (!isQuickMemoryOpen()) return false;
  return JSON.stringify(quickMemoryState()) !== quickMemorySnapshot;
}

function formatQuickMemoryDate(isoDate) {
  const parsed = parseIsoDate(isoDate);
  if (Number.isNaN(parsed.getTime())) return isoDate || "今天";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(parsed);
}

function deriveQuickMemoryTitle(content) {
  const compact = richHtmlToPlainText(content).replace(/\s+/g, " ").trim();
  if (!compact) return "今日记忆";
  return compact.length > 28 ? `${compact.slice(0, 28)}…` : compact;
}

async function openQuickMemoryModal() {
  if (!quickMemoryModal || !quickMemoryForm) return;
  if (!currentProgress?.today) {
    showToast("请先解锁并加载人生图谱。", "error");
    return;
  }
  quickMemoryReturnFocus = document.activeElement;
  quickMemoryForm.reset();
  resetMemoryTagSelector("quick");
  quickMemoryDateText.textContent = `${formatQuickMemoryDate(currentProgress.today)} · 今天`;
  quickMemoryModal.classList.remove("hidden");
  quickMemoryModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("quick-memory-open");
  try {
    await loadMemoryTags();
  } catch (error) {
    showOperationError(error);
  }
  initMemoryRichEditor(memoryRichEditorIds.quick, "");
  requestAnimationFrame(() => {
    captureQuickMemorySnapshot();
    focusMemoryRichEditor(memoryRichEditorIds.quick);
  });
}

function closeQuickMemoryModalNow({ restoreFocus = true } = {}) {
  if (!quickMemoryModal || !quickMemoryForm) return;
  destroyMemoryRichEditor(memoryRichEditorIds.quick);
  quickMemoryForm.reset();
  resetMemoryTagSelector("quick");
  quickMemoryModal.classList.add("hidden");
  quickMemoryModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("quick-memory-open");
  quickMemorySnapshot = "";
  if (restoreFocus && quickMemoryReturnFocus instanceof HTMLElement && document.contains(quickMemoryReturnFocus)) {
    quickMemoryReturnFocus.focus();
  }
  quickMemoryReturnFocus = null;
}

async function requestCloseQuickMemoryModal() {
  if (isQuickMemoryDirty()) {
    const confirmed = await askConfirmation({
      eyebrow: "尚未保存",
      title: "放弃这条今日小记吗？",
      message: "窗口里还有未保存的记忆内容。关闭后，这些文字不会保留。",
      confirmLabel: "放弃记录",
      tone: "warning",
    });
    if (!confirmed) return false;
  }
  closeQuickMemoryModalNow();
  return true;
}

async function saveQuickMemory(event) {
  event.preventDefault();
  if (!currentProgress?.today) return;
  const formState = quickMemoryState();
  const content = formState.content.trim();
  if (isRichHtmlEmpty(content)) {
    showToast("先写下一点今天的内容吧。", "error");
    focusMemoryRichEditor(memoryRichEditorIds.quick);
    return;
  }
  const submit = quickMemoryForm.querySelector('button[type="submit"]');
  setButtonBusy(submit, true, "加密保存中…");
  try {
    const memory = await api("/api/v1/memories", {
      method: "POST",
      body: JSON.stringify({
        time_scope: "day",
        period_key: currentProgress.today,
        title: formState.title || deriveQuickMemoryTitle(content),
        content,
        content_format: "html",
      }),
    }, true);
    await syncMemoryTags(memory.id, selectedMemoryTagIds.quick);
    closeQuickMemoryModalNow({ restoreFocus: false });
    await refreshContentStatuses();
    renderLifeMapView(true);
    if (!dateDrawer?.classList.contains("hidden") && selectedScope && selectedPeriodKey) {
      await openPeriodDrawer(selectedScope, selectedPeriodKey);
    }
    showToast("今日记忆已加密保存", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
}


function isMemorySearchOpen() {
  return Boolean(memorySearchModal && !memorySearchModal.classList.contains("hidden"));
}

function memorySearchScopeLabel(item) {
  if (item.time_scope === "year") return `${item.period_key} · 年度记忆`;
  if (item.time_scope === "month") return `${item.period_key} · 月份记忆`;
  return `${item.period_key} · 日期记忆`;
}

function plainTextFromMemoryContent(content = "", format = "plain") {
  if (!content) return "";
  if (format !== "html") return content.replace(/\s+/g, " ").trim();
  const template = document.createElement("template");
  template.innerHTML = sanitizeRichMemoryHtml(content);
  return (template.content.textContent || "").replace(/\s+/g, " ").trim();
}

function memorySearchSnippet(item) {
  const text = plainTextFromMemoryContent(item.content || "", item.content_format || "plain");
  if (!text) return "暂无正文";
  return text.length > 150 ? `${text.slice(0, 150)}…` : text;
}

function renderMemorySearchTagOptions() {
  if (!memorySearchTagOptions) return;
  memorySearchTagOptions.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("span");
    empty.className = "memory-search-tag-empty";
    empty.textContent = "暂无标签，可先在记忆编辑中创建。";
    memorySearchTagOptions.appendChild(empty);
    return;
  }
  availableMemoryTags.forEach((tag) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "memory-search-tag-chip";
    button.classList.toggle("is-selected", selectedMemorySearchTagIds.has(tag.id));
    button.setAttribute("aria-pressed", selectedMemorySearchTagIds.has(tag.id) ? "true" : "false");
    button.textContent = `#${tag.name}`;
    button.addEventListener("click", () => {
      if (selectedMemorySearchTagIds.has(tag.id)) selectedMemorySearchTagIds.delete(tag.id);
      else selectedMemorySearchTagIds.add(tag.id);
      renderMemorySearchTagOptions();
    });
    memorySearchTagOptions.appendChild(button);
  });
}

function clearMemorySearchResults(message = "输入条件后开始搜索") {
  memorySearchRequestSequence += 1;
  memorySearchResults?.replaceChildren();
  if (memorySearchSummary) memorySearchSummary.textContent = message;
  memorySearchLimitHint?.classList.add("hidden");
}

function resetMemorySearchFilters() {
  memorySearchForm?.reset();
  selectedMemorySearchTagIds.clear();
  renderMemorySearchTagOptions();
  clearMemorySearchResults();
  memorySearchQuery?.focus();
}

function closeMemorySearchModalNow({ restoreFocus = true } = {}) {
  if (!isMemorySearchOpen()) return;
  memorySearchRequestSequence += 1;
  memorySearchModal.classList.add("hidden");
  memorySearchModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("memory-search-open");
  if (restoreFocus && memorySearchReturnFocus instanceof HTMLElement && document.contains(memorySearchReturnFocus)) {
    memorySearchReturnFocus.focus();
  }
  memorySearchReturnFocus = null;
}

async function openMemorySearchModal() {
  if (!memorySearchModal || !currentProfile) return;
  if (isMemoryMapFilterOpen()) closeMemoryMapFilterModalNow({ restoreFocus: false });
  memorySearchReturnFocus = document.activeElement;
  memorySearchModal.classList.remove("hidden");
  memorySearchModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("memory-search-open");
  try {
    await loadMemoryTags();
    renderMemorySearchTagOptions();
  } catch (error) {
    showOperationError(error);
  }
  requestAnimationFrame(() => memorySearchQuery?.focus());
}

function focusMemorySearchTarget(memoryId) {
  requestAnimationFrame(() => {
    const selector = `[data-content-kind="memory"][data-content-id="${CSS.escape(memoryId)}"]`;
    const card = document.querySelector(selector);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("search-target-flash");
    window.setTimeout(() => card.classList.remove("search-target-flash"), 1800);
  });
}

async function openMemorySearchResult(item) {
  closeMemorySearchModalNow({ restoreFocus: false });
  const opened = await openPeriodDrawer(item.time_scope, item.period_key);
  if (opened !== false) focusMemorySearchTarget(item.id);
}

function renderMemorySearchResultsData(data) {
  memorySearchResults.replaceChildren();
  const items = data?.items || [];
  memorySearchSummary.textContent = items.length ? `找到 ${items.length} 条记忆` : "没有找到符合条件的记忆";
  memorySearchLimitHint.classList.toggle("hidden", !data?.has_more);
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "memory-search-empty";
    empty.textContent = "可以换一个关键词、减少标签条件，或放宽日期范围。";
    memorySearchResults.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "memory-search-result-card";
    button.addEventListener("click", () => openMemorySearchResult(item));

    const top = document.createElement("div");
    top.className = "memory-search-result-top";
    const title = document.createElement("strong");
    title.textContent = item.title || "未命名记忆";
    const scope = document.createElement("span");
    scope.textContent = memorySearchScopeLabel(item);
    top.append(title, scope);

    const snippet = document.createElement("p");
    snippet.textContent = memorySearchSnippet(item);
    button.append(top, snippet);

    if (item.tags?.length) {
      const tags = document.createElement("div");
      tags.className = "memory-search-result-tags";
      item.tags.forEach((tag) => {
        const badge = document.createElement("span");
        badge.textContent = `#${tag.name}`;
        tags.appendChild(badge);
      });
      button.appendChild(tags);
    }
    memorySearchResults.appendChild(button);
  });
}

async function runMemorySearch() {
  if (!memorySearchForm) return;
  const submit = memorySearchForm.querySelector('button[type="submit"]');
  if (memorySearchDateFrom.value && memorySearchDateTo.value && memorySearchDateFrom.value > memorySearchDateTo.value) {
    showToast("开始日期不能晚于结束日期", "error");
    memorySearchDateFrom.focus();
    return;
  }
  const params = new URLSearchParams();
  const query = memorySearchQuery.value.trim();
  if (query) params.set("q", query);
  if (memorySearchDateFrom.value) params.set("date_from", memorySearchDateFrom.value);
  if (memorySearchDateTo.value) params.set("date_to", memorySearchDateTo.value);
  selectedMemorySearchTagIds.forEach((tagId) => params.append("tag_id", tagId));
  params.set("limit", "100");

  const requestSequence = ++memorySearchRequestSequence;
  setButtonBusy(submit, true, "搜索中…");
  memorySearchSummary.textContent = "正在搜索加密记忆……";
  memorySearchResults.replaceChildren();
  memorySearchLimitHint.classList.add("hidden");
  try {
    const data = await api(`/api/v1/memories/search?${params.toString()}`, {}, true);
    if (requestSequence !== memorySearchRequestSequence || !isMemorySearchOpen()) return;
    renderMemorySearchResultsData(data);
  } catch (error) {
    if (requestSequence !== memorySearchRequestSequence) return;
    showOperationError(error);
    clearMemorySearchResults("搜索失败，请调整条件后重试");
  } finally {
    setButtonBusy(submit, false);
  }
}

function isMemoryMapFilterOpen() {
  return Boolean(memoryMapFilterModal && !memoryMapFilterModal.classList.contains("hidden"));
}

function memoryMapFilterIsActive() {
  return selectedMemoryMapTagIds.size > 0;
}

function updateMemoryMapFilterEntryButtons() {
  const count = selectedMemoryMapTagIds.size;
  const text = count ? `标签筛选 · ${count}` : "标签筛选";
  [memoryMapFilterHomeButton, memoryMapFilterFullPageButton].forEach((button) => {
    if (!button) return;
    button.textContent = text;
    button.classList.toggle("is-active", count > 0);
    button.setAttribute("aria-pressed", count > 0 ? "true" : "false");
  });
}

function memoryMapFilterSummaryText() {
  if (!memoryMapFilterIsActive()) return "当前未启用标签筛选。";
  const tagNames = availableMemoryTags
    .filter((tag) => selectedMemoryMapTagIds.has(tag.id))
    .map((tag) => `#${tag.name}`);
  const label = tagNames.length ? tagNames.join(" + ") : `${selectedMemoryMapTagIds.size} 个标签`;
  return `${label} · 命中 ${memoryMapTagMatches.memoryCount} 条记忆，覆盖 ${memoryMapTagMatches.dates.size} 天、${memoryMapTagMatches.months.size} 月、${memoryMapTagMatches.years.size} 年。`;
}

function updateMemoryMapFilterSummary() {
  if (memoryMapFilterSummary) memoryMapFilterSummary.textContent = memoryMapFilterSummaryText();
}

function renderMemoryMapFilterTagOptions() {
  if (!memoryMapFilterTagOptions) return;
  memoryMapFilterTagOptions.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("p");
    empty.className = "memory-map-filter-empty";
    empty.textContent = "还没有标签。可以先在“记一记”或记忆编辑中创建标签。";
    memoryMapFilterTagOptions.appendChild(empty);
    return;
  }
  availableMemoryTags.forEach((tag) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "memory-map-filter-tag-chip";
    button.classList.toggle("is-selected", draftMemoryMapTagIds.has(tag.id));
    button.setAttribute("aria-pressed", draftMemoryMapTagIds.has(tag.id) ? "true" : "false");
    button.textContent = `#${tag.name}`;
    button.addEventListener("click", () => {
      if (draftMemoryMapTagIds.has(tag.id)) draftMemoryMapTagIds.delete(tag.id);
      else draftMemoryMapTagIds.add(tag.id);
      renderMemoryMapFilterTagOptions();
    });
    memoryMapFilterTagOptions.appendChild(button);
  });
}

function setMemoryMapTagMatchData(data = {}) {
  memoryMapTagMatches = {
    dates: new Set(data.dates || []),
    months: new Set(data.months || []),
    years: new Set(data.years || []),
    memoryCount: Number(data.memory_count || 0),
  };
  memoryMapFilterRevision += 1;
  lifeGridSignature = "";
  fullPageGridSignature = "";
}

function redrawMemoryMapFilterState() {
  renderLifeMapView(true);
  if (fullPageLifeOpen) drawFullPageLifeGrid(true);
}

async function refreshMemoryMapTagMatches({ redraw = true } = {}) {
  if (!currentProgress || !memoryMapFilterIsActive()) {
    setMemoryMapTagMatchData();
    updateMemoryMapFilterEntryButtons();
    updateMemoryMapFilterSummary();
    if (redraw) redrawMemoryMapFilterState();
    return;
  }
  const params = new URLSearchParams({
    start: currentProgress.birth_date,
    end: currentProgress.target_date,
  });
  selectedMemoryMapTagIds.forEach((tagId) => params.append("tag_id", tagId));
  const requestSequence = ++memoryMapFilterRequestSequence;
  const data = await api(`/api/v1/memories/tag-map?${params.toString()}`, {}, true);
  if (requestSequence !== memoryMapFilterRequestSequence) return;
  setMemoryMapTagMatchData(data);
  updateMemoryMapFilterEntryButtons();
  updateMemoryMapFilterSummary();
  if (redraw) redrawMemoryMapFilterState();
}

function closeMemoryMapFilterModalNow({ restoreFocus = true } = {}) {
  if (!memoryMapFilterModal) return;
  memoryMapFilterModal.classList.add("hidden");
  memoryMapFilterModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("memory-map-filter-open");
  draftMemoryMapTagIds.clear();
  if (restoreFocus && memoryMapFilterReturnFocus instanceof HTMLElement && document.contains(memoryMapFilterReturnFocus)) {
    memoryMapFilterReturnFocus.focus();
  }
  memoryMapFilterReturnFocus = null;
}

async function openMemoryMapFilterModal() {
  if (!memoryMapFilterModal || !currentProfile) return;
  if (isMemorySearchOpen()) closeMemorySearchModalNow({ restoreFocus: false });
  memoryMapFilterReturnFocus = document.activeElement;
  draftMemoryMapTagIds.clear();
  selectedMemoryMapTagIds.forEach((tagId) => draftMemoryMapTagIds.add(tagId));
  memoryMapFilterModal.classList.remove("hidden");
  memoryMapFilterModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("memory-map-filter-open");
  try {
    await loadMemoryTags();
    renderMemoryMapFilterTagOptions();
    updateMemoryMapFilterSummary();
  } catch (error) {
    showOperationError(error);
  }
}

async function applyMemoryMapTagFilter() {
  selectedMemoryMapTagIds.clear();
  draftMemoryMapTagIds.forEach((tagId) => selectedMemoryMapTagIds.add(tagId));
  try {
    await refreshMemoryMapTagMatches();
    if (memoryMapFilterIsActive()) showToast(memoryMapFilterSummaryText(), "success");
    else showToast("已清除地图标签筛选", "success");
    closeMemoryMapFilterModalNow();
  } catch (error) {
    showOperationError(error);
  }
}

async function clearMemoryMapTagFilter() {
  draftMemoryMapTagIds.clear();
  selectedMemoryMapTagIds.clear();
  memoryMapFilterRequestSequence += 1;
  setMemoryMapTagMatchData();
  renderMemoryMapFilterTagOptions();
  updateMemoryMapFilterEntryButtons();
  updateMemoryMapFilterSummary();
  redrawMemoryMapFilterState();
  showToast("已清除地图标签筛选", "success");
}

function memoryMapScopeMatches(scope, key) {
  if (!memoryMapFilterIsActive()) return false;
  if (scope === "day") return memoryMapTagMatches.dates.has(key);
  if (scope === "month") return memoryMapTagMatches.months.has(key);
  if (scope === "year") return memoryMapTagMatches.years.has(key);
  return false;
}

async function api(path, options = {}, requireAuth = false) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (requireAuth && token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(path, { ...options, headers });
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : { ok: false, error: { message: "响应为空" } };
  } catch (_) {
    payload = { ok: false, error: { message: `响应格式错误：HTTP ${response.status} ${text.slice(0, 180)}` } };
  }
  if (!response.ok || !payload.ok) {
    const detail = Array.isArray(payload.detail) ? payload.detail.map(item => item.msg).join("；") : null;
    const error = new Error(payload.error?.message || detail || `请求失败：${response.status}`);
    error.code = payload.error?.code;
    throw error;
  }
  return payload.data;
}

const settingsModal = document.getElementById("settingsModal");
const closeSettingsButton = document.getElementById("closeSettings");
const profileSettingsForm = document.getElementById("profileSettingsForm");
const profileSettingsSummary = document.getElementById("profileSettingsSummary");
const profileDisplayNameValue = document.getElementById("profileDisplayNameValue");
const profileBirthDateValue = document.getElementById("profileBirthDateValue");
const editProfileSettingsButton = document.getElementById("editProfileSettings");
const cancelProfileSettingsButton = document.getElementById("cancelProfileSettings");
const tagManagementSummary = document.getElementById("tagManagementSummary");
const tagManagementList = document.getElementById("tagManagementList");
const tagManagementNewName = document.getElementById("tagManagementNewName");
const createManagedTagButton = document.getElementById("createManagedTag");
const changePinForm = document.getElementById("changePinForm");
const recoveryCredentialForm = document.getElementById("recoveryCredentialForm");
const customRecoveryFields = document.getElementById("customRecoveryFields");
const refreshSecuritySummaryButton = document.getElementById("refreshSecuritySummaryButton");
const securitySlotSummary = document.getElementById("securitySlotSummary");
const securityAuditSummary = document.getElementById("securityAuditSummary");
const securityAuditList = document.getElementById("securityAuditList");
const recoveryModal = document.getElementById("recoveryModal");
const recoveryTitle = document.getElementById("recoveryTitle");
const recoveryDescription = document.getElementById("recoveryDescription");
const recoveryValue = document.getElementById("recoveryValue");
const resetPinModal = document.getElementById("resetPinModal");
const resetPinForm = document.getElementById("resetPinForm");
const openResetPinButton = document.getElementById("openResetPin");
const closeResetPinButton = document.getElementById("closeResetPin");
const cancelResetPinButton = document.getElementById("cancelResetPin");
const checkBackupButton = document.getElementById("checkBackupButton");
const exportBackupButton = document.getElementById("exportBackupButton");
const backupStatusText = document.getElementById("backupStatusText");
const autoBackupForm = document.getElementById("autoBackupForm");
const saveAutoBackupButton = document.getElementById("saveAutoBackupButton");
const runAutoBackupButton = document.getElementById("runAutoBackupButton");
const autoBackupStatusText = document.getElementById("autoBackupStatusText");
const autoBackupHealthCard = document.getElementById("autoBackupHealthCard");
const autoBackupHealthBadge = document.getElementById("autoBackupHealthBadge");
const autoBackupHealthTitle = document.getElementById("autoBackupHealthTitle");
const autoBackupHealthMessage = document.getElementById("autoBackupHealthMessage");
const autoBackupHealthMeta = document.getElementById("autoBackupHealthMeta");
const verifyLatestAutoBackupButton = document.getElementById("verifyLatestAutoBackupButton");
const autoBackupHistorySummary = document.getElementById("autoBackupHistorySummary");
const autoBackupHistoryList = document.getElementById("autoBackupHistoryList");
const refreshAutoBackupHistoryButton = document.getElementById("refreshAutoBackupHistoryButton");
const clearAutoBackupHistoryButton = document.getElementById("clearAutoBackupHistoryButton");
const importBackupFile = document.getElementById("importBackupFile");
const importCredentialMethod = document.getElementById("importCredentialMethod");
const importCredentialSecret = document.getElementById("importCredentialSecret");
const checkImportBackupButton = document.getElementById("checkImportBackupButton");
const restoreImportBackupButton = document.getElementById("restoreImportBackupButton");
const importBackupStatusText = document.getElementById("importBackupStatusText");
let verifiedImportState = null;
let settingsReturnFocus = null;
let settingsProfileSnapshot = "";
let profileSettingsEditing = false;
let autoBackupSettingsSnapshot = "";
let recoveryModalContext = "initialize";
let backupReminderShownCode = "";

function profileSettingsState() {
  if (!profileSettingsForm) return {};
  const form = new FormData(profileSettingsForm);
  return {
    display_name: String(form.get("display_name") || "").trim(),
    birth_date: String(form.get("birth_date") || ""),
  };
}

function renderProfileSettingsSummary() {
  if (!currentProfile) return;
  if (profileDisplayNameValue) profileDisplayNameValue.textContent = currentProfile.display_name || "—";
  if (profileBirthDateValue) profileBirthDateValue.textContent = currentProfile.birth_date || "—";
}

function resetProfileSettingsFormValues() {
  if (!currentProfile || !profileSettingsForm) return;
  profileSettingsForm.elements.display_name.value = currentProfile.display_name || "";
  profileSettingsForm.elements.birth_date.value = currentProfile.birth_date || "";
  profileSettingsForm.elements.current_pin.value = "";
  settingsProfileSnapshot = JSON.stringify(profileSettingsState());
}

function setProfileSettingsEditMode(editing, { focus = true } = {}) {
  profileSettingsEditing = Boolean(editing);
  profileSettingsSummary?.classList.toggle("hidden", profileSettingsEditing);
  profileSettingsForm?.classList.toggle("hidden", !profileSettingsEditing);
  resetProfileSettingsFormValues();
  if (!focus) return;
  requestAnimationFrame(() => {
    const target = profileSettingsEditing
      ? profileSettingsForm?.elements.display_name
      : editProfileSettingsButton;
    target?.focus({ preventScroll: true });
  });
}

function tagUsageLabel(tag) {
  const count = Number(tag?.memory_count || 0);
  return `${count} 条记忆`;
}

function renderTagManagementEditRow(row, tag) {
  row.replaceChildren();
  row.classList.add("is-editing");

  const input = document.createElement("input");
  input.className = "tag-management-edit-input";
  input.maxLength = 40;
  input.value = tag.name;
  input.setAttribute("aria-label", `重命名标签 ${tag.name}`);

  const meta = document.createElement("span");
  meta.className = "tag-management-count";
  meta.textContent = tagUsageLabel(tag);

  const actions = document.createElement("div");
  actions.className = "tag-management-actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "text-button";
  cancel.textContent = "取消";
  const save = document.createElement("button");
  save.type = "button";
  save.className = "primary-button tag-management-save-button";
  save.textContent = "保存";
  actions.append(cancel, save);
  row.append(input, meta, actions);

  const cancelEdit = () => renderTagManagement();
  const saveEdit = async () => {
    const name = input.value.trim();
    if (!name) {
      showToast("请输入标签名称。", "error");
      input.focus();
      return;
    }
    const duplicate = availableMemoryTags.find(
      (item) => item.id !== tag.id && memoryTagNameKey(item.name) === memoryTagNameKey(name)
    );
    if (duplicate) {
      showToast("已经存在同名标签。", "error");
      input.focus();
      input.select();
      return;
    }
    setButtonBusy(save, true, "保存中…");
    try {
      const updated = await api(`/api/v1/tags/${encodeURIComponent(tag.id)}`, {
        method: "PUT",
        body: JSON.stringify({ name, color: tag.color || null }),
      }, true);
      await loadMemoryTags({ force: true });
      showToast(`标签已重命名为 #${updated.name}`, "success");
    } catch (error) {
      showOperationError(error);
      setButtonBusy(save, false);
    }
  };

  cancel.addEventListener("click", cancelEdit);
  save.addEventListener("click", saveEdit);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      cancelEdit();
    } else if (event.key === "Enter") {
      event.preventDefault();
      saveEdit();
    }
  });
  requestAnimationFrame(() => {
    input.focus();
    input.select();
  });
}

async function deleteManagedTag(tag) {
  const count = Number(tag?.memory_count || 0);
  const confirmed = await askConfirmation({
    eyebrow: "删除标签",
    title: `删除 #${tag.name}？`,
    message: count
      ? `这个标签当前用于 ${count} 条记忆。删除后记忆正文仍会保留，只移除标签关联。`
      : "这个标签当前没有关联记忆。删除后无法恢复标签本身。",
    confirmLabel: "删除标签",
    tone: "danger",
  });
  if (!confirmed) return;

  const affectedMapFilter = selectedMemoryMapTagIds.has(tag.id);

  try {
    await api(`/api/v1/tags/${encodeURIComponent(tag.id)}`, { method: "DELETE" }, true);
    selectedMemoryTagIds.quick.delete(tag.id);
    selectedMemoryTagIds.drawer.delete(tag.id);
    selectedMemorySearchTagIds.delete(tag.id);
    selectedMemoryMapTagIds.delete(tag.id);
    draftMemoryMapTagIds.delete(tag.id);
    await loadMemoryTags({ force: true });
    if (affectedMapFilter) await refreshMemoryMapTagMatches();
    showToast(`标签 #${tag.name} 已删除`, "success");
  } catch (error) {
    showOperationError(error);
  }
}

function renderTagManagement() {
  if (!tagManagementList || !tagManagementSummary) return;
  const totalUsage = availableMemoryTags.reduce(
    (sum, tag) => sum + Number(tag.memory_count || 0),
    0,
  );
  tagManagementSummary.textContent = `${availableMemoryTags.length} 个标签 · ${totalUsage} 次使用`;
  tagManagementList.replaceChildren();

  if (!availableMemoryTags.length) {
    const empty = document.createElement("p");
    empty.className = "tag-management-empty";
    empty.textContent = "还没有标签，可以在上方新建。";
    tagManagementList.appendChild(empty);
    return;
  }

  availableMemoryTags.forEach((tag) => {
    const row = document.createElement("div");
    row.className = "tag-management-row";
    row.dataset.tagId = tag.id;

    const identity = document.createElement("div");
    identity.className = "tag-management-identity";
    const name = document.createElement("strong");
    name.textContent = `#${tag.name}`;
    const count = document.createElement("span");
    count.className = "tag-management-count";
    count.textContent = tagUsageLabel(tag);
    identity.append(name, count);

    const actions = document.createElement("div");
    actions.className = "tag-management-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "text-button";
    edit.textContent = "重命名";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "text-button danger-text-button";
    remove.textContent = "删除";
    edit.addEventListener("click", () => renderTagManagementEditRow(row, tag));
    remove.addEventListener("click", () => deleteManagedTag(tag));
    actions.append(edit, remove);
    row.append(identity, actions);
    tagManagementList.appendChild(row);
  });
}

async function createManagedTag() {
  const name = String(tagManagementNewName?.value || "").trim();
  if (!name) {
    showToast("请输入标签名称。", "error");
    tagManagementNewName?.focus();
    return;
  }
  const existing = availableMemoryTags.find(
    (tag) => memoryTagNameKey(tag.name) === memoryTagNameKey(name)
  );
  if (existing) {
    showToast(`标签 #${existing.name} 已存在`, "error");
    tagManagementNewName?.focus();
    tagManagementNewName?.select();
    return;
  }

  setButtonBusy(createManagedTagButton, true, "新建中…");
  try {
    const tag = await api("/api/v1/tags", {
      method: "POST",
      body: JSON.stringify({ name }),
    }, true);
    if (tagManagementNewName) tagManagementNewName.value = "";
    await loadMemoryTags({ force: true });
    showToast(`标签 #${tag.name} 已创建`, "success");
    tagManagementNewName?.focus();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(createManagedTagButton, false);
  }
}

async function loadTagManagement() {
  if (tagManagementSummary) tagManagementSummary.textContent = "正在读取…";
  if (tagManagementList) {
    tagManagementList.innerHTML = '<p class="tag-management-empty">正在读取标签…</p>';
  }
  try {
    await loadMemoryTags({ force: true });
  } catch (error) {
    if (tagManagementSummary) tagManagementSummary.textContent = "读取失败";
    if (tagManagementList) {
      tagManagementList.innerHTML = '<p class="tag-management-empty">标签读取失败，请稍后重试。</p>';
    }
    showOperationError(error);
  }
}

function autoBackupFormState() {
  if (!autoBackupForm) return {};
  const form = new FormData(autoBackupForm);
  return {
    enabled: Boolean(autoBackupForm.elements.enabled?.checked),
    frequency: String(form.get("frequency") || "daily"),
    retention_count: Number(form.get("retention_count") || 10),
  };
}

function recoveryCredentialFormHasInput() {
  if (!recoveryCredentialForm) return false;
  return Array.from(recoveryCredentialForm.querySelectorAll('input[type="password"]'))
    .some(input => Boolean(input.value));
}

function syncRecoveryCredentialMode() {
  if (!recoveryCredentialForm || !customRecoveryFields) return;
  const generate = Boolean(recoveryCredentialForm.elements.generate?.checked);
  customRecoveryFields.classList.toggle("hidden", generate);
  for (const input of customRecoveryFields.querySelectorAll("input")) {
    input.required = !generate;
    if (generate) input.value = "";
  }
}

function showRecoverySecret(secret, { context = "initialize", title, description } = {}) {
  recoveryModalContext = context;
  recoveryTitle.textContent = title || "保存你的恢复密钥";
  recoveryDescription.textContent = description || "请离线保存。它可以在忘记 PIN 或迁移设备时解锁仓库。";
  recoveryValue.textContent = secret;
  recoveryModal.classList.remove("hidden");
}

function hasUnsavedSettingsChanges() {
  if (settingsModal.classList.contains("hidden")) return false;
  const profileChanged = profileSettingsEditing && JSON.stringify(profileSettingsState()) !== settingsProfileSnapshot;
  const profilePin = profileSettingsEditing
    ? profileSettingsForm.querySelector('[name="current_pin"]')?.value || ""
    : "";
  const pinValues = Array.from(changePinForm.querySelectorAll('input[type="password"]')).some(input => input.value);
  const recoveryValues = recoveryCredentialFormHasInput();
  const importSelected = Boolean(importBackupFile?.files?.length || importCredentialSecret?.value);
  const autoBackupChanged = Boolean(
    autoBackupSettingsSnapshot &&
    JSON.stringify(autoBackupFormState()) !== autoBackupSettingsSnapshot
  );
  return profileChanged || Boolean(profilePin) || pinValues || recoveryValues || importSelected || autoBackupChanged;
}

function fillProfileSettingsForm() {
  if (!currentProfile) return;
  renderProfileSettingsSummary();
  resetProfileSettingsFormValues();
  setProfileSettingsEditMode(false, { focus: false });
  changePinForm.reset();
  recoveryCredentialForm?.reset();
  syncRecoveryCredentialMode();
  if (importBackupFile) importBackupFile.value = "";
  if (importCredentialMethod) importCredentialMethod.value = "pin";
  if (importCredentialSecret) {
    importCredentialSecret.value = "";
    importCredentialSecret.placeholder = "输入该备份对应的 PIN";
  }
  verifiedImportState = null;
  autoBackupSettingsSnapshot = "";
  if (autoBackupStatusText) {
    autoBackupStatusText.textContent = "正在读取自动备份状态…";
    delete autoBackupStatusText.dataset.tone;
  }
  if (autoBackupHealthCard) {
    autoBackupHealthCard.dataset.level = "neutral";
    autoBackupHealthBadge.textContent = "检查中";
    autoBackupHealthTitle.textContent = "正在检查备份健康状态";
    autoBackupHealthMessage.textContent = "请稍候…";
    autoBackupHealthMeta.textContent = "";
    verifyLatestAutoBackupButton.disabled = true;
  }
  if (autoBackupHistorySummary) autoBackupHistorySummary.textContent = "尚未读取";
  if (autoBackupHistoryList) autoBackupHistoryList.replaceChildren();
  if (restoreImportBackupButton) restoreImportBackupButton.disabled = true;
  if (importBackupStatusText) {
    importBackupStatusText.textContent = "尚未选择并验证备份包。";
    delete importBackupStatusText.dataset.tone;
  }
  settingsProfileSnapshot = JSON.stringify(profileSettingsState());
}

async function openSettingsModal() {
  if (!currentProfile) return;
  if (!dateDrawer.classList.contains("hidden")) {
    if (!(await confirmDiscardChanges())) return;
    closeDateDrawerNow();
  }
  settingsReturnFocus = document.activeElement;
  fillProfileSettingsForm();
  settingsModal.classList.remove("hidden");
  settingsModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("settings-open");
  await Promise.all([loadAutoBackupPanel(), loadSecuritySummary(), loadTagManagement()]);
  requestAnimationFrame(() => {
    const target = profileSettingsEditing
      ? profileSettingsForm?.elements.display_name
      : editProfileSettingsButton;
    target?.focus({ preventScroll: true });
  });
}

function closeSettingsModalNow() {
  if (!settingsModal || settingsModal.classList.contains("hidden")) return;
  settingsModal.classList.add("hidden");
  settingsModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("settings-open");
  profileSettingsEditing = false;
  profileSettingsSummary?.classList.remove("hidden");
  profileSettingsForm.classList.add("hidden");
  profileSettingsForm.reset();
  changePinForm.reset();
  recoveryCredentialForm?.reset();
  syncRecoveryCredentialMode();
  autoBackupForm?.reset();
  settingsProfileSnapshot = "";
  autoBackupSettingsSnapshot = "";
  if (settingsReturnFocus instanceof HTMLElement && document.contains(settingsReturnFocus)) {
    settingsReturnFocus.focus({ preventScroll: true });
  }
  settingsReturnFocus = null;
}

async function requestCloseSettingsModal() {
  if (settingsModal.classList.contains("hidden")) return;
  if (hasUnsavedSettingsChanges()) {
    const confirmed = await askConfirmation({
      eyebrow: "尚未保存",
      title: "放弃设置修改？",
      message: "当前个人档案、PIN、恢复密钥、自动备份或恢复区域还有未保存的输入。",
      confirmLabel: "放弃修改",
      tone: "warning",
    });
    if (!confirmed) return;
  }
  closeSettingsModalNow();
}

function openResetPinModal() {
  resetPinForm.reset();
  resetPinModal.classList.remove("hidden");
  resetPinModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("settings-open");
  requestAnimationFrame(() => resetPinForm.elements.recovery_secret.focus());
}

function closeResetPinModal() {
  if (resetPinModal.classList.contains("hidden")) return;
  resetPinModal.classList.add("hidden");
  resetPinModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("settings-open");
  resetPinForm.reset();
  openResetPinButton?.focus({ preventScroll: true });
}

settingsButton.addEventListener("click", openSettingsModal);
fullPageSettingsButton.addEventListener("click", openSettingsModal);
quickMemoryHomeButton?.addEventListener("click", openQuickMemoryModal);
quickMemoryFullPageButton?.addEventListener("click", openQuickMemoryModal);
closeQuickMemoryButton?.addEventListener("click", requestCloseQuickMemoryModal);
cancelQuickMemoryButton?.addEventListener("click", requestCloseQuickMemoryModal);
quickMemoryForm?.addEventListener("submit", saveQuickMemory);
document.getElementById("toggleQuickMemoryTagPicker")?.addEventListener("click", () => toggleMemoryTagPicker("quick"));
document.getElementById("createQuickMemoryTag")?.addEventListener("click", () => createAndSelectMemoryTag("quick"));
document.getElementById("quickMemoryNewTagName")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createAndSelectMemoryTag("quick");
});
quickMemoryModal?.addEventListener("click", (event) => {
  if (event.target === quickMemoryModal) requestCloseQuickMemoryModal();
});
closeSettingsButton.addEventListener("click", requestCloseSettingsModal);
editProfileSettingsButton?.addEventListener("click", () => setProfileSettingsEditMode(true));
cancelProfileSettingsButton?.addEventListener("click", () => setProfileSettingsEditMode(false));
createManagedTagButton?.addEventListener("click", createManagedTag);
tagManagementNewName?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createManagedTag();
});
settingsModal.addEventListener("click", (event) => {
  if (event.target === settingsModal) requestCloseSettingsModal();
});
openResetPinButton.addEventListener("click", openResetPinModal);
closeResetPinButton.addEventListener("click", closeResetPinModal);
cancelResetPinButton.addEventListener("click", closeResetPinModal);
resetPinModal.addEventListener("click", (event) => {
  if (event.target === resetPinModal) closeResetPinModal();
});

async function confirmBackupUsesSavedState() {
  if (!hasUnsavedSettingsChanges()) return true;
  return askConfirmation({
    eyebrow: "备份提示",
    title: "导出当前已保存的数据？",
    message: "设置表单中尚未保存的修改不会进入本次备份。",
    confirmLabel: "继续备份",
    tone: "warning",
  });
}

async function checkBackupIntegrity() {
  if (!(await confirmBackupUsesSavedState())) return;
  setButtonBusy(checkBackupButton, true, "检查中…");
  try {
    const report = await api("/api/v1/backup/check", {}, true);
    backupStatusText.textContent = `检查通过：schema v${report.schema_version}，已验证 ${report.encrypted_records_verified} 条加密记录。`;
    backupStatusText.dataset.tone = "success";
    showToast("加密仓库完整性检查通过", "success");
  } catch (error) {
    backupStatusText.textContent = friendlyErrorMessage(error);
    backupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(checkBackupButton, false);
  }
}

function backupFilenameFromDisposition(value) {
  const utf8Match = value?.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const plainMatch = value?.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] || "lifegraph-backup.lifevault";
}

async function exportLifevaultBackup() {
  if (!(await confirmBackupUsesSavedState())) return;
  setButtonBusy(exportBackupButton, true, "正在生成…");
  try {
    const headers = {};
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch("/api/v1/backup/export", { headers });
    if (!response.ok) {
      let payload = null;
      try { payload = await response.json(); } catch (_) { /* ignore */ }
      const error = new Error(payload?.error?.message || `备份导出失败：HTTP ${response.status}`);
      error.code = payload?.error?.code;
      throw error;
    }
    const blob = await response.blob();
    const filename = backupFilenameFromDisposition(response.headers.get("Content-Disposition"));
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    backupStatusText.textContent = `已导出 ${filename}，请将它保存到独立磁盘或可信云盘。`;
    backupStatusText.dataset.tone = "success";
    showToast(".lifevault 加密备份已导出", "success");
  } catch (error) {
    backupStatusText.textContent = friendlyErrorMessage(error);
    backupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(exportBackupButton, false);
  }
}

checkBackupButton?.addEventListener("click", checkBackupIntegrity);
exportBackupButton?.addEventListener("click", exportLifevaultBackup);

function formatBackupDateTime(value) {
  if (!value) return "尚无";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "时间未知" : parsed.toLocaleString();
}

function renderSecuritySummary(summary) {
  if (!securitySlotSummary || !securityAuditList || !securityAuditSummary) return;
  securitySlotSummary.replaceChildren();
  const slotLabels = { pin: "PIN 密钥槽", recovery: "恢复密钥槽" };
  for (const slotName of ["pin", "recovery"]) {
    const slot = summary?.key_slots?.[slotName] || {};
    const card = document.createElement("article");
    card.className = "security-slot-card";
    const title = document.createElement("strong");
    title.textContent = slotLabels[slotName];
    const meta = document.createElement("span");
    meta.textContent = slot.configured
      ? `${String(slot.kdf || "unknown").toUpperCase()} · 最近更新 ${formatBackupDateTime(slot.updated_at)}`
      : "未配置";
    card.append(title, meta);
    securitySlotSummary.appendChild(card);
  }

  const audit = Array.isArray(summary?.audit) ? summary.audit : [];
  securityAuditSummary.textContent = `${summary?.audit_count || audit.length} 条记录 · 最近显示 ${audit.length} 条`;
  securityAuditList.replaceChildren();
  if (!audit.length) {
    const empty = document.createElement("p");
    empty.className = "security-summary-empty";
    empty.textContent = "尚无安全操作记录。";
    securityAuditList.appendChild(empty);
    return;
  }
  for (const item of audit) {
    const row = document.createElement("article");
    row.className = "security-audit-item";
    const label = document.createElement("strong");
    label.textContent = item.label || "安全设置已更新";
    const time = document.createElement("span");
    time.textContent = formatBackupDateTime(item.at);
    row.append(label, time);
    securityAuditList.appendChild(row);
  }
}

async function loadSecuritySummary() {
  if (!securitySlotSummary || !securityAuditList) return;
  try {
    const summary = await api("/api/v1/security/summary", {}, true);
    renderSecuritySummary(summary);
  } catch (error) {
    securitySlotSummary.innerHTML = '<p class="security-summary-empty">安全状态读取失败。</p>';
    securityAuditList.replaceChildren();
    securityAuditSummary.textContent = "读取失败";
    showOperationError(error);
  }
}

refreshSecuritySummaryButton?.addEventListener("click", loadSecuritySummary);

function formatBackupSize(value) {
  const bytes = Number(value || 0);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatBackupDuration(seconds) {
  const value = Math.max(0, Number(seconds || 0));
  if (value < 3600) return `${Math.max(1, Math.round(value / 60))} 分钟`;
  if (value < 86400) return `${Math.round(value / 3600)} 小时`;
  return `${Math.round(value / 86400)} 天`;
}

function renderAutoBackupHealth(status) {
  if (!autoBackupHealthCard || !status?.health) return;
  const health = status.health;
  const labels = {
    healthy: ["健康", "最近备份已验证"],
    disabled: ["未启用", "自动备份尚未启用"],
    missing: ["需备份", "尚无可用自动备份"],
    invalid: ["异常", "最近备份文件异常"],
    failed: ["失败", "最近自动备份失败"],
    overdue: ["已超期", "自动备份已经超期"],
    verification_due: ["待验证", "最近备份等待恢复验证"],
  };
  const [badge, title] = labels[health.code] || ["检查", "备份状态需要确认"];
  autoBackupHealthCard.dataset.level = health.level || "neutral";
  autoBackupHealthBadge.textContent = badge;
  autoBackupHealthTitle.textContent = title;
  autoBackupHealthMessage.textContent = health.message || "";
  const meta = [];
  if (health.latest_backup?.created_at) {
    meta.push(`最近备份 ${formatBackupDateTime(health.latest_backup.created_at)}`);
  }
  if (health.overdue) meta.push(`已超期 ${formatBackupDuration(health.overdue_seconds)}`);
  if (health.verification?.verified_at) {
    meta.push(`最近验证 ${formatBackupDateTime(health.verification.verified_at)}`);
  }
  if (health.verification?.error) meta.push(`验证错误：${health.verification.error}`);
  autoBackupHealthMeta.textContent = meta.join(" · ") || "尚无备份健康记录";
  verifyLatestAutoBackupButton.disabled = !health.latest_backup?.filename;
}

function applyBackupHealthIndicator(status, { notify = false } = {}) {
  const health = status?.health;
  const alertLevel = ["missing", "overdue", "verification_due"].includes(health?.code)
    ? "warning"
    : (["invalid", "failed"].includes(health?.code) ? "error" : "");
  for (const button of [settingsButton, fullPageSettingsButton]) {
    if (!button) continue;
    if (alertLevel) button.dataset.backupAlert = alertLevel;
    else delete button.dataset.backupAlert;
    button.title = alertLevel ? `个人设置 · 备份提醒：${health.message}` : "个人设置";
  }
  if (notify && alertLevel && backupReminderShownCode !== health.code) {
    backupReminderShownCode = health.code;
    showToast(`备份提醒：${health.message}`, alertLevel === "error" ? "error" : "info");
  }
}

async function refreshBackupHealthReminder() {
  try {
    const status = await api("/api/v1/backup/auto", {}, true);
    applyBackupHealthIndicator(status, { notify: true });
  } catch (_) {
    // 首页主体已加载时，备份提醒读取失败不应打断用户。
  }
}

function fillAutoBackupForm(status) {
  if (!autoBackupForm || !status) return;
  autoBackupForm.elements.enabled.checked = Boolean(status.enabled);
  autoBackupForm.elements.frequency.value = status.frequency || "daily";
  autoBackupForm.elements.retention_count.value = String(status.retention_count || 10);
  autoBackupSettingsSnapshot = JSON.stringify(autoBackupFormState());
  renderAutoBackupHealth(status);
  applyBackupHealthIndicator(status);
  const frequencyLabel = status.frequency === "weekly" ? "每周" : "每天";
  const stateLabel = status.enabled ? `已启用（${frequencyLabel}）` : "未启用";
  const lastSuccess = status.last_success_at
    ? `最近成功：${formatBackupDateTime(status.last_success_at)}`
    : "尚无成功备份";
  const nextDue = status.enabled && status.next_due_at
    ? `；下次到期：${formatBackupDateTime(status.next_due_at)}`
    : "";
  const errorText = status.last_error ? `；最近失败：${status.last_error}` : "";
  autoBackupStatusText.textContent = `${stateLabel}；${lastSuccess}${nextDue}；本地保留 ${status.history_count || 0} 个备份${errorText}`;
  autoBackupStatusText.dataset.tone = status.last_error ? "error" : (status.last_success_at ? "success" : "");
  if (!autoBackupStatusText.dataset.tone) delete autoBackupStatusText.dataset.tone;
}

function renderAutoBackupHistory(items) {
  if (!autoBackupHistoryList || !autoBackupHistorySummary) return;
  autoBackupHistoryList.replaceChildren();
  const totalSize = items.reduce((sum, item) => sum + Number(item.size || 0), 0);
  autoBackupHistorySummary.textContent = `${items.length} 个 · ${formatBackupSize(totalSize)}`;
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "auto-backup-history-empty";
    empty.textContent = "暂无本地自动备份。启用后会立即生成首个备份，也可以点击“立即备份”。";
    autoBackupHistoryList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "auto-backup-history-item";
    if (!item.valid) card.dataset.invalid = "true";

    const main = document.createElement("div");
    main.className = "auto-backup-history-main";
    const title = document.createElement("strong");
    title.textContent = item.filename;
    const meta = document.createElement("span");
    meta.textContent = item.valid
      ? `${formatBackupDateTime(item.created_at || item.modified_at)} · ${formatBackupSize(item.size)} · schema v${item.schema_version}`
      : `${formatBackupDateTime(item.modified_at)} · ${formatBackupSize(item.size)} · 文件校验异常`;
    main.append(title, meta);

    const actions = document.createElement("div");
    actions.className = "auto-backup-history-actions";
    const downloadButton = document.createElement("button");
    downloadButton.type = "button";
    downloadButton.className = "text-button";
    downloadButton.textContent = "下载";
    downloadButton.addEventListener("click", () => downloadAutoBackup(item, downloadButton));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "text-button danger-text-button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => deleteAutoBackupHistoryItem(item, deleteButton));
    actions.append(downloadButton, deleteButton);
    card.append(main, actions);
    autoBackupHistoryList.appendChild(card);
  });
}

async function loadAutoBackupHistory() {
  const result = await api("/api/v1/backup/auto/history", {}, true);
  renderAutoBackupHistory(result.items || []);
  return result.items || [];
}

async function loadAutoBackupPanel() {
  try {
    const [status] = await Promise.all([
      api("/api/v1/backup/auto", {}, true),
      loadAutoBackupHistory(),
    ]);
    fillAutoBackupForm(status);
  } catch (error) {
    if (autoBackupStatusText) {
      autoBackupStatusText.textContent = friendlyErrorMessage(error);
      autoBackupStatusText.dataset.tone = "error";
    }
    if (autoBackupHistorySummary) autoBackupHistorySummary.textContent = "读取失败";
  }
}

async function saveAutoBackupPolicy(event) {
  event.preventDefault();
  const state = autoBackupFormState();
  setButtonBusy(saveAutoBackupButton, true, "保存中…");
  try {
    const status = await api("/api/v1/backup/auto", {
      method: "PUT",
      body: JSON.stringify({ ...state, create_initial_backup: true }),
    }, true);
    fillAutoBackupForm(status);
    await loadAutoBackupHistory();
    showToast(status.enabled ? "自动备份已启用" : "自动备份已关闭", "success");
  } catch (error) {
    autoBackupStatusText.textContent = friendlyErrorMessage(error);
    autoBackupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(saveAutoBackupButton, false);
  }
}

async function runAutoBackupNow() {
  if (!(await confirmBackupUsesSavedState())) return;
  setButtonBusy(runAutoBackupButton, true, "备份中…");
  try {
    const status = await api("/api/v1/backup/auto/run", { method: "POST" }, true);
    fillAutoBackupForm(status);
    await loadAutoBackupHistory();
    showToast(`本地备份已生成：${status.filename}`, "success");
  } catch (error) {
    autoBackupStatusText.textContent = friendlyErrorMessage(error);
    autoBackupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(runAutoBackupButton, false);
  }
}

async function verifyLatestAutoBackup() {
  setButtonBusy(verifyLatestAutoBackupButton, true, "验证中…");
  try {
    const result = await api("/api/v1/backup/auto/verify-latest", { method: "POST" }, true);
    fillAutoBackupForm(result.status);
    await loadAutoBackupHistory();
    showToast(`最近备份已通过恢复验证，共验证 ${result.encrypted_records_verified} 条加密记录`, "success");
  } catch (error) {
    try {
      const status = await api("/api/v1/backup/auto", {}, true);
      fillAutoBackupForm(status);
    } catch (_) { /* 保留原始错误 */ }
    showOperationError(error);
  } finally {
    setButtonBusy(verifyLatestAutoBackupButton, false);
  }
}

async function downloadAutoBackup(item, button) {
  setButtonBusy(button, true, "下载中…");
  try {
    const headers = {};
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(`/api/v1/backup/auto/history/${encodeURIComponent(item.filename)}`, { headers });
    if (!response.ok) {
      let payload = null;
      try { payload = await response.json(); } catch (_) { /* ignore */ }
      throw new Error(payload?.error?.message || `备份下载失败：HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = item.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function deleteAutoBackupHistoryItem(item, button) {
  const confirmed = await askConfirmation({
    eyebrow: "备份历史",
    title: "删除这个本地备份？",
    message: `${item.filename}\n删除后无法从备份历史中恢复。`,
    confirmLabel: "删除备份",
    tone: "danger",
  });
  if (!confirmed) return;
  setButtonBusy(button, true, "删除中…");
  try {
    const status = await api(`/api/v1/backup/auto/history/${encodeURIComponent(item.filename)}`, {
      method: "DELETE",
    }, true);
    fillAutoBackupForm(status);
    await loadAutoBackupHistory();
    showToast("本地备份已删除", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function clearAutoBackupHistory() {
  const confirmed = await askConfirmation({
    eyebrow: "备份历史",
    title: "清空全部本地自动备份？",
    message: "只会删除 data/backups/auto 中的自动备份，不影响当前仓库、手动导出的文件和恢复前安全备份。",
    confirmLabel: "清空备份历史",
    tone: "danger",
  });
  if (!confirmed) return;
  setButtonBusy(clearAutoBackupHistoryButton, true, "清空中…");
  try {
    const status = await api("/api/v1/backup/auto/history/clear", {
      method: "POST",
      body: JSON.stringify({ confirm: "CLEAR_AUTO_BACKUPS" }),
    }, true);
    fillAutoBackupForm(status);
    renderAutoBackupHistory([]);
    showToast(`已清理 ${status.deleted_count} 个本地自动备份`, "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(clearAutoBackupHistoryButton, false);
  }
}

autoBackupForm?.addEventListener("submit", saveAutoBackupPolicy);
runAutoBackupButton?.addEventListener("click", runAutoBackupNow);
verifyLatestAutoBackupButton?.addEventListener("click", verifyLatestAutoBackup);
refreshAutoBackupHistoryButton?.addEventListener("click", async () => {
  setButtonBusy(refreshAutoBackupHistoryButton, true, "刷新中…");
  try {
    await loadAutoBackupHistory();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(refreshAutoBackupHistoryButton, false);
  }
});
clearAutoBackupHistoryButton?.addEventListener("click", clearAutoBackupHistory);

function resetImportVerification(message = "备份选择已变化，请重新验证。") {
  verifiedImportState = null;
  if (restoreImportBackupButton) restoreImportBackupButton.disabled = true;
  if (importBackupStatusText) {
    importBackupStatusText.textContent = message;
    delete importBackupStatusText.dataset.tone;
  }
}

function selectedImportValues() {
  const file = importBackupFile?.files?.[0] || null;
  const method = importCredentialMethod?.value || "pin";
  const secret = importCredentialSecret?.value || "";
  return { file, method, secret };
}

function importSelectionMatchesVerification() {
  const current = selectedImportValues();
  return Boolean(
    verifiedImportState &&
    current.file === verifiedImportState.file &&
    current.method === verifiedImportState.method &&
    current.secret === verifiedImportState.secret
  );
}

function backupImportFormData({ includeConfirmation = false } = {}) {
  const { file, method, secret } = selectedImportValues();
  if (!file) {
    const error = new Error("请先选择 .lifevault 备份文件");
    error.code = "INVALID_BACKUP_FILE";
    throw error;
  }
  if (!secret) {
    const error = new Error(method === "pin" ? "请输入备份 PIN" : "请输入备份恢复密钥");
    error.code = "INVALID_BACKUP_CREDENTIAL";
    throw error;
  }
  const form = new FormData();
  form.append("backup_file", file, file.name);
  form.append("credential_method", method);
  form.append("credential_secret", secret);
  if (includeConfirmation) form.append("confirm", "REPLACE_REPOSITORY");
  return form;
}

async function apiForm(path, formData) {
  const headers = {};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(path, { method: "POST", headers, body: formData });
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : { ok: false, error: { message: "响应为空" } };
  } catch (_) {
    payload = { ok: false, error: { message: `响应格式错误：HTTP ${response.status}` } };
  }
  if (!response.ok || !payload.ok) {
    const error = new Error(payload.error?.message || `请求失败：${response.status}`);
    error.code = payload.error?.code;
    throw error;
  }
  return payload.data;
}

function formatImportReport(report) {
  const counts = report.record_counts || {};
  const totalContent = (counts.event || 0) + (counts.memory || 0) + (counts.plan || 0);
  const createdAt = report.created_at ? new Date(report.created_at).toLocaleString() : "未知时间";
  return `演练通过：备份创建于 ${createdAt}，schema v${report.schema_version}，包含 ${totalContent} 条内容，已验证 ${report.encrypted_records_verified} 条加密记录。`;
}

async function checkLifevaultImport() {
  setButtonBusy(checkImportBackupButton, true, "演练中…");
  if (restoreImportBackupButton) restoreImportBackupButton.disabled = true;
  try {
    const values = selectedImportValues();
    const report = await apiForm(
      "/api/v1/backup/import/check",
      backupImportFormData(),
    );
    verifiedImportState = { ...values, report };
    restoreImportBackupButton.disabled = false;
    importBackupStatusText.textContent = formatImportReport(report);
    importBackupStatusText.dataset.tone = "success";
    showToast("备份包验证与恢复演练通过", "success");
  } catch (error) {
    verifiedImportState = null;
    importBackupStatusText.textContent = friendlyErrorMessage(error);
    importBackupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(checkImportBackupButton, false);
  }
}

async function restoreLifevaultImport() {
  if (!importSelectionMatchesVerification()) {
    resetImportVerification("备份文件或凭据已变化，请重新执行恢复演练。");
    return;
  }
  const report = verifiedImportState.report;
  const confirmed = await askConfirmation({
    eyebrow: "仓库恢复",
    title: "用此备份替换当前仓库？",
    message: `${formatImportReport(report)}

系统会先把当前仓库自动保存到 data/recovery，再执行替换。恢复成功后会立即锁定，请使用该备份对应的凭据重新解锁。`,
    confirmLabel: "备份当前仓库并恢复",
    tone: "danger",
  });
  if (!confirmed) return;

  setButtonBusy(restoreImportBackupButton, true, "恢复中…");
  if (checkImportBackupButton) checkImportBackupButton.disabled = true;
  try {
    const method = importCredentialMethod.value;
    const restored = await apiForm(
      "/api/v1/backup/import",
      backupImportFormData({ includeConfirmation: true }),
    );
    setToken(null);
    currentProfile = null;
    currentProgress = null;
    contentStatus = {};
    monthContentStatus = {};
    yearContentStatus = {};
    closeDateDrawerNow();
    closeSettingsModalNow();
    statusBadge.textContent = "仓库已恢复，请重新解锁";
    showView("unlock");
    unlockForm.elements.method.value = method;
    unlockForm.elements.secret.value = "";
    showToast(`仓库恢复完成；恢复前备份：${restored.rescue_backup_filename}`, "success");
  } catch (error) {
    importBackupStatusText.textContent = friendlyErrorMessage(error);
    importBackupStatusText.dataset.tone = "error";
    showOperationError(error);
  } finally {
    setButtonBusy(restoreImportBackupButton, false);
    if (checkImportBackupButton) checkImportBackupButton.disabled = false;
  }
}

importBackupFile?.addEventListener("change", () => resetImportVerification("已选择备份文件，请输入凭据并执行恢复演练。"));
importCredentialMethod?.addEventListener("change", () => {
  if (importCredentialSecret) {
    importCredentialSecret.value = "";
    importCredentialSecret.placeholder = importCredentialMethod.value === "pin"
      ? "输入该备份对应的 PIN"
      : "输入该备份对应的恢复密钥";
  }
  resetImportVerification("验证方式已变化，请重新执行恢复演练。");
});
importCredentialSecret?.addEventListener("input", () => resetImportVerification("凭据已变化，请重新执行恢复演练。"));
checkImportBackupButton?.addEventListener("click", checkLifevaultImport);
restoreImportBackupButton?.addEventListener("click", restoreLifevaultImport);

profileSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentProfile || !profileSettingsEditing) return;
  const form = new FormData(profileSettingsForm);
  const displayName = String(form.get("display_name") || "").trim();
  const birthDate = String(form.get("birth_date") || "");
  const currentPin = String(form.get("current_pin") || "");
  const submit = profileSettingsForm.querySelector('button[type="submit"]');

  try {
    if (birthDate !== currentProfile.birth_date) {
      const impact = await api("/api/v1/profile/change-impact", {
        method: "POST",
        body: JSON.stringify({ birth_date: birthDate }),
      }, true);
      const hiddenMessage = impact.hidden_content_count
        ? `修改后有 ${impact.hidden_content_count} 条内容将暂时超出图谱范围，但不会被删除。`
        : "现有内容都仍在新的图谱范围内。";
      const confirmed = await askConfirmation({
        eyebrow: "出生日期调整",
        title: "重新计算人生图谱？",
        message: `出生日期将改为 ${birthDate}，人生进度、年龄和今天的位置会重新计算。\n${hiddenMessage}`,
        confirmLabel: "确认修改",
        tone: "warning",
      });
      if (!confirmed) return;
    }

    setButtonBusy(submit, true, "加密保存中…");
    const updated = await api("/api/v1/profile", {
      method: "PUT",
      body: JSON.stringify({
        display_name: displayName,
        birth_date: birthDate,
        current_pin: currentPin,
        revision: currentProfile.revision,
      }),
    }, true);
    currentProfile = updated;
    closeDateDrawerNow();
    closeSettingsModalNow();
    lifeGridSignature = "";
    fullPageGridSignature = "";
    await loadHome();
    requestAnimationFrame(() => {
      if (fullPageLifeOpen) scrollFullPageToDate(currentProgress.today);
    });
    showToast("个人档案已更新", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
});

recoveryCredentialForm?.elements.generate?.addEventListener("change", syncRecoveryCredentialMode);

recoveryCredentialForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(recoveryCredentialForm);
  const generate = Boolean(recoveryCredentialForm.elements.generate?.checked);
  const submit = recoveryCredentialForm.querySelector('button[type="submit"]');
  const confirmed = await askConfirmation({
    eyebrow: "安全设置",
    title: "更换恢复密钥？",
    message: "更换后原恢复密钥会立即失效。当前 PIN 与加密内容不变；此前导出的旧备份仍需要它们导出当时的恢复密钥。",
    confirmLabel: "更换恢复密钥",
    tone: "warning",
  });
  if (!confirmed) return;

  try {
    setButtonBusy(submit, true, "正在更换…");
    const result = await api("/api/v1/auth/change-recovery", {
      method: "POST",
      body: JSON.stringify({
        current_pin: form.get("current_pin"),
        generate,
        new_recovery_secret: generate ? null : form.get("new_recovery_secret"),
        confirm_new_recovery_secret: generate ? null : form.get("confirm_new_recovery_secret"),
      }),
    }, true);
    recoveryCredentialForm.reset();
    syncRecoveryCredentialMode();
    renderSecuritySummary(result.security);
    if (result.generated_recovery_secret) {
      showRecoverySecret(result.generated_recovery_secret, {
        context: "settings",
        title: "保存新的恢复密钥",
        description: "这份新恢复密钥只显示一次。请离线保存；原恢复密钥已经失效。",
      });
    } else {
      showToast("恢复密钥已更换，原恢复密钥已失效", "success");
    }
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
});

changePinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(changePinForm);
  const submit = changePinForm.querySelector('button[type="submit"]');
  const confirmed = await askConfirmation({
    eyebrow: "安全设置",
    title: "修改 PIN 并重新锁定？",
    message: "修改成功后，当前会话会立即失效，需要使用新 PIN 重新解锁。原有加密内容不会被重写。",
    confirmLabel: "修改 PIN",
    tone: "warning",
  });
  if (!confirmed) return;

  try {
    setButtonBusy(submit, true, "正在修改…");
    await api("/api/v1/auth/change-pin", {
      method: "POST",
      body: JSON.stringify({
        current_pin: form.get("current_pin"),
        new_pin: form.get("new_pin"),
        confirm_new_pin: form.get("confirm_new_pin"),
      }),
    }, true);
    setToken(null);
    currentProfile = null;
    currentProgress = null;
    closeSettingsModalNow();
    statusBadge.textContent = "PIN 已修改，请重新解锁";
    showView("unlock");
    unlockForm.elements.method.value = "pin";
    showToast("PIN 已修改，请使用新 PIN 解锁", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
});

resetPinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(resetPinForm);
  const submit = resetPinForm.querySelector('button[type="submit"]');
  try {
    setButtonBusy(submit, true, "正在重置…");
    await api("/api/v1/auth/reset-pin", {
      method: "POST",
      body: JSON.stringify({
        recovery_secret: form.get("recovery_secret"),
        new_pin: form.get("new_pin"),
        confirm_new_pin: form.get("confirm_new_pin"),
      }),
    });
    closeResetPinModal();
    unlockForm.elements.method.value = "pin";
    unlockForm.elements.secret.value = "";
    statusBadge.textContent = "PIN 已重置";
    showToast("PIN 已重置，请使用新 PIN 解锁", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
});

async function bootstrap() {
  showView("loading");
  try {
    const status = await api("/api/v1/system/status");
    if (!status.initialized) {
      statusBadge.textContent = "尚未初始化";
      showView("init");
      document.querySelector('#initForm [name="timezone"]').value = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      return;
    }
    if (!token()) {
      statusBadge.textContent = "仓库已锁定";
      showView("unlock");
      return;
    }
    await loadHome({ enterFullPage: true });
  } catch (error) {
    statusBadge.textContent = "连接失败";
    showToast(error.message);
  }
}

async function loadHome({ enterFullPage = false } = {}) {
  try {
    const [profile, progress] = await Promise.all([
      api("/api/v1/profile", {}, true),
      api("/api/v1/progress/life", {}, true),
    ]);
    const statusResult = await api(
      `/api/v1/dates/content-status?start=${encodeURIComponent(progress.birth_date)}&end=${encodeURIComponent(progress.target_date)}`,
      {},
      true,
    );

    currentProfile = profile;
    currentProgress = progress;
    contentStatus = statusResult.dates || {};
    monthContentStatus = statusResult.months || {};
    yearContentStatus = statusResult.years || {};
    contentStatusRevision += 1;
    if (memoryMapFilterIsActive()) {
      await loadMemoryTags(true);
      const knownTagIds = new Set(availableMemoryTags.map((tag) => tag.id));
      [...selectedMemoryMapTagIds].forEach((tagId) => {
        if (!knownTagIds.has(tagId)) selectedMemoryMapTagIds.delete(tagId);
      });
      if (memoryMapFilterIsActive()) await refreshMemoryMapTagMatches({ redraw: false });
      else setMemoryMapTagMatchData();
    }
    updateMemoryMapFilterEntryButtons();
    statusBadge.textContent = "加密仓库已解锁";
    document.getElementById("welcomeTitle").textContent = profile.display_name;
    document.getElementById("todayText").textContent = `${progress.today} · ${progress.timezone}`;
    document.getElementById("lifeSentence").textContent = `你已经走过 ${progress.life.elapsed_days.toLocaleString()} 天。`;
    document.getElementById("lifePercent").textContent = `${progress.life.percent.toFixed(2)}%`;
    document.querySelector(".life-percent").style.setProperty("--progress", `${Math.min(100, progress.life.percent)}%`);
    const lifeDayMetric = document.getElementById("lifeDay");
    const yearPercentMetric = document.getElementById("yearPercent");
    const monthPercentMetric = document.getElementById("monthPercent");

    lifeDayMetric.textContent = progress.life.elapsed_days.toLocaleString();
    yearPercentMetric.textContent = `${progress.year.percent.toFixed(1)}%`;
    monthPercentMetric.textContent = `${progress.month.percent.toFixed(1)}%`;
    const currentYear = progress.today.slice(0, 4);
    const currentMonth = Number(progress.today.slice(5, 7));
    document.getElementById("yearMetricNote").textContent = `途径${currentYear}，不赶时间，去吹吹风，年度结余${progress.year.remaining_days}天。`;
    document.getElementById("monthMetricNote").textContent = `${currentMonth}月小憩，看一看，走走停停，本月还有${progress.month.remaining_days}天。`;

    lifeDayMetric.style.setProperty("--metric-progress", `${Math.max(0, Math.min(100, progress.life.percent))}%`);
    yearPercentMetric.style.setProperty("--metric-progress", `${Math.max(0, Math.min(100, progress.year.percent))}%`);
    monthPercentMetric.style.setProperty("--metric-progress", `${Math.max(0, Math.min(100, progress.month.percent))}%`);
    initializeLifeNavigator(progress);
    showView("home");
    void refreshBackupHealthReminder();
    requestAnimationFrame(() => {
      renderLifeMapView(true);
      if (fullPageLifeOpen) {
        fullPageGridSignature = "";
        drawFullPageLifeGrid(true);
      } else if (enterFullPage) openFullPageLifeView();
    });
  } catch (error) {
    if (["SESSION_EXPIRED", "AUTH_REQUIRED", "VAULT_LOCKED"].includes(error.code)) {
      setToken(null);
      statusBadge.textContent = "仓库已锁定";
      showView("unlock");
    }
    showToast(error.message);
  }
}

async function refreshContentStatuses() {
  if (!currentProgress) return;
  const statusResult = await api(
    `/api/v1/dates/content-status?start=${encodeURIComponent(currentProgress.birth_date)}&end=${encodeURIComponent(currentProgress.target_date)}`,
    {},
    true,
  );
  contentStatus = statusResult.dates || {};
  monthContentStatus = statusResult.months || {};
  yearContentStatus = statusResult.years || {};
  contentStatusRevision += 1;
  if (memoryMapFilterIsActive()) await refreshMemoryMapTagMatches({ redraw: false });
  lifeGridSignature = "";
  fullPageGridSignature = "";
  renderLifeMapView(true);
  if (fullPageLifeOpen) drawFullPageLifeGrid(true);
}

const initForm = document.getElementById("initForm");
if (initForm) {
  initForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formNode = event.target;
    const form = new FormData(formNode);
    const submit = formNode.querySelector("button[type=submit]");
    if (submit) submit.disabled = true;
    try {
      const data = await api("/api/v1/auth/initialize", {
        method: "POST",
        body: JSON.stringify({
          display_name: form.get("display_name"),
          birth_date: form.get("birth_date"),
          target_age: Number(form.get("target_age")),
          timezone: form.get("timezone") || "UTC",
          pin: form.get("pin"),
          recovery_secret: form.get("recovery_secret") || null,
        }),
      });
      setToken(data.token);
      if (data.generated_recovery_secret) {
        showRecoverySecret(data.generated_recovery_secret, { context: "initialize" });
      } else {
        await loadHome({ enterFullPage: true });
      }
    } catch (error) {
      showToast(error.message);
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

const unlockForm = document.getElementById("unlockForm");
if (unlockForm) {
  unlockForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formNode = event.target;
    const form = new FormData(formNode);
    const submit = formNode.querySelector("button[type=submit]");
    if (submit) submit.disabled = true;
    try {
      const data = await api("/api/v1/auth/unlock", {
        method: "POST",
        body: JSON.stringify({ method: form.get("method"), secret: form.get("secret") }),
      });
      setToken(data.token);
      const secretInput = formNode.querySelector('[name="secret"]');
      if (secretInput) secretInput.value = "";
      await loadHome({ enterFullPage: true });
    } catch (error) {
      showToast(error.message);
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

lockButton.addEventListener("click", async () => {
  if (!(await confirmDiscardChanges())) return;
  try {
    await api("/api/v1/auth/lock", { method: "POST" });
  } catch (_) {
    // A local lock must still clear the browser session even if the request failed.
  }
  setToken(null);
  currentProfile = null;
  currentProgress = null;
  contentStatus = {};
  activeLifeMapView = "life";
  navigatorYear = null;
  navigatorMonth = null;
  navigatorDate = null;
  closeDateDrawerNow();
  statusBadge.textContent = "仓库已锁定";
  showView("unlock");
});

document.getElementById("refreshButton").addEventListener("click", () => loadHome());
document.getElementById("closeRecovery").addEventListener("click", async () => {
  recoveryModal.classList.add("hidden");
  recoveryValue.textContent = "";
  if (recoveryModalContext === "initialize") {
    await loadHome({ enterFullPage: true });
  } else {
    showToast("新的恢复密钥已生效", "success");
    recoveryCredentialForm?.elements.current_pin?.focus({ preventScroll: true });
  }
});
document.getElementById("copyRecovery").addEventListener("click", async () => {
  await navigator.clipboard.writeText(recoveryValue.textContent);
  showToast("恢复密钥已复制");
});

function parseIsoDate(value) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

function addUtcYears(date, years) {
  const y = date.getUTCFullYear() + years;
  const m = date.getUTCMonth();
  const d = date.getUTCDate();
  const result = new Date(Date.UTC(y, m, d));
  if (result.getUTCMonth() !== m) return new Date(Date.UTC(y, m + 1, 0));
  return result;
}

function daysBetween(a, b) {
  return Math.round((b - a) / 86400000);
}

function addUtcDays(date, days) {
  return new Date(date.getTime() + days * 86400000);
}

function formatUtc(date) {
  return date.toISOString().slice(0, 10);
}

function addUtcMonths(date, months) {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + months, 1));
}

function getLifeBounds() {
  if (!currentProgress) return null;
  return {
    birth: parseIsoDate(currentProgress.birth_date),
    target: parseIsoDate(currentProgress.target_date),
    today: parseIsoDate(currentProgress.today),
  };
}

function monthIntersectsLife(year, month) {
  const bounds = getLifeBounds();
  if (!bounds) return false;
  const start = new Date(Date.UTC(year, month - 1, 1));
  const end = new Date(Date.UTC(year, month, 1));
  return start < bounds.target && end > bounds.birth;
}

function firstAvailableMonth(year) {
  for (let month = 1; month <= 12; month += 1) {
    if (monthIntersectsLife(year, month)) return month;
  }
  return 1;
}

function lastAvailableMonth(year) {
  for (let month = 12; month >= 1; month -= 1) {
    if (monthIntersectsLife(year, month)) return month;
  }
  return 12;
}

function normalizeNavigatorMonth() {
  if (!currentProgress || navigatorYear === null) return;
  navigatorMonth = Math.min(12, Math.max(1, Number(navigatorMonth) || 1));
  if (monthIntersectsLife(navigatorYear, navigatorMonth)) return;

  const today = parseIsoDate(currentProgress.today);
  if (navigatorYear === today.getUTCFullYear() && monthIntersectsLife(navigatorYear, today.getUTCMonth() + 1)) {
    navigatorMonth = today.getUTCMonth() + 1;
    return;
  }

  const first = firstAvailableMonth(navigatorYear);
  const last = lastAvailableMonth(navigatorYear);
  navigatorMonth = navigatorMonth < first ? first : last;
}

function initializeLifeNavigator(progress, preferredIsoDate = null) {
  const birth = parseIsoDate(progress.birth_date);
  const target = parseIsoDate(progress.target_date);
  const today = parseIsoDate(progress.today);
  let preferred = preferredIsoDate ? parseIsoDate(preferredIsoDate) : null;

  if (!preferred || preferred < birth || preferred >= target) {
    preferred = today < birth ? birth : today >= target ? addUtcDays(target, -1) : today;
  }

  const startYear = birth.getUTCFullYear();
  const endYear = addUtcDays(target, -1).getUTCFullYear();
  if (navigatorYear === null || navigatorYear < startYear || navigatorYear > endYear) {
    navigatorYear = preferred.getUTCFullYear();
  }
  if (navigatorMonth === null) navigatorMonth = preferred.getUTCMonth() + 1;
  if (!navigatorDate) navigatorDate = formatUtc(preferred);
  normalizeNavigatorMonth();
}

function setNavigatorFromDate(isoDate) {
  const date = parseIsoDate(isoDate);
  navigatorYear = date.getUTCFullYear();
  navigatorMonth = date.getUTCMonth() + 1;
  navigatorDate = isoDate;
}

function contentStateForRange(startDate, endDate) {
  const start = formatUtc(startDate);
  const end = formatUtc(endDate);
  const aggregate = { has_event: false, has_memory: false, has_plan: false };
  for (const [dateKey, state] of Object.entries(contentStatus)) {
    if (dateKey < start || dateKey >= end) continue;
    aggregate.has_event ||= Boolean(state.has_event);
    aggregate.has_memory ||= Boolean(state.has_memory);
    aggregate.has_plan ||= Boolean(state.has_plan);
    if (aggregate.has_event && aggregate.has_memory && aggregate.has_plan) break;
  }
  return aggregate;
}

function contentStateLabel(state) {
  const labels = [];
  if (state.has_event) labels.push("有事件");
  if (state.has_memory) labels.push("有记忆");
  if (state.has_plan) labels.push("有计划");
  return labels.join("、");
}

function hierarchyTimeStateLabel(startDate, endDate) {
  const bounds = getLifeBounds();
  if (!bounds) return "";
  if (endDate <= bounds.today) return "已走过";
  if (startDate > bounds.today) return "未来";
  return "当前";
}

function hideHierarchyPointerTooltip() {
  if (!hierarchyPointerTooltip) return;
  hierarchyPointerTooltip.classList.add("hidden");
  hierarchyPointerTooltip.setAttribute("aria-hidden", "true");
}

function positionHierarchyPointerTooltip(event) {
  if (!hierarchyPointerTooltip) return;
  const edge = 12;
  const gap = 16;
  const rect = hierarchyPointerTooltip.getBoundingClientRect();
  let left = event.clientX + gap;
  let top = event.clientY + gap;

  if (left + rect.width > window.innerWidth - edge) {
    left = event.clientX - rect.width - gap;
  }
  if (top + rect.height > window.innerHeight - edge) {
    top = event.clientY - rect.height - gap;
  }

  hierarchyPointerTooltip.style.left = `${Math.max(edge, left)}px`;
  hierarchyPointerTooltip.style.top = `${Math.max(edge, top)}px`;
}

function showHierarchyPointerTooltip(event, text) {
  if (!hierarchyPointerTooltip || activeLifeMapView === "life") return;
  const parts = String(text).split(" · ");
  hierarchyPointerTitle.textContent = parts.shift() || "—";
  hierarchyPointerMeta.textContent = parts.join(" · ") || "点击打开对应时间范围详情";
  hierarchyPointerTooltip.classList.remove("hidden");
  hierarchyPointerTooltip.setAttribute("aria-hidden", "false");
  positionHierarchyPointerTooltip(event);
}
function appendHierarchyMarkers(cell, state) {
  cell.classList.toggle("has-event", Boolean(state.has_event));
  cell.classList.toggle("has-memory", Boolean(state.has_memory));
  cell.classList.toggle("has-plan", Boolean(state.has_plan));

  if (!state.has_event && !state.has_plan) return;
  const markers = document.createElement("span");
  markers.className = "hierarchy-markers";
  if (state.has_event) {
    const eventMarker = document.createElement("i");
    eventMarker.className = "hierarchy-event-marker";
    eventMarker.setAttribute("aria-hidden", "true");
    markers.appendChild(eventMarker);
  }
  if (state.has_plan) {
    const planMarker = document.createElement("i");
    planMarker.className = "hierarchy-plan-marker";
    planMarker.setAttribute("aria-hidden", "true");
    markers.appendChild(planMarker);
  }
  cell.appendChild(markers);
}

function classifyHierarchyCell(cell, startDate, endDate, selected = false) {
  const bounds = getLifeBounds();
  if (!bounds) return;
  if (endDate <= bounds.today) cell.classList.add("is-past");
  else if (startDate > bounds.today) cell.classList.add("is-future");
  else cell.classList.add("is-current");
  if (selected) cell.classList.add("is-selected");
}

function createHierarchyCell({ label, ariaLabel, hoverText, startDate, endDate, state, selected = false, disabled = false, tagFilterMatch = null, onClick }) {
  const cell = document.createElement("button");
  cell.type = "button";
  cell.className = "hierarchy-cell";
  cell.disabled = disabled;
  const stateText = contentStateLabel(state);
  const fullAriaLabel = `${ariaLabel}${stateText ? `，${stateText}` : ""}`;
  cell.setAttribute("aria-label", fullAriaLabel);

  const value = document.createElement("span");
  value.className = "hierarchy-cell-value";
  value.textContent = label;
  cell.appendChild(value);

  classifyHierarchyCell(cell, startDate, endDate, selected);
  appendHierarchyMarkers(cell, state);
  if (memoryMapFilterIsActive()) {
    cell.classList.toggle("is-tag-filter-match", tagFilterMatch === true);
    cell.classList.toggle("is-tag-filter-muted", tagFilterMatch !== true);
    if (tagFilterMatch === true) cell.setAttribute("data-tag-filter-match", "true");
  }
  if (!disabled) {
    const resolvedHoverText = hoverText || fullAriaLabel;
    cell.addEventListener("mouseenter", (event) => showHierarchyPointerTooltip(event, resolvedHoverText));
    cell.addEventListener("mousemove", (event) => positionHierarchyPointerTooltip(event));
    cell.addEventListener("mouseleave", hideHierarchyPointerTooltip);
    cell.addEventListener("blur", hideHierarchyPointerTooltip);
  }
  if (onClick) {
    cell.addEventListener("click", (event) => {
      hideHierarchyPointerTooltip();
      onClick(event);
    });
  }
  return cell;
}

function renderYearGrid() {
  const grid = document.getElementById("yearGrid");
  grid.replaceChildren();
  const bounds = getLifeBounds();
  if (!bounds) return;
  const startYear = bounds.birth.getUTCFullYear();
  const endYear = addUtcDays(bounds.target, -1).getUTCFullYear();

  for (let year = startYear; year <= endYear; year += 1) {
    const start = new Date(Date.UTC(year, 0, 1));
    const end = new Date(Date.UTC(year + 1, 0, 1));
    const rangeStart = start < bounds.birth ? bounds.birth : start;
    const rangeEnd = end > bounds.target ? bounds.target : end;
    if (rangeStart >= rangeEnd) continue;
    const state = yearContentStatus[String(year)] || { has_event: false, has_memory: false, has_plan: false };
    const cell = createHierarchyCell({
      label: String(year),
      ariaLabel: `${year}年`,
      hoverText: `${year}年 · ${hierarchyTimeStateLabel(rangeStart, rangeEnd)}${contentStateLabel(state) ? ` · ${contentStateLabel(state)}` : ""}`,
      startDate: rangeStart,
      endDate: rangeEnd,
      state,
      selected: year === navigatorYear,
      tagFilterMatch: memoryMapScopeMatches("year", String(year)),
      onClick: () => {
        navigatorYear = year;
        normalizeNavigatorMonth();
        renderYearGrid();
        openPeriodDrawer("year", String(year));
      },
    });
    cell.dataset.year = String(year);
    grid.appendChild(cell);
  }
}

function renderMonthGrid() {
  const grid = document.getElementById("monthGrid");
  grid.replaceChildren();
  const bounds = getLifeBounds();
  if (!bounds) return;

  let monthStart = new Date(Date.UTC(bounds.birth.getUTCFullYear(), bounds.birth.getUTCMonth(), 1));
  while (monthStart < bounds.target) {
    const monthEnd = addUtcMonths(monthStart, 1);
    const rangeStart = monthStart < bounds.birth ? bounds.birth : monthStart;
    const rangeEnd = monthEnd > bounds.target ? bounds.target : monthEnd;
    if (rangeStart < rangeEnd) {
      const year = monthStart.getUTCFullYear();
      const month = monthStart.getUTCMonth() + 1;
      const periodKey = `${year.toString().padStart(4, "0")}-${month.toString().padStart(2, "0")}`;
      const state = monthContentStatus[periodKey] || { has_event: false, has_memory: false, has_plan: false };
      const cell = createHierarchyCell({
        label: `${year}年${month}月`,
        ariaLabel: `${year}年${month}月`,
        hoverText: `${year}年${month}月 · ${hierarchyTimeStateLabel(rangeStart, rangeEnd)}${contentStateLabel(state) ? ` · ${contentStateLabel(state)}` : ""}`,
        startDate: rangeStart,
        endDate: rangeEnd,
        state,
        selected: year === navigatorYear && month === navigatorMonth,
        tagFilterMatch: memoryMapScopeMatches("month", periodKey),
        onClick: () => {
          navigatorYear = year;
          navigatorMonth = month;
          navigatorDate = formatUtc(rangeStart);
          renderMonthGrid();
          openPeriodDrawer("month", periodKey);
        },
      });
      cell.dataset.year = String(year);
      cell.dataset.month = String(month);
      grid.appendChild(cell);
    }
    monthStart = monthEnd;
  }
}

function renderLifeMapView(force = false) {
  if (!currentProgress) return;
  initializeLifeNavigator(currentProgress);

  lifeMapTabs.forEach((button) => {
    const active = button.dataset.lifeView === activeLifeMapView;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", active ? "true" : "false");
  });
  Object.entries(lifeMapViewNodes).forEach(([name, node]) => node.classList.toggle("hidden", name !== activeLifeMapView));
  hideHierarchyPointerTooltip();
  hideGridMagnifier();

  const bounds = getLifeBounds();
  const startYear = bounds.birth.getUTCFullYear();
  const endYear = addUtcDays(bounds.target, -1).getUTCFullYear();

  if (activeLifeMapView === "life") {
    lifeMapViewTitle.textContent = "太阳每天都是新的";
    const focusText = navigatorYear && navigatorMonth ? ` 当前定位：${navigatorYear}年${navigatorMonth}月。` : "";
    lifeMapViewSubtitle.textContent = `完整人生日期格保持不变，用于观察生命进度与内容分布。${focusText}`;
    drawLifeGrid(currentProgress, force);
    return;
  }

  if (activeLifeMapView === "year") {
    lifeMapViewTitle.textContent = "年视图";
    lifeMapViewSubtitle.textContent = `${startYear}—${endYear} 年全部显示，包含过去、当前与未来；点击年份在右侧展开年度内容和 12 个月。`;
    renderYearGrid();
    return;
  }

  lifeMapViewTitle.textContent = "月视图";
  lifeMapViewSubtitle.textContent = "整个目标人生范围内的所有月份同时显示，包含过去与未来；点击月份在右侧展开整月内容和月内日期。";
  renderMonthGrid();
}

function switchLifeMapView(view) {
  if (!lifeMapViewNodes[view] || !currentProgress) return;
  activeLifeMapView = view;
  renderLifeMapView(true);
}

lifeMapTabs.forEach((button) => {
  button.addEventListener("click", () => switchLifeMapView(button.dataset.lifeView));
});

function hideFullPageDateTooltip() {
  fullPageDateTooltip.classList.add("hidden");
  fullPageDateTooltip.setAttribute("aria-hidden", "true");
}

function positionFullPageDateTooltip(event) {
  const edge = 12;
  const gap = 18;
  const rect = fullPageDateTooltip.getBoundingClientRect();
  let left = event.clientX + gap;
  let top = event.clientY + gap;

  if (left + rect.width > window.innerWidth - edge) left = event.clientX - rect.width - gap;
  if (top + rect.height > window.innerHeight - edge) top = event.clientY - rect.height - gap;

  fullPageDateTooltip.style.left = `${Math.max(edge, left)}px`;
  fullPageDateTooltip.style.top = `${Math.max(edge, top)}px`;
}

function fullPageContentLabel(isoDate) {
  const state = contentStatus[isoDate] || {};
  const labels = [];
  if (state.has_event) labels.push("有事件");
  if (state.has_memory) labels.push("有记忆");
  if (state.has_plan) labels.push("有计划");
  return labels;
}

function drawFullPageLifeGrid(force = false) {
  if (!currentProgress || !fullPageLifeOpen) return;
  const measuredWidth = Math.floor(fullPageLifeCanvasWrap.clientWidth || 0);
  const cssWidth = Math.max(320, measuredWidth || window.innerWidth);
  const birth = parseIsoDate(currentProgress.birth_date);
  const target = parseIsoDate(currentProgress.target_date);
  const today = parseIsoDate(currentProgress.today);
  const totalDays = daysBetween(birth, target);
  const padding = cssWidth < 620 ? 10 : 16;
  const gap = cssWidth < 620 ? 0.8 : 1;
  const preferredCellSize = cssWidth >= 1500 ? 14 : cssWidth >= 1100 ? 12 : cssWidth >= 760 ? 10 : 8;
  const columns = Math.max(24, Math.floor((cssWidth - padding * 2 + gap) / (preferredCellSize + gap)));
  const stride = (cssWidth - padding * 2 + gap) / columns;
  const cellSize = Math.max(5, stride - gap);
  const rows = Math.ceil(totalDays / columns);
  const cssHeight = Math.ceil(padding * 2 + rows * stride - gap);
  const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
  const signature = [cssWidth, cssHeight, dpr, currentProgress.birth_date, currentProgress.today, currentProgress.target_date, contentStatusRevision, memoryMapFilterRevision, selectedDate].join(":");

  if (!force && signature === fullPageGridSignature) return;
  fullPageGridSignature = signature;

  fullPageLifeCanvas.width = Math.round(cssWidth * dpr);
  fullPageLifeCanvas.height = Math.round(cssHeight * dpr);
  fullPageLifeCanvas.style.width = `${cssWidth}px`;
  fullPageLifeCanvas.style.height = `${cssHeight}px`;

  const ctx = fullPageLifeCanvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);
  ctx.fillStyle = "rgba(255,255,255,.34)";
  ctx.fillRect(0, 0, cssWidth, cssHeight);

  const past = "#315c4d";
  const future = "#dfddd5";
  const todayColor = "#c06b3e";
  const eventColor = "#f0b84a";
  const memoryPastColor = "#b9dfcf";
  const memoryFutureColor = "#477765";
  const planPastColor = "#a8bfd4";
  const planFutureColor = "#3f6fa5";

  for (let index = 0; index < totalDays; index += 1) {
    const row = Math.floor(index / columns);
    const column = index % columns;
    const x = padding + column * stride;
    const y = padding + row * stride;
    const date = addUtcDays(birth, index);
    const isoDate = formatUtc(date);
    const isToday = isoDate === currentProgress.today;
    const state = contentStatus[isoDate] || {};

    ctx.fillStyle = isToday ? todayColor : date < today ? past : future;
    ctx.fillRect(x, y, cellSize, cellSize);

    if (isoDate === selectedDate) {
      ctx.strokeStyle = "rgba(255,255,255,.98)";
      ctx.lineWidth = Math.max(1.2, cellSize * .16);
      ctx.strokeRect(x - 1, y - 1, cellSize + 2, cellSize + 2);
      ctx.strokeStyle = "#172d25";
      ctx.lineWidth = Math.max(.7, cellSize * .08);
      ctx.strokeRect(x, y, cellSize, cellSize);
    }

    if (state.has_memory) {
      const inset = Math.max(1, cellSize * .13);
      ctx.strokeStyle = date < today ? memoryPastColor : memoryFutureColor;
      ctx.lineWidth = Math.max(.7, cellSize * .08);
      ctx.strokeRect(x + inset, y + inset, Math.max(1, cellSize - inset * 2), Math.max(1, cellSize - inset * 2));
    }

    if (state.has_plan) {
      ctx.beginPath();
      ctx.arc(x + cellSize / 2, y + cellSize / 2, Math.max(1.4, cellSize * .28), 0, Math.PI * 2);
      ctx.strokeStyle = date < today ? planPastColor : planFutureColor;
      ctx.lineWidth = Math.max(.65, cellSize * .07);
      ctx.stroke();
    }

    if (state.has_event) {
      ctx.beginPath();
      ctx.arc(x + cellSize / 2, y + cellSize / 2, Math.max(1, cellSize * .13), 0, Math.PI * 2);
      ctx.fillStyle = eventColor;
      ctx.fill();
    }

    if (memoryMapFilterIsActive()) {
      const isTagMatch = memoryMapScopeMatches("day", isoDate);
      if (!isTagMatch) {
        ctx.fillStyle = "rgba(250,249,245,.66)";
        ctx.fillRect(x, y, cellSize, cellSize);
      } else {
        ctx.strokeStyle = "#7a5aa6";
        ctx.lineWidth = Math.max(1.1, cellSize * .14);
        ctx.strokeRect(x - .5, y - .5, cellSize + 1, cellSize + 1);
      }
    }
  }

  fullPageLifeCanvas._fullPageGrid = {
    birth,
    totalDays,
    columns,
    padding,
    gap,
    stride,
    cellSize,
    cssWidth,
    cssHeight,
    dpr,
  };
  fullPageLifeSummary.textContent = memoryMapFilterIsActive()
    ? `完整人生共 ${totalDays.toLocaleString()} 天；当前标签筛选命中 ${memoryMapTagMatches.dates.size} 个具体日期，未命中日期已弱化显示。`
    : `完整人生共 ${totalDays.toLocaleString()} 天，日期连续排列；悬停查看日期，点击打开右侧详情。`;
}

function resolveFullPageDateFromPointer(event) {
  const grid = fullPageLifeCanvas._fullPageGrid;
  if (!grid) return null;
  const rect = fullPageLifeCanvas.getBoundingClientRect();
  const x = (event.clientX - rect.left) * (grid.cssWidth / rect.width) - grid.padding;
  const y = (event.clientY - rect.top) * (grid.cssHeight / rect.height) - grid.padding;
  if (x < 0 || y < 0) return null;

  const column = Math.floor(x / grid.stride);
  const row = Math.floor(y / grid.stride);
  if (column < 0 || column >= grid.columns || row < 0) return null;
  const withinX = x - column * grid.stride;
  const withinY = y - row * grid.stride;
  if (withinX > grid.cellSize || withinY > grid.cellSize) return null;

  const index = row * grid.columns + column;
  if (index < 0 || index >= grid.totalDays) return null;
  const date = addUtcDays(grid.birth, index);
  return { index, date, isoDate: formatUtc(date) };
}

function showFullPageDateTooltip(event, resolved) {
  const stateLabel = resolved.isoDate === currentProgress.today
    ? "今天"
    : resolved.isoDate < currentProgress.today ? "已走过" : "未来";
  const labels = fullPageContentLabel(resolved.isoDate);
  fullPageDateTooltipTitle.textContent = formatHoverDate(resolved.isoDate);
  fullPageDateTooltipMeta.textContent = `人生第 ${(resolved.index + 1).toLocaleString()} 天 · ${stateLabel}${labels.length ? ` · ${labels.join(" · ")}` : ""}`;
  fullPageDateTooltip.classList.remove("hidden");
  fullPageDateTooltip.setAttribute("aria-hidden", "false");
  positionFullPageDateTooltip(event);
}

function scrollFullPageToDate(isoDate, behavior = "auto") {
  const grid = fullPageLifeCanvas._fullPageGrid;
  if (!grid) return;
  const date = parseIsoDate(isoDate);
  const index = daysBetween(grid.birth, date);
  if (index < 0 || index >= grid.totalDays) return;
  const row = Math.floor(index / grid.columns);
  const cellTop = grid.padding + row * grid.stride;
  const top = Math.max(0, cellTop - fullPageLifeCanvasWrap.clientHeight / 2 + grid.cellSize / 2);
  fullPageLifeCanvasWrap.scrollTo({ top, behavior });
}

function fullPageViewportAnchorDate() {
  const grid = fullPageLifeCanvas._fullPageGrid;
  if (!grid) return null;
  const centerY = fullPageLifeCanvasWrap.scrollTop + fullPageLifeCanvasWrap.clientHeight / 2;
  const row = Math.max(0, Math.floor((centerY - grid.padding) / grid.stride));
  const index = Math.min(grid.totalDays - 1, row * grid.columns + Math.floor(grid.columns / 2));
  return formatUtc(addUtcDays(grid.birth, index));
}

function openFullPageLifeView() {
  if (!currentProgress || fullPageLifeOpen) return;
  fullPageReturnFocus = views.home.contains(document.activeElement)
    ? document.activeElement
    : openFullPageViewButton;
  fullPageLifeOpen = true;
  fullPageLifeView.classList.remove("hidden");
  fullPageLifeView.setAttribute("aria-hidden", "false");
  document.documentElement.classList.add("full-page-life-open");
  document.body.classList.add("full-page-life-open");
  hideGridMagnifier();
  hideHierarchyPointerTooltip();
  requestAnimationFrame(() => {
    drawFullPageLifeGrid(true);
    scrollFullPageToDate(currentProgress.today);
    closeFullPageViewButton.focus({ preventScroll: true });
  });
}

function closeFullPageLifeViewNow() {
  if (!fullPageLifeOpen) return;
  fullPageLifeOpen = false;
  fullPageLifeView.classList.add("hidden");
  fullPageLifeView.setAttribute("aria-hidden", "true");
  document.documentElement.classList.remove("full-page-life-open");
  document.body.classList.remove("full-page-life-open");
  hideFullPageDateTooltip();
  if (fullPageReturnFocus?.focus) fullPageReturnFocus.focus({ preventScroll: true });
  fullPageReturnFocus = null;
}

async function requestCloseFullPageLifeView() {
  if (!fullPageLifeOpen) return;
  if (!dateDrawer.classList.contains("hidden")) {
    if (!(await confirmDiscardChanges())) return;
    closeDateDrawerNow();
  }
  closeFullPageLifeViewNow();
}

openFullPageViewButton.addEventListener("click", openFullPageLifeView);
closeFullPageViewButton.addEventListener("click", requestCloseFullPageLifeView);
fullPageLocateTodayButton.addEventListener("click", () => {
  drawFullPageLifeGrid();
  scrollFullPageToDate(currentProgress.today, "smooth");
});
fullPageLifeCanvas.addEventListener("mousemove", (event) => {
  const resolved = resolveFullPageDateFromPointer(event);
  if (!resolved) {
    hideFullPageDateTooltip();
    return;
  }
  showFullPageDateTooltip(event, resolved);
});
fullPageLifeCanvas.addEventListener("mouseleave", hideFullPageDateTooltip);
fullPageLifeCanvas.addEventListener("click", (event) => {
  const resolved = resolveFullPageDateFromPointer(event);
  if (!resolved) return;
  hideFullPageDateTooltip();
  setNavigatorFromDate(resolved.isoDate);
  selectedDate = resolved.isoDate;
  drawFullPageLifeGrid(true);
  openDateDrawer(resolved.isoDate);
});
fullPageLifeCanvasWrap.addEventListener("scroll", hideFullPageDateTooltip, { passive: true });

function drawLifeGrid(progress, force = false) {
  const canvas = document.getElementById("lifeCanvas");
  const wrap = canvas.parentElement;
  const measuredWidth = Math.floor(wrap.clientWidth || 0);
  const cssWidth = measuredWidth > 0 ? measuredWidth : 780;
  const cssHeight = 430;
  const dpr = window.devicePixelRatio || 1;
  const signature = [
    cssWidth,
    cssHeight,
    dpr,
    progress.birth_date,
    progress.today,
    progress.target_age,
    contentStatusRevision,
    memoryMapFilterRevision,
  ].join(":");

  if (!force && signature === lifeGridSignature) return;
  lifeGridSignature = signature;

  const previousScrollLeft = wrap.scrollLeft;
  const previousScrollTop = wrap.scrollTop;

  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;

  wrap.scrollLeft = previousScrollLeft;
  wrap.scrollTop = previousScrollTop;

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  const birth = parseIsoDate(progress.birth_date);
  const today = parseIsoDate(progress.today);
  const rows = progress.target_age;
  const left = 42;
  const top = 12;
  const gap = 0.65;
  const rowHeight = (cssHeight - top * 2) / rows;
  const cellWidth = (cssWidth - left - 10) / 366;
  const cellHeight = Math.max(1.3, rowHeight - gap);
  const past = "#315c4d";
  const future = "#dfddd5";
  const todayColor = "#c06b3e";
  const eventColor = "#f0b84a";
  const memoryPastColor = "#b9dfcf";
  const memoryFutureColor = "#477765";
  const planPastColor = "#a8bfd4";
  const planFutureColor = "#3f6fa5";

  const hitMap = [];
  for (let age = 0; age < rows; age += 1) {
    const start = addUtcYears(birth, age);
    const end = addUtcYears(birth, age + 1);
    const days = daysBetween(start, end);
    const y = top + age * rowHeight;
    if (age % 5 === 0) {
      ctx.fillStyle = "#74766d";
      ctx.font = "9px system-ui";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(`${age}岁`, left - 7, y + cellHeight / 2);
    }
    for (let day = 0; day < days; day += 1) {
      const current = addUtcDays(start, day);
      const dateKey = formatUtc(current);
      const x = left + day * cellWidth;
      const isToday = dateKey === progress.today;
      const cellDrawWidth = Math.max(0.8, cellWidth - 0.35);
      const dateState = contentStatus[dateKey];
      ctx.fillStyle = isToday ? todayColor : current < today ? past : future;
      ctx.fillRect(x, y, cellDrawWidth, cellHeight);

      if (current.getUTCFullYear() === navigatorYear && current.getUTCMonth() + 1 === navigatorMonth) {
        ctx.strokeStyle = "rgba(26,45,37,.72)";
        ctx.lineWidth = Math.max(0.45, Math.min(0.72, cellWidth * 0.22));
        ctx.strokeRect(x + 0.12, y + 0.12, Math.max(0.3, cellDrawWidth - 0.24), Math.max(0.3, cellHeight - 0.24));
      }

      if (dateState?.has_memory) {
        const inset = Math.min(0.32, cellDrawWidth * 0.14, cellHeight * 0.1);
        ctx.strokeStyle = current < today ? memoryPastColor : memoryFutureColor;
        ctx.lineWidth = Math.max(0.5, Math.min(0.78, cellWidth * 0.3));
        ctx.strokeRect(
          x + inset,
          y + inset,
          Math.max(0.25, cellDrawWidth - inset * 2),
          Math.max(0.25, cellHeight - inset * 2),
        );
      }

      if (dateState?.has_plan) {
        const ringRadius = Math.max(0.85, Math.min(1.75, cellWidth * 0.48, cellHeight * 0.43));
        ctx.beginPath();
        ctx.arc(x + cellDrawWidth / 2, y + cellHeight / 2, ringRadius, 0, Math.PI * 2);
        ctx.strokeStyle = current < today ? planPastColor : planFutureColor;
        ctx.lineWidth = Math.max(0.45, Math.min(0.72, cellWidth * 0.24));
        ctx.stroke();
      }

      if (dateState?.has_event) {
        const radius = Math.max(0.62, Math.min(1.22, cellWidth * 0.32, cellHeight * 0.31));
        ctx.beginPath();
        ctx.arc(x + cellDrawWidth / 2, y + cellHeight / 2, radius, 0, Math.PI * 2);
        ctx.fillStyle = eventColor;
        ctx.fill();
      }

      if (memoryMapFilterIsActive()) {
        const isTagMatch = memoryMapScopeMatches("day", dateKey);
        if (!isTagMatch) {
          ctx.fillStyle = "rgba(250,249,245,.66)";
          ctx.fillRect(x, y, cellDrawWidth, cellHeight);
        } else {
          ctx.strokeStyle = "#7a5aa6";
          ctx.lineWidth = Math.max(0.72, Math.min(1.08, cellWidth * .38));
          ctx.strokeRect(x - .08, y - .08, cellDrawWidth + .16, cellHeight + .16);
        }
      }
    }
    hitMap.push({ age, start, days, y, rowHeight });
  }
  canvas._lifeGrid = {
    left,
    top,
    cellWidth,
    cellHeight,
    cellDrawWidth: Math.max(0.8, cellWidth - 0.35),
    rowHeight,
    hitMap,
    cssWidth,
    cssHeight,
    dpr,
  };
}

function resolveLifeDateFromPointer(event) {
  const canvas = document.getElementById("lifeCanvas");
  if (!canvas._lifeGrid || !currentProgress) return null;

  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas._lifeGrid.cssWidth / rect.width;
  const scaleY = canvas._lifeGrid.cssHeight / rect.height;
  const canvasX = (event.clientX - rect.left) * scaleX;
  const canvasY = (event.clientY - rect.top) * scaleY;
  const { left, top, cellWidth, rowHeight, hitMap } = canvas._lifeGrid;
  const age = Math.floor((canvasY - top) / rowHeight);
  const day = Math.floor((canvasX - left) / cellWidth);

  if (age < 0 || age >= hitMap.length || day < 0 || day >= hitMap[age].days) return null;
  const date = addUtcDays(hitMap[age].start, day);
  return { age, day, date, isoDate: formatUtc(date) };
}

const canvas = document.getElementById("lifeCanvas");
const canvasWrap = canvas.parentElement;
const gridMagnifier = document.getElementById("gridMagnifier");
const gridMagnifierCanvas = document.getElementById("gridMagnifierCanvas");
const gridMagnifierDate = document.getElementById("gridMagnifierDate");
const gridMagnifierMeta = document.getElementById("gridMagnifierMeta");

function formatHoverDate(isoDate) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "short",
    timeZone: "UTC",
  }).format(parseIsoDate(isoDate));
}

function hideGridMagnifier() {
  gridMagnifier.classList.add("hidden");
  gridMagnifier.setAttribute("aria-hidden", "true");
}

function positionGridMagnifier(event) {
  const edge = 12;
  const gap = 18;
  const rect = gridMagnifier.getBoundingClientRect();
  let left = event.clientX + gap;
  let top = event.clientY + gap;

  if (left + rect.width > window.innerWidth - edge) {
    left = event.clientX - rect.width - gap;
  }
  if (top + rect.height > window.innerHeight - edge) {
    top = event.clientY - rect.height - gap;
  }

  gridMagnifier.style.left = `${Math.max(edge, left)}px`;
  gridMagnifier.style.top = `${Math.max(edge, top)}px`;
}

function drawGridMagnifier(resolved) {
  const grid = canvas._lifeGrid;
  if (!grid) return;

  const lensWidth = 220;
  const lensHeight = 116;
  const zoom = 8;
  const dpr = window.devicePixelRatio || 1;
  const sourceWidth = lensWidth / zoom;
  const sourceHeight = lensHeight / zoom;
  const row = grid.hitMap[resolved.age];
  const cellX = grid.left + resolved.day * grid.cellWidth;
  const cellY = row.y;
  const cellCenterX = cellX + grid.cellDrawWidth / 2;
  const cellCenterY = cellY + grid.cellHeight / 2;
  const sourceX = Math.max(0, Math.min(grid.cssWidth - sourceWidth, cellCenterX - sourceWidth / 2));
  const sourceY = Math.max(0, Math.min(grid.cssHeight - sourceHeight, cellCenterY - sourceHeight / 2));

  gridMagnifierCanvas.width = Math.round(lensWidth * dpr);
  gridMagnifierCanvas.height = Math.round(lensHeight * dpr);
  gridMagnifierCanvas.style.width = `${lensWidth}px`;
  gridMagnifierCanvas.style.height = `${lensHeight}px`;

  const ctx = gridMagnifierCanvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, lensWidth, lensHeight);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(
    canvas,
    sourceX * grid.dpr,
    sourceY * grid.dpr,
    sourceWidth * grid.dpr,
    sourceHeight * grid.dpr,
    0,
    0,
    lensWidth,
    lensHeight,
  );

  const highlightX = (cellX - sourceX) * zoom;
  const highlightY = (cellY - sourceY) * zoom;
  const highlightWidth = Math.max(5, grid.cellDrawWidth * zoom);
  const highlightHeight = Math.max(5, grid.cellHeight * zoom);

  ctx.strokeStyle = "rgba(255,255,255,.98)";
  ctx.lineWidth = 4;
  ctx.strokeRect(highlightX - 1, highlightY - 1, highlightWidth + 2, highlightHeight + 2);
  ctx.strokeStyle = "#172d25";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(highlightX, highlightY, highlightWidth, highlightHeight);
}

function showGridMagnifier(event, resolved) {
  const stateLabel = resolved.isoDate === currentProgress.today
    ? "今天"
    : resolved.isoDate < currentProgress.today ? "已走过" : "未来";
  const dateState = contentStatus[resolved.isoDate] || {};
  const contentLabels = [];
  if (dateState.has_event) contentLabels.push("有事件");
  if (dateState.has_memory) contentLabels.push("有记忆");
  if (dateState.has_plan) contentLabels.push("有计划");
  const contentLabel = contentLabels.length ? ` · ${contentLabels.join(" · ")}` : "";

  gridMagnifierDate.textContent = formatHoverDate(resolved.isoDate);
  gridMagnifierMeta.textContent = `${resolved.age} 岁 · 本生命年第 ${resolved.day + 1} 天 · ${stateLabel}${contentLabel}`;
  drawGridMagnifier(resolved);
  gridMagnifier.classList.remove("hidden");
  gridMagnifier.setAttribute("aria-hidden", "false");
  positionGridMagnifier(event);
}

canvas.addEventListener("mousemove", (event) => {
  const resolved = resolveLifeDateFromPointer(event);
  if (!resolved) {
    hideGridMagnifier();
    return;
  }
  showGridMagnifier(event, resolved);
});
canvas.addEventListener("mouseleave", hideGridMagnifier);
canvas.addEventListener("click", (event) => {
  const resolved = resolveLifeDateFromPointer(event);
  if (resolved) {
    hideGridMagnifier();
    setNavigatorFromDate(resolved.isoDate);
    drawLifeGrid(currentProgress, true);
    openDateDrawer(resolved.isoDate);
  }
});
canvasWrap.addEventListener("scroll", hideGridMagnifier, { passive: true });
document.querySelectorAll(".hierarchy-stage-wrap").forEach((wrap) => {
  wrap.addEventListener("scroll", hideHierarchyPointerTooltip, { passive: true });
});
window.addEventListener("resize", () => {
  if (!currentProgress) return;
  hideHierarchyPointerTooltip();
  hideGridMagnifier();
  hideFullPageDateTooltip();
  const fullPageAnchor = fullPageLifeOpen ? fullPageViewportAnchorDate() : null;
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    renderLifeMapView(true);
    if (fullPageLifeOpen) {
      fullPageGridSignature = "";
      drawFullPageLifeGrid(true);
      if (fullPageAnchor) scrollFullPageToDate(fullPageAnchor);
    }
  }, 120);
});

const dateDrawer = document.getElementById("dateDrawer");
const dateDrawerBackdrop = document.getElementById("dateDrawerBackdrop");
const dateDrawerLoading = document.getElementById("dateDrawerLoading");
const dateDrawerContent = document.getElementById("dateDrawerContent");
const previousContentDateButton = document.getElementById("previousContentDate");
const nextContentDateButton = document.getElementById("nextContentDate");
const expandDateDrawerButton = document.getElementById("expandDateDrawer");
const trashDrawerContent = document.getElementById("trashDrawerContent");
const trashList = document.getElementById("trashList");
const trashSummary = document.getElementById("trashSummary");
const refreshTrashButton = document.getElementById("refreshTrashButton");
const emptyTrashButton = document.getElementById("emptyTrashButton");
const periodNavigator = document.getElementById("periodNavigator");
const periodDrawerBreadcrumb = document.getElementById("periodDrawerBreadcrumb");
const periodPreviousYear = document.getElementById("periodPreviousYear");
const periodNextYear = document.getElementById("periodNextYear");
const periodWeekdayHeader = document.getElementById("periodWeekdayHeader");
const periodChildGrid = document.getElementById("periodChildGrid");
const eventForm = document.getElementById("eventForm");
const toggleEventFormButton = document.getElementById("toggleEventForm");
const memoryForm = document.getElementById("memoryForm");
const toggleMemoryFormButton = document.getElementById("toggleMemoryForm");
const planForm = document.getElementById("planForm");
const togglePlanFormButton = document.getElementById("togglePlanForm");
const planAvailability = document.getElementById("planAvailability");
const eventSection = document.getElementById("eventSection");
const memorySection = document.getElementById("memorySection");
const planSection = document.getElementById("planSection");

const contentFormConfigurations = {
  event: {
    form: eventForm,
    toggleButton: toggleEventFormButton,
    section: eventSection,
    heading: document.getElementById("eventSectionHeading"),
    endpoint: "/api/v1/events",
    createLabel: "＋ 添加事件",
    openLabel: "收起表单",
    saveLabel: "保存事件",
    createMessage: "事件已加密保存",
    editMessage: "事件修改已加密保存",
    deleteMessage: "事件已移入回收站",
    itemLabel: "事件",
  },
  memory: {
    form: memoryForm,
    toggleButton: toggleMemoryFormButton,
    section: memorySection,
    heading: document.getElementById("memorySectionHeading"),
    endpoint: "/api/v1/memories",
    createLabel: "＋ 添加记忆",
    openLabel: "收起表单",
    saveLabel: "保存记忆",
    createMessage: "记忆已加密保存",
    editMessage: "记忆修改已加密保存",
    deleteMessage: "记忆已移入回收站",
    itemLabel: "记忆",
  },
  plan: {
    form: planForm,
    toggleButton: togglePlanFormButton,
    section: planSection,
    heading: document.getElementById("planSectionHeading"),
    endpoint: "/api/v1/plans",
    createLabel: "＋ 添加计划",
    openLabel: "收起表单",
    saveLabel: "保存计划",
    createMessage: "未来计划已加密保存",
    editMessage: "未来计划修改已加密保存",
    deleteMessage: "未来计划已移入回收站",
    itemLabel: "计划",
  },
};

const EMPTY_CONTENT_STATE = { has_event: false, has_memory: false, has_plan: false };

function contentFormValue(kind) {
  const form = contentFormConfigurations[kind].form;
  const content = kind === "memory"
    ? getMemoryRichEditorContent(memoryRichEditorIds.drawer)
    : form.querySelector('[name="content"]')?.value || "";
  return {
    title: form.querySelector('[name="title"]')?.value || "",
    content,
    ...(kind === "memory" ? { tagIds: [...selectedMemoryTagIds.drawer].sort() } : {}),
  };
}

function contentFormSnapshot(kind) {
  return JSON.stringify(contentFormValue(kind));
}

function captureContentFormSnapshot(kind) {
  const form = contentFormConfigurations[kind].form;
  form.dataset.initialSnapshot = contentFormSnapshot(kind);
}

function isContentFormDirty(kind) {
  const form = contentFormConfigurations[kind].form;
  if (form.classList.contains("hidden")) return false;
  return contentFormSnapshot(kind) !== (form.dataset.initialSnapshot || JSON.stringify({ title: "", content: "" }));
}

function hasUnsavedContentChanges() {
  return Object.keys(contentFormConfigurations).some((kind) => isContentFormDirty(kind));
}

async function confirmDiscardChanges() {
  if (!hasUnsavedContentChanges()) return true;
  return askConfirmation({
    eyebrow: "尚未保存",
    title: "放弃当前更改吗？",
    message: "表单中还有未保存的文字。继续后，这些更改将不会保留。",
    confirmLabel: "放弃更改",
    tone: "warning",
  });
}

let drawerReturnFocus = null;
let dateDrawerExpanded = false;

function setDateDrawerExpanded(expanded) {
  dateDrawerExpanded = Boolean(expanded);
  dateDrawer.classList.toggle("is-expanded", dateDrawerExpanded);
  expandDateDrawerButton?.setAttribute(
    "aria-label",
    dateDrawerExpanded ? "收起日期详情" : "展开日期详情"
  );
  if (expandDateDrawerButton) {
    expandDateDrawerButton.textContent = dateDrawerExpanded ? "↙" : "⛶";
  }
}

function toggleDateDrawerExpanded() {
  if (dateDrawer.classList.contains("hidden")) return;
  setDateDrawerExpanded(!dateDrawerExpanded);
}

function setDrawerOpen(open) {
  const wasOpen = !dateDrawer.classList.contains("hidden");
  if (open && !wasOpen) drawerReturnFocus = document.activeElement;
  dateDrawer.classList.toggle("hidden", !open);
  dateDrawerBackdrop.classList.toggle("hidden", !open);
  dateDrawer.setAttribute("aria-hidden", open ? "false" : "true");
  dateDrawerBackdrop.setAttribute("aria-hidden", open ? "false" : "true");
  document.body.classList.toggle("drawer-open", open);
  if (open && !wasOpen) {
    window.requestAnimationFrame(() => document.getElementById("closeDateDrawer")?.focus());
  }
  if (!open && wasOpen && drawerReturnFocus instanceof HTMLElement && document.contains(drawerReturnFocus)) {
    drawerReturnFocus.focus();
    drawerReturnFocus = null;
  }
}

function updateContentSectionVisibility(kind) {
  const config = contentFormConfigurations[kind];
  const itemCount = Number(config.section.dataset.itemCount || 0);
  const formOpen = !config.form.classList.contains("hidden");
  config.section.classList.toggle("hidden", itemCount === 0 && !formOpen);
  config.toggleButton.classList.toggle("is-active", formOpen);
  config.toggleButton.setAttribute("aria-expanded", formOpen ? "true" : "false");
}

function resetContentForm(kind, hide = true) {
  const config = contentFormConfigurations[kind];
  const submit = config.form.querySelector('button[type="submit"]');
  const cancel = config.form.querySelector('.event-form-actions button[type="button"]');
  if (kind === "memory") destroyMemoryRichEditor(memoryRichEditorIds.drawer);
  config.form.reset();
  if (kind === "memory") resetMemoryTagSelector("drawer");
  config.form.classList.toggle("hidden", hide);
  config.form.classList.remove("is-editing");
  delete config.form.dataset.editId;
  delete config.form.dataset.editRevision;
  delete config.form.dataset.initialSnapshot;
  config.toggleButton.textContent = kind === "plan" && config.toggleButton.disabled
    ? "该时间范围已过去"
    : config.createLabel;
  submit.textContent = config.saveLabel;
  cancel.textContent = "取消";
  updateContentSectionVisibility(kind);
}

function resetAllContentForms() {
  Object.keys(contentFormConfigurations).forEach((kind) => resetContentForm(kind, true));
}

function resetDrawerForms() {
  togglePlanFormButton.disabled = false;
  resetAllContentForms();
  planAvailability.classList.add("hidden");
}

function closeDateDrawerNow() {
  drawerRequestSequence += 1;
  selectedDate = null;
  selectedScope = null;
  selectedPeriodKey = null;
  setDateDrawerExpanded(false);
  previousContentDateButton.disabled = true;
  nextContentDateButton.disabled = true;
  dateDrawerContent.classList.add("hidden");
  trashDrawerContent.classList.add("hidden");
  dateDrawerLoading.classList.add("hidden");
  setDrawerOpen(false);
  resetDrawerForms();
}

async function requestCloseDateDrawer() {
  if (!(await confirmDiscardChanges())) return false;
  closeDateDrawerNow();
  return true;
}

function statusForPeriod(scope, periodKey) {
  if (scope === "year") return yearContentStatus[periodKey] || EMPTY_CONTENT_STATE;
  if (scope === "month") return monthContentStatus[periodKey] || EMPTY_CONTENT_STATE;
  return contentStatus[periodKey] || EMPTY_CONTENT_STATE;
}

function addPeriodBreadcrumb(label, scope = null, periodKey = null) {
  if (periodDrawerBreadcrumb.childElementCount > 0) {
    const separator = document.createElement("span");
    separator.textContent = "›";
    separator.className = "period-breadcrumb-separator";
    periodDrawerBreadcrumb.appendChild(separator);
  }
  if (scope && periodKey) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => openPeriodDrawer(scope, periodKey));
    periodDrawerBreadcrumb.appendChild(button);
  } else {
    const current = document.createElement("span");
    current.textContent = label;
    current.className = "is-current";
    periodDrawerBreadcrumb.appendChild(current);
  }
}

function renderPeriodBreadcrumb(scope, periodKey) {
  periodDrawerBreadcrumb.replaceChildren();
  const year = periodKey.slice(0, 4);
  if (scope === "year") {
    addPeriodBreadcrumb(`${year}年`);
    return;
  }
  const monthKey = periodKey.slice(0, 7);
  const month = Number(monthKey.slice(5, 7));
  addPeriodBreadcrumb(`${year}年`, "year", year);
  if (scope === "month") {
    addPeriodBreadcrumb(`${month}月`);
    return;
  }
  addPeriodBreadcrumb(`${month}月`, "month", monthKey);
  addPeriodBreadcrumb(`${Number(periodKey.slice(8, 10))}日`);
}

function shiftPeriodKeyByYears(scope, periodKey, yearDelta) {
  const nextYear = Number(periodKey.slice(0, 4)) + yearDelta;
  if (scope === "year") return String(nextYear);

  const month = Number(periodKey.slice(5, 7));
  const monthText = String(month).padStart(2, "0");
  if (scope === "month") return `${nextYear}-${monthText}`;

  const requestedDay = Number(periodKey.slice(8, 10));
  const lastDay = new Date(Date.UTC(nextYear, month, 0)).getUTCDate();
  return `${nextYear}-${monthText}-${String(Math.min(requestedDay, lastDay)).padStart(2, "0")}`;
}

function periodKeyIntersectsLife(scope, periodKey) {
  const bounds = getLifeBounds();
  if (!bounds) return false;

  if (scope === "day") {
    const value = parseIsoDate(periodKey);
    return value >= bounds.birth && value < bounds.target;
  }

  const year = Number(periodKey.slice(0, 4));
  if (scope === "year") {
    const start = new Date(Date.UTC(year, 0, 1));
    const end = new Date(Date.UTC(year + 1, 0, 1));
    return start < bounds.target && end > bounds.birth;
  }

  const month = Number(periodKey.slice(5, 7));
  const start = new Date(Date.UTC(year, month - 1, 1));
  const end = new Date(Date.UTC(year, month, 1));
  return start < bounds.target && end > bounds.birth;
}

function configurePeriodYearNavigation(scope, periodKey) {
  const previousKey = shiftPeriodKeyByYears(scope, periodKey, -1);
  const nextKey = shiftPeriodKeyByYears(scope, periodKey, 1);

  periodPreviousYear.disabled = !periodKeyIntersectsLife(scope, previousKey);
  periodNextYear.disabled = !periodKeyIntersectsLife(scope, nextKey);
  periodPreviousYear.dataset.periodKey = previousKey;
  periodNextYear.dataset.periodKey = nextKey;
  periodPreviousYear.title = `切换到 ${previousKey}`;
  periodNextYear.title = `切换到 ${nextKey}`;
}

periodPreviousYear.addEventListener("click", () => {
  if (!selectedScope || periodPreviousYear.disabled) return;
  openPeriodDrawer(selectedScope, periodPreviousYear.dataset.periodKey);
});

periodNextYear.addEventListener("click", () => {
  if (!selectedScope || periodNextYear.disabled) return;
  openPeriodDrawer(selectedScope, periodNextYear.dataset.periodKey);
});

function periodChildButton(child, selectedKey) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "period-child-cell";
  button.textContent = child.label;
  button.classList.toggle("is-selected", child.period_key === selectedKey);

  if (child.disabled) {
    button.disabled = true;
    button.classList.add("is-outside-life");
    button.title = `${child.period_key} · 不在当前人生图谱范围内`;
    return button;
  }

  const state = statusForPeriod(child.scope, child.period_key);
  const stateText = contentStateLabel(state);
  button.title = `${child.period_key}${stateText ? ` · ${stateText}` : ""}`;
  button.classList.add(child.time_state === "past" ? "is-past" : child.time_state === "future" ? "is-future" : "is-current");
  button.classList.toggle("has-event", state.has_event);
  button.classList.toggle("has-memory", state.has_memory);
  button.classList.toggle("has-plan", state.has_plan);
  button.addEventListener("click", () => openPeriodDrawer(child.scope, child.period_key));
  return button;
}

function dayChildrenForMonth(monthKey) {
  const [yearText, monthText] = monthKey.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const totalDays = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const bounds = getLifeBounds();
  const children = [];

  for (let day = 1; day <= totalDays; day += 1) {
    const key = `${yearText}-${monthText}-${String(day).padStart(2, "0")}`;
    const value = parseIsoDate(key);
    const disabled = !bounds || value < bounds.birth || value >= bounds.target;
    children.push({
      scope: "day",
      period_key: key,
      label: String(day),
      time_state: disabled ? "outside" : value < bounds.today ? "past" : value > bounds.today ? "future" : "today",
      disabled,
    });
  }
  return children;
}

function appendMonthCalendarCells(monthKey, selectedKey) {
  const [yearText, monthText] = monthKey.split("-");
  const firstDay = new Date(Date.UTC(Number(yearText), Number(monthText) - 1, 1));
  const mondayOffset = (firstDay.getUTCDay() + 6) % 7;
  const children = dayChildrenForMonth(monthKey);

  for (let index = 0; index < mondayOffset; index += 1) {
    const placeholder = document.createElement("span");
    placeholder.className = "period-day-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    periodChildGrid.appendChild(placeholder);
  }

  children.forEach((child) => periodChildGrid.appendChild(periodChildButton(child, selectedKey)));

  const trailing = (7 - ((mondayOffset + children.length) % 7)) % 7;
  for (let index = 0; index < trailing; index += 1) {
    const placeholder = document.createElement("span");
    placeholder.className = "period-day-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    periodChildGrid.appendChild(placeholder);
  }
}

function weekChildrenForDay(dayKey) {
  const selected = parseIsoDate(dayKey);
  const mondayOffset = (selected.getUTCDay() + 6) % 7;
  const weekStart = addUtcDays(selected, -mondayOffset);
  const bounds = getLifeBounds();
  const children = [];

  for (let index = 0; index < 7; index += 1) {
    const value = addUtcDays(weekStart, index);
    const key = formatUtc(value);
    const disabled = !bounds || value < bounds.birth || value >= bounds.target;
    children.push({
      scope: "day",
      period_key: key,
      label: String(value.getUTCDate()),
      time_state: disabled ? "outside" : value < bounds.today ? "past" : value > bounds.today ? "future" : "today",
      disabled,
    });
  }
  return children;
}

function appendSelectedWeekCells(dayKey, selectedKey) {
  weekChildrenForDay(dayKey).forEach((child) => {
    periodChildGrid.appendChild(periodChildButton(child, selectedKey));
  });
}

function renderPeriodNavigator(detail) {
  periodNavigator.classList.remove("hidden");
  periodNavigator.dataset.scope = detail.scope;
  renderPeriodBreadcrumb(detail.scope, detail.period_key);
  configurePeriodYearNavigation(detail.scope, detail.period_key);
  periodChildGrid.replaceChildren();

  const selectedKey = detail.period_key;
  if (detail.scope === "year") {
    periodWeekdayHeader.classList.add("hidden");
    periodWeekdayHeader.setAttribute("aria-hidden", "true");
    (detail.children || []).forEach((child) => periodChildGrid.appendChild(periodChildButton(child, selectedKey)));
    return;
  }

  periodWeekdayHeader.classList.remove("hidden");
  periodWeekdayHeader.setAttribute("aria-hidden", "false");

  if (detail.scope === "month") {
    const monthKey = detail.period_key.slice(0, 7);
    appendMonthCalendarCells(monthKey, selectedKey);
    return;
  }

  appendSelectedWeekCells(detail.period_key, selectedKey);
}

function periodContentStatusEntries(scope) {
  const source = scope === "year" ? yearContentStatus : (scope === "month" ? monthContentStatus : contentStatus);
  return Object.entries(source || {})
    .filter(([, value]) => value && (value.has_event || value.has_memory || value.has_plan))
    .map(([key]) => key)
    .sort();
}

function updateContentDateNavigation() {
  if (!selectedScope || !selectedPeriodKey) return;
  const entries = periodContentStatusEntries(selectedScope);
  const currentIndex = entries.indexOf(selectedPeriodKey);
  const previous = currentIndex > 0 ? entries[currentIndex - 1] : null;
  const next = currentIndex >= 0 && currentIndex < entries.length - 1 ? entries[currentIndex + 1] : null;
  previousContentDateButton.disabled = !previous;
  nextContentDateButton.disabled = !next;
  previousContentDateButton.title = previous ? `切换到 ${previous}` : "没有更早的有内容日期";
  nextContentDateButton.title = next ? `切换到 ${next}` : "没有更晚的有内容日期";
}

function drawerNavigationTarget(direction) {
  if (!selectedScope || !selectedPeriodKey) return null;
  const entries = periodContentStatusEntries(selectedScope);
  const index = entries.indexOf(selectedPeriodKey);
  const targetIndex = index + direction;
  return targetIndex >= 0 && targetIndex < entries.length ? entries[targetIndex] : null;
}

async function navigateContentDate(direction, options = {}) {
  const target = drawerNavigationTarget(direction);
  if (!target) return false;
  const opened = await openPeriodDrawer(selectedScope, target);
  if (opened === false) return false;
  if (["button", "keyboard"].includes(options.source)) {
    requestAnimationFrame(() => {
      dateDrawerContent.scrollTop = 0;
      dateDrawer.scrollTop = 0;
    });
  }
  return true;
}

function hasOpenContentForm() {
  return Object.values(contentFormConfigurations).some((config) => !config.form.classList.contains("hidden"));
}

function drawerKeyboardNavigationBlocked(event) {
  if (dateDrawer.classList.contains("hidden")) return true;
  if (dateDrawerContent.classList.contains("hidden")) return true;
  if (!selectedScope || !selectedPeriodKey) return true;
  if (!confirmModal.classList.contains("hidden")) return true;
  if (!settingsModal.classList.contains("hidden")) return true;
  if (!resetPinModal.classList.contains("hidden")) return true;
  if (isQuickMemoryOpen()) return true;
  if (isMemoryMapFilterOpen()) return true;
  if (openContentMenu) return true;
  if (hasUnsavedContentChanges() || hasOpenContentForm()) return true;
  const active = document.activeElement;
  const activeInteractive = active?.closest?.("input, textarea, select, button, a, [contenteditable='true'], .content-card-actions");
  const eventInteractive = event.target?.closest?.("input, textarea, select, button, a, [contenteditable='true'], .content-card-actions");
  return Boolean(activeInteractive || eventInteractive);
}

async function handleDrawerKeyboardNavigation(event) {
  if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return false;
  if (drawerKeyboardNavigationBlocked(event)) return false;
  const direction = event.key === "ArrowLeft" ? -1 : 1;
  if (!drawerNavigationTarget(direction)) return false;
  event.preventDefault();
  await navigateContentDate(direction, { source: "keyboard" });
  return true;
}


function drawerOpenShortcutBlocked(event) {
  if (!currentProgress) return true;
  if (views.home.classList.contains("hidden")) return true;
  if (!dateDrawer.classList.contains("hidden")) return true;
  if (!confirmModal.classList.contains("hidden")) return true;
  if (!settingsModal.classList.contains("hidden")) return true;
  if (!resetPinModal.classList.contains("hidden")) return true;
  if (!recoveryModal.classList.contains("hidden")) return true;
  if (isQuickMemoryOpen()) return true;
  if (openContentMenu) return true;
  if (hasUnsavedContentChanges() || hasOpenContentForm()) return true;

  const interactiveSelector = "input, textarea, select, button, a, [contenteditable='true'], [role='button'], [role='menuitem']";
  const active = document.activeElement;
  const activeInteractive = active?.closest?.(interactiveSelector);
  const eventInteractive = event.target?.closest?.(interactiveSelector);
  return Boolean(activeInteractive || eventInteractive);
}

function drawerShortcutTarget() {
  if (!currentProgress) return null;

  if (fullPageLifeOpen) {
    return {
      scope: "day",
      periodKey: fullPageViewportAnchorDate() || selectedDate || navigatorDate || currentProgress.today,
    };
  }

  if (activeLifeMapView === "year") {
    const today = parseIsoDate(currentProgress.today);
    const year = navigatorYear || today.getUTCFullYear();
    return { scope: "year", periodKey: String(year) };
  }

  if (activeLifeMapView === "month") {
    const today = parseIsoDate(currentProgress.today);
    const year = navigatorYear || today.getUTCFullYear();
    const month = navigatorMonth || today.getUTCMonth() + 1;
    return { scope: "month", periodKey: `${year}-${String(month).padStart(2, "0")}` };
  }

  return {
    scope: "day",
    periodKey: navigatorDate || selectedDate || currentProgress.today,
  };
}

async function handleDrawerOpenShortcut(event) {
  if (event.key !== "Enter" || !event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat) return false;
  if (drawerOpenShortcutBlocked(event)) return false;
  const target = drawerShortcutTarget();
  if (!target) return false;
  event.preventDefault();
  await openPeriodDrawer(target.scope, target.periodKey);
  return true;
}

async function openPeriodDrawer(scope, periodKey) {
  if (hasUnsavedContentChanges() && !(await confirmDiscardChanges())) return false;
  selectedScope = scope;
  selectedPeriodKey = periodKey;
  selectedDate = scope === "day" ? periodKey : null;
  if (scope === "year") navigatorYear = Number(periodKey);
  if (scope === "month" || scope === "day") {
    navigatorYear = Number(periodKey.slice(0, 4));
    navigatorMonth = Number(periodKey.slice(5, 7));
  }
  if (scope === "day") navigatorDate = periodKey;

  const requestSequence = ++drawerRequestSequence;
  setDrawerOpen(true);
  dateDrawerLoading.classList.remove("hidden");
  dateDrawerContent.classList.add("hidden");
  trashDrawerContent.classList.add("hidden");
  document.getElementById("dateDrawerTitle").textContent = periodKey;
  document.getElementById("dateDrawerMeta").textContent = "正在读取……";
  resetDrawerForms();

  try {
    const detail = await api(`/api/v1/periods/${encodeURIComponent(scope)}/${encodeURIComponent(periodKey)}`, {}, true);
    if (requestSequence !== drawerRequestSequence || selectedScope !== scope || selectedPeriodKey !== periodKey) return;
    renderPeriodDetail(detail);
    updateContentDateNavigation();
    dateDrawerLoading.classList.add("hidden");
    dateDrawerContent.classList.remove("hidden");
    renderLifeMapView(true);
    if (fullPageLifeOpen) drawFullPageLifeGrid(true);
    return true;
  } catch (error) {
    if (requestSequence !== drawerRequestSequence) return;
    closeDateDrawerNow();
    if (["SESSION_EXPIRED", "AUTH_REQUIRED", "VAULT_LOCKED"].includes(error.code)) {
      setToken(null);
      statusBadge.textContent = "仓库已锁定";
      showView("unlock");
    }
    showToast(error.message);
  }
}

function trashKindCopy(kind) {
  if (kind === "event") return { label: "事件", className: "event" };
  if (kind === "memory") return { label: "记忆", className: "memory" };
  return { label: "计划", className: "plan" };
}

function trashScopeLabel(item) {
  if (item.time_scope === "year") return `${item.period_key}年`;
  if (item.time_scope === "month") {
    const [year, month] = item.period_key.split("-");
    return `${year}年${Number(month)}月`;
  }
  const [year, month, day] = item.period_key.split("-");
  return `${year}年${Number(month)}月${Number(day)}日`;
}

function renderTrashList(data) {
  const items = data.items || [];
  const counts = data.counts || { event: 0, memory: 0, plan: 0 };
  trashSummary.textContent = items.length
    ? `共 ${items.length} 项 · 事件 ${counts.event || 0} · 记忆 ${counts.memory || 0} · 计划 ${counts.plan || 0}`
    : "回收站为空";
  emptyTrashButton.disabled = items.length === 0;
  trashList.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-copy trash-empty-copy";
    empty.textContent = "这里暂时没有已删除内容。";
    trashList.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const kindCopy = trashKindCopy(item.kind);
    const article = document.createElement("article");
    article.className = `trash-card trash-card-${kindCopy.className}`;

    const heading = document.createElement("div");
    heading.className = "trash-card-heading";
    const titleWrap = document.createElement("div");
    const badge = document.createElement("span");
    badge.className = `trash-kind-badge trash-kind-${kindCopy.className}`;
    badge.textContent = kindCopy.label;
    const title = document.createElement("h4");
    title.textContent = item.title;
    titleWrap.append(badge, title);

    const actions = document.createElement("div");
    actions.className = "trash-card-actions";
    const restoreButton = document.createElement("button");
    restoreButton.type = "button";
    restoreButton.className = "trash-restore-button";
    restoreButton.textContent = "恢复";
    restoreButton.addEventListener("click", () => restoreTrashItem(item, restoreButton));
    const purgeButton = document.createElement("button");
    purgeButton.type = "button";
    purgeButton.className = "trash-purge-button";
    purgeButton.textContent = "彻底删除";
    purgeButton.addEventListener("click", () => purgeTrashItem(item, purgeButton));
    actions.append(restoreButton, purgeButton);
    heading.append(titleWrap, actions);
    article.appendChild(heading);

    if (item.content) {
      const body = document.createElement("p");
      body.textContent = item.content;
      article.appendChild(body);
    }

    const meta = document.createElement("small");
    meta.textContent = `${trashScopeLabel(item)} · 删除于 ${formatDateTime(item.deleted_at)} · 版本 ${item.revision}`;
    article.appendChild(meta);
    trashList.appendChild(article);
  });
}

async function openTrashDrawer() {
  if (hasUnsavedContentChanges() && !(await confirmDiscardChanges())) return false;
  const requestSequence = ++drawerRequestSequence;
  selectedDate = null;
  selectedScope = null;
  selectedPeriodKey = null;
  resetDrawerForms();
  setDrawerOpen(true);
  dateDrawerContent.classList.add("hidden");
  trashDrawerContent.classList.add("hidden");
  dateDrawerLoading.classList.remove("hidden");
  document.getElementById("dateDrawerEyebrow").textContent = "统一回收站";
  document.getElementById("dateDrawerTitle").textContent = "回收站";
  document.getElementById("dateDrawerMeta").textContent = "正在读取已删除的加密内容……";

  try {
    const data = await api("/api/v1/trash", {}, true);
    if (requestSequence !== drawerRequestSequence) return;
    renderTrashList(data);
    document.getElementById("dateDrawerMeta").textContent = data.total
      ? "可恢复到原时间范围，也可永久清除"
      : "已删除内容会集中显示在这里";
    dateDrawerLoading.classList.add("hidden");
    trashDrawerContent.classList.remove("hidden");
  } catch (error) {
    if (requestSequence !== drawerRequestSequence) return;
    closeDateDrawerNow();
    showOperationError(error);
  }
}

async function restoreTrashItem(item, button) {
  setButtonBusy(button, true, "恢复中…");
  try {
    await api(`/api/v1/trash/${encodeURIComponent(item.kind)}/${encodeURIComponent(item.id)}/restore`, {
      method: "POST",
      body: JSON.stringify({ revision: item.revision }),
    }, true);
    await refreshContentStatuses();
    renderLifeMapView(true);
    showToast(`${trashKindCopy(item.kind).label}已恢复到${trashScopeLabel(item)}`, "success");
    await openTrashDrawer();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function purgeTrashItem(item, button) {
  const confirmed = await askConfirmation({
    eyebrow: "永久删除",
    title: `彻底删除${trashKindCopy(item.kind).label}吗？`,
    message: `“${item.title}”将从本机加密数据库中永久移除，之后无法恢复。`,
    confirmLabel: "彻底删除",
  });
  if (!confirmed) return;
  setButtonBusy(button, true, "删除中…");
  try {
    await api(`/api/v1/trash/${encodeURIComponent(item.kind)}/${encodeURIComponent(item.id)}`, {
      method: "DELETE",
      body: JSON.stringify({ revision: item.revision }),
    }, true);
    showToast("内容已彻底删除", "success");
    await openTrashDrawer();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function emptyTrash() {
  const confirmed = await askConfirmation({
    eyebrow: "永久删除",
    title: "清空整个回收站吗？",
    message: "回收站中的所有事件、记忆和计划都会被永久删除，且无法恢复。",
    confirmLabel: "清空回收站",
  });
  if (!confirmed) return;
  setButtonBusy(emptyTrashButton, true, "清空中…");
  try {
    const result = await api("/api/v1/trash", {
      method: "DELETE",
      body: JSON.stringify({ confirm: "EMPTY_TRASH" }),
    }, true);
    showToast(`回收站已清空，共彻底删除 ${result.total} 项内容`, "success");
    await openTrashDrawer();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(emptyTrashButton, false);
    emptyTrashButton.disabled = !trashList.querySelector(".trash-card");
  }
}

function openDateDrawer(isoDate) {
  return openPeriodDrawer("day", isoDate);
}

async function startContentEdit(kind, item) {
  if (hasUnsavedContentChanges() && !(await confirmDiscardChanges())) return;
  const config = contentFormConfigurations[kind];
  resetAllContentForms();
  config.form.dataset.editId = item.id;
  config.form.dataset.editRevision = String(item.revision);
  config.form.classList.remove("hidden");
  config.form.classList.add("is-editing");
  config.form.querySelector('[name="title"]').value = item.title || "";
  if (kind === "memory") {
    try {
      await loadMemoryTags();
    } catch (error) {
      showOperationError(error);
    }
    setMemoryTagSelection("drawer", item.tags || []);
    initMemoryRichEditor(memoryRichEditorIds.drawer, contentToEditableMemoryHtml(item));
  } else {
    config.form.querySelector('[name="content"]').value = item.content || "";
  }
  config.form.querySelector('button[type="submit"]').textContent = "保存修改";
  config.form.querySelector('.event-form-actions button[type="button"]').textContent = "取消编辑";
  config.toggleButton.textContent = "取消编辑";
  updateContentSectionVisibility(kind);
  requestAnimationFrame(() => captureContentFormSnapshot(kind));
  config.form.querySelector('[name="title"]').focus();
  config.form.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function deleteScopedContent(kind, item, button) {
  if (!selectedScope || !selectedPeriodKey) return;
  const config = contentFormConfigurations[kind];
  const confirmed = await askConfirmation({
    eyebrow: "移入回收站",
    title: `删除这条${config.itemLabel}吗？`,
    message: `“${item.title}”会移入回收站，之后仍可恢复到原时间范围。`,
    confirmLabel: "移入回收站",
    tone: "warning",
  });
  if (!confirmed) {
    closeOpenContentMenu({ restoreFocus: true });
    return;
  }
  closeOpenContentMenu();

  setButtonBusy(button, true, "删除中…");
  try {
    await api(`${config.endpoint}/${encodeURIComponent(item.id)}`, {
      method: "DELETE",
      body: JSON.stringify({ revision: item.revision }),
    }, true);

    if (config.form.dataset.editId === item.id) resetContentForm(kind, true);
    await refreshContentStatuses();
    renderLifeMapView(true);
    showToast(config.deleteMessage, "success");
    await openPeriodDrawer(selectedScope, selectedPeriodKey);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

function closeOpenContentMenu({ restoreFocus = false } = {}) {
  if (!openContentMenu) return;
  const trigger = openContentMenuTrigger;
  openContentMenu.classList.add("hidden");
  openContentMenu.setAttribute("aria-hidden", "true");
  trigger?.setAttribute("aria-expanded", "false");
  openContentMenu = null;
  openContentMenuTrigger = null;
  if (restoreFocus && trigger instanceof HTMLElement && document.contains(trigger)) {
    trigger.focus();
  }
}

function toggleContentMenu(menu, trigger) {
  const shouldOpen = menu.classList.contains("hidden");
  closeOpenContentMenu();
  if (!shouldOpen) return;
  menu.classList.remove("hidden");
  menu.setAttribute("aria-hidden", "false");
  trigger.setAttribute("aria-expanded", "true");
  openContentMenu = menu;
  openContentMenuTrigger = trigger;
}

const MEMORY_COLLAPSE_HEIGHT = 260;

function setMemoryCardCollapsed(article, button, collapsed) {
  article.classList.toggle("is-memory-collapsed", collapsed);
  button.textContent = collapsed ? "展开" : "折叠";
  button.setAttribute("aria-expanded", collapsed ? "false" : "true");
}

function prepareMemoryCardCollapse(article, body, button) {
  requestAnimationFrame(() => {
    const canCollapse = body.scrollHeight > MEMORY_COLLAPSE_HEIGHT + 24;
    article.classList.toggle("is-memory-collapsible", canCollapse);
    button.classList.toggle("hidden", !canCollapse);
    button.setAttribute("aria-hidden", canCollapse ? "false" : "true");
    if (!canCollapse) {
      article.classList.remove("is-memory-collapsed");
      button.textContent = "折叠";
      button.setAttribute("aria-expanded", "true");
      return;
    }
    setMemoryCardCollapsed(article, button, true);
  });
}

function renderContentList(elementId, items, _emptyText, kind, cardClass = "", _allowAction = true) {
  const list = document.getElementById(elementId);
  const config = contentFormConfigurations[kind];
  if (openContentMenu && list.contains(openContentMenu)) closeOpenContentMenu();
  list.replaceChildren();
  config.section.dataset.itemCount = String(items.length);
  config.heading.textContent = items.length ? `${config.itemLabel} · ${items.length}` : config.itemLabel;

  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = `content-card ${cardClass}`.trim();
    article.dataset.contentKind = kind;
    article.dataset.contentId = item.id;

    const header = document.createElement("div");
    header.className = "content-card-header";

    const title = document.createElement("h4");
    title.textContent = item.title;
    header.appendChild(title);

    const actions = document.createElement("div");
    actions.className = "content-card-actions";

    let collapseButton = null;
    if (kind === "memory" && item.content) {
      collapseButton = document.createElement("button");
      collapseButton.type = "button";
      collapseButton.className = "memory-collapse-button hidden";
      collapseButton.textContent = "折叠";
      collapseButton.setAttribute("aria-hidden", "true");
      collapseButton.setAttribute("aria-expanded", "true");
      collapseButton.setAttribute("aria-label", `折叠或展开记忆：${item.title}`);
    }

    const menuId = `content-menu-${kind}-${item.id}`;
    const moreButton = document.createElement("button");
    moreButton.type = "button";
    moreButton.className = "content-more-button";
    moreButton.textContent = "⋯";
    moreButton.setAttribute("aria-label", `更多操作：${item.title}`);
    moreButton.setAttribute("aria-haspopup", "menu");
    moreButton.setAttribute("aria-expanded", "false");
    moreButton.setAttribute("aria-controls", menuId);

    const menu = document.createElement("div");
    menu.id = menuId;
    menu.className = "content-more-menu hidden";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-hidden", "true");

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "content-menu-item content-edit-button";
    editButton.textContent = "编辑";
    editButton.setAttribute("role", "menuitem");
    editButton.setAttribute("aria-label", `编辑${item.title}`);
    editButton.addEventListener("click", () => {
      closeOpenContentMenu();
      startContentEdit(kind, item);
    });
    menu.appendChild(editButton);

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "content-menu-item content-delete-button";
    deleteButton.textContent = "删除";
    deleteButton.setAttribute("role", "menuitem");
    deleteButton.setAttribute("aria-label", `删除${item.title}`);
    deleteButton.addEventListener("click", () => deleteScopedContent(kind, item, deleteButton));
    menu.appendChild(deleteButton);

    moreButton.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleContentMenu(menu, moreButton);
    });
    menu.addEventListener("click", (event) => event.stopPropagation());

    if (collapseButton) actions.appendChild(collapseButton);
    actions.append(moreButton, menu);
    header.appendChild(actions);
    article.appendChild(header);

    let memoryBody = null;
    if (item.content) {
      if (kind === "memory" && item.content_format === "html") {
        const body = document.createElement("div");
        body.className = "memory-rich-content memory-content-body";
        body.innerHTML = sanitizeRichMemoryHtml(item.content);
        article.appendChild(body);
        memoryBody = body;
      } else {
        const body = document.createElement("p");
        body.className = kind === "memory" ? "content-plain-text memory-content-body" : "content-plain-text";
        body.textContent = item.content;
        article.appendChild(body);
        if (kind === "memory") memoryBody = body;
      }
    }

    if (collapseButton && memoryBody) {
      collapseButton.addEventListener("click", (event) => {
        event.stopPropagation();
        closeOpenContentMenu();
        setMemoryCardCollapsed(article, collapseButton, !article.classList.contains("is-memory-collapsed"));
      });
      prepareMemoryCardCollapse(article, memoryBody, collapseButton);
    }

    if (kind === "memory") appendMemoryTagBadges(article, item.tags || []);

    const meta = document.createElement("small");
    const metaParts = [`创建于 ${formatDateTime(item.created_at)}`];
    if (item.revision > 1) {
      metaParts.push(`更新于 ${formatDateTime(item.updated_at)}`);
      metaParts.push(`版本 ${item.revision}`);
    }
    meta.textContent = metaParts.join(" · ");
    article.appendChild(meta);
    list.appendChild(article);
  });

  updateContentSectionVisibility(kind);
}

function scopeCopy(scope) {
  if (scope === "year") return { noun: "这一年", eyebrow: "年度详情" };
  if (scope === "month") return { noun: "这个月", eyebrow: "月份详情" };
  return { noun: "这一天", eyebrow: "日期详情" };
}

function renderPeriodDetail(detail) {
  const copy = scopeCopy(detail.scope);
  document.getElementById("dateDrawerEyebrow").textContent = `${detail.time_state_label} · ${copy.eyebrow}`;
  if (detail.scope === "day") {
    document.getElementById("dateDrawerTitle").textContent = `${detail.date} · ${detail.weekday}`;
    document.getElementById("dateDrawerMeta").textContent = `${detail.age} 岁 · 人生第 ${detail.life_day_number.toLocaleString()} 天 · ${detail.timezone}`;
  } else {
    document.getElementById("dateDrawerTitle").textContent = detail.label;
    document.getElementById("dateDrawerMeta").textContent = `${detail.start_date} 至 ${detail.end_date} · 共 ${detail.days_in_period} 天 · ${detail.timezone}`;
  }

  renderPeriodNavigator(detail);
  renderContentList("eventList", detail.events, `${copy.noun}还没有事件。`, "event");
  renderContentList("memoryList", detail.memories, `${copy.noun}还没有个人记忆。`, "memory", "memory-card");
  renderContentList("planList", detail.plans, `${copy.noun}还没有未来计划。`, "plan", "plan-card", detail.plan_allowed);

  const planUnavailable = !detail.plan_allowed;
  togglePlanFormButton.disabled = planUnavailable;
  togglePlanFormButton.textContent = planUnavailable ? "计划不可新增" : "＋ 添加计划";
  planAvailability.textContent = detail.scope === "day"
    ? "过去日期不能新增未来计划，但此前保存的计划仍会显示。"
    : "已经结束的年份或月份不能新增未来计划，但此前保存的计划仍会显示。";
  togglePlanFormButton.title = planUnavailable ? planAvailability.textContent : "添加未来计划";
  planAvailability.classList.toggle("hidden", !planUnavailable);
  if (planUnavailable) {
    planForm.reset();
    planForm.classList.add("hidden");
  }
}

function formatDateTime(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

async function toggleContentForm(kind, forceOpen = null) {
  const config = contentFormConfigurations[kind];
  const isEditing = Boolean(config.form.dataset.editId);
  if (kind === "plan" && config.toggleButton.disabled && !isEditing) return;

  const shouldOpen = forceOpen === null ? config.form.classList.contains("hidden") : forceOpen;
  if (!shouldOpen) {
    if (isContentFormDirty(kind) && !(await confirmDiscardChanges())) return;
    resetContentForm(kind, true);
    return;
  }

  if (hasUnsavedContentChanges() && !(await confirmDiscardChanges())) return;
  resetAllContentForms();
  config.form.classList.remove("hidden");
  config.toggleButton.textContent = config.openLabel;
  if (kind === "memory") {
    resetMemoryTagSelector("drawer");
    try {
      await loadMemoryTags();
    } catch (error) {
      showOperationError(error);
    }
    initMemoryRichEditor(memoryRichEditorIds.drawer, "");
  }
  updateContentSectionVisibility(kind);
  requestAnimationFrame(() => captureContentFormSnapshot(kind));
  config.form.querySelector('[name="title"]').focus();
}

function toggleEventForm(forceOpen = null) {
  return toggleContentForm("event", forceOpen);
}

function toggleMemoryForm(forceOpen = null) {
  return toggleContentForm("memory", forceOpen);
}

function togglePlanForm(forceOpen = null) {
  return toggleContentForm("plan", forceOpen);
}

memoryMapFilterHomeButton?.addEventListener("click", openMemoryMapFilterModal);
memoryMapFilterFullPageButton?.addEventListener("click", openMemoryMapFilterModal);
closeMemoryMapFilterButton?.addEventListener("click", () => closeMemoryMapFilterModalNow());
clearMemoryMapFilterButton?.addEventListener("click", clearMemoryMapTagFilter);
memoryMapFilterModal?.addEventListener("click", (event) => {
  if (event.target === memoryMapFilterModal) closeMemoryMapFilterModalNow();
});
memoryMapFilterForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await applyMemoryMapTagFilter();
});

memorySearchHomeButton?.addEventListener("click", openMemorySearchModal);
memorySearchFullPageButton?.addEventListener("click", openMemorySearchModal);
closeMemorySearchButton?.addEventListener("click", () => closeMemorySearchModalNow());
resetMemorySearchButton?.addEventListener("click", resetMemorySearchFilters);
memorySearchModal?.addEventListener("click", (event) => {
  if (event.target === memorySearchModal) closeMemorySearchModalNow();
});
memorySearchForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runMemorySearch();
});

toggleEventFormButton.addEventListener("click", () => toggleEventForm());
document.getElementById("cancelEventForm").addEventListener("click", () => toggleContentForm("event", false));
toggleMemoryFormButton.addEventListener("click", () => toggleMemoryForm());
document.getElementById("cancelMemoryForm").addEventListener("click", () => toggleContentForm("memory", false));
document.getElementById("toggleMemoryTagPicker")?.addEventListener("click", () => toggleMemoryTagPicker("drawer"));
document.getElementById("createMemoryTag")?.addEventListener("click", () => createAndSelectMemoryTag("drawer"));
document.getElementById("memoryNewTagName")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createAndSelectMemoryTag("drawer");
});
togglePlanFormButton.addEventListener("click", () => togglePlanForm());
document.getElementById("cancelPlanForm").addEventListener("click", () => toggleContentForm("plan", false));
trashButton.addEventListener("click", openTrashDrawer);
refreshTrashButton.addEventListener("click", openTrashDrawer);
emptyTrashButton.addEventListener("click", emptyTrash);
document.getElementById("closeDateDrawer").addEventListener("click", requestCloseDateDrawer);
expandDateDrawerButton?.addEventListener("click", toggleDateDrawerExpanded);
previousContentDateButton?.addEventListener("click", () => navigateContentDate(-1, { source: "button" }));
nextContentDateButton?.addEventListener("click", () => navigateContentDate(1, { source: "button" }));
dateDrawerBackdrop.addEventListener("click", requestCloseDateDrawer);
document.addEventListener("click", (event) => {
  if (!openContentMenu) return;
  const actionContainer = openContentMenu.closest(".content-card-actions");
  if (!actionContainer?.contains(event.target)) closeOpenContentMenu();
});
document.addEventListener("keydown", async (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && !event.altKey && !event.shiftKey) {
    if (
      !views.home.classList.contains("hidden") && currentProfile &&
      !isQuickMemoryOpen() && !isMemorySearchOpen() && !isMemoryMapFilterOpen() &&
      confirmModal.classList.contains("hidden") &&
      settingsModal.classList.contains("hidden") &&
      resetPinModal.classList.contains("hidden") &&
      recoveryModal.classList.contains("hidden") &&
      dateDrawer.classList.contains("hidden")
    ) {
      event.preventDefault();
      await openMemorySearchModal();
      return;
    }
  }
  if (await handleDrawerOpenShortcut(event)) return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    if (await handleDrawerKeyboardNavigation(event)) return;
  }
  if (event.key !== "Escape") return;
  if (openContentMenu) {
    closeOpenContentMenu({ restoreFocus: true });
    return;
  }
  if (!confirmModal.classList.contains("hidden")) {
    closeConfirmation(false);
    return;
  }
  if (!resetPinModal.classList.contains("hidden")) {
    closeResetPinModal();
    return;
  }
  if (isMemoryMapFilterOpen()) {
    closeMemoryMapFilterModalNow();
    return;
  }
  if (isMemorySearchOpen()) {
    closeMemorySearchModalNow();
    return;
  }
  if (isQuickMemoryOpen()) {
    requestCloseQuickMemoryModal();
    return;
  }
  if (!settingsModal.classList.contains("hidden")) {
    requestCloseSettingsModal();
    return;
  }
  if (!dateDrawer.classList.contains("hidden")) {
    if (dateDrawerExpanded) {
      setDateDrawerExpanded(false);
    } else {
      requestCloseDateDrawer();
    }
    return;
  }
  if (fullPageLifeOpen) requestCloseFullPageLifeView();
});

window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedContentChanges() && !hasUnsavedSettingsChanges() && !isQuickMemoryDirty()) return;
  event.preventDefault();
  event.returnValue = "";
});

async function submitScopedContent(kind) {
  if (!selectedScope || !selectedPeriodKey) return;
  const config = contentFormConfigurations[kind];
  const formNode = config.form;
  const form = new FormData(formNode);
  const formValue = contentFormValue(kind);
  const submit = formNode.querySelector('button[type="submit"]');
  const editId = formNode.dataset.editId || null;
  const editRevision = Number(formNode.dataset.editRevision || 0);
  const idleSubmitLabel = submit.textContent;
  submit.disabled = true;
  submit.classList.add("is-busy");
  submit.setAttribute("aria-busy", "true");
  submit.textContent = editId ? "保存修改中…" : "加密保存中…";
  try {
    const requestBody = editId
      ? {
          title: formValue.title,
          content: formValue.content || "",
          ...(kind === "memory" ? { content_format: "html" } : {}),
          revision: editRevision,
        }
      : {
          time_scope: selectedScope,
          period_key: selectedPeriodKey,
          title: formValue.title,
          content: formValue.content || "",
          ...(kind === "memory" ? { content_format: "html" } : {}),
        };
    const savedItem = await api(editId ? `${config.endpoint}/${encodeURIComponent(editId)}` : config.endpoint, {
      method: editId ? "PUT" : "POST",
      body: JSON.stringify(requestBody),
    }, true);
    if (kind === "memory") {
      await syncMemoryTags(savedItem.id, selectedMemoryTagIds.drawer);
    }
    await refreshContentStatuses();
    renderLifeMapView(true);
    resetAllContentForms();
    showToast(editId ? config.editMessage : config.createMessage, "success");
    await openPeriodDrawer(selectedScope, selectedPeriodKey);
  } catch (error) {
    showOperationError(error);
  } finally {
    submit.disabled = false;
    submit.classList.remove("is-busy");
    submit.removeAttribute("aria-busy");
    if (!formNode.classList.contains("hidden")) submit.textContent = idleSubmitLabel;
  }
}

eventForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent("event");
});

memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent("memory");
});

planForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent("plan");
});

bootstrap();
