const SCHEMA = "integrated-video-downloader.task.v1";
const SKILL_DIR_WINDOWS = "agent-skill\\integrated-video-downloader";
const SKILL_DIR_POSIX = "agent-skill/integrated-video-downloader";

const elements = {
  form: document.querySelector("#taskForm"),
  input: document.querySelector("#videoInput"),
  inputError: document.querySelector("#inputError"),
  platformBadge: document.querySelector("#platformBadge"),
  pageGroup: document.querySelector("#pageGroup"),
  allPages: document.querySelector("#allPages"),
  pageNumber: document.querySelector("#pageNumber"),
  outputDir: document.querySelector("#outputDir"),
  timeout: document.querySelector("#timeout"),
  timeoutValue: document.querySelector("#timeoutValue"),
  taskJson: document.querySelector("#taskJson"),
  commandText: document.querySelector("#commandText"),
  validationState: document.querySelector("#validationState"),
  resultInput: document.querySelector("#resultInput"),
  resultSummary: document.querySelector("#resultSummary"),
  signalPlatform: document.querySelector("#signalPlatform"),
  signalAction: document.querySelector("#signalAction"),
  canvas: document.querySelector("#signalCanvas"),
  toast: document.querySelector("#toast")
};

let selectedShell = "windows";
let toastTimer;

function detectPlatform(value) {
  const input = value.trim();
  if (!input) return "auto";
  if (/^(BV[0-9A-Za-z]{10}|av\d+|\d+)$/i.test(input)) return "bilibili";
  try {
    const host = new URL(input).hostname.toLowerCase();
    if (host === "b23.tv" || host === "bilibili.com" || host.endsWith(".bilibili.com")) return "bilibili";
    if (host === "weibo.com" || host === "weibo.cn" || host.endsWith(".weibo.com") || host.endsWith(".weibo.cn")) return "weibo";
  } catch (_) {
    return "unknown";
  }
  return "unknown";
}

function currentAction() {
  return new FormData(elements.form).get("action") || "resolve";
}

function buildTask() {
  const input = elements.input.value.trim();
  const platform = detectPlatform(input);
  const task = {
    schema: SCHEMA,
    input,
    platform: platform === "unknown" ? "auto" : platform,
    action: currentAction(),
    outputDir: elements.outputDir.value.trim() || "videos",
    timeout: Number(elements.timeout.value)
  };
  if (platform === "bilibili") {
    if (elements.allPages.checked) task.allPages = true;
    else if (elements.pageNumber.value) task.page = Math.max(1, Number(elements.pageNumber.value));
  }
  return task;
}

function quote(value, shell) {
  if (shell === "windows") return `"${String(value).replaceAll('"', '`"')}"`;
  return `'${String(value).replaceAll("'", "'\\''")}'`;
}

function buildCommand(task, shell) {
  const python = shell === "windows" ? "py -3 -S" : "python3 -S";
  const skillDir = shell === "windows" ? SKILL_DIR_WINDOWS : SKILL_DIR_POSIX;
  const separator = shell === "windows" ? "\\" : "/";
  const args = [quote(`${skillDir}${separator}scripts${separator}video_downloader.py`, shell), quote(task.input || "<链接或编号>", shell)];
  if (task.action === "resolve") args.push("--resolve-only");
  if (task.action === "download") args.push("--output-dir", quote(task.outputDir, shell));
  if (task.platform === "bilibili" && task.allPages) args.push("--all-pages");
  if (task.platform === "bilibili" && task.page) args.push("--page", String(task.page));
  args.push("--timeout", String(task.timeout));
  return `${python} ${args.join(" ")}`;
}

function validate(task) {
  if (!task.input) return {ok: false, message: "填写视频链接或编号"};
  if (detectPlatform(task.input) === "unknown") return {ok: false, message: "当前仅支持微博与 Bilibili"};
  return {ok: true, message: `${task.platform === "weibo" ? "微博" : "Bilibili"}任务已就绪`};
}

function updateBadge(platform) {
  const labels = {auto: "待识别", unknown: "不支持", weibo: "微博", bilibili: "Bilibili"};
  elements.platformBadge.textContent = labels[platform];
  elements.platformBadge.className = `platform-badge ${platform === "unknown" ? "neutral" : platform}`;
  elements.pageGroup.disabled = platform !== "bilibili";
}

function drawSignal(task) {
  const canvas = elements.canvas;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const seed = [...(task.input || "video")].reduce((total, char) => total + char.charCodeAt(0), 0);
  const accent = task.platform === "weibo" ? "#d9485f" : task.platform === "bilibili" ? "#2878b8" : "#f3c64e";
  ctx.fillStyle = "#182027";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#26323a";
  for (let x = -20; x < width; x += 80) {
    ctx.fillRect(x, 20, 54, 34);
    ctx.fillRect(x + 24, height - 60, 54, 34);
  }
  ctx.strokeStyle = accent;
  ctx.lineWidth = 4;
  ctx.beginPath();
  for (let x = 0; x <= width; x += 12) {
    const y = height / 2 + Math.sin((x + seed) / 34) * 28 + Math.sin((x + seed) / 11) * 8;
    if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.fillStyle = accent;
  ctx.fillRect(0, height - 5, Math.max(70, (seed % width)), 5);
}

function render() {
  const task = buildTask();
  const platform = detectPlatform(task.input);
  const state = validate(task);
  updateBadge(platform);
  elements.inputError.textContent = task.input && !state.ok ? state.message : "";
  elements.timeoutValue.textContent = `${task.timeout} 秒`;
  elements.taskJson.textContent = JSON.stringify(task, null, 2);
  elements.commandText.textContent = buildCommand(task, selectedShell);
  elements.validationState.textContent = state.message;
  elements.signalPlatform.textContent = platform === "weibo" ? "WEIBO" : platform === "bilibili" ? "BILIBILI" : "VIDEO TASK";
  elements.signalAction.textContent = task.action === "resolve" ? "解析媒体信息" : "下载最高可用画质";
  drawSignal(task);
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elements.toast.classList.remove("visible"), 1800);
}

async function copyText(text, message) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
  } else {
    const input = document.createElement("textarea");
    input.value = text;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
  showToast(message);
}

function requireValidTask() {
  const task = buildTask();
  const state = validate(task);
  if (!state.ok) {
    elements.input.focus();
    elements.inputError.textContent = state.message;
    showToast(state.message);
    return null;
  }
  return task;
}

function downloadTask() {
  const task = requireValidTask();
  if (!task) return;
  const blob = new Blob([JSON.stringify(task, null, 2)], {type: "application/json"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `video-task-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  showToast("任务文件已下载");
}

