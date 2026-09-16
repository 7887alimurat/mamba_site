// ---------------------------------------------------------------- helpers

async function api(url, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Ошибка запроса: ${res.status}`);
  }
  return res.json();
}

let toastEl = null;
function showToast(message) {
  if (!toastEl) {
    toastEl = document.createElement("div");
    toastEl.className = "toast";
    document.body.appendChild(toastEl);
  }
  toastEl.textContent = message;
  toastEl.classList.add("is-visible");
  clearTimeout(toastEl._timer);
  toastEl._timer = setTimeout(() => toastEl.classList.remove("is-visible"), 2200);
}

function formatCountdown(deadlineIso) {
  const now = new Date();
  const deadline = new Date(deadlineIso);
  const diffMs = deadline - now;
  if (diffMs <= 0) return { label: "просрочено", urgent: true };

  const mins = Math.floor(diffMs / 60000);
  const hours = Math.floor(mins / 60);
  const days = Math.floor(hours / 24);

  let label;
  if (days >= 1) {
    label = `через ${days} д ${hours % 24} ч`;
  } else if (hours >= 1) {
    label = `через ${hours} ч ${mins % 60} мин`;
  } else {
    label = `через ${mins} мин`;
  }
  return { label, urgent: hours < 24 };
}

async function uploadHomeMedia(file, settingsKey) {
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  showToast("Загружаю...");
  const res = await fetch("/api/upload", { method: "POST", body: form });
  const data = await res.json();
  if (data.error) return showToast(data.error);
  await api("/api/settings", "POST", { [settingsKey]: data.path });
  location.reload();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-countdown]").forEach((el) => {
    const iso = el.getAttribute("data-countdown");
    const { label, urgent } = formatCountdown(iso);
    el.textContent = label;
    if (urgent) el.classList.add("is-urgent");
  });
});
