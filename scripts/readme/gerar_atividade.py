"""Gera tema/atividade.svg: o grafico de contribuicoes do ano em mosaico + o que esta em andamento.

O total e o mesmo do grafico do perfil (contributionCalendar.totalContributions), que ja
inclui a quantidade de contribuicoes em repositorios privados. Do que esta em andamento so
entram repositorios publicos.

uso: GITHUB_TOKEN=... python scripts/readme/gerar_atividade.py USUARIO tema/atividade.svg
"""
import datetime as dt
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tema as t
from tema import Fontes, texto

W = 840
MESES = 'jan fev mar abr mai jun jul ago set out nov dez'.split()
DIAS = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado']
NIVEL = {'NONE': 0, 'FIRST_QUARTILE': 1, 'SECOND_QUARTILE': 2, 'THIRD_QUARTILE': 3, 'FOURTH_QUARTILE': 4}
COR_NIVEL = ['#1f3b3e', t.CIANO_APAGADO, '#3fb6be', t.CIANO, t.CIANO_CLARO]


def api(token, url=None, graphql=None):
    req = urllib.request.Request(
        url or 'https://api.github.com/graphql',
        data=json.dumps({'query': graphql}).encode() if graphql else None,
        headers={'Authorization': f'bearer {token}', 'User-Agent': 'perfil-atividade',
                 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def coletar(usuario, token):
    q = ('{ user(login: "%s") {'
         ' contributionsCollection { contributionCalendar { totalContributions'
         '  weeks { contributionDays { date contributionCount contributionLevel weekday } } } }'
         ' repositories(first: 10, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false,'
         '  orderBy: {field: PUSHED_AT, direction: DESC}) { nodes { name pushedAt isArchived'
         '  defaultBranchRef { target { ... on Commit { message committedDate } } } } } } }') % usuario
    u = api(token, graphql=q)['data']['user']
    cal = u['contributionsCollection']['contributionCalendar']
    repos = []
    for r in u['repositories']['nodes']:
        if r['name'].lower() == usuario.lower() or r['isArchived'] or not r['defaultBranchRef']:
            continue                                    # o repositorio do perfil e atualizado pelo robo todo dia
        c = r['defaultBranchRef']['target']
        repos.append({'nome': r['name'], 'quando': c['committedDate'], 'msg': c['message'].splitlines()[0]})
    return cal, repos[:3]


def resumo(cal):
    dias = [d for w in cal['weeks'] for d in w['contributionDays']]
    maior = atual = 0
    for d in dias:
        atual = atual + 1 if d['contributionCount'] > 0 else 0
        maior = max(maior, atual)
    seq = 0
    for d in reversed(dias):
        if d['contributionCount'] > 0:
            seq += 1
        elif seq or d is not dias[-1]:                 # hoje ainda sem nada nao quebra a sequencia
            break
    por_dia = [0] * 7
    for d in dias:
        por_dia[d['weekday']] += d['contributionCount']
    melhor = max(dias, key=lambda d: d['contributionCount'])
    semanas = max(len(cal['weeks']), 1)
    return {'maior': maior, 'atual': seq, 'dia': DIAS[por_dia.index(max(por_dia))],
            'media': cal['totalContributions'] / semanas, 'melhor': melhor['date'], 'hoje': dias[-1]['date']}


def ha_quanto(iso, agora):
    d = (agora.date() - dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).date()).days
    if d <= 0:
        return 'hoje'
    if d == 1:
        return 'ontem'
    if d < 14:
        return f'há {d} dias'
    if d < 60:
        return f'há {d // 7} semanas'
    return f'há {d // 30} meses'


def cortar(s, tam, peso, maximo, espaco=0):
    if t.largura(s, tam, peso, espaco) <= maximo:
        return s
    while s and t.largura(s + '…', tam, peso, espaco) > maximo:
        s = s[:-1]
    return s.rstrip() + '…'


def desenhar(cal, repos, agora, numero='05'):
    from gerar_visual import titulo
    f = Fontes()
    r = resumo(cal)
    total = cal['totalContributions']
    p = [titulo('atividade', 'ATIVIDADE', numero, f)]

    # numero grande e os tres numeros curtos
    p.append(texto(30, 112, f'{total}', 44, 700, t.CIANO_CLARO, f))
    nw = t.largura(f'{total}', 44, 700)
    p.append(texto(30 + nw + 12, 100, 'contribuições', 18, 600, t.TEXTO, f))
    p.append(texto(30 + nw + 12, 118, 'nos últimos 12 meses', 15, 500, t.CIANO_APAGADO, f))
    blocos = [('MAIOR SEQUÊNCIA', f"{r['maior']} dias"), ('DIA MAIS ATIVO', r['dia']),
              ('MÉDIA POR SEMANA', f"{r['media']:.0f}".replace('.', ','))]
    x = W - 30
    for rot, val in reversed(blocos):
        bw = max(t.largura(rot, 11, 700, 1.6), t.largura(val, 20, 700)) + 8
        x -= bw
        p.append(f'<path d="M{x - 12:g} 82 V120" stroke="{t.VERMELHO_APAGADO}"/>')
        p.append(texto(x, 94, rot, 11, 700, t.VERMELHO, f, espaco=1.6))
        p.append(texto(x, 117, val, 20, 700, t.CIANO, f))
        x -= 24

    # o mapa: semanas em colunas, dias em linhas, um caractere por dia
    cel = 13.5
    x0, y0 = 62, 156
    semanas = cal['weeks']
    mes_ant, ultimo_x = None, -99
    for wi, w in enumerate(semanas):
        m = int(w['contributionDays'][-1]['date'][5:7])
        if m != mes_ant:
            mes_ant = m
            x = x0 + wi * cel
            if x - ultimo_x >= 30 and wi < len(semanas) - 2:   # mes que mal comecou no canto nao ganha rotulo
                p.append(texto(x, y0 - 8, MESES[m - 1], 11, 600, t.VERMELHO, f))
                ultimo_x = x
    for k, nome in ((1, 'seg'), (3, 'qua'), (5, 'sex')):
        p.append(texto(x0 - 10, y0 + k * cel + cel * 0.75, nome, 11, 600, t.VERMELHO_APAGADO, f, ancora='end'))
    usos = []
    for wi, w in enumerate(semanas):
        for d in w['contributionDays']:
            n = NIVEL[d['contributionLevel']]
            gx, gy = x0 + wi * cel, y0 + d['weekday'] * cel
            if d['date'] == r['melhor']:
                usos.append(f'<use href="#g5" x="{gx:.1f}" y="{gy:.1f}" fill="{t.VERMELHO}"/>')
            else:
                usos.append(f'<use href="#g{[0, 1, 2, 3, 5][n]}" x="{gx:.1f}" y="{gy:.1f}" fill="{COR_NIVEL[n]}"/>')
            if d['date'] == r['hoje']:
                usos.append(f'<rect class="hoje" x="{gx + 0.5:.1f}" y="{gy + 0.5:.1f}" width="{cel - 1:.1f}" '
                            f'height="{cel - 1:.1f}" fill="none" stroke="{t.AMARELO}"/>')
    p.append(f'<defs>{t.glifo_defs(cel)}</defs>' + ''.join(usos))
    yl = y0 + 7 * cel + 18
    p.append(texto(x0, yl, 'melhor dia', 11, 600, t.VERMELHO_APAGADO, f))
    p.append(f'<use href="#g5" x="{x0 + 52}" y="{yl - 10.5}" fill="{t.VERMELHO}"/>')
    p.append(texto(x0 + 76, yl, 'hoje', 11, 600, t.VERMELHO_APAGADO, f))
    p.append(f'<rect x="{x0 + 101}" y="{yl - 10}" width="12.5" height="12.5" fill="none" stroke="{t.AMARELO}"/>')
    lx = x0 + 53 * cel
    p.append(texto(lx - 5 * cel - 8, yl, 'menos', 11, 600, t.VERMELHO_APAGADO, f, ancora='end'))
    for k, g in enumerate([0, 1, 2, 3, 5]):
        p.append(f'<use href="#g{g}" x="{lx - (5 - k) * cel:.1f}" y="{yl - 10.5}" fill="{COR_NIVEL[k]}"/>')
    p.append(texto(lx + 6, yl, 'mais', 11, 600, t.VERMELHO_APAGADO, f))

    # em andamento
    y = yl + 34
    p.append(texto(30, y, 'EM ANDAMENTO', 13, 700, t.VERMELHO, f, espaco=2.2))
    lw = t.largura('EM ANDAMENTO', 13, 700, 2.2)
    p.append(f'<path d="M{30 + lw + 12:g} {y - 4} H{W - 30}" stroke="{t.VERMELHO_APAGADO}"/>')
    y += 14
    for rp in repos:
        p.append(f'<path d="{t.chanfro(30, y, W - 60, 34, 7, "tl")}" fill="#0e0b10" stroke="#3b1b1d"/>')
        p.append(texto(46, y + 22, cortar(rp['nome'], 15, 700, 226, 0.8), 15, 700, t.CIANO, f, espaco=0.8))
        p.append(texto(290, y + 22, ha_quanto(rp['quando'], agora), 13, 600, t.VERMELHO, f, espaco=0.5))
        p.append(texto(372, y + 22, cortar(rp['msg'], 14, 500, W - 46 - 372), 14, 500, t.TEXTO, f))
        y += 42
    H = y + 12
    css = ('.hoje{animation:pisca 1.6s step-end infinite}@keyframes pisca{0%{opacity:1}50%{opacity:0}}'
           '@media (prefers-reduced-motion:reduce){.hoje{animation:none}}')
    alt = (f"Atividade: {total} contribuições nos últimos 12 meses; maior sequência de {r['maior']} dias; "
           f"dia mais ativo: {r['dia']}. Em andamento: " + '; '.join(x['nome'] for x in repos))
    return t.svg(W, H, ''.join(p), f, alt, extra_css=css), alt


def main(usuario, saida):
    token = os.environ['GITHUB_TOKEN']
    cal, repos = coletar(usuario, token)
    svg, alt = desenhar(cal, repos, dt.datetime.now(dt.timezone.utc))
    with open(saida, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    print(alt)
    print(f"{len(svg.encode()) / 1024:.0f} KB")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
