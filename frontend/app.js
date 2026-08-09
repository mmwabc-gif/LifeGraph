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
const frontendBuildVersion = "0.0.10";
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
let activeLifeMapView = "month";
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
const homeMonthCalendarTitle = document.getElementById("homeMonthCalendarTitle");
const homeMonthCalendarGrid = document.getElementById("homeMonthCalendarGrid");
const homeMonthCalendarPickerButton = document.getElementById("homeMonthCalendarPickerButton");
const homeMonthCalendarPicker = document.getElementById("homeMonthCalendarPicker");
const homeMonthCalendarYear = document.getElementById("homeMonthCalendarYear");
const homeMonthCalendarMonth = document.getElementById("homeMonthCalendarMonth");
const homeMonthCalendarToday = document.getElementById("homeMonthCalendarToday");
const homeMonthCalendarApply = document.getElementById("homeMonthCalendarApply");
let homeMonthCalendarMonthKey = null;
const quickMemoryHomeButton = document.getElementById("quickMemoryHomeButton");
const quickMemoryFullPageButton = document.getElementById("quickMemoryFullPageButton");
const contentCenterHomeButton = document.getElementById("contentCenterHomeButton");
const contentCenterFullPageButton = document.getElementById("contentCenterFullPageButton");
const materialCenterHomeButton = document.getElementById("materialCenterHomeButton");
const materialCenterFullPageButton = document.getElementById("materialCenterFullPageButton");
const materialCenterModal = document.getElementById("materialCenterModal");
const materialCenterForm = document.getElementById("materialCenterForm");
const materialCenterQuery = document.getElementById("materialCenterQuery");
const materialCenterDateFrom = document.getElementById("materialCenterDateFrom");
const materialCenterDateTo = document.getElementById("materialCenterDateTo");
const materialCenterSort = document.getElementById("materialCenterSort");
const materialCenterResults = document.getElementById("materialCenterResults");
const materialCenterSummary = document.getElementById("materialCenterSummary");
const materialCenterLimitHint = document.getElementById("materialCenterLimitHint");
const materialCenterTimelineViewButton = document.getElementById("materialCenterTimelineView");
const materialCenterListViewButton = document.getElementById("materialCenterListView");
const materialTimelineBackfillPanel = document.getElementById("materialTimelineBackfillPanel");
const materialTimelineBackfillStatus = document.getElementById("materialTimelineBackfillStatus");
const materialTimelineBackfillProgress = document.getElementById("materialTimelineBackfillProgress");
const materialTimelineBackfillButton = document.getElementById("materialTimelineBackfillButton");
const importMaterialButton = document.getElementById("importMaterialButton");
const materialImportInput = document.getElementById("materialImportInput");
const largeMaterialUploadPanel = document.getElementById("largeMaterialUploadPanel");
const largeMaterialUploadSummary = document.getElementById("largeMaterialUploadSummary");
const largeMaterialUploadList = document.getElementById("largeMaterialUploadList");
const cleanupStaleLargeUploadsButton = document.getElementById("cleanupStaleLargeUploadsButton");
const reviewMaterialTimeButton = document.getElementById("reviewMaterialTimeButton");
const materialTimeCorrectionModal = document.getElementById("materialTimeCorrectionModal");
const closeMaterialTimeCorrectionButton = document.getElementById("closeMaterialTimeCorrection");
const cancelMaterialTimeCorrectionButton = document.getElementById("cancelMaterialTimeCorrection");
const materialTimeCorrectionForm = document.getElementById("materialTimeCorrectionForm");
const materialTimeCorrectionFilename = document.getElementById("materialTimeCorrectionFilename");
const materialTimeCorrectionCurrent = document.getElementById("materialTimeCorrectionCurrent");
const materialTimeCorrectionDate = document.getElementById("materialTimeCorrectionDate");
const materialTimeCorrectionTime = document.getElementById("materialTimeCorrectionTime");
const manageMaterialScanSourcesButton = document.getElementById("manageMaterialScanSourcesButton");
const materialAutoScanModal = document.getElementById("materialAutoScanModal");
const closeMaterialAutoScanButton = document.getElementById("closeMaterialAutoScan");
const materialScanSourceForm = document.getElementById("materialScanSourceForm");
const materialScanSourcePath = document.getElementById("materialScanSourcePath");
const materialScanSourceRecursive = document.getElementById("materialScanSourceRecursive");
const addMaterialScanSourceButton = document.getElementById("addMaterialScanSource");
const materialScannerStatus = document.getElementById("materialScannerStatus");
const startMaterialScannerButton = document.getElementById("startMaterialScanner");
const pauseMaterialScannerButton = document.getElementById("pauseMaterialScanner");
const materialScanSourceSummary = document.getElementById("materialScanSourceSummary");
const materialScanSourceList = document.getElementById("materialScanSourceList");
const scanMaterialDirectoryButton = document.getElementById("scanMaterialDirectoryButton");
const materialDirectoryInput = document.getElementById("materialDirectoryInput");
const materialDirectoryScanModal = document.getElementById("materialDirectoryScanModal");
const closeMaterialDirectoryScanButton = document.getElementById("closeMaterialDirectoryScan");
const cancelMaterialDirectoryScanButton = document.getElementById("cancelMaterialDirectoryScan");
const materialDirectoryScanSummary = document.getElementById("materialDirectoryScanSummary");
const materialDirectoryScanProgress = document.getElementById("materialDirectoryScanProgress");
const materialDirectorySelectAll = document.getElementById("materialDirectorySelectAll");
const materialDirectorySelectedCount = document.getElementById("materialDirectorySelectedCount");
const materialDirectoryScanList = document.getElementById("materialDirectoryScanList");
const importScannedMaterialsButton = document.getElementById("importScannedMaterials");
const closeMaterialCenterButton = document.getElementById("closeMaterialCenter");
const resetMaterialCenterButton = document.getElementById("resetMaterialCenter");
let materialCenterReturnFocus = null;
let materialCenterRequestSequence = 0;
let materialCenterDrawerResumeState = null;
let materialCenterViewMode = "timeline";
let materialCenterTimeStatus = "all";
let materialTimeCorrectionAttachment = null;
let materialTimeCorrectionReturnFocus = null;
let materialTimelineAxisAutoResolve = null;
let materialCenterLastData = null;
let materialCenterBrowseParams = null;
let materialCenterLoadingMore = false;
let materialCenterLoadObserver = null;
let materialThumbnailObserver = null;
let materialTimelineBackfillPollTimer = null;
let materialTimelineBackfillLastState = null;
let materialTimelineAxisYear = null;
let materialTimelineAxisMonth = null;
let materialTimelineAxisDay = null;
let materialTimelineYearWindowStart = null;
let materialTimelineAxisRequestSequence = 0;
let materialTimelineAxisLastData = null;
let materialTimelineDayLoadingMore = false;
const materialTimelineExpandedMinuteGroups = new Set();
const MATERIAL_TIMELINE_DAY_PAGE_SIZE = 100;
const MATERIAL_TIMELINE_MINUTE_GROUP_THRESHOLD = 4;
const MATERIAL_TIMELINE_YEAR_MIN_WIDTH = 72;
const MATERIAL_TIMELINE_YEAR_MIN_ITEMS = 7;
const MATERIAL_TIMELINE_YEAR_MAX_ITEMS = 21;
let materialDirectoryScanSequence = 0;
let materialDirectoryScanItems = [];
let materialDirectoryRootName = "";
let materialDirectoryScanReturnFocus = null;
let materialAutoScanReturnFocus = null;
let materialScannerPollTimer = null;
let materialScannerLastState = "idle";
let materialScanSources = [];
const LARGE_UPLOAD_STORAGE_KEY = "lifegraph.large-material-uploads.v1";
const MAX_LARGE_MATERIAL_BYTES = 2 * 1024 * 1024 * 1024 * 1024;
const LARGE_UPLOAD_MAX_RETRIES = 3;
const LARGE_UPLOAD_CONCURRENCY = 3;
const LARGE_UPLOAD_SPEED_WINDOW_MS = 8000;
const largeMaterialUploadTasks = new Map();
let largeMaterialUploadQueueRunning = false;
let largeMaterialUploadRestoreProfileId = null;
let largeMaterialUploadRenderTimer = null;
let largeUploadMaintenanceStatus = null;
const contentCenterModal = document.getElementById("contentCenterModal");
const contentCenterForm = document.getElementById("contentCenterForm");
const contentCenterQuery = document.getElementById("contentCenterQuery");
const contentCenterDateFrom = document.getElementById("contentCenterDateFrom");
const contentCenterDateTo = document.getElementById("contentCenterDateTo");
const contentCenterSort = document.getElementById("contentCenterSort");
const contentCenterTagOptions = document.getElementById("contentCenterTagOptions");
const contentCenterResults = document.getElementById("contentCenterResults");
const contentCenterSummary = document.getElementById("contentCenterSummary");
const contentCenterLimitHint = document.getElementById("contentCenterLimitHint");
const contentCenterBatchModeToggle = document.getElementById("contentCenterBatchModeToggle");
const closeContentCenterButton = document.getElementById("closeContentCenter");
const resetContentCenterButton = document.getElementById("resetContentCenter");
const contentCenterBatchToolbar = document.getElementById("contentCenterBatchToolbar");
const contentCenterSelectAll = document.getElementById("contentCenterSelectAll");
const contentCenterSelectedCount = document.getElementById("contentCenterSelectedCount");
const contentCenterBulkTagsButton = document.getElementById("contentCenterBulkTags");
const contentCenterClearSelectionButton = document.getElementById("contentCenterClearSelection");
const contentCenterBatchTagEditor = document.getElementById("contentCenterBatchTagEditor");
const contentCenterBatchTargetSummary = document.getElementById("contentCenterBatchTargetSummary");
const contentCenterBatchTagOptions = document.getElementById("contentCenterBatchTagOptions");
const contentCenterBatchNewTagName = document.getElementById("contentCenterBatchNewTagName");
const contentCenterApplyBatchTagsButton = document.getElementById("contentCenterApplyBatchTags");
const contentCenterCloseBatchTagsButton = document.getElementById("contentCenterCloseBatchTags");
let contentCenterReturnFocus = null;
let contentCenterRequestSequence = 0;
let contentCenterDrawerResumeState = null;
let activeContentCenterTagEditor = null;
let contentCenterCurrentItems = [];
let contentCenterBatchMode = false;
const selectedContentCenterTagIds = new Set();
const selectedContentCenterItems = new Map();
const selectedContentCenterBatchTagIds = new Set();
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
let memoryMapTagMatches = { dates: new Set(), months: new Set(), years: new Set(), contentCount: 0, counts: { event: 0, memory: 0, plan: 0 } };
const materialSection = document.getElementById("materialSection");
const materialSectionCount = document.getElementById("materialSectionCount");
let materialSectionToggle = document.getElementById("materialSectionToggle");
const materialSectionLoadMore = document.getElementById("materialSectionLoadMore");
const materialList = document.getElementById("materialList");
const MATERIAL_SECTION_COLLAPSED_LIMIT = 6;
const PERIOD_MATERIAL_PAGE_SIZE = 12;
let materialSectionExpanded = false;
let materialSectionTotal = 0;
let materialSectionItems = [];
let materialSectionNextOffset = null;
let materialSectionLoadingMore = false;
const attachmentPreviewModal = document.getElementById("attachmentPreviewModal");
const attachmentPreviewStage = attachmentPreviewModal?.querySelector(".attachment-preview-stage");
const attachmentPreviewTitle = document.getElementById("attachmentPreviewTitle");
const attachmentPreviewMeta = document.getElementById("attachmentPreviewMeta");
const attachmentPreviewImage = document.getElementById("attachmentPreviewImage");
const attachmentPreviewStatus = document.getElementById("attachmentPreviewStatus");
const attachmentPreviewCounter = document.getElementById("attachmentPreviewCounter");
const attachmentPreviewPrevious = document.getElementById("attachmentPreviewPrevious");
const attachmentPreviewNext = document.getElementById("attachmentPreviewNext");
const downloadAttachmentPreviewButton = document.getElementById("downloadAttachmentPreview");
const closeAttachmentPreviewButton = document.getElementById("closeAttachmentPreview");
const videoPlayerModal = document.getElementById("videoPlayerModal");
const videoPlayerTitle = document.getElementById("videoPlayerTitle");
const videoPlayerMeta = document.getElementById("videoPlayerMeta");
const videoPlayer = document.getElementById("videoPlayer");
const videoCompatAudio = document.getElementById("videoCompatAudio");
const videoPlayerStatus = document.getElementById("videoPlayerStatus");
const videoAudioCompatStatus = document.getElementById("videoAudioCompatStatus");
const videoAudioCompatAction = document.getElementById("videoAudioCompatAction");
const closeVideoPlayerButton = document.getElementById("closeVideoPlayer");
const downloadVideoPlayerButton = document.getElementById("downloadVideoPlayer");
let videoPlayerAttachment = null;
let videoPlayerReturnFocus = null;
let videoPlayerRequestSequence = 0;
let videoPlayerTicket = null;
let videoAudioCompatPollTimer = null;
let videoAudioCompatState = null;
let videoAudioCompatRateSample = null;
let attachmentPreviewItems = [];
let attachmentPreviewIndex = -1;
let attachmentPreviewReturnFocus = null;
let attachmentPreviewLastWheelAt = 0;
const attachmentObjectUrls = new Map();
const attachmentObjectUrlPromises = new Map();
const mediaPreviewObjectUrls = new Map();
const mediaPreviewObjectUrlPromises = new Map();

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
  event: new Set(),
  drawer: new Set(),
  plan: new Set(),
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
    closeAttachmentPreview({ restoreFocus: false });
    closeVideoPlayer({ restoreFocus: false });
    releaseAllAttachmentObjectUrls();
    closeDateDrawerNow();
    closeFullPageLifeViewNow();
    closeSettingsModalNow();
    closeMemoryMapFilterModalNow({ restoreFocus: false });
    closeMaterialCenterModalNow({ restoreFocus: false });
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
    INVALID_MATERIAL_RANGE: "资料开始日期不能晚于结束日期。",
    TAG_NAME_CONFLICT: "已经存在同名标签，请换一个名称。",
    ATTACHMENT_TOO_LARGE: "单个附件不能超过 50 MB。",
    ATTACHMENT_UPLOAD_FAILED: "附件上传失败。",
    ATTACHMENT_NOT_FOUND: "附件不存在，或已经被删除。",
    ATTACHMENT_TIMELINE_FALLBACK_FAILED: "无法从来源内容日期或附件添加时间确定资料归属日期。",
  };
  const preferServerDetail = new Set([
    "BACKUP_CHECK_FAILED",
    "BACKUP_EXPORT_FAILED",
    "AUTO_BACKUP_FAILED",
    "AUTO_BACKUP_VERIFY_FAILED",
    "BACKUP_IMPORT_CHECK_FAILED",
    "BACKUP_RESTORE_FAILED",
  ]);
  if (preferServerDetail.has(error?.code) && error?.message) return error.message;
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
  const ids = {
    quick: ["quickMemorySelectedTags", "quickMemoryTagPicker", "quickMemoryTagOptions", "toggleQuickMemoryTagPicker", "quickMemoryNewTagName", "createQuickMemoryTag"],
    event: ["eventSelectedTags", "eventTagPicker", "eventTagOptions", "toggleEventTagPicker", "eventNewTagName", null],
    drawer: ["memorySelectedTags", "memoryTagPicker", "memoryTagOptions", "toggleMemoryTagPicker", "memoryNewTagName", null],
    plan: ["planSelectedTags", "planTagPicker", "planTagOptions", "togglePlanTagPicker", "planNewTagName", null],
  }[mode];
  if (!ids) return {};
  return {
    selected: document.getElementById(ids[0]),
    picker: document.getElementById(ids[1]),
    options: document.getElementById(ids[2]),
    toggle: document.getElementById(ids[3]),
    input: document.getElementById(ids[4]),
    create: ids[5] ? document.getElementById(ids[5]) : null,
  };
}

function tagModeForKind(kind) {
  return kind === "memory" ? "drawer" : kind;
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

  const inlineCreateInput = elements.input?.classList.contains("memory-tag-inline-create-input")
    ? elements.input
    : null;
  elements.options.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("span");
    empty.className = "memory-tag-picker-empty";
    empty.textContent = "还没有标签";
    elements.options.appendChild(empty);
  } else {
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
  if (inlineCreateInput) elements.options.appendChild(inlineCreateInput);
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
    selectedMemoryTagIds.event,
    selectedMemoryTagIds.drawer,
    selectedMemoryTagIds.plan,
    selectedContentCenterTagIds,
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
  renderMemoryTagSelector("event");
  renderMemoryTagSelector("drawer");
  renderMemoryTagSelector("plan");
  renderContentCenterTagOptions();
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
  if (elements.input?.disabled) return;

  setButtonBusy(elements.create, true, "新建中…");
  if (elements.input) {
    elements.input.disabled = true;
    elements.input.setAttribute("aria-busy", "true");
  }
  try {
    await loadMemoryTags();
    const existing = availableMemoryTags.find((tag) => memoryTagNameKey(tag.name) === memoryTagNameKey(name));
    if (existing) {
      selectedMemoryTagIds[mode].add(existing.id);
      if (elements.input) elements.input.value = "";
      renderMemoryTagSelector(mode);
      showToast(`已选中标签 #${existing.name}`, "success");
      return;
    }

    const tag = await api("/api/v1/tags", {
      method: "POST",
      body: JSON.stringify({ name }),
    }, true);
    availableMemoryTags.push(tag);
    availableMemoryTags.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
    selectedMemoryTagIds[mode].add(tag.id);
    if (elements.input) elements.input.value = "";
    renderAllMemoryTagControls();
    showToast(`标签 #${tag.name} 已创建并选中`, "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(elements.create, false);
    if (elements.input) {
      elements.input.disabled = false;
      elements.input.removeAttribute("aria-busy");
      elements.input.focus({ preventScroll: true });
    }
  }
}

async function syncContentTags(kind, contentId, selectedIds) {
  const base = `/api/v1/content/${encodeURIComponent(kind)}/${encodeURIComponent(contentId)}/tags`;
  const currentTags = await api(base, {}, true);
  const currentIds = new Set((currentTags || []).map((tag) => tag.id));
  const desiredIds = new Set(selectedIds || []);
  const toAttach = [...desiredIds].filter((tagId) => !currentIds.has(tagId));
  const toDetach = [...currentIds].filter((tagId) => !desiredIds.has(tagId));

  for (const tagId of toAttach) {
    await api(`${base}/${encodeURIComponent(tagId)}`, { method: "POST" }, true);
  }
  for (const tagId of toDetach) {
    await api(`${base}/${encodeURIComponent(tagId)}`, { method: "DELETE" }, true);
  }
}

async function syncMemoryTags(memoryId, selectedIds) {
  return syncContentTags("memory", memoryId, selectedIds);
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



function isContentCenterOpen() {
  return Boolean(contentCenterModal && !contentCenterModal.classList.contains("hidden"));
}

function contentCenterKindLabel(kind) {
  return { event: "事件", memory: "记忆", plan: "计划" }[kind] || "内容";
}

function contentCenterScopeLabel(item) {
  const key = item.period_key || item.anchor_date || "—";
  if (item.time_scope === "year") return `${key} · 年度`;
  if (item.time_scope === "month") return `${key} · 月份`;
  return `${key} · 日期`;
}

function contentCenterSnippet(item) {
  const text = plainTextFromMemoryContent(item.content || "", item.content_format || "plain");
  if (!text) return "暂无正文";
  return text.length > 150 ? `${text.slice(0, 150)}…` : text;
}

function selectedContentCenterKinds() {
  if (!contentCenterForm) return [];
  return Array.from(contentCenterForm.querySelectorAll('input[name="kind"]:checked')).map((input) => input.value);
}

function renderContentCenterTagOptions() {
  if (!contentCenterTagOptions) return;
  contentCenterTagOptions.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("span");
    empty.className = "content-center-tag-empty";
    empty.textContent = "暂无标签，可先在任一内容编辑中创建。";
    contentCenterTagOptions.appendChild(empty);
    return;
  }
  availableMemoryTags.forEach((tag) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "content-center-tag-chip";
    const selected = selectedContentCenterTagIds.has(tag.id);
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.textContent = `#${tag.name}`;
    button.addEventListener("click", () => {
      if (selectedContentCenterTagIds.has(tag.id)) selectedContentCenterTagIds.delete(tag.id);
      else selectedContentCenterTagIds.add(tag.id);
      renderContentCenterTagOptions();
    });
    contentCenterTagOptions.appendChild(button);
  });
}

function contentCenterItemKey(item) {
  return `${item.kind}:${item.id}`;
}

function setContentCenterBatchMode(enabled, { clearSelection = true, focusToggle = false } = {}) {
  contentCenterBatchMode = Boolean(enabled);
  contentCenterModal?.classList.toggle("is-batch-mode", contentCenterBatchMode);
  contentCenterBatchToolbar?.classList.toggle("hidden", !contentCenterBatchMode);
  if (contentCenterBatchModeToggle) {
    contentCenterBatchModeToggle.textContent = contentCenterBatchMode ? "退出批量" : "批量整理";
    contentCenterBatchModeToggle.setAttribute("aria-pressed", contentCenterBatchMode ? "true" : "false");
  }
  if (!contentCenterBatchMode && clearSelection) {
    clearContentCenterBatchSelection();
  } else {
    updateContentCenterSelectionControls();
  }
  if (focusToggle) contentCenterBatchModeToggle?.focus();
}

function toggleContentCenterBatchMode() {
  setContentCenterBatchMode(!contentCenterBatchMode, { clearSelection: true, focusToggle: false });
}

function selectedContentCenterBatchOperation() {
  return document.querySelector('input[name="content_center_batch_operation"]:checked')?.value || "add";
}

function closeContentCenterBatchTagEditor({ restoreFocus = false } = {}) {
  if (!contentCenterBatchTagEditor) return;
  contentCenterBatchTagEditor.classList.add("hidden");
  selectedContentCenterBatchTagIds.clear();
  if (contentCenterBatchNewTagName) contentCenterBatchNewTagName.value = "";
  const addRadio = document.querySelector('input[name="content_center_batch_operation"][value="add"]');
  if (addRadio) addRadio.checked = true;
  if (restoreFocus && contentCenterBulkTagsButton && !contentCenterBulkTagsButton.disabled) {
    contentCenterBulkTagsButton.focus();
  }
}

function updateContentCenterSelectionControls() {
  const selectedCount = selectedContentCenterItems.size;
  const currentKeys = contentCenterCurrentItems.map(contentCenterItemKey);
  const selectedCurrentCount = currentKeys.filter((key) => selectedContentCenterItems.has(key)).length;
  if (contentCenterSelectedCount) contentCenterSelectedCount.textContent = `已选 ${selectedCount} 条`;
  if (contentCenterBulkTagsButton) contentCenterBulkTagsButton.disabled = selectedCount === 0;
  if (contentCenterClearSelectionButton) contentCenterClearSelectionButton.disabled = selectedCount === 0;
  if (contentCenterSelectAll) {
    contentCenterSelectAll.disabled = currentKeys.length === 0;
    contentCenterSelectAll.checked = currentKeys.length > 0 && selectedCurrentCount === currentKeys.length;
    contentCenterSelectAll.indeterminate = selectedCurrentCount > 0 && selectedCurrentCount < currentKeys.length;
  }
  if (contentCenterBatchTargetSummary) {
    contentCenterBatchTargetSummary.textContent = `已选 ${selectedCount} 条内容`;
  }
  document.querySelectorAll('[data-content-center-select-key]').forEach((checkbox) => {
    checkbox.checked = selectedContentCenterItems.has(checkbox.dataset.contentCenterSelectKey || "");
  });
  if (selectedCount === 0) closeContentCenterBatchTagEditor();
}

function setContentCenterItemSelected(item, selected) {
  const key = contentCenterItemKey(item);
  if (selected) selectedContentCenterItems.set(key, { kind: item.kind, id: item.id });
  else selectedContentCenterItems.delete(key);
  updateContentCenterSelectionControls();
}

function clearContentCenterBatchSelection() {
  selectedContentCenterItems.clear();
  closeContentCenterBatchTagEditor();
  updateContentCenterSelectionControls();
}

function renderContentCenterBatchTagOptions() {
  if (!contentCenterBatchTagOptions) return;
  contentCenterBatchTagOptions.replaceChildren();
  if (!availableMemoryTags.length) {
    const empty = document.createElement("span");
    empty.className = "content-center-batch-tag-empty";
    empty.textContent = "暂无标签，可直接输入新标签并按回车。";
    contentCenterBatchTagOptions.appendChild(empty);
  }
  availableMemoryTags.forEach((tag) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "content-center-batch-tag-chip";
    const selected = selectedContentCenterBatchTagIds.has(tag.id);
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.textContent = `#${tag.name}`;
    button.addEventListener("click", () => {
      if (selectedContentCenterBatchTagIds.has(tag.id)) selectedContentCenterBatchTagIds.delete(tag.id);
      else selectedContentCenterBatchTagIds.add(tag.id);
      renderContentCenterBatchTagOptions();
    });
    contentCenterBatchTagOptions.appendChild(button);
  });
  if (contentCenterBatchNewTagName) {
    const removing = selectedContentCenterBatchOperation() === "remove";
    contentCenterBatchNewTagName.classList.toggle("hidden", removing);
    if (!removing) contentCenterBatchTagOptions.appendChild(contentCenterBatchNewTagName);
  }
}

async function openContentCenterBatchTagEditor() {
  if (!selectedContentCenterItems.size || !contentCenterBatchTagEditor) return;
  closeContentCenterQuickTagEditor({ restoreFocus: false });
  try {
    await loadMemoryTags();
  } catch (error) {
    showOperationError(error);
    return;
  }
  selectedContentCenterBatchTagIds.clear();
  if (contentCenterBatchNewTagName) contentCenterBatchNewTagName.value = "";
  const addRadio = document.querySelector('input[name="content_center_batch_operation"][value="add"]');
  if (addRadio) addRadio.checked = true;
  renderContentCenterBatchTagOptions();
  updateContentCenterSelectionControls();
  contentCenterBatchTagEditor.classList.remove("hidden");
  requestAnimationFrame(() => contentCenterBatchTagOptions?.querySelector("button")?.focus());
}

async function createContentCenterBatchTag() {
  const name = contentCenterBatchNewTagName?.value.trim() || "";
  if (!name) {
    showToast("请输入标签名称。", "error");
    contentCenterBatchNewTagName?.focus();
    return;
  }
  const existing = availableMemoryTags.find(
    (tag) => memoryTagNameKey(tag.name) === memoryTagNameKey(name)
  );
  if (existing) {
    selectedContentCenterBatchTagIds.add(existing.id);
    contentCenterBatchNewTagName.value = "";
    renderContentCenterBatchTagOptions();
    contentCenterBatchNewTagName?.focus();
    showToast(`已选中标签 #${existing.name}`, "success");
    return;
  }
  const originalPlaceholder = contentCenterBatchNewTagName?.placeholder || "＋ 新标签";
  if (contentCenterBatchNewTagName) {
    contentCenterBatchNewTagName.disabled = true;
    contentCenterBatchNewTagName.placeholder = "新建中…";
  }
  try {
    const tag = await api("/api/v1/tags", {
      method: "POST",
      body: JSON.stringify({ name }),
    }, true);
    availableMemoryTags.push(tag);
    availableMemoryTags.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
    selectedContentCenterBatchTagIds.add(tag.id);
    contentCenterBatchNewTagName.value = "";
    renderAllMemoryTagControls();
    renderContentCenterTagOptions();
    renderContentCenterBatchTagOptions();
    showToast(`标签 #${tag.name} 已创建并选中`, "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    if (contentCenterBatchNewTagName) {
      contentCenterBatchNewTagName.disabled = false;
      contentCenterBatchNewTagName.placeholder = originalPlaceholder;
      contentCenterBatchNewTagName.focus();
    }
  }
}

async function applyContentCenterBatchTags() {
  if (!selectedContentCenterItems.size) {
    showToast("请先选择要整理的内容。", "error");
    return;
  }
  if (!selectedContentCenterBatchTagIds.size) {
    showToast("请至少选择一个标签。", "error");
    return;
  }
  const operation = selectedContentCenterBatchOperation();
  const items = [...selectedContentCenterItems.values()].map((item) => ({
    kind: item.kind,
    content_id: item.id,
  }));
  setButtonBusy(contentCenterApplyBatchTagsButton, true, operation === "add" ? "批量添加中…" : "批量移除中…");
  try {
    await api("/api/v1/content/bulk/tags", {
      method: "POST",
      body: JSON.stringify({
        operation,
        items,
        tag_ids: [...selectedContentCenterBatchTagIds],
      }),
    }, true);
    const affectedCount = items.length;
    closeContentCenterBatchTagEditor();
    selectedContentCenterItems.clear();
    await loadMemoryTags({ force: true });
    if (memoryMapFilterIsActive()) await refreshMemoryMapTagMatches();
    await runContentCenterBrowse();
    showToast(
      operation === "add"
        ? `已为 ${affectedCount} 条内容批量添加标签`
        : `已从 ${affectedCount} 条内容批量移除标签`,
      "success",
    );
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(contentCenterApplyBatchTagsButton, false);
  }
}

function closeContentCenterModalNow({ restoreFocus = true } = {}) {
  if (!isContentCenterOpen()) return;
  closeContentCenterQuickTagEditor({ restoreFocus: false });
  clearContentCenterBatchSelection();
  setContentCenterBatchMode(false, { clearSelection: false });
  contentCenterRequestSequence += 1;
  contentCenterDrawerResumeState = null;
  contentCenterModal.classList.add("hidden");
  contentCenterModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("content-center-open");
  if (restoreFocus && contentCenterReturnFocus instanceof HTMLElement && document.contains(contentCenterReturnFocus)) {
    contentCenterReturnFocus.focus();
  }
  contentCenterReturnFocus = null;
}

function suspendContentCenterForDrawer(trigger = null) {
  if (!isContentCenterOpen()) return false;
  closeContentCenterQuickTagEditor({ restoreFocus: false });
  closeContentCenterBatchTagEditor();
  contentCenterRequestSequence += 1;
  contentCenterDrawerResumeState = {
    scrollTop: contentCenterResults?.scrollTop || 0,
    trigger: trigger instanceof HTMLElement ? trigger : null,
  };
  contentCenterModal.classList.add("hidden");
  contentCenterModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("content-center-open");
  return true;
}

function resumeContentCenterAfterDrawer() {
  const resumeState = contentCenterDrawerResumeState;
  if (!resumeState || !contentCenterModal || !currentProfile) return false;
  contentCenterDrawerResumeState = null;
  contentCenterModal.classList.remove("hidden");
  contentCenterModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("content-center-open");
  requestAnimationFrame(() => {
    if (contentCenterResults) contentCenterResults.scrollTop = resumeState.scrollTop || 0;
    if (resumeState.trigger instanceof HTMLElement && document.contains(resumeState.trigger)) {
      resumeState.trigger.focus({ preventScroll: true });
    }
  });
  return true;
}

function resetContentCenterFilters({ refresh = true } = {}) {
  if (!contentCenterForm) return;
  clearContentCenterBatchSelection();
  contentCenterForm.querySelectorAll('input[name="kind"]').forEach((input) => { input.checked = true; });
  contentCenterQuery.value = "";
  contentCenterDateFrom.value = "";
  contentCenterDateTo.value = "";
  contentCenterSort.value = "date_desc";
  selectedContentCenterTagIds.clear();
  renderContentCenterTagOptions();
  if (refresh) runContentCenterBrowse();
}

async function openContentCenterModal() {
  if (!contentCenterModal || !currentProfile) return;
  contentCenterDrawerResumeState = null;
  clearContentCenterBatchSelection();
  setContentCenterBatchMode(false, { clearSelection: false });
  if (isMemorySearchOpen()) closeMemorySearchModalNow({ restoreFocus: false });
  if (isMemoryMapFilterOpen()) closeMemoryMapFilterModalNow({ restoreFocus: false });
  contentCenterReturnFocus = document.activeElement;
  contentCenterModal.classList.remove("hidden");
  contentCenterModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("content-center-open");
  try {
    await loadMemoryTags();
    renderContentCenterTagOptions();
  } catch (error) {
    showOperationError(error);
  }
  await runContentCenterBrowse();
}

function focusContentCenterTarget(kind, contentId) {
  requestAnimationFrame(() => {
    const selector = `[data-content-kind="${CSS.escape(kind)}"][data-content-id="${CSS.escape(contentId)}"]`;
    const card = document.querySelector(selector);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("search-target-flash");
    window.setTimeout(() => card.classList.remove("search-target-flash"), 1800);
  });
}

async function openContentCenterResult(item, trigger = null) {
  const suspended = suspendContentCenterForDrawer(trigger);
  const opened = await openPeriodDrawer(item.time_scope, item.period_key);
  if (opened !== true) {
    if (suspended) resumeContentCenterAfterDrawer();
    return;
  }
  focusContentCenterTarget(item.kind, item.id);
}

function closeContentCenterQuickTagEditor({ restoreFocus = true } = {}) {
  if (!activeContentCenterTagEditor) return;
  const { editor, trigger } = activeContentCenterTagEditor;
  editor?.remove();
  if (trigger) {
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus && document.contains(trigger)) trigger.focus();
  }
  activeContentCenterTagEditor = null;
}

function renderContentCenterReadonlyTags(container, tags = []) {
  if (!container) return;
  container.replaceChildren();
  container.classList.toggle("hidden", !tags.length);
  tags.forEach((tag) => {
    const badge = document.createElement("span");
    badge.textContent = `#${tag.name}`;
    container.appendChild(badge);
  });
}

async function openContentCenterQuickTagEditor(item, card, trigger, readonlyTags) {
  closeContentCenterBatchTagEditor();
  if (activeContentCenterTagEditor?.trigger === trigger) {
    closeContentCenterQuickTagEditor();
    return;
  }
  closeContentCenterQuickTagEditor({ restoreFocus: false });
  try {
    await loadMemoryTags();
  } catch (error) {
    showOperationError(error);
    return;
  }

  const draftIds = new Set((item.tags || []).map((tag) => tag.id));
  const originalIds = new Set(draftIds);
  const editor = document.createElement("section");
  editor.className = "content-center-quick-tag-editor";
  editor.setAttribute("aria-label", `整理${contentCenterKindLabel(item.kind)}标签`);

  const heading = document.createElement("div");
  heading.className = "content-center-quick-tag-heading";
  const headingText = document.createElement("strong");
  headingText.textContent = "快速调整标签";
  const headingActions = document.createElement("div");
  headingActions.className = "content-center-quick-tag-heading-actions";
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "ghost-button content-center-quick-tag-cancel";
  cancel.textContent = "取消";
  const save = document.createElement("button");
  save.type = "button";
  save.className = "primary-button content-center-quick-tag-save";
  save.textContent = "保存标签";
  save.disabled = true;
  headingActions.append(cancel, save);
  heading.append(headingText, headingActions);

  const options = document.createElement("div");
  options.className = "content-center-quick-tag-options";

  const input = document.createElement("input");
  input.type = "text";
  input.maxLength = 40;
  input.autocomplete = "off";
  input.className = "content-center-quick-tag-inline-input";
  input.placeholder = "＋ 新标签";
  input.setAttribute("aria-label", "新建标签，按回车创建并选中");

  editor.append(heading, options);

  const updateSaveState = () => {
    const unchanged = draftIds.size === originalIds.size && [...draftIds].every((id) => originalIds.has(id));
    save.disabled = unchanged;
  };

  const renderOptions = () => {
    options.replaceChildren();
    if (!availableMemoryTags.length) {
      const empty = document.createElement("span");
      empty.className = "content-center-quick-tag-empty";
      empty.textContent = "暂无标签，可直接输入新标签并按回车。";
      options.appendChild(empty);
    }
    availableMemoryTags.forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "content-center-quick-tag-chip";
      chip.classList.toggle("is-selected", draftIds.has(tag.id));
      chip.setAttribute("aria-pressed", draftIds.has(tag.id) ? "true" : "false");
      chip.textContent = `#${tag.name}`;
      chip.addEventListener("click", () => {
        if (draftIds.has(tag.id)) draftIds.delete(tag.id);
        else draftIds.add(tag.id);
        renderOptions();
        updateSaveState();
      });
      options.appendChild(chip);
    });
    options.appendChild(input);
  };

  const createAndSelectTag = async () => {
    const name = input.value.trim();
    if (!name) {
      showToast("请输入标签名称。", "error");
      input.focus();
      return;
    }
    const existing = availableMemoryTags.find(
      (tag) => memoryTagNameKey(tag.name) === memoryTagNameKey(name)
    );
    if (existing) {
      draftIds.add(existing.id);
      input.value = "";
      renderOptions();
      updateSaveState();
      input.focus();
      showToast(`已选中标签 #${existing.name}`, "success");
      return;
    }

    const originalPlaceholder = input.placeholder;
    input.disabled = true;
    input.placeholder = "新建中…";
    try {
      const tag = await api("/api/v1/tags", {
        method: "POST",
        body: JSON.stringify({ name }),
      }, true);
      availableMemoryTags.push(tag);
      availableMemoryTags.sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
      draftIds.add(tag.id);
      input.value = "";
      renderAllMemoryTagControls();
      renderOptions();
      updateSaveState();
      showToast(`标签 #${tag.name} 已创建并选中`, "success");
    } catch (error) {
      showOperationError(error);
    } finally {
      input.disabled = false;
      input.placeholder = originalPlaceholder;
      input.focus();
    }
  };
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      createAndSelectTag();
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeContentCenterQuickTagEditor();
    }
  });
  cancel.addEventListener("click", () => closeContentCenterQuickTagEditor());
  save.addEventListener("click", async () => {
    setButtonBusy(save, true, "保存中…");
    try {
      const savedTags = await api(
        `/api/v1/content/${encodeURIComponent(item.kind)}/${encodeURIComponent(item.id)}/tags`,
        {
          method: "PUT",
          body: JSON.stringify({ tag_ids: [...draftIds] }),
        },
        true,
      );
      item.tags = Array.isArray(savedTags) ? savedTags : [];
      renderContentCenterReadonlyTags(readonlyTags, item.tags);
      const stillMatchesCurrentFilter = [...selectedContentCenterTagIds].every((tagId) => draftIds.has(tagId));
      closeContentCenterQuickTagEditor({ restoreFocus: false });
      await loadMemoryTags({ force: true });
      if (memoryMapFilterIsActive()) await refreshMemoryMapTagMatches();
      showToast(`${contentCenterKindLabel(item.kind)}标签已更新`, "success");
      if (!stillMatchesCurrentFilter && isContentCenterOpen()) await runContentCenterBrowse();
      else if (document.contains(trigger)) trigger.focus();
    } catch (error) {
      showOperationError(error);
      setButtonBusy(save, false);
    }
  });

  card.appendChild(editor);
  activeContentCenterTagEditor = { editor, trigger };
  trigger.setAttribute("aria-expanded", "true");
  renderOptions();
  requestAnimationFrame(() => input.focus());
}