function renderResult() {
  const value = elements.resultInput.value.trim();
  if (!value) {
    elements.resultSummary.className = "result-summary empty";
    elements.resultSummary.textContent = "尚无执行结果";
    return;
  }
  try {
    const data = JSON.parse(value);
    if (!data.ok) throw new Error(data.error || "任务执行失败");
    const downloads = Array.isArray(data.downloads) ? data.downloads : [];
    if (downloads.length) {
      const bytes = downloads.reduce((sum, item) => sum + Number(item.bytes || 0), 0);
      elements.resultSummary.className = "result-summary";
      elements.resultSummary.textContent = `已完成 ${downloads.length} 个文件 · ${(bytes / 1024 / 1024).toFixed(2)} MB · ${downloads.map(item => item.quality || item.quality_name || "可用画质").join(" / ")}`;
    } else {
      const pages = Array.isArray(data.pages) ? data.pages.length : 0;
      elements.resultSummary.className = "result-summary";
      elements.resultSummary.textContent = `解析成功 · ${pages || 1} 个视频条目`;
    }
  } catch (error) {
    elements.resultSummary.className = "result-summary error";
    elements.resultSummary.textContent = error.message;
  }
}

document.querySelectorAll("[role=tab]").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("[role=tab]").forEach(item => item.setAttribute("aria-selected", String(item === tab)));
    document.querySelectorAll(".tab-panel").forEach(panel => { panel.hidden = panel.id !== tab.getAttribute("aria-controls"); });
  });
});

document.querySelectorAll("[data-shell]").forEach(button => {
  button.addEventListener("click", () => {
    selectedShell = button.dataset.shell;
    document.querySelectorAll("[data-shell]").forEach(item => item.classList.toggle("active", item === button));
    render();
  });
});

elements.form.addEventListener("input", render);
elements.allPages.addEventListener("change", () => { elements.pageNumber.disabled = elements.allPages.checked; render(); });
elements.resultInput.addEventListener("input", renderResult);
document.querySelector("#copyTaskButton").addEventListener("click", () => { const task = requireValidTask(); if (task) copyText(JSON.stringify(task, null, 2), "Agent 任务已复制"); });
document.querySelector("#downloadTaskButton").addEventListener("click", downloadTask);
document.querySelector("#copyJsonButton").addEventListener("click", () => copyText(elements.taskJson.textContent, "JSON 已复制"));
document.querySelector("#copyCommandButton").addEventListener("click", () => copyText(elements.commandText.textContent, "命令已复制"));
document.querySelector("#resetButton").addEventListener("click", () => {
  elements.form.reset();
  elements.outputDir.value = "videos";
  elements.resultInput.value = "";
  renderResult();
  render();
});

render();
