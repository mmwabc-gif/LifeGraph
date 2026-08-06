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
const frontendBuildVersion = "0.0.3";
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
    INVALID_RECOVERY_CREDENTIAL: "恢复凭据不正确。",
    PROFILE_UPDATE_FAILED: "个人档案保存失败。",
    PIN_CHANGE_FAILED: "PIN 修改失败。",
    PIN_RESET_FAILED: "PIN 重置失败。",
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
const changePinForm = document.getElementById("changePinForm");
const resetPinModal = document.getElementById("resetPinModal");
const resetPinForm = document.getElementById("resetPinForm");
const openResetPinButton = document.getElementById("openResetPin");
const closeResetPinButton = document.getElementById("closeResetPin");
const cancelResetPinButton = document.getElementById("cancelResetPin");
let settingsReturnFocus = null;
let settingsProfileSnapshot = "";

function profileSettingsState() {
  if (!profileSettingsForm) return {};
  const form = new FormData(profileSettingsForm);
  return {
    display_name: String(form.get("display_name") || "").trim(),
    birth_date: String(form.get("birth_date") || ""),
  };
}

function hasUnsavedSettingsChanges() {
  if (settingsModal.classList.contains("hidden")) return false;
  const profileChanged = JSON.stringify(profileSettingsState()) !== settingsProfileSnapshot;
  const profilePin = profileSettingsForm.querySelector('[name="current_pin"]')?.value || "";
  const pinValues = Array.from(changePinForm.querySelectorAll('input[type="password"]')).some(input => input.value);
  return profileChanged || Boolean(profilePin) || pinValues;
}

function fillProfileSettingsForm() {
  if (!currentProfile) return;
  profileSettingsForm.elements.display_name.value = currentProfile.display_name || "";
  profileSettingsForm.elements.birth_date.value = currentProfile.birth_date || "";
  profileSettingsForm.elements.current_pin.value = "";
  changePinForm.reset();
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
  requestAnimationFrame(() => profileSettingsForm.elements.display_name.focus());
}

