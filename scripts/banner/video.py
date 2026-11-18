"""Leitura do video, remocao das legendas e conversao em celulas (cor media por celula)."""
import subprocess
import numpy as np
import cv2
from PIL import Image

FW, FH = 960, 540                      # resolucao de trabalho (metade do 1080p)
COLS, ROWS = 100, 56
NFRAMES = 126                          # 4,2 s a 30 qps

# legendas gravadas na imagem: (primeiro quadro, ultimo + 1, caixa em 960x540, quadro limpo para copiar)
# "Is that it?" cai no escuro parado (copia do quadro 16); "Over already?" tem os raios passando
# por tras, entao e reconstruida quadro a quadro (copia=None).
SUBTITLES = [
    (17, 52, (420, 455, 545, 490), 16),
    (68, 110, (395, 455, 570, 492), None),
]


def read_frames(video, keep):
    """Devolve {indice: quadro RGB 960x540} so para os quadros pedidos."""
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={FW}:{FH}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = FW * FH * 3
    out, i = {}, 0
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        if i in keep:
            out[i] = np.frombuffer(buf, np.uint8).reshape(FH, FW, 3).copy()
        i += 1
    proc.wait()
    return out, i


def subtitle_mask(frames, a, b, box, grow=11):
    """O texto fica parado e os raios nao: e texto o pixel branco em 90% dos quadros do trecho."""
    x0, y0, x1, y1 = box
    cnt = np.zeros((FH, FW), int)
    for i in range(a, b):
        f = frames[i].astype(int)
        cnt += (f.min(axis=2) > 200) & ((f.max(axis=2) - f.min(axis=2)) < 40)
    m = np.zeros((FH, FW), np.uint8)
    m[y0:y1, x0:x1] = cnt[y0:y1, x0:x1] >= 0.9 * (b - a)
    return cv2.dilate(m * 255, np.ones((grow, grow), np.uint8))


def clean_subtitles(frames):
    """Apaga as legendas de todos os quadros (precisa de todos os quadros dos trechos)."""
    for a, b, box, ref in SUBTITLES:
        m = subtitle_mask(frames, a, b, box)
        sel = m > 0
        for i in range(a, b):
            if ref is not None:
                frames[i][sel] = frames[ref][sel]
            else:
                frames[i] = cv2.inpaint(frames[i], m, 6, cv2.INPAINT_TELEA)


def to_cells(rgb, cols=COLS, rows=ROWS, box=None):
    """Cor media de cada celula (float, 0..255), shape (rows, cols, 3)."""
    im = Image.fromarray(rgb)
    small = im.resize((cols, rows), Image.BOX, box=box)
    return np.asarray(small).astype(float)


def features(c):
    mx, mn = c.max(axis=2), c.min(axis=2)
    luma = (0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]) / 255
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    tone = 0.65 * (mx / 255) + 0.35 * luma
    return tone, luma, sat
