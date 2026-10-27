"""
policy.py - Resona Vision decision rules (plain Python, no AWS code).

The AI may APPROVE or ESCALATE or ask for a RETAKE. It can never DENY a claim:
only a human reviewer can reject.
"""

POLICY = {
    "max_retakes": 2,          # how many times the customer may be asked for a better photo
    "medium_amount_limit": 500,  # medium trust: refunds at or above this go to a human
    "high_trust": 80,
    "low_trust": 50,           # below this = LOW
}

TIPS = {
    "TOO_BLURRY": "The photo is blurry. Hold the phone steady and tap the screen to focus.",
    "TOO_DARK": "The photo is too dark. Move to a brighter place or turn on a light.",
    "TOO_BRIGHT": "The photo is too bright. Avoid direct flash or strong glare.",
    "LOW_CONTRAST": "The photo looks washed out. Try a plain background and better light.",
    "LOW_RESOLUTION": "The photo is too small. Use the normal camera, not a screenshot.",
    "PRODUCT_NO_MATCH": "I could not recognise the product. Show the whole product, front side up.",
    "PRODUCT_WEAK": "I am not sure this is the right product. Show the whole product and its label.",
}


def trust_band(score, cfg=POLICY):
    if score >= cfg["high_trust"]:
        return "HIGH"
    if score >= cfg["low_trust"]:
        return "MEDIUM"
    return "LOW"


def _tips(codes):
    return " ".join(TIPS[c] for c in codes if c in TIPS)


def decide(evidence, trust_score, price, uploads_so_far, cfg=POLICY):
    """
    evidence: the dict returned by cv_core.analyze
    trust_score: current refund trust score (0-100)
    price: refund amount of the item
    uploads_so_far: how many photos the customer has sent for this claim, including this one
    Returns: {action, rule, reasons, suggested, customer_message}
    """
    codes = evidence["reason_codes"]
    q_ok = evidence["quality"]["ok"]
    product = evidence["product"]["status"]
    damage = evidence["damage"]["level"]
    reused = evidence["reuse"]["reused"]
    band = trust_band(trust_score, cfg)
    retakes_left = (uploads_so_far - 1) < cfg["max_retakes"]

    strong = q_ok and product == "MATCH" and damage == "LIKELY" and not reused
    suggested = "LIKELY_VALID" if strong else "UNCLEAR"

    def out(action, rule, reasons, message):
        return {"action": action, "rule": rule, "reasons": reasons,
                "suggested": suggested, "trust_band": band, "customer_message": message}

    if reused:
        return out("ESCALATE", "R1_REUSED_PHOTO", ["PHOTO_REUSED"],
                   "This photo looks like one that was sent before, so a person will review your claim.")
    if not q_ok:
        bad = evidence["quality"]["reasons"]
        if retakes_left:
            return out("RETAKE", "R2_BAD_QUALITY", bad, _tips(bad))
        return out("ESCALATE", "R2_QUALITY_RETRIES_USED", bad,
                   "The photos were still hard to use, so a person will review your claim.")
    if product == "NO_REFERENCE":
        return out("ESCALATE", "R3_NO_REFERENCE_IMAGE", ["NO_REFERENCE_IMAGE"],
                   "I cannot compare this product automatically, so a person will review your claim.")
    if product != "MATCH":
        code = "PRODUCT_" + product
        if retakes_left:
            return out("RETAKE", "R4_PRODUCT_NOT_CONFIRMED", [code], _tips([code]))
        return out("ESCALATE", "R4_PRODUCT_RETRIES_USED", [code],
                   "I could not confirm the product, so a person will review your claim.")
    if damage != "LIKELY":
        why = "DAMAGE_" + damage
        return out("ESCALATE", "R5_DAMAGE_NOT_CLEAR", [why],
                   "I could not clearly see the damage, so a person will review your claim.")
    if band == "LOW":
        return out("ESCALATE", "R6_LOW_TRUST", ["TRUST_LOW"],
                   "A person will review your claim before any refund is made.")
    if band == "MEDIUM" and price >= cfg["medium_amount_limit"]:
        return out("ESCALATE", "R6_AMOUNT_LIMIT", ["AMOUNT_OVER_LIMIT"],
                   "Because of the refund amount, a person will review your claim.")
    return out("AUTO_APPROVE", "R7_EVIDENCE_AND_TRUST_OK", ["EVIDENCE_STRONG", "TRUST_" + band],
               "The photo supports your claim. I am processing your refund now.")
