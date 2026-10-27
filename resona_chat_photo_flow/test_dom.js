// Loads your page in a fake browser (jsdom), applies the 2-line patch, and chats with it.
const fs = require("fs");
const { JSDOM } = require("jsdom");

let html = fs.readFileSync(process.argv[2] || "index.html", "utf8");
// THE PATCH (same as the guide, step 5): one line at the top of sendMessage
html = html.replace("if (!message || busy) return;", "if (!message || busy) return;\n  if (await handleClaimFlow(message)) return;");
const flowSrc = fs.readFileSync("./claim_flow.js", "utf8");
html = html.replace("</body>", "<script>" + flowSrc.replace(/<\/script>/g, "<\\/script>") + "</script>\n</body>");

const calls = [];
function mockFetch(url, opts) {
  opts = opts || {}; calls.push({ url, method: opts.method || "GET", body: opts.body });
  const json = (status, obj) => Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(obj) });
  if (url.endsWith("/chat")) return json(200, { reply: "LEX: your order 1234 is shipped." });
  if (url.includes("/orders/9999")) return json(200, { orderId: "9999", items: [{ itemId: "9999-1", name: "Keyboard", price: 1299, status: "DELIVERED", productId: "P001" }] });
  if (url.includes("/orders/A1001")) return json(200, { orderId: "A1001", items: [
      { itemId: "A1001-1", name: "Mouse", price: 399, status: "DELIVERED" }, { itemId: "A1001-2", name: "Headset", price: 1999, status: "DELIVERED" }] });
  if (url.includes("/orders/")) return json(404, { message: "Order not found" });
  if (url.endsWith("/claims") && opts.method === "POST") return json(200, { caseId: "c-123", status: "AWAITING_EVIDENCE" });
  if (url.includes("/evidence")) {
    evidenceCalls++;
    if (evidenceCalls === 1) return json(200, { caseId: "c-123", status: "AWAITING_EVIDENCE", decision: { action: "RETAKE", message: "The photo is blurry. Hold the phone steady." } });
    return json(200, { caseId: "c-123", status: "RESOLVED_REFUNDED", refund: { actionId: "act-77", verified: true }, decision: { action: "AUTO_APPROVE" }, annotatedUrl: "https://example.com/a.jpg" });
  }
  return json(500, { message: "unexpected " + url });
}
let evidenceCalls = 0;

const dom = new JSDOM(html, { runScripts: "dangerously", pretendToBeVisual: true, url: "http://localhost:8000/",
  beforeParse(w) { w.fetch = mockFetch; w.RESONA_CLAIM_API = "https://api.test"; w.HTMLElement.prototype.scrollIntoView = () => {}; } });
const w = dom.window, d = w.document;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
let failed = 0;
const check = (n, c) => { console.log((c ? "ok  " : "BAD ") + n); if (!c) failed++; };
const chat = () => d.getElementById("chatArea").textContent;

async function say(text) { await w.sendMessage(text); await sleep(30); }
async function sendPhoto(desc) {
  const cards = d.querySelectorAll(".rvc-card"); const card = cards[cards.length - 1];
  const gallery = card.querySelectorAll("input[type=file]")[1];
  const file = new w.File([new Uint8Array([255, 216, 255, 224, 0, 16, 74, 70, 73, 70])], "damaged.jpg", { type: "image/jpeg" });
  Object.defineProperty(gallery, "files", { value: [file], configurable: true });
  gallery.dispatchEvent(new w.Event("change"));
  if (desc) card.querySelector("input[type=text]").value = desc;
  card.querySelector(".rvc-primary").click();
  await sleep(150);
}

(async () => {
  await sleep(50);
  // the exact conversation from the brief
  await say("I want a refund");
  check("bot asks which order number", /Which order number/.test(chat()));
  await say("9999");
  check("bot asks for the picture in the chat", /upload a clear photo of the Keyboard/.test(chat()));
  check("upload card appears inside the chat", d.querySelectorAll("#chatArea .rvc-card").length === 1);
  check("order lookup used the new API, Lex was NOT called", calls.some(c => c.url.includes("/orders/9999")) && !calls.some(c => c.url.endsWith("/chat")));
  check("send button is disabled until a photo is chosen", d.querySelector(".rvc-primary").disabled === true);

  await sendPhoto("corner crushed");
  const claimCall = calls.find(c => c.url.endsWith("/claims"));
  check("claim created with order, item and the typed description", claimCall && /"orderId":"9999"/.test(claimCall.body) && /9999-1/.test(claimCall.body) && /corner crushed/.test(claimCall.body));
  const evCall = calls.find(c => c.url.includes("/claims/c-123/evidence"));
  check("photo sent as base64 JSON to the evidence route", evCall && /"image":"/.test(evCall.body));
  check("first result was RETAKE: message and a new upload card", /blurry/.test(chat()) && d.querySelectorAll("#chatArea .rvc-card").length === 2);

  await sendPhoto("");
  check("second photo reused the same case (no second claim)", calls.filter(c => c.url.endsWith("/claims")).length === 1);
  check("verified refund confirmed with action id", /refund has been processed/.test(chat()) && /act-77/.test(chat()));
  check("annotated picture shown", !!d.querySelector("#chatArea img.rvc-img"));
  check("side panel shows case and action ids", d.getElementById("caseIdValue").textContent === "c-123" && d.getElementById("actionIdValue").textContent === "act-77");

  // normal chat still goes to Lex
  const before = calls.length;
  await say("Where is my order 1234?");
  check("normal question still reaches Lex", calls.slice(before).some(c => c.url.endsWith("/chat")) && /LEX: your order 1234/.test(chat()));

  // quick button + multi item + cancel + unknown order
  await say("I want to request a refund"); await say("0000");
  check("unknown order is reported", /could not find order 0000/.test(chat()));
  await say("A1001");
  check("multi-item order asks which item", /Which item has the problem/.test(chat()));
  await say("cancel");
  check("cancel stops the flow", /cancelled this request/.test(chat()));
  await say("Where is my order 1234?");
  check("after cancel, normal chat works again", calls.filter(c => c.url.endsWith("/chat")).length === 2);

  // new conversation resets
  await say("refund"); d.getElementById("newConversationBtn").click(); await sleep(30);
  await say("hello there");
  check("new conversation resets the flow", calls.filter(c => c.url.endsWith("/chat")).length === 3);

  console.log(failed ? "\nFAILED: " + failed : "\nALL PASSED");
  process.exit(failed ? 1 : 0);
})();
