"""Recorte do ceu (o fundo atras dele), quadro a quadro.

Duas fases, porque a camera se move ate o quadro ~89 e depois fica parada (do 97 ao 125 o quadro e
identico ao final):
- Quadro final (e os parados): GrabCut no lado esquerdo, com o ombro (cacos de cristal e armadura) e o
  visor marcados a mao como personagem, mais o ceu azul-petroleo entre as mechas atras da cabeca, pixel a
  pixel, para as pontas do cabelo continuarem espetadas.
- Antes disso: ceu so onde e certamente ceu (o azul-petroleo e a nevoa quente), e nunca em pele, visor,
  tinta vermelha ou miolo de raio.
"""
import numpy as np
import cv2

import video as bf

# coordenadas no quadro 960x540
VISOR = [(250, 0), (345, 0), (350, 150), (330, 200), (345, 265), (290, 275), (262, 230), (245, 120)]
OMBRO = [(0, 420), (25, 395), (145, 283), (160, 300), (330, 266), (380, 266), (380, 540), (0, 540)]
PARADO = 89                     # a partir daqui a composicao e a final (ate 1 a 3 celulas no 89-96)

# antes da camera parar: o ceu de cada desenho (o anime repete o desenho ate o proximo quadro-chave),
# desenhado a mao sobre o quadro clareado. E o canto de cima a esquerda, com as faiscas, que cresce
# enquanto ele levanta a cabeca; para a direita fica o visor, para baixo o ombro.
CEU_CHAVES = {
    0:  [(0, 0), (150, 0), (95, 22), (0, 62)],
    67: [(0, 0), (50, 0), (40, 60), (25, 120), (0, 130)],
    70: [(0, 0), (60, 0), (50, 60), (30, 110), (0, 120)],
    73: [(0, 0), (70, 0), (60, 120), (80, 250), (0, 290)],
    75: [(0, 0), (100, 0), (90, 130), (120, 250), (0, 300)],
    78: [(0, 0), (150, 0), (130, 120), (150, 230), (0, 280)],
    81: [(0, 0), (170, 0), (130, 130), (160, 230), (0, 280)],
    82: [(0, 0), (200, 0), (170, 100), (170, 230), (0, 290)],
    83: [(0, 0), (200, 0), (170, 120), (180, 260), (0, 300)],
    86: [(0, 0), (200, 0), (180, 130), (200, 270), (0, 310)],
}


def blue_sky_px(rgb):
    """Azul-petroleo do ceu: B acima de G e bem acima de R (as pontas do cabelo tem B ~ G)."""
    a = rgb.astype(np.int32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = a.max(axis=2)
    sky = (b - g >= 3) & (b - r >= 12) & (mx >= 15) & (mx <= 100)
    return cv2.morphologyEx(sky.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)) > 0


def never_sky_px(rgb):
    """Pele, visor e destaques (claro e nao quente) e tinta vermelha: sempre ele."""
    L = rgb.astype(np.float32).mean(axis=2) / 255
    r, g, b = [rgb[..., k].astype(np.float32) for k in range(3)]
    warm = (r + g) / 2 - b
    return ((L > 0.45) & (warm < 7)) | ((r > g * 1.3) & (r > 90))


def to_cells(px, frac=0.5):
    return cv2.resize(px.astype(np.float32), (bf.COLS, bf.ROWS), interpolation=cv2.INTER_AREA) >= frac


def final_sky(rgb):
    H, W = rgb.shape[:2]
    L = rgb.astype(np.float32).mean(axis=2) / 255
    r, g, b = [rgb[..., k].astype(np.float32) for k in range(3)]
    warm = (r + g) / 2 - b
    yy, xx = np.mgrid[0:H, 0:W]
    m = np.full((H, W), cv2.GC_PR_FGD, np.uint8)
    m[(xx < 330) & (yy < 300)] = cv2.GC_PR_BGD
    m[(xx < 200) & (yy < 230) & (L > 0.35) & (warm > 5)] = cv2.GC_BGD
    m[(xx < 40) & (yy < 330)] = cv2.GC_BGD
    m[never_sky_px(rgb) & (xx > 240)] = cv2.GC_FGD
    m[L < 0.06] = cv2.GC_FGD
    m[xx > 420] = cv2.GC_FGD                                  # o lado direito sai do GrabCut (abaixo)
    poly = np.zeros((H, W), np.uint8)
    cv2.fillPoly(poly, [np.array(VISOR, np.int32)], 1)
    cv2.fillPoly(poly, [np.array(OMBRO, np.int32)], 1)
    m[poly > 0] = cv2.GC_FGD
    m[(xx >= 325) & (xx < 400) & (yy > 140) & (yy < 300)] = cv2.GC_FGD
    cv2.setRNGSeed(0)
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    cv2.grabCut(np.ascontiguousarray(rgb[..., ::-1]), m, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    left = (m == cv2.GC_BGD) | (m == cv2.GC_PR_BGD)
    left = cv2.medianBlur(to_cells(left).astype(np.uint8) * 255, 3) > 0
    # atras da cabeca: so o azul do ceu, celula a celula (sem suavizar, para as pontas ficarem)
    right = to_cells(blue_sky_px(rgb) & (xx > 650) & (yy < 320), 0.45)
    return left | right


def frame_sky(rgb, i):
    """Antes da camera parar: o contorno do desenho, sem tinta vermelha nem olho."""
    key = max(k for k in CEU_CHAVES if k <= i)
    poly = np.zeros(rgb.shape[:2], np.uint8)
    cv2.fillPoly(poly, [np.array(CEU_CHAVES[key], np.int32)], 1)
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    red = (r > g * 1.3) & (r > 90)
    return to_cells(poly > 0) & ~to_cells(red, 0.25)


def sky_masks(frames):
    """Ceu por celula (ROWS, COLS) em cada quadro."""
    n = len(frames)
    fin = final_sky(frames[n - 1])
    out = []
    for i in range(n):
        if i >= PARADO:
            prot = to_cells(never_sky_px(frames[i]), 0.25)
            out.append(fin & ~prot)
        else:
            out.append(frame_sky(frames[i], i))
    return out
