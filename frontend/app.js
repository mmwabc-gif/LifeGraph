const views = {
  loading: document.getElementById("loadingView"),
  init: document.getElementById("initView"),
  unlock: document.getElementById("unlockView"),
  home: document.getElementById("homeView"),
};

const statusBadge = document.getElementById("statusBadge");
const lockButton = document.getElementById("lockButton");
const toast = document.getElementById("toast");
const tokenKey = "lifegraph_session_token";
const frontendBuildVersion = "0.0.2";
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

function token() {
  return sessionStorage.getItem(tokenKey);
}

function setToken(value) {
  value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey);
}

function showView(name) {
  Object.entries(views).forEach(([key, node]) => node.classList.toggle("hidden", key !== name));
  lockButton.classList.toggle("hidden", name !== "home");
  if (name !== "home") closeDateDrawer();
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 3200);
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
    currentProgress = progress;
    contentStatus = statusResult.dates || {};
    monthContentStatus = statusResult.months || {};
    yearContentStatus = statusResult.years || {};
    contentStatusRevision += 1;
    statusBadge.textContent = "加密仓库已解锁";
    document.getElementById("welcomeTitle").textContent = profile.display_name;
    document.getElementById("todayText").textContent = `${progress.today} · ${progress.timezone}`;
    document.getElementById("lifeSentence").textContent = `今天是人生的第 ${progress.life_day_number.toLocaleString()} 天。按 ${progress.target_age} 岁展示，你已经走过 ${progress.life.elapsed_days.toLocaleString()} 天。`;
    document.getElementById("lifePercent").textContent = `${progress.life.percent.toFixed(2)}%`;
    document.querySelector(".life-percent").style.setProperty("--progress", `${Math.min(100, progress.life.percent)}%`);
    const lifeDayMetric = document.getElementById("lifeDay");
    const yearPercentMetric = document.getElementById("yearPercent");
    const monthPercentMetric = document.getElementById("monthPercent");

    lifeDayMetric.textContent = progress.life_day_number.toLocaleString();
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
    requestAnimationFrame(() => renderLifeMapView(true));
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
  closeDateDrawer();
  statusBadge.textContent = "仓库已锁定";
  showView("unlock");
});

document.getElementById("refreshButton").addEventListener("click", loadHome);
document.getElementById("closeRecovery").addEventListener("click", async () => {
  document.getElementById("recoveryModal").classList.add("hidden");
  await loadHome();
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
    lifeMapViewTitle.textContent = "人生总览";
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
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    renderLifeMapView(true);
  }, 120);
});

const dateDrawer = document.getElementById("dateDrawer");
const dateDrawerBackdrop = document.getElementById("dateDrawerBackdrop");
const dateDrawerLoading = document.getElementById("dateDrawerLoading");
const dateDrawerContent = document.getElementById("dateDrawerContent");
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

const EMPTY_CONTENT_STATE = { has_event: false, has_memory: false, has_plan: false };

function setDrawerOpen(open) {
  dateDrawer.classList.toggle("hidden", !open);
  dateDrawerBackdrop.classList.toggle("hidden", !open);
  dateDrawer.setAttribute("aria-hidden", open ? "false" : "true");
  dateDrawerBackdrop.setAttribute("aria-hidden", open ? "false" : "true");
  document.body.classList.toggle("drawer-open", open);
}

function resetDrawerForms() {
  eventForm.reset();
  eventForm.classList.add("hidden");
  toggleEventFormButton.textContent = "＋ 添加事件";
  memoryForm.reset();
  memoryForm.classList.add("hidden");
  toggleMemoryFormButton.textContent = "＋ 添加记忆";
  planForm.reset();
  planForm.classList.add("hidden");
  togglePlanFormButton.disabled = false;
  togglePlanFormButton.textContent = "＋ 添加计划";
  planAvailability.classList.add("hidden");
}

function closeDateDrawer() {
  drawerRequestSequence += 1;
  selectedDate = null;
  selectedScope = null;
  selectedPeriodKey = null;
  setDrawerOpen(false);
  resetDrawerForms();
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
  } catch (error) {
    if (requestSequence !== drawerRequestSequence) return;
    closeDateDrawer();
    if (["SESSION_EXPIRED", "AUTH_REQUIRED", "VAULT_LOCKED"].includes(error.code)) {
      setToken(null);
      statusBadge.textContent = "仓库已锁定";
      showView("unlock");
    }
    showToast(error.message);
  }
}

function openDateDrawer(isoDate) {
  return openPeriodDrawer("day", isoDate);
}