function closeSettingsModalNow() {
  if (!settingsModal || settingsModal.classList.contains("hidden")) return;
  settingsModal.classList.add("hidden");
  settingsModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("settings-open");
  profileSettingsForm.reset();
  changePinForm.reset();
  settingsProfileSnapshot = "";
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
      message: "当前个人档案或 PIN 表单中还有未保存内容。",
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
closeSettingsButton.addEventListener("click", requestCloseSettingsModal);
document.getElementById("cancelProfileSettings").addEventListener("click", requestCloseSettingsModal);
settingsModal.addEventListener("click", (event) => {
  if (event.target === settingsModal) requestCloseSettingsModal();
});
openResetPinButton.addEventListener("click", openResetPinModal);
closeResetPinButton.addEventListener("click", closeResetPinModal);
cancelResetPinButton.addEventListener("click", closeResetPinModal);
resetPinModal.addEventListener("click", (event) => {
  if (event.target === resetPinModal) closeResetPinModal();
});

profileSettingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentProfile) return;
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
  lifeGridSignature = "";
  fullPageGridSignature = "";
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
        document.getElementById("recoveryValue").textContent = data.generated_recovery_secret;
        document.getElementById("recoveryModal").classList.remove("hidden");
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
  document.getElementById("recoveryModal").classList.add("hidden");
  await loadHome({ enterFullPage: true });
});
document.getElementById("copyRecovery").addEventListener("click", async () => {
  await navigator.clipboard.writeText(document.getElementById("recoveryValue").textContent);
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

function createHierarchyCell({ label, ariaLabel, hoverText, startDate, endDate, state, selected = false, disabled = false, onClick }) {
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
  const signature = [cssWidth, cssHeight, dpr, currentProgress.birth_date, currentProgress.today, currentProgress.target_date, contentStatusRevision, selectedDate].join(":");

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
  fullPageLifeSummary.textContent = `完整人生共 ${totalDays.toLocaleString()} 天，日期连续排列；悬停查看日期，点击打开右侧详情。`;
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

function contentFormSnapshot(form) {
  return JSON.stringify({
    title: form.querySelector('[name="title"]')?.value || "",
    content: form.querySelector('[name="content"]')?.value || "",
  });
}

function captureContentFormSnapshot(kind) {
  const form = contentFormConfigurations[kind].form;
  form.dataset.initialSnapshot = contentFormSnapshot(form);
}

function isContentFormDirty(kind) {
  const form = contentFormConfigurations[kind].form;
  if (form.classList.contains("hidden")) return false;
  return contentFormSnapshot(form) !== (form.dataset.initialSnapshot || JSON.stringify({ title: "", content: "" }));
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
  const cancel = config.form.querySelector('button[type="button"]');
  config.form.reset();
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
    dateDrawerLoading.classList.add("hidden");
    dateDrawerContent.classList.remove("hidden");
    renderLifeMapView(true);
    if (fullPageLifeOpen) drawFullPageLifeGrid(true);
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
  config.form.querySelector('[name="content"]').value = item.content || "";
  config.form.querySelector('button[type="submit"]').textContent = "保存修改";
  config.form.querySelector('button[type="button"]').textContent = "取消编辑";
  config.toggleButton.textContent = "取消编辑";
  updateContentSectionVisibility(kind);
  captureContentFormSnapshot(kind);
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

    const header = document.createElement("div");
    header.className = "content-card-header";

    const title = document.createElement("h4");
    title.textContent = item.title;
    header.appendChild(title);

    const actions = document.createElement("div");
    actions.className = "content-card-actions";

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

    actions.append(moreButton, menu);
    header.appendChild(actions);
    article.appendChild(header);

    if (item.content) {
      const body = document.createElement("p");
      body.textContent = item.content;
      article.appendChild(body);
    }

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
  updateContentSectionVisibility(kind);
  captureContentFormSnapshot(kind);
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

toggleEventFormButton.addEventListener("click", () => toggleEventForm());
document.getElementById("cancelEventForm").addEventListener("click", () => toggleContentForm("event", false));
toggleMemoryFormButton.addEventListener("click", () => toggleMemoryForm());
document.getElementById("cancelMemoryForm").addEventListener("click", () => toggleContentForm("memory", false));
togglePlanFormButton.addEventListener("click", () => togglePlanForm());
document.getElementById("cancelPlanForm").addEventListener("click", () => toggleContentForm("plan", false));
trashButton.addEventListener("click", openTrashDrawer);
refreshTrashButton.addEventListener("click", openTrashDrawer);
emptyTrashButton.addEventListener("click", emptyTrash);
document.getElementById("closeDateDrawer").addEventListener("click", requestCloseDateDrawer);
dateDrawerBackdrop.addEventListener("click", requestCloseDateDrawer);
document.addEventListener("click", (event) => {
  if (!openContentMenu) return;
  const actionContainer = openContentMenu.closest(".content-card-actions");
  if (!actionContainer?.contains(event.target)) closeOpenContentMenu();
});
document.addEventListener("keydown", (event) => {
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
  if (!settingsModal.classList.contains("hidden")) {
    requestCloseSettingsModal();
    return;
  }
  if (!dateDrawer.classList.contains("hidden")) {
    requestCloseDateDrawer();
    return;
  }
  if (fullPageLifeOpen) requestCloseFullPageLifeView();
});

window.addEventListener("beforeunload", (event) => {
  if (!hasUnsavedContentChanges() && !hasUnsavedSettingsChanges()) return;
  event.preventDefault();
  event.returnValue = "";
});

async function submitScopedContent(kind) {
  if (!selectedScope || !selectedPeriodKey) return;
  const config = contentFormConfigurations[kind];
  const formNode = config.form;
  const form = new FormData(formNode);
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
          title: form.get("title"),
          content: form.get("content") || "",
          revision: editRevision,
        }
      : {
          time_scope: selectedScope,
          period_key: selectedPeriodKey,
          title: form.get("title"),
          content: form.get("content") || "",
        };
    await api(editId ? `${config.endpoint}/${encodeURIComponent(editId)}` : config.endpoint, {
      method: editId ? "PUT" : "POST",
      body: JSON.stringify(requestBody),
    }, true);
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
