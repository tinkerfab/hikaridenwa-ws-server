(() => {
  const STORAGE_KEY = "hikaridenwa_call_history_v1";
  const MAX_HISTORY = 50;

  const listEl = document.getElementById("call-list");
  const statusEl = document.getElementById("connection-status");
  const template = document.getElementById("call-card-template");
  const cardsById = new Map();

  const STATUS_TEXT = {
    connecting: "接続中...",
    open: "接続中",
    closed: "切断されました。再接続します...",
  };

  // The server keeps no history at all — it only broadcasts live events —
  // so this array (persisted to localStorage) is this browser's own record
  // of recent calls. Most-recent-first, capped at MAX_HISTORY, matching the
  // ring-buffer behavior the original dashboard's server used to provide.
  let history = loadHistory();
  const historyById = new Map(history.filter((c) => c.id).map((c) => [c.id, c]));

  function loadHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function saveHistory() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
    } catch {
      // localStorage unavailable/full (private browsing, quota, ...) —
      // degrade to in-memory-only for the rest of this page session.
    }
  }

  function formatTime(epochSeconds) {
    if (!epochSeconds) return "";
    return new Date(epochSeconds * 1000).toLocaleString("ja-JP");
  }

  function statusLabel(status) {
    return status === "ended" ? "終了" : "着信中";
  }

  function removeEmptyState() {
    const emptyState = document.getElementById("empty-state");
    if (emptyState) emptyState.remove();
  }

  function renderEmptyState() {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.id = "empty-state";
    empty.innerHTML = `
      <span class="empty-state__icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.36 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>
        </svg>
      </span>
      <p class="empty-state__title">まだ着信はありません</p>
      <p class="empty-state__hint">電話がかかってくると、ここにリアルタイムで表示されます</p>
    `;
    listEl.appendChild(empty);
  }

  function renderCard(call, { prepend = false } = {}) {
    let card = cardsById.get(call.id);
    if (!card) {
      removeEmptyState();
      const fragment = template.content.cloneNode(true);
      card = fragment.querySelector(".call-card");
      cardsById.set(call.id, card);
      if (prepend && listEl.firstChild) {
        listEl.insertBefore(card, listEl.firstChild);
      } else {
        listEl.appendChild(card);
      }
    }

    const numberText = call.anonymous ? "非通知" : call.number || "不明";
    card.querySelector(".call-card__number").textContent = numberText;
    card.querySelector(".call-card__display-name").textContent = call.display_name || "";
    card.querySelector(".call-card__time").textContent = formatTime(call.received_at);

    const badge = card.querySelector(".call-card__badge");
    badge.textContent = statusLabel(call.status);
    badge.classList.toggle("call-card__badge--ended", call.status === "ended");
    card.classList.toggle("call-card--ringing", call.status !== "ended");

    return card;
  }

  function renderHistory() {
    listEl.innerHTML = "";
    cardsById.clear();
    if (history.length === 0) {
      renderEmptyState();
      return;
    }
    for (const call of history) {
      renderCard(call);
    }
  }

  function pruneHistory() {
    if (history.length <= MAX_HISTORY) return;
    for (const dropped of history.splice(MAX_HISTORY)) {
      if (dropped.id) historyById.delete(dropped.id);
    }
  }

  function handleRinging(call) {
    if (!call.id) return; // can't safely track this call without a stable id
    history.unshift(call);
    historyById.set(call.id, call);
    pruneHistory();
    saveHistory();
    renderCard(call, { prepend: true });
  }

  function handleEnded(payload) {
    // call:ended only carries {id, call_id, ended_at, end_reason} — no id
    // means the server itself couldn't correlate it either (e.g. it
    // restarted mid-call), so there's nothing reliable to update here.
    if (!payload.id) return;
    const existing = historyById.get(payload.id);
    if (!existing) return; // never saw ringing for this call in this session
    existing.status = "ended";
    existing.end_reason = payload.end_reason;
    existing.ended_at = payload.ended_at;
    saveHistory();
    renderCard(existing);
  }

  function setConnectionStatus(state) {
    statusEl.textContent = STATUS_TEXT[state];
    statusEl.className = `status status--${state}`;
  }

  function connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${location.host}/ws`);

    setConnectionStatus("connecting");

    ws.addEventListener("open", () => setConnectionStatus("open"));

    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "call:ringing") {
        handleRinging(message.call);
      } else if (message.type === "call:ended") {
        handleEnded(message.call);
      }
    });

    ws.addEventListener("close", () => {
      setConnectionStatus("closed");
      setTimeout(connect, 3000);
    });

    ws.addEventListener("error", () => ws.close());
  }

  renderHistory();
  connect();
})();
