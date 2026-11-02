"""Real forensic feature extraction (ELA, noise, sharpness, OCR statistics, metadata)."""
import hashlib
import io
import os
import re

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # tesseract: one thread per process

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps

FEATURE_NAMES = [
    "ela_mean", "ela_std", "ela_hot_ratio", "ela_block_cv", "noise_block_cv",
    "sharpness_log", "sharpness_block_cv", "edge_density", "brightness_block_cv",
    "ocr_word_count_log", "ocr_mean_conf", "ocr_low_conf_ratio", "ocr_height_cv",
    "editor_meta_flag", "date_mismatch_flag", "incremental_updates",
]

FEATURE_DESC = {
    "ela_mean": "average JPEG error level (re-compression inconsistency)",
    "ela_std": "variation of JPEG error level across the page",
    "ela_hot_ratio": "share of regions with abnormally high error level (possible pasted/edited areas)",
    "ela_block_cv": "uneven error level between page regions",
    "noise_block_cv": "inconsistent sensor/scan noise between regions",
    "sharpness_log": "overall sharpness",
    "sharpness_block_cv": "uneven sharpness between regions (local blur/sharpening)",
    "edge_density": "density of edges",
    "brightness_block_cv": "uneven brightness between regions",
    "ocr_word_count_log": "amount of recognised text",
    "ocr_mean_conf": "average OCR confidence",
    "ocr_low_conf_ratio": "share of words with low OCR confidence",
    "ocr_height_cv": "inconsistent text height/font size",
    "editor_meta_flag": "file metadata indicates an image/PDF editor",
    "date_mismatch_flag": "modification date differs from creation date",
    "incremental_updates": "PDF contains incremental update sections",
}

EDITOR_RE = re.compile(r"photoshop|gimp|canva|pixlr|paint\.net|ilovepdf|smallpdf|sejda|pdfescape|acrobat pro|foxit phantom|illustrator|affinity|snapseed|lightroom", re.I)
STOP = {"the", "a", "of", "and", "to", "in", "is", "for"}


def load_image(data: bytes, mime: str) -> tuple[Image.Image, dict]:
    """Return RGB PIL image (first PDF page rasterised) and metadata flags."""
    meta = {"editor": 0, "date_mismatch": 0, "incremental": 0, "pdf_text": ""}
    if mime == "application/pdf" or data[:5] == b"%PDF-":
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        m = doc.metadata or {}
        blob = " ".join(str(m.get(k, "")) for k in ("producer", "creator"))
        meta["editor"] = int(bool(EDITOR_RE.search(blob)))
        cd, md = m.get("creationDate", ""), m.get("modDate", "")
        meta["date_mismatch"] = int(bool(cd and md and cd[2:16] != md[2:16]))
        meta["incremental"] = max(0, data.count(b"%%EOF") - 1)
        meta["pdf_text"] = "\n".join(p.get_text() for p in list(doc)[:3])
        pix = doc[0].get_pixmap(dpi=130)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img, meta
    img = Image.open(io.BytesIO(data))
    sw = " ".join(str(v) for k, v in (img.info or {}).items() if isinstance(v, (str, bytes)) and k.lower() in ("software", "comment"))
    try:
        exif = img.getexif()
        sw += " " + str(exif.get(305, ""))  # Software tag
    except Exception:
        pass
    meta["editor"] = int(bool(EDITOR_RE.search(sw)))
    img = ImageOps.exif_transpose(img).convert("RGB")
    return img, meta


def _blocks(arr: np.ndarray, size: int = 32):
    h, w = arr.shape[:2]
    for y in range(0, h - size + 1, size):
        for x in range(0, w - size + 1, size):
            yield arr[y:y + size, x:x + size]


def _cv(vals) -> float:
    vals = np.asarray(list(vals), dtype=float)
    return float(vals.std() / (vals.mean() + 1e-6)) if len(vals) else 0.0


