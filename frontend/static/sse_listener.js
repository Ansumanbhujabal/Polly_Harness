/**
 * sse_listener.js — vanilla JS SSE client for the Refund Agent admin dashboard.
 *
 * Exports two public functions (attached to window):
 *   - subscribeToEvents(conversationId)  — streams LayerEvents for one conversation
 *   - subscribeToLayerPulses()           — streams all events for the Mermaid diagram
 *
 * Both functions push received events into the DOM so that Gradio picks them
 * up on the next event-loop tick via a hidden gr.State.
 */

(function () {
  "use strict";

  /** Active EventSource instances so we can close them on re-subscribe. */
  let _eventSource = null;
  let _pulseSource = null;

  /**
   * subscribeToEvents(conversationId)
   *
   * Opens an SSE connection to /events/stream?conversation_id=<id>.
   * Each received message is appended to #trace-container as a styled row.
   *
   * @param {string} conversationId
   */
  function subscribeToEvents(conversationId) {
    if (!conversationId) return;

    // Close any previous subscription for this tab
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }

    const url = "/events/stream?conversation_id=" + conversationId;
    _eventSource = new EventSource(url);

    _eventSource.onmessage = function (evt) {
      try {
        const data = JSON.parse(evt.data);
        _appendTraceRow(data);
        _maybeRevealApprovalBanner(data);
      } catch (e) {
        console.warn("[sse_listener] Failed to parse event data:", evt.data, e);
      }
    };

    _eventSource.onerror = function (err) {
      console.error("[sse_listener] SSE connection error:", err);
    };
  }

  /**
   * subscribeToLayerPulses()
   *
   * Opens a separate SSE connection to /events/stream (no conversation_id filter).
   * Pulses the Mermaid diagram node that corresponds to the event's layer.
   */
  function subscribeToLayerPulses() {
    if (_pulseSource) {
      _pulseSource.close();
      _pulseSource = null;
    }

    _pulseSource = new EventSource("/events/stream");

    _pulseSource.onmessage = function (evt) {
      try {
        const data = JSON.parse(evt.data);
        if (data.layer) {
          _pulseLayer(data.layer);
        }
      } catch (e) {
        console.warn("[sse_listener] pulse parse error:", e);
      }
    };

    _pulseSource.onerror = function (err) {
      console.error("[sse_listener] pulse SSE error:", err);
    };
  }

  // ---------------------------------------------------------------------------
  // Internal helpers
  // ---------------------------------------------------------------------------

  /**
   * Append one LayerEvent row to the #trace-container element.
   *
   * @param {{ layer: string, event_type: string, timestamp: string, payload: object }} data
   */
  function _appendTraceRow(data) {
    var container = document.getElementById("trace-container");
    if (!container) return;

    var row = document.createElement("div");
    row.className = "trace-row";

    var ts = document.createElement("span");
    ts.className = "trace-timestamp";
    ts.textContent = data.timestamp ? data.timestamp.substring(11, 23) : "";

    var chip = document.createElement("span");
    var layerCss = (data.layer || "").toLowerCase().replace(/_/g, "-");
    chip.className = "layer-chip layer-" + layerCss;
    chip.textContent = data.layer || "?";

    var eventType = document.createElement("span");
    eventType.className = "trace-event-type";
    eventType.textContent = data.event_type || "";

    var payload = document.createElement("details");
    var summary = document.createElement("summary");
    summary.textContent = "payload";
    var pre = document.createElement("pre");
    pre.style.fontSize = "0.7rem";
    pre.textContent = JSON.stringify(data.payload || {}, null, 2);
    payload.appendChild(summary);
    payload.appendChild(pre);

    row.appendChild(ts);
    row.appendChild(chip);
    row.appendChild(eventType);
    row.appendChild(payload);
    container.appendChild(row);

    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
  }

  /**
   * Pulse the Mermaid diagram node for the given layer by toggling the
   * `active-layer` CSS class on the matching <div> element.
   *
   * Mermaid renders nodes as `<div id="flowchart-<nodeId>-0">` — we rely on
   * the node id matching the LayerName value (set in mermaid_diagram.html).
   *
   * @param {string} layer  — e.g. "L1_INSTRUCTIONS"
   */
  function _pulseLayer(layer) {
    // Strip existing active-layer class from all nodes first
    var active = document.querySelectorAll(".active-layer");
    active.forEach(function (el) {
      el.classList.remove("active-layer");
    });

    // Find the node in the Mermaid SVG — node ids are lowercased by Mermaid
    var nodeId = "flowchart-" + layer.toLowerCase() + "-0";
    var node = document.getElementById(nodeId);
    if (node) {
      node.classList.add("active-layer");
      // Remove after animation completes (3 × 1.2s = 3.6s)
      setTimeout(function () {
        node.classList.remove("active-layer");
      }, 3600);
    }
  }

  /**
   * Show the approval banner if the event is an `interrupt_raised`.
   *
   * @param {{ event_type: string, payload: object }} data
   */
  function _maybeRevealApprovalBanner(data) {
    if (data.event_type !== "interrupt_raised") return;

    var banner = document.getElementById("approval-banner");
    if (!banner) return;

    var approvalId = (data.payload && data.payload.approval_id) ? data.payload.approval_id : "";
    banner.innerHTML =
      '<div class="approval-banner-visible">' +
      "Approval required for approval_id=" + approvalId + ". " +
      "Switch to the Admin tab &rarr; Pending Approvals." +
      "</div>";
    banner.style.display = "block";
  }

  // Expose to window
  window.subscribeToEvents = subscribeToEvents;
  window.subscribeToLayerPulses = subscribeToLayerPulses;
})();
