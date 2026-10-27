// Tests for the conversation logic in claim_flow.js (no browser needed): node test_flow.js
const L = require("./claim_flow.js");
let failed = 0;
function check(name, cond) { console.log((cond ? "ok  " : "BAD ") + name); if (!cond) failed++; }
const texts = (r) => r.actions.filter(a => a.type === "say").map(a => a.text).join(" | ");
const has = (r, type) => r.actions.some(a => a.type === type);

const one  = { orderId: "9999", items: [{ itemId: "9999-1", name: "Keyboard", price: 1299, status: "DELIVERED" }] };
const many = { orderId: "A1001", items: [
  { itemId: "A1001-1", name: "Mouse", price: 399, status: "DELIVERED" },
  { itemId: "A1001-2", name: "Headset", price: 1999, status: "DELIVERED" },
  { itemId: "A1001-3", name: "Webcam", price: 899, status: "REFUNDED" }] };

// 1. the example conversation from the brief
let s = L.newState();
let r = L.claimOnText(s, "I want a refund");
check("refund request asks for the order number", r.handled && r.state.step === "ASK_ORDER" && /Which order number/.test(texts(r)));
r = L.claimOnText(r.state, "9999");
check("order number triggers a lookup", r.state.step === "LOOKUP" && r.actions[0].type === "lookup" && r.actions[0].orderId === "9999");
r = L.claimOnOrder(r.state, one);
check("single item goes straight to the photo request", r.state.step === "ASK_PHOTO" && has(r, "uploadCard") && /upload a clear photo/i.test(texts(r)));

// 2. quick-button wording and direct order number
r = L.claimOnText(L.newState(), "I want to request a refund");
check("quick button text starts the flow", r.handled && r.state.step === "ASK_ORDER");
r = L.claimOnText(L.newState(), "my keyboard arrived broken, order number A1001");
check("order number in the first message skips a question", r.state.step === "LOOKUP" && r.actions[0].orderId === "A1001");
r = L.claimOnText(L.newState(), "I paid 5000 rupees and it is damaged");
check("a price is not mistaken for an order number", r.state.step === "ASK_ORDER");

// 3. multiple items
r = L.claimOnText(L.newState(), "refund please"); r = L.claimOnText(r.state, "a1001");
check("lowercase order id is normalised", r.actions[0].orderId === "A1001");
r = L.claimOnOrder(r.state, many);
check("multi-item order lists only claimable items", r.state.step === "ASK_ITEM" && /1\. Mouse/.test(texts(r)) && /2\. Headset/.test(texts(r)) && !/Webcam/.test(texts(r)));
let askItem = r.state;
r = L.claimOnText(askItem, "maybe");
check("unclear item answer asks again", r.state.step === "ASK_ITEM");
r = L.claimOnText(askItem, "2");
check("number picks the item", r.state.step === "ASK_PHOTO" && r.state.item.itemId === "A1001-2" && has(r, "uploadCard"));
r = L.claimOnText(askItem, "a1001-1");
check("item id picks the item", r.state.item && r.state.item.itemId === "A1001-1");
r = L.claimOnText(askItem, "headset");
check("item name picks the item", r.state.item && r.state.item.itemId === "A1001-2");
r = L.claimOnText(askItem, "3");
check("a number outside the list is refused", r.state.step === "ASK_ITEM");

// 4. normal chat is left alone
r = L.claimOnText(L.newState(), "Where is my order 1234?");
check("order status question is not handled (goes to Lex)", r.handled === false);
r = L.claimOnText(L.newState(), "Can you check my shipment?");
check("shipment question is not handled (goes to Lex)", r.handled === false);

// 5. cancel and waiting
r = L.claimOnText({ ...L.newState(), step: "ASK_PHOTO", item: one.items[0] }, "cancel");
check("cancel resets the flow", r.state.step === "IDLE" && /cancelled/.test(texts(r)));
r = L.claimOnText({ ...L.newState(), step: "ASK_PHOTO", item: one.items[0] }, "hello?");
check("typing while waiting for a photo gives a reminder", r.handled && r.state.step === "ASK_PHOTO");
r = L.claimOnText({ ...L.newState(), step: "ASK_ORDER" }, "no idea");
check("no order number in the answer asks again", r.state.step === "ASK_ORDER");

// 6. order problems
r = L.claimOnOrder({ ...L.newState(), step: "LOOKUP", orderId: "0000" }, null);
check("unknown order asks again", r.state.step === "ASK_ORDER" && /could not find order 0000/.test(texts(r)));
r = L.claimOnOrder({ ...L.newState(), step: "LOOKUP", orderId: "5678" }, { orderId: "5678", items: [{ itemId: "x", name: "Cable", price: 100, status: "REFUNDED" }] });
check("nothing claimable ends the flow", r.state.step === "IDLE");
r = L.claimOnOrder({ ...L.newState(), step: "LOOKUP", orderId: "1122" }, { OrderId: "1122", Items: [{ ItemId: "I1", Name: "Lamp", Price: 500, Status: "DELIVERED" }] });
check("PascalCase DynamoDB-style order is accepted", r.state.step === "ASK_PHOTO" && r.state.item.name === "Lamp");

// 7. results: honesty rules
const base = { ...L.newState(), step: "WORKING", orderId: "9999", item: one.items[0], caseId: "c-1" };
r = L.claimOnResult(base, { caseId: "c-1", status: "AWAITING_EVIDENCE", decision: { action: "RETAKE", message: "The photo is blurry." } });
check("RETAKE asks for a new photo and shows the card again", r.state.step === "ASK_PHOTO" && has(r, "uploadCard") && r.state.caseId === "c-1");
r = L.claimOnResult(base, { caseId: "c-1", status: "PENDING_REVIEW", decision: { action: "ESCALATE", message: "A person will review." } });
check("escalation says nothing was refunded and gives the case id", r.state.step === "IDLE" && /c-1/.test(texts(r)) && /Nothing has been refunded/.test(texts(r)));
r = L.claimOnResult(base, { caseId: "c-1", status: "RESOLVED_REFUNDED", refund: { actionId: "a-9", verified: true }, decision: { action: "AUTO_APPROVE" } });
check("verified refund is confirmed with the action id", /refund has been processed/.test(texts(r)) && /a-9/.test(texts(r)));
r = L.claimOnResult(base, { caseId: "c-1", status: "RESOLVED_REFUNDED", refund: { actionId: "a-9", verified: false } });
check("an unverified refund is NOT reported as success", !/refund has been processed/.test(texts(r)));
r = L.claimOnResult(base, { caseId: "c-1", status: "RESOLVED_REFUNDED" });
check("a refund without an action id is NOT reported as success", !/refund has been processed/.test(texts(r)));
r = L.claimOnResult(base, { caseId: "c-1", status: "PENDING_REVIEW", decision: { action: "AUTO_APPROVE" } });
check("AUTO_APPROVE with a pending status is not a success message", !/refund has been processed/.test(texts(r)));
r = L.claimOnResult(base, { caseId: "c-1", status: "PENDING_REVIEW", annotatedUrl: "https://x/y.jpg" });
check("annotated picture is shown when present", has(r, "image"));
r = L.claimOnResult(base, null);
check("empty response does not crash", r.state.step === "IDLE");

console.log(failed === 0 ? "\nALL PASSED" : "\nFAILED: " + failed);
process.exit(failed ? 1 : 0);