def _ocr(img: Image.Image):
    g = img.convert("L")
    if g.width > 1600:
        g = g.resize((1600, int(g.height * 1600 / g.width)))
    d = pytesseract.image_to_data(g, output_type=pytesseract.Output.DICT, config="--psm 6")
    words, confs, heights = [], [], []
    for t, c, h in zip(d["text"], d["conf"], d["height"]):
        c = float(c)
        if t.strip() and c >= 0:
            words.append(t.strip()); confs.append(c); heights.append(h)
    return words, confs, heights


def visual_features(img: Image.Image) -> dict:
    img = img.copy()
    img.thumbnail((1000, 1000))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=90); buf.seek(0)
    re_img = Image.open(buf).convert("RGB")
    ela = np.abs(np.asarray(img, dtype=np.int16) - np.asarray(re_img, dtype=np.int16)).mean(axis=2)
    blocks = [b.mean() for b in _blocks(ela)] or [0.0]
    mu, sd = float(ela.mean()), float(ela.std())
    hot = float(np.mean(np.asarray(blocks) > (np.mean(blocks) + 3 * np.std(blocks) + 1e-6)))
    gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)
    resid = gray.astype(np.float32) - cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
    noise = [np.median(np.abs(b)) for b in _blocks(resid)]
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharp_blocks = [b.var() for b in _blocks(lap)]
    edges = cv2.Canny(gray, 80, 160)
    bright = [b.mean() for b in _blocks(gray.astype(np.float32))]
    return {
        "ela_mean": mu, "ela_std": sd, "ela_hot_ratio": hot, "ela_block_cv": _cv(blocks),
        "noise_block_cv": _cv(noise), "sharpness_log": float(np.log1p(lap.var())),
        "sharpness_block_cv": _cv(sharp_blocks), "edge_density": float((edges > 0).mean()),
        "brightness_block_cv": _cv(bright),
    }


def ocr_features(img: Image.Image) -> tuple[dict, list[str]]:
    words, confs, heights = _ocr(img)
    f = {
        "ocr_word_count_log": float(np.log1p(len(words))),
        "ocr_mean_conf": float(np.mean(confs)) if confs else 0.0,
        "ocr_low_conf_ratio": float(np.mean(np.asarray(confs) < 60)) if confs else 1.0,
        "ocr_height_cv": _cv(heights) if len(heights) > 3 else 0.0,
    }
    return f, words


def analyze(data: bytes, mime: str) -> dict:
    """Returns {features, words, phash, minhash, meta}."""
    img, meta = load_image(data, mime)
    f = visual_features(img)
    of, words = ocr_features(img)
    f.update(of)
    f.update({"editor_meta_flag": float(meta["editor"]), "date_mismatch_flag": float(meta["date_mismatch"]),
              "incremental_updates": float(min(meta["incremental"], 5))})
    text_words = re.findall(r"[a-z0-9]+", (meta["pdf_text"] or " ".join(words)).lower())
    return {"features": f, "words": text_words, "phash": dhash(img), "minhash": minhash(text_words)}


def vector(f: dict) -> np.ndarray:
    return np.array([f[n] for n in FEATURE_NAMES], dtype=float)


# ---- privacy-preserving similarity fingerprints (no plaintext stored) ----
def dhash(img: Image.Image) -> str:
    g = np.asarray(img.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def dhash_similarity(a: str, b: str) -> float:
    return 1 - bin(int(a, 16) ^ int(b, 16)).count("1") / 64


_N_PERM = 128
_MASK = (1 << 61) - 1
_rng = np.random.RandomState(1337)
_A = [int(x) | 1 for x in _rng.randint(1, 2**31 - 1, _N_PERM)]
_B = [int(x) for x in _rng.randint(0, 2**31 - 1, _N_PERM)]


def minhash(words: list[str]) -> list[int] | None:
    toks = [w for w in words if w not in STOP]
    shingles = {" ".join(toks[i:i + 2]) for i in range(max(1, len(toks) - 1))} if len(toks) >= 2 else set()
    if len(shingles) < 3:
        return None
    hs = [int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big") & _MASK for s in shingles]
    return [min(((a * h + b) & _MASK) for h in hs) for a, b in zip(_A, _B)]


def minhash_similarity(a: list[int] | None, b: list[int] | None) -> float:
    if not a or not b:
        return 0.0
    return float(np.mean(np.asarray(a) == np.asarray(b)))
