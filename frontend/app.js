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
const frontendBuildVersion = "0.0.1.10";
console.info(`[LifeGraph] frontend build ${frontendBuildVersion}`);
const buildBadge = document.querySelector(".build-badge");
if (buildBadge) buildBadge.textContent = `v${frontendBuildVersion} · JS`;
let currentProgress = null;
let lifeGridSignature = "";
let resizeTimer = null;
let homeRenderTimer = null;

function token() { return sessionStorage.getItem(tokenKey); }
function setToken(value) { value ? sessionStorage.setItem(tokenKey, value) : sessionStorage.removeItem(tokenKey); }

function showView(name) {
  Object.entries(views).forEach(([key, node]) => node.classList.toggle("hidden", key !== name));
  lockButton.classList.toggle("hidden", name !== "home");
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.remove("hidden");
  setTimeout(() => toast.classList.add("hidden"), 3200);
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
    currentProgress = progress;
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
  try { await api("/api/v1/auth/lock", { method: "POST" }); } catch (_) {}
  setToken(null);
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
function daysBetween(a, b) { return Math.round((b - a) / 86400000); }
function addUtcDays(date, days) { return new Date(date.getTime() + days * 86400000); }
function formatUtc(date) { return date.toISOString().slice(0, 10); }

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
  ].join(":");

  if (!force && signature === lifeGridSignature) {
    return;
  }
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
      const x = left + day * cellWidth;
      const isToday = formatUtc(current) === progress.today;
      ctx.fillStyle = isToday ? todayColor : current < today ? past : future;
      ctx.fillRect(x, y, Math.max(.8, cellWidth - .35), cellHeight);
    }
    hitMap.push({ age, start, days, y, rowHeight });
  }
  canvas._lifeGrid = { left, top, cellWidth, rowHeight, hitMap, cssWidth, cssHeight };
}

const canvas = document.getElementById("lifeCanvas");
const tooltip = document.getElementById("canvasTooltip");
canvas.addEventListener("mousemove", (event) => {
  if (!canvas._lifeGrid || !currentProgress) return;

  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas._lifeGrid.cssWidth / rect.width;
  const scaleY = canvas._lifeGrid.cssHeight / rect.height;
  const canvasX = (event.clientX - rect.left) * scaleX;
  const canvasY = (event.clientY - rect.top) * scaleY;

  const { left, top, cellWidth, rowHeight, hitMap } = canvas._lifeGrid;
  const age = Math.floor((canvasY - top) / rowHeight);
  const day = Math.floor((canvasX - left) / cellWidth);

  if (age < 0 || age >= hitMap.length || day < 0 || day >= hitMap[age].days) {
    tooltip.textContent = "指向：—";
    tooltip.classList.remove("is-active");
    return;
  }

  const date = addUtcDays(hitMap[age].start, day);
  tooltip.textContent = `指向：${age} 岁 · ${formatUtc(date)}`;
  tooltip.classList.add("is-active");
});
canvas.addEventListener("mouseleave", () => {
  tooltip.textContent = "指向：—";
  tooltip.classList.remove("is-active");
});
window.addEventListener("resize", () => {
  if (!currentProgress) return;
  tooltip.textContent = "指向：—";
  tooltip.classList.remove("is-active");
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => drawLifeGrid(currentProgress), 120);
});

bootstrap();
