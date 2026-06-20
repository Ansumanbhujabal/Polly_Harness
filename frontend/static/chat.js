/* Refund Harness — custom inline chat with CRM sidebar.

   - Scenario click → fetch /api/v1/crm/context, render the left ticket panel,
     start a fresh conversation, prefill the message.
   - User submits → POST /api/v1/chat with the active customer/order +
     conversation_id; render reply with DECISION chip.
   - If a turn ends in awaiting_human_approval, the next free-form turn starts
     a new conversation_id (so follow-up questions like "how much can you
     approve?" don't get re-routed through the same await_approval interrupt).
   - "↻ new thread" button resets conversation_id manually.
*/

(function () {
  "use strict";

  // --- DOM ---
  const messagesEl = document.getElementById("rh-chat-messages");
  const placeholderEl = messagesEl ? messagesEl.querySelector(".rh-chat__placeholder") : null;
  const formEl = document.getElementById("rh-chat-form");
  const inputEl = document.getElementById("rh-chat-input");
  const sendBtn = document.getElementById("rh-chat-send");
  const scenariosEl = document.getElementById("rh-chat-scenarios");
  const resetBtn = document.getElementById("rh-chat-reset");

  const ticketPlaceholder = document.getElementById("rh-ticket-placeholder");
  const ticketBody = document.getElementById("rh-ticket-body");
  const tCustId = document.getElementById("rh-ticket-cust-id");
  const tCustName = document.getElementById("rh-ticket-cust-name");
  const tCustMeta = document.getElementById("rh-ticket-cust-meta");
  const tCustFlags = document.getElementById("rh-ticket-cust-flags");
  const tOrderId = document.getElementById("rh-ticket-order-id");
  const tOrderItem = document.getElementById("rh-ticket-order-item");
  const tOrderMeta = document.getElementById("rh-ticket-order-meta");
  const tExpect = document.getElementById("rh-ticket-expect");
  const tConvId = document.getElementById("rh-ticket-convid");

  if (!messagesEl || !formEl || !inputEl) return;

  // --- State ---
  let conversationId = null;
  let activeCustomer = null;
  let activeOrder = null;
  let lastTurnCompleted = false; // true after a turn ends with a final decision
  let inFlight = false;

  // --- helpers ---
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function clearPlaceholder() {
    if (placeholderEl && placeholderEl.parentNode) {
      placeholderEl.parentNode.removeChild(placeholderEl);
    }
  }

  function scrollToBottom() {
    requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
  }

  // --- Ticket sidebar ---
  function fmtDollar(n) {
    if (n === null || n === undefined || isNaN(n)) return "—";
    return "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtDate(s) {
    if (!s) return "—";
    return String(s).slice(0, 10);
  }

  function renderTicket(customer, order, expectText) {
    if (!ticketBody) return;
    ticketPlaceholder.hidden = true;
    ticketBody.hidden = false;

    if (customer) {
      tCustId.textContent = customer.customer_id || "—";
      tCustName.textContent = customer.name || "—";
      const metaParts = [];
      if (customer.tier) metaParts.push((customer.tier + "").toUpperCase() + " tier");
      if (customer.account_age_days !== undefined) metaParts.push(customer.account_age_days + " days old");
      if (customer.lifetime_value_usd !== undefined) metaParts.push(fmtDollar(customer.lifetime_value_usd) + " LTV");
      if (customer.prior_refunds_last_90d !== undefined) metaParts.push(customer.prior_refunds_last_90d + " refunds (90d)");
      tCustMeta.textContent = metaParts.join(" · ");

      const flagBits = [];
      if (customer.flagged_for_abuse) flagBits.push('<span class="flag flag--terra">⚠ abuse flag</span>');
      if (customer.active_chargeback) flagBits.push('<span class="flag flag--terra">⚠ active chargeback</span>');
      if (!customer.flagged_for_abuse && !customer.active_chargeback) flagBits.push('<span class="flag flag--ok">✓ clean record</span>');
      tCustFlags.innerHTML = flagBits.join(" ");
    }

    if (order) {
      tOrderId.textContent = order.order_id || "—";
      const items = order.items || [];
      tOrderItem.textContent = items.length ? items.map(i => `${i.name || i.sku} × ${i.qty || 1}`).join(", ") : "—";
      const orderMetaParts = [];
      orderMetaParts.push(fmtDollar(order.total_usd));
      if (order.purchase_date) orderMetaParts.push("purchased " + fmtDate(order.purchase_date));
      if (order.delivery_date) orderMetaParts.push("delivered " + fmtDate(order.delivery_date));
      if (order.item_condition_reported) orderMetaParts.push("condition: " + order.item_condition_reported.replace(/_/g, " "));
      tOrderMeta.innerHTML = orderMetaParts.map(p => escapeHtml(p)).join(" · ");
    } else {
      tOrderId.textContent = "—";
      tOrderItem.textContent = "—";
      tOrderMeta.textContent = "";
    }

    tExpect.textContent = expectText || "—";
    tConvId.textContent = conversationId ? "thread · " + conversationId.slice(0, 18) : "thread · (none yet)";
  }

  function clearTicket() {
    if (!ticketBody) return;
    ticketBody.hidden = true;
    ticketPlaceholder.hidden = false;
  }

  function updateConvIdDisplay() {
    if (tConvId) tConvId.textContent = conversationId ? "thread · " + conversationId.slice(0, 18) : "thread · (none yet)";
  }

  // --- Chat messages ---
  function decisionChip(decision) {
    if (!decision || !decision.kind) return "";
    const colorMap = {
      approve_full: "#2E5C3A",
      approve_partial: "#B07A1C",
      deny: "#B83A2C",
      escalate: "#1F4F7A",
    };
    const color = colorMap[decision.kind] || "#54616C";
    const amount = (decision.amount_usd || 0).toFixed(2);
    const cited = (decision.cited_clause_ids || []).slice(0, 3).join(", ") || "—";
    return (
      `<div class="rh-chat__chip-decision" style="border-color:${color}; color:${color};">` +
      `DECISION · ${decision.kind.toUpperCase()} · $${amount} · clauses: ${cited}` +
      `</div>`
    );
  }

  function appendUser(text) {
    clearPlaceholder();
    const row = document.createElement("div");
    row.className = "rh-chat__row rh-chat__row--user";
    row.innerHTML = `<div class="rh-chat__bubble rh-chat__bubble--user">${escapeHtml(text)}</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function appendTyping() {
    clearPlaceholder();
    const row = document.createElement("div");
    row.className = "rh-chat__row rh-chat__row--bot";
    row.dataset.typing = "1";
    row.innerHTML =
      `<div class="rh-chat__bubble rh-chat__bubble--bot">` +
      `<span class="rh-chat__typing"><span></span><span></span><span></span>` +
      `<em>&nbsp;Polly is thinking — running through 9 layers…</em></span>` +
      `</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendBot(text, decision, awaiting) {
    const row = document.createElement("div");
    row.className = "rh-chat__row rh-chat__row--bot";
    let extraNotice = "";
    if (awaiting) {
      extraNotice =
        `<div class="rh-chat__hint">` +
        `Approval routed to a human. Type a follow-up question (e.g. "how much can you approve?") ` +
        `and I'll handle it in a fresh thread.` +
        `</div>`;
    }
    row.innerHTML =
      `<div class="rh-chat__bubble rh-chat__bubble--bot">` +
      `<div class="rh-chat__bubble-text">${escapeHtml(text)}</div>` +
      decisionChip(decision) +
      `</div>` +
      extraNotice;
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  function appendError(detail) {
    const row = document.createElement("div");
    row.className = "rh-chat__row rh-chat__row--bot";
    row.innerHTML =
      `<div class="rh-chat__bubble rh-chat__bubble--bot rh-chat__bubble--error">` +
      `Agent error: ${escapeHtml(detail)}` +
      `</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
  }

  // --- Submit handler ---
  async function send(message, opts) {
    if (!message || inFlight) return;
    const isScenarioClick = !!(opts && opts.fromScenario);

    // After ANY completed turn (deny / approve / escalate, with or without
    // awaiting_human_approval), the next free-form message is a NEW question
    // — start a fresh thread. Otherwise LangGraph's checkpointer carries
    // forward the previous turn's classification and final_decision, and
    // the agent echoes the same canned reply.
    if (!isScenarioClick && lastTurnCompleted) {
      conversationId = null;
      lastTurnCompleted = false;
      updateConvIdDisplay();
    }

    inFlight = true;
    sendBtn.disabled = true;
    inputEl.disabled = true;

    appendUser(message);
    inputEl.value = "";
    const typingRow = appendTyping();

    const payload = { message };
    if (conversationId) payload.conversation_id = conversationId;
    if (activeCustomer) payload.customer_id = activeCustomer;
    if (activeOrder) payload.order_id = activeOrder;

    try {
      const resp = await fetch("/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (typingRow && typingRow.parentNode) typingRow.parentNode.removeChild(typingRow);
      if (!resp.ok) {
        let detail = `HTTP ${resp.status}`;
        try {
          const ej = await resp.json();
          detail = ej.detail || detail;
        } catch (_) {}
        appendError(detail);
      } else {
        const data = await resp.json();
        conversationId = data.conversation_id || conversationId;
        const summary = data.final_state_summary || {};
        // A "completed" turn = anything that produced a final_decision or set
        // awaiting_human_approval. The next free-form message gets a new thread.
        lastTurnCompleted = !!(summary.final_decision || summary.awaiting_human_approval);
        const replyText = summary.response_text || "(no response)";
        appendBot(replyText, summary.final_decision, !!summary.awaiting_human_approval);
        updateConvIdDisplay();
      }
    } catch (err) {
      if (typingRow && typingRow.parentNode) typingRow.parentNode.removeChild(typingRow);
      appendError(err && err.message ? err.message : String(err));
    } finally {
      inFlight = false;
      sendBtn.disabled = false;
      inputEl.disabled = false;
      inputEl.focus();
    }
  }

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    const text = inputEl.value.trim();
    if (!text) return;
    send(text);
  });

  // --- Scenario click ---
  async function loadScenario(btn) {
    activeCustomer = btn.dataset.customer || null;
    activeOrder = btn.dataset.order || null;
    const msg = btn.dataset.msg || "";
    const expect = btn.dataset.expect || "";

    // Fresh conversation for the new scenario
    conversationId = null;
    lastTurnCompleted = false;

    // Highlight active chip
    scenariosEl
      .querySelectorAll(".rh-chat__chip--active")
      .forEach((b) => b.classList.remove("rh-chat__chip--active"));
    btn.classList.add("rh-chat__chip--active");

    // Render ticket panel — fetch live CRM data
    try {
      const url =
        "/api/v1/crm/context?customer_id=" + encodeURIComponent(activeCustomer) +
        (activeOrder ? "&order_id=" + encodeURIComponent(activeOrder) : "");
      const r = await fetch(url);
      if (r.ok) {
        const data = await r.json();
        renderTicket(data.customer, data.order, expect);
      } else {
        renderTicket({ customer_id: activeCustomer }, { order_id: activeOrder }, expect);
      }
    } catch (_) {
      renderTicket({ customer_id: activeCustomer }, { order_id: activeOrder }, expect);
    }

    // Prefill input but don't auto-send
    inputEl.value = msg;
    inputEl.focus();
  }

  if (scenariosEl) {
    scenariosEl.addEventListener("click", function (e) {
      const btn = e.target.closest(".rh-chat__chip");
      if (!btn) return;
      loadScenario(btn);
    });
  }

  // --- Free customer/order picker ---
  const custSelect = document.getElementById("rh-chat-cust-select");
  const orderSelect = document.getElementById("rh-chat-order-select");
  let allCustomers = [];
  let allOrders = [];
  try {
    allCustomers = JSON.parse(document.getElementById("rh-crm-customers").textContent || "[]");
    allOrders = JSON.parse(document.getElementById("rh-crm-orders").textContent || "[]");
  } catch (_) { /* leave empty */ }

  function populateOrdersForCustomer(custId) {
    if (!orderSelect) return;
    orderSelect.innerHTML = "";
    const matches = allOrders.filter((o) => o.customer_id === custId);
    if (!custId || matches.length === 0) {
      orderSelect.disabled = true;
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = custId ? "(no orders on file)" : "— choose a customer first —";
      orderSelect.appendChild(opt);
      return;
    }
    orderSelect.disabled = false;
    const ph = document.createElement("option");
    ph.value = "";
    ph.textContent = `— choose one of ${matches.length} order${matches.length === 1 ? "" : "s"} —`;
    orderSelect.appendChild(ph);
    for (const o of matches) {
      const opt = document.createElement("option");
      opt.value = o.id;
      const totalStr = (typeof o.total_usd === "number") ? `$${o.total_usd.toFixed(2)}` : "—";
      opt.textContent = `${o.id} · ${o.items_summary} · ${totalStr}`;
      orderSelect.appendChild(opt);
    }
  }

  async function loadPickerContext() {
    const custId = custSelect ? custSelect.value : "";
    const orderId = orderSelect ? orderSelect.value : "";
    if (!custId) {
      activeCustomer = null;
      activeOrder = null;
      clearTicket();
      conversationId = null;
      lastTurnCompleted = false;
      updateConvIdDisplay();
      return;
    }
    activeCustomer = custId;
    activeOrder = orderId || null;
    conversationId = null;
    lastTurnCompleted = false;
    // Clear active scenario highlight — they're using the free picker now
    if (scenariosEl) {
      scenariosEl
        .querySelectorAll(".rh-chat__chip--active")
        .forEach((b) => b.classList.remove("rh-chat__chip--active"));
    }
    try {
      const url =
        "/api/v1/crm/context?customer_id=" + encodeURIComponent(activeCustomer) +
        (activeOrder ? "&order_id=" + encodeURIComponent(activeOrder) : "");
      const r = await fetch(url);
      if (r.ok) {
        const data = await r.json();
        const expect = activeOrder
          ? `Free chat as ${data.customer && data.customer.name || activeCustomer} regarding ${activeOrder}.`
          : `Free chat as ${data.customer && data.customer.name || activeCustomer}. No order context loaded — Polly will ask for an order ID.`;
        renderTicket(data.customer, data.order, expect);
      } else {
        renderTicket({ customer_id: activeCustomer }, activeOrder ? { order_id: activeOrder } : null, "Free chat — CRM context partial.");
      }
    } catch (_) {
      renderTicket({ customer_id: activeCustomer }, activeOrder ? { order_id: activeOrder } : null, "Free chat — CRM context partial.");
    }
    inputEl.focus();
  }

  if (custSelect) {
    custSelect.addEventListener("change", function () {
      populateOrdersForCustomer(custSelect.value);
      loadPickerContext();
    });
  }
  if (orderSelect) {
    orderSelect.addEventListener("change", loadPickerContext);
  }

  // --- Reset thread ---
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      conversationId = null;
      lastTurnCompleted = false;
      updateConvIdDisplay();
      // Clear the visible conversation but keep the active scenario context
      while (messagesEl.firstChild) messagesEl.removeChild(messagesEl.firstChild);
      const p = document.createElement("div");
      p.className = "rh-chat__placeholder";
      p.innerHTML =
        "Fresh thread started. Active customer/order context is still loaded on the left.<br>" +
        "Type a message or pick a different scenario.";
      messagesEl.appendChild(p);
    });
  }
})();
