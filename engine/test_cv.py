import time, cv2, numpy as np
from cv_core import *
from make_synth import *

ref = make_product(1)
other = make_product(2)
ref_b = to_bytes(ref)

store = {}                 # fake "database" of earlier photos: id -> image
def load(i): return store[i]
def known(): return [{"id": k, "hash": dhash(v)} for k, v in store.items()]

def run(name, img):
    t = time.time()
    res, ann = analyze(to_bytes(img), ref_b, known(), load)
    ms = int((time.time() - t) * 1000)
    print(f"{name:<28} q={res['quality']['ok']!s:<5} reuse={res['reuse']['reused']!s:<5} "
          f"prod={res['product']['status']:<9}/{res['product']['inliers']:<4} "
          f"dmg={res['damage']['level']:<8}{res['damage']['fraction']:<7} score={res['evidence_score']:<3} {ms}ms")
    return res, ann

good  = photo_of(ref, angle=5, scale=0.92, seed=11)
good2 = photo_of(ref, angle=-8, scale=0.85, bright=1.15, seed=12)
good3 = photo_of(ref, angle=3, scale=0.95, bright=0.85, noise=6, seed=13, jpeg=60)
dmg   = photo_of(add_damage(ref, "crumple", 3), angle=4, scale=0.9, seed=14)
dmg2  = photo_of(add_damage(ref, "crumple", 8), angle=-6, scale=0.9, bright=1.1, seed=15)
blur  = cv2.GaussianBlur(photo_of(ref, seed=16), (0, 0), 9)
dark  = np.clip(photo_of(ref, seed=17).astype(np.float32) * 0.18, 0, 255).astype(np.uint8)
wrong = photo_of(other, seed=18)

for n, im in [("intact photo 1", good), ("intact photo 2 (bright)", good2), ("intact photo 3 (dim+noisy)", good3),
              ("damaged photo 1", dmg), ("damaged photo 2", dmg2),
              ("blurry photo", blur), ("dark photo", dark), ("wrong product", wrong)]:
    run(n, im)

# reuse test: store the damaged photo, then upload a rotated + cropped + recompressed copy
store["E1"] = dmg
h, w = dmg.shape[:2]
copy = cv2.warpAffine(dmg[20:h-30, 30:w-20], cv2.getRotationMatrix2D((w/2, h/2), 9, 1.0), (w, h))
run("reused photo (rotated/crop)", copy)
run("exact re-upload", dmg)
run("new damaged (not reused)", dmg2)