function renderContentCenterResults(data) {
  closeContentCenterQuickTagEditor({ restoreFocus: false });
  closeContentCenterBatchTagEditor();
  contentCenterResults.replaceChildren();
  const items = data?.items || [];
  contentCenterCurrentItems = items;
  const counts = data?.counts || {};
  const total = Number(data?.total || 0);
  contentCenterSummary.textContent = total
    ? `共 ${total} 条 · 事件 ${counts.event || 0} · 记忆 ${counts.memory || 0} · 计划 ${counts.plan || 0}`
    : "当前条件下没有内容";
  contentCenterLimitHint.classList.toggle("hidden", !data?.has_more);

  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "content-center-empty";
    empty.textContent = "可以清空关键词、减少标签条件、选择更多内容类型，或放宽日期范围。";
    contentCenterResults.appendChild(empty);
    updateContentCenterSelectionControls();
    return;
  }

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `content-center-result-card is-${item.kind}`;

    const top = document.createElement("div");
    top.className = "content-center-result-top";

    const titleLead = document.createElement("div");
    titleLead.className = "content-center-result-title-lead";
    const selectLabel = document.createElement("label");
    selectLabel.className = "content-center-result-select";
    const selectCheckbox = document.createElement("input");
    selectCheckbox.type = "checkbox";
    selectCheckbox.setAttribute("aria-label", `选择${item.title || contentCenterKindLabel(item.kind)}`);
    selectCheckbox.dataset.contentCenterSelectKey = contentCenterItemKey(item);
    selectCheckbox.checked = selectedContentCenterItems.has(contentCenterItemKey(item));
    selectCheckbox.addEventListener("change", () => setContentCenterItemSelected(item, selectCheckbox.checked));
    selectLabel.append(selectCheckbox);

    const titleButton = document.createElement("button");
    titleButton.type = "button";
    titleButton.className = "content-center-result-title-button";
    titleButton.addEventListener("click", () => openContentCenterResult(item, titleButton));
    const titleWrap = document.createElement("span");
    titleWrap.className = "content-center-result-title";
    const kind = document.createElement("span");
    kind.className = `content-center-kind-badge is-${item.kind}`;
    kind.textContent = contentCenterKindLabel(item.kind);
    const title = document.createElement("strong");
    title.textContent = item.title || `未命名${contentCenterKindLabel(item.kind)}`;
    titleWrap.append(kind, title);
    titleButton.append(titleWrap);
    titleLead.append(selectLabel, titleButton);

    const topActions = document.createElement("div");
    topActions.className = "content-center-result-top-actions";
    const tagButton = document.createElement("button");
    tagButton.type = "button";
    tagButton.className = "content-center-quick-tag-toggle";
    tagButton.textContent = "整理标签";
    tagButton.setAttribute("aria-expanded", "false");
    tagButton.addEventListener("click", () => {
      openContentCenterQuickTagEditor(item, card, tagButton, readonlyTags);
    });
    const scope = document.createElement("span");
    scope.className = "content-center-scope";
    scope.textContent = contentCenterScopeLabel(item);
    topActions.append(tagButton, scope);
    top.append(titleLead, topActions);

    const main = document.createElement("button");
    main.type = "button";
    main.className = "content-center-result-main";
    main.addEventListener("click", () => openContentCenterResult(item, main));
    const snippet = document.createElement("p");
    snippet.textContent = contentCenterSnippet(item);
    main.append(snippet);

    const readonlyTags = document.createElement("div");
    readonlyTags.className = "content-center-result-tags";
    renderContentCenterReadonlyTags(readonlyTags, item.tags || []);

    card.append(top, main, readonlyTags);
    contentCenterResults.appendChild(card);
  });
  updateContentCenterSelectionControls();
}

async function runContentCenterBrowse() {
  if (!contentCenterForm || !isContentCenterOpen()) return;
  clearContentCenterBatchSelection();
  const submit = contentCenterForm.querySelector('button[type="submit"]');
  const kinds = selectedContentCenterKinds();
  if (!kinds.length) {
    showToast("请至少选择一种内容类型", "error");
    return;
  }
  if (contentCenterDateFrom.value && contentCenterDateTo.value && contentCenterDateFrom.value > contentCenterDateTo.value) {
    showToast("开始日期不能晚于结束日期", "error");
    contentCenterDateFrom.focus();
    return;
  }

  const params = new URLSearchParams();
  const query = contentCenterQuery.value.trim();
  if (query) params.set("q", query);
  kinds.forEach((kind) => params.append("kind", kind));
  if (contentCenterDateFrom.value) params.set("date_from", contentCenterDateFrom.value);
  if (contentCenterDateTo.value) params.set("date_to", contentCenterDateTo.value);
  selectedContentCenterTagIds.forEach((tagId) => params.append("tag_id", tagId));
  params.set("sort", contentCenterSort.value || "date_desc");
  params.set("limit", "200");

  const requestSequence = ++contentCenterRequestSequence;
  setButtonBusy(submit, true, "整理中…");
  contentCenterSummary.textContent = "正在整理加密内容……";
  contentCenterResults.replaceChildren();
  contentCenterLimitHint.classList.add("hidden");
  try {
    const data = await api(`/api/v1/content/search?${params.toString()}`, {}, true);
    if (requestSequence !== contentCenterRequestSequence || !isContentCenterOpen()) return;
    renderContentCenterResults(data);
  } catch (error) {
    if (requestSequence !== contentCenterRequestSequence) return;
    showOperationError(error);
    contentCenterSummary.textContent = "内容整理失败，请调整条件后重试";
  } finally {
    setButtonBusy(submit, false);
  }
}


function isMaterialCenterOpen() {
  return Boolean(materialCenterModal && !materialCenterModal.classList.contains("hidden"));
}

function selectedMaterialCenterCategories() {
  if (!materialCenterForm) return [];
  return Array.from(materialCenterForm.querySelectorAll('input[name="material_category"]:checked')).map((input) => input.value);
}

function materialCenterCategoryLabel(category) {
  if (category === "image") return "图片";
  if (category === "video") return "视频";
  if (category === "document") return "文档";
  return "其他";
}

function stopMaterialTimelineBackfillPolling() {
  if (materialTimelineBackfillPollTimer) {
    window.clearTimeout(materialTimelineBackfillPollTimer);
    materialTimelineBackfillPollTimer = null;
  }
}

function scheduleMaterialTimelineBackfillPolling() {
  stopMaterialTimelineBackfillPolling();
  if (!isMaterialCenterOpen()) return;
  materialTimelineBackfillPollTimer = window.setTimeout(() => {
    refreshMaterialTimelineBackfillStatus({ silent: true });
  }, 1200);
}

function renderMaterialTimelineBackfillStatus(data) {
  if (!materialTimelineBackfillPanel || !materialTimelineBackfillStatus || !materialTimelineBackfillButton) return;
  const total = Number(data?.total || 0);
  const indexed = Number(data?.indexed || 0);
  const undated = Number(data?.undated || 0);
  const pending = Number(data?.pending || 0);
  const failed = Number(data?.failed_count || 0);
  const percent = Math.max(0, Math.min(100, Number(data?.progress_percent || 0)));
  const state = String(data?.state || "idle");
  const completed = indexed + undated;
  materialTimelineBackfillLastState = state;

  if (!total || (pending === 0 && state === "completed" && failed === 0)) {
    materialTimelineBackfillPanel.classList.add("hidden");
    stopMaterialTimelineBackfillPolling();
    return;
  }
  materialTimelineBackfillPanel.classList.remove("hidden");
  if (materialTimelineBackfillProgress) {
    materialTimelineBackfillProgress.value = percent;
    materialTimelineBackfillProgress.textContent = `${percent.toFixed(1)}%`;
  }

  const pieces = [`已整理 ${completed}/${total}`];
  if (undated) pieces.push(`待确认时间 ${undated}`);
  if (failed) pieces.push(`本轮失败 ${failed}`);
  if (data?.current_filename) pieces.push(`正在处理：${data.current_filename}`);
  if (state === "paused") pieces.push("已暂停，可继续");
  if (state === "cancelled") pieces.push("仓库锁定后已停止，可重新继续");
  if (state === "error" && data?.last_error) pieces.push(`最近错误：${data.last_error}`);
  materialTimelineBackfillStatus.textContent = pieces.join(" · ");

  if (state === "running") {
    materialTimelineBackfillButton.textContent = "暂停整理";
    materialTimelineBackfillButton.disabled = false;
    scheduleMaterialTimelineBackfillPolling();
  } else {
    materialTimelineBackfillButton.textContent = failed ? "重试未完成项" : (state === "paused" ? "继续整理" : "整理时间索引");
    materialTimelineBackfillButton.disabled = pending <= 0;
    stopMaterialTimelineBackfillPolling();
  }
}

async function refreshMaterialTimelineBackfillStatus({ silent = false } = {}) {
  if (!materialTimelineBackfillPanel || !currentProfile) return null;
  try {
    const data = await api("/api/v1/materials/timeline-backfill", {}, true);
    renderMaterialTimelineBackfillStatus(data);
    return data;
  } catch (error) {
    stopMaterialTimelineBackfillPolling();
    if (!silent) showOperationError(error);
    return null;
  }
}

