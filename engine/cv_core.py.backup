"""
cv_core.py - Resona Vision evidence engine (OpenCV 5).

Pure functions only: no AWS code in this file, so you can test it on your laptop
and then run the same file inside AWS Lambda.
"""
import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Thresholds. These are STARTING values. You will tune them with your own photos
# in Part 4 (use the dev split only, then report results on the test split).
# ---------------------------------------------------------------------------
CFG = {
    "norm_width": 800,        # every photo is resized to this width before measuring
    "min_side": 400,          # smaller photos are rejected as LOW_RESOLUTION
    "blur_min": 35.0,         # Laplacian variance below this = TOO_BLURRY
    "dark_max": 50.0,         # mean brightness below this = TOO_DARK
    "bright_min": 215.0,      # mean brightness above this = TOO_BRIGHT
    "contrast_min": 25.0,     # std of brightness below this = LOW_CONTRAST
    "ratio": 0.75,            # Lowe ratio test for feature matching
    "match_good": 40,         # RANSAC inliers needed for MATCH
    "match_ratio": 0.65,      # ...and inliers / good matches must be at least this
    "match_weak": 15,         # RANSAC inliers needed for WEAK
    "reuse_hash_dist": 6,     # dHash distance at or below this = same photo
    "reuse_inliers": 60,      # inliers needed to call two photos the same scene
    "reuse_ratio": 0.85,      # and inliers / good matches must be at least this
    "reuse_residual": 0.03,   # and the aligned photos must differ by less than this
    "reuse_candidates": 5,    # how many nearest stored photos get the feature check
    "diff_threshold": 0.30,   # per-pixel structure difference counted as "changed"
    "diff_possible": 0.010,   # changed area fraction -> POSSIBLE damage
    "diff_likely": 0.025,     # changed area fraction -> LIKELY damage
    "min_blob_frac": 0.004,   # ignore changed blobs smaller than this fraction
}


def _f(x):
    """numpy number -> plain float (so results can be turned into JSON)."""
    return round(float(x), 4)


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------
def decode_image(data):
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode the image")
    return img


def limit_width(img, max_width):
    """Shrink very large photos, never enlarge small ones."""
    return normalize(img, max_width) if img.shape[1] > max_width else img


def normalize(img, width):
    h, w = img.shape[:2]
    if w == width:
        return img
    scale = width / float(w)
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(img, (width, max(1, int(round(h * scale)))), interpolation=interp)


# ---------------------------------------------------------------------------
# Check 1: photo quality
# ---------------------------------------------------------------------------
def check_quality(img, cfg=CFG):
    h, w = img.shape[:2]
    small = normalize(img, cfg["norm_width"])
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blur = cv2.Laplacian(gray, cv2.CV_64F).var()
    brightness = gray.mean()
    contrast = gray.std()
    reasons = []
    if min(h, w) < cfg["min_side"]:
        reasons.append("LOW_RESOLUTION")
    if blur < cfg["blur_min"]:
        reasons.append("TOO_BLURRY")
    if brightness < cfg["dark_max"]:
        reasons.append("TOO_DARK")
    if brightness > cfg["bright_min"]:
        reasons.append("TOO_BRIGHT")
    if contrast < cfg["contrast_min"]:
        reasons.append("LOW_CONTRAST")
    return {"ok": not reasons, "blur": _f(blur), "brightness": _f(brightness),
            "contrast": _f(contrast), "reasons": reasons}


# ---------------------------------------------------------------------------
# Check 2: reused photo (hash first, then feature matching)
# ---------------------------------------------------------------------------
def dhash(img, size=8):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return format(value, "016x")


def hamming(h1, h2):
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