function renderContentList(elementId, items, emptyText, cardClass = "") {
  const list = document.getElementById(elementId);
  list.replaceChildren();

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-copy";
    empty.textContent = emptyText;
    list.appendChild(empty);
    return;
  }

  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = `content-card ${cardClass}`.trim();

    const title = document.createElement("h4");
    title.textContent = item.title;
    article.appendChild(title);

    if (item.content) {
      const body = document.createElement("p");
      body.textContent = item.content;
      article.appendChild(body);
    }

    const meta = document.createElement("small");
    meta.textContent = `创建于 ${formatDateTime(item.created_at)}`;
    article.appendChild(meta);
    list.appendChild(article);
  });
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
  document.getElementById("eventSectionHeading").textContent = `${copy.noun}发生了什么`;
  document.getElementById("memorySectionHeading").textContent = `我如何记得${copy.noun}`;
  document.getElementById("planSectionHeading").textContent = `我准备在${copy.noun}做什么`;
  renderContentList("eventList", detail.events, `${copy.noun}还没有事件。`);
  renderContentList("memoryList", detail.memories, `${copy.noun}还没有个人记忆。`, "memory-card");
  renderContentList("planList", detail.plans, `${copy.noun}还没有未来计划。`, "plan-card");

  const planUnavailable = !detail.plan_allowed;
  togglePlanFormButton.disabled = planUnavailable;
  togglePlanFormButton.textContent = planUnavailable ? "该时间范围已过去" : "＋ 添加计划";
  planAvailability.textContent = detail.scope === "day"
    ? "过去日期不能新增未来计划，但此前保存的计划仍会显示。"
    : "已经结束的年份或月份不能新增未来计划，但此前保存的计划仍会显示。";
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

function toggleEventForm(forceOpen = null) {
  const shouldOpen = forceOpen === null ? eventForm.classList.contains("hidden") : forceOpen;
  eventForm.classList.toggle("hidden", !shouldOpen);
  toggleEventFormButton.textContent = shouldOpen ? "收起表单" : "＋ 添加事件";
  if (shouldOpen) {
    toggleMemoryForm(false);
    togglePlanForm(false);
    eventForm.querySelector('[name="title"]').focus();
  }
}

function toggleMemoryForm(forceOpen = null) {
  const shouldOpen = forceOpen === null ? memoryForm.classList.contains("hidden") : forceOpen;
  memoryForm.classList.toggle("hidden", !shouldOpen);
  toggleMemoryFormButton.textContent = shouldOpen ? "收起表单" : "＋ 添加记忆";
  if (shouldOpen) {
    toggleEventForm(false);
    togglePlanForm(false);
    memoryForm.querySelector('[name="title"]').focus();
  }
}

function togglePlanForm(forceOpen = null) {
  if (togglePlanFormButton.disabled) return;
  const shouldOpen = forceOpen === null ? planForm.classList.contains("hidden") : forceOpen;
  planForm.classList.toggle("hidden", !shouldOpen);
  togglePlanFormButton.textContent = shouldOpen ? "收起表单" : "＋ 添加计划";
  if (shouldOpen) {
    toggleEventForm(false);
    toggleMemoryForm(false);
    planForm.querySelector('[name="title"]').focus();
  }
}

toggleEventFormButton.addEventListener("click", () => toggleEventForm());
document.getElementById("cancelEventForm").addEventListener("click", () => {
  eventForm.reset();
  toggleEventForm(false);
});
toggleMemoryFormButton.addEventListener("click", () => toggleMemoryForm());
document.getElementById("cancelMemoryForm").addEventListener("click", () => {
  memoryForm.reset();
  toggleMemoryForm(false);
});
togglePlanFormButton.addEventListener("click", () => togglePlanForm());
document.getElementById("cancelPlanForm").addEventListener("click", () => {
  planForm.reset();
  togglePlanForm(false);
});
document.getElementById("closeDateDrawer").addEventListener("click", closeDateDrawer);
dateDrawerBackdrop.addEventListener("click", closeDateDrawer);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !dateDrawer.classList.contains("hidden")) closeDateDrawer();
});

async function submitScopedContent({ formNode, endpoint, successMessage }) {
  if (!selectedScope || !selectedPeriodKey) return;
  const form = new FormData(formNode);
  const submit = formNode.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api(endpoint, {
      method: "POST",
      body: JSON.stringify({
        time_scope: selectedScope,
        period_key: selectedPeriodKey,
        title: form.get("title"),
        content: form.get("content") || "",
      }),
    }, true);
    await refreshContentStatuses();
    renderLifeMapView(true);
    formNode.reset();
    toggleEventForm(false);
    toggleMemoryForm(false);
    togglePlanForm(false);
    showToast(successMessage);
    await openPeriodDrawer(selectedScope, selectedPeriodKey);
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
}

eventForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent({ formNode: eventForm, endpoint: "/api/v1/events", successMessage: "事件已加密保存" });
});

memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent({ formNode: memoryForm, endpoint: "/api/v1/memories", successMessage: "记忆已加密保存" });
});

planForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await submitScopedContent({ formNode: planForm, endpoint: "/api/v1/plans", successMessage: "未来计划已加密保存" });
});

bootstrap();