async function toggleMaterialTimelineBackfill() {
  if (!materialTimelineBackfillButton) return;
  const running = materialTimelineBackfillLastState === "running";
  setButtonBusy(materialTimelineBackfillButton, true, running ? "暂停中…" : "启动中…");
  let data = null;
  try {
    const endpoint = running
      ? "/api/v1/materials/timeline-backfill/pause"
      : "/api/v1/materials/timeline-backfill/start";
    data = await api(endpoint, { method: "POST" }, true);
    if (running) showToast("资料时间索引整理已暂停", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(materialTimelineBackfillButton, false);
    if (data) renderMaterialTimelineBackfillStatus(data);
  }
}

function closeMaterialCenterModalNow({ restoreFocus = true } = {}) {
  if (isMaterialDirectoryScanOpen()) closeMaterialDirectoryScanModal({ restoreFocus: false });
  if (isMaterialAutoScanOpen()) closeMaterialAutoScanModal({ restoreFocus: false });
  if (materialTimeCorrectionModal && !materialTimeCorrectionModal.classList.contains("hidden")) closeMaterialTimeCorrectionModal({ restoreFocus: false });
  if (!isMaterialCenterOpen()) return;
  materialCenterRequestSequence += 1;
  resetMaterialCenterPaging();
  stopMaterialTimelineBackfillPolling();
  materialThumbnailObserver?.disconnect?.();
  materialCenterDrawerResumeState = null;
  materialCenterModal.classList.add("hidden");
  materialCenterModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("material-center-open");
  if (restoreFocus && materialCenterReturnFocus instanceof HTMLElement && document.contains(materialCenterReturnFocus)) {
    materialCenterReturnFocus.focus();
  }
  materialCenterReturnFocus = null;
}

function suspendMaterialCenterForDrawer(trigger = null) {
  if (!isMaterialCenterOpen()) return false;
  materialCenterRequestSequence += 1;
  materialCenterDrawerResumeState = {
    scrollTop: materialCenterResults?.scrollTop || 0,
    trigger: trigger instanceof HTMLElement ? trigger : null,
  };
  materialCenterModal.classList.add("hidden");
  materialCenterModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("material-center-open");
  return true;
}

function resumeMaterialCenterAfterDrawer() {
  const resumeState = materialCenterDrawerResumeState;
  if (!resumeState || !materialCenterModal || !currentProfile) return false;
  materialCenterDrawerResumeState = null;
  materialCenterModal.classList.remove("hidden");
  materialCenterModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("material-center-open");
  requestAnimationFrame(() => {
    if (materialCenterResults) materialCenterResults.scrollTop = resumeState.scrollTop || 0;
    if (resumeState.trigger instanceof HTMLElement && document.contains(resumeState.trigger)) {
      resumeState.trigger.focus({ preventScroll: true });
    }
  });
  return true;
}

function resetMaterialCenterFilters({ refresh = true } = {}) {
  if (!materialCenterForm) return;
  materialCenterForm.querySelectorAll('input[name="material_category"]').forEach((input) => { input.checked = true; });
  materialCenterQuery.value = "";
  materialCenterDateFrom.value = "";
  materialCenterDateTo.value = "";
  materialCenterSort.value = "timeline_desc";
  materialCenterTimeStatus = "all";
  updateMaterialTimeReviewButton();
  if (refresh) runMaterialCenterBrowse();
}

async function openMaterialCenterModal() {
  if (!materialCenterModal || !currentProfile) return;
  materialCenterDrawerResumeState = null;
  if (isContentCenterOpen()) closeContentCenterModalNow({ restoreFocus: false });
  if (isMemorySearchOpen()) closeMemorySearchModalNow({ restoreFocus: false });
  if (isMemoryMapFilterOpen()) closeMemoryMapFilterModalNow({ restoreFocus: false });
  materialCenterReturnFocus = document.activeElement;
  materialCenterModal.classList.remove("hidden");
  materialCenterModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("material-center-open");
  if (materialCenterViewMode === "timeline") resetMaterialTimelineAxisToToday();
  setMaterialCenterViewMode(materialCenterViewMode, { rerender: false });
  await Promise.all([
    runMaterialCenterBrowse(),
    loadLargeUploadMaintenanceStatus(),
    refreshMaterialTimelineBackfillStatus({ silent: true }),
  ]);
}

async function openMaterialCenterPeriod(scope, periodKey, trigger = null, target = null) {
  const suspended = suspendMaterialCenterForDrawer(trigger);
  const opened = await openPeriodDrawer(scope, periodKey);
  if (opened !== true) {
    if (suspended) resumeMaterialCenterAfterDrawer();
    return;
  }
  if (target?.kind && target?.id) focusContentCenterTarget(target.kind, target.id);
}

function setMaterialCenterViewMode(mode, { rerender = true } = {}) {
  materialCenterViewMode = mode === "list" ? "list" : "timeline";
  const timelineActive = materialCenterViewMode === "timeline";
  materialCenterTimelineViewButton?.classList.toggle("is-active", timelineActive);
  materialCenterListViewButton?.classList.toggle("is-active", !timelineActive);
  materialCenterTimelineViewButton?.setAttribute("aria-selected", String(timelineActive));
  materialCenterListViewButton?.setAttribute("aria-selected", String(!timelineActive));
  const addedOption = materialCenterSort?.querySelector('option[value="added_desc"]');
  if (addedOption) addedOption.disabled = timelineActive;
  if (timelineActive && materialCenterSort?.value === "added_desc") {
    materialCenterSort.value = "timeline_desc";
  }
  materialCenterForm?.classList.toggle("hidden", timelineActive);
  materialCenterForm?.querySelectorAll("input, select, button").forEach((control) => {
    control.disabled = timelineActive;
  });
  if (rerender && isMaterialCenterOpen()) runMaterialCenterBrowse();
}

function largeUploadTaskFingerprint(fileOrRecord, options = {}) {
  const name = String(fileOrRecord?.name || fileOrRecord?.filename || "");
  const size = Number(fileOrRecord?.size ?? fileOrRecord?.sizeBytes ?? fileOrRecord?.size_bytes ?? 0);
  const lastModified = Number(fileOrRecord?.lastModified ?? fileOrRecord?.fileLastModifiedMs ?? fileOrRecord?.file_last_modified_ms ?? 0);
  const relativePath = String(options.sourceRelativePath ?? fileOrRecord?.sourceRelativePath ?? fileOrRecord?.source_relative_path ?? "");
  return `${name}\n${size}\n${lastModified}\n${relativePath}`;
}

function readLargeUploadStorageRecords() {
  try {
    const parsed = JSON.parse(localStorage.getItem(LARGE_UPLOAD_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item === "object") : [];
  } catch (_) {
    return [];
  }
}

function persistLargeMaterialUploadTasks() {
  if (!currentProfile?.id) return;
  const profileId = String(currentProfile.id);
  const otherProfiles = readLargeUploadStorageRecords().filter((item) => String(item.profileId || "") !== profileId);
  const currentRecords = Array.from(largeMaterialUploadTasks.values())
    .filter((task) => task.status !== "completed" && task.status !== "cancelled")
    .map((task) => ({
      profileId,
      sessionId: task.sessionId,
      updatedAt: new Date().toISOString(),
    }));
  try {
    localStorage.setItem(LARGE_UPLOAD_STORAGE_KEY, JSON.stringify([...otherProfiles, ...currentRecords]));
  } catch (_) {
    // Uploads still work for the current page even if browser storage is unavailable.
  }
}

function restoreLargeMaterialUploadTasksForCurrentProfile() {
  if (!currentProfile?.id) return;
  const profileId = String(currentProfile.id);
  if (largeMaterialUploadRestoreProfileId === profileId) return;
  largeMaterialUploadRestoreProfileId = profileId;
  largeMaterialUploadTasks.clear();
  readLargeUploadStorageRecords()
    .filter((item) => String(item.profileId || "") === profileId && item.sessionId)
    .forEach((record) => {
      largeMaterialUploadTasks.set(record.sessionId, {
        sessionId: String(record.sessionId),
        mediaId: null,
        filename: "未完成的大文件上传",
        mediaType: "application/octet-stream",
        sizeBytes: 0,
        fileLastModifiedMs: 0,
        sourceRelativePath: "",
        sourceDirectoryName: "",
        rejectDuplicate: false,
        quickFingerprint: "",
        chunkSize: 0,
        chunkCount: 0,
        completedBytes: 0,
        completedRanges: [],
        status: "recoverable",
        file: null,
        abortController: null,
        abortControllers: new Set(),
        pauseRequested: false,
        resumeRequested: false,
        cancelRequested: false,
        speedSamples: [],
        uploadSpeedBps: 0,
        estimatedSecondsRemaining: null,
        errorMessage: "正在读取服务器断点信息……",
      });
    });
  renderLargeMaterialUploadPanel();
  void reconcileRecoverableLargeMaterialUploads();
}

function largeUploadStatusLabel(task) {
  const labels = {
    queued: "等待上传",
    uploading: "正在分块上传",
    pausing: "正在暂停",
    paused: "已暂停",
    recoverable: "等待重新选择原文件",
    finalizing: "正在校验并写入资料库",
    failed: "上传失败",
    cancelling: "正在取消",
    completed: "上传完成",
    cancelled: "已取消",
  };
  return labels[task?.status] || "等待上传";
}

function largeUploadProgressPercent(task) {
  const total = Number(task?.sizeBytes) || 0;
  if (!total) return 0;
  if (task.status === "completed") return 100;
  return Math.max(0, Math.min(100, (Number(task.completedBytes || 0) / total) * 100));
}

function formatLargeUploadRate(bytesPerSecond) {
  const value = Number(bytesPerSecond) || 0;
  if (value <= 0) return "";
  const mib = value / (1024 * 1024);
  if (mib >= 1) return `${mib.toFixed(mib >= 100 ? 0 : mib >= 10 ? 1 : 2)} MB/s`;
  const kib = value / 1024;
  return `${kib.toFixed(kib >= 100 ? 0 : 1)} KB/s`;
}

function formatLargeUploadEta(seconds) {
  const total = Math.max(0, Math.ceil(Number(seconds) || 0));
  if (!Number.isFinite(total) || total <= 0) return "";
  if (total < 60) return `${total}秒`;
  const minutes = Math.floor(total / 60);
  const remain = total % 60;
  if (minutes < 60) return `${minutes}分${String(remain).padStart(2, "0")}秒`;
  const hours = Math.floor(minutes / 60);
  const minuteRemain = minutes % 60;
  return `${hours}小时${String(minuteRemain).padStart(2, "0")}分`;
}

function resetLargeUploadSpeed(task) {
  const now = globalThis.performance?.now?.() ?? Date.now();
  task.speedSamples = [{ at: now, bytes: Number(task.completedBytes || 0) }];
  task.uploadSpeedBps = 0;
  task.estimatedSecondsRemaining = null;
}

function recordLargeUploadSpeed(task) {
  const now = globalThis.performance?.now?.() ?? Date.now();
  if (!Array.isArray(task.speedSamples) || !task.speedSamples.length) resetLargeUploadSpeed(task);
  task.speedSamples.push({ at: now, bytes: Number(task.completedBytes || 0) });
  const cutoff = now - LARGE_UPLOAD_SPEED_WINDOW_MS;
  while (task.speedSamples.length > 2 && task.speedSamples[1].at < cutoff) task.speedSamples.shift();
  const first = task.speedSamples[0];
  const last = task.speedSamples[task.speedSamples.length - 1];
  const elapsedSeconds = Math.max(0, (last.at - first.at) / 1000);
  const transferred = Math.max(0, last.bytes - first.bytes);
  if (elapsedSeconds >= 0.35 && transferred > 0) {
    task.uploadSpeedBps = transferred / elapsedSeconds;
    const remaining = Math.max(0, Number(task.sizeBytes || 0) - Number(task.completedBytes || 0));
    task.estimatedSecondsRemaining = task.uploadSpeedBps > 0 ? remaining / task.uploadSpeedBps : null;
  }
}

function largeUploadActiveRequestCount(task) {
  if (task?.abortControllers instanceof Set) return task.abortControllers.size;
  return task?.abortController ? 1 : 0;
}

function abortLargeUploadRequests(task) {
  if (task?.abortControllers instanceof Set) {
    Array.from(task.abortControllers).forEach((controller) => controller?.abort?.());
  }
  task?.abortController?.abort?.();
}

function largeUploadDetailsText(task) {
  const percent = largeUploadProgressPercent(task);
  const chunkText = task.chunkSize ? ` · ${formatAttachmentSize(task.chunkSize)}/块` : "";
  let transferText = "";
  if (task.status === "uploading") {
    const rate = formatLargeUploadRate(task.uploadSpeedBps);
    const eta = formatLargeUploadEta(task.estimatedSecondsRemaining);
    if (rate) transferText += ` · ${rate}`;
    if (eta) transferText += ` · 预计剩余 ${eta}`;
  } else if (task.status === "finalizing") {
    transferText = " · 上传已完成，正在校验";
  }
  return `${percent.toFixed(percent >= 10 ? 0 : 1)}% · ${formatAttachmentSize(task.completedBytes || 0)} / ${formatAttachmentSize(task.sizeBytes || 0)}${chunkText}${transferText}`;
}

function largeUploadCompletedIndexSet(ranges) {
  const set = new Set();
  (Array.isArray(ranges) ? ranges : []).forEach((range) => {
    if (!Array.isArray(range) || range.length < 2) return;
    const start = Math.max(0, Number(range[0]) || 0);
    const end = Math.max(start, Number(range[1]) || start);
    for (let index = start; index <= end; index += 1) set.add(index);
  });
  return set;
}

function applyLargeUploadServerStatus(task, status) {
  task.sessionId = String(status.session_id || task.sessionId || "");
  task.mediaId = status.media_id || task.mediaId || null;
  task.filename = String(status.filename || task.filename || "未命名大型资料");
  task.mediaType = String(status.media_type || task.mediaType || "application/octet-stream");
  task.sizeBytes = Number(status.size_bytes) || task.sizeBytes || 0;
  task.fileLastModifiedMs = Number(status.file_last_modified_ms) || task.fileLastModifiedMs || 0;
  task.sourceRelativePath = String(status.source_relative_path || task.sourceRelativePath || "");
  task.sourceDirectoryName = String(status.source_directory_name || task.sourceDirectoryName || "");
  task.rejectDuplicate = Boolean(status.reject_duplicate ?? task.rejectDuplicate);
  task.quickFingerprint = String(status.quick_fingerprint || task.quickFingerprint || "");
  task.chunkSize = Number(status.chunk_size) || task.chunkSize || 0;
  task.chunkCount = Number(status.chunk_count) || task.chunkCount || 0;
  task.completedBytes = Number(status.completed_bytes) || 0;
  task.completedRanges = Array.isArray(status.completed_ranges) ? status.completed_ranges : [];
}

function updateLargeMaterialUploadProgressDisplay(task) {
  if (!largeMaterialUploadList || !task?.sessionId) return;
  const row = largeMaterialUploadList.querySelector(`[data-large-upload-session="${String(task.sessionId)}"]`);
  if (!(row instanceof HTMLElement)) return;
  const percent = largeUploadProgressPercent(task);
  const progressBar = row.querySelector('[data-large-upload-role="progress-bar"]');
  const details = row.querySelector('[data-large-upload-role="details"]');
  if (progressBar instanceof HTMLElement) progressBar.style.width = `${percent.toFixed(2)}%`;
  if (details instanceof HTMLElement) {
    const detailText = largeUploadDetailsText(task);
    details.textContent = detailText;
    details.title = task.errorMessage || detailText;
  }
}

function scheduleLargeMaterialUploadPanelRender(delay = 180) {
  if (largeMaterialUploadRenderTimer !== null) return;
  largeMaterialUploadRenderTimer = window.setTimeout(() => {
    largeMaterialUploadRenderTimer = null;
    largeMaterialUploadTasks.forEach((task) => updateLargeMaterialUploadProgressDisplay(task));
  }, Math.max(0, Number(delay) || 0));
}

function flushLargeMaterialUploadPanelRender() {
  if (largeMaterialUploadRenderTimer !== null) {
    window.clearTimeout(largeMaterialUploadRenderTimer);
    largeMaterialUploadRenderTimer = null;
  }
  renderLargeMaterialUploadPanel();
}

function renderLargeMaterialUploadPanel() {
  if (!largeMaterialUploadPanel || !largeMaterialUploadList) return;
  const tasks = Array.from(largeMaterialUploadTasks.values()).filter((task) => task.status !== "cancelled");
  const stale = Number(largeUploadMaintenanceStatus?.stale_sessions || 0);
  largeMaterialUploadPanel.classList.toggle("hidden", tasks.length === 0 && stale === 0);
  largeMaterialUploadList.replaceChildren();
  const active = tasks.filter((task) => ["queued", "uploading", "finalizing"].includes(task.status)).length;
  const paused = tasks.filter((task) => ["paused", "recoverable", "failed"].includes(task.status)).length;
  if (largeMaterialUploadSummary) {
    const parts = [];
    if (tasks.length) parts.push(`${tasks.length} 个任务`);
    if (active) parts.push(`进行中 ${active}`);
    if (paused) parts.push(`待处理 ${paused}`);
    if (stale) parts.push(`过期断点 ${stale}`);
    largeMaterialUploadSummary.textContent = parts.join(" · ");
  }
  cleanupStaleLargeUploadsButton?.classList.toggle("hidden", stale === 0);
  if (!tasks.length) return;

  tasks.forEach((task) => {
    const row = document.createElement("article");
    row.className = `large-material-upload-item is-${task.status || "queued"}`;
    row.dataset.largeUploadSession = String(task.sessionId || "");

    const main = document.createElement("div");
    main.className = "large-material-upload-main";
    const heading = document.createElement("div");
    heading.className = "large-material-upload-heading";
    const name = document.createElement("strong");
    name.textContent = task.filename || "未命名大型资料";
    name.title = name.textContent;
    const state = document.createElement("span");
    state.textContent = largeUploadStatusLabel(task);
    heading.append(name, state);

    const progress = document.createElement("div");
    progress.className = "large-material-upload-progress";
    const progressBar = document.createElement("span");
    progressBar.dataset.largeUploadRole = "progress-bar";
    progressBar.style.width = `${largeUploadProgressPercent(task).toFixed(2)}%`;
    progress.appendChild(progressBar);

    const details = document.createElement("div");
    details.className = "large-material-upload-details";
    details.dataset.largeUploadRole = "details";
    details.textContent = largeUploadDetailsText(task);
    details.title = task.errorMessage || details.textContent;
    main.append(heading, progress, details);

    const actions = document.createElement("div");
    actions.className = "large-material-upload-actions";
    if (task.status === "uploading" || task.status === "queued") {
      const pause = document.createElement("button");
      pause.className = "ghost-button";
      pause.type = "button";
      pause.textContent = "暂停";
      pause.addEventListener("click", () => pauseLargeMaterialUploadTask(task));
      actions.appendChild(pause);
    } else if (["paused", "failed", "recoverable"].includes(task.status)) {
      const resume = document.createElement("button");
      resume.className = "ghost-button";
      resume.type = "button";
      resume.textContent = task.file ? "继续" : "选择原文件继续";
      resume.addEventListener("click", () => {
        if (task.file) resumeLargeMaterialUploadTask(task);
        else {
          showToast(`请重新选择“${task.filename}”，系统会自动匹配断点。`, "info");
          materialImportInput?.click();
        }
      });
      actions.appendChild(resume);
    }
    if (!["finalizing", "completed", "cancelling"].includes(task.status)) {
      const cancel = document.createElement("button");
      cancel.className = "ghost-button is-danger";
      cancel.type = "button";
      cancel.textContent = "取消";
      cancel.addEventListener("click", () => cancelLargeMaterialUploadTask(task));
      actions.appendChild(cancel);
    }
    if (task.status === "completed") {
      const dismiss = document.createElement("button");
      dismiss.className = "ghost-button";
      dismiss.type = "button";
      dismiss.textContent = "清理";
      dismiss.addEventListener("click", () => {
        largeMaterialUploadTasks.delete(task.sessionId);
        renderLargeMaterialUploadPanel();
      });
      actions.appendChild(dismiss);
    }
    row.append(main, actions);
    largeMaterialUploadList.appendChild(row);
  });
}

async function reconcileRecoverableLargeMaterialUploads() {
  const tasks = Array.from(largeMaterialUploadTasks.values()).filter((task) => task.status === "recoverable");
  for (const task of tasks) {
    try {
      const status = await api(`/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}`, {}, true);
      applyLargeUploadServerStatus(task, status);
      task.status = "recoverable";
      task.errorMessage = "请选择同一个本地文件继续断点上传。";
    } catch (error) {
      if (error?.code === "LARGE_UPLOAD_NOT_FOUND") {
        largeMaterialUploadTasks.delete(task.sessionId);
      } else {
        task.errorMessage = error?.message || "断点状态暂时无法确认";
      }
    }
  }
  persistLargeMaterialUploadTasks();
  renderLargeMaterialUploadPanel();
}

async function loadLargeUploadMaintenanceStatus() {
  if (!currentProfile?.id) return null;
  try {
    largeUploadMaintenanceStatus = await api("/api/v1/materials/large/uploads/maintenance?stale_days=30", {}, true);
  } catch (_) {
    largeUploadMaintenanceStatus = null;
  }
  renderLargeMaterialUploadPanel();
  return largeUploadMaintenanceStatus;
}

cleanupStaleLargeUploadsButton?.addEventListener("click", async () => {
  const stale = Number(largeUploadMaintenanceStatus?.stale_sessions || 0);
  if (!stale) {
    showToast("当前没有超过 30 天的过期上传断点", "info");
    return;
  }
  const confirmed = await askConfirmation({
    eyebrow: "清理上传断点",
    title: `清理 ${stale} 个过期任务？`,
    message: "只会删除超过 30 天且当前没有正在写入的未完成大文件上传会话；已经入库的资料不会受影响。",
    confirmLabel: "清理过期任务",
    tone: "warning",
  });
  if (!confirmed) return;
  setButtonBusy(cleanupStaleLargeUploadsButton, true, "清理中…");
  try {
    const result = await api("/api/v1/materials/large/uploads/cleanup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stale_days: 30 }),
    }, true);
    await reconcileRecoverableLargeMaterialUploads();
    await loadLargeUploadMaintenanceStatus();
    showToast(`已清理 ${Number(result.removed_sessions || 0)} 个过期上传任务`, "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(cleanupStaleLargeUploadsButton, false);
  }
});

function findMatchingLargeUploadTask(file, options = {}) {
  const fingerprint = largeUploadTaskFingerprint(file, options);
  const tasks = Array.from(largeMaterialUploadTasks.values());
  const exact = tasks.find((task) => (
    largeUploadTaskFingerprint({
      filename: task.filename,
      sizeBytes: task.sizeBytes,
      fileLastModifiedMs: task.fileLastModifiedMs,
      sourceRelativePath: task.sourceRelativePath,
    }) === fingerprint
  ));
  if (exact) return exact;
  if (options.sourceRelativePath) return null;
  const fallback = tasks.filter((task) => (
    String(task.filename || "") === String(file?.name || "")
    && Number(task.sizeBytes || 0) === Number(file?.size || 0)
    && Number(task.fileLastModifiedMs || 0) === Number(file?.lastModified || 0)
    && ["recoverable", "paused", "failed"].includes(task.status)
  ));
  return fallback.length === 1 ? fallback[0] : null;
}

async function computeLargeMaterialQuickFingerprint(file) {
  if (!file?.size || !window.crypto?.subtle) return "";
  const sampleSize = 1024 * 1024;
  const ranges = [
    [0, Math.min(file.size, sampleSize)],
    [Math.max(0, Math.floor(file.size / 2) - Math.floor(sampleSize / 2)), Math.min(file.size, Math.max(0, Math.floor(file.size / 2) - Math.floor(sampleSize / 2)) + sampleSize)],
    [Math.max(0, file.size - sampleSize), file.size],
  ];
  const unique = [];
  const seen = new Set();
  ranges.forEach(([start, end]) => {
    const key = `${start}:${end}`;
    if (end > start && !seen.has(key)) {
      seen.add(key);
      unique.push(file.slice(start, end));
    }
  });
  const prefix = new TextEncoder().encode(`LifeGraph-quick-v1:${file.size}:`);
  const sampled = await new Blob([prefix, ...unique]).arrayBuffer();
  const digest = await window.crypto.subtle.digest("SHA-256", sampled);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function createLargeMaterialUploadTask(file, options = {}) {
  const quickFingerprint = await computeLargeMaterialQuickFingerprint(file);
  const data = await api("/api/v1/materials/large/uploads", {
    method: "POST",
    body: JSON.stringify({
      filename: file.name || "未命名大型资料",
      media_type: file.type || "application/octet-stream",
      size_bytes: file.size,
      file_last_modified_ms: Number.isFinite(file.lastModified) && file.lastModified > 0 ? Math.trunc(file.lastModified) : null,
      source_relative_path: options.sourceRelativePath || null,
      source_directory_name: options.sourceDirectoryName || null,
      quick_fingerprint: quickFingerprint || null,
      reject_duplicate: options.rejectDuplicate !== false,
    }),
  }, true);
  const task = {
    sessionId: data.session_id,
    mediaId: data.media_id || null,
    filename: data.filename || file.name,
    mediaType: data.media_type || file.type || "application/octet-stream",
    sizeBytes: Number(data.size_bytes) || file.size,
    fileLastModifiedMs: Number(data.file_last_modified_ms) || Number(file.lastModified) || 0,
    sourceRelativePath: String(data.source_relative_path || options.sourceRelativePath || ""),
    sourceDirectoryName: String(data.source_directory_name || options.sourceDirectoryName || ""),
    rejectDuplicate: Boolean(data.reject_duplicate ?? (options.rejectDuplicate !== false)),
    quickFingerprint: String(data.quick_fingerprint || quickFingerprint || ""),
    chunkSize: Number(data.chunk_size) || 0,
    chunkCount: Number(data.chunk_count) || 0,
    completedBytes: Number(data.completed_bytes) || 0,
    completedRanges: Array.isArray(data.completed_ranges) ? data.completed_ranges : [],
    status: "queued",
    file,
    abortController: null,
    abortControllers: new Set(),
    pauseRequested: false,
    resumeRequested: false,
    cancelRequested: false,
    speedSamples: [],
    uploadSpeedBps: 0,
    estimatedSecondsRemaining: null,
    errorMessage: "",
  };
  largeMaterialUploadTasks.set(task.sessionId, task);
  persistLargeMaterialUploadTasks();
  renderLargeMaterialUploadPanel();
  return task;
}

async function prepareLargeMaterialVideoAssets(task) {
  if (!task?.file || !isVideoFile(task.file)) return;
  const assets = await extractVideoMediaAssets(task.file);
  if (assets?.metadata && Object.keys(assets.metadata).length) {
    await api(
      `/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}/video-metadata`,
      { method: "PUT", body: JSON.stringify(assets.metadata) },
      true,
    );
  }
  if (assets?.previewBlob) {
    const headers = { "Content-Type": assets.previewBlob.type || "image/jpeg" };
    if (token()) headers.Authorization = `Bearer ${token()}`;
    const response = await fetch(
      `/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}/preview`,
      { method: "PUT", headers, body: assets.previewBlob },
    );
    if (!response.ok) {
      let message = `视频封面保存失败：HTTP ${response.status}`;
      try {
        const payload = await response.json();
        message = payload.error?.message || message;
      } catch (_) {}
      throw new Error(message);
    }
  }
}

async function queueLargeMaterialUploadFile(file, options = {}) {
  if (!file?.size) throw new Error("大型资料文件不能为空。");
  if (Array.from(largeMaterialUploadTasks.values()).some((task) => task.status === "recoverable" && !task.sizeBytes)) {
    await reconcileRecoverableLargeMaterialUploads();
  }
  if (file.size > MAX_LARGE_MATERIAL_BYTES) {
    const error = new Error(`“${file.name}”超过 2 TB，暂不能导入。`);
    error.code = "MATERIAL_TOO_LARGE";
    throw error;
  }
  let task = findMatchingLargeUploadTask(file, options);
  if (task) {
    task.file = file;
    task.pauseRequested = false;
    task.resumeRequested = false;
    task.cancelRequested = false;
    try {
      const status = await api(`/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}`, {}, true);
      if (Number(status.size_bytes) !== file.size || String(status.filename || "") !== String(file.name || "")) {
        throw new Error("本地文件与断点上传会话不匹配。");
      }
      applyLargeUploadServerStatus(task, status);
      task.status = status.complete ? "queued" : "queued";
      task.errorMessage = "";
    } catch (error) {
      if (error?.code !== "LARGE_UPLOAD_NOT_FOUND") throw error;
      largeMaterialUploadTasks.delete(task.sessionId);
      task = null;
    }
  }
  if (!task) task = await createLargeMaterialUploadTask(file, options);
  if (isVideoFile(file)) {
    try {
      await prepareLargeMaterialVideoAssets(task);
    } catch (error) {
      console.warn("LifeGraph video metadata extraction/upload skipped:", error);
    }
  }
  persistLargeMaterialUploadTasks();
  renderLargeMaterialUploadPanel();
  scheduleLargeMaterialUploadQueue();
  return task;
}

async function uploadLargeMaterialChunk(task, index, blob) {
  let lastError = null;
  for (let attempt = 1; attempt <= LARGE_UPLOAD_MAX_RETRIES; attempt += 1) {
    if (task.cancelRequested) {
      const cancelled = new Error("UPLOAD_CANCELLED");
      cancelled.code = "UPLOAD_CANCELLED";
      throw cancelled;
    }
    if (task.pauseRequested) {
      const paused = new Error("UPLOAD_PAUSED");
      paused.code = "UPLOAD_PAUSED";
      throw paused;
    }
    const controller = new AbortController();
    if (!(task.abortControllers instanceof Set)) task.abortControllers = new Set();
    task.abortControllers.add(controller);
    task.abortController = controller;
    try {
      const headers = { "Content-Type": "application/octet-stream" };
      if (token()) headers.Authorization = `Bearer ${token()}`;
      const response = await fetch(
        `/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}/chunks/${index}`,
        { method: "PUT", headers, body: blob, signal: controller.signal },
      );
      const text = await response.text();
      let payload;
      try {
        payload = text ? JSON.parse(text) : { ok: false, error: { message: "响应为空" } };
      } catch (_) {
        payload = { ok: false, error: { message: `响应格式错误：HTTP ${response.status}` } };
      }
      if (!response.ok || !payload.ok) {
        const error = new Error(payload.error?.message || `分块上传失败：HTTP ${response.status}`);
        error.code = payload.error?.code || "LARGE_UPLOAD_CHUNK_FAILED";
        error.httpStatus = response.status;
        throw error;
      }
      return payload.data;
    } catch (error) {
      if (controller.signal.aborted && task.cancelRequested) {
        const cancelled = new Error("UPLOAD_CANCELLED");
        cancelled.code = "UPLOAD_CANCELLED";
        throw cancelled;
      }
      if (controller.signal.aborted && task.pauseRequested) {
        const paused = new Error("UPLOAD_PAUSED");
        paused.code = "UPLOAD_PAUSED";
        throw paused;
      }
      lastError = error;
      const retryable = !error?.httpStatus || error.httpStatus >= 500 || error.httpStatus === 429;
      if (!retryable || attempt >= LARGE_UPLOAD_MAX_RETRIES) break;
      await new Promise((resolve) => window.setTimeout(resolve, 500 * attempt));
    } finally {
      task.abortControllers?.delete?.(controller);
      if (task.abortController === controller) task.abortController = null;
    }
  }
  throw lastError || new Error("分块上传失败");
}

function syncMaterialDirectoryItemFromLargeTask(task) {
  const item = materialDirectoryScanItems.find((entry) => entry.largeUploadSessionId === task.sessionId);
  if (!item) return;
  if (task.status === "completed") item.status = "imported";
  else if (task.status === "cancelled") {
    item.status = "ready";
    item.selected = false;
    item.largeUploadSessionId = null;
  } else if (task.status === "failed") {
    item.status = "failed";
    item.errorMessage = task.errorMessage || "大文件上传失败";
  } else if (["paused", "pausing", "recoverable"].includes(task.status)) item.status = "paused_large";
  else if (["queued", "uploading", "finalizing", "cancelling"].includes(task.status)) item.status = task.status === "uploading" ? "uploading_large" : "queued_large";
  if (isMaterialDirectoryScanOpen()) renderMaterialDirectoryScanList();
}

async function runLargeMaterialUploadTask(task) {
  if (!task.file) {
    task.status = "recoverable";
    task.errorMessage = "请选择同一个本地文件继续断点上传。";
    persistLargeMaterialUploadTasks();
    renderLargeMaterialUploadPanel();
    return;
  }
  try {
    const status = await api(`/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}`, {}, true);
    applyLargeUploadServerStatus(task, status);
    if (task.cancelRequested) {
      const cancelled = new Error("UPLOAD_CANCELLED");
      cancelled.code = "UPLOAD_CANCELLED";
      throw cancelled;
    }
    if (task.pauseRequested) {
      const paused = new Error("UPLOAD_PAUSED");
      paused.code = "UPLOAD_PAUSED";
      throw paused;
    }
    if (Number(status.size_bytes) !== task.file.size) throw new Error("本地文件大小与上传会话不匹配。");
    const completed = largeUploadCompletedIndexSet(task.completedRanges);
    const pendingIndices = [];
    for (let index = 0; index < task.chunkCount; index += 1) {
      if (!completed.has(index)) pendingIndices.push(index);
    }
    task.status = "uploading";
    task.errorMessage = "";
    resetLargeUploadSpeed(task);
    syncMaterialDirectoryItemFromLargeTask(task);
    persistLargeMaterialUploadTasks();
    renderLargeMaterialUploadPanel();

    let nextPendingIndex = 0;
    let workerFailure = null;
    const uploadWorker = async () => {
      while (true) {
        if (workerFailure) return;
        if (task.cancelRequested) {
          const cancelled = new Error("UPLOAD_CANCELLED");
          cancelled.code = "UPLOAD_CANCELLED";
          throw cancelled;
        }
        if (task.pauseRequested) {
          const paused = new Error("UPLOAD_PAUSED");
          paused.code = "UPLOAD_PAUSED";
          throw paused;
        }
        const cursor = nextPendingIndex;
        nextPendingIndex += 1;
        if (cursor >= pendingIndices.length) return;
        const index = pendingIndices[cursor];
        const start = index * task.chunkSize;
        const end = Math.min(task.sizeBytes, start + task.chunkSize);
        const chunk = task.file.slice(start, end);
        try {
          await uploadLargeMaterialChunk(task, index, chunk);
        } catch (error) {
          if (!workerFailure) {
            workerFailure = error;
            abortLargeUploadRequests(task);
          }
          throw error;
        }
        completed.add(index);
        task.completedBytes = Math.min(task.sizeBytes, Number(task.completedBytes || 0) + (end - start));
        recordLargeUploadSpeed(task);
        scheduleLargeMaterialUploadPanelRender();
      }
    };

    const workerCount = Math.min(LARGE_UPLOAD_CONCURRENCY, Math.max(1, pendingIndices.length));
    const settled = await Promise.allSettled(Array.from({ length: workerCount }, () => uploadWorker()));
    const rejected = settled.find((item) => item.status === "rejected");
    if (rejected) throw rejected.reason;

    const sorted = Array.from(completed).sort((a, b) => a - b);
    task.completedRanges = [];
    sorted.forEach((value) => {
      const last = task.completedRanges[task.completedRanges.length - 1];
      if (!last || value > last[1] + 1) task.completedRanges.push([value, value]);
      else last[1] = value;
    });

    task.status = "finalizing";
    task.completedBytes = task.sizeBytes;
    persistLargeMaterialUploadTasks();
    renderLargeMaterialUploadPanel();
    const result = await api(`/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}/finalize`, { method: "POST" }, true);
    task.status = "completed";
    task.completedBytes = task.sizeBytes;
    task.errorMessage = "";
    persistLargeMaterialUploadTasks();
    syncMaterialDirectoryItemFromLargeTask(task);
    renderLargeMaterialUploadPanel();
    showToast(`“${task.filename}”大文件上传完成`, "success");
    if (isMaterialCenterOpen()) {
      await runMaterialCenterBrowse();
      focusMaterialCenterImportedAttachment(result);
    }
    await refreshContentStatuses();
    return result;
  } catch (error) {
    if (error?.code === "UPLOAD_CANCELLED" || task.cancelRequested) {
      task.status = "cancelled";
      task.errorMessage = "";
    } else if (error?.code === "UPLOAD_PAUSED" || task.pauseRequested) {
      const resumeAfterPause = Boolean(task.resumeRequested && task.file);
      task.pauseRequested = false;
      task.resumeRequested = false;
      task.status = resumeAfterPause ? "queued" : "paused";
      task.errorMessage = resumeAfterPause ? "" : "已暂停，可从现有断点继续。";
    } else if (error?.code === "LARGE_UPLOAD_NOT_FOUND") {
      task.status = "failed";
      task.errorMessage = "服务器端上传会话已不存在，请取消此任务后重新选择文件。";
    } else {
      task.status = "failed";
      task.errorMessage = error?.message || "上传失败";
      showToast(`${task.filename}：${task.errorMessage}`, "error");
    }
    persistLargeMaterialUploadTasks();
    syncMaterialDirectoryItemFromLargeTask(task);
    renderLargeMaterialUploadPanel();
  }
}

async function scheduleLargeMaterialUploadQueue() {
  if (largeMaterialUploadQueueRunning) return;
  largeMaterialUploadQueueRunning = true;
  try {
    while (true) {
      const task = Array.from(largeMaterialUploadTasks.values()).find((item) => item.status === "queued" && item.file);
      if (!task) break;
      await runLargeMaterialUploadTask(task);
    }
  } finally {
    largeMaterialUploadQueueRunning = false;
  }
}

function pauseLargeMaterialUploadTask(task) {
  if (!task || !["queued", "uploading"].includes(task.status)) return;
  task.pauseRequested = true;
  task.resumeRequested = false;
  task.cancelRequested = false;
  const hasActiveRequest = largeUploadActiveRequestCount(task) > 0;
  task.status = hasActiveRequest ? "pausing" : "paused";
  task.errorMessage = hasActiveRequest ? "正在停止当前分块请求……" : "已暂停，可从服务器记录的断点继续。";
  abortLargeUploadRequests(task);
  persistLargeMaterialUploadTasks();
  syncMaterialDirectoryItemFromLargeTask(task);
  flushLargeMaterialUploadPanelRender();
}

function resumeLargeMaterialUploadTask(task) {
  if (!task?.file) {
    task.status = "recoverable";
    renderLargeMaterialUploadPanel();
    return;
  }
  if (largeUploadActiveRequestCount(task) > 0) {
    task.resumeRequested = true;
    task.errorMessage = "正在结束当前分块请求，随后自动继续。";
    renderLargeMaterialUploadPanel();
    return;
  }
  task.pauseRequested = false;
  task.resumeRequested = false;
  task.cancelRequested = false;
  task.status = "queued";
  task.errorMessage = "";
  persistLargeMaterialUploadTasks();
  syncMaterialDirectoryItemFromLargeTask(task);
  renderLargeMaterialUploadPanel();
  scheduleLargeMaterialUploadQueue();
}

async function cancelLargeMaterialUploadTask(task) {
  if (!task?.sessionId) return;
  const confirmed = await askConfirmation({
    eyebrow: "取消大文件上传",
    title: `取消“${task.filename || "未命名大型资料"}”的上传？`,
    message: "服务器上已上传的加密分块会一起删除。之后如需导入，需要重新开始。",
    confirmLabel: "取消上传",
    tone: "danger",
  });
  if (!confirmed) return;
  task.cancelRequested = true;
  task.pauseRequested = false;
  task.resumeRequested = false;
  task.status = "cancelling";
  task.errorMessage = "正在停止上传并清理服务器分块……";
  abortLargeUploadRequests(task);
  persistLargeMaterialUploadTasks();
  flushLargeMaterialUploadPanelRender();
  try {
    await api(`/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}`, { method: "DELETE" }, true);
  } catch (error) {
    if (error?.code !== "LARGE_UPLOAD_NOT_FOUND") {
      task.cancelRequested = false;
      task.status = task.file ? "paused" : "recoverable";
      task.errorMessage = "取消失败，可再次尝试。";
      persistLargeMaterialUploadTasks();
      flushLargeMaterialUploadPanelRender();
      showOperationError(error);
      return;
    }
  }
  task.status = "cancelled";
  largeMaterialUploadTasks.delete(task.sessionId);
  persistLargeMaterialUploadTasks();
  syncMaterialDirectoryItemFromLargeTask(task);
  renderLargeMaterialUploadPanel();
  showToast("大文件上传任务已取消", "success");
}

function pauseLargeMaterialUploadsForLock() {
  largeMaterialUploadTasks.forEach((task) => {
    if (!["queued", "uploading"].includes(task.status)) return;
    task.pauseRequested = true;
    task.resumeRequested = false;
    task.status = "paused";
    task.errorMessage = "仓库锁定，上传已暂停。重新解锁后可继续。";
    abortLargeUploadRequests(task);
  });
  persistLargeMaterialUploadTasks();
  renderLargeMaterialUploadPanel();
}

async function importIndependentMaterialFile(file, options = {}) {
  if (file.size > MAX_ATTACHMENT_BYTES) {
    return queueLargeMaterialUploadFile(file, options);
  }
  const formData = new FormData();
  formData.append("material_file", file, file.name);
  if (isVideoFile(file)) {
    try {
      const assets = await extractVideoMediaAssets(file);
      if (assets?.metadata && Object.keys(assets.metadata).length) {
        formData.append("video_metadata_json", JSON.stringify(assets.metadata));
      }
      if (assets?.previewBlob) {
        formData.append("video_preview", assets.previewBlob, "video-preview.jpg");
      }
    } catch (error) {
      console.warn("LifeGraph video metadata extraction skipped:", error);
    }
  }
  if (Number.isFinite(file.lastModified) && file.lastModified > 0) {
    formData.append("file_last_modified_ms", String(Math.trunc(file.lastModified)));
  }
  if (options.sourceRelativePath) formData.append("source_relative_path", String(options.sourceRelativePath));
  if (options.sourceDirectoryName) formData.append("source_directory_name", String(options.sourceDirectoryName));
  if (options.rejectDuplicate) formData.append("reject_duplicate", "true");
  const headers = {};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch("/api/v1/materials/import", { method: "POST", headers, body: formData });
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

async function importIndependentMaterials(files) {
  const selected = Array.from(files || []);
  if (!selected.length) return;
  setButtonBusy(importMaterialButton, true, `导入中 0/${selected.length}`);
  let imported = 0;
  let queuedLarge = 0;
  let lastImportedResult = null;
  const failed = [];
  for (let index = 0; index < selected.length; index += 1) {
    const file = selected[index];
    if (importMaterialButton) importMaterialButton.textContent = `导入中 ${index + 1}/${selected.length}`;
    try {
      const result = await importIndependentMaterialFile(file, { rejectDuplicate: true });
      if (file.size > MAX_ATTACHMENT_BYTES) queuedLarge += 1;
      else {
        imported += 1;
        lastImportedResult = result;
      }
    } catch (error) {
      failed.push({ file, error });
    }
  }
  setButtonBusy(importMaterialButton, false);
  if (importMaterialButton) importMaterialButton.textContent = "＋ 导入资料";
  if (imported) {
    await runMaterialCenterBrowse();
    if (lastImportedResult) focusMaterialCenterImportedAttachment(lastImportedResult);
    await refreshContentStatuses();
  }
  if (imported || queuedLarge) {
    const parts = [];
    if (imported) parts.push(`已导入 ${imported} 份`);
    if (queuedLarge) parts.push(`${queuedLarge} 个大文件已加入分块上传`);
    if (failed.length) parts.push(`${failed.length} 份失败`);
    showToast(parts.join("，"), failed.length ? "info" : "success");
  }
  if (failed.length) {
    const first = failed[0];
    const message = first?.error?.message || "导入失败";
    showToast(`${first.file?.name || "资料"}：${message}`, "error");
  }
}

function isMaterialAutoScanOpen() {
  return Boolean(materialAutoScanModal && !materialAutoScanModal.classList.contains("hidden"));
}

function stopMaterialScannerPolling() {
  if (materialScannerPollTimer) {
    window.clearTimeout(materialScannerPollTimer);
    materialScannerPollTimer = null;
  }
}

function scheduleMaterialScannerPolling() {
  stopMaterialScannerPolling();
  if (!isMaterialAutoScanOpen()) return;
  materialScannerPollTimer = window.setTimeout(() => refreshMaterialScannerStatus({ silent: true }), 1000);
}

function openMaterialAutoScanModal() {
  if (!materialAutoScanModal || !currentProfile) return;
  materialAutoScanReturnFocus = document.activeElement;
  materialAutoScanModal.classList.remove("hidden");
  materialAutoScanModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("material-auto-scan-open");
  Promise.all([
    refreshMaterialScanSources({ silent: true }),
    refreshMaterialScannerStatus({ silent: true }),
  ]).catch(() => {});
  requestAnimationFrame(() => materialScanSourcePath?.focus());
}

function closeMaterialAutoScanModal({ restoreFocus = true } = {}) {
  if (!isMaterialAutoScanOpen()) return;
  stopMaterialScannerPolling();
  materialAutoScanModal.classList.add("hidden");
  materialAutoScanModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("material-auto-scan-open");
  if (restoreFocus && materialAutoScanReturnFocus instanceof HTMLElement && document.contains(materialAutoScanReturnFocus)) {
    materialAutoScanReturnFocus.focus();
  }
  materialAutoScanReturnFocus = null;
}

function scanSourceCountText(counts = {}) {
  const imported = Number(counts.imported || 0);
  const duplicate = Number(counts.duplicate || 0);
  const missing = Number(counts.missing || 0);
  const failed = Number(counts.failed || 0);
  const pieces = [];
  if (imported) pieces.push(`已入库 ${imported}`);
  if (duplicate) pieces.push(`重复 ${duplicate}`);
  if (missing) pieces.push(`源缺失 ${missing}`);
  if (failed) pieces.push(`失败 ${failed}`);
  return pieces.join(" · ") || "尚未扫描";
}

function renderMaterialScanSources(sources = materialScanSources) {
  if (!materialScanSourceList) return;
  materialScanSourceList.innerHTML = "";
  materialScanSources = Array.isArray(sources) ? sources : [];
  if (materialScanSourceSummary) {
    const enabled = materialScanSources.filter((source) => source.enabled).length;
    materialScanSourceSummary.textContent = materialScanSources.length ? `${materialScanSources.length} 个目录 · 启用 ${enabled}` : "尚未配置";
  }
  if (startMaterialScannerButton && !["waiting", "running", "pausing"].includes(materialScannerLastState)) {
    startMaterialScannerButton.disabled = materialScanSources.length === 0;
  }
  if (!materialScanSources.length) {
    const empty = document.createElement("div");
    empty.className = "material-scan-source-empty";
    empty.textContent = "还没有自动扫描目录。添加照片、视频或文档所在的本机文件夹即可。";
    materialScanSourceList.appendChild(empty);
    return;
  }
  const fragment = document.createDocumentFragment();
  materialScanSources.forEach((source) => {
    const row = document.createElement("article");
    row.className = `material-scan-source-row${source.enabled ? "" : " is-disabled"}${source.available === false ? " is-offline" : ""}`;

    const main = document.createElement("div");
    main.className = "material-scan-source-main";
    const title = document.createElement("strong");
    title.textContent = source.label || "扫描目录";
    const path = document.createElement("span");
    path.className = "material-scan-source-path-text";
    path.textContent = source.path || "";
    path.title = path.textContent;
    const meta = document.createElement("span");
    meta.className = "material-scan-source-meta";
    const availability = source.available === false ? "目录当前不可访问" : (source.include_subdirectories ? "包含子目录" : "仅当前目录");
    const scanTime = source.last_scan_completed_at ? ` · 最近完成 ${formatDateTime(source.last_scan_completed_at)}` : "";
    meta.textContent = `${availability} · ${scanSourceCountText(source.file_counts)}${scanTime}`;
    main.append(title, path, meta);

    const actions = document.createElement("div");
    actions.className = "material-scan-source-actions";
    const scan = document.createElement("button");
    scan.type = "button";
    scan.className = "ghost-button";
    scan.textContent = "扫描";
    scan.disabled = source.available === false;
    scan.addEventListener("click", () => startMaterialScanner(source.id, scan));
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "ghost-button";
    toggle.textContent = source.enabled ? "停用" : "启用";
    toggle.addEventListener("click", () => toggleMaterialScanSource(source, toggle));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost-button danger-text-button";
    remove.textContent = "移除";
    remove.addEventListener("click", () => removeMaterialScanSource(source, remove));
    actions.append(scan, toggle, remove);
    row.append(main, actions);
    fragment.appendChild(row);
  });
  materialScanSourceList.appendChild(fragment);
}

async function refreshMaterialScanSources({ silent = false } = {}) {
  try {
    const data = await api("/api/v1/materials/scan-sources", {}, true);
    renderMaterialScanSources(data || []);
    return data;
  } catch (error) {
    if (!silent) showOperationError(error);
    return null;
  }
}

function renderMaterialScannerStatus(data = {}) {
  const state = String(data.state || "idle");
  const previousState = materialScannerLastState;
  materialScannerLastState = state;
  if (materialScannerStatus) {
    if (state === "idle") {
      materialScannerStatus.textContent = "空闲；解锁后会自动检查已启用目录";
    } else if (state === "waiting") {
      materialScannerStatus.textContent = "等待后台自动扫描…";
    } else if (["running", "pausing"].includes(state)) {
      const pieces = [
        `目录 ${Number(data.processed_sources || 0)}/${Number(data.total_sources || 0)}`,
        `发现 ${Number(data.discovered_files || 0)}`,
        `新增 ${Number(data.imported_files || 0)}`,
      ];
      if (Number(data.skipped_files || 0)) pieces.push(`未变化 ${Number(data.skipped_files)}`);
      if (Number(data.duplicate_files || 0)) pieces.push(`重复 ${Number(data.duplicate_files)}`);
      if (Number(data.failed_files || 0)) pieces.push(`失败 ${Number(data.failed_files)}`);
      if (Number(data.unavailable_sources || 0)) pieces.push(`不可访问目录 ${Number(data.unavailable_sources)}`);
      if (data.current_file) pieces.push(`正在处理 ${data.current_file}`);
      materialScannerStatus.textContent = pieces.join(" · ");
    } else if (state === "completed") {
      materialScannerStatus.textContent = `扫描完成 · 新增 ${Number(data.imported_files || 0)} · 未变化 ${Number(data.skipped_files || 0)} · 重复 ${Number(data.duplicate_files || 0)}${Number(data.failed_files || 0) ? ` · 失败 ${Number(data.failed_files)}` : ""}`;
    } else if (state === "paused") {
      materialScannerStatus.textContent = `已暂停 · 已发现 ${Number(data.discovered_files || 0)} · 已新增 ${Number(data.imported_files || 0)}`;
    } else if (state === "failed") {
      materialScannerStatus.textContent = `扫描失败${data.error ? `：${data.error}` : ""}`;
    } else {
      materialScannerStatus.textContent = state;
    }
  }
  const running = ["waiting", "running", "pausing"].includes(state);
  if (startMaterialScannerButton) {
    startMaterialScannerButton.disabled = running || materialScanSources.length === 0;
    startMaterialScannerButton.textContent = state === "paused" ? "继续扫描" : "立即扫描全部";
  }
  if (pauseMaterialScannerButton) pauseMaterialScannerButton.disabled = !["waiting", "running"].includes(state);
  if (["waiting", "running", "pausing"].includes(state)) scheduleMaterialScannerPolling();
  else stopMaterialScannerPolling();

  if (["completed", "paused", "failed"].includes(state) && state !== previousState) {
    refreshMaterialScanSources({ silent: true });
    if (state === "completed" && Number(data.imported_files || 0) > 0 && isMaterialCenterOpen()) {
      runMaterialCenterBrowse();
      refreshContentStatuses();
    }
  }
}

async function refreshMaterialScannerStatus({ silent = false } = {}) {
  if (!currentProfile) return null;
  try {
    const data = await api("/api/v1/materials/scanner", {}, true);
    renderMaterialScannerStatus(data || {});
    return data;
  } catch (error) {
    stopMaterialScannerPolling();
    if (!silent) showOperationError(error);
    return null;
  }
}

async function addMaterialScanSource(event) {
  event?.preventDefault?.();
  const path = String(materialScanSourcePath?.value || "").trim();
  if (!path || !addMaterialScanSourceButton) return;
  setButtonBusy(addMaterialScanSourceButton, true, "添加中…");
  try {
    const source = await api("/api/v1/materials/scan-sources", {
      method: "POST",
      body: JSON.stringify({
        path,
        include_subdirectories: Boolean(materialScanSourceRecursive?.checked),
      }),
    }, true);
    if (materialScanSourcePath) materialScanSourcePath.value = "";
    await refreshMaterialScanSources({ silent: true });
    showToast(`已添加扫描源：${source.label || source.path}`, "success");
    await startMaterialScanner(source.id);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(addMaterialScanSourceButton, false);
  }
}

async function toggleMaterialScanSource(source, button) {
  setButtonBusy(button, true, source.enabled ? "停用中…" : "启用中…");
  try {
    await api(`/api/v1/materials/scan-sources/${encodeURIComponent(source.id)}`, {
      method: "PUT",
      body: JSON.stringify({ enabled: !source.enabled }),
    }, true);
    await refreshMaterialScanSources({ silent: true });
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function removeMaterialScanSource(source, button) {
  const confirmed = await askConfirmation({
    eyebrow: "移除自动扫描源",
    title: `停止扫描“${source.label || source.path}”吗？`,
    message: "只会移除这个目录的自动扫描配置；已经进入 LifeGraph 的加密资料副本会完整保留。",
    confirmLabel: "移除扫描源",
    tone: "warning",
  });
  if (!confirmed) return;
  setButtonBusy(button, true, "移除中…");
  try {
    await api(`/api/v1/materials/scan-sources/${encodeURIComponent(source.id)}`, { method: "DELETE" }, true);
    await refreshMaterialScanSources({ silent: true });
    showToast("扫描源已移除，已入库资料保持不变", "success");
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function startMaterialScanner(sourceId = null, button = null) {
  const targetButton = button || startMaterialScannerButton;
  if (targetButton) setButtonBusy(targetButton, true, "启动中…");
  try {
    const data = await api("/api/v1/materials/scanner/start", {
      method: "POST",
      body: JSON.stringify({ source_id: sourceId || null }),
    }, true);
    renderMaterialScannerStatus(data || {});
  } catch (error) {
    showOperationError(error);
  } finally {
    if (targetButton) setButtonBusy(targetButton, false);
  }
}

async function pauseMaterialScanner() {
  if (!pauseMaterialScannerButton) return;
  setButtonBusy(pauseMaterialScannerButton, true, "暂停中…");
  try {
    const data = await api("/api/v1/materials/scanner/pause", { method: "POST" }, true);
    renderMaterialScannerStatus(data || {});
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(pauseMaterialScannerButton, false);
  }
}

const MAX_DIRECTORY_SCAN_FILES = 1000;
const MATERIAL_DIRECTORY_EXCLUDED_NAMES = new Set([
  ".ds_store", "thumbs.db", "desktop.ini", ".stfolder", "@eadir",
]);
const MATERIAL_DIRECTORY_EXCLUDED_SEGMENTS = new Set([
  "$recycle.bin", "system volume information", "node_modules", "__pycache__",
]);

function isMaterialDirectoryScanOpen() {
  return Boolean(materialDirectoryScanModal && !materialDirectoryScanModal.classList.contains("hidden"));
}

function materialFileCategory(file) {
  const type = String(file?.type || "").toLowerCase();
  const name = String(file?.name || "").toLowerCase();
  const ext = name.includes(".") ? name.slice(name.lastIndexOf(".")) : "";
  if (type.startsWith("image/") || [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"].includes(ext)) return "image";
  if (type.startsWith("video/") || [".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".flv", ".mpeg", ".mpg", ".ts", ".mts", ".m2ts"].includes(ext)) return "video";
  if (type.startsWith("text/") || type === "application/pdf" || type.includes("office") || type.includes("msword") || type.includes("excel") || type.includes("powerpoint") || type.includes("opendocument") || [".pdf", ".txt", ".md", ".rtf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".csv"].includes(ext)) return "document";
  return "other";
}

function materialDirectoryRelativePath(file) {
  return String(file?.webkitRelativePath || file?.name || "").replaceAll("\\", "/");
}

function materialDirectoryExclusionReason(file) {
  const path = materialDirectoryRelativePath(file);
  const parts = path.split("/").filter(Boolean);
  const fileName = String(file?.name || "").toLowerCase();
  if (MATERIAL_DIRECTORY_EXCLUDED_NAMES.has(fileName)) return "系统文件";
  if (parts.some((part, index) => index > 0 && (part.startsWith(".") || MATERIAL_DIRECTORY_EXCLUDED_SEGMENTS.has(part.toLowerCase())))) return "隐藏/系统目录";
  if (!file?.size) return "空文件";
  if (file.size > MAX_LARGE_MATERIAL_BYTES) return "超过 2 TB";
  return "";
}

function materialDirectoryStatusLabel(item) {
  const labels = {
    hashing: "检查重复中",
    ready: item?.file?.size > MAX_ATTACHMENT_BYTES ? "可分块导入" : "可导入",
    queued_large: "大文件已入队",
    uploading_large: "大文件上传中",
    paused_large: "大文件已暂停",
    excluded: item.reason || "已排除",
    duplicate_selection: "目录内重复",
    duplicate_repository: "仓库已存在",
    importing: "导入中",
    imported: "已导入",
    failed: "导入失败",
  };
  return labels[item.status] || item.status || "";
}

function materialDirectoryItemSelectable(item) {
  return item?.status === "ready";
}

function updateMaterialDirectoryScanControls() {
  const selectable = materialDirectoryScanItems.filter(materialDirectoryItemSelectable);
  const selected = selectable.filter((item) => item.selected);
  if (materialDirectorySelectedCount) materialDirectorySelectedCount.textContent = `已选 ${selected.length} 份`;
  if (importScannedMaterialsButton) {
    importScannedMaterialsButton.disabled = selected.length === 0;
    importScannedMaterialsButton.textContent = `导入选中 ${selected.length}`;
  }
  if (materialDirectorySelectAll) {
    materialDirectorySelectAll.disabled = selectable.length === 0;
    materialDirectorySelectAll.checked = selectable.length > 0 && selected.length === selectable.length;
    materialDirectorySelectAll.indeterminate = selected.length > 0 && selected.length < selectable.length;
  }
}

function updateMaterialDirectoryScanSummary() {
  const total = materialDirectoryScanItems.length;
  const ready = materialDirectoryScanItems.filter((item) => item.status === "ready").length;
  const duplicates = materialDirectoryScanItems.filter((item) => item.status === "duplicate_selection" || item.status === "duplicate_repository").length;
  const excluded = materialDirectoryScanItems.filter((item) => item.status === "excluded").length;
  const imported = materialDirectoryScanItems.filter((item) => item.status === "imported").length;
  const folderLabel = materialDirectoryRootName ? `“${materialDirectoryRootName}”` : "所选目录";
  if (materialDirectoryScanSummary) {
    materialDirectoryScanSummary.textContent = `${folderLabel} · ${total} 个文件 · 可导入 ${ready} · 重复 ${duplicates} · 排除 ${excluded}${imported ? ` · 已导入 ${imported}` : ""}`;
  }
  updateMaterialDirectoryScanControls();
}

function renderMaterialDirectoryScanList() {
  if (!materialDirectoryScanList) return;
  materialDirectoryScanList.replaceChildren();
  if (!materialDirectoryScanItems.length) {
    const empty = document.createElement("div");
    empty.className = "material-directory-scan-empty";
    empty.textContent = "没有可显示的扫描结果";
    materialDirectoryScanList.appendChild(empty);
    updateMaterialDirectoryScanSummary();
    return;
  }
  const fragment = document.createDocumentFragment();
  materialDirectoryScanItems.forEach((item) => {
    const row = document.createElement("div");
    row.className = `material-directory-scan-item is-${item.status || "ready"}`;

    const select = document.createElement("input");
    select.type = "checkbox";
    select.checked = Boolean(item.selected && materialDirectoryItemSelectable(item));
    select.disabled = !materialDirectoryItemSelectable(item);
    select.setAttribute("aria-label", `选择 ${item.relativePath || item.file?.name || "资料"}`);
    select.addEventListener("change", () => {
      item.selected = select.checked;
      updateMaterialDirectoryScanControls();
    });

    const main = document.createElement("div");
    main.className = "material-directory-scan-item-main";
    const name = document.createElement("strong");
    name.className = "material-directory-scan-item-name";
    name.textContent = item.file?.name || "未命名资料";
    name.title = item.relativePath || name.textContent;
    const path = document.createElement("span");
    path.className = "material-directory-scan-item-path";
    path.textContent = item.relativePath || name.textContent;
    path.title = path.textContent;
    main.append(name, path);

    const meta = document.createElement("div");
    meta.className = "material-directory-scan-item-meta";
    const modified = Number.isFinite(item.file?.lastModified) && item.file.lastModified > 0
      ? new Date(item.file.lastModified).toLocaleString("zh-CN", { hour12: false })
      : "时间未知";
    meta.textContent = `${materialCenterCategoryLabel(item.category)} · ${formatAttachmentSize(item.file?.size || 0)} · ${modified}`;

    const status = document.createElement("span");
    status.className = `material-directory-scan-status is-${item.status || "ready"}`;
    status.textContent = materialDirectoryStatusLabel(item);
    if (item.status === "duplicate_repository" && item.duplicateName) status.title = `仓库已有：${item.duplicateName}`;
    if (item.status === "failed" && item.errorMessage) status.title = item.errorMessage;

    row.append(select, main, meta, status);
    fragment.appendChild(row);
  });
  materialDirectoryScanList.appendChild(fragment);
  updateMaterialDirectoryScanSummary();
}

function openMaterialDirectoryScanModal() {
  if (!materialDirectoryScanModal) return;
  materialDirectoryScanReturnFocus = document.activeElement;
  materialDirectoryScanModal.classList.remove("hidden");
  materialDirectoryScanModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("material-directory-scan-open");
}

function closeMaterialDirectoryScanModal({ restoreFocus = true } = {}) {
  if (!isMaterialDirectoryScanOpen()) return;
  materialDirectoryScanSequence += 1;
  materialDirectoryScanModal.classList.add("hidden");
  materialDirectoryScanModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("material-directory-scan-open");
  if (materialDirectoryInput) materialDirectoryInput.value = "";
  if (restoreFocus && materialDirectoryScanReturnFocus instanceof HTMLElement && document.contains(materialDirectoryScanReturnFocus)) {
    materialDirectoryScanReturnFocus.focus();
  }
  materialDirectoryScanReturnFocus = null;
}

async function sha256File(file) {
  if (!window.crypto?.subtle || typeof file?.arrayBuffer !== "function") return "";
  const buffer = await file.arrayBuffer();
  const digest = await window.crypto.subtle.digest("SHA-256", buffer);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function checkMaterialDirectoryExistingDuplicates(items) {
  const hashes = Array.from(new Set(items.map((item) => item.sha256).filter(Boolean)));
  if (!hashes.length) return;
  const data = await api("/api/v1/materials/duplicates", {
    method: "POST",
    body: JSON.stringify({ sha256: hashes }),
  }, true);
  const matches = data?.matches || {};
  items.forEach((item) => {
    const existing = item.sha256 ? matches[item.sha256] : null;
    if (!existing?.length || item.status !== "ready") return;
    item.status = "duplicate_repository";
    item.selected = false;
    item.duplicateName = existing[0]?.filename || "已有资料";
  });
}

async function startMaterialDirectoryScan(files) {
  const allFiles = Array.from(files || []);
  if (!allFiles.length) return;
  const sequence = ++materialDirectoryScanSequence;
  const rootPath = materialDirectoryRelativePath(allFiles[0]);
  materialDirectoryRootName = rootPath.includes("/") ? rootPath.split("/")[0] : "所选目录";
  const limited = allFiles.slice(0, MAX_DIRECTORY_SCAN_FILES);
  materialDirectoryScanItems = limited.map((file, index) => {
    const reason = materialDirectoryExclusionReason(file);
    return {
      id: `${index}-${file.name}-${file.size}-${file.lastModified}`,
      file,
      relativePath: materialDirectoryRelativePath(file),
      category: materialFileCategory(file),
      status: reason ? "excluded" : (file.size > MAX_ATTACHMENT_BYTES ? "ready" : "hashing"),
      reason,
      selected: !reason && file.size > MAX_ATTACHMENT_BYTES,
      sha256: "",
      largeUploadSessionId: null,
    };
  });
  openMaterialDirectoryScanModal();
  if (allFiles.length > MAX_DIRECTORY_SCAN_FILES) {
    showToast(`目录包含 ${allFiles.length} 个文件，本次先扫描前 ${MAX_DIRECTORY_SCAN_FILES} 个；可选择更小的子目录继续导入。`, "info");
  }
  if (materialDirectoryScanProgress) materialDirectoryScanProgress.textContent = "正在检查重复…";
  renderMaterialDirectoryScanList();

  const seenHashes = new Map();
  const candidates = materialDirectoryScanItems.filter((item) => item.status === "hashing");
  for (let index = 0; index < candidates.length; index += 1) {
    if (sequence !== materialDirectoryScanSequence) return;
    const item = candidates[index];
    try {
      item.sha256 = await sha256File(item.file);
      if (item.sha256 && seenHashes.has(item.sha256)) {
        item.status = "duplicate_selection";
        item.selected = false;
        item.duplicateName = seenHashes.get(item.sha256)?.file?.name || "同目录文件";
      } else {
        if (item.sha256) seenHashes.set(item.sha256, item);
        item.status = "ready";
        item.selected = true;
      }
    } catch (error) {
      // If browser hashing is unavailable/fails, server-side duplicate rejection
      // during import remains authoritative.
      item.status = "ready";
      item.selected = true;
    }
    if (materialDirectoryScanProgress) materialDirectoryScanProgress.textContent = `检查重复 ${index + 1}/${candidates.length}`;
    if ((index + 1) % 10 === 0 || index === candidates.length - 1) renderMaterialDirectoryScanList();
  }

  if (sequence !== materialDirectoryScanSequence) return;
  try {
    await checkMaterialDirectoryExistingDuplicates(materialDirectoryScanItems);
  } catch (error) {
    showToast(`仓库重复检查未完成：${error.message || "请求失败"}；导入时仍会再次检查。`, "info");
  }
  if (materialDirectoryScanProgress) materialDirectoryScanProgress.textContent = "扫描完成";
  renderMaterialDirectoryScanList();
}

async function importSelectedScannedMaterials() {
  const selected = materialDirectoryScanItems.filter((item) => materialDirectoryItemSelectable(item) && item.selected);
  if (!selected.length || !importScannedMaterialsButton) return;
  setButtonBusy(importScannedMaterialsButton, true, `导入中 0/${selected.length}`);
  let imported = 0;
  let queuedLarge = 0;
  let failed = 0;
  for (let index = 0; index < selected.length; index += 1) {
    const item = selected[index];
    item.status = "importing";
    item.selected = false;
    importScannedMaterialsButton.textContent = `导入中 ${index + 1}/${selected.length}`;
    if (index % 5 === 0) renderMaterialDirectoryScanList();
    try {
      const result = await importIndependentMaterialFile(item.file, {
        sourceRelativePath: item.relativePath,
        sourceDirectoryName: materialDirectoryRootName,
        rejectDuplicate: true,
      });
      if (item.file.size > MAX_ATTACHMENT_BYTES) {
        item.largeUploadSessionId = result.sessionId;
        item.status = result.status === "uploading" ? "uploading_large" : "queued_large";
        queuedLarge += 1;
      } else {
        item.status = "imported";
        imported += 1;
      }
    } catch (error) {
      if (error?.code === "MATERIAL_DUPLICATE") {
        item.status = "duplicate_repository";
        item.duplicateName = "导入时发现仓库已有相同文件";
      } else {
        item.status = "failed";
        item.errorMessage = error?.message || "导入失败";
        failed += 1;
      }
    }
  }
  setButtonBusy(importScannedMaterialsButton, false);
  const queuedText = queuedLarge ? ` · 大文件队列 ${queuedLarge}` : "";
  if (materialDirectoryScanProgress) materialDirectoryScanProgress.textContent = `导入处理完成：立即成功 ${imported}${queuedText}${failed ? ` · 失败 ${failed}` : ""}`;
  renderMaterialDirectoryScanList();
  if (imported) {
    await runMaterialCenterBrowse();
    await refreshContentStatuses();
  }
  if (imported || queuedLarge) {
    showToast(`已导入 ${imported} 份资料${queuedLarge ? `，${queuedLarge} 个大文件进入分块上传队列` : ""}${failed ? `，${failed} 份失败` : ""}`, failed ? "info" : "success");
  } else if (failed) {
    showToast("目录资料导入失败，请查看状态提示", "error");
  }
}

async function deleteIndependentMaterial(attachment, button) {
  if (!attachment?.is_independent) return;
  const confirmed = await askConfirmation({
    eyebrow: "删除独立资料",
    title: `删除“${attachment.filename || "未命名资料"}”吗？`,
    message: "这个操作不会删除任何事件、记忆或计划，但资料文件本身会从本地加密仓库中永久删除。",
    confirmLabel: "删除资料",
    tone: "danger",
  });
  if (!confirmed) return;
  setButtonBusy(button, true, "删除中…");
  try {
    await api(`/api/v1/materials/${encodeURIComponent(attachment.id)}`, { method: "DELETE" }, true);
    releaseAttachmentObjectUrl(attachment.id);
    if (videoPlayerAttachment?.id === attachment.id) closeVideoPlayer({ restoreFocus: false });
    showToast("独立资料已删除", "success");
    await runMaterialCenterBrowse();
    await refreshContentStatuses();
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

async function assignAttachmentTimelineFallback(attachment, button, { refreshMaterialCenter = false } = {}) {
  setButtonBusy(button, true, "归入中…");
  try {
    const updated = await api(
      `/api/v1/attachments/${encodeURIComponent(attachment.id)}/timeline-fallback`,
      { method: "POST" },
      true,
    );
    Object.assign(attachment, updated);
    showToast(`已归入 ${updated.timeline_date || "可用日期"}`, "success");
    if (refreshMaterialCenter) await runMaterialCenterBrowse();
    return updated;
  } catch (error) {
    showOperationError(error);
    return null;
  } finally {
    setButtonBusy(button, false);
  }
}

function updateMaterialTimeReviewButton() {
  if (!reviewMaterialTimeButton) return;
  const active = materialCenterTimeStatus === "review";
  reviewMaterialTimeButton.classList.toggle("is-active", active);
  reviewMaterialTimeButton.setAttribute("aria-pressed", active ? "true" : "false");
}

async function openMaterialTimeReviewList() {
  materialCenterTimeStatus = materialCenterTimeStatus === "review" ? "all" : "review";
  updateMaterialTimeReviewButton();
  if (materialCenterTimeStatus === "review") {
    materialCenterQuery.value = "";
    materialCenterDateFrom.value = "";
    materialCenterDateTo.value = "";
    setMaterialCenterViewMode("list", { rerender: false });
  }
  await runMaterialCenterBrowse();
}

function isMaterialTimeCorrectionOpen() {
  return Boolean(materialTimeCorrectionModal && !materialTimeCorrectionModal.classList.contains("hidden"));
}

function closeMaterialTimeCorrectionModal({ restoreFocus = true } = {}) {
  if (!isMaterialTimeCorrectionOpen()) return;
  materialTimeCorrectionModal.classList.add("hidden");
  materialTimeCorrectionModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("material-time-correction-open");
  materialTimeCorrectionAttachment = null;
  if (restoreFocus && materialTimeCorrectionReturnFocus instanceof HTMLElement && document.contains(materialTimeCorrectionReturnFocus)) {
    materialTimeCorrectionReturnFocus.focus({ preventScroll: true });
  }
  materialTimeCorrectionReturnFocus = null;
}

function openMaterialTimeCorrectionModal(attachment, trigger = null) {
  if (!materialTimeCorrectionModal || !attachment) return;
  materialTimeCorrectionAttachment = attachment;
  materialTimeCorrectionReturnFocus = trigger instanceof HTMLElement ? trigger : document.activeElement;
  materialTimeCorrectionFilename.textContent = attachment.filename || "未命名资料";
  materialTimeCorrectionCurrent.textContent = attachment.timeline_date
    ? `当前：${attachmentTimelineLabel(attachment) || attachment.timeline_date} · ${attachmentTimelineSourceLabel(attachment)}`
    : "当前：时间待确认";
  materialTimeCorrectionDate.value = String(attachment.timeline_date || currentProgress?.today || "").slice(0, 10);
  const precision = String(attachment.time_precision || "");
  const rawTime = String(attachment.timeline_at || "");
  materialTimeCorrectionTime.value = ["minute", "second"].includes(precision) && rawTime.includes("T")
    ? rawTime.slice(11, 19)
    : "";
  materialTimeCorrectionModal.classList.remove("hidden");
  materialTimeCorrectionModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("material-time-correction-open");
  requestAnimationFrame(() => materialTimeCorrectionDate?.focus());
}

async function saveMaterialTimeCorrection(event) {
  event.preventDefault();
  if (!materialTimeCorrectionAttachment || !materialTimeCorrectionForm) return;
  const submit = materialTimeCorrectionForm.querySelector('button[type="submit"]');
  if (!materialTimeCorrectionDate.value) {
    showToast("请选择资料日期", "error");
    materialTimeCorrectionDate.focus();
    return;
  }
  setButtonBusy(submit, true, "保存中…");
  try {
    const updated = await api(
      `/api/v1/attachments/${encodeURIComponent(materialTimeCorrectionAttachment.id)}/timeline`,
      {
        method: "PUT",
        body: JSON.stringify({
          timeline_date: materialTimeCorrectionDate.value,
          timeline_time: materialTimeCorrectionTime.value || null,
        }),
      },
      true,
    );
    Object.assign(materialTimeCorrectionAttachment, updated);
    closeMaterialTimeCorrectionModal({ restoreFocus: false });
    showToast(`资料时间已修正为 ${updated.timeline_date}`, "success");
    await Promise.all([runMaterialCenterBrowse(), refreshContentStatuses()]);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(submit, false);
  }
}

function ensureMaterialThumbnailObserver() {
  if (materialThumbnailObserver || typeof IntersectionObserver === "undefined") return materialThumbnailObserver;
  materialThumbnailObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      const loader = entry.target._lifegraphThumbnailLoader;
      if (typeof loader === "function") loader();
    });
  }, { root: materialCenterResults || null, rootMargin: "240px 0px", threshold: 0.01 });
  return materialThumbnailObserver;
}

function observeMaterialThumbnail(button, loader) {
  button._lifegraphThumbnailLoader = loader;
  const observer = ensureMaterialThumbnailObserver();
  if (observer) observer.observe(button);
  else loader();
}

function resetMaterialCenterPaging() {
  materialCenterBrowseParams = null;
  materialCenterLoadingMore = false;
  materialCenterLoadObserver?.disconnect();
  materialCenterLoadObserver = null;
}

function appendMaterialCenterLoadSentinel(data) {
  materialCenterLoadObserver?.disconnect();
  materialCenterLoadObserver = null;
  if (!data?.has_more || !materialCenterResults) return;
  const sentinel = document.createElement("div");
  sentinel.className = "material-center-load-sentinel";
  sentinel.textContent = materialCenterLoadingMore ? "正在加载更多资料……" : "继续向下滚动加载更多";
  materialCenterResults.appendChild(sentinel);
  if (typeof IntersectionObserver === "undefined") return;
  materialCenterLoadObserver = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) loadMoreMaterialCenterResults();
  }, { root: materialCenterResults, rootMargin: "360px 0px", threshold: 0.01 });
  materialCenterLoadObserver.observe(sentinel);
}

function isLargeMediaOffline(attachment) {
  return Boolean(attachment?.is_large && attachment?.media_available === false);
}

function mediaAvailabilityLabel(attachment) {
  if (!isLargeMediaOffline(attachment)) return "";
  const state = String(attachment?.media_state || "offline");
  if (state === "incomplete") return "媒体不完整";
  if (state === "invalid") return "媒体异常";
  return "媒体离线";
}

function applyMediaAvailabilityToButton(button, attachment, normalLabel) {
  if (!button) return;
  if (!isLargeMediaOffline(attachment)) return;
  button.disabled = true;
  button.textContent = mediaAvailabilityLabel(attachment);
  button.title = `${normalLabel}不可用：请恢复 data/media 媒体库后重试`;
}

function createMaterialCenterCard(attachment, imageItems, imageIndexById, { timeline = false } = {}) {
  const card = document.createElement("article");
  card.className = `material-center-card-item is-${attachment.category || "other"}${timeline ? " is-timeline" : ""}`;
  card.classList.toggle("is-media-offline", isLargeMediaOffline(attachment));
  if (attachment.id) card.dataset.attachmentId = String(attachment.id);

  if (isImageAttachment(attachment)) {
    const thumbnail = createAttachmentThumbnail(
      attachment,
      imageItems,
      imageIndexById.get(attachment.id) || 0,
      { lazy: true },
    );
    thumbnail.classList.add("material-center-thumbnail");
    card.appendChild(thumbnail);
  } else if (isVideoAttachment(attachment) && attachment.has_preview) {
    const thumbnail = createVideoThumbnail(attachment, { lazy: true });
    thumbnail.classList.add("material-center-thumbnail");
    card.appendChild(thumbnail);
  } else {
    const icon = document.createElement("div");
    icon.className = `material-center-file-icon is-${attachment.category || "other"}`;
    icon.textContent = attachment.category === "document" ? "文" : (attachment.category === "video" ? "影" : "档");
    card.appendChild(icon);
  }

  const main = document.createElement("div");
  main.className = "material-center-item-main";
  const titleRow = document.createElement("div");
  titleRow.className = "material-center-item-title-row";
  const title = document.createElement("strong");
  title.className = "material-center-item-name";
  title.textContent = attachment.filename || "未命名资料";
  title.title = title.textContent;
  const badge = document.createElement("span");
  badge.className = `material-center-category-badge is-${attachment.category || "other"}`;
  badge.textContent = materialCenterCategoryLabel(attachment.category);
  titleRow.append(title, badge);

  const meta = document.createElement("p");
  meta.className = "material-center-item-meta";
  const timelineMeta = timeline ? "" : (attachmentTimelineLabel(attachment) || "资料日期未识别");
  meta.textContent = [
    formatAttachmentSize(attachment.size_bytes),
    attachment.media_type || "文件",
    ...videoTechnicalMetaParts(attachment),
    mediaAvailabilityLabel(attachment),
    timelineMeta,
  ].filter(Boolean).join(" · ");
  meta.title = meta.textContent;

  const relation = document.createElement("div");
  relation.className = "material-center-item-relation";
  const source = attachment.source_content;
  if (source?.period_key) {
    const sourceButton = document.createElement("button");
    sourceButton.type = "button";
    sourceButton.className = "material-center-source-button";
    sourceButton.textContent = `来自 ${source.period_key} · ${materialSourceKindLabel(source.kind)}：${source.title || "未命名内容"}`;
    sourceButton.title = sourceButton.textContent;
    sourceButton.addEventListener("click", () => openMaterialCenterPeriod(
      source.time_scope || "day",
      source.period_key,
      sourceButton,
      source,
    ));
    relation.appendChild(sourceButton);
  } else if (attachment.is_independent) {
    const independent = document.createElement("span");
    independent.className = "material-center-independent-label";
    if (attachment.material_origin === "directory_import" && attachment.source_relative_path) {
      independent.textContent = `目录导入 · ${attachment.source_relative_path}`;
    } else {
      independent.textContent = "独立资料 · 直接导入人生资料库";
    }
    independent.title = independent.textContent;
    independent.title = "这份资料目前不依附任何事件、记忆或计划";
    relation.appendChild(independent);
  }
  main.append(titleRow, meta, relation);

  const actions = document.createElement("div");
  actions.className = "material-center-item-actions";
  if (!timeline && attachment.timeline_date) {
    const dateButton = document.createElement("button");
    dateButton.type = "button";
    dateButton.className = "ghost-button material-center-date-button";
    dateButton.textContent = `时间轴 ${attachment.timeline_date}`;
    dateButton.title = `${attachmentTimelineSourceLabel(attachment)} · 打开资料归属日期`;
    dateButton.addEventListener("click", () => openMaterialCenterPeriod("day", attachment.timeline_date, dateButton));
    actions.appendChild(dateButton);
  } else if (!attachment.timeline_date) {
    const fallbackButton = document.createElement("button");
    fallbackButton.type = "button";
    fallbackButton.className = "ghost-button material-center-fallback-button";
    fallbackButton.textContent = "归入来源/添加时间";
    fallbackButton.title = "优先归入来源内容的明确日期；否则使用附件添加时间";
    fallbackButton.addEventListener("click", () => assignAttachmentTimelineFallback(
      attachment,
      fallbackButton,
      { refreshMaterialCenter: true },
    ));
    actions.appendChild(fallbackButton);
  }
  if (!timeline) {
    const correctTimeButton = document.createElement("button");
    correctTimeButton.type = "button";
    correctTimeButton.className = "ghost-button material-center-time-correct-button";
    correctTimeButton.textContent = "修正时间";
    correctTimeButton.title = "手工确认这份资料在人生时间轴中的日期与具体时间";
    correctTimeButton.addEventListener("click", () => openMaterialTimeCorrectionModal(attachment, correctTimeButton));
    actions.appendChild(correctTimeButton);
  }
  if (attachment.is_independent) {
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "ghost-button material-center-delete-button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => deleteIndependentMaterial(attachment, deleteButton));
    actions.appendChild(deleteButton);
  }
  if (isVideoAttachment(attachment)) {
    const playButton = document.createElement("button");
    playButton.type = "button";
    playButton.className = "ghost-button material-center-play-button";
    playButton.textContent = "播放";
    applyMediaAvailabilityToButton(playButton, attachment, "播放");
    playButton.addEventListener("click", () => openVideoPlayer(attachment, playButton));
    actions.appendChild(playButton);
  }
  const download = document.createElement("button");
  download.type = "button";
  download.className = "ghost-button";
  download.textContent = "下载";
  applyMediaAvailabilityToButton(download, attachment, "下载");
  download.addEventListener("click", async () => {
    setButtonBusy(download, true, "准备中…");
    try {
      await downloadAttachmentFile(attachment);
    } catch (error) {
      showOperationError(error);
    } finally {
      setButtonBusy(download, false);
    }
  });
  actions.appendChild(download);

  card.append(main, actions);
  return card;
}

function materialTimelineNodeSummary(items = []) {
  const imageCount = items.filter((item) => item.category === "image").length;
  const fileCount = items.length - imageCount;
  const parts = [];
  if (imageCount) parts.push(`${imageCount} 张照片`);
  if (fileCount) parts.push(`${fileCount} 个文件`);
  return parts.join(" · ") || `${items.length} 份资料`;
}

function bindMaterialTimelineCollapse(grid, items, toggleHost, imageItems, imageIndexById) {
  const cards = items.map((attachment) =>
    createMaterialCenterCard(attachment, imageItems, imageIndexById, { timeline: true }),
  );
  cards.forEach((card, index) => {
    card.classList.toggle("hidden", index >= MATERIAL_SECTION_COLLAPSED_LIMIT);
    grid.appendChild(card);
  });

  if (items.length <= MATERIAL_SECTION_COLLAPSED_LIMIT) return;

  let expanded = false;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "material-timeline-toggle";
  toggle.textContent = `展开全部（${items.length}）`;
  toggle.setAttribute("aria-expanded", "false");
  toggle.addEventListener("click", () => {
    expanded = !expanded;
    cards.forEach((card, index) => {
      card.classList.toggle("hidden", !expanded && index >= MATERIAL_SECTION_COLLAPSED_LIMIT);
    });
    toggle.textContent = expanded ? "收起" : `展开全部（${items.length}）`;
    toggle.setAttribute("aria-expanded", String(expanded));
  });
  toggleHost.appendChild(toggle);
}

function renderMaterialCenterTimeline(items, imageItems, imageIndexById) {
  materialCenterResults.classList.add("is-timeline-view");
  const timeline = document.createElement("div");
  timeline.className = "material-center-timeline";

  const dated = items.filter((item) => item.timeline_date);
  const undated = items.filter((item) => !item.timeline_date);
  const ascending = materialCenterSort?.value === "timeline_asc";
  dated.sort((left, right) => {
    const a = String(left.timeline_at || left.timeline_date || "");
    const b = String(right.timeline_at || right.timeline_date || "");
    return ascending ? a.localeCompare(b) : b.localeCompare(a);
  });

  const years = new Map();
  dated.forEach((attachment) => {
    const [year, month] = String(attachment.timeline_date).split("-");
    if (!years.has(year)) years.set(year, new Map());
    const months = years.get(year);
    if (!months.has(month)) months.set(month, new Map());
    const dates = months.get(month);
    if (!dates.has(attachment.timeline_date)) dates.set(attachment.timeline_date, []);
    dates.get(attachment.timeline_date).push(attachment);
  });

  years.forEach((months, year) => {
    const yearSection = document.createElement("section");
    yearSection.className = "material-timeline-year";

    const yearItems = [];
    months.forEach((dates) => {
      dates.forEach((dateItems) => yearItems.push(...dateItems));
    });

    const yearHeading = document.createElement("div");
    yearHeading.className = "material-timeline-year-heading";
    const yearHeadingText = document.createElement("h3");
    yearHeadingText.className = "material-timeline-year-title";
    yearHeadingText.textContent = `${year} 年 · ${yearItems.length} 份资料`;
    const yearToggle = document.createElement("button");
    yearToggle.type = "button";
    yearToggle.className = "material-timeline-year-toggle";
    yearToggle.textContent = "收起年度";
    yearToggle.setAttribute("aria-expanded", "true");
    yearHeading.append(yearHeadingText, yearToggle);
    yearSection.appendChild(yearHeading);

    const yearBody = document.createElement("div");
    yearBody.className = "material-timeline-year-body";
    let yearExpanded = true;
    yearToggle.addEventListener("click", () => {
      yearExpanded = !yearExpanded;
      yearBody.classList.toggle("hidden", !yearExpanded);
      yearToggle.textContent = yearExpanded ? "收起年度" : `展开年度（${yearItems.length}）`;
      yearToggle.setAttribute("aria-expanded", String(yearExpanded));
    });

    months.forEach((dates, month) => {
      const monthSection = document.createElement("section");
      monthSection.className = "material-timeline-month";

      const monthItems = [];
      dates.forEach((dateItems) => monthItems.push(...dateItems));

      const monthHeading = document.createElement("div");
      monthHeading.className = "material-timeline-month-heading";
      const monthHeadingText = document.createElement("h4");
      monthHeadingText.className = "material-timeline-month-title";
      monthHeadingText.textContent = `${Number(month)} 月 · ${monthItems.length} 份资料`;
      const monthToggle = document.createElement("button");
      monthToggle.type = "button";
      monthToggle.className = "material-timeline-month-toggle";
      monthToggle.textContent = "收起月份";
      monthToggle.setAttribute("aria-expanded", "true");
      monthHeading.append(monthHeadingText, monthToggle);
      monthSection.appendChild(monthHeading);

      const monthBody = document.createElement("div");
      monthBody.className = "material-timeline-month-body";
      let monthExpanded = true;
      monthToggle.addEventListener("click", () => {
        monthExpanded = !monthExpanded;
        monthBody.classList.toggle("hidden", !monthExpanded);
        monthToggle.textContent = monthExpanded ? "收起月份" : `展开月份（${monthItems.length}）`;
        monthToggle.setAttribute("aria-expanded", String(monthExpanded));
      });

      dates.forEach((dateItems, timelineDate) => {
        const row = document.createElement("div");
        row.className = "material-timeline-date-row";
        row.dataset.timelineDate = String(timelineDate);
        const rail = document.createElement("div");
        rail.className = "material-timeline-date-rail";
        const dateButton = document.createElement("button");
        dateButton.type = "button";
        dateButton.className = "material-timeline-date-button";
        dateButton.textContent = timelineDate.slice(5);
        dateButton.title = `打开 ${timelineDate} 人生详情`;
        dateButton.addEventListener("click", () => openMaterialCenterPeriod("day", timelineDate, dateButton));
        const dot = document.createElement("span");
        dot.className = "material-timeline-dot";
        dot.setAttribute("aria-hidden", "true");
        rail.append(dateButton, dot);

        const body = document.createElement("div");
        body.className = "material-timeline-date-body";
        const nodeHeader = document.createElement("div");
        nodeHeader.className = "material-timeline-node-header";
        const nodeMeta = document.createElement("div");
        nodeMeta.className = "material-timeline-node-meta";
        nodeMeta.textContent = materialTimelineNodeSummary(dateItems);
        nodeHeader.appendChild(nodeMeta);
        const grid = document.createElement("div");
        grid.className = "material-timeline-grid";
        bindMaterialTimelineCollapse(grid, dateItems, nodeHeader, imageItems, imageIndexById);
        body.append(nodeHeader, grid);
        row.append(rail, body);
        monthBody.appendChild(row);
      });
      monthSection.appendChild(monthBody);
      yearBody.appendChild(monthSection);
    });
    yearSection.appendChild(yearBody);
    timeline.appendChild(yearSection);
  });

  if (undated.length) {
    const unknown = document.createElement("section");
    unknown.className = "material-timeline-undated";
    const heading = document.createElement("div");
    heading.className = "material-timeline-year-heading material-timeline-undated-heading";
    const headingText = document.createElement("h3");
    headingText.className = "material-timeline-undated-title";
    headingText.textContent = "时间未识别";
    heading.appendChild(headingText);
    const grid = document.createElement("div");
    grid.className = "material-timeline-grid material-timeline-undated-grid";
    bindMaterialTimelineCollapse(grid, undated, heading, imageItems, imageIndexById);
    unknown.append(heading, grid);
    timeline.appendChild(unknown);
  }
  materialCenterResults.appendChild(timeline);
}

function materialTimelineLifeYearBounds() {
  if (currentProgress?.birth_date && currentProgress?.target_date) {
    const birth = parseIsoDate(currentProgress.birth_date);
    const target = addUtcDays(parseIsoDate(currentProgress.target_date), -1);
    return {
      startYear: birth.getUTCFullYear(),
      endYear: target.getUTCFullYear(),
    };
  }
  const currentYear = new Date().getFullYear();
  return { startYear: currentYear - 50, endYear: currentYear + 49 };
}

function materialTimelineDefaultDate() {
  if (currentProgress?.today) return String(currentProgress.today).slice(0, 10);
  return new Date().toISOString().slice(0, 10);
}

function resetMaterialTimelineDayViewState() {
  materialTimelineExpandedMinuteGroups.clear();
  materialTimelineDayLoadingMore = false;
}

function resetMaterialTimelineAxisToToday() {
  const { startYear, endYear } = materialTimelineLifeYearBounds();
  const defaultDate = materialTimelineDefaultDate();
  const [defaultYear, defaultMonth] = defaultDate.split("-").map(Number);
  materialTimelineAxisYear = Math.min(endYear, Math.max(startYear, Number.isInteger(defaultYear) ? defaultYear : new Date().getFullYear()));
  materialTimelineAxisMonth = Number.isInteger(defaultMonth) && defaultMonth >= 1 && defaultMonth <= 12 ? defaultMonth : 1;
  materialTimelineAxisDay = null;
  materialTimelineAxisAutoResolve = "year";
  materialTimelineYearWindowStart = null;
  resetMaterialTimelineDayViewState();
}

function initializeMaterialTimelineAxis() {
  const { startYear, endYear } = materialTimelineLifeYearBounds();
  const defaultDate = materialTimelineDefaultDate();
  const [defaultYear, defaultMonth] = defaultDate.split("-").map(Number);
  if (!Number.isInteger(materialTimelineAxisYear) || materialTimelineAxisYear < startYear || materialTimelineAxisYear > endYear) {
    materialTimelineAxisYear = Math.min(endYear, Math.max(startYear, defaultYear));
  }
  if (!Number.isInteger(materialTimelineAxisMonth) || materialTimelineAxisMonth < 1 || materialTimelineAxisMonth > 12) {
    materialTimelineAxisMonth = Number.isInteger(defaultMonth) ? defaultMonth : 1;
  }
  if (materialTimelineAxisDay !== null && (!Number.isInteger(materialTimelineAxisDay) || materialTimelineAxisDay < 1 || materialTimelineAxisDay > 31)) {
    materialTimelineAxisDay = null;
  }
}

function materialTimelineYearWindowCapacity() {
  const available = Math.max(420, Number(materialCenterResults?.clientWidth || 0));
  const usable = Math.max(320, available - 104);
  let capacity = Math.floor(usable / MATERIAL_TIMELINE_YEAR_MIN_WIDTH);
  capacity = Math.max(MATERIAL_TIMELINE_YEAR_MIN_ITEMS, Math.min(MATERIAL_TIMELINE_YEAR_MAX_ITEMS, capacity));
  if (capacity % 2 === 0 && capacity > MATERIAL_TIMELINE_YEAR_MIN_ITEMS) capacity -= 1;
  return capacity;
}

function materialTimelineYearWindowForSelection({ recenter = false } = {}) {
  initializeMaterialTimelineAxis();
  const { startYear, endYear } = materialTimelineLifeYearBounds();
  const capacity = Math.min(materialTimelineYearWindowCapacity(), endYear - startYear + 1);
  const maxStart = Math.max(startYear, endYear - capacity + 1);
  if (materialTimelineYearWindowStart === null || recenter) {
    materialTimelineYearWindowStart = materialTimelineAxisYear - Math.floor(capacity / 2);
  }
  materialTimelineYearWindowStart = Math.max(startYear, Math.min(maxStart, materialTimelineYearWindowStart));
  return {
    startYear: materialTimelineYearWindowStart,
    endYear: Math.min(endYear, materialTimelineYearWindowStart + capacity - 1),
    capacity,
    lifeStartYear: startYear,
    lifeEndYear: endYear,
  };
}

function materialTimelineDensityClass(count, maxCount) {
  const value = Number(count || 0);
  if (value <= 0) return "is-empty";
  if (maxCount <= 0) return "is-low";
  const ratio = value / maxCount;
  if (ratio >= 0.66) return "is-high";
  if (ratio >= 0.25) return "is-medium";
  return "is-low";
}

function createMaterialTimelineAxisTick(item, { level, maxCount }) {
  const button = document.createElement("button");
  button.type = "button";
  const totalCount = Number(item.total_count || 0);
  const hasData = totalCount > 0;
  button.className = `material-time-axis-tick ${materialTimelineDensityClass(totalCount, maxCount)}`;
  const value = level === "year" ? Number(item.year) : level === "month" ? Number(item.month) : Number(item.day);
  const selected = level === "year"
    ? value === materialTimelineAxisYear
    : level === "month"
      ? value === materialTimelineAxisMonth
      : value === materialTimelineAxisDay;
  button.classList.toggle("is-selected", selected && hasData);
  button.dataset.periodKey = String(item.period_key || "");
  button.disabled = !hasData;
  button.setAttribute("aria-disabled", String(!hasData));
  button.title = hasData ? `${item.period_key} · ${totalCount} 份资料` : `${item.period_key} · 暂无资料`;

  const label = document.createElement("span");
  label.className = "material-time-axis-label";
  const valueLabel = document.createElement("span");
  valueLabel.className = "material-time-axis-label-value";
  valueLabel.textContent = level === "year" ? String(value) : level === "month" ? `${value}月` : String(value);
  label.appendChild(valueLabel);
  if (hasData) {
    const inlineCount = document.createElement("span");
    inlineCount.className = "material-time-axis-inline-count";
    inlineCount.textContent = `[${totalCount}]`;
    label.appendChild(inlineCount);
  }
  button.appendChild(label);

  if (hasData) {
    button.addEventListener("click", () => {
      resetMaterialTimelineDayViewState();
      if (level === "year") {
        materialTimelineAxisYear = value;
        materialTimelineAxisDay = null;
        materialTimelineAxisAutoResolve = "year";
        materialTimelineYearWindowStart = materialTimelineYearWindowForSelection({ recenter: true }).startYear;
      } else if (level === "month") {
        materialTimelineAxisMonth = value;
        materialTimelineAxisDay = null;
        materialTimelineAxisAutoResolve = "month";
      } else {
        materialTimelineAxisDay = value;
        materialTimelineAxisAutoResolve = null;
      }
      runMaterialTimelineAxis();
    });
  }
  return button;
}

function createMaterialTimelineAxisRow({ level, items, yearWindow = null }) {
  const row = document.createElement("section");
  row.className = `material-time-axis-row is-${level}`;

  const name = document.createElement("strong");
  name.className = "material-time-axis-row-name";
  name.textContent = level === "year" ? "年" : level === "month" ? "月" : "日";
  row.appendChild(name);

  const previousSlot = document.createElement("div");
  previousSlot.className = "material-time-axis-page-slot";
  if (level === "year" && yearWindow) {
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "material-time-axis-page-button is-previous";
    previous.textContent = "‹";
    previous.title = "显示更早年份";
    previous.disabled = yearWindow.startYear <= yearWindow.lifeStartYear;
    previous.addEventListener("click", () => {
      const shift = Math.max(1, Math.floor(yearWindow.capacity / 2));
      materialTimelineYearWindowStart = Math.max(yearWindow.lifeStartYear, yearWindow.startYear - shift);
      runMaterialTimelineAxis();
    });
    previousSlot.appendChild(previous);
  }
  row.appendChild(previousSlot);

  const track = document.createElement("div");
  track.className = "material-time-axis-track";
  track.style.setProperty("--axis-items", String(Math.max(1, items.length)));
  const maxCount = Math.max(0, ...items.map((item) => Number(item.total_count || 0)));
  items.forEach((item) => track.appendChild(createMaterialTimelineAxisTick(item, { level, maxCount })));
  row.appendChild(track);

  const nextSlot = document.createElement("div");
  nextSlot.className = "material-time-axis-page-slot";
  if (level === "year" && yearWindow) {
    const next = document.createElement("button");
    next.type = "button";
    next.className = "material-time-axis-page-button is-next";
    next.textContent = "›";
    next.title = "显示更晚年份";
    next.disabled = yearWindow.endYear >= yearWindow.lifeEndYear;
    next.addEventListener("click", () => {
      const shift = Math.max(1, Math.floor(yearWindow.capacity / 2));
      const maxStart = Math.max(yearWindow.lifeStartYear, yearWindow.lifeEndYear - yearWindow.capacity + 1);
      materialTimelineYearWindowStart = Math.min(maxStart, yearWindow.startYear + shift);
      runMaterialTimelineAxis();
    });
    nextSlot.appendChild(next);
  }
  row.appendChild(nextSlot);
  return row;
}

function materialDayTimelineTimeText(value, precision = "") {
  const text = String(value || "").trim();
  const normalizedPrecision = String(precision || "").trim().toLowerCase();
  const match = text.match(/T(\d{2}):(\d{2})(?::(\d{2}))?/);
  if (!match || ["year", "month", "day", "unknown"].includes(normalizedPrecision)) return "";
  if (normalizedPrecision === "minute") return `${match[1]}:${match[2]}`;
  return `${match[1]}:${match[2]}:${match[3] || "00"}`;
}

function materialDayTimelineCategoryIcon(attachment) {
  if (isImageAttachment(attachment)) return "图";
  if (isVideoAttachment(attachment)) return "影";
  if (attachment?.category === "document") return "文";
  return "档";
}

function materialDayTimelineCategoryLabel(attachment) {
  if (isImageAttachment(attachment)) return "图片";
  if (isVideoAttachment(attachment)) return "视频";
  return materialCenterCategoryLabel(attachment?.category || "other");
}

function createMaterialDayTimelineAction(attachment, allItems, itemIndex) {
  const action = document.createElement("button");
  action.type = "button";
  action.className = "ghost-button material-day-time-action";
  if (isImageAttachment(attachment)) {
    action.textContent = "查看";
    action.addEventListener("click", () => openAttachmentPreview(allItems, itemIndex, action));
    return action;
  }
  if (isVideoAttachment(attachment)) {
    action.textContent = "播放";
    action.addEventListener("click", () => openVideoPlayer(attachment, action));
    return action;
  }
  action.textContent = "下载";
  action.addEventListener("click", async () => {
    setButtonBusy(action, true, "准备中…");
    try {
      await downloadAttachmentFile(attachment);
    } catch (error) {
      showOperationError(error);
    } finally {
      setButtonBusy(action, false);
    }
  });
  return action;
}

function createMaterialDayTimelineEntry(attachment, allItems, itemIndex) {
  const row = document.createElement("article");
  row.className = "material-day-time-entry";
  row.dataset.attachmentId = String(attachment.id || "");

  const point = document.createElement("span");
  point.className = `material-day-time-point is-${attachment.category || "other"}`;
  point.setAttribute("aria-hidden", "true");

  const card = document.createElement("div");
  card.className = "material-day-time-card";

  const top = document.createElement("div");
  top.className = "material-day-time-card-top";
  const time = document.createElement("time");
  time.className = "material-day-time-value";
  time.textContent = materialDayTimelineTimeText(attachment.timeline_at, attachment.time_precision) || "时间未精确";
  if (attachment.timeline_at) time.dateTime = String(attachment.timeline_at);
  const badge = document.createElement("span");
  badge.className = `material-day-time-kind is-${attachment.category || "other"}`;
  badge.textContent = materialDayTimelineCategoryLabel(attachment);
  top.append(time, badge);

  const name = document.createElement("strong");
  name.className = "material-day-time-filename";
  name.textContent = attachment.filename || "未命名资料";
  name.title = name.textContent;

  const meta = document.createElement("div");
  meta.className = "material-day-time-meta";
  const metaParts = [formatAttachmentSize(attachment.size_bytes)];
  if (isVideoAttachment(attachment) && attachment.duration_seconds !== null && attachment.duration_seconds !== undefined) {
    const duration = formatVideoDuration(attachment.duration_seconds);
    if (duration) metaParts.push(`时长 ${duration}`);
  }
  const endTime = materialDayTimelineTimeText(attachment.timeline_end_at, "second");
  if (endTime) metaParts.push(`至 ${endTime}`);
  meta.textContent = metaParts.join(" · ");

  const action = createMaterialDayTimelineAction(attachment, allItems, itemIndex);
  card.append(top, name, meta, action);
  row.append(point, card);
  return row;
}

function materialDayTimelineBucketMode(minuteItems) {
  const occupiedMinutes = Array.isArray(minuteItems) ? minuteItems.length : 0;
  if (occupiedMinutes > 720) return "hour";
  if (occupiedMinutes > 240) return "ten-minute";
  return "minute";
}

function materialDayTimelineBucketKey(timeText, mode) {
  const match = String(timeText || "").match(/^(\d{2}):(\d{2})/);
  if (!match) return "";
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (mode === "hour") return `${String(hour).padStart(2, "0")}:00`;
  if (mode === "ten-minute") {
    const bucketMinute = Math.floor(minute / 10) * 10;
    return `${String(hour).padStart(2, "0")}:${String(bucketMinute).padStart(2, "0")}`;
  }
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function materialDayTimelineBucketLabel(key, mode) {
  const match = String(key || "").match(/^(\d{2}):(\d{2})$/);
  if (!match) return key || "时间段";
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  if (mode === "hour") return `${match[1]}:00–${match[1]}:59`;
  if (mode === "ten-minute") {
    const endMinute = Math.min(59, minute + 9);
    return `${match[1]}:${match[2]}–${match[1]}:${String(endMinute).padStart(2, "0")}`;
  }
  return `${match[1]}:${match[2]}`;
}

function materialDayTimelineMinuteBucketCounts(dayData, mode) {
  const counts = new Map();
  const minuteItems = Array.isArray(dayData?.minutes?.items) ? dayData.minutes.items : [];
  minuteItems.forEach((item) => {
    const timeText = String(item?.time || String(item?.period_key || "").slice(11, 16));
    const key = materialDayTimelineBucketKey(timeText, mode);
    if (!key) return;
    counts.set(key, Number(counts.get(key) || 0) + Number(item?.total_count || 0));
  });
  return counts;
}

function createMaterialDayTimelineGroupItem({ item, index, allItems }) {
  const row = document.createElement("div");
  row.className = "material-day-time-group-item";

  const time = document.createElement("time");
  time.className = "material-day-time-value";
  time.textContent = materialDayTimelineTimeText(item.timeline_at, item.time_precision) || "时间未精确";
  if (item.timeline_at) time.dateTime = String(item.timeline_at);

  const kind = document.createElement("span");
  kind.className = `material-day-time-kind is-${item.category || "other"}`;
  kind.textContent = materialDayTimelineCategoryLabel(item);

  const name = document.createElement("strong");
  name.className = "material-day-time-filename";
  name.textContent = item.filename || "未命名资料";
  name.title = name.textContent;

  const meta = document.createElement("span");
  meta.className = "material-day-time-meta";
  const metaParts = [formatAttachmentSize(item.size_bytes)];
  if (isVideoAttachment(item) && item.duration_seconds !== null && item.duration_seconds !== undefined) {
    const duration = formatVideoDuration(item.duration_seconds);
    if (duration) metaParts.push(`时长 ${duration}`);
  }
  meta.textContent = metaParts.join(" · ");

  row.append(time, kind, name, meta, createMaterialDayTimelineAction(item, allItems, index));
  return row;
}

function createMaterialDayTimelineGroup({ key, mode, totalCount, loadedEntries, allItems }) {
  const row = document.createElement("article");
  row.className = "material-day-time-group";
  row.dataset.bucketKey = key;

  const point = document.createElement("span");
  point.className = "material-day-time-point is-group";
  point.setAttribute("aria-hidden", "true");

  const card = document.createElement("div");
  card.className = "material-day-time-group-card";

  const groupId = `${materialTimelineAxisYear}-${String(materialTimelineAxisMonth).padStart(2, "0")}-${String(materialTimelineAxisDay).padStart(2, "0")}T${key}/${mode}`;
  const expanded = materialTimelineExpandedMinuteGroups.has(groupId);

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "material-day-time-group-toggle";
  toggle.setAttribute("aria-expanded", String(expanded));

  const label = document.createElement("strong");
  label.textContent = materialDayTimelineBucketLabel(key, mode);
  const count = document.createElement("span");
  count.textContent = `${totalCount} 项`;
  const loaded = document.createElement("span");
  loaded.className = "material-day-time-group-loaded";
  loaded.textContent = loadedEntries.length < totalCount
    ? `已加载 ${loadedEntries.length}/${totalCount}`
    : "点击展开";
  toggle.append(label, count, loaded);

  const body = document.createElement("div");
  body.className = "material-day-time-group-body";
  body.hidden = !expanded;

  if (loadedEntries.length) {
    loadedEntries.forEach(({ item, index }) => {
      body.appendChild(createMaterialDayTimelineGroupItem({ item, index, allItems }));
    });
  } else {
    const pending = document.createElement("p");
    pending.className = "material-day-time-group-pending";
    pending.textContent = "该时间段的文件名尚未加载，可使用下方“继续加载”读取下一批轻量资料。";
    body.appendChild(pending);
  }

  toggle.addEventListener("click", () => {
    const nextExpanded = !materialTimelineExpandedMinuteGroups.has(groupId);
    if (nextExpanded) materialTimelineExpandedMinuteGroups.add(groupId);
    else materialTimelineExpandedMinuteGroups.delete(groupId);
    toggle.setAttribute("aria-expanded", String(nextExpanded));
    body.hidden = !nextExpanded;
  });

  card.append(toggle, body);
  row.append(point, card);
  return row;
}

function createMaterialDayTimeAxis(dayData, dayCount) {
  const section = document.createElement("section");
  section.className = "material-day-time-axis";
  const selectedDay = Number(materialTimelineAxisDay || 1);
  const safeDayCount = Math.max(1, Number(dayCount || 1));
  const axisX = ((selectedDay - 0.5) / safeDayCount) * 100;
  section.style.setProperty("--day-axis-x", `${Math.max(1.5, Math.min(98.5, axisX))}%`);
  section.classList.toggle("is-left-facing", selectedDay > safeDayCount / 2);

  const startCap = document.createElement("div");
  startCap.className = "material-day-time-cap is-start";
  startCap.textContent = "00:00";
  section.appendChild(startCap);

  const allItems = Array.isArray(dayData?.page?.items) ? dayData.page.items : [];
  const preciseItems = [];
  const impreciseItems = [];
  allItems.forEach((item, index) => {
    const timeText = materialDayTimelineTimeText(item.timeline_at, item.time_precision);
    const target = timeText ? preciseItems : impreciseItems;
    target.push({ item, index, timeText });
  });

  if (impreciseItems.length) {
    const unknown = document.createElement("div");
    unknown.className = "material-day-time-unknown";
    const title = document.createElement("strong");
    title.textContent = `当天时间未精确到时分秒 · ${impreciseItems.length} 项`;
    const list = document.createElement("div");
    list.className = "material-day-time-unknown-list";
    impreciseItems.forEach(({ item, index }) => {
      const entry = createMaterialDayTimelineEntry(item, allItems, index);
      entry.classList.add("is-imprecise");
      list.appendChild(entry);
    });
    unknown.append(title, list);
    section.appendChild(unknown);
  }

  const minuteItems = Array.isArray(dayData?.minutes?.items) ? dayData.minutes.items : [];
  const bucketMode = materialDayTimelineBucketMode(minuteItems);
  const bucketCounts = materialDayTimelineMinuteBucketCounts(dayData, bucketMode);
  const loadedByBucket = new Map();
  preciseItems.forEach((entry) => {
    const key = materialDayTimelineBucketKey(entry.timeText, bucketMode);
    if (!key) return;
    if (!loadedByBucket.has(key)) loadedByBucket.set(key, []);
    loadedByBucket.get(key).push(entry);
    if (!bucketCounts.has(key)) bucketCounts.set(key, 0);
    if (Number(bucketCounts.get(key) || 0) < loadedByBucket.get(key).length) {
      bucketCounts.set(key, loadedByBucket.get(key).length);
    }
  });

  const hourCounts = new Map(
    (Array.isArray(dayData?.hours?.items) ? dayData.hours.items : [])
      .map((item) => [Number(item.hour), Number(item.total_count || 0)]),
  );
  let previousHour = null;
  [...bucketCounts.keys()].sort().forEach((key) => {
    const hour = Number(String(key).slice(0, 2));
    if (Number.isInteger(hour) && hour !== previousHour) {
      const hourMarker = document.createElement("div");
      hourMarker.className = "material-day-time-hour-marker";
      const label = document.createElement("span");
      label.textContent = `${String(hour).padStart(2, "0")}:00`;
      const count = Number(hourCounts.get(hour) || 0);
      if (count) label.title = `该小时共 ${count} 份资料`;
      hourMarker.appendChild(label);
      section.appendChild(hourMarker);
      previousHour = hour;
    }

    const loadedEntries = loadedByBucket.get(key) || [];
    const totalCount = Number(bucketCounts.get(key) || loadedEntries.length);
    const shouldGroup = totalCount >= MATERIAL_TIMELINE_MINUTE_GROUP_THRESHOLD || loadedEntries.length < totalCount;
    if (shouldGroup) {
      section.appendChild(createMaterialDayTimelineGroup({
        key,
        mode: bucketMode,
        totalCount,
        loadedEntries,
        allItems,
      }));
    } else {
      loadedEntries.forEach(({ item, index }) => {
        section.appendChild(createMaterialDayTimelineEntry(item, allItems, index));
      });
    }
  });

  if (!allItems.length && !bucketCounts.size) {
    const empty = document.createElement("div");
    empty.className = "material-day-time-empty";
    empty.textContent = "这一天暂无已建立时间索引的资料";
    section.appendChild(empty);
  }

  const endCap = document.createElement("div");
  endCap.className = "material-day-time-cap is-end";
  endCap.textContent = "24:00";
  section.appendChild(endCap);

  if (dayData?.page?.has_more) {
    const more = document.createElement("div");
    more.className = "material-day-time-more";
    const status = document.createElement("span");
    status.textContent = `已加载 ${allItems.length} / ${Number(dayData.page.total || allItems.length)} 项`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ghost-button material-day-time-load-more";
    button.textContent = materialTimelineDayLoadingMore ? "加载中…" : "继续加载";
    button.disabled = materialTimelineDayLoadingMore;
    button.addEventListener("click", () => loadMoreMaterialTimelineDay());
    more.append(status, button);
    section.appendChild(more);
  }
  return section;
}

function selectMaterialTimelineIsoDate(isoDate) {
  const match = String(isoDate || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (![year, month, day].every(Number.isInteger)) return;
  materialTimelineAxisYear = year;
  materialTimelineAxisMonth = month;
  materialTimelineAxisDay = day;
  materialTimelineAxisAutoResolve = null;
  resetMaterialTimelineDayViewState();
  materialTimelineYearWindowStart = null;
  runMaterialTimelineAxis({ recenterYears: true });
}

function materialTimelineNeighborLabel(isoDate) {
  const match = String(isoDate || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return "";
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  return year === materialTimelineAxisYear ? `${month}月${day}日` : `${year}年${month}月${day}日`;
}

async function loadMoreMaterialTimelineDay() {
  if (materialTimelineDayLoadingMore || materialCenterViewMode !== "timeline") return;
  const state = materialTimelineAxisLastData;
  const page = state?.dayDetail?.page;
  const nextOffset = Number(page?.next_offset);
  if (!page?.has_more || !Number.isInteger(nextOffset)) return;

  const isoDate = `${materialTimelineAxisYear}-${String(materialTimelineAxisMonth).padStart(2, "0")}-${String(materialTimelineAxisDay).padStart(2, "0")}`;
  const selectionKey = isoDate;
  materialTimelineDayLoadingMore = true;
  renderMaterialTimelineAxes(state);
  try {
    const nextPage = await api(
      `/api/v1/materials/timeline/day?date=${encodeURIComponent(isoDate)}&limit=${MATERIAL_TIMELINE_DAY_PAGE_SIZE}&offset=${nextOffset}`,
      {},
      true,
    );
    const currentKey = `${materialTimelineAxisYear}-${String(materialTimelineAxisMonth).padStart(2, "0")}-${String(materialTimelineAxisDay).padStart(2, "0")}`;
    if (currentKey !== selectionKey || materialCenterViewMode !== "timeline") return;
    const existing = Array.isArray(state.dayDetail.page.items) ? state.dayDetail.page.items : [];
    const incoming = Array.isArray(nextPage?.items) ? nextPage.items : [];
    const seen = new Set(existing.map((item) => String(item.id)));
    incoming.forEach((item) => {
      if (!seen.has(String(item.id))) {
        existing.push(item);
        seen.add(String(item.id));
      }
    });
    state.dayDetail.page = {
      ...state.dayDetail.page,
      ...nextPage,
      items: existing,
    };
  } catch (error) {
    showOperationError(error);
  } finally {
    materialTimelineDayLoadingMore = false;
    if (materialCenterViewMode === "timeline") renderMaterialTimelineAxes(state);
  }
}

function renderMaterialTimelineAxes({ years, months, days, yearWindow, dayDetail = null }) {
  materialTimelineAxisLastData = { years, months, days, yearWindow, dayDetail };
  materialCenterResults.replaceChildren();
  materialCenterResults.classList.add("is-timeline-view", "is-axis-view");
  materialCenterLimitHint.classList.add("hidden");

  const root = document.createElement("section");
  root.className = "material-time-axis-view";

  const note = document.createElement("p");
  note.className = "material-time-axis-note";
  note.textContent = "年、月、日三条时间轴同时显示；日内资料密集时会自动按分钟、10 分钟或小时聚合，可继续加载并跳转上一/下一有资料日期。";
  root.appendChild(note);

  const stack = document.createElement("div");
  stack.className = "material-time-axis-stack";
  const yearItems = Array.isArray(years?.items) ? years.items : [];
  const monthItems = Array.isArray(months?.items) ? months.items : [];
  const dayItems = Array.isArray(days?.items) ? days.items : [];
  stack.appendChild(createMaterialTimelineAxisRow({ level: "year", items: yearItems, yearWindow }));
  stack.appendChild(createMaterialTimelineAxisRow({ level: "month", items: monthItems }));
  stack.appendChild(createMaterialTimelineAxisRow({ level: "day", items: dayItems }));
  root.appendChild(stack);

  if (Number.isInteger(materialTimelineAxisDay) && dayDetail) {
    const detailRow = document.createElement("div");
    detailRow.className = "material-time-axis-detail-row";
    detailRow.appendChild(document.createElement("span"));
    detailRow.appendChild(document.createElement("span"));
    const detailHost = document.createElement("div");
    detailHost.className = "material-time-axis-detail-host";
    detailHost.appendChild(createMaterialDayTimeAxis(dayDetail, dayItems.length));
    detailRow.appendChild(detailHost);
    detailRow.appendChild(document.createElement("span"));
    root.appendChild(detailRow);
  }

  const footer = document.createElement("div");
  footer.className = "material-time-axis-footer";
  if (Number.isInteger(materialTimelineAxisDay)) {
    const selected = dayItems.find((item) => Number(item.day) === materialTimelineAxisDay);
    const isoDate = `${materialTimelineAxisYear}-${String(materialTimelineAxisMonth).padStart(2, "0")}-${String(materialTimelineAxisDay).padStart(2, "0")}`;
    const copy = document.createElement("div");
    copy.className = "material-time-axis-selection";
    const strong = document.createElement("strong");
    strong.textContent = `${materialTimelineAxisYear}年${materialTimelineAxisMonth}月${materialTimelineAxisDay}日`;
    const span = document.createElement("span");
    const loadedCount = Number(dayDetail?.page?.items?.length || 0);
    const totalCount = Number(dayDetail?.page?.total ?? selected?.total_count ?? 0);
    span.textContent = totalCount ? `共 ${totalCount} 份资料 · 当前显示 ${loadedCount}` : "暂无资料";
    copy.append(strong, span);
    footer.appendChild(copy);

    const dayNavigation = document.createElement("div");
    dayNavigation.className = "material-time-axis-day-navigation";
    const previousDate = dayDetail?.page?.previous_date || null;
    const nextDate = dayDetail?.page?.next_date || null;

    const previousButton = document.createElement("button");
    previousButton.type = "button";
    previousButton.className = "ghost-button material-time-axis-neighbor-button";
    previousButton.disabled = !previousDate;
    previousButton.textContent = previousDate ? `← ${materialTimelineNeighborLabel(previousDate)}` : "← 没有更早资料";
    previousButton.title = previousDate ? "跳到上一有资料日期" : "已经是最早有资料日期";
    if (previousDate) previousButton.addEventListener("click", () => selectMaterialTimelineIsoDate(previousDate));

    const nextButton = document.createElement("button");
    nextButton.type = "button";
    nextButton.className = "ghost-button material-time-axis-neighbor-button";
    nextButton.disabled = !nextDate;
    nextButton.textContent = nextDate ? `${materialTimelineNeighborLabel(nextDate)} →` : "没有更晚资料 →";
    nextButton.title = nextDate ? "跳到下一有资料日期" : "已经是最晚有资料日期";
    if (nextDate) nextButton.addEventListener("click", () => selectMaterialTimelineIsoDate(nextDate));

    dayNavigation.append(previousButton, nextButton);
    footer.appendChild(dayNavigation);

    const openList = document.createElement("button");
    openList.type = "button";
    openList.className = "ghost-button material-time-axis-open-day";
    openList.textContent = "在列表中查看当日资料";
    openList.addEventListener("click", () => {
      setMaterialCenterViewMode("list", { rerender: false });
      materialCenterDateFrom.value = isoDate;
      materialCenterDateTo.value = isoDate;
      materialCenterSort.value = "timeline_asc";
      runMaterialCenterBrowse();
    });
    footer.appendChild(openList);
  } else {
    const hint = document.createElement("span");
    hint.className = "material-time-axis-hint";
    hint.textContent = `${materialTimelineAxisYear}年 ${materialTimelineAxisMonth}月 · 选择日期展开日内时间轴`;
    footer.appendChild(hint);
  }
  root.appendChild(footer);
  materialCenterResults.appendChild(root);

  const selectedDayCount = Number(dayDetail?.page?.total || 0);
  materialCenterSummary.textContent = Number.isInteger(materialTimelineAxisDay)
    ? `${materialTimelineAxisYear} 年 ${materialTimelineAxisMonth} 月 ${materialTimelineAxisDay} 日 · ${selectedDayCount} 份资料`
    : `${materialTimelineAxisYear} 年 ${materialTimelineAxisMonth} 月 · 点击日期查看日内时间`;
}

function materialTimelineLatestDataValue(items, field) {
  let latest = null;
  (Array.isArray(items) ? items : []).forEach((item) => {
    if (Number(item?.total_count || 0) <= 0) return;
    const value = Number(item?.[field]);
    if (!Number.isInteger(value)) return;
    if (latest === null || value > latest) latest = value;
  });
  return latest;
}

async function runMaterialTimelineAxis({ recenterYears = false } = {}) {
  if (!isMaterialCenterOpen() || materialCenterViewMode !== "timeline") return;
  initializeMaterialTimelineAxis();
  const requestSequence = ++materialTimelineAxisRequestSequence;
  const autoResolve = materialTimelineAxisAutoResolve;
  materialCenterSummary.textContent = "正在读取时间索引……";
  materialCenterResults.replaceChildren();
  materialCenterLimitHint.classList.add("hidden");
  try {
    const yearWindow = materialTimelineYearWindowForSelection({ recenter: recenterYears });
    const [years, months] = await Promise.all([
      api(`/api/v1/materials/timeline/years?start_year=${yearWindow.startYear}&end_year=${yearWindow.endYear}`, {}, true),
      api(`/api/v1/materials/timeline/months?year=${materialTimelineAxisYear}`, {}, true),
    ]);
    if (requestSequence !== materialTimelineAxisRequestSequence || materialCenterViewMode !== "timeline") return;

    const monthItems = Array.isArray(months?.items) ? months.items : [];
    if (autoResolve === "year") {
      const latestMonth = materialTimelineLatestDataValue(monthItems, "month");
      if (latestMonth !== null) materialTimelineAxisMonth = latestMonth;
    }

    const days = await api(
      `/api/v1/materials/timeline/days?year=${materialTimelineAxisYear}&month=${materialTimelineAxisMonth}`,
      {},
      true,
    );
    if (requestSequence !== materialTimelineAxisRequestSequence || materialCenterViewMode !== "timeline") return;

    const dayItems = Array.isArray(days?.items) ? days.items : [];
    const validDays = dayItems.length;
    if (autoResolve === "year" || autoResolve === "month") {
      materialTimelineAxisDay = materialTimelineLatestDataValue(dayItems, "day");
      materialTimelineAxisAutoResolve = null;
    } else if (
      materialTimelineAxisDay !== null &&
      (!Number.isInteger(materialTimelineAxisDay) || materialTimelineAxisDay < 1 || materialTimelineAxisDay > validDays)
    ) {
      materialTimelineAxisDay = null;
    }

    let dayDetail = null;
    if (Number.isInteger(materialTimelineAxisDay)) {
      const isoDate = `${materialTimelineAxisYear}-${String(materialTimelineAxisMonth).padStart(2, "0")}-${String(materialTimelineAxisDay).padStart(2, "0")}`;
      const [hours, minutes, page] = await Promise.all([
        api(`/api/v1/materials/timeline/hours?date=${encodeURIComponent(isoDate)}`, {}, true),
        api(`/api/v1/materials/timeline/minutes?date=${encodeURIComponent(isoDate)}`, {}, true),
        api(`/api/v1/materials/timeline/day?date=${encodeURIComponent(isoDate)}&limit=${MATERIAL_TIMELINE_DAY_PAGE_SIZE}&offset=0`, {}, true),
      ]);
      if (requestSequence !== materialTimelineAxisRequestSequence || materialCenterViewMode !== "timeline") return;
      dayDetail = { hours, minutes, page };
    }
    renderMaterialTimelineAxes({ years, months, days, yearWindow, dayDetail });
  } catch (error) {
    if (requestSequence !== materialTimelineAxisRequestSequence) return;
    showOperationError(error);
    materialCenterSummary.textContent = "时间轴读取失败，请稍后重试";
    const empty = document.createElement("div");
    empty.className = "material-center-empty";
    empty.textContent = "无法读取资料时间索引。";
    materialCenterResults.appendChild(empty);
  }
}

function renderMaterialCenterList(items, imageItems, imageIndexById) {
  materialCenterResults.classList.remove("is-timeline-view", "is-axis-view");
  items.forEach((attachment) => {
    materialCenterResults.appendChild(createMaterialCenterCard(attachment, imageItems, imageIndexById));
  });
}

function renderMaterialCenterResults(data) {
  materialCenterLastData = data;
  materialCenterLoadObserver?.disconnect();
  materialCenterResults.replaceChildren();
  const items = Array.isArray(data?.items) ? data.items : [];
  const counts = data?.counts || {};
  const total = Number(data?.total || 0);
  const loaded = items.length;
  const summaryParts = [
    total ? `共 ${total} 份 · 已加载 ${loaded}` : "当前条件下没有资料",
    `图片 ${counts.image || 0}`,
    `文档 ${counts.document || 0}`,
    `其他 ${counts.other || 0}`,
  ];
  if (counts.undated) summaryParts.push(`未识别日期 ${counts.undated}`);
  if (counts.review) summaryParts.push(`时间待确认 ${counts.review}`);
  materialCenterSummary.textContent = summaryParts.join(" · ");
  materialCenterLimitHint.textContent = data?.has_more ? "滚动继续加载" : (total ? "已加载全部" : "");
  materialCenterLimitHint.classList.toggle("hidden", !total);

  if (!items.length) {
    materialCenterResults.classList.remove("is-timeline-view", "is-axis-view");
    const empty = document.createElement("div");
    empty.className = "material-center-empty";
    empty.textContent = "可以清空关键词、选择更多资料类型，或放宽资料日期范围。";
    materialCenterResults.appendChild(empty);
    return;
  }

  const imageItems = items.filter(isImageAttachment);
  const imageIndexById = new Map(imageItems.map((attachment, index) => [attachment.id, index]));
  if (materialCenterViewMode === "list") {
    renderMaterialCenterList(items, imageItems, imageIndexById);
  } else {
    renderMaterialCenterTimeline(items, imageItems, imageIndexById);
  }
  appendMaterialCenterLoadSentinel(data);
}

async function fetchMaterialCenterPage(params, { append = false } = {}) {
  if (!isMaterialCenterOpen()) return;
  const requestSequence = materialCenterRequestSequence;
  const data = await api(`/api/v1/materials/browse?${params.toString()}`, {}, true);
  if (requestSequence !== materialCenterRequestSequence || !isMaterialCenterOpen()) return;
  if (!append || !materialCenterLastData) {
    renderMaterialCenterResults(data);
    return;
  }
  const existing = Array.isArray(materialCenterLastData.items) ? materialCenterLastData.items : [];
  const incoming = Array.isArray(data?.items) ? data.items : [];
  const seen = new Set(existing.map((item) => item.id));
  const merged = existing.concat(incoming.filter((item) => !seen.has(item.id)));
  renderMaterialCenterResults({ ...data, items: merged });
}

async function loadMoreMaterialCenterResults() {
  if (materialCenterLoadingMore || !materialCenterLastData?.has_more || !materialCenterBrowseParams) return;
  materialCenterLoadingMore = true;
  const params = new URLSearchParams(materialCenterBrowseParams.toString());
  params.set("offset", String(materialCenterLastData.next_offset || materialCenterLastData.items?.length || 0));
  try {
    await fetchMaterialCenterPage(params, { append: true });
  } catch (error) {
    showOperationError(error);
  } finally {
    materialCenterLoadingMore = false;
  }
}

function materialCenterImportedCategory(attachment) {
  return materialFileCategory({
    type: String(attachment?.media_type || ""),
    name: String(attachment?.filename || ""),
  });
}

function materialCenterCurrentFiltersInclude(attachment) {
  if (!attachment) return false;
  const category = attachment.category || materialCenterImportedCategory(attachment);
  if (!selectedMaterialCenterCategories().includes(category)) return false;
  const timelineDate = String(attachment.timeline_date || "");
  const timeConfidence = String(attachment.time_confidence || "").toLowerCase();
  if (materialCenterTimeStatus === "review" && timelineDate && !["low", "unknown"].includes(timeConfidence)) return false;
  if (materialCenterDateFrom?.value && (!timelineDate || timelineDate < materialCenterDateFrom.value)) return false;
  if (materialCenterDateTo?.value && (!timelineDate || timelineDate > materialCenterDateTo.value)) return false;
  const needle = String(materialCenterQuery?.value || "").trim().toLocaleLowerCase();
  if (needle) {
    const haystack = `${attachment.filename || ""}\n${attachment.media_type || ""}`.toLocaleLowerCase();
    if (!haystack.includes(needle)) return false;
  }
  return true;
}

function focusMaterialCenterImportedAttachment(attachment) {
  if (!isMaterialCenterOpen() || !attachment?.id) return;
  if (materialCenterViewMode === "timeline" && attachment.timeline_date) {
    const [year, month, day] = String(attachment.timeline_date).split("-").map(Number);
    materialTimelineAxisYear = year;
    materialTimelineAxisMonth = month;
    materialTimelineAxisDay = day;
    materialTimelineYearWindowStart = null;
    runMaterialTimelineAxis({ recenterYears: true });
    return;
  }
  const normalized = {
    ...attachment,
    category: attachment.category || materialCenterImportedCategory(attachment),
    source_content: attachment.source_content || null,
  };
  const currentItems = Array.isArray(materialCenterLastData?.items) ? materialCenterLastData.items : [];
  if (!currentItems.some((item) => item.id === normalized.id) && materialCenterCurrentFiltersInclude(normalized)) {
    renderMaterialCenterResults({ ...materialCenterLastData, items: [...currentItems, normalized] });
  }
  window.requestAnimationFrame(() => {
    const timelineDate = String(normalized.timeline_date || "");
    let target = null;
    if (materialCenterViewMode === "timeline" && timelineDate) {
      target = materialCenterResults?.querySelector(`[data-timeline-date="${timelineDate}"]`);
    }
    if (!target) {
      target = materialCenterResults?.querySelector(`[data-attachment-id="${String(normalized.id)}"]`);
    }
    if (!(target instanceof HTMLElement)) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.classList.add("is-upload-focus");
    window.setTimeout(() => target.classList.remove("is-upload-focus"), 1800);
  });
}

async function runMaterialCenterBrowse() {
  if (!materialCenterForm || !isMaterialCenterOpen()) return;
  if (materialCenterViewMode === "timeline") {
    await runMaterialTimelineAxis();
    return;
  }
  const submit = materialCenterForm.querySelector('button[type="submit"]');
  const categories = selectedMaterialCenterCategories();
  if (!categories.length) {
    showToast("请至少选择一种资料类型", "error");
    return;
  }
  if (materialCenterDateFrom.value && materialCenterDateTo.value && materialCenterDateFrom.value > materialCenterDateTo.value) {
    showToast("资料开始日期不能晚于结束日期", "error");
    materialCenterDateFrom.focus();
    return;
  }

  const params = new URLSearchParams();
  const query = materialCenterQuery.value.trim();
  if (query) params.set("q", query);
  categories.forEach((category) => params.append("category", category));
  if (materialCenterDateFrom.value) params.set("date_from", materialCenterDateFrom.value);
  if (materialCenterDateTo.value) params.set("date_to", materialCenterDateTo.value);
  params.set("sort", materialCenterSort.value || "timeline_desc");
  params.set("time_status", materialCenterTimeStatus);
  params.set("limit", "48");
  params.set("offset", "0");

  ++materialCenterRequestSequence;
  resetMaterialCenterPaging();
  materialCenterBrowseParams = new URLSearchParams(params.toString());
  setButtonBusy(submit, true, "筛选中…");
  materialCenterSummary.textContent = "正在整理加密资料……";
  materialCenterResults.replaceChildren();
  materialCenterLimitHint.classList.add("hidden");
  try {
    await fetchMaterialCenterPage(params, { append: false });
    materialCenterResults.scrollTop = 0;
  } catch (error) {
    showOperationError(error);
    materialCenterSummary.textContent = "资料读取失败，请调整条件后重试";
  } finally {
    setButtonBusy(submit, false);
  }
}

function isMemorySearchOpen() {
  return Boolean(memorySearchModal && !memorySearchModal.classList.contains("hidden"));
}

function memorySearchScopeLabel(item) {
  return contentCenterScopeLabel(item);
}

function selectedMemorySearchKinds() {
  if (!memorySearchForm) return [];
  return Array.from(memorySearchForm.querySelectorAll('input[name="search_kind"]:checked')).map((input) => input.value);
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
    empty.textContent = "暂无标签，可先在任一内容编辑中创建。";
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
  memorySearchForm?.querySelectorAll('input[name="search_kind"]').forEach((input) => { input.checked = true; });
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
  if (isContentCenterOpen()) closeContentCenterModalNow({ restoreFocus: false });
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

function focusMemorySearchTarget(kind, contentId) {
  requestAnimationFrame(() => {
    const selector = `[data-content-kind="${CSS.escape(kind)}"][data-content-id="${CSS.escape(contentId)}"]`;
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
  if (opened !== false) focusMemorySearchTarget(item.kind, item.id);
}

function renderMemorySearchResultsData(data) {
  memorySearchResults.replaceChildren();
  const items = data?.items || [];
  const counts = data?.counts || {};
  const total = Number(data?.total ?? items.length);
  memorySearchSummary.textContent = total
    ? `共 ${total} 条 · 事件 ${counts.event || 0} · 记忆 ${counts.memory || 0} · 计划 ${counts.plan || 0}`
    : "没有找到符合条件的内容";
  memorySearchLimitHint.classList.toggle("hidden", !data?.has_more);
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "memory-search-empty";
    empty.textContent = "可以换一个关键词、选择更多内容类型、减少标签条件，或放宽日期范围。";
    memorySearchResults.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `memory-search-result-card is-${item.kind}`;
    button.addEventListener("click", () => openMemorySearchResult(item));

    const top = document.createElement("div");
    top.className = "memory-search-result-top";
    const titleWrap = document.createElement("div");
    titleWrap.className = "memory-search-result-title";
    const kind = document.createElement("span");
    kind.className = `memory-search-kind-badge is-${item.kind}`;
    kind.textContent = contentCenterKindLabel(item.kind);
    const title = document.createElement("strong");
    title.textContent = item.title || `未命名${contentCenterKindLabel(item.kind)}`;
    titleWrap.append(kind, title);
    const scope = document.createElement("span");
    scope.textContent = memorySearchScopeLabel(item);
    top.append(titleWrap, scope);

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
  const kinds = selectedMemorySearchKinds();
  if (!kinds.length) {
    showToast("请至少选择一种内容类型", "error");
    return;
  }
  if (memorySearchDateFrom.value && memorySearchDateTo.value && memorySearchDateFrom.value > memorySearchDateTo.value) {
    showToast("开始日期不能晚于结束日期", "error");
    memorySearchDateFrom.focus();
    return;
  }
  const params = new URLSearchParams();
  const query = memorySearchQuery.value.trim();
  if (query) params.set("q", query);
  kinds.forEach((kind) => params.append("kind", kind));
  if (memorySearchDateFrom.value) params.set("date_from", memorySearchDateFrom.value);
  if (memorySearchDateTo.value) params.set("date_to", memorySearchDateTo.value);
  selectedMemorySearchTagIds.forEach((tagId) => params.append("tag_id", tagId));
  params.set("limit", "100");

  const requestSequence = ++memorySearchRequestSequence;
  setButtonBusy(submit, true, "搜索中…");
  memorySearchSummary.textContent = "正在搜索加密内容……";
  memorySearchResults.replaceChildren();
  memorySearchLimitHint.classList.add("hidden");
  try {
    const data = await api(`/api/v1/content/search?${params.toString()}`, {}, true);
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
  const parts = [
    ["事件", memoryMapTagMatches.counts.event],
    ["记忆", memoryMapTagMatches.counts.memory],
    ["计划", memoryMapTagMatches.counts.plan],
  ].filter(([, count]) => count > 0).map(([name, count]) => `${name} ${count}`);
  const breakdown = parts.length ? `（${parts.join(" · ")}）` : "";
  return `${label} · 命中 ${memoryMapTagMatches.contentCount} 条内容${breakdown}，覆盖 ${memoryMapTagMatches.dates.size} 天、${memoryMapTagMatches.months.size} 月、${memoryMapTagMatches.years.size} 年。`;
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
    empty.textContent = "还没有标签。可以先在事件、记忆或计划编辑中创建标签。";
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
    contentCount: Number(data.content_count ?? data.memory_count ?? 0),
    counts: {
      event: Number(data.counts?.event || 0),
      memory: Number(data.counts?.memory ?? data.memory_count ?? 0),
      plan: Number(data.counts?.plan || 0),
    },
  };
  memoryMapFilterRevision += 1;
  lifeGridSignature = "";
  fullPageGridSignature = "";
}

function redrawMemoryMapFilterState() {
  renderHomeMonthCalendar();
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
  const data = await api(`/api/v1/content/tag-map?${params.toString()}`, {}, true);
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
  if (isContentCenterOpen()) closeContentCenterModalNow({ restoreFocus: false });
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
const mediaBackupStatusCard = document.getElementById("mediaBackupStatusCard");
const mediaBackupStatusBadge = document.getElementById("mediaBackupStatusBadge");
const mediaBackupStatusTitle = document.getElementById("mediaBackupStatusTitle");
const mediaBackupStatusMessage = document.getElementById("mediaBackupStatusMessage");
const mediaBackupStatusMeta = document.getElementById("mediaBackupStatusMeta");
const refreshMediaBackupStatusButton = document.getElementById("refreshMediaBackupStatusButton");
const mediaBackupTargetPath = document.getElementById("mediaBackupTargetPath");
const startMediaBackupButton = document.getElementById("startMediaBackupButton");
const verifyMediaLibraryButton = document.getElementById("verifyMediaLibraryButton");
const verifyMediaBackupButton = document.getElementById("verifyMediaBackupButton");
const cancelMediaBackupButton = document.getElementById("cancelMediaBackupButton");
const mediaBackupJobStatusText = document.getElementById("mediaBackupJobStatusText");
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
let mediaBackupPollTimer = 0;

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
  const total = Number(tag?.total_count ?? tag?.memory_count ?? 0);
  if (!total) return "尚未使用";
  const parts = [];
  if (Number(tag?.event_count || 0)) parts.push(`事件 ${tag.event_count}`);
  if (Number(tag?.memory_count || 0)) parts.push(`记忆 ${tag.memory_count}`);
  if (Number(tag?.plan_count || 0)) parts.push(`计划 ${tag.plan_count}`);
  return `${total} 次 · ${parts.join(" · ")}`;
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
  const count = Number(tag?.total_count ?? tag?.memory_count ?? 0);
  const confirmed = await askConfirmation({
    eyebrow: "删除标签",
    title: `删除 #${tag.name}？`,
    message: count
      ? `这个标签当前关联 ${count} 条内容。删除后事件、记忆和计划正文都会保留，只移除标签关联。`
      : "这个标签当前没有关联内容。删除后无法恢复标签本身。",
    confirmLabel: "删除标签",
    tone: "danger",
  });
  if (!confirmed) return;

  const affectedMapFilter = selectedMemoryMapTagIds.has(tag.id);

  try {
    await api(`/api/v1/tags/${encodeURIComponent(tag.id)}`, { method: "DELETE" }, true);
    selectedMemoryTagIds.quick.delete(tag.id);
    selectedMemoryTagIds.event.delete(tag.id);
    selectedMemoryTagIds.drawer.delete(tag.id);
    selectedMemoryTagIds.plan.delete(tag.id);
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
    (sum, tag) => sum + Number(tag.total_count ?? tag.memory_count ?? 0),
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
  if (mediaBackupStatusCard) {
    mediaBackupStatusCard.dataset.level = "neutral";
    mediaBackupStatusBadge.textContent = "检查中";
    mediaBackupStatusTitle.textContent = "正在检查大型媒体库";
    mediaBackupStatusMessage.textContent = "请稍候…";
    mediaBackupStatusMeta.textContent = "";
  }
  if (mediaBackupJobStatusText) {
    mediaBackupJobStatusText.textContent = "尚未执行大型媒体独立备份。";
    delete mediaBackupJobStatusText.dataset.tone;
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
  await Promise.all([loadAutoBackupPanel(), loadMediaBackupStatus(), loadSecuritySummary(), loadTagManagement()]);
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
  stopMediaBackupPolling();
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

function renderMediaBackupStatus(status = {}) {
  if (!mediaBackupStatusCard) return;
  const total = Number(status.original_records || 0);
  const online = Number(status.online || 0);
  const offline = Number(status.offline || 0);
  const incomplete = Number(status.incomplete || 0);
  const invalid = Number(status.invalid || 0);
  const chunks = Number(status.original_chunks || 0);
  const derived = Number(status.audio_compat_records || 0);
  const problemCount = offline + incomplete + invalid;
  const external = status.external_backup || {};
  const backedUp = Boolean(total && external.current);
  const level = problemCount ? "warning" : (total && !backedUp ? "warning" : "success");
  mediaBackupStatusCard.dataset.level = level;
  mediaBackupStatusBadge.textContent = problemCount ? "需处理" : (backedUp ? "已备份" : (total ? "待备份" : "在线"));
  mediaBackupStatusTitle.textContent = total
    ? `大型媒体 ${online}/${total} 在线${backedUp ? " · 独立备份已同步" : ""}`
    : "当前没有大型媒体";
  if (!total) {
    mediaBackupStatusMessage.textContent = "核心 .lifevault v3 可以独立完成当前仓库恢复。";
  } else if (problemCount) {
    const issues = [];
    if (offline) issues.push(`${offline} 个离线`);
    if (incomplete) issues.push(`${incomplete} 个分块不完整`);
    if (invalid) issues.push(`${invalid} 个索引异常`);
    mediaBackupStatusMessage.textContent = `${issues.join("、")}；.lifevault 仍可保存核心索引，但完整媒体备份尚未就绪。`;
  } else if (backedUp) {
    mediaBackupStatusMessage.textContent = `核心 .lifevault 与大型媒体独立备份均已就绪。${external.last_verified_at ? "媒体备份已完成完整校验。" : "可按需执行一次完整校验。"}`;
  } else if (external.configured && external.state === "stale") {
    mediaBackupStatusMessage.textContent = "独立备份目录已配置，但媒体库已有变化，请再次执行增量备份。";
  } else {
    mediaBackupStatusMessage.textContent = "核心备份已就绪；完整恢复还需要为 data/media 建立独立增量备份。";
  }
  const meta = [`原始媒体 ${formatAttachmentSize(status.original_bytes || 0)}`];
  if (chunks) meta.push(`媒体分块 ${chunks} 个`);
  if (derived) meta.push(`兼容音轨 ${derived} 个（可重建，不备份）`);
  if (external.last_synced_at) meta.push(`最近媒体备份 ${formatBackupDateTime(external.last_synced_at)}`);
  mediaBackupStatusMeta.textContent = meta.join(" · ");
  if (mediaBackupTargetPath && external.target_path && document.activeElement !== mediaBackupTargetPath) {
    mediaBackupTargetPath.value = external.target_path;
  }
  renderMediaBackupJob(status.backup_job || { state: "idle" });
}

function renderMediaBackupJob(job = {}) {
  if (!mediaBackupJobStatusText) return;
  const state = String(job.state || "idle");
  const active = state === "running" || state === "cancelling";
  startMediaBackupButton && (startMediaBackupButton.disabled = active);
  verifyMediaLibraryButton && (verifyMediaLibraryButton.disabled = active);
  verifyMediaBackupButton && (verifyMediaBackupButton.disabled = active);
  cancelMediaBackupButton?.classList.toggle("hidden", !active);
  if (state === "idle") return;
  const totalBytes = Number(job.total_bytes || 0);
  const completedBytes = Number(job.completed_bytes || 0);
  const totalFiles = Number(job.total_files || 0);
  const completedFiles = Number(job.completed_files || 0);
  const percent = totalBytes > 0 ? Math.min(100, completedBytes / totalBytes * 100) : (totalFiles > 0 ? completedFiles / totalFiles * 100 : 0);
  const modeLabel = job.mode === "source-verify" ? "原始媒体校验" : (job.mode === "verify" ? "备份校验" : "增量备份");
  if (state === "running" || state === "cancelling") {
    const parts = [`${modeLabel} ${percent.toFixed(percent >= 10 ? 0 : 1)}%`];
    if (totalBytes) parts.push(`${formatAttachmentSize(completedBytes)} / ${formatAttachmentSize(totalBytes)}`);
    if (totalFiles) parts.push(`${completedFiles}/${totalFiles} 个文件`);
    if (job.mode === "sync") {
      if (Number(job.copied_files || 0)) parts.push(`复制 ${job.copied_files} 个`);
      if (Number(job.skipped_files || 0)) parts.push(`跳过 ${job.skipped_files} 个未变化文件`);
    }
    if (state === "cancelling") parts.push("正在取消…");
    mediaBackupJobStatusText.textContent = parts.join(" · ");
    mediaBackupJobStatusText.dataset.tone = "info";
  } else if (state === "completed") {
    if (job.mode === "source-verify") {
      mediaBackupJobStatusText.textContent = `原始媒体完整校验完成：${job.verified_media || 0} 个媒体、${job.verified_files || job.completed_files || 0} 个分块通过。`;
    } else if (job.mode === "verify") {
      mediaBackupJobStatusText.textContent = `媒体备份校验完成：${job.verified_files || job.completed_files || 0} 个文件通过。`;
    } else {
      mediaBackupJobStatusText.textContent = `媒体增量备份完成：复制 ${job.copied_files || 0} 个文件，跳过 ${job.skipped_files || 0} 个未变化文件。`;
    }
    mediaBackupJobStatusText.dataset.tone = "success";
  } else if (state === "cancelled") {
    mediaBackupJobStatusText.textContent = "大型媒体备份任务已取消；已完成的分块会保留，下次继续增量补齐。";
    mediaBackupJobStatusText.dataset.tone = "warning";
  } else if (state === "failed") {
    mediaBackupJobStatusText.textContent = job.error || "大型媒体备份失败";
    mediaBackupJobStatusText.dataset.tone = "error";
  }
}

function stopMediaBackupPolling() {
  if (mediaBackupPollTimer) window.clearTimeout(mediaBackupPollTimer);
  mediaBackupPollTimer = 0;
}

async function pollMediaBackupJob() {
  stopMediaBackupPolling();
  if (settingsModal?.classList.contains("hidden")) return;
  try {
    const job = await api("/api/v1/backup/media/job", {}, true);
    renderMediaBackupJob(job);
    if (job.state === "running" || job.state === "cancelling") {
      mediaBackupPollTimer = window.setTimeout(pollMediaBackupJob, 700);
    } else {
      await loadMediaBackupStatus();
    }
  } catch (error) {
    if (mediaBackupJobStatusText) {
      mediaBackupJobStatusText.textContent = friendlyErrorMessage(error);
      mediaBackupJobStatusText.dataset.tone = "error";
    }
  }
}

async function loadMediaBackupStatus() {
  if (!mediaBackupStatusCard) return null;
  try {
    const status = await api("/api/v1/backup/media/status", {}, true);
    renderMediaBackupStatus(status);
    if (status?.backup_job?.state === "running" || status?.backup_job?.state === "cancelling") {
      stopMediaBackupPolling();
      mediaBackupPollTimer = window.setTimeout(pollMediaBackupJob, 700);
    }
    return status;
  } catch (error) {
    mediaBackupStatusCard.dataset.level = "error";
    mediaBackupStatusBadge.textContent = "异常";
    mediaBackupStatusTitle.textContent = "大型媒体库状态读取失败";
    mediaBackupStatusMessage.textContent = friendlyErrorMessage(error);
    mediaBackupStatusMeta.textContent = "";
    return null;
  }
}

refreshMediaBackupStatusButton?.addEventListener("click", async () => {
  setButtonBusy(refreshMediaBackupStatusButton, true, "检查中…");
  try {
    await loadMediaBackupStatus();
  } finally {
    setButtonBusy(refreshMediaBackupStatusButton, false);
  }
});


async function startMediaBackup(mode) {
  const targetPath = String(mediaBackupTargetPath?.value || "").trim();
  if (mode === "sync" && !targetPath) {
    showToast("请先填写大型媒体独立备份目录", "info");
    mediaBackupTargetPath?.focus();
    return;
  }
  const button = mode === "source-verify" ? verifyMediaLibraryButton : (mode === "verify" ? verifyMediaBackupButton : startMediaBackupButton);
  setButtonBusy(button, true, mode === "source-verify" ? "校验中…" : (mode === "verify" ? "启动中…" : "准备中…"));
  try {
    const route = mode === "source-verify" ? "/api/v1/backup/media/verify-library" : `/api/v1/backup/media/${mode}`;
    const options = mode === "source-verify"
      ? { method: "POST" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_path: targetPath || null }),
        };
    const job = await api(route, options, true);
    renderMediaBackupJob(job);
    mediaBackupPollTimer = window.setTimeout(pollMediaBackupJob, 300);
  } catch (error) {
    if (mediaBackupJobStatusText) {
      mediaBackupJobStatusText.textContent = friendlyErrorMessage(error);
      mediaBackupJobStatusText.dataset.tone = "error";
    }
    showOperationError(error);
  } finally {
    setButtonBusy(button, false);
  }
}

startMediaBackupButton?.addEventListener("click", () => startMediaBackup("sync"));
verifyMediaLibraryButton?.addEventListener("click", () => startMediaBackup("source-verify"));
verifyMediaBackupButton?.addEventListener("click", () => startMediaBackup("verify"));
cancelMediaBackupButton?.addEventListener("click", async () => {
  setButtonBusy(cancelMediaBackupButton, true, "取消中…");
  try {
    const job = await api("/api/v1/backup/media/cancel", { method: "POST" }, true);
    renderMediaBackupJob(job);
    mediaBackupPollTimer = window.setTimeout(pollMediaBackupJob, 300);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(cancelMediaBackupButton, false);
  }
});

async function checkBackupIntegrity() {
  if (!(await confirmBackupUsesSavedState())) return;
  setButtonBusy(checkBackupButton, true, "检查中…");
  try {
    const report = await api("/api/v1/backup/check", {}, true);
    const mediaCount = Number(report.external_media_records || 0);
    const mediaProblems = Number(report.external_media_offline || 0)
      + Number(report.external_media_incomplete || 0)
      + Number(report.external_media_invalid || 0);
    const mediaText = mediaCount
      ? `；大型媒体 ${mediaCount - mediaProblems}/${mediaCount} 在线${mediaProblems ? "，完整媒体备份需处理离线/异常项" : ""}`
      : "";
    backupStatusText.textContent = `核心检查通过：schema v${report.schema_version}，已验证 ${report.encrypted_records_verified} 条加密记录${mediaText}。`;
    backupStatusText.dataset.tone = mediaProblems ? "warning" : "success";
    renderMediaBackupStatus({
      original_records: report.external_media_records,
      original_bytes: report.external_media_bytes,
      online: report.external_media_online,
      offline: report.external_media_offline,
      incomplete: report.external_media_incomplete,
      invalid: report.external_media_invalid,
      audio_compat_records: report.audio_compat_records,
    });
    showToast(mediaProblems ? "核心备份检查通过；大型媒体库需处理" : "核心仓库与媒体索引检查通过", mediaProblems ? "info" : "success");
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
    backupStatusText.textContent = `已导出核心备份 ${filename}。如有大型媒体，请同时镜像 data/media 才构成完整备份。`;
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
    // 首页只读取轻量提醒状态，避免为一个角标重新哈希所有 .lifevault。
    const status = await api("/api/v1/backup/auto/reminder", {}, true);
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
  const externalCount = Number(report.external_media_records || 0);
  const mediaText = externalCount
    ? `；另含 ${externalCount} 个大型媒体索引（${formatAttachmentSize(report.external_media_bytes || 0)}），恢复核心后需提供对应 data/media 媒体库`
    : "";
  return `演练通过：备份创建于 ${createdAt}，schema v${report.schema_version}，包含 ${totalContent} 条内容，已验证 ${report.encrypted_records_verified} 条加密记录${mediaText}。`;
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
    await loadHome();
  } catch (error) {
    statusBadge.textContent = "连接失败";
    showToast(error.message);
  }
}

async function loadHome() {
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
    restoreLargeMaterialUploadTasksForCurrentProfile();
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
    renderHomeMonthCalendar();
    initializeLifeNavigator(progress);
    showView("home");
    void refreshBackupHealthReminder();
    requestAnimationFrame(() => {
      renderLifeMapView(true);
      if (fullPageLifeOpen) {
        fullPageGridSignature = "";
        drawFullPageLifeGrid(true);
      }
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
  renderHomeMonthCalendar();
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
        await loadHome();
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
      await loadHome();
    } catch (error) {
      showToast(error.message);
    } finally {
      if (submit) submit.disabled = false;
    }
  });
}

lockButton.addEventListener("click", async () => {
  if (!(await confirmDiscardChanges())) return;
  pauseLargeMaterialUploadsForLock();
  try {
    await api("/api/v1/auth/lock", { method: "POST" });
  } catch (_) {
    // A local lock must still clear the browser session even if the request failed.
  }
  setToken(null);
  currentProfile = null;
  currentProgress = null;
  contentStatus = {};
  activeLifeMapView = "month";
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
    await loadHome();
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
  const aggregate = { has_event: false, has_memory: false, has_plan: false, has_material: false };
  for (const [dateKey, state] of Object.entries(contentStatus)) {
    if (dateKey < start || dateKey >= end) continue;
    aggregate.has_event ||= Boolean(state.has_event);
    aggregate.has_memory ||= Boolean(state.has_memory);
    aggregate.has_plan ||= Boolean(state.has_plan);
    aggregate.has_material ||= Boolean(state.has_material);
    if (aggregate.has_event && aggregate.has_memory && aggregate.has_plan && aggregate.has_material) break;
  }
  return aggregate;
}

function contentStateLabel(state) {
  const labels = [];
  if (state.has_event) labels.push("有事件");
  if (state.has_memory) labels.push("有记忆");
  if (state.has_plan) labels.push("有计划");
  if (state.has_material) labels.push("有资料");
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
  cell.classList.toggle("has-material", Boolean(state.has_material));

  if (!state.has_event && !state.has_plan && !state.has_material) return;
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
  if (state.has_material) {
    const materialMarker = document.createElement("i");
    materialMarker.className = "hierarchy-material-marker";
    materialMarker.setAttribute("aria-hidden", "true");
    markers.appendChild(materialMarker);
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
    const state = yearContentStatus[String(year)] || { has_event: false, has_memory: false, has_plan: false, has_material: false };
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
      const state = monthContentStatus[periodKey] || { has_event: false, has_memory: false, has_plan: false, has_material: false };
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
  lifeMapViewSubtitle.textContent = "点击月份在右侧展开整月内容和月内日期。";
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
  if (state.has_material) labels.push("有资料");
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

    if (state.has_material) {
      const materialSize = Math.max(1.2, cellSize * .18);
      ctx.fillStyle = "#7f6aa8";
      ctx.fillRect(x + cellSize - materialSize - 1, y + 1, materialSize, materialSize);
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
    ? `完整人生共 ${totalDays.toLocaleString()} 天；当前标签筛选命中 ${memoryMapTagMatches.contentCount} 条内容、${memoryMapTagMatches.dates.size} 个具体日期，未命中日期已弱化显示。`
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

      if (dateState?.has_material) {
        const materialSize = Math.max(0.8, Math.min(1.5, cellWidth * 0.34, cellHeight * 0.3));
        ctx.fillStyle = "#7f6aa8";
        ctx.fillRect(x + cellDrawWidth - materialSize, y, materialSize, materialSize);
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
  if (dateState.has_material) contentLabels.push("有资料");
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
    listToggle: document.getElementById("eventListToggle"),
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
    listToggle: document.getElementById("memoryListToggle"),
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
    listToggle: document.getElementById("planListToggle"),
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

const contentSectionCollapsed = { event: false, memory: false, plan: false };
let contentSectionCollapsePeriodKey = "";

function periodScopeLabel(scope = selectedScope) {
  if (scope === "year") return "年";
  if (scope === "month") return "月";
  if (scope === "day") return "日";
  return "";
}

function scopedContentCreateLabel(kind, scope = selectedScope) {
  const config = contentFormConfigurations[kind];
  return `＋ 添加${periodScopeLabel(scope)}${config.itemLabel}`;
}

function resetContentSectionCollapseState() {
  Object.keys(contentSectionCollapsed).forEach((kind) => {
    contentSectionCollapsed[kind] = false;
  });
}

function updateContentListCollapse(kind) {
  const config = contentFormConfigurations[kind];
  const list = config.section.querySelector(".content-list");
  const toggle = config.listToggle;
  if (!list || !toggle) return;
  const itemCount = Number(config.section.dataset.itemCount || 0);
  const collapsed = itemCount > 0 && Boolean(contentSectionCollapsed[kind]);
  list.classList.toggle("hidden", collapsed);
  toggle.classList.toggle("hidden", itemCount === 0);
  toggle.hidden = itemCount === 0;
  toggle.setAttribute("aria-expanded", String(!collapsed));
  toggle.textContent = collapsed
    ? `展开${config.itemLabel}（${itemCount}）`
    : `收起${config.itemLabel}`;
}

Object.entries(contentFormConfigurations).forEach(([kind, config]) => {
  config.listToggle?.addEventListener("click", () => {
    contentSectionCollapsed[kind] = !contentSectionCollapsed[kind];
    updateContentListCollapse(kind);
  });
});

const EMPTY_CONTENT_STATE = { has_event: false, has_memory: false, has_plan: false, has_material: false };

const pendingContentAttachments = {
  event: [],
  memory: [],
  plan: [],
};

function pendingAttachmentSignature(file) {
  return `${file.name}::${file.size}::${file.lastModified}::${file.type || ""}`;
}

function contentFormValue(kind) {
  const form = contentFormConfigurations[kind].form;
  const content = kind === "memory"
    ? getMemoryRichEditorContent(memoryRichEditorIds.drawer)
    : form.querySelector('[name="content"]')?.value || "";
  return {
    title: form.querySelector('[name="title"]')?.value || "",
    content,
    tagIds: [...selectedMemoryTagIds[tagModeForKind(kind)]].sort(),
    attachments: pendingContentAttachments[kind].map((file) => pendingAttachmentSignature(file)),
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
    message: "表单中还有未保存的内容或待上传附件。继续后，这些更改将不会保留。",
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
  updateContentListCollapse(kind);
}

function resetContentForm(kind, hide = true) {
  const config = contentFormConfigurations[kind];
  const submit = config.form.querySelector('button[type="submit"]');
  const cancel = config.form.querySelector('.event-form-actions button[type="button"]');
  if (kind === "memory") destroyMemoryRichEditor(memoryRichEditorIds.drawer);
  config.form.reset();
  clearPendingContentAttachments(kind);
  resetMemoryTagSelector(tagModeForKind(kind));
  config.form.classList.toggle("hidden", hide);
  config.form.classList.remove("is-editing");
  delete config.form.dataset.editId;
  delete config.form.dataset.editRevision;
  delete config.form.dataset.initialSnapshot;
  config.toggleButton.textContent = kind === "plan" && config.toggleButton.disabled
    ? "该时间范围已过去"
    : scopedContentCreateLabel(kind);
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
  contentSectionCollapsePeriodKey = "";
  resetContentSectionCollapseState();
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
  if (!resumeContentCenterAfterDrawer()) resumeMaterialCenterAfterDrawer();
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
  button.classList.toggle("has-material", state.has_material);
  if (state.has_material) {
    const materialMarker = document.createElement("i");
    materialMarker.className = "period-material-marker";
    materialMarker.setAttribute("aria-hidden", "true");
    button.appendChild(materialMarker);
  }
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

function decorateDayCalendarButton(button, child, options = {}) {
  const calendarMeta = window.LifeGraphCalendarMeta?.getDateMeta?.(child.period_key) || null;
  const materialMarker = button.querySelector(".period-material-marker");
  button.replaceChildren();
  button.classList.add("calendar-day-cell");

  if (calendarMeta?.lunarDisplay) {
    const watermark = document.createElement("span");
    watermark.className = "calendar-day-watermark";
    watermark.classList.toggle("is-solar-term", Boolean(calendarMeta.solarTerm));
    watermark.classList.toggle("is-festival", Boolean(calendarMeta.festival));
    watermark.setAttribute("aria-hidden", "true");
    const watermarkCharacters = [...calendarMeta.lunarDisplay];
    watermark.classList.add(`glyph-count-${watermarkCharacters.length}`);
    watermarkCharacters.forEach((character, index) => {
      const glyph = document.createElement("span");
      glyph.className = `glyph glyph-${index + 1}`;
      glyph.textContent = character;
      watermark.appendChild(glyph);
    });
    button.appendChild(watermark);
  }

  const solarDay = document.createElement("span");
  solarDay.className = "calendar-day-solar";
  solarDay.textContent = child.label;
  button.appendChild(solarDay);
  if (materialMarker) button.appendChild(materialMarker);

  const state = child.disabled ? null : statusForPeriod("day", child.period_key);
  const stateText = state ? contentStateLabel(state) : "";
  const tooltipBase = calendarMeta?.tooltip || child.period_key;
  if (child.disabled) {
    button.title = `${tooltipBase} · 不在当前人生图谱范围内`;
    button.setAttribute("aria-label", `${tooltipBase}，不在当前人生图谱范围内`);
  } else {
    button.title = `${tooltipBase}${stateText ? ` · ${stateText}` : ""}`;
    const actionLabel = options.actionLabel || "点击查看";
    button.setAttribute("aria-label", `${tooltipBase}${stateText ? `，${stateText}` : ""}，${actionLabel}`);
  }
  return button;
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

  children.forEach((child) => {
    const button = periodChildButton(child, selectedKey);
    periodChildGrid.appendChild(decorateDayCalendarButton(button, child));
  });

  const trailing = (7 - ((mondayOffset + children.length) % 7)) % 7;
  for (let index = 0; index < trailing; index += 1) {
    const placeholder = document.createElement("span");
    placeholder.className = "period-day-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    periodChildGrid.appendChild(placeholder);
  }
}

function homeMonthCalendarIsPickerOpen() {
  return Boolean(homeMonthCalendarPicker && !homeMonthCalendarPicker.classList.contains("hidden"));
}

function closeHomeMonthCalendarPicker({ restoreFocus = false } = {}) {
  if (!homeMonthCalendarPicker || !homeMonthCalendarPickerButton) return;
  homeMonthCalendarPicker.classList.add("hidden");
  homeMonthCalendarPickerButton.setAttribute("aria-expanded", "false");
  if (restoreFocus) homeMonthCalendarPickerButton.focus({ preventScroll: true });
}

function validHomeCalendarYears() {
  const bounds = getLifeBounds();
  if (!bounds) return [];
  const firstYear = bounds.birth.getUTCFullYear();
  const lastDate = addUtcDays(bounds.target, -1);
  const lastYear = lastDate.getUTCFullYear();
  const years = [];
  for (let year = firstYear; year <= lastYear; year += 1) {
    if (Array.from({ length: 12 }, (_, index) => index + 1).some((month) => monthIntersectsLife(year, month))) {
      years.push(year);
    }
  }
  return years;
}

function syncHomeMonthCalendarMonthOptions(preferredMonth = null) {
  if (!homeMonthCalendarYear || !homeMonthCalendarMonth) return;
  const year = Number(homeMonthCalendarYear.value);
  const fallbackMonth = Number(preferredMonth || homeMonthCalendarMonth.value || currentProgress?.today?.slice(5, 7) || 1);
  homeMonthCalendarMonth.replaceChildren();
  const availableMonths = [];
  for (let month = 1; month <= 12; month += 1) {
    if (!monthIntersectsLife(year, month)) continue;
    availableMonths.push(month);
    const option = document.createElement("option");
    option.value = String(month);
    option.textContent = `${month} 月`;
    homeMonthCalendarMonth.appendChild(option);
  }
  if (!availableMonths.length) return;
  const selectedMonth = availableMonths.includes(fallbackMonth)
    ? fallbackMonth
    : availableMonths.reduce((best, month) => Math.abs(month - fallbackMonth) < Math.abs(best - fallbackMonth) ? month : best, availableMonths[0]);
  homeMonthCalendarMonth.value = String(selectedMonth);
}

function syncHomeMonthCalendarPicker() {
  if (!currentProgress?.today || !homeMonthCalendarYear || !homeMonthCalendarMonth) return;
  const monthKey = homeMonthCalendarMonthKey || currentProgress.today.slice(0, 7);
  const [yearText, monthText] = monthKey.split("-");
  const years = validHomeCalendarYears();
  homeMonthCalendarYear.replaceChildren();
  years.forEach((year) => {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = `${year} 年`;
    homeMonthCalendarYear.appendChild(option);
  });
  if (!years.length) return;
  const year = years.includes(Number(yearText)) ? Number(yearText) : years[0];
  homeMonthCalendarYear.value = String(year);
  syncHomeMonthCalendarMonthOptions(Number(monthText));
}

function openHomeMonthCalendarPicker() {
  if (!homeMonthCalendarPicker || !homeMonthCalendarPickerButton) return;
  syncHomeMonthCalendarPicker();
  homeMonthCalendarPicker.classList.remove("hidden");
  homeMonthCalendarPickerButton.setAttribute("aria-expanded", "true");
  requestAnimationFrame(() => homeMonthCalendarYear?.focus({ preventScroll: true }));
}

function setHomeMonthCalendarMonth(monthKey, { closePicker = true } = {}) {
  if (!/^\d{4}-\d{2}$/.test(monthKey)) return;
  const [yearText, monthText] = monthKey.split("-");
  if (!monthIntersectsLife(Number(yearText), Number(monthText))) return;
  homeMonthCalendarMonthKey = monthKey;
  renderHomeMonthCalendar();
  syncHomeMonthCalendarPicker();
  if (closePicker) closeHomeMonthCalendarPicker({ restoreFocus: true });
}

function renderHomeMonthCalendar() {
  if (!homeMonthCalendarGrid || !homeMonthCalendarTitle || !currentProgress?.today) return;

  const todayMonthKey = currentProgress.today.slice(0, 7);
  if (!homeMonthCalendarMonthKey) homeMonthCalendarMonthKey = todayMonthKey;
  const [activeYearText, activeMonthText] = homeMonthCalendarMonthKey.split("-");
  if (!monthIntersectsLife(Number(activeYearText), Number(activeMonthText))) homeMonthCalendarMonthKey = todayMonthKey;
  const monthKey = homeMonthCalendarMonthKey;
  const [yearText, monthText] = monthKey.split("-");
  homeMonthCalendarTitle.textContent = `${Number(yearText)} 年 ${Number(monthText)} 月`;
  homeMonthCalendarPickerButton?.classList.toggle("is-away-from-current", monthKey !== todayMonthKey);
  homeMonthCalendarGrid.replaceChildren();

  const firstDay = new Date(Date.UTC(Number(yearText), Number(monthText) - 1, 1));
  const mondayOffset = (firstDay.getUTCDay() + 6) % 7;
  const children = dayChildrenForMonth(monthKey);

  for (let index = 0; index < mondayOffset; index += 1) {
    const placeholder = document.createElement("span");
    placeholder.className = "hero-month-day-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    homeMonthCalendarGrid.appendChild(placeholder);
  }

  children.forEach((child) => {
    const button = periodChildButton(child, currentProgress.today);
    button.classList.add("hero-month-day");
    homeMonthCalendarGrid.appendChild(
      decorateDayCalendarButton(button, child, { actionLabel: "点击查看或添加" }),
    );
  });

  const trailing = (7 - ((mondayOffset + children.length) % 7)) % 7;
  for (let index = 0; index < trailing; index += 1) {
    const placeholder = document.createElement("span");
    placeholder.className = "hero-month-day-placeholder";
    placeholder.setAttribute("aria-hidden", "true");
    homeMonthCalendarGrid.appendChild(placeholder);
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
    const button = periodChildButton(child, selectedKey);
    periodChildGrid.appendChild(decorateDayCalendarButton(button, child));
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
    .filter(([, value]) => value && (value.has_event || value.has_memory || value.has_plan || value.has_material))
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
  try {
    await loadMemoryTags();
  } catch (error) {
    showOperationError(error);
  }
  setMemoryTagSelection(tagModeForKind(kind), item.tags || []);
  if (kind === "memory") {
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

const MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024;

function formatAttachmentSize(sizeBytes) {
  const size = Number(sizeBytes) || 0;
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(size < 10 * 1024 ? 1 : 0)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(size < 10 * 1024 * 1024 ? 1 : 0)} MB`;
  if (size < 1024 * 1024 * 1024 * 1024) return `${(size / (1024 * 1024 * 1024)).toFixed(size < 10 * 1024 * 1024 * 1024 ? 2 : 1)} GB`;
  return `${(size / (1024 * 1024 * 1024 * 1024)).toFixed(2)} TB`;
}

function formatAttachmentTimelineTime(value) {
  const text = String(value || "").trim();
  if (!text) return "";
  const match = text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
  if (!match) return text;
  return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}:${match[6]}`;
}

function attachmentTimelineLabel(attachment) {
  if (!attachment?.timeline_at) return "";
  const source = String(attachment.timeline_time_source || "");
  const time = formatAttachmentTimelineTime(attachment.timeline_at);
  if (source.startsWith("exif:")) return `拍摄于 ${time}`;
  if (source === "document:created") return `文档创建于 ${time}`;
  if (source === "document:modified") return `文档保存于 ${time}`;
  if (source === "file:last_modified") return `文件修改于 ${time}`;
  if (source === "content:date") return `来源内容日期 ${String(attachment.timeline_date || time).slice(0, 10)}`;
  if (source === "attachment:added") return `附件添加于 ${time}`;
  if (source === "manual") return `手工确认于 ${time}`;
  return `资料时间 ${time}`;
}

function attachmentTimelineSourceLabel(attachment) {
  const source = String(attachment?.timeline_time_source || "");
  if (source.startsWith("exif:")) return "照片 EXIF";
  if (source === "document:created") return "文档内部创建时间";
  if (source === "document:modified") return "文档内部保存时间";
  if (source === "file:last_modified") return "文件修改时间";
  if (source === "content:date") return "来源内容日期";
  if (source === "attachment:added") return "附件添加时间";
  if (source === "manual") return "手工确认时间";
  return "资料元数据";
}

function isImageAttachment(attachment) {
  return String(attachment?.media_type || "").toLowerCase().startsWith("image/");
}

function isImageFile(file) {
  return String(file?.type || "").toLowerCase().startsWith("image/");
}

function videoExtension(value) {
  const name = String(value?.name || value?.filename || value || "").toLowerCase();
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot) : "";
}

function isVideoAttachment(attachment) {
  const mediaType = String(attachment?.media_type || "").toLowerCase();
  return mediaType.startsWith("video/") || [".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".flv", ".ts", ".mts", ".m2ts"].includes(videoExtension(attachment));
}

function isVideoFile(file) {
  const mediaType = String(file?.type || "").toLowerCase();
  return mediaType.startsWith("video/") || [".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi", ".wmv", ".flv", ".ts", ".mts", ".m2ts"].includes(videoExtension(file));
}

function formatVideoDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  if (!total && Number(seconds) !== 0) return "";
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

function videoTechnicalMetaParts(attachment) {
  if (!isVideoAttachment(attachment)) return [];
  const parts = [];
  const duration = formatVideoDuration(attachment?.duration_seconds);
  if (duration) parts.push(duration);
  const width = Number(attachment?.video_width || 0);
  const height = Number(attachment?.video_height || 0);
  if (width > 0 && height > 0) parts.push(`${width}×${height}`);
  if (attachment?.video_codec) parts.push(String(attachment.video_codec));
  if (attachment?.audio_codec) parts.push(`音频 ${String(attachment.audio_codec)}`);
  return parts;
}

function readEbmlVint(bytes, offset, { keepMarker = false } = {}) {
  if (offset >= bytes.length) return null;
  const first = bytes[offset];
  let length = 1;
  let mask = 0x80;
  while (length <= 8 && !(first & mask)) {
    length += 1;
    mask >>= 1;
  }
  if (length > 8 || offset + length > bytes.length) return null;
  let value = keepMarker ? first : (first & (mask - 1));
  for (let index = 1; index < length; index += 1) value = value * 256 + bytes[offset + index];
  if (!keepMarker) {
    let unknown = (first & (mask - 1)) === (mask - 1);
    for (let index = 1; index < length && unknown; index += 1) unknown = bytes[offset + index] === 0xff;
    if (unknown) value = null;
  }
  return { length, value };
}

function readEbmlUnsigned(bytes, start, size) {
  if (size <= 0 || size > 8 || start + size > bytes.length) return null;
  let value = 0;
  for (let index = 0; index < size; index += 1) value = value * 256 + bytes[start + index];
  return Number.isSafeInteger(value) ? value : null;
}

function readEbmlFloat(bytes, start, size) {
  if (![4, 8].includes(size) || start + size > bytes.length) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset + start, size);
  return size === 4 ? view.getFloat32(0, false) : view.getFloat64(0, false);
}

function readEbmlString(bytes, start, size) {
  if (size <= 0 || start + size > bytes.length) return "";
  return new TextDecoder("utf-8", { fatal: false }).decode(bytes.subarray(start, start + size)).replace(/\0+$/g, "").trim();
}

function friendlyAudioCodec(codecId) {
  const codec = String(codecId || "");
  const labels = {
    "A_DTS": "DTS",
    "A_AC3": "AC-3",
    "A_EAC3": "E-AC-3",
    "A_TRUEHD": "Dolby TrueHD",
    "A_MLP": "MLP / TrueHD",
    "A_AAC": "AAC",
    "A_OPUS": "Opus",
    "A_VORBIS": "Vorbis",
    "A_FLAC": "FLAC",
    "A_MPEG/L3": "MP3",
  };
  return labels[codec] || codec.replace(/^A_/, "").replaceAll("_", " ");
}

function friendlyVideoCodec(codecId) {
  const codec = String(codecId || "");
  const labels = {
    "V_MPEGH/ISO/HEVC": "H.265 / HEVC",
    "V_MPEG4/ISO/AVC": "H.264 / AVC",
    "V_AV1": "AV1",
    "V_VP9": "VP9",
    "V_VP8": "VP8",
    "V_MPEG2": "MPEG-2",
  };
  return labels[codec] || codec.replace(/^V_/, "").replaceAll("_", " ");
}

async function extractMatroskaVideoMetadata(file) {
  if (![".mkv", ".webm"].includes(videoExtension(file))) return null;
  const probeSize = Math.min(file.size, 16 * 1024 * 1024);
  const bytes = new Uint8Array(await file.slice(0, probeSize).arrayBuffer());
  const result = {
    timecodeScale: 1000000, rawDuration: null, width: null, height: null, codec: "",
    audioCodec: "", audioCodecId: "", audioChannels: null, audioSampleRate: null,
  };
  const containerIds = new Set([0x18538067, 0x1549a966, 0x1654ae6b, 0xae, 0xe0, 0xe1]);
  const parseRange = (start, end, context = {}) => {
    let offset = start;
    while (offset < end && offset < bytes.length) {
      const idInfo = readEbmlVint(bytes, offset, { keepMarker: true });
      if (!idInfo) break;
      const sizeInfo = readEbmlVint(bytes, offset + idInfo.length);
      if (!sizeInfo) break;
      const id = idInfo.value;
      const payloadStart = offset + idInfo.length + sizeInfo.length;
      if (payloadStart > bytes.length) break;
      const declaredSize = sizeInfo.value;
      const payloadEnd = declaredSize == null ? Math.min(end, bytes.length) : Math.min(payloadStart + declaredSize, end, bytes.length);
      if (id === 0x1f43b675) return; // Cluster: metadata normally ends before media frames.
      if (id === 0x2ad7b1) result.timecodeScale = readEbmlUnsigned(bytes, payloadStart, payloadEnd - payloadStart) || result.timecodeScale;
      else if (id === 0x4489) result.rawDuration = readEbmlFloat(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0x83) context.track.type = readEbmlUnsigned(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0x86) context.track.codec = readEbmlString(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0xb0) context.track.width = readEbmlUnsigned(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0xba) context.track.height = readEbmlUnsigned(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0x9f) context.track.audioChannels = readEbmlUnsigned(bytes, payloadStart, payloadEnd - payloadStart);
      else if (context.track && id === 0xb5) context.track.audioSampleRate = readEbmlFloat(bytes, payloadStart, payloadEnd - payloadStart);

      if (containerIds.has(id) && payloadEnd > payloadStart) {
        if (id === 0xae) {
          const track = {};
          parseRange(payloadStart, payloadEnd, { track });
          if (track.type === 1 && (!result.width || !result.height)) {
            result.width = track.width || result.width;
            result.height = track.height || result.height;
            result.codec = friendlyVideoCodec(track.codec) || result.codec;
          } else if (track.type === 2 && !result.audioCodecId) {
            result.audioCodecId = String(track.codec || "");
            result.audioCodec = friendlyAudioCodec(track.codec);
            result.audioChannels = track.audioChannels || null;
            result.audioSampleRate = track.audioSampleRate || null;
          }
        } else {
          parseRange(payloadStart, payloadEnd, context);
        }
      }
      if (declaredSize == null || payloadEnd <= offset) break;
      offset = payloadStart + declaredSize;
      if (offset > end || offset > bytes.length) break;
    }
  };
  parseRange(0, bytes.length, {});
  const metadata = {};
  if (Number.isFinite(result.rawDuration) && result.rawDuration >= 0) {
    metadata.duration_seconds = result.rawDuration * result.timecodeScale / 1_000_000_000;
  }
  if (result.width) metadata.video_width = result.width;
  if (result.height) metadata.video_height = result.height;
  if (result.codec) metadata.video_codec = result.codec;
  if (result.audioCodec) metadata.audio_codec = result.audioCodec;
  if (result.audioCodecId) metadata.audio_codec_id = result.audioCodecId;
  if (result.audioChannels) metadata.audio_channels = result.audioChannels;
  if (result.audioSampleRate) metadata.audio_sample_rate = Math.round(result.audioSampleRate);
  return Object.keys(metadata).length ? metadata : null;
}

function canvasBlob(canvas, type = "image/jpeg", quality = 0.76) {
  return new Promise((resolve) => canvas.toBlob(resolve, type, quality));
}

async function generateVideoInfoPoster(file, metadata) {
  const canvas = document.createElement("canvas");
  canvas.width = 480;
  canvas.height = 270;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, "#303b35");
  gradient.addColorStop(1, "#171c19");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(255,255,255,.12)";
  ctx.beginPath();
  ctx.arc(72, 82, 38, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,.9)";
  ctx.beginPath();
  ctx.moveTo(64, 62);
  ctx.lineTo(64, 102);
  ctx.lineTo(96, 82);
  ctx.closePath();
  ctx.fill();
  ctx.font = "600 22px sans-serif";
  ctx.fillText("视频资料", 28, 164);
  ctx.font = "15px sans-serif";
  ctx.fillStyle = "rgba(255,255,255,.72)";
  const details = [formatVideoDuration(metadata?.duration_seconds)];
  if (metadata?.video_width && metadata?.video_height) details.push(`${metadata.video_width}×${metadata.video_height}`);
  if (metadata?.video_codec) details.push(metadata.video_codec);
  ctx.fillText(details.filter(Boolean).join(" · ") || "媒体信息待识别", 28, 193);
  ctx.font = "13px sans-serif";
  ctx.fillStyle = "rgba(255,255,255,.5)";
  const filename = String(file?.name || "视频");
  ctx.fillText(filename.length > 52 ? `${filename.slice(0, 49)}…` : filename, 28, 226);
  return canvasBlob(canvas);
}

async function extractNativeVideoAssets(file) {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "metadata";
  video.muted = true;
  video.playsInline = true;
  video.src = url;
  const waitFor = (successEvent, errorEvent = "error", timeoutMs = 6500) => new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error("VIDEO_METADATA_TIMEOUT")), timeoutMs);
    const cleanup = () => {
      window.clearTimeout(timer);
      video.removeEventListener(successEvent, onSuccess);
      video.removeEventListener(errorEvent, onError);
    };
    const onSuccess = () => { cleanup(); resolve(); };
    const onError = () => { cleanup(); reject(new Error("VIDEO_METADATA_UNSUPPORTED")); };
    video.addEventListener(successEvent, onSuccess, { once: true });
    video.addEventListener(errorEvent, onError, { once: true });
  });
  try {
    await waitFor("loadedmetadata");
    const metadata = {};
    if (Number.isFinite(video.duration) && video.duration >= 0) metadata.duration_seconds = video.duration;
    if (video.videoWidth > 0) metadata.video_width = video.videoWidth;
    if (video.videoHeight > 0) metadata.video_height = video.videoHeight;
    let posterBlob = null;
    if (video.videoWidth > 0 && video.videoHeight > 0 && Number.isFinite(video.duration) && video.duration > 0.05) {
      const seekTo = Math.min(Math.max(video.duration * 0.1, 0.05), Math.max(0.05, Math.min(30, video.duration - 0.03)));
      if (Math.abs(video.currentTime - seekTo) > 0.02) {
        video.currentTime = seekTo;
        await waitFor("seeked", "error", 5000).catch(() => {});
      }
      const maxWidth = 480;
      const scale = Math.min(1, maxWidth / video.videoWidth);
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      const ctx = canvas.getContext("2d");
      if (ctx) {
        try {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          posterBlob = await canvasBlob(canvas);
        } catch (_) {}
      }
    }
    return { metadata, posterBlob };
  } finally {
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}

const videoMediaAssetCache = new WeakMap();

async function extractVideoMediaAssets(file) {
  if (!isVideoFile(file)) return { metadata: {}, previewBlob: null };
  if (videoMediaAssetCache.has(file)) return videoMediaAssetCache.get(file);
  const promise = (async () => {
    let nativeAssets = null;
    try {
      nativeAssets = await extractNativeVideoAssets(file);
    } catch (_) {}
    let ebmlMetadata = null;
    const nativeMetadata = nativeAssets?.metadata || {};
    if ([".mkv", ".webm"].includes(videoExtension(file)) && (!nativeMetadata.duration_seconds || !nativeMetadata.video_width || !nativeMetadata.video_height)) {
      try {
        ebmlMetadata = await extractMatroskaVideoMetadata(file);
      } catch (_) {}
    }
    const metadata = {
      ...(ebmlMetadata || {}),
      ...nativeMetadata,
    };
    metadata.metadata_source = nativeAssets ? "browser:html-video" : (ebmlMetadata ? "browser:matroska-ebml" : "browser:video-file");
    let previewBlob = nativeAssets?.posterBlob || null;
    metadata.poster_source = previewBlob ? "browser:video-frame" : "generated:video-info";
    if (!previewBlob) previewBlob = await generateVideoInfoPoster(file, metadata);
    return { metadata, previewBlob };
  })();
  videoMediaAssetCache.set(file, promise);
  return promise;
}

async function requestAttachmentStreamTicket(attachment) {
  if (!attachment?.id) throw new Error("资料标识无效");
  return api(
    `/api/v1/attachments/${encodeURIComponent(attachment.id)}/playback-ticket`,
    { method: "POST" },
    true,
  );
}

function attachmentStreamUrlWithTicket(attachment, ticket, { download = false } = {}) {
  const params = new URLSearchParams({ ticket: ticket.ticket });
  if (download) params.set("download", "true");
  return `/api/v1/attachments/${encodeURIComponent(attachment.id)}/stream?${params.toString()}`;
}

async function attachmentStreamUrl(attachment, { download = false } = {}) {
  const ticket = await requestAttachmentStreamTicket(attachment);
  return attachmentStreamUrlWithTicket(attachment, ticket, { download });
}

function attachmentCompatAudioUrlWithTicket(attachment, ticket) {
  const params = new URLSearchParams({ ticket: ticket.ticket });
  return `/api/v1/attachments/${encodeURIComponent(attachment.id)}/audio-compat/stream?${params.toString()}`;
}

async function attachmentAudioCompatStatus(attachment) {
  return api(
    `/api/v1/attachments/${encodeURIComponent(attachment.id)}/audio-compat`,
    { method: "GET" },
    true,
  );
}

async function startAttachmentAudioCompat(attachment) {
  return api(
    `/api/v1/attachments/${encodeURIComponent(attachment.id)}/audio-compat`,
    { method: "POST" },
    true,
  );
}

function isVideoPlayerOpen() {
  return Boolean(videoPlayerModal && !videoPlayerModal.classList.contains("hidden"));
}

function videoPlayerMetadataText(attachment) {
  return [
    formatAttachmentSize(attachment?.size_bytes),
    attachment?.media_type || "视频",
    ...videoTechnicalMetaParts(attachment || {}),
    attachmentTimelineLabel(attachment || {}),
  ].filter(Boolean).join(" · ");
}

function showVideoPlayerStatus(message, { error = false } = {}) {
  if (!videoPlayerStatus) return;
  videoPlayerStatus.textContent = message || "";
  videoPlayerStatus.classList.toggle("hidden", !message);
  videoPlayerStatus.classList.toggle("is-error", Boolean(error));
}

function clearVideoAudioCompatPoll() {
  if (videoAudioCompatPollTimer) window.clearTimeout(videoAudioCompatPollTimer);
  videoAudioCompatPollTimer = null;
}

function showVideoAudioCompatStatus(message, { error = false, action = "" } = {}) {
  if (videoAudioCompatStatus) {
    videoAudioCompatStatus.textContent = message || "";
    videoAudioCompatStatus.classList.toggle("hidden", !message);
    videoAudioCompatStatus.classList.toggle("is-error", Boolean(error));
  }
  if (videoAudioCompatAction) {
    videoAudioCompatAction.textContent = action || "生成兼容音轨";
    videoAudioCompatAction.classList.toggle("hidden", !action);
  }
}

function resetVideoCompatAudio() {
  clearVideoAudioCompatPoll();
  videoAudioCompatState = null;
  videoAudioCompatRateSample = null;
  videoPlayerTicket = null;
  if (videoCompatAudio) {
    videoCompatAudio.pause();
    videoCompatAudio.removeAttribute("src");
    videoCompatAudio.load();
  }
  showVideoAudioCompatStatus("");
}

function syncCompatAudioFromVideo({ force = false } = {}) {
  if (!videoCompatAudio?.src || !videoPlayer) return;
  videoCompatAudio.muted = Boolean(videoPlayer.muted);
  videoCompatAudio.volume = Math.min(1, Math.max(0, Number(videoPlayer.volume) || 0));
  videoCompatAudio.playbackRate = Math.min(4, Math.max(0.25, Number(videoPlayer.playbackRate) || 1));
  const target = Number(videoPlayer.currentTime || 0);
  const current = Number(videoCompatAudio.currentTime || 0);
  if (force || Math.abs(current - target) > 0.35) {
    try { videoCompatAudio.currentTime = target; } catch (_) {}
  }
}

function audioCompatTargetCodec(state = videoAudioCompatState) {
  return String(state?.compat_codec || state?.target_codec || "AAC").trim() || "AAC";
}

function playCompatAudioWithVideo() {
  if (!videoCompatAudio?.src || !videoPlayer || videoPlayer.paused) return;
  syncCompatAudioFromVideo({ force: true });
  videoCompatAudio.play().catch(() => {
    showVideoAudioCompatStatus("兼容音轨已准备，请暂停后再次点击播放以启用声音。", { action: "重新启用声音" });
  });
}

function attachCompatAudio(attachment, ticket, { generatedNow = false } = {}) {
  if (!videoCompatAudio || !attachment || !ticket) return;
  const expected = attachmentCompatAudioUrlWithTicket(attachment, ticket);
  if (!videoCompatAudio.src || !videoCompatAudio.src.includes("/audio-compat/stream?")) {
    videoCompatAudio.src = expected;
    videoCompatAudio.load();
  }
  syncCompatAudioFromVideo({ force: true });
  const sourceCodec = videoAudioCompatState?.audio_codec || "原音轨";
  const targetCodec = audioCompatTargetCodec();
  showVideoAudioCompatStatus(`兼容音轨：${sourceCodec} → ${targetCodec} · 已启用`);
  if (generatedNow && videoPlayer && !videoPlayer.paused) {
    videoPlayer.pause();
    showVideoAudioCompatStatus(`兼容音轨：${sourceCodec} → ${targetCodec} · 已生成，请点击播放继续`);
  }
}

function audioCompatProgressText(state) {
  const codec = state?.audio_codec || "当前音轨";
  const percent = Number(state?.progress_percent || 0);
  const processed = Number(state?.processed_bytes || 0);
  const total = Number(state?.source_size_bytes || 0);
  const attachmentId = String(state?.attachment_id || videoPlayerAttachment?.id || "");
  const now = globalThis.performance?.now?.() ?? Date.now();
  let speedBps = 0;
  if (
    videoAudioCompatRateSample
    && videoAudioCompatRateSample.attachmentId === attachmentId
    && processed >= videoAudioCompatRateSample.processed
  ) {
    const elapsed = Math.max(0, (now - videoAudioCompatRateSample.at) / 1000);
    const delta = Math.max(0, processed - videoAudioCompatRateSample.processed);
    if (elapsed >= 0.45 && delta > 0) {
      const current = delta / elapsed;
      const previous = Number(videoAudioCompatRateSample.speedBps || 0);
      speedBps = previous > 0 ? previous * 0.6 + current * 0.4 : current;
    } else {
      speedBps = Number(videoAudioCompatRateSample.speedBps || 0);
    }
  }
  videoAudioCompatRateSample = { attachmentId, at: now, processed, speedBps };

  let detail = total > 0
    ? `${percent.toFixed(1)}% · ${formatAttachmentSize(processed)} / ${formatAttachmentSize(total)}`
    : `${percent.toFixed(1)}%`;
  const rate = formatLargeUploadRate(speedBps);
  if (rate) detail += ` · ${rate}`;
  if (rate && total > processed) {
    const eta = formatLargeUploadEta((total - processed) / speedBps);
    if (eta) detail += ` · 预计剩余 ${eta}`;
  }
  return `检测到 ${codec}，正在生成浏览器兼容 ${audioCompatTargetCodec(state)} 音轨 · ${detail}`;
}

async function renderVideoAudioCompatState(state, attachment, ticket, requestId, { generatedNow = false } = {}) {
  if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
  videoAudioCompatState = state || null;
  const statusValue = String(state?.state || "unknown");
  if (statusValue === "ready" || state?.has_compat_audio) {
    clearVideoAudioCompatPoll();
    attachCompatAudio(attachment, ticket, { generatedNow });
    return;
  }
  if (statusValue === "building") {
    showVideoAudioCompatStatus(audioCompatProgressText(state));
    clearVideoAudioCompatPoll();
    videoAudioCompatPollTimer = window.setTimeout(async () => {
      if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
      try {
        const next = await attachmentAudioCompatStatus(attachment);
        const becameReady = String(next?.state || "") === "ready";
        await renderVideoAudioCompatState(next, attachment, ticket, requestId, { generatedNow: becameReady });
      } catch (error) {
        showVideoAudioCompatStatus(friendlyErrorMessage(error), { error: true, action: "重试" });
      }
    }, 1200);
    return;
  }
  if (statusValue === "unavailable") {
    const codec = state?.audio_codec || "不兼容音轨";
    showVideoAudioCompatStatus(`检测到 ${codec}，但未找到 FFmpeg。已自动检查 C:\\ffmpeg 和系统 PATH。`, { error: true });
    return;
  }
  if (statusValue === "error" || statusValue === "cancelled") {
    showVideoAudioCompatStatus(state?.error || "兼容音轨生成失败", { error: true, action: "重试" });
    return;
  }
  if (statusValue === "not_needed") {
    showVideoAudioCompatStatus(state?.audio_codec ? `音轨 ${state.audio_codec} 可直接由浏览器处理` : "");
    return;
  }
  if (state?.needs_compat) {
    showVideoAudioCompatStatus(`检测到 ${state.audio_codec || "不兼容音轨"}`, { action: "生成兼容音轨" });
    return;
  }
  showVideoAudioCompatStatus("");
}

async function prepareVideoAudioCompatibility(attachment, ticket, requestId) {
  try {
    let state = await attachmentAudioCompatStatus(attachment);
    if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
    if (state?.needs_compat && !state?.has_compat_audio && state?.state === "idle" && state?.ffmpeg_available) {
      showVideoAudioCompatStatus(`检测到 ${state.audio_codec || "不兼容音轨"}，正在启动兼容音轨生成…`);
      state = await startAttachmentAudioCompat(attachment);
    }
    await renderVideoAudioCompatState(state, attachment, ticket, requestId);
  } catch (error) {
    if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
    showVideoAudioCompatStatus(friendlyErrorMessage(error), { error: true, action: "重试" });
  }
}

async function openVideoPlayer(attachment, returnFocus = null) {
  if (!videoPlayerModal || !videoPlayer || !attachment) return;
  closeAttachmentPreview({ restoreFocus: false });
  const requestId = ++videoPlayerRequestSequence;
  videoPlayerAttachment = attachment;
  videoPlayerReturnFocus = returnFocus instanceof HTMLElement ? returnFocus : document.activeElement;
  videoPlayerTitle.textContent = attachment.filename || "视频播放";
  videoPlayerMeta.textContent = videoPlayerMetadataText(attachment) || "视频资料";
  videoPlayerModal.classList.remove("hidden");
  videoPlayerModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("video-player-open");
  videoPlayer.pause();
  videoPlayer.removeAttribute("src");
  videoPlayer.removeAttribute("poster");
  videoPlayer.load();
  resetVideoCompatAudio();
  showVideoPlayerStatus("正在建立安全播放通道…");
  if (attachment.has_preview) {
    mediaPreviewObjectUrl(attachment).then((url) => {
      if (requestId === videoPlayerRequestSequence && isVideoPlayerOpen()) videoPlayer.poster = url;
    }).catch(() => {});
  }
  try {
    const ticket = await requestAttachmentStreamTicket(attachment);
    if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
    videoPlayerTicket = ticket;
    videoPlayer.src = attachmentStreamUrlWithTicket(attachment, ticket);
    videoPlayer.load();
    showVideoPlayerStatus("正在按需解密视频…");
    // Probe and, when required, start the one-time audio derivative in parallel.
    // If a compatible track already exists it is attached before the first play.
    await prepareVideoAudioCompatibility(attachment, ticket, requestId);
    if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
    videoPlayer.play().catch(() => {});
  } catch (error) {
    if (requestId !== videoPlayerRequestSequence || !isVideoPlayerOpen()) return;
    showVideoPlayerStatus(friendlyErrorMessage(error), { error: true });
  }
  window.requestAnimationFrame(() => closeVideoPlayerButton?.focus({ preventScroll: true }));
}

function closeVideoPlayer({ restoreFocus = true } = {}) {
  if (!videoPlayerModal || videoPlayerModal.classList.contains("hidden")) return;
  videoPlayerRequestSequence += 1;
  videoPlayer?.pause();
  videoPlayer?.removeAttribute("src");
  videoPlayer?.removeAttribute("poster");
  videoPlayer?.load();
  resetVideoCompatAudio();
  videoPlayerModal.classList.add("hidden");
  videoPlayerModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("video-player-open");
  showVideoPlayerStatus("");
  const returnFocus = videoPlayerReturnFocus;
  videoPlayerAttachment = null;
  videoPlayerReturnFocus = null;
  if (restoreFocus && returnFocus instanceof HTMLElement && document.contains(returnFocus)) {
    returnFocus.focus({ preventScroll: true });
  }
}

async function fetchAttachmentBlob(attachment) {
  const headers = {};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(
    `/api/v1/attachments/${encodeURIComponent(attachment.id)}/download`,
    { headers },
  );
  if (!response.ok) {
    let message = `读取附件失败：${response.status}`;
    try {
      const payload = await response.json();
      message = payload.error?.message || message;
    } catch (_) {}
    const error = new Error(message);
    error.code = response.status === 404 ? "ATTACHMENT_NOT_FOUND" : "ATTACHMENT_READ_FAILED";
    throw error;
  }
  return response.blob();
}

async function attachmentObjectUrl(attachment) {
  const cached = attachmentObjectUrls.get(attachment.id);
  if (cached) return cached;
  const pending = attachmentObjectUrlPromises.get(attachment.id);
  if (pending) return pending;
  const promise = fetchAttachmentBlob(attachment)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      attachmentObjectUrls.set(attachment.id, url);
      attachmentObjectUrlPromises.delete(attachment.id);
      return url;
    })
    .catch((error) => {
      attachmentObjectUrlPromises.delete(attachment.id);
      throw error;
    });
  attachmentObjectUrlPromises.set(attachment.id, promise);
  return promise;
}

async function fetchMediaPreviewBlob(attachment) {
  const headers = {};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(
    `/api/v1/attachments/${encodeURIComponent(attachment.id)}/preview`,
    { headers },
  );
  if (!response.ok) throw new Error(`读取视频封面失败：${response.status}`);
  return response.blob();
}

async function mediaPreviewObjectUrl(attachment) {
  const cached = mediaPreviewObjectUrls.get(attachment.id);
  if (cached) return cached;
  const pending = mediaPreviewObjectUrlPromises.get(attachment.id);
  if (pending) return pending;
  const promise = fetchMediaPreviewBlob(attachment)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      mediaPreviewObjectUrls.set(attachment.id, url);
      mediaPreviewObjectUrlPromises.delete(attachment.id);
      return url;
    })
    .catch((error) => {
      mediaPreviewObjectUrlPromises.delete(attachment.id);
      throw error;
    });
  mediaPreviewObjectUrlPromises.set(attachment.id, promise);
  return promise;
}

function releaseAttachmentObjectUrl(attachmentId) {
  const url = attachmentObjectUrls.get(attachmentId);
  if (url) URL.revokeObjectURL(url);
  attachmentObjectUrls.delete(attachmentId);
  attachmentObjectUrlPromises.delete(attachmentId);
}

function releaseAllAttachmentObjectUrls() {
  attachmentObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  attachmentObjectUrls.clear();
  attachmentObjectUrlPromises.clear();
  mediaPreviewObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  mediaPreviewObjectUrls.clear();
  mediaPreviewObjectUrlPromises.clear();
}

function isAttachmentPreviewOpen() {
  return Boolean(attachmentPreviewModal && !attachmentPreviewModal.classList.contains("hidden"));
}

function isAttachmentPreviewFullscreen() {
  return Boolean(attachmentPreviewModal && document.fullscreenElement === attachmentPreviewModal);
}

async function setAttachmentPreviewFullscreen(enabled) {
  if (!attachmentPreviewModal || !isAttachmentPreviewOpen()) return;
  if (enabled) {
    attachmentPreviewModal.classList.add("is-fullscreen-zoom");
    if (!isAttachmentPreviewFullscreen() && attachmentPreviewModal.requestFullscreen) {
      try {
        await attachmentPreviewModal.requestFullscreen({ navigationUI: "hide" });
      } catch (_error) {
        // 浏览器拒绝 Fullscreen API 时仍保留沉浸式放大样式。
      }
    }
    return;
  }
  attachmentPreviewModal.classList.remove("is-fullscreen-zoom");
  if (isAttachmentPreviewFullscreen() && document.exitFullscreen) {
    try {
      await document.exitFullscreen();
    } catch (_error) {
      // 退出全屏失败时仍恢复页面内预览样式。
    }
  }
}

async function toggleAttachmentPreviewFullscreen() {
  const shouldEnter = !isAttachmentPreviewFullscreen() && !attachmentPreviewModal?.classList.contains("is-fullscreen-zoom");
  await setAttachmentPreviewFullscreen(shouldEnter);
}

async function renderAttachmentPreview() {
  if (!isAttachmentPreviewOpen()) return;
  const attachment = attachmentPreviewItems[attachmentPreviewIndex];
  if (!attachment) {
    closeAttachmentPreview();
    return;
  }
  attachmentPreviewTitle.textContent = attachment.filename || "未命名图片";
  const previewMetaParts = [formatAttachmentSize(attachment.size_bytes), attachment.media_type || "图片"];
  const timelineLabel = attachmentTimelineLabel(attachment);
  if (timelineLabel) previewMetaParts.push(timelineLabel);
  attachmentPreviewMeta.textContent = previewMetaParts.join(" · ");
  attachmentPreviewCounter.textContent = `${attachmentPreviewIndex + 1} / ${attachmentPreviewItems.length}`;
  const canNavigate = attachmentPreviewItems.length > 1;
  attachmentPreviewPrevious.disabled = !canNavigate;
  attachmentPreviewNext.disabled = !canNavigate;
  attachmentPreviewImage.removeAttribute("src");
  attachmentPreviewImage.alt = attachment.filename || "图片附件";
  attachmentPreviewImage.classList.add("is-loading");
  attachmentPreviewStatus.classList.remove("hidden", "is-error");
  attachmentPreviewStatus.textContent = "正在解密图片…";
  const expectedId = attachment.id;
  try {
    const url = await attachmentObjectUrl(attachment);
    if (!isAttachmentPreviewOpen() || attachmentPreviewItems[attachmentPreviewIndex]?.id !== expectedId) return;
    attachmentPreviewImage.src = url;
    attachmentPreviewImage.classList.remove("is-loading");
    attachmentPreviewStatus.classList.add("hidden");
  } catch (error) {
    if (!isAttachmentPreviewOpen() || attachmentPreviewItems[attachmentPreviewIndex]?.id !== expectedId) return;
    attachmentPreviewImage.classList.remove("is-loading");
    attachmentPreviewStatus.textContent = friendlyErrorMessage(error);
    attachmentPreviewStatus.classList.add("is-error");
  }
}

function openAttachmentPreview(items, index, returnFocus = null) {
  if (!attachmentPreviewModal) return;
  const images = (items || []).filter(isImageAttachment);
  const target = items?.[index];
  const normalizedIndex = Math.max(0, images.findIndex((item) => item.id === target?.id));
  if (!images.length) return;
  attachmentPreviewItems = images;
  attachmentPreviewIndex = normalizedIndex;
  attachmentPreviewReturnFocus = returnFocus instanceof HTMLElement ? returnFocus : document.activeElement;
  attachmentPreviewModal.classList.remove("hidden");
  attachmentPreviewModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("attachment-preview-open");
  renderAttachmentPreview();
  window.requestAnimationFrame(() => closeAttachmentPreviewButton?.focus());
}

function closeAttachmentPreview({ restoreFocus = true } = {}) {
  if (!attachmentPreviewModal || attachmentPreviewModal.classList.contains("hidden")) return;
  if (isAttachmentPreviewFullscreen() && document.exitFullscreen) {
    document.exitFullscreen().catch(() => {});
  }
  attachmentPreviewModal.classList.remove("is-fullscreen-zoom");
  attachmentPreviewModal.classList.add("hidden");
  attachmentPreviewModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("attachment-preview-open");
  attachmentPreviewImage?.removeAttribute("src");
  attachmentPreviewStatus?.classList.remove("is-error");
  attachmentPreviewItems = [];
  attachmentPreviewIndex = -1;
  if (restoreFocus && attachmentPreviewReturnFocus instanceof HTMLElement && document.contains(attachmentPreviewReturnFocus)) {
    attachmentPreviewReturnFocus.focus({ preventScroll: true });
  }
  attachmentPreviewReturnFocus = null;
}

function navigateAttachmentPreview(delta) {
  if (!isAttachmentPreviewOpen() || attachmentPreviewItems.length < 2) return;
  attachmentPreviewIndex = (attachmentPreviewIndex + delta + attachmentPreviewItems.length) % attachmentPreviewItems.length;
  renderAttachmentPreview();
}

function createAttachmentThumbnail(attachment, images, imageIndex, { lazy = false } = {}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "attachment-thumbnail-button";
  button.setAttribute("aria-label", `预览图片：${attachment.filename || "未命名图片"}`);
  const image = document.createElement("img");
  image.className = "attachment-thumbnail-image";
  image.alt = "";
  const placeholder = document.createElement("span");
  placeholder.className = "attachment-thumbnail-placeholder";
  placeholder.textContent = "图片";
  button.append(image, placeholder);
  const loadThumbnail = () => {
    if (button.dataset.thumbnailStarted === "1") return;
    button.dataset.thumbnailStarted = "1";
    attachmentObjectUrl(attachment)
      .then((url) => {
        if (!document.contains(button)) return;
        image.src = url;
        button.classList.add("is-loaded");
      })
      .catch(() => {
        if (!document.contains(button)) return;
        placeholder.textContent = "无法预览";
        button.classList.add("is-error");
      });
  };
  if (lazy) observeMaterialThumbnail(button, loadThumbnail);
  else loadThumbnail();
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    openAttachmentPreview(images, imageIndex, button);
  });
  return button;
}

function createVideoThumbnail(attachment, { lazy = false } = {}) {
  const preview = document.createElement("button");
  preview.type = "button";
  preview.className = "video-thumbnail";
  preview.setAttribute("aria-label", `播放视频：${attachment.filename || "未命名视频"}`);
  preview.title = isLargeMediaOffline(attachment) ? "媒体离线：恢复 data/media 后可播放" : "在线播放";
  preview.classList.toggle("is-media-offline", isLargeMediaOffline(attachment));
  const image = document.createElement("img");
  image.className = "video-thumbnail-image";
  image.alt = "";
  const placeholder = document.createElement("span");
  placeholder.className = "video-thumbnail-placeholder";
  placeholder.textContent = "视频";
  const play = document.createElement("span");
  play.className = "video-thumbnail-play";
  play.textContent = "▶";
  play.setAttribute("aria-hidden", "true");
  const duration = document.createElement("span");
  duration.className = "video-thumbnail-duration";
  duration.textContent = formatVideoDuration(attachment.duration_seconds);
  duration.classList.toggle("hidden", !duration.textContent);
  preview.append(image, placeholder, play, duration);
  const loadPreview = () => {
    if (!attachment.has_preview || preview.dataset.previewStarted === "1") return;
    preview.dataset.previewStarted = "1";
    mediaPreviewObjectUrl(attachment)
      .then((url) => {
        if (!document.contains(preview)) return;
        image.src = url;
        preview.classList.add("is-loaded");
      })
      .catch(() => {
        if (!document.contains(preview)) return;
        preview.classList.add("is-error");
      });
  };
  if (attachment.has_preview) {
    if (lazy) observeMaterialThumbnail(preview, loadPreview);
    else loadPreview();
  }
  preview.addEventListener("click", (event) => {
    event.stopPropagation();
    if (isLargeMediaOffline(attachment)) {
      showToast("大型媒体当前离线，请恢复 data/media 媒体库后再播放", "info");
      return;
    }
    openVideoPlayer(attachment, preview);
  });
  return preview;
}

const pendingAttachmentElements = {
  event: {
    input: document.getElementById("eventPendingAttachments"),
    list: document.getElementById("eventPendingAttachmentList"),
  },
  memory: {
    input: document.getElementById("memoryPendingAttachments"),
    list: document.getElementById("memoryPendingAttachmentList"),
  },
  plan: {
    input: document.getElementById("planPendingAttachments"),
    list: document.getElementById("planPendingAttachmentList"),
  },
};

function renderPendingContentAttachments(kind) {
  const elements = pendingAttachmentElements[kind];
  if (!elements?.list) return;
  elements.list.replaceChildren();
  const files = pendingContentAttachments[kind] || [];
  if (!files.length) {
    const empty = document.createElement("span");
    empty.className = "attachment-empty";
    empty.textContent = "尚未选择附件";
    elements.list.appendChild(empty);
    return;
  }

  files.forEach((file, index) => {
    const row = document.createElement("div");
    row.className = "attachment-item pending-attachment-item";
    if (isImageFile(file)) {
      const preview = document.createElement("span");
      preview.className = "pending-attachment-thumbnail";
      const image = document.createElement("img");
      image.alt = "";
      const localUrl = URL.createObjectURL(file);
      image.addEventListener("load", () => URL.revokeObjectURL(localUrl), { once: true });
      image.addEventListener("error", () => URL.revokeObjectURL(localUrl), { once: true });
      image.src = localUrl;
      preview.appendChild(image);
      row.appendChild(preview);
    }
    const main = document.createElement("div");
    main.className = "attachment-item-main";
    const name = document.createElement("span");
    name.className = "attachment-name";
    name.textContent = file.name || "未命名附件";
    const meta = document.createElement("span");
    meta.className = "attachment-meta";
    meta.textContent = `${formatAttachmentSize(file.size)} · ${file.type || "文件"}`;
    main.append(name, meta);

    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "attachment-link-button is-danger";
    removeButton.textContent = "移除";
    removeButton.addEventListener("click", () => {
      pendingContentAttachments[kind].splice(index, 1);
      renderPendingContentAttachments(kind);
    });
    row.append(main, removeButton);
    elements.list.appendChild(row);
  });
}

function clearPendingContentAttachments(kind) {
  pendingContentAttachments[kind] = [];
  const elements = pendingAttachmentElements[kind];
  if (elements?.input) elements.input.value = "";
  renderPendingContentAttachments(kind);
}

function addPendingContentAttachments(kind, files) {
  const current = pendingContentAttachments[kind] || [];
  const known = new Set(current.map((file) => pendingAttachmentSignature(file)));
  let oversizedCount = 0;
  Array.from(files || []).forEach((file) => {
    if (file.size > MAX_ATTACHMENT_BYTES) {
      oversizedCount += 1;
      return;
    }
    const signature = pendingAttachmentSignature(file);
    if (known.has(signature)) return;
    known.add(signature);
    current.push(file);
  });
  pendingContentAttachments[kind] = current;
  renderPendingContentAttachments(kind);
  if (oversizedCount) showToast(`${oversizedCount} 个附件超过 50 MB，未加入待上传列表。`, "error");
}

async function uploadPendingContentAttachments(kind, contentId) {
  const queued = [...(pendingContentAttachments[kind] || [])];
  const failed = [];
  let uploaded = 0;
  for (const file of queued) {
    try {
      await uploadAttachmentFile(kind, contentId, file);
      uploaded += 1;
    } catch (error) {
      failed.push({ file, error });
    }
  }
  pendingContentAttachments[kind] = failed.map((entry) => entry.file);
  renderPendingContentAttachments(kind);
  return { uploaded, failed };
}

Object.entries(pendingAttachmentElements).forEach(([kind, elements]) => {
  elements.input?.addEventListener("change", () => {
    addPendingContentAttachments(kind, elements.input.files);
    elements.input.value = "";
  });
  renderPendingContentAttachments(kind);
});

async function uploadAttachmentFile(kind, contentId, file) {
  if (file.size > MAX_ATTACHMENT_BYTES) {
    const error = new Error(`“${file.name}”超过 50 MB，暂不能上传。`);
    error.code = "ATTACHMENT_TOO_LARGE";
    throw error;
  }
  const formData = new FormData();
  formData.append("attachment_file", file, file.name);
  if (isVideoFile(file)) {
    try {
      const assets = await extractVideoMediaAssets(file);
      if (assets?.metadata && Object.keys(assets.metadata).length) {
        formData.append("video_metadata_json", JSON.stringify(assets.metadata));
      }
      if (assets?.previewBlob) {
        formData.append("video_preview", assets.previewBlob, "video-preview.jpg");
      }
    } catch (error) {
      console.warn("LifeGraph attachment video metadata extraction skipped:", error);
    }
  }
  if (Number.isFinite(file.lastModified) && file.lastModified > 0) {
    formData.append("file_last_modified_ms", String(Math.trunc(file.lastModified)));
  }
  const headers = {};
  if (token()) headers.Authorization = `Bearer ${token()}`;
  const response = await fetch(
    `/api/v1/content/${encodeURIComponent(kind)}/${encodeURIComponent(contentId)}/attachments`,
    { method: "POST", headers, body: formData },
  );
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

async function downloadAttachmentFile(attachment) {
  if (attachment?.is_large) {
    const url = await attachmentStreamUrl(attachment, { download: true });
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = attachment.filename || "attachment";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return;
  }
  const blob = await fetchAttachmentBlob(attachment);
  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = attachment.filename || "attachment";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function attachmentEmptyState() {
  const empty = document.createElement("p");
  empty.className = "attachment-empty";
  empty.textContent = "还没有附件。可以添加照片、文档或其他文件。";
  return empty;
}

async function refreshAttachmentPanel(panel, kind, item, button) {
  const contentId = item.id;
  const list = panel.querySelector(".attachment-list");
  list.replaceChildren();
  const loading = document.createElement("p");
  loading.className = "attachment-empty";
  loading.textContent = "正在读取附件…";
  list.appendChild(loading);
  try {
    const attachments = await api(
      `/api/v1/content/${encodeURIComponent(kind)}/${encodeURIComponent(contentId)}/attachments`,
      {},
      true,
    );
    button.textContent = `附件 ${attachments.length}`;
    list.replaceChildren();
    if (!attachments.length) {
      list.appendChild(attachmentEmptyState());
      return;
    }
    const imageAttachments = attachments.filter(isImageAttachment);
    const imageIndexById = new Map(imageAttachments.map((attachment, index) => [attachment.id, index]));
    attachments.forEach((attachment) => {
      const row = document.createElement("div");
      row.className = "attachment-item";
      if (isImageAttachment(attachment)) {
        row.classList.add("has-thumbnail");
        row.appendChild(
          createAttachmentThumbnail(
            attachment,
            imageAttachments,
            imageIndexById.get(attachment.id) || 0,
          ),
        );
      }

      const main = document.createElement("div");
      main.className = "attachment-item-main";
      const name = document.createElement("strong");
      name.className = "attachment-name";
      name.textContent = attachment.filename || "未命名附件";
      const meta = document.createElement("span");
      meta.className = "attachment-meta";
      meta.textContent = [
        formatAttachmentSize(attachment.size_bytes),
        attachment.media_type || "文件",
        mediaAvailabilityLabel(attachment),
      ].filter(Boolean).join(" · ");
      main.append(name, meta);
      const timelineLabel = attachmentTimelineLabel(attachment);
      if (timelineLabel) {
        const timelineMeta = document.createElement("span");
        timelineMeta.className = "attachment-timeline-meta";
        timelineMeta.textContent = timelineLabel;
        main.appendChild(timelineMeta);
      }
      if (attachment.timeline_date) {
        const timelineRow = document.createElement("span");
        timelineRow.className = "attachment-timeline-date";
        const timelineButton = document.createElement("button");
        timelineButton.type = "button";
        timelineButton.className = "attachment-timeline-date-button";
        timelineButton.textContent = `时间轴归属 ${attachment.timeline_date}`;
        timelineButton.title = `${attachmentTimelineSourceLabel(attachment)} · 打开 ${attachment.timeline_date} 的人生资料`;
        timelineButton.addEventListener("click", () => openPeriodDrawer("day", attachment.timeline_date));
        timelineRow.appendChild(timelineButton);
        main.appendChild(timelineRow);
      }

      const actions = document.createElement("div");
      actions.className = "attachment-item-actions";
      if (!attachment.timeline_date) {
        const fallbackButton = document.createElement("button");
        fallbackButton.type = "button";
        fallbackButton.className = "attachment-link-button";
        fallbackButton.textContent = "归入来源/添加时间";
        fallbackButton.title = "优先归入来源内容的明确日期；否则使用附件添加时间";
        fallbackButton.addEventListener("click", async () => {
          const updated = await assignAttachmentTimelineFallback(attachment, fallbackButton);
          if (updated) await refreshAttachmentPanel(panel, kind, item, button);
        });
        actions.appendChild(fallbackButton);
      }
      if (isVideoAttachment(attachment)) {
        const playButton = document.createElement("button");
        playButton.type = "button";
        playButton.className = "attachment-link-button";
        playButton.textContent = "播放";
        applyMediaAvailabilityToButton(playButton, attachment, "播放");
        playButton.addEventListener("click", () => openVideoPlayer(attachment, playButton));
        actions.appendChild(playButton);
      }
      const downloadButton = document.createElement("button");
      downloadButton.type = "button";
      downloadButton.className = "attachment-link-button";
      downloadButton.textContent = "下载";
      applyMediaAvailabilityToButton(downloadButton, attachment, "下载");
      downloadButton.addEventListener("click", async () => {
        setButtonBusy(downloadButton, true, "下载中…");
        try {
          await downloadAttachmentFile(attachment);
        } catch (error) {
          showOperationError(error);
        } finally {
          setButtonBusy(downloadButton, false);
        }
      });

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "attachment-link-button is-danger";
      deleteButton.textContent = "删除";
      deleteButton.addEventListener("click", async () => {
        const confirmed = await askConfirmation({
          eyebrow: "删除附件",
          title: `删除“${attachment.filename || "未命名附件"}”吗？`,
          message: "附件会从本地加密仓库中永久删除；正文内容不会被删除。",
          confirmLabel: "删除附件",
          tone: "danger",
        });
        if (!confirmed) return;
        setButtonBusy(deleteButton, true, "删除中…");
        try {
          await api(
            `/api/v1/content/${encodeURIComponent(kind)}/${encodeURIComponent(contentId)}/attachments/${encodeURIComponent(attachment.id)}`,
            { method: "DELETE" },
            true,
          );
          releaseAttachmentObjectUrl(attachment.id);
          if (attachmentPreviewItems.some((item) => item.id === attachment.id)) {
            closeAttachmentPreview({ restoreFocus: false });
          }
          if (videoPlayerAttachment?.id === attachment.id) closeVideoPlayer({ restoreFocus: false });
          showToast("附件已删除", "success");
          await refreshAttachmentPanel(panel, kind, item, button);
        } catch (error) {
          showOperationError(error);
        } finally {
          setButtonBusy(deleteButton, false);
        }
      });
      actions.append(downloadButton, deleteButton);
      row.append(main, actions);
      list.appendChild(row);
    });
  } catch (error) {
    list.replaceChildren();
    const failed = document.createElement("p");
    failed.className = "attachment-empty is-error";
    failed.textContent = friendlyErrorMessage(error);
    list.appendChild(failed);
  }
}

function createAttachmentPanel(kind, item, button) {
  const panel = document.createElement("section");
  panel.className = "attachment-panel hidden";
  panel.setAttribute("aria-label", `${item.title}的附件`);

  const toolbar = document.createElement("div");
  toolbar.className = "attachment-panel-toolbar";
  const heading = document.createElement("strong");
  heading.textContent = "附件";
  const uploadLabel = document.createElement("label");
  uploadLabel.className = "attachment-upload-button";
  uploadLabel.textContent = "＋ 添加附件";
  const input = document.createElement("input");
  input.type = "file";
  input.multiple = true;
  input.className = "attachment-file-input";
  uploadLabel.appendChild(input);
  toolbar.append(heading, uploadLabel);

  const list = document.createElement("div");
  list.className = "attachment-list";
  const note = document.createElement("p");
  note.className = "attachment-storage-note";
  note.textContent = "单个附件最多 50 MB；文件内容会使用当前仓库主密钥加密后保存在本地。";
  panel.append(toolbar, list, note);

  input.addEventListener("change", async () => {
    const files = Array.from(input.files || []);
    if (!files.length) return;
    uploadLabel.classList.add("is-busy");
    input.disabled = true;
    try {
      for (const file of files) {
        await uploadAttachmentFile(kind, item.id, file);
      }
      showToast(files.length > 1 ? `已添加 ${files.length} 个附件` : "附件已添加", "success");
      await refreshAttachmentPanel(panel, kind, item, button);
    } catch (error) {
      showOperationError(error);
    } finally {
      input.value = "";
      input.disabled = false;
      uploadLabel.classList.remove("is-busy");
    }
  });
  return panel;
}

closeVideoPlayerButton?.addEventListener("click", () => closeVideoPlayer());
videoPlayerModal?.addEventListener("click", (event) => {
  if (event.target === videoPlayerModal) closeVideoPlayer();
});
videoPlayer?.addEventListener("loadedmetadata", () => {
  if (isVideoPlayerOpen()) showVideoPlayerStatus("");
});
videoPlayer?.addEventListener("canplay", () => {
  if (isVideoPlayerOpen()) showVideoPlayerStatus("");
});
videoPlayer?.addEventListener("play", () => {
  if (!isVideoPlayerOpen()) return;
  playCompatAudioWithVideo();
});
videoPlayer?.addEventListener("playing", () => {
  if (isVideoPlayerOpen()) {
    showVideoPlayerStatus("");
    playCompatAudioWithVideo();
  }
});
videoPlayer?.addEventListener("pause", () => {
  if (isVideoPlayerOpen()) videoCompatAudio?.pause();
});
videoPlayer?.addEventListener("volumechange", () => {
  if (isVideoPlayerOpen()) syncCompatAudioFromVideo();
});
videoPlayer?.addEventListener("ratechange", () => {
  if (isVideoPlayerOpen()) syncCompatAudioFromVideo();
});
videoPlayer?.addEventListener("timeupdate", () => {
  if (isVideoPlayerOpen() && videoCompatAudio?.src) syncCompatAudioFromVideo();
});
videoPlayer?.addEventListener("waiting", () => {
  if (isVideoPlayerOpen()) showVideoPlayerStatus("正在按需解密并缓冲…");
});
videoPlayer?.addEventListener("seeking", () => {
  if (isVideoPlayerOpen()) {
    showVideoPlayerStatus("正在定位并解密目标分块…");
    videoCompatAudio?.pause();
  }
});
videoPlayer?.addEventListener("seeked", () => {
  if (!isVideoPlayerOpen()) return;
  if (videoPlayer.readyState >= 2) showVideoPlayerStatus("");
  syncCompatAudioFromVideo({ force: true });
  if (!videoPlayer.paused) playCompatAudioWithVideo();
});
videoPlayer?.addEventListener("error", () => {
  if (!isVideoPlayerOpen()) return;
  const codec = String(videoPlayerAttachment?.video_codec || "").toUpperCase();
  const container = String(videoPlayerAttachment?.media_type || "");
  const technical = [container, codec].filter(Boolean).join(" · ");
  showVideoPlayerStatus(
    `Range 播放通道已建立，但当前浏览器无法解码这个视频${technical ? `（${technical}）` : ""}。MKV / H.265 等格式可能依赖系统解码器，可下载原视频用本地播放器打开。`,
    { error: true },
  );
});
videoCompatAudio?.addEventListener("error", () => {
  if (!isVideoPlayerOpen() || !videoCompatAudio?.src) return;
  showVideoAudioCompatStatus("兼容音轨读取失败，可关闭播放器后重新打开再试。", { error: true, action: "重试" });
});
videoAudioCompatAction?.addEventListener("click", async () => {
  if (!videoPlayerAttachment || !videoPlayerTicket) return;
  if (videoCompatAudio?.src && videoAudioCompatState?.state === "ready") {
    syncCompatAudioFromVideo({ force: true });
    if (videoPlayer?.paused) {
      videoPlayer.play().catch(() => {});
    } else {
      videoCompatAudio.play().catch(() => {});
    }
    showVideoAudioCompatStatus(`兼容音轨：${videoAudioCompatState?.audio_codec || "原音轨"} → ${audioCompatTargetCodec()} · 已启用`);
    return;
  }
  const requestId = videoPlayerRequestSequence;
  setButtonBusy(videoAudioCompatAction, true, "启动中…");
  try {
    const state = await startAttachmentAudioCompat(videoPlayerAttachment);
    await renderVideoAudioCompatState(state, videoPlayerAttachment, videoPlayerTicket, requestId);
  } catch (error) {
    showVideoAudioCompatStatus(friendlyErrorMessage(error), { error: true, action: "重试" });
  } finally {
    setButtonBusy(videoAudioCompatAction, false);
  }
});

downloadVideoPlayerButton?.addEventListener("click", async () => {
  if (!videoPlayerAttachment) return;
  setButtonBusy(downloadVideoPlayerButton, true, "准备中…");
  try {
    await downloadAttachmentFile(videoPlayerAttachment);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(downloadVideoPlayerButton, false);
  }
});

closeAttachmentPreviewButton?.addEventListener("click", () => closeAttachmentPreview());
attachmentPreviewModal?.addEventListener("click", (event) => {
  if (event.target === attachmentPreviewModal) closeAttachmentPreview();
});
attachmentPreviewPrevious?.addEventListener("click", () => navigateAttachmentPreview(-1));
attachmentPreviewNext?.addEventListener("click", () => navigateAttachmentPreview(1));
attachmentPreviewStage?.addEventListener("wheel", (event) => {
  if (!isAttachmentPreviewOpen()) return;
  event.preventDefault();
  if (attachmentPreviewItems.length < 2) return;
  const now = performance.now();
  if (now - attachmentPreviewLastWheelAt < 320) return;
  const delta = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
  if (!delta) return;
  attachmentPreviewLastWheelAt = now;
  navigateAttachmentPreview(delta > 0 ? 1 : -1);
}, { passive: false });
attachmentPreviewImage?.addEventListener("mousedown", (event) => {
  if (event.button === 1) event.preventDefault();
});
attachmentPreviewImage?.addEventListener("auxclick", async (event) => {
  if (event.button !== 1 || !isAttachmentPreviewOpen()) return;
  event.preventDefault();
  await toggleAttachmentPreviewFullscreen();
});
attachmentPreviewImage?.addEventListener("contextmenu", (event) => {
  if (!isAttachmentPreviewOpen()) return;
  event.preventDefault();
  closeAttachmentPreview();
});
document.addEventListener("fullscreenchange", () => {
  if (!attachmentPreviewModal || document.fullscreenElement === attachmentPreviewModal) return;
  attachmentPreviewModal.classList.remove("is-fullscreen-zoom");
});
downloadAttachmentPreviewButton?.addEventListener("click", async () => {
  const attachment = attachmentPreviewItems[attachmentPreviewIndex];
  if (!attachment) return;
  setButtonBusy(downloadAttachmentPreviewButton, true, "下载中…");
  try {
    await downloadAttachmentFile(attachment);
  } catch (error) {
    showOperationError(error);
  } finally {
    setButtonBusy(downloadAttachmentPreviewButton, false);
  }
});

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

    const attachmentButton = document.createElement("button");
    attachmentButton.type = "button";
    attachmentButton.className = "content-attachment-button";
    attachmentButton.textContent = `附件 ${Number.isInteger(item.attachment_count) ? item.attachment_count : 0}`;
    attachmentButton.setAttribute("aria-expanded", "false");
    attachmentButton.setAttribute("aria-label", `查看或添加附件：${item.title}`);

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
    actions.append(attachmentButton, moreButton, menu);
    header.appendChild(actions);
    article.appendChild(header);

    const attachmentPanel = createAttachmentPanel(kind, item, attachmentButton);
    attachmentButton.addEventListener("click", async (event) => {
      event.stopPropagation();
      closeOpenContentMenu();
      const opening = attachmentPanel.classList.contains("hidden");
      attachmentPanel.classList.toggle("hidden", !opening);
      attachmentButton.setAttribute("aria-expanded", opening ? "true" : "false");
      if (opening) {
        await refreshAttachmentPanel(attachmentPanel, kind, item, attachmentButton);
      }
    });

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

    appendMemoryTagBadges(article, item.tags || []);
    article.appendChild(attachmentPanel);

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

function materialSourceKindLabel(kind) {
  if (kind === "event") return "事件";
  if (kind === "memory") return "记忆";
  if (kind === "plan") return "计划";
  return "内容";
}

function ensureMaterialSectionToggle() {
  if (!materialSectionToggle?.isConnected) {
    const heading = materialSection?.querySelector(".material-kind-heading");
    if (!heading) return null;
    let actions = heading.querySelector(".material-heading-actions");
    if (!actions) {
      actions = document.createElement("div");
      actions.className = "material-heading-actions";
      heading.appendChild(actions);
    }
    materialSectionToggle = actions.querySelector("#materialSectionToggle");
    if (!materialSectionToggle) {
      materialSectionToggle = document.createElement("button");
      materialSectionToggle.id = "materialSectionToggle";
      materialSectionToggle.className = "material-section-toggle hidden";
      materialSectionToggle.type = "button";
      materialSectionToggle.setAttribute("aria-expanded", "false");
      materialSectionToggle.textContent = "展开全部";
      actions.appendChild(materialSectionToggle);
    }
  }
  if (materialSectionToggle.dataset.collapseBound !== "1") {
    materialSectionToggle.dataset.collapseBound = "1";
    materialSectionToggle.addEventListener("click", () => {
      materialSectionExpanded = !materialSectionExpanded;
      updateMaterialSectionCollapse();
    });
  }
  return materialSectionToggle;
}

function updateMaterialSectionCollapse() {
  if (!materialList) return;
  const cards = Array.from(materialList.querySelectorAll(".material-item"));
  const total = Math.max(materialSectionTotal, cards.length);
  const hasOverflow = total > MATERIAL_SECTION_COLLAPSED_LIMIT;
  cards.forEach((card, index) => {
    card.classList.toggle(
      "hidden",
      hasOverflow && !materialSectionExpanded && index >= MATERIAL_SECTION_COLLAPSED_LIMIT,
    );
  });
  const toggle = ensureMaterialSectionToggle();
  if (!toggle) return;
  toggle.classList.toggle("hidden", !hasOverflow);
  toggle.hidden = !hasOverflow;
  toggle.setAttribute("aria-expanded", String(hasOverflow && materialSectionExpanded));
  toggle.textContent = materialSectionExpanded
    ? "收起"
    : (cards.length < total ? `展开已加载（${cards.length}/${total}）` : `展开全部（${total}）`);

  if (materialSectionLoadMore) {
    const hasMore = materialSectionNextOffset !== null && materialSectionNextOffset !== undefined;
    materialSectionLoadMore.classList.toggle("hidden", !hasMore || !materialSectionExpanded);
    materialSectionLoadMore.hidden = !hasMore || !materialSectionExpanded;
    materialSectionLoadMore.disabled = materialSectionLoadingMore;
    materialSectionLoadMore.textContent = materialSectionLoadingMore
      ? "加载中…"
      : `继续加载（${cards.length}/${total}）`;
  }
}

function renderMaterialList(materials = [], options = {}) {
  if (!materialSection || !materialList) return;
  const incoming = Array.isArray(materials) ? materials : [];
  const append = Boolean(options.append);
  if (append) {
    const known = new Set(materialSectionItems.map((item) => item.id));
    incoming.forEach((item) => {
      if (!known.has(item.id)) {
        materialSectionItems.push(item);
        known.add(item.id);
      }
    });
  } else {
    materialSectionItems = [...incoming];
    materialSectionExpanded = false;
  }
  const items = materialSectionItems;
  materialSectionTotal = Number(options.total ?? materialSectionTotal ?? items.length);
  if (!append && options.total === undefined) materialSectionTotal = items.length;
  materialSectionNextOffset = options.nextOffset ?? null;
  materialSection.classList.toggle("hidden", materialSectionTotal === 0);
  if (materialSectionCount) materialSectionCount.textContent = String(materialSectionTotal);
  materialList.replaceChildren();
  if (!items.length) {
    updateMaterialSectionCollapse();
    return;
  }

  const imageMaterials = items.filter(isImageAttachment);
  const imageIndexById = new Map(imageMaterials.map((attachment, index) => [attachment.id, index]));
  items.forEach((attachment) => {
    const card = document.createElement("article");
    card.className = "material-item";
    card.classList.toggle("is-media-offline", isLargeMediaOffline(attachment));
    if (isImageAttachment(attachment)) {
      card.classList.add("has-thumbnail");
      card.appendChild(
        createAttachmentThumbnail(
          attachment,
          imageMaterials,
          imageIndexById.get(attachment.id) || 0,
        ),
      );
    } else if (isVideoAttachment(attachment) && attachment.has_preview) {
      card.classList.add("has-thumbnail");
      card.appendChild(createVideoThumbnail(attachment));
    }

    const main = document.createElement("div");
    main.className = "material-item-main";
    const name = document.createElement("strong");
    name.className = "material-name";
    name.textContent = attachment.filename || "未命名资料";
    const meta = document.createElement("span");
    meta.className = "material-meta";
    const timelineLabel = attachmentTimelineLabel(attachment);
    meta.textContent = [
      formatAttachmentSize(attachment.size_bytes),
      attachment.media_type || "文件",
      ...videoTechnicalMetaParts(attachment),
      mediaAvailabilityLabel(attachment),
      timelineLabel,
    ].filter(Boolean).join(" · ");
    main.append(name, meta);

    const source = attachment.source_content;
    if (source?.period_key) {
      const sourceButton = document.createElement("button");
      sourceButton.type = "button";
      sourceButton.className = "material-source-button";
      sourceButton.textContent = `来自 ${source.period_key} · ${materialSourceKindLabel(source.kind)}：${source.title || "未命名内容"}`;
      sourceButton.title = "打开它所属的事件、记忆或计划";
      sourceButton.addEventListener("click", () => openPeriodDrawer(source.time_scope || "day", source.period_key));
      main.appendChild(sourceButton);
    } else if (attachment.is_independent) {
      const independent = document.createElement("span");
      independent.className = "material-source-independent";
      independent.textContent = "独立资料";
      main.appendChild(independent);
    }

    const actions = document.createElement("div");
    actions.className = "material-item-actions";
    if (isVideoAttachment(attachment)) {
      const playButton = document.createElement("button");
      playButton.type = "button";
      playButton.className = "attachment-link-button";
      playButton.textContent = "播放";
      applyMediaAvailabilityToButton(playButton, attachment, "播放");
      playButton.addEventListener("click", () => openVideoPlayer(attachment, playButton));
      actions.appendChild(playButton);
    }
    const downloadButton = document.createElement("button");
    downloadButton.type = "button";
    downloadButton.className = "attachment-link-button";
    downloadButton.textContent = "下载";
    applyMediaAvailabilityToButton(downloadButton, attachment, "下载");
    downloadButton.addEventListener("click", async () => {
      setButtonBusy(downloadButton, true, "下载中…");
      try {
        await downloadAttachmentFile(attachment);
      } catch (error) {
        showOperationError(error);
      } finally {
        setButtonBusy(downloadButton, false);
      }
    });
    actions.appendChild(downloadButton);
    card.append(main, actions);
    materialList.appendChild(card);
  });
  updateMaterialSectionCollapse();
}

async function loadMorePeriodMaterials({ silent = false } = {}) {
  if (materialSectionLoadingMore) return false;
  if (!selectedScope || !selectedPeriodKey) return false;
  if (materialSectionNextOffset === null || materialSectionNextOffset === undefined) return false;

  const scope = selectedScope;
  const periodKey = selectedPeriodKey;
  const offset = Number(materialSectionNextOffset || 0);
  const requestSequence = drawerRequestSequence;
  materialSectionLoadingMore = true;
  updateMaterialSectionCollapse();
  try {
    const page = await api(
      `/api/v1/periods/${encodeURIComponent(scope)}/${encodeURIComponent(periodKey)}/materials?limit=${PERIOD_MATERIAL_PAGE_SIZE}&offset=${offset}`,
      {},
      true,
    );
    if (requestSequence !== drawerRequestSequence || selectedScope !== scope || selectedPeriodKey !== periodKey) return false;
    renderMaterialList(page.items || [], {
      append: true,
      total: page.total,
      nextOffset: page.next_offset,
    });
    return true;
  } catch (error) {
    if (!silent) showOperationError(error);
    return false;
  } finally {
    materialSectionLoadingMore = false;
    updateMaterialSectionCollapse();
  }
}

ensureMaterialSectionToggle();
materialSectionLoadMore?.addEventListener("click", () => loadMorePeriodMaterials());

dateDrawerContent?.addEventListener("scroll", () => {
  if (!materialSectionExpanded || materialSectionLoadingMore) return;
  if (materialSectionNextOffset === null || materialSectionNextOffset === undefined) return;
  const remaining = dateDrawerContent.scrollHeight - dateDrawerContent.scrollTop - dateDrawerContent.clientHeight;
  if (remaining <= 280) loadMorePeriodMaterials({ silent: true });
}, { passive: true });

function scopeCopy(scope) {
  if (scope === "year") return { noun: "这一年", eyebrow: "年度详情" };
  if (scope === "month") return { noun: "这个月", eyebrow: "月份详情" };
  return { noun: "这一天", eyebrow: "日期详情" };
}

function renderPeriodDetail(detail) {
  const copy = scopeCopy(detail.scope);
  const collapsePeriodKey = `${detail.scope}:${selectedPeriodKey || detail.date || detail.label || ""}`;
  if (contentSectionCollapsePeriodKey !== collapsePeriodKey) {
    contentSectionCollapsePeriodKey = collapsePeriodKey;
    resetContentSectionCollapseState();
  }
  document.getElementById("dateDrawerEyebrow").textContent = `${detail.time_state_label} · ${copy.eyebrow}`;
  if (detail.scope === "day") {
    document.getElementById("dateDrawerTitle").textContent = `${detail.date} · ${detail.weekday}`;
    document.getElementById("dateDrawerMeta").textContent = `${detail.age} 岁 · 人生第 ${detail.life_day_number.toLocaleString()} 天 · ${detail.timezone}`;
  } else {
    document.getElementById("dateDrawerTitle").textContent = detail.label;
    document.getElementById("dateDrawerMeta").textContent = `${detail.start_date} 至 ${detail.end_date} · 共 ${detail.days_in_period} 天 · ${detail.timezone}`;
  }

  renderPeriodNavigator(detail);
  toggleEventFormButton.textContent = scopedContentCreateLabel("event", detail.scope);
  toggleMemoryFormButton.textContent = scopedContentCreateLabel("memory", detail.scope);
  renderContentList("eventList", detail.events, `${copy.noun}还没有事件。`, "event");
  renderContentList("memoryList", detail.memories, `${copy.noun}还没有个人记忆。`, "memory", "memory-card");
  renderContentList("planList", detail.plans, `${copy.noun}还没有未来计划。`, "plan", "plan-card", detail.plan_allowed);
  renderMaterialList(detail.materials || [], {
    total: Number(detail.materials_total ?? (detail.materials || []).length),
    nextOffset: detail.materials_next_offset ?? null,
  });

  const planUnavailable = !detail.plan_allowed;
  togglePlanFormButton.disabled = planUnavailable;
  togglePlanFormButton.textContent = planUnavailable
    ? `${periodScopeLabel(detail.scope)}计划不可新增`
    : scopedContentCreateLabel("plan", detail.scope);
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
  resetMemoryTagSelector(tagModeForKind(kind));
  try {
    await loadMemoryTags();
  } catch (error) {
    showOperationError(error);
  }
  if (kind === "memory") initMemoryRichEditor(memoryRichEditorIds.drawer, "");
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

materialCenterHomeButton?.addEventListener("click", openMaterialCenterModal);
materialCenterFullPageButton?.addEventListener("click", openMaterialCenterModal);
reviewMaterialTimeButton?.addEventListener("click", openMaterialTimeReviewList);
manageMaterialScanSourcesButton?.addEventListener("click", openMaterialAutoScanModal);
closeMaterialTimeCorrectionButton?.addEventListener("click", () => closeMaterialTimeCorrectionModal());
cancelMaterialTimeCorrectionButton?.addEventListener("click", () => closeMaterialTimeCorrectionModal());
materialTimeCorrectionModal?.addEventListener("click", (event) => {
  if (event.target === materialTimeCorrectionModal) closeMaterialTimeCorrectionModal();
});
materialTimeCorrectionForm?.addEventListener("submit", saveMaterialTimeCorrection);
closeMaterialAutoScanButton?.addEventListener("click", () => closeMaterialAutoScanModal());
materialAutoScanModal?.addEventListener("click", (event) => {
  if (event.target === materialAutoScanModal) closeMaterialAutoScanModal();
});
materialScanSourceForm?.addEventListener("submit", addMaterialScanSource);
startMaterialScannerButton?.addEventListener("click", () => startMaterialScanner());
pauseMaterialScannerButton?.addEventListener("click", pauseMaterialScanner);
scanMaterialDirectoryButton?.addEventListener("click", () => materialDirectoryInput?.click());
materialDirectoryInput?.addEventListener("change", async () => {
  const files = Array.from(materialDirectoryInput.files || []);
  if (!files.length) return;
  await startMaterialDirectoryScan(files);
});
importMaterialButton?.addEventListener("click", () => materialImportInput?.click());
materialImportInput?.addEventListener("change", async () => {
  const files = Array.from(materialImportInput.files || []);
  materialImportInput.value = "";
  await importIndependentMaterials(files);
});
closeMaterialDirectoryScanButton?.addEventListener("click", () => closeMaterialDirectoryScanModal());
cancelMaterialDirectoryScanButton?.addEventListener("click", () => closeMaterialDirectoryScanModal());
materialDirectoryScanModal?.addEventListener("click", (event) => {
  if (event.target === materialDirectoryScanModal) closeMaterialDirectoryScanModal();
});
materialDirectorySelectAll?.addEventListener("change", () => {
  materialDirectoryScanItems.forEach((item) => {
    if (materialDirectoryItemSelectable(item)) item.selected = materialDirectorySelectAll.checked;
  });
  renderMaterialDirectoryScanList();
});
importScannedMaterialsButton?.addEventListener("click", importSelectedScannedMaterials);
materialCenterTimelineViewButton?.addEventListener("click", () => setMaterialCenterViewMode("timeline"));
materialCenterListViewButton?.addEventListener("click", () => setMaterialCenterViewMode("list"));
materialTimelineBackfillButton?.addEventListener("click", toggleMaterialTimelineBackfill);
closeMaterialCenterButton?.addEventListener("click", () => closeMaterialCenterModalNow());
resetMaterialCenterButton?.addEventListener("click", () => resetMaterialCenterFilters());
materialCenterModal?.addEventListener("click", (event) => {
  if (event.target === materialCenterModal) closeMaterialCenterModalNow();
});
materialCenterForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runMaterialCenterBrowse();
});

contentCenterHomeButton?.addEventListener("click", openContentCenterModal);
contentCenterFullPageButton?.addEventListener("click", openContentCenterModal);
closeContentCenterButton?.addEventListener("click", () => closeContentCenterModalNow());
resetContentCenterButton?.addEventListener("click", () => resetContentCenterFilters());
contentCenterModal?.addEventListener("click", (event) => {
  if (event.target === contentCenterModal) closeContentCenterModalNow();
});
contentCenterForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runContentCenterBrowse();
});
contentCenterBatchModeToggle?.addEventListener("click", toggleContentCenterBatchMode);

contentCenterSelectAll?.addEventListener("change", () => {
  contentCenterCurrentItems.forEach((item) => {
    const key = contentCenterItemKey(item);
    if (contentCenterSelectAll.checked) selectedContentCenterItems.set(key, { kind: item.kind, id: item.id });
    else selectedContentCenterItems.delete(key);
  });
  updateContentCenterSelectionControls();
});
contentCenterClearSelectionButton?.addEventListener("click", clearContentCenterBatchSelection);
contentCenterBulkTagsButton?.addEventListener("click", openContentCenterBatchTagEditor);
contentCenterCloseBatchTagsButton?.addEventListener("click", () => closeContentCenterBatchTagEditor({ restoreFocus: true }));
contentCenterApplyBatchTagsButton?.addEventListener("click", applyContentCenterBatchTags);
contentCenterBatchNewTagName?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createContentCenterBatchTag();
});
document.querySelectorAll('input[name="content_center_batch_operation"]').forEach((input) => {
  input.addEventListener("change", () => {
    renderContentCenterBatchTagOptions();
    if (selectedContentCenterBatchOperation() === "add") {
      requestAnimationFrame(() => contentCenterBatchNewTagName?.focus());
    }
  });
});

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
document.getElementById("toggleEventTagPicker")?.addEventListener("click", () => toggleMemoryTagPicker("event"));
document.getElementById("eventNewTagName")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createAndSelectMemoryTag("event");
});
toggleMemoryFormButton.addEventListener("click", () => toggleMemoryForm());
document.getElementById("cancelMemoryForm").addEventListener("click", () => toggleContentForm("memory", false));
document.getElementById("toggleMemoryTagPicker")?.addEventListener("click", () => toggleMemoryTagPicker("drawer"));
document.getElementById("memoryNewTagName")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createAndSelectMemoryTag("drawer");
});
togglePlanFormButton.addEventListener("click", () => togglePlanForm());
document.getElementById("cancelPlanForm").addEventListener("click", () => toggleContentForm("plan", false));
document.getElementById("togglePlanTagPicker")?.addEventListener("click", () => toggleMemoryTagPicker("plan"));
document.getElementById("planNewTagName")?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  createAndSelectMemoryTag("plan");
});
trashButton.addEventListener("click", openTrashDrawer);
refreshTrashButton.addEventListener("click", openTrashDrawer);
emptyTrashButton.addEventListener("click", emptyTrash);
document.getElementById("closeDateDrawer").addEventListener("click", requestCloseDateDrawer);
expandDateDrawerButton?.addEventListener("click", toggleDateDrawerExpanded);
previousContentDateButton?.addEventListener("click", () => navigateContentDate(-1, { source: "button" }));
nextContentDateButton?.addEventListener("click", () => navigateContentDate(1, { source: "button" }));
dateDrawerBackdrop.addEventListener("click", requestCloseDateDrawer);
homeMonthCalendarPickerButton?.addEventListener("click", (event) => {
  event.stopPropagation();
  if (homeMonthCalendarIsPickerOpen()) closeHomeMonthCalendarPicker();
  else openHomeMonthCalendarPicker();
});
homeMonthCalendarPicker?.addEventListener("click", (event) => event.stopPropagation());
homeMonthCalendarYear?.addEventListener("change", () => syncHomeMonthCalendarMonthOptions());
homeMonthCalendarApply?.addEventListener("click", () => {
  if (!homeMonthCalendarYear?.value || !homeMonthCalendarMonth?.value) return;
  const monthKey = `${homeMonthCalendarYear.value}-${String(Number(homeMonthCalendarMonth.value)).padStart(2, "0")}`;
  setHomeMonthCalendarMonth(monthKey);
});
homeMonthCalendarToday?.addEventListener("click", () => {
  if (!currentProgress?.today) return;
  setHomeMonthCalendarMonth(currentProgress.today.slice(0, 7));
});
document.addEventListener("click", (event) => {
  if (homeMonthCalendarIsPickerOpen() && !event.target.closest(".hero-month-calendar-picker")) {
    closeHomeMonthCalendarPicker();
  }
});

document.addEventListener("click", (event) => {
  if (!openContentMenu) return;
  const actionContainer = openContentMenu.closest(".content-card-actions");
  if (!actionContainer?.contains(event.target)) closeOpenContentMenu();
});
document.addEventListener("keydown", async (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && !event.altKey && !event.shiftKey) {
    if (
      !views.home.classList.contains("hidden") && currentProfile &&
      !isQuickMemoryOpen() && !isContentCenterOpen() && !isMaterialCenterOpen() && !isMemorySearchOpen() && !isMemoryMapFilterOpen() && !isAttachmentPreviewOpen() &&
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
  if (event.key === "Escape" && homeMonthCalendarIsPickerOpen()) {
    event.preventDefault();
    closeHomeMonthCalendarPicker({ restoreFocus: true });
    return;
  }
  if (isVideoPlayerOpen() && event.key === "Escape") {
    event.preventDefault();
    closeVideoPlayer();
    return;
  }
  if (isAttachmentPreviewOpen() && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
    event.preventDefault();
    navigateAttachmentPreview(event.key === "ArrowLeft" ? -1 : 1);
    return;
  }
  if (await handleDrawerOpenShortcut(event)) return;
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    if (await handleDrawerKeyboardNavigation(event)) return;
  }
  if (event.key !== "Escape") return;
  if (isAttachmentPreviewOpen()) {
    if (isAttachmentPreviewFullscreen() || attachmentPreviewModal?.classList.contains("is-fullscreen-zoom")) {
      event.preventDefault();
      await setAttachmentPreviewFullscreen(false);
      return;
    }
    closeAttachmentPreview();
    return;
  }
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
  if (isContentCenterOpen()) {
    if (contentCenterBatchTagEditor && !contentCenterBatchTagEditor.classList.contains("hidden")) {
      closeContentCenterBatchTagEditor({ restoreFocus: true });
      return;
    }
    if (activeContentCenterTagEditor) {
      closeContentCenterQuickTagEditor();
      return;
    }
    closeContentCenterModalNow();
    return;
  }
  if (isMaterialDirectoryScanOpen()) {
    closeMaterialDirectoryScanModal();
    return;
  }
  if (isMaterialCenterOpen()) {
    closeMaterialCenterModalNow();
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
    await syncContentTags(kind, savedItem.id, selectedMemoryTagIds[tagModeForKind(kind)]);
    const attachmentResult = await uploadPendingContentAttachments(kind, savedItem.id);
    await refreshContentStatuses();
    renderLifeMapView(true);

    if (attachmentResult.failed.length) {
      formNode.dataset.editId = savedItem.id;
      formNode.dataset.editRevision = String(savedItem.revision);
      formNode.classList.add("is-editing");
      config.toggleButton.textContent = "取消编辑";
      submit.textContent = "保存修改";
      const cancelButton = formNode.querySelector('.event-form-actions button[type="button"]');
      if (cancelButton) cancelButton.textContent = "取消编辑";
      updateContentSectionVisibility(kind);
      const firstError = attachmentResult.failed[0]?.error;
      const detail = firstError?.message ? `：${firstError.message}` : "";
      showToast(`内容已保存，但有 ${attachmentResult.failed.length} 个附件上传失败，可再次保存重试${detail}`, "error");
      return;
    }

    resetAllContentForms();
    const attachmentMessage = attachmentResult.uploaded ? `，并上传 ${attachmentResult.uploaded} 个附件` : "";
    showToast(`${editId ? config.editMessage : config.createMessage}${attachmentMessage}`, "success");
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