def match_images(img_a, img_b, cfg=CFG):
    """Find the same object in two photos using SIFT features + RANSAC.
    Returns inliers, ratio and H (maps points of img_a onto img_b)."""
    sift = cv2.SIFT_create(nfeatures=1500)
    ga = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
    ka, da = sift.detectAndCompute(ga, None)
    kb, db = sift.detectAndCompute(gb, None)
    empty = {"inliers": 0, "good": 0, "ratio": 0.0, "H": None}
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return empty
    pairs = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    good = [m for m, n in (p for p in pairs if len(p) == 2) if m.distance < cfg["ratio"] * n.distance]
    if len(good) < 8:
        return {**empty, "good": len(good)}
    pa = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    pb = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, mask = cv2.findHomography(pa, pb, cv2.RANSAC, 5.0)
    if H is None:
        return {**empty, "good": len(good)}
    inliers = int(mask.sum())
    return {"inliers": inliers, "good": len(good), "ratio": inliers / float(len(good)), "H": H}


def aligned_residual(img_a, img_b, H):
    """Line up photo A on photo B and measure how different they still are.
    A re-uploaded copy leaves almost nothing; a NEW photo of the same product leaves more.
    Brightness and contrast are normalised first, so a darker copy still counts as a copy."""
    hb, wb = img_b.shape[:2]
    warped = cv2.warpPerspective(img_a, H, (wb, hb))
    ink = cv2.warpPerspective((cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY) > 6).astype(np.uint8) * 255, H, (wb, hb))
    valid = cv2.erode(ink, np.ones((21, 21), np.uint8)) > 0
    ga = cv2.GaussianBlur(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY), (0, 0), 1.2).astype(np.float32)
    gb = cv2.GaussianBlur(cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY), (0, 0), 1.2).astype(np.float32)
    x, y = ga[valid], gb[valid]
    if x.size < 2000:
        return 1.0
    x = (x - x.mean()) / (x.std() + 1e-6)
    y = (y - y.mean()) / (y.std() + 1e-6)
    return float(np.abs(x - y).mean())


def check_reuse(img, known, load_image, cfg=CFG):
    """known: list of {"id": ..., "hash": ...} for photos stored earlier.
    load_image(id) returns the stored photo as an OpenCV image."""
    new_hash = dhash(img)
    result = {"hash": new_hash, "reused": False, "nearest_id": None,
              "hash_distance": None, "inliers": 0}
    ranked = sorted(known, key=lambda k: hamming(new_hash, k["hash"]))
    for cand in ranked[: cfg["reuse_candidates"]]:
        dist = hamming(new_hash, cand["hash"])
        if result["nearest_id"] is None:
            result["nearest_id"], result["hash_distance"] = cand["id"], dist
        if dist <= cfg["reuse_hash_dist"]:
            result.update(reused=True, nearest_id=cand["id"], hash_distance=dist)
            return result
        other = normalize(load_image(cand["id"]), cfg["norm_width"])
        mine = normalize(img, cfg["norm_width"])
        m = match_images(mine, other, cfg)
        if m["H"] is None or m["inliers"] < cfg["reuse_inliers"] or m["ratio"] < cfg["reuse_ratio"]:
            continue
        if aligned_residual(mine, other, m["H"]) <= cfg["reuse_residual"]:
            result.update(reused=True, nearest_id=cand["id"], hash_distance=dist,
                          inliers=m["inliers"])
            return result
    return result


# ---------------------------------------------------------------------------
# Check 3: is it the right product? (compare with the catalog reference photo)
# ---------------------------------------------------------------------------
def check_product(img, ref, cfg=CFG):
    m = match_images(img, ref, cfg)          # H maps the customer photo onto the reference
    if m["inliers"] >= cfg["match_good"] and m["ratio"] >= cfg["match_ratio"]:
        status = "MATCH"
    elif m["inliers"] >= cfg["match_weak"]:
        status = "WEAK"
    else:
        status = "NO_MATCH"
    return {"status": status, "inliers": m["inliers"], "ratio": _f(m["ratio"])}, m["H"]


# ---------------------------------------------------------------------------
# Check 4: damage hint (align photo to the reference, then look for changes)
# ---------------------------------------------------------------------------
def _structure_map(gray):
    """Edges/texture map that ignores most lighting changes."""
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    gray = cv2.GaussianBlur(gray, (7, 7), 0)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    mag = cv2.GaussianBlur(mag, (9, 9), 0)
    top = np.percentile(mag, 99) + 1e-6
    return np.clip(mag / top, 0, 1)


