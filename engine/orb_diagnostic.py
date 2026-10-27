import cv2
import numpy as np
from pathlib import Path

photo = cv2.imread("dataset/dev/P1_damaged.jpeg")
if photo is None:
    raise SystemExit("Could not read P1 damaged photo")

detector = cv2.ORB_create(nfeatures=3000)
kp1, des1 = detector.detectAndCompute(photo, None)
if des1 is None:
    raise SystemExit("No ORB descriptors in uploaded photo")

print("Reference ranking for real P1 damaged photo")
print("-" * 52)

for path in sorted(Path("dataset/references_optimized").glob("*_reference.jpg")):
    ref = cv2.imread(str(path))
    if ref is None:
        continue
    kp2, des2 = detector.detectAndCompute(ref, None)
    if des2 is None:
        print(f"{path.name}: no descriptors")
        continue

    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(des1, des2, k=2)
    good = [m for pair in pairs if len(pair) == 2
            for m, n in [pair] if m.distance < 0.75 * n.distance]
    inliers = 0
    if len(good) >= 4:
        src = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        inliers = int(mask.sum()) if mask is not None else 0

    print(f"{path.name:<24} good={len(good):<3} inliers={inliers}")
