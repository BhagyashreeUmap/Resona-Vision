/*
 * claim_flow.js - Resona chat-guided damage claim (the photo is uploaded inside the chat).
 *
 * How it works in one paragraph:
 *   Every message goes through handleClaimFlow() first. If the customer is asking for a refund or
 *   reporting damage, this file runs a small conversation (order number -> item -> photo) and calls
 *   the Resona Vision API. Any other message is left alone and goes to Lex exactly as before.
 *
 * The conversation steps are plain functions with no browser code (claimOnText, claimOnOrder,
 * claimOnResult), so they can be tested with Node. The browser part (glue) is at the bottom.
 */
(function (root) {
  "use strict";

  // ===================================================================== 1. SETTINGS
  var CONFIG = {
    // Invoke URL of Resona-Vision-API, with no slash at the end.
    // Or set window.RESONA_CLAIM_API = "https://..." in the page before this file loads.
    API: "https://ohhb1qlnxj.execute-api.us-east-1.amazonaws.com",
    MAX_PHOTO_BYTES: 4 * 1024 * 1024,   // the server rejects bigger photos
    MAX_SIDE: 1280                      // photos are shrunk to this width before upload
  };

  // ===================================================================== 2. CONVERSATION LOGIC (no browser code)
  var REFUND_WORDS = /\b(refund|money back|damaged?|broken|cracked|torn|defective|crushed|dent(?:ed)?)\b/i;
  var CANCEL_WORDS = /\b(cancel|never ?mind|forget it|stop|exit)\b/i;
  var ORDER_AFTER_WORD = /order\s*(?:number|no\.?|id|#)?\s*[:#]?\s*([A-Za-z]{0,2}\d{3,8})\b/i;
  var ORDER_ANY = /\b([A-Za-z]{0,2}\d{3,8})\b/;

  function newState() {
    return { step: "IDLE", orderId: null, items: [], item: null, caseId: null };
  }
  function copy(s) { return JSON.parse(JSON.stringify(s)); }
  function say(text) { return { type: "say", text: text }; }

  function money(v) {
    var n = Number(v);
    if (!isFinite(n) || n <= 0) return "";
    return " (\u20B9" + n.toLocaleString("en-IN") + ")";
  }

  function isClaimable(item) {
    return String(item.status || "").toUpperCase() !== "REFUNDED";
  }

  // Accept both camelCase (new API) and PascalCase (DynamoDB style) fields.
  function normalizeOrder(o) {
    if (!o) return null;
    var raw = o.items || o.Items || [];
    return {
      orderId: String(o.orderId || o.OrderId || ""),
      items: raw.map(function (i) {
        var id = i.itemId || i.ItemId || "";
        return {
          itemId: String(id),
          name: String(i.name || i.Name || id),
          price: Number(i.price != null ? i.price : (i.Price != null ? i.Price : (i.RefundAmount || 0))),
          status: String(i.status || i.Status || ""),
          productId: i.productId || i.ProductId || ""
        };
      })
    };
  }

  function uploadPrompt(item) {
    return "Thanks. Please upload a clear photo of the " + item.name + money(item.price) +
      " you received. Show the whole product and the damaged part, in good light.";
  }

  // What the customer typed -> what to do next.
  // Returns { handled, state, actions }. handled=false means "not my job, send it to Lex".
  function claimOnText(state, text) {
    var t = String(text || "").trim();
    var s = copy(state);
    var id;

    if (s.step === "IDLE") {
      if (!REFUND_WORDS.test(t)) return { handled: false, state: s, actions: [] };
      var m = t.match(ORDER_AFTER_WORD);
      if (m) {
        s.step = "LOOKUP"; s.orderId = m[1].toUpperCase();
        return { handled: true, state: s, actions: [{ type: "lookup", orderId: s.orderId }] };
      }
      s.step = "ASK_ORDER";
      return { handled: true, state: s, actions: [say("Sure, I can help with that. Which order number is this for?")] };
    }

    if (s.step === "LOOKUP" || s.step === "WORKING") {
      return { handled: true, state: s, actions: [say("One moment, I am still working on your request.")] };
    }

    if (CANCEL_WORDS.test(t)) {
      return { handled: true, state: newState(),
        actions: [say("No problem, I have cancelled this request. Ask me anything else, or say you want a refund to start again.")] };
    }

    if (s.step === "ASK_ORDER") {
      var found = t.match(ORDER_ANY);
      if (!found) {
        return { handled: true, state: s, actions: [say("I could not see an order number in that. It looks like 9999 or A1001. Please send it again, or type cancel.")] };
      }
      s.step = "LOOKUP"; s.orderId = found[1].toUpperCase();
      return { handled: true, state: s, actions: [{ type: "lookup", orderId: s.orderId }] };
    }

    if (s.step === "ASK_ITEM") {
      var pick = null;
      var n = parseInt(t, 10);
      if (/^\d{1,2}$/.test(t) && n >= 1 && n <= s.items.length) pick = s.items[n - 1];
      if (!pick) {
        var low = t.toLowerCase();
        pick = s.items.filter(function (i) {
          return i.itemId.toLowerCase() === low || (low.length >= 3 && i.name.toLowerCase().indexOf(low) !== -1);
        })[0] || null;
      }
      if (!pick) {
        return { handled: true, state: s,
          actions: [say("Please reply with the number of the item (1 to " + s.items.length + ") or its item ID. Type cancel to stop.")] };
      }
      s.item = pick; s.step = "ASK_PHOTO";
      return { handled: true, state: s, actions: [say(uploadPrompt(pick)), { type: "uploadCard" }] };
    }

    if (s.step === "ASK_PHOTO") {
      return { handled: true, state: s,
        actions: [say("I am waiting for your photo. Use the Take photo or Choose photo button above. Type cancel to stop.")] };
    }

    return { handled: false, state: s, actions: [] };
  }

  // The order came back from the API (or null if it does not exist).
  function claimOnOrder(state, orderRaw) {
    var s = copy(state);
    var order = normalizeOrder(orderRaw);
    if (!order) {
      s.step = "ASK_ORDER";
      return { state: s, actions: [say("I could not find order " + s.orderId + ". Please check the number and send it again, or type cancel.")] };
    }
    var items = order.items.filter(isClaimable);
    s.orderId = order.orderId || s.orderId;
    if (items.length === 0) {
      return { state: newState(), actions: [say("Order " + s.orderId + " has no items that can be claimed right now. They may already be refunded or not delivered yet.")] };
    }
    s.items = items;
    if (items.length === 1) {
      s.item = items[0]; s.step = "ASK_PHOTO";
      return { state: s, actions: [say("I found order " + s.orderId + ". " + uploadPrompt(items[0])), { type: "uploadCard" }] };
    }
    s.step = "ASK_ITEM";
    var lines = items.map(function (i, k) { return (k + 1) + ". " + i.name + money(i.price) + " [" + i.itemId + "]"; });
    return { state: s, actions: [say("I found order " + s.orderId + " with " + items.length + " items:\n" + lines.join("\n") +
      "\nWhich item has the problem? Reply with the number or the item ID.")] };
  }

  // The API answered after the photo was sent. Never claim a refund unless the backend verified it.
  function claimOnResult(state, data) {
    var s = copy(state);
    var d = data || {};
    var decision = d.decision || {};
    var status = String(d.status || "").toUpperCase();
    var action = String(decision.action || "").toUpperCase();
    var caseId = d.caseId || s.caseId || "";
    var refund = d.refund || {};
    var annotated = d.annotatedUrl || d.annotated_url || "";
    var panel = { type: "panel", item: s.item ? s.item.name : "", amount: s.item ? s.item.price : "",
                  decision: action || status, actionId: refund.actionId || "", caseId: caseId };
    var out = [];

    if (status === "RESOLVED_REFUNDED" && refund.actionId && refund.verified !== false) {
      s = newState();
      out.push(say("Your refund has been processed and checked against the order record. Action ID: " + refund.actionId + "."));
    }  else if (status === "AWAITING_EVIDENCE" || action === "RETAKE") {
  s.step = "ASK_PHOTO";
  s.caseId = caseId || s.caseId;

  var reason = String(
    decision.reason || decision.message || d.message || ""
  ).toLowerCase();

  var isBlurry =
    reason.includes("blur") ||
    reason.includes("blurry") ||
    reason.includes("focus") ||
    reason.includes("sharpness");

  out.push(say(
    isBlurry
      ? "⚠️ BLURRY IMAGE — RETAKE REQUIRED. Please upload a sharper, clearer photo."
      : "⚠️ PHOTO CHECK FAILED — RETAKE REQUIRED. " +
        (decision.message || "Please upload a clearer photo.")
  ));

  if (annotated) out.push({ type: "image", url: annotated });
  out.push({ type: "uploadCard" });
  out.push(panel);

  return { state: s, actions: out };
    } else if (status === "PENDING_REVIEW" || status === "IN_REVIEW" || action === "ESCALATE") {
      s = newState();
      out.push(say((decision.message || "A person will review your claim.") +
        " Your case ID is " + caseId + ". Status: waiting for a person to review. Nothing has been refunded yet."));
    } else {
      s = newState();
      out.push(say((decision.message || "Your photo was received.") + (caseId ? " Your case ID is " + caseId + "." : "")));
    }
    if (annotated) out.push({ type: "image", url: annotated });
    out.push(panel);
    return { state: s, actions: out };
  }

  var Logic = { CONFIG: CONFIG, newState: newState, claimOnText: claimOnText, claimOnOrder: claimOnOrder,
                claimOnResult: claimOnResult, normalizeOrder: normalizeOrder };
  if (typeof module !== "undefined" && module.exports) { module.exports = Logic; }
  root.ClaimFlowLogic = Logic;

  // ===================================================================== 3. BROWSER PART (glue)
  if (typeof document === "undefined" || !document.getElementById("chatArea")) { return; }

  var flow = newState();

  function apiBase() { return (root.RESONA_CLAIM_API || CONFIG.API).replace(/\/$/, ""); }

  async function api(method, path, body) {
    var opts = { method: method };
    if (body) { opts.headers = { "Content-Type": "application/json" }; opts.body = JSON.stringify(body); }
    var res = await fetch(apiBase() + path, opts);
    var data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
      var err = new Error(data.message || data.error || ("Request failed (" + res.status + ")"));
      err.status = res.status;
      throw err;
    }
    return data;
  }

  async function lookupOrder(orderId) {
    try { return await api("GET", "/orders/" + encodeURIComponent(orderId)); }
    catch (e) { if (e.status === 404) return null; throw e; }
  }

  function readAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      var r = new FileReader();
      r.onload = function () { resolve(r.result); };
      r.onerror = function () { reject(new Error("Could not read the photo.")); };
      r.readAsDataURL(file);
    });
  }

  // Shrink the photo (also removes location data). Falls back to the original if the browser cannot.
  async function photoToBase64(file) {
    var dataUrl = null;
    try {
      if (typeof createImageBitmap === "function") {
        var bmp = await createImageBitmap(file);
        var scale = Math.min(1, CONFIG.MAX_SIDE / bmp.width);
        var c = document.createElement("canvas");
        c.width = Math.max(1, Math.round(bmp.width * scale));
        c.height = Math.max(1, Math.round(bmp.height * scale));
        c.getContext("2d").drawImage(bmp, 0, 0, c.width, c.height);
        dataUrl = c.toDataURL("image/jpeg", 0.85);
      }
    } catch (e) { dataUrl = null; }
    if (!dataUrl) dataUrl = await readAsDataURL(file);
    var b64 = dataUrl.split(",")[1] || "";
    if (b64.length * 0.75 > CONFIG.MAX_PHOTO_BYTES) throw new Error("That photo is too large. Please use one under 4 MB.");
    return b64;
  }

  function el(tag, props, children) {
    var e = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "text") e.textContent = props[k]; else if (k === "class") e.className = props[k]; else e.setAttribute(k, props[k]);
    });
    (children || []).forEach(function (c) { e.appendChild(c); });
    return e;
  }

  function injectStyles() {
    if (document.getElementById("rvc-styles")) return;
    var css = ".rvc-card{display:grid;gap:10px;min-width:260px}" +
      ".rvc-card strong{font-size:14px}.rvc-card p{margin:0;font-size:13px;opacity:.85}" +
      ".rvc-row{display:flex;gap:8px;flex-wrap:wrap}" +
      ".rvc-btn{border:1px solid rgba(255,154,97,.55);background:rgba(255,154,97,.1);color:inherit;border-radius:10px;padding:9px 14px;font:inherit;cursor:pointer}" +
      ".rvc-btn:hover{background:rgba(255,154,97,.22)}.rvc-btn:disabled{opacity:.45;cursor:not-allowed}" +
      ".rvc-primary{background:linear-gradient(135deg,#ffa468,#ff8a4d);color:#1a1209;font-weight:700;border-color:transparent}" +
      ".rvc-text{border:1px solid rgba(255,255,255,.18);background:rgba(0,0,0,.25);color:inherit;border-radius:10px;padding:9px 12px;font:inherit}" +
      ".rvc-preview{max-width:100%;max-height:220px;border-radius:10px;display:none}" +
      ".rvc-status{font-size:12px;opacity:.9;min-height:1em}" +
      ".rvc-img{max-width:100%;border-radius:10px;display:block;margin-bottom:8px}";
    var st = el("style", { id: "rvc-styles" }); st.textContent = css; document.head.appendChild(st);
  }

  function say_(text) { root.addMessage(text, "bot"); }

  function lastBubble() {
    var rows = document.getElementById("chatArea").children;
    return rows[rows.length - 1].querySelector(".bubble");
  }

  function addImageMessage(url, caption) {
    root.addMessage(caption, "bot");
    var img = el("img", { class: "rvc-img", src: url, alt: caption });
    var b = lastBubble(); b.insertBefore(img, b.firstChild);
  }

  function setPanel(p) {
    function put(id, v) { var n = document.getElementById(id); if (n && v !== "" && v != null) n.textContent = String(v); }
    put("refundItemValue", p.item);
    put("refundAmountValue", p.amount ? "\u20B9" + Number(p.amount).toLocaleString("en-IN") : "");
    put("refundDecisionValue", p.decision);
    put("actionIdValue", p.actionId);
    put("caseIdValue", p.caseId);
  }

  function addUploadCard() {
    injectStyles();
    root.addMessage("", "bot");
    var bubble = lastBubble();
    bubble.textContent = "";

    var camera = el("input", { type: "file", accept: "image/*", capture: "environment", hidden: "" });
    var gallery = el("input", { type: "file", accept: "image/*", hidden: "" });
    var desc = el("input", { type: "text", class: "rvc-text", maxlength: "200", placeholder: "What is damaged? (optional)", "aria-label": "What is damaged" });
    var takeBtn = el("button", { type: "button", class: "rvc-btn", text: "Take photo" });
    var pickBtn = el("button", { type: "button", class: "rvc-btn", text: "Choose photo" });
    var sendBtn = el("button", { type: "button", class: "rvc-btn rvc-primary", text: "Send photo" });
    sendBtn.disabled = true;
    var preview = el("img", { class: "rvc-preview", alt: "Preview of your photo" });
    var status = el("div", { class: "rvc-status", role: "status", "aria-live": "polite" });
    var chosen = null;

    function choose(file) {
      if (!file) return;
      chosen = file; sendBtn.disabled = false;
      if (root.URL && URL.createObjectURL) { preview.src = URL.createObjectURL(file); preview.style.display = "block"; }
      status.textContent = "Photo ready: " + (file.name || "camera photo");
    }
    takeBtn.addEventListener("click", function () { camera.click(); });
    pickBtn.addEventListener("click", function () { gallery.click(); });
    camera.addEventListener("change", function () { choose(camera.files && camera.files[0]); });
    gallery.addEventListener("change", function () { choose(gallery.files && gallery.files[0]); });
    sendBtn.addEventListener("click", function () {
      if (!chosen) return;
      [takeBtn, pickBtn, sendBtn, desc].forEach(function (x) { x.disabled = true; });
      submitPhoto(chosen, desc.value.trim(), status, [takeBtn, pickBtn, sendBtn, desc]);
    });

    var card = el("div", { class: "rvc-card", role: "group", "aria-label": "Upload a photo" }, [
      el("strong", { text: "Upload a photo of the item" }),
      el("p", { text: "On a phone, Take photo opens the camera. On a computer it opens a file chooser. Maximum 4 MB." }),
      desc, el("div", { class: "rvc-row" }, [takeBtn, pickBtn]), camera, gallery, preview,
      el("div", { class: "rvc-row" }, [sendBtn]), status
    ]);
    bubble.appendChild(card);
    root.scrollChatToBottom && root.scrollChatToBottom();
  }

  async function submitPhoto(file, description, statusEl, controls) {
    var typing = root.showTypingIndicator ? root.showTypingIndicator() : null;
    flow.step = "WORKING";
    statusEl.textContent = "Checking your photo...";
    try {
      if (!flow.caseId) {
        var claim = await api("POST", "/claims", {
          orderId: flow.orderId, itemId: flow.item.itemId, description: description || "Damaged item reported in chat"
        });
        flow.caseId = claim.caseId;
        setPanel({ item: flow.item.name, amount: flow.item.price, decision: "Evidence needed", caseId: flow.caseId });
      }
      var image = await photoToBase64(file);
      var data = await api("POST", "/claims/" + encodeURIComponent(flow.caseId) + "/evidence", { image: image });
      if (typing) typing.remove();
      statusEl.textContent = "Photo sent.";
      var r = claimOnResult(flow, data);
      flow = r.state;
      await runActions(r.actions);
    } catch (e) {
      if (typing) typing.remove();
      var business = e.status && e.status >= 400 && e.status < 500;
      if (business) {
        flow = newState();
        say_(e.message + " I have stopped this request. You can start again any time.");
        statusEl.textContent = "";
      } else {
        flow.step = "ASK_PHOTO";
        statusEl.textContent = "Something went wrong: " + e.message + " You can press Send photo to try again.";
        controls.forEach(function (x) { x.disabled = false; });
        if (root.setConnection) root.setConnection(false, "Service issue");
      }
    }
  }

  async function runActions(actions) {
    for (var i = 0; i < actions.length; i++) {
      var a = actions[i];
      if (a.type === "say") say_(a.text);
      else if (a.type === "uploadCard") addUploadCard();
      else if (a.type === "image") addImageMessage(a.url, "Red box: where your photo differs from the catalog photo. Heat map: how different.");
      else if (a.type === "panel") setPanel(a);
      else if (a.type === "lookup") {
        var typing = root.showTypingIndicator ? root.showTypingIndicator() : null;
        var order = null, failed = null;
        try { order = await lookupOrder(a.orderId); } catch (e) { failed = e; }
        if (typing) typing.remove();
        if (failed) {
          flow.step = "ASK_ORDER";
          say_("I could not reach the order service just now. Please send the order number again in a moment.");
          if (root.setConnection) root.setConnection(false, "Service issue");
        } else {
          var r = claimOnOrder(flow, order);
          flow = r.state;
          await runActions(r.actions);
        }
      }
    }
  }

  // Called by sendMessage() before anything is sent to Lex. Returns true if this file handled the message.
  root.handleClaimFlow = async function (message) {
    var r = claimOnText(flow, message);
    if (!r.handled) return false;
    var welcome = document.getElementById("welcome"); if (welcome) welcome.remove();
    root.addMessage(message, "user");
    var box = document.getElementById("messageInput"); if (box) box.value = "";
    flow = r.state;
    await runActions(r.actions);
    return true;
  };

  root.resetClaimFlow = function () { flow = newState(); };
  var newBtn = document.getElementById("newConversationBtn");
  if (newBtn) newBtn.addEventListener("click", root.resetClaimFlow);

})(typeof window !== "undefined" ? window : globalThis);
