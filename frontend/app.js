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
const frontendBuildVersion = "0.0.2.4";
console.info(`[LifeGraph] frontend build ${frontendBuildVersion}`);
const buildBadge = document.querySelector(".build-badge");
if (buildBadge) buildBadge.textContent = `v${frontendBuildVersion} · JS`;

let currentProfile = null;
let currentProgress = null;
let contentStatus = {};
let contentStatusRevision = 0;
let lifeGridSignature = "";
let resizeTimer = null;
let selectedDate = null;
let drawerRequestSequence = 0;

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
    contentStatusRevision += 1;
    statusBadge.textContent = "加密仓库已解锁";
    document.getElementById("welcomeTitle").textContent = profile.display_name;
    document.getElementById("todayText").textContent = `${progress.today} · ${progress.timezone}`;
    document.getElementById("lifeSentence").textContent = `今天是人生的第 ${progress.life_day_number.toLocaleString()} 天。按 ${progress.target_age} 岁展示，你已经走过 ${progress.life.elapsed_days.toLocaleString()} 天。`;
    document.getElementById("lifePercent").textContent = `${progress.life.percent.toFixed(2)}%`;
    document.querySelector(".life-percent").style.setProperty("--progress", `${Math.min(100, progress.life.percent)}%`);
    document.getElementById("lifeDay").textContent = progress.life_day_number.toLocaleString();
    document.getElementById("yearPercent").textContent = `${progress.year.percent.toFixed(1)}%`;
    document.getElementById("yearRemaining").textContent = `还剩 ${progress.year.remaining_text || `${progress.year.remaining_days} 天`}`;
    document.getElementById("monthPercent").textContent = `${progress.month.percent.toFixed(1)}%`;
    document.getElementById("monthRemaining").textContent = `还剩 ${progress.month.remaining_text || `${progress.month.remaining_days} 天`}`;
    showView("home");
    requestAnimationFrame(() => drawLifeGrid(progress, true));
  } catch (error) {
    if (["SESSION_EXPIRED", "AUTH_REQUIRED", "VAULT_LOCKED"].includes(error.code)) {
      setToken(null);
      statusBadge.textContent = "仓库已锁定";
      showView("unlock");
    }
    showToast(error.message);
  }
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

function drawLifeGrid(progress, force = false) {
  const canvas = document.getElementById("lifeCanvas");
  const wrap = canvas.parentElement;
  const cssWidth = Math.max(780, Math.round(wrap.clientWidth || 780));
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
const tooltip = document.getElementById("canvasTooltip");
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
    tooltip.textContent = "指向：—";
    tooltip.classList.remove("is-active");
    hideGridMagnifier();
    return;
  }
  tooltip.textContent = `指向：${resolved.age} 岁 · ${resolved.isoDate}`;
  tooltip.classList.add("is-active");
  showGridMagnifier(event, resolved);
});
canvas.addEventListener("mouseleave", () => {
  tooltip.textContent = "指向：—";
  tooltip.classList.remove("is-active");
  hideGridMagnifier();
});
canvas.addEventListener("click", (event) => {
  const resolved = resolveLifeDateFromPointer(event);
  if (resolved) {
    hideGridMagnifier();
    openDateDrawer(resolved.isoDate);
  }
});
canvasWrap.addEventListener("scroll", hideGridMagnifier, { passive: true });
window.addEventListener("resize", () => {
  if (!currentProgress) return;
  tooltip.textContent = "指向：—";
  tooltip.classList.remove("is-active");
  hideGridMagnifier();
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => drawLifeGrid(currentProgress), 120);
});

const dateDrawer = document.getElementById("dateDrawer");
const dateDrawerBackdrop = document.getElementById("dateDrawerBackdrop");
const dateDrawerLoading = document.getElementById("dateDrawerLoading");
const dateDrawerContent = document.getElementById("dateDrawerContent");
const eventForm = document.getElementById("eventForm");
const toggleEventFormButton = document.getElementById("toggleEventForm");
const memoryForm = document.getElementById("memoryForm");
const toggleMemoryFormButton = document.getElementById("toggleMemoryForm");
const planForm = document.getElementById("planForm");
const togglePlanFormButton = document.getElementById("togglePlanForm");
const planAvailability = document.getElementById("planAvailability");