def check_damage(img, ref, H, cfg=CFG):
    rh, rw = ref.shape[:2]
    warped = cv2.warpPerspective(img, H, (rw, rh))
    valid = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), H, (rw, rh))
    valid = cv2.erode(valid, np.ones((25, 25), np.uint8))          # ignore the border
    diff = np.abs(_structure_map(cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)) -
                  _structure_map(cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)))
    changed = ((diff > cfg["diff_threshold"]) & (valid > 0)).astype(np.uint8) * 255
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    changed = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    area_valid = max(1, int((valid > 0).sum()))
    contours, _ = cv2.findContours(changed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions, flagged = [], 0
    for c in contours:
        a = cv2.contourArea(c)
        if a / area_valid >= cfg["min_blob_frac"]:
            x, y, w, h = cv2.boundingRect(c)
            regions.append([int(x), int(y), int(w), int(h)])
            flagged += a
    fraction = flagged / float(area_valid)
    if fraction >= cfg["diff_likely"]:
        level = "LIKELY"
    elif fraction >= cfg["diff_possible"]:
        level = "POSSIBLE"
    else:
        level = "NONE"
    return {"level": level, "fraction": _f(fraction), "regions": regions}, warped, diff


# ---------------------------------------------------------------------------
# Annotated picture for the customer and the human reviewer
# ---------------------------------------------------------------------------
def annotate(warped, diff, damage, label):
    left = warped.copy()
    for x, y, w, h in damage["regions"]:
        cv2.rectangle(left, (x, y), (x + w, y + h), (0, 0, 255), 3)
    heat = cv2.applyColorMap((np.clip(diff, 0, 1) * 255).astype(np.uint8), cv2.COLORMAP_JET)
    both = np.hstack([left, heat])
    bar = np.full((44, both.shape[1], 3), 30, np.uint8)
    cv2.putText(bar, label, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    out = np.vstack([bar, both])
    out = normalize(out, 1400)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes() if ok else b""


# ---------------------------------------------------------------------------
# The whole analysis in one call
# ---------------------------------------------------------------------------
def analyze(photo_bytes, reference_bytes, known_hashes, load_image, cfg=CFG):
    """Returns (result_dict, annotated_jpeg_bytes_or_empty)."""
    img = limit_width(decode_image(photo_bytes), cfg["norm_width"] * 2)   # keep some detail
    result = {"quality": check_quality(img, cfg), "reuse": None, "product": None,
              "damage": {"level": "UNKNOWN", "fraction": 0.0, "regions": []},
              "reason_codes": [], "evidence_score": 0}
    result["reuse"] = check_reuse(img, known_hashes, load_image, cfg)
    codes = list(result["quality"]["reasons"])
    if result["reuse"]["reused"]:
        codes.append("PHOTO_REUSED")

    annotated = b""
    if reference_bytes is None:
        result["product"] = {"status": "NO_REFERENCE", "inliers": 0, "ratio": 0.0}
        codes.append("NO_REFERENCE_IMAGE")
    else:
        ref = normalize(decode_image(reference_bytes), cfg["norm_width"])
        small = normalize(img, cfg["norm_width"])
        result["product"], H = check_product(small, ref, cfg)
        codes.append("PRODUCT_" + result["product"]["status"])
        if result["product"]["status"] == "MATCH" and H is not None:
            result["damage"], warped, diff = check_damage(small, ref, H, cfg)
            codes.append("DAMAGE_" + result["damage"]["level"])
            label = "product " + result["product"]["status"] + " | damage " + result["damage"]["level"]
            annotated = annotate(warped, diff, result["damage"], label)

    q = 1.0 if result["quality"]["ok"] else 0.0
    m = min(result["product"]["inliers"] / float(cfg["match_good"]), 1.0) \
        if result["product"]["status"] == "MATCH" else 0.0
    d = min(result["damage"]["fraction"] / cfg["diff_likely"], 1.0)
    score = 0 if result["reuse"]["reused"] else round(100 * (0.25 * q + 0.35 * m + 0.40 * d))
    result["evidence_score"] = int(score)
    result["reason_codes"] = codes
    return result, annotated
