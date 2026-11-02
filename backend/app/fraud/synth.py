"""SYNTHETIC training data generator.

!! All data produced here is SYNTHETIC. Certificates are rendered programmatically and tampering
!! (retyping, clone-stamp, local blur/brightness edits) is simulated. Models trained on this data are
!! demonstration-grade and must be re-trained on real, labelled documents before production use.
"""
import io
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

FONT_DIR = Path("/usr/share/fonts")
_CANDIDATES = [
    "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSans-Regular.ttf",
    "LiberationSans-Bold.ttf", "LiberationMono-Regular.ttf", "DejaVuSans.ttf", "DejaVuSerif.ttf",
]
FONTS = [str(p) for n in _CANDIDATES for p in list(FONT_DIR.rglob(n))[:1]]

NAMES = ["Aarav Mehta", "Sofia Alvarez", "Liam O'Connor", "Mei Tanaka", "Noah Becker", "Amara Okafor", "Elena Petrova", "Daniel Kim", "Priya Nair", "Lucas Moreau"]
COURSES = ["Bachelor of Computer Science", "Master of Data Science", "Diploma in Cyber Security", "Bachelor of Engineering", "Certificate in Cloud Computing"]
UNIS = ["Northbridge University", "Eastgate Institute of Technology", "Crestview College", "Halden University of Sciences"]


def _font(rng, size, bold=None):
    if not FONTS:
        return ImageFont.load_default(size)
    return ImageFont.truetype(rng.choice(FONTS), size)


def render(rng: random.Random, name=None, grade=None):
    W, H = 900, 650
    bg = rng.choice([(255, 255, 255), (253, 249, 236), (247, 247, 250), (250, 244, 232)])
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, W - 20, H - 20], outline=(40, 50, 90), width=6)
    d.rectangle([34, 34, W - 34, H - 34], outline=(120, 130, 170), width=2)
    f_main = _font(rng, 26)
    uni = rng.choice(UNIS)
    d.text((W // 2, 100), uni.upper(), font=_font(rng, 38), fill=(25, 35, 85), anchor="mm")
    d.text((W // 2, 170), "Certificate of Achievement", font=_font(rng, 30), fill=(60, 60, 60), anchor="mm")
    d.text((W // 2, 245), "This is to certify that", font=f_main, fill=(70, 70, 70), anchor="mm")
    d.text((W // 2, 305), name or rng.choice(NAMES), font=_font(rng, 40), fill=(10, 10, 10), anchor="mm")
    d.text((W // 2, 375), "has successfully completed the " + rng.choice(COURSES), font=_font(rng, 24), fill=(70, 70, 70), anchor="mm")
    d.text((W // 2, 440), f"Grade: {grade or rng.choice(['A', 'B+', 'First Class', 'Distinction', 'B'])}", font=f_main, fill=(10, 10, 10), anchor="mm")
    d.text((120, 560), f"Date: {rng.randint(1,28):02d}/{rng.randint(1,12):02d}/{rng.randint(2015,2025)}", font=_font(rng, 22), fill=(60, 60, 60))
    d.text((W - 120, 560), f"Serial: {rng.randint(10**7, 10**8)}", font=_font(rng, 22), fill=(60, 60, 60), anchor="ra")
    return img


def _noise(img, sigma, rng):
    a = np.asarray(img, dtype=np.float32)
    a = a + np.random.RandomState(rng.randint(0, 2**31)).normal(0, sigma, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def _jpeg(img, q):
    b = io.BytesIO(); img.save(b, "JPEG", quality=q); b.seek(0)
    return Image.open(b).convert("RGB")


def _tamper(img, rng, base_noise):
    W, H = img.size
    for _ in range(rng.choice([1, 1, 2])):
        op = rng.choice(["retype", "retype", "clone", "blur", "brightness"])
        w, h = rng.randint(120, 380), rng.randint(30, 80)
        x, y = rng.randint(40, W - w - 40), rng.randint(220, H - h - 60)
        box = (x, y, x + w, y + h)
        if op == "retype":
            d = ImageDraw.Draw(img)
            bgc = img.getpixel((x + 2, y + 2))
            d.rectangle(box, fill=bgc)
            d.text((x + w // 2, y + h // 2), rng.choice(["Distinction", "First Class", "A+", "Dr. " + rng.choice(NAMES), str(rng.randint(10**7, 10**8))]),
                   font=_font(rng, rng.randint(22, 40)), fill=(10, 10, 10), anchor="mm")
        elif op == "clone":
            sx, sy = rng.randint(40, W - w - 40), rng.randint(40, H - h - 40)
            img.paste(img.crop((sx, sy, sx + w, sy + h)), (x, y))
        elif op == "blur":
            img.paste(img.crop(box).filter(ImageFilter.GaussianBlur(rng.uniform(0.8, 2.0))), (x, y))
        else:
            img.paste(ImageEnhance.Brightness(img.crop(box)).enhance(rng.uniform(0.85, 1.15)), (x, y))
        if rng.random() < 0.3:  # evasive: add matching noise to the edited patch
            img.paste(_noise(img.crop(box), base_noise, rng), (x, y))
    return img


def make_sample(seed: int, tampered: bool) -> bytes:
    rng = random.Random(seed)
    sigma = rng.uniform(0.0, 5)
    q1 = rng.randint(72, 95)
    img = _noise(render(rng), sigma, rng)
    if rng.random() < 0.5:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.2, 0.7)))
    img = _jpeg(img, q1)
    if tampered:
        img = _tamper(img, rng, sigma)
        q2 = q1 if rng.random() < 0.25 else rng.randint(70, 95)
        img = _jpeg(img, q2)
    elif rng.random() < 0.25:  # benign re-save so double-compression alone is not a giveaway
        img = _jpeg(img, rng.randint(70, 95))
    b = io.BytesIO(); img.save(b, "JPEG", quality=rng.randint(85, 95)); return b.getvalue()


def make_activity(n: int, seed: int = 7) -> np.ndarray:
    """SYNTHETIC normal verification-activity windows.
    columns: count_10m, count_1h, distinct_docs_1h, bad_ratio_24h, bad_count_1h, hour_sin, hour_cos, new_ip"""
    r = np.random.RandomState(seed)
    c10 = 1 + r.poisson(0.6, n)
    c1h = c10 + r.poisson(1.5, n)
    distinct = np.maximum(1, np.round(c1h * r.uniform(0.7, 1.0, n)))
    bad_ratio = r.beta(1, 14, n)
    bad_cnt = r.binomial(c1h, np.clip(bad_ratio, 0, 1))
    hour = np.clip(r.normal(13, 3.2, n), 0, 23.99)
    ang = 2 * np.pi * hour / 24
    new_ip = (r.rand(n) < 0.04).astype(float)
    return np.column_stack([c10, c1h, distinct, bad_ratio, bad_cnt, np.sin(ang), np.cos(ang), new_ip])
