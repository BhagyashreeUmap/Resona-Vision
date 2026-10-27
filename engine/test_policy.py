from policy import decide

def ev(q=True, product="MATCH", damage="LIKELY", reused=False, qr=None):
    return {"quality": {"ok": q, "reasons": qr or ([] if q else ["TOO_BLURRY"])},
            "product": {"status": product}, "damage": {"level": damage},
            "reuse": {"reused": reused},
            "reason_codes": ([] if q else ["TOO_BLURRY"]) + ["PRODUCT_" + product, "DAMAGE_" + damage]}

cases = [
 ("strong evidence, HIGH trust",         ev(),                      90, 200, 1, "AUTO_APPROVE"),
 ("strong evidence, MEDIUM, 300",        ev(),                      60, 300, 1, "AUTO_APPROVE"),
 ("strong evidence, MEDIUM, 800",        ev(),                      60, 800, 1, "ESCALATE"),
 ("strong evidence, LOW trust",          ev(),                      30, 200, 1, "ESCALATE"),
 ("blurry, first upload",                ev(q=False),               90, 200, 1, "RETAKE"),
 ("blurry, third upload",                ev(q=False),               90, 200, 3, "ESCALATE"),
 ("wrong product, first upload",         ev(product="NO_MATCH", damage="UNKNOWN"), 90, 200, 1, "RETAKE"),
 ("ambiguous damage",                    ev(damage="POSSIBLE"),     90, 200, 1, "ESCALATE"),
 ("no damage seen",                      ev(damage="NONE"),         90, 200, 1, "ESCALATE"),
 ("reused photo, HIGH trust",            ev(reused=True),           95, 100, 1, "ESCALATE"),
 ("no reference image",                  ev(product="NO_REFERENCE", damage="UNKNOWN"), 90, 100, 1, "ESCALATE"),
]
bad = 0
for name, e, trust, price, n, want in cases:
    got = decide(e, trust, price, n)
    flag = "ok " if got["action"] == want else "BAD"
    bad += got["action"] != want
    print(f"{flag} {name:<34} -> {got['action']:<13} {got['rule']}")
assert all(decide(e, t, p, n)["action"] != "DENY" for _, e, t, p, n, _ in cases)
print("failures:", bad)