function setDrawerOpen(open) {
  dateDrawer.classList.toggle("hidden", !open);
  dateDrawerBackdrop.classList.toggle("hidden", !open);
  dateDrawer.setAttribute("aria-hidden", open ? "false" : "true");
  dateDrawerBackdrop.setAttribute("aria-hidden", open ? "false" : "true");
  document.body.classList.toggle("drawer-open", open);
}

function closeDateDrawer() {
  drawerRequestSequence += 1;
  selectedDate = null;
  setDrawerOpen(false);
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

async function openDateDrawer(isoDate) {
  selectedDate = isoDate;
  const requestSequence = ++drawerRequestSequence;
  setDrawerOpen(true);
  dateDrawerLoading.classList.remove("hidden");
  dateDrawerContent.classList.add("hidden");
  document.getElementById("dateDrawerTitle").textContent = isoDate;
  document.getElementById("dateDrawerMeta").textContent = "正在读取……";
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

  try {
    const detail = await api(`/api/v1/dates/${encodeURIComponent(isoDate)}`, {}, true);
    if (requestSequence !== drawerRequestSequence || selectedDate !== isoDate) return;
    renderDateDetail(detail);
    dateDrawerLoading.classList.add("hidden");
    dateDrawerContent.classList.remove("hidden");
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

function renderDateDetail(detail) {
  document.getElementById("dateDrawerEyebrow").textContent = `${detail.time_state_label} · 日期详情`;
  document.getElementById("dateDrawerTitle").textContent = `${detail.date} · ${detail.weekday}`;
  document.getElementById("dateDrawerMeta").textContent = `${detail.age} 岁 · 人生第 ${detail.life_day_number.toLocaleString()} 天 · ${detail.timezone}`;

  renderContentList("eventList", detail.events, "这一天还没有事件。");
  renderContentList("memoryList", detail.memories, "这一天还没有个人记忆。", "memory-card");
  renderContentList("planList", detail.plans, "这一天还没有未来计划。", "plan-card");

  const isPastDate = detail.time_state === "past";
  togglePlanFormButton.disabled = isPastDate;
  togglePlanFormButton.textContent = isPastDate ? "过去日期不可添加" : "＋ 添加计划";
  planAvailability.classList.toggle("hidden", !isPastDate);
  if (isPastDate) {
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

eventForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedDate) return;
  const form = new FormData(eventForm);
  const submit = eventForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api("/api/v1/events", {
      method: "POST",
      body: JSON.stringify({
        event_date: selectedDate,
        title: form.get("title"),
        content: form.get("content") || "",
      }),
    }, true);

    const existing = contentStatus[selectedDate] || {
      has_event: false,
      has_memory: false,
      has_plan: false,
    };
    contentStatus[selectedDate] = { ...existing, has_event: true };
    contentStatusRevision += 1;
    lifeGridSignature = "";
    drawLifeGrid(currentProgress, true);
    eventForm.reset();
    toggleEventForm(false);
    showToast("事件已加密保存");
    await openDateDrawer(selectedDate);
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

memoryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedDate) return;
  const form = new FormData(memoryForm);
  const submit = memoryForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api("/api/v1/memories", {
      method: "POST",
      body: JSON.stringify({
        memory_date: selectedDate,
        title: form.get("title"),
        content: form.get("content") || "",
      }),
    }, true);

    const existing = contentStatus[selectedDate] || {
      has_event: false,
      has_memory: false,
      has_plan: false,
    };
    contentStatus[selectedDate] = { ...existing, has_memory: true };
    contentStatusRevision += 1;
    lifeGridSignature = "";
    drawLifeGrid(currentProgress, true);
    memoryForm.reset();
    toggleMemoryForm(false);
    showToast("记忆已加密保存");
    await openDateDrawer(selectedDate);
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

planForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedDate) return;
  const form = new FormData(planForm);
  const submit = planForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  try {
    await api("/api/v1/plans", {
      method: "POST",
      body: JSON.stringify({
        plan_date: selectedDate,
        title: form.get("title"),
        content: form.get("content") || "",
      }),
    }, true);

    const existing = contentStatus[selectedDate] || {
      has_event: false,
      has_memory: false,
      has_plan: false,
    };
    contentStatus[selectedDate] = { ...existing, has_plan: true };
    contentStatusRevision += 1;
    lifeGridSignature = "";
    drawLifeGrid(currentProgress, true);
    planForm.reset();
    togglePlanForm(false);
    showToast("未来计划已加密保存");
    await openDateDrawer(selectedDate);
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});


bootstrap();
