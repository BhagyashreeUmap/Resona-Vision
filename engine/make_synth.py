"""Makes fake 'product photos' so cv_core can be tested without real photos."""
import cv2, numpy as np

def make_product(seed, w=900, h=650):
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), (205, 200, 195), np.uint8)
    cv2.rectangle(img, (120, 90), (w - 120, h - 90), (40 + seed * 25 % 120, 120, 200 - seed * 20 % 90), -1)
    for _ in range(90):                                   # printed pattern
        x, y = int(rng.integers(130, w - 140)), int(rng.integers(100, h - 100))
        r = int(rng.integers(6, 28))
        col = tuple(int(v) for v in rng.integers(0, 255, 3))
        if rng.random() < 0.5:
            cv2.circle(img, (x, y), r, col, -1 if rng.random() < 0.5 else 2)
        else:
            cv2.rectangle(img, (x, y), (x + r, y + r), col, 2)
    cv2.putText(img, "ACME KEYBOARD %d" % seed, (170, 170), cv2.FONT_HERSHEY_DUPLEX, 1.6, (255, 255, 255), 3)
    cv2.putText(img, "Model K-%04d" % (seed * 137), (170, 520), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (20, 20, 20), 2)
    return img

def photo_of(ref, angle=6, scale=0.9, bright=1.0, noise=3, seed=1, jpeg=80):
    """Pretend a customer photographed the product (different angle, light, noise)."""
    rng = np.random.default_rng(seed)
    h, w = ref.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    out = cv2.warpAffine(ref, M, (w, h), borderValue=(150, 150, 150))
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = src + rng.uniform(-18, 18, src.shape).astype(np.float32)
    out = cv2.warpPerspective(out, cv2.getPerspectiveTransform(src, dst), (w, h), borderValue=(150, 150, 150))
    out = np.clip(out.astype(np.float32) * bright + rng.normal(0, noise, out.shape), 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, jpeg])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

def add_damage(img, kind="crumple", seed=3):
    rng = np.random.default_rng(seed)
    out = img.copy()
    h, w = out.shape[:2]
    cx, cy = int(w * 0.55), int(h * 0.55)
    if kind == "crumple":
        for _ in range(26):                               # crease lines + shadows
            p1 = (cx + int(rng.integers(-110, 110)), cy + int(rng.integers(-90, 90)))
            p2 = (p1[0] + int(rng.integers(-90, 90)), p1[1] + int(rng.integers(-90, 90)))
            cv2.line(out, p1, p2, (25, 25, 25), int(rng.integers(2, 5)))
        pts = np.array([[cx - 70, cy - 40], [cx + 10, cy - 70], [cx + 85, cy - 10],
                        [cx + 60, cy + 70], [cx - 40, cy + 60]], np.int32)
        overlay = out.copy()
        cv2.fillPoly(overlay, [pts], (60, 60, 60))
        out = cv2.addWeighted(overlay, 0.55, out, 0.45, 0)
    return out

def to_bytes(img, q=88):
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
    return buf.tobytes()
