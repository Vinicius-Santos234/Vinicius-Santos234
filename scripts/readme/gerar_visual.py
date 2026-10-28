"""Gera as pecas do README no tema novo (SVGs em tema/) e o README.md que as junta.

uso: python scripts/readme/gerar_visual.py MOSAICO.svg PASTA_DO_REPOSITORIO [URL_DAS_IMAGENS]
     MOSAICO.svg sai de scripts/banner/gerar_banner.py. Sem URL, o README aponta para ./tema/
     (bom para previa local); no perfil, use o raw do repositorio.
     A secao ATIVIDADE (tema/atividade.svg) vem de gerar_atividade.py, que o workflow roda todo dia.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tema as t
from tema import Fontes, chanfro, icone, icone_marca, losango, texto

W = 840
USER = 'Vinicius-Santos234'

BIO = [
    [("Desenvolvedor web focado em", 0), ("React / Next.js", 1), ("e em aplicar", 0), ("IA", 1),
     ("em coisas que rodam de verdade — assistente de voz, visão computacional e agentes que trabalham sozinhos.", 0)],
    [("Estudante de", 0), ("Desenvolvimento de Software Multiplataforma", 1), ("na", 0), ("Fatec", 1),
     ("(4º semestre).", 0)],
]

TECNOLOGIAS = [
    ("FRONT-END", [("JavaScript", "javascript"), ("React", "react"), ("Next.js", "nextdotjs"), ("Vite", "vite"),
                   ("Tailwind", "tailwindcss"), ("CSS", "css3")]),
    ("BACK-END E DADOS", [("Node.js", "nodedotjs"), ("Python", "python"), ("Supabase", "supabase"),
                          ("PostgreSQL", "postgresql")]),
    ("MOBILE, TESTES E DEPLOY", [("Flutter", "flutter"), ("Dart", "dart"), ("Vitest", "vitest"), ("Git", "git"),
                                 ("Vercel", "vercel")]),
]

IA = [
    ("voz", "ASSISTENTE DE VOZ", "Assistente de voz para o Windows em português, offline por padrão, com IA opcional.",
     "PYTHON · CLAUDE", "ev-assistente-desktop"),
    ("visao", "VISÃO COMPUTACIONAL", "Controle de música por gestos da mão, pela webcam.",
     "PYTHON · MEDIAPIPE · OPENCV", "spotify-por-gestos"),
    ("agente", "AGENTE 24 HORAS", "Agente de IA rodando sem parar num servidor Linux.",
     "NODE.JS · LINUX", "agente-ia-servidor"),
]

PROJETOS = [
    ("XERETA", "Um gato no topo da tela que fica de olho no Claude Code e deixa aprovar permissões sem voltar ao terminal.",
     "TAURI 2 · JAVASCRIPT", "xereta"),
    ("PS5 PELA REDE", "Ver se o PS5 está ligado ou em repouso, e ligar ou pôr em repouso, direto do terminal.",
     "NODE.JS", "ps5-pela-rede"),
    ("HOMEM-ARANHA: UM NOVO DIA", "Site para aprender animações com rolagem e layout, com o tema do novo filme.",
     "JAVASCRIPT", "homem-aranha-um-novo-dia"),
    ("SEGUNDO CÉREBRO", "Modelo de vault do Obsidian com skills do Claude Code que transformam sessões em conhecimento.",
     "OBSIDIAN · CLAUDE CODE", "segundo-cerebro-claude-code"),
]

CONTATO = [
    ("email", "E-MAIL", "mailto:viniciusgsantos234@gmail.com"),
    ("linkedin", "LINKEDIN", "https://www.linkedin.com/in/vinicius-santos-26a4b5361/"),
    ("github", "GITHUB", f"https://github.com/{USER}"),
]

MENU = [("sobre", "SOBRE"), ("tecnologias", "TECNOLOGIAS"), ("ia", "IA"), ("projetos", "PROJETOS"),
        ("atividade", "ATIVIDADE"), ("contato", "CONTATO")]
MENU_W = 134


def regua(x, y0, y1, passo=12):
    """Marquinhas na borda, como a regua do lado esquerdo da tela do jogo."""
    return ''.join(f'<path d="M{x} {y} h{5 if (y - y0) % (passo * 4) == 0 else 2.5}" stroke="{t.VERMELHO_APAGADO}"/>'
                   for y in range(int(y0), int(y1), passo))


# ------------------------------------------------------------------ banner com moldura
def banner(caminho_mosaico):
    src = open(caminho_mosaico, encoding='utf-8').read()
    estilo = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
    defs = re.search(r'<defs>(.*?)</defs>', src, re.S).group(1)
    corpo = src[src.index('</defs>') + len('</defs>'):src.rindex('</svg>')]
    f = Fontes()
    H = 520
    p = [
        f'<path d="{chanfro(6, 6, W - 12, H - 12, 16)}" fill="none" stroke="{t.VERMELHO}" stroke-width="1.5"/>',
        texto(28, 38, 'VINICIUS SANTOS', 24, 700, t.CIANO, f, espaco=4),
        texto(W - 26, 36, 'DESENVOLVEDOR WEB · IA', 14, 600, t.VERMELHO, f, espaco=2.5, ancora='end'),
        f'<path d="M22 48 H{W - 22}" stroke="{t.VERMELHO_APAGADO}"/>',
        f'<path d="M22 48 H120" stroke="{t.VERMELHO}" stroke-width="2"/>',
        ''.join(f'<rect x="{W - 120 + i * 9}" y="3" width="6" height="6" fill="{t.VERMELHO if i == 0 else t.VERMELHO_APAGADO}"/>'
                for i in range(4)),
        regua(1, 70, 500),
        f'<g transform="translate(20 56)">{corpo}</g>',
        f'<path d="M20 {H - 10} h60" stroke="{t.CIANO_APAGADO}" stroke-width="2"/>',
    ]
    return t.svg(W, H, ''.join(p), f, 'Vinicius Santos — mosaico animado (fan art de Cyberpunk: Edgerunners 2)',
                 extra_css=estilo).replace('</style>', f'</style><defs>{defs}</defs>', 1)


# ------------------------------------------------------------------ menu (botoes clicaveis)
def botao(nome_icone, rotulo, w=160, h=46, selecionado=False, marca=None):
    f = Fontes()
    tam, esp = 15, 1.6
    while t.largura(rotulo, tam, 600, esp) > w - 54 and tam > 12:
        tam -= 0.5
        esp = max(0.8, esp - 0.1)
    fundo = t.SELECIONADO if selecionado else t.PAINEL
    borda = t.VERMELHO if selecionado else '#9a2d2a'
    ic = (icone_marca(marca, 17, 16, 14, t.CIANO) if marca else icone(nome_icone, 17, 16, 14, t.CIANO, 1.4))
    p = [
        f'<path d="{chanfro(1, 1, w - 2, h - 2, 9, "tl")}" fill="{fundo}" stroke="{borda}" stroke-width="1.2"/>',
        losango(24, h / 2, 13, t.CIANO_APAGADO, ic),
        texto(44, h / 2 + 5.5, rotulo, tam, 600, t.CIANO, f, espaco=esp),
    ]
    if selecionado:
        p.append(f'<rect x="{w - 14}" y="{h / 2 - 5}" width="8" height="10" fill="none" stroke="{t.CIANO}"/>')
    return t.svg(w, h, ''.join(p), f, 'IA' if rotulo == 'IA' else rotulo.capitalize())


# ------------------------------------------------------------------ titulo de secao
def titulo(nome_icone, rotulo, numero, f=None, y=0):
    proprio = f is None
    f = f or Fontes()
    tw = t.largura(rotulo, 20, 700, 3)
    p = [
        losango(24, y + 28, 14, t.CIANO, icone(nome_icone, 16.5, y + 20.5, 15, t.CIANO, 1.5)),
        texto(50, y + 35, rotulo, 20, 700, t.CIANO, f, espaco=3),
        f'<path d="M{50 + tw + 16:g} {y + 28} H{W - 40}" stroke="{t.VERMELHO}"/>',
        f'<path d="M{W - 40} {y + 28} l8 -8 H{W - 14}" fill="none" stroke="{t.VERMELHO}"/>',
        texto(W - 16, y + 44, numero, 11, 600, t.VERMELHO_APAGADO, f, espaco=1, ancora='end'),
    ]
    if proprio:
        return t.svg(W, 54, ''.join(p), f, rotulo.capitalize())
    return ''.join(p)


# ------------------------------------------------------------------ sobre
def linhas_ricas(paragrafo, tam, maximo):
    """Quebra um paragrafo com trechos em destaque; devolve linhas de [(palavra, destaque)]."""
    palavras = [(w, d) for trecho, d in paragrafo for w in trecho.split()]
    linhas, atual = [], []
    for w, d in palavras:
        tentativa = ' '.join(x for x, _ in atual + [(w, d)])
        if atual and t.largura(tentativa, tam, 600) > maximo:
            linhas.append(atual)
            atual = []
        atual.append((w, d))
    if atual:
        linhas.append(atual)
    return linhas


def sobre():
    f = Fontes()
    tam, lh = 19, 28
    blocos = [linhas_ricas(par, tam, W - 80) for par in BIO]
    n = sum(len(b) for b in blocos)
    H = 54 + 24 + n * lh + 14 * (len(blocos) - 1) + 22
    p = [titulo('sobre', 'SOBRE', '01', f),
         f'<path d="{chanfro(6, 62, W - 12, H - 68, 12)}" fill="{t.PAINEL}" stroke="{t.VERMELHO_APAGADO}"/>',
         f'<path d="M6 74 V{H - 18}" stroke="{t.CIANO_APAGADO}" stroke-width="2"/>']
    y = 62 + 34
    for b in blocos:
        for linha in b:
            spans = []
            for k, (w, d) in enumerate(linha):
                f.usar(w + ' ', 600 if d else 500)
                cor = t.CIANO_CLARO if d else t.TEXTO
                peso = 600 if d else 500
                spans.append(f'<tspan fill="{cor}" font-weight="{peso}">{t.esc(w)}{" " if k < len(linha) - 1 else ""}</tspan>')
            p.append(f'<text x="32" y="{y}" font-family="R,\'Rajdhani\',sans-serif" font-size="{tam}">{"".join(spans)}</text>')
            y += lh
        y += 14
    return t.svg(W, H, ''.join(p), f, 'Sobre: ' + ' '.join(tr for par in BIO for tr, _ in par))


# ------------------------------------------------------------------ tecnologias (itens em slots)
def tecnologias():
    f = Fontes()
    sw, sh, gap = 100, 92, 12
    y = 70
    p = [titulo('tecnologias', 'TECNOLOGIAS', '02', f)]
    for grupo, itens in TECNOLOGIAS:
        p.append(texto(30, y + 10, grupo, 13, 700, t.VERMELHO, f, espaco=2.2))
        lw = t.largura(grupo, 13, 700, 2.2)
        p.append(f'<path d="M{30 + lw + 12:g} {y + 6} H{W - 30}" stroke="{t.VERMELHO_APAGADO}"/>')
        y += 22
        for i, (nome, slug) in enumerate(itens):
            x = 30 + i * (sw + gap)
            p.append(f'<path d="{chanfro(x, y, sw, sh, 9, "tl")}" fill="#0e0b10" stroke="#3b1b1d"/>')
            p.append(f'<path d="M{x + sw - 14} {y + sh - 1} h13 v-13" fill="none" stroke="{t.VERMELHO}"/>')
            p.append(icone_marca(slug, x + sw / 2 - 16, y + 14, 32, t.CIANO))
            p.append(texto(x + sw / 2, y + 76, nome, 14, 600, t.CIANO_CLARO, f, ancora='middle', espaco=0.5))
        y += sh + 22
    H = y + 6
    nomes = ', '.join(n for _, itens in TECNOLOGIAS for n, _ in itens)
    return t.svg(W, H, ''.join(p), f, 'Tecnologias: ' + nomes)


# ------------------------------------------------------------------ cartoes (IA e projetos)
def cartao_ia(nome_icone, rotulo, desc, tags, w=272, altura=None):
    f = Fontes()
    linhas = t.quebrar(desc, 14, w - 32)
    H = altura or (110 + 22 + len(linhas) * 17 + 34)
    p = [
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3a1013"/>'
        f'<stop offset="1" stop-color="{t.PAINEL}"/></linearGradient></defs>',
        f'<path d="{chanfro(1, 1, w - 2, H - 2, 12)}" fill="{t.PAINEL}" stroke="{t.VERMELHO}" stroke-width="1.2"/>',
        f'<path d="{chanfro(8, 8, w - 16, 84, 8, "tl")}" fill="url(#g)" stroke="{t.VERMELHO_APAGADO}"/>',
        losango(w / 2, 50, 30, t.CIANO_APAGADO, icone(nome_icone, w / 2 - 16, 34, 32, t.CIANO, 1.6)),
        texto(16, 120, rotulo, 17, 700, t.CIANO, f, espaco=1.5),
    ]
    for k, ln in enumerate(linhas):
        p.append(texto(16, 142 + k * 17, ln, 14, 500, t.TEXTO, f))
    p.append(texto(16, H - 16, tags, 12, 600, t.VERMELHO, f, espaco=1.2))
    p.append(f'<path d="M{w - 30} {H - 26} l10 -10 M{w - 27} {H - 36} h7 v7" fill="none" stroke="{t.CIANO_APAGADO}" stroke-width="1.5"/>')
    return t.svg(w, H, ''.join(p), f, f'{rotulo.capitalize()}: {desc}')


def cartao_projeto(rotulo, desc, tags, w=412, altura=None):
    f = Fontes()
    linhas = t.quebrar(desc, 14, w - 90)
    H = altura or (30 + 22 + len(linhas) * 17 + 40)
    p = [
        f'<path d="{chanfro(1, 1, w - 2, H - 2, 12)}" fill="{t.PAINEL}" stroke="{t.VERMELHO}" stroke-width="1.2"/>',
        losango(34, 36, 16, t.CIANO_APAGADO, icone('projetos', 25, 27, 18, t.CIANO, 1.5)),
        texto(64, 40, rotulo, 17, 700, t.CIANO, f, espaco=1.5),
    ]
    for k, ln in enumerate(linhas):
        p.append(texto(64, 62 + k * 17, ln, 14, 500, t.TEXTO, f))
    p.append(texto(64, H - 16, tags, 12, 600, t.VERMELHO, f, espaco=1.2))
    p.append(f'<path d="M{w - 30} {H - 26} l10 -10 M{w - 27} {H - 36} h7 v7" fill="none" stroke="{t.CIANO_APAGADO}" stroke-width="1.5"/>')
    return t.svg(w, H, ''.join(p), f, f'{rotulo.capitalize()}: {desc}')


def rodape():
    f = Fontes()
    p = [f'<path d="M6 14 H{W - 6}" stroke="{t.VERMELHO_APAGADO}"/>',
         ''.join(f'<rect x="{6 + i * 9}" y="20" width="6" height="3" fill="{t.VERMELHO if i < 2 else t.VERMELHO_APAGADO}"/>'
                 for i in range(6)),
         texto(W - 8, 30, 'VINICIUS SANTOS · 2026', 11, 600, t.VERMELHO_APAGADO, f, espaco=2, ancora='end')]
    return t.svg(W, 38, ''.join(p), f, 'Fim')


# ------------------------------------------------------------------ montagem
def main(mosaico, saida, base='./tema/'):
    pasta = os.path.join(saida, 'tema')
    os.makedirs(pasta, exist_ok=True)
    arquivos = {}

    def salvar(nome, conteudo):
        with open(os.path.join(pasta, nome), 'w', encoding='utf-8') as fh:
            fh.write(conteudo)
        arquivos[nome] = len(conteudo.encode())

    salvar('banner.svg', banner(mosaico))
    for i, (ancora, rotulo) in enumerate(MENU):
        salvar(f'menu-{ancora}.svg', botao(ancora, rotulo, w=MENU_W, selecionado=(i == 0)))
    salvar('sobre.svg', sobre())
    salvar('tecnologias.svg', tecnologias())
    salvar('titulo-ia.svg', titulo('ia', 'IA', '03'))
    alt_ia = max(110 + 22 + len(t.quebrar(d, 14, 272 - 32)) * 17 + 34 for _, _, d, _, _ in IA)
    for ic, rot, desc, tags, repo in IA:
        salvar(f'ia-{ic}.svg', cartao_ia(ic, rot, desc, tags, altura=alt_ia))
    salvar('titulo-projetos.svg', titulo('projetos', 'PROJETOS', '04'))
    alt = max(30 + 22 + len(t.quebrar(d, 14, 412 - 90)) * 17 + 40 for _, d, _, _ in PROJETOS)
    for rot, desc, tags, repo in PROJETOS:
        salvar(f'projeto-{repo}.svg', cartao_projeto(rot, desc, tags, altura=alt))
    salvar('titulo-contato.svg', titulo('contato', 'CONTATO', '06'))
    for ic, rot, link in CONTATO:
        salvar(f'contato-{ic}.svg', botao(ic, rot, w=200, marca='github' if ic == 'github' else None))
    salvar('rodape.svg', rodape())

    def img(nome, largura, alt):
        return f'<img src="{base}{nome}" width="{largura}" alt="{alt}">'

    md = ['<p align="center">', '  ' + img('banner.svg', '100%', 'Vinicius Santos — mosaico animado (fan art de Cyberpunk: Edgerunners 2)'),
          '</p>', '', '<p align="center">']
    md += [f'  <a href="#{a}">{img(f"menu-{a}.svg", MENU_W, "IA" if a == "ia" else r.capitalize())}</a>' for a, r in MENU]
    md += ['</p>', '']
    bio = ' '.join(tr for par in BIO for tr, _ in par)
    md += ['<a name="sobre"></a>', '<p align="center">', '  ' + img('sobre.svg', '100%', 'Sobre: ' + bio), '</p>', '']
    nomes = ', '.join(n for _, itens in TECNOLOGIAS for n, _ in itens)
    md += ['<a name="tecnologias"></a>', '<p align="center">', '  ' + img('tecnologias.svg', '100%', 'Tecnologias: ' + nomes),
           '</p>', '']
    md += ['<a name="ia"></a>', '<p align="center">', '  ' + img('titulo-ia.svg', '100%', 'IA') + '<br>']
    md += [f'  <a href="https://github.com/{USER}/{repo}">{img(f"ia-{ic}.svg", "32%", rot.capitalize().replace("Ia", "IA") + ": " + desc)}</a>'
           for ic, rot, desc, tags, repo in IA]
    md += ['</p>', '', '<a name="projetos"></a>', '<p align="center">',
           '  ' + img('titulo-projetos.svg', '100%', 'Projetos') + '<br>']
    md += [f'  <a href="https://github.com/{USER}/{repo}">{img(f"projeto-{repo}.svg", "49%", rot.capitalize() + ": " + desc)}</a>'
           for rot, desc, tags, repo in PROJETOS]
    md += ['</p>', '', '<a name="atividade"></a>', '<p align="center">',
           '  ' + img('atividade.svg', '100%', 'Atividade (gerada todo dia)'), '</p>', '']
    md += ['<a name="contato"></a>', '<p align="center">',
           '  ' + img('titulo-contato.svg', '100%', 'Contato') + '<br>']
    md += [f'  <a href="{link}">{img(f"contato-{ic}.svg", 200, rot.capitalize())}</a>' for ic, rot, link in CONTATO]
    md += ['</p>', '', '<p align="center">', '  ' + img('rodape.svg', '100%', ''), '</p>', '']
    with open(os.path.join(saida, 'README.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(md))
    total = sum(arquivos.values())
    print(f"{len(arquivos)} SVGs, {total / 1024:.0f} KB no total; sem o banner: {(total - arquivos['banner.svg']) / 1024:.0f} KB")


if __name__ == '__main__':
    main(*sys.argv[1:4])
