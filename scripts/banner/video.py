"""Leitura do video, remocao de legenda e conversao em celulas (cor media por celula)."""
import subprocess
import numpy as np
import cv2
from PIL import Image

FW, FH = 960, 540                      # resolucao de trabalho (metade do 1080p)
COLS, ROWS = 100, 56
CUT1, CUT2, NFRAMES = 37, 82, 150      # primeiro quadro da cena 2, da cena 3, total

# legenda de baixo (cenas 1 e 2), em coordenadas de 960x540
SUB_BOTTOM = (370, 425, 593, 490)

# cena 3: recorte visivel (x 250..810, y 215..528.6) e a faixa larga que vira o fundo
S3_CELL = 5.6
S3_Y0 = 215.0
S3_X0 = 250.0 - 44 * S3_CELL           # a faixa comeca 44 colunas antes do recorte
S3_STRIP_COLS = 170
S3_VIEW_COL = 44                       # coluna da faixa onde o recorte comeca


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


def subtitle_mask(rgb, box, grow=13):
    x0, y0, x1, y1 = box
    a = rgb.astype(int)
    white = (a.min(axis=2) > 200) & ((a.max(axis=2) - a.min(axis=2)) < 40)
    mask = np.zeros(white.shape, np.uint8)
    mask[y0:y1, x0:x1] = white[y0:y1, x0:x1]
    if mask.sum() < 30:
        return None
    return cv2.dilate(mask * 255, np.ones((grow, grow), np.uint8)) > 0


def clean_scene1(frames):
    """Cena 1: o quadro 0 nao tem legenda; o resto pega a regiao da legenda dele."""
    base = frames[0]
    for i, f in frames.items():
        if i == 0 or i >= CUT1:
            continue
        m = subtitle_mask(f, SUB_BOTTOM)
        if m is not None:
            f[m] = base[m]


def inpaint_subtitle(rgb, box):
    m = subtitle_mask(rgb, box)
    if m is None:
        return rgb
    return cv2.inpaint(rgb, m.astype(np.uint8) * 255, 8, cv2.INPAINT_TELEA)


def to_cells(rgb, cols, rows, box=None):
    """Cor media de cada celula (float, 0..255), shape (rows, cols, 3)."""
    im = Image.fromarray(rgb)
    small = im.resize((cols, rows), Image.BOX, box=box)
    return np.asarray(small).astype(float)


def scene3_strip_box():
    return (S3_X0, S3_Y0, S3_X0 + S3_STRIP_COLS * S3_CELL, S3_Y0 + ROWS * S3_CELL)


def features(c):
    mx, mn = c.max(axis=2), c.min(axis=2)
    luma = (0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]) / 255
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    tone = 0.65 * (mx / 255) + 0.35 * luma
    return tone, luma, sat
