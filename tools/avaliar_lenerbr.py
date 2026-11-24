"""Avalia o detector de nomes (NER + filtros) no LeNER-Br (textos jurídicos reais, entidade PESSOA).

Uso: python tools/avaliar_lenerbr.py CAMINHO/leNER-Br/test/test.conll [--saida pasta]
Dois critérios sobre a MESMA lista de predições: trecho exato e sobreposição com
emparelhamento 1 a 1. O filtro de 2+ palavras restringe só o gabarito. Os filtros do detector (mín. 2 palavras,
prefixos institucionais) são os da versão final; nada foi ajustado a este corpus.
"""
import sys, json, math, argparse, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from dlgpd.detectors.ner_detector import NerDetector
from dlgpd.models import Segment


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def ler(path):
    sents, cur = [], []
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            if cur: sents.append(cur); cur = []
            continue
        tok, tag = line.rsplit(" ", 1)
        cur.append((tok, tag))
    if cur: sents.append(cur)
    out = []
    for s in sents:
        text, pos, gold, start = "", [], [], None
        for i, (tok, tag) in enumerate(s):
            if text: text += " "
            a = len(text); text += tok
            pos.append((a, len(text)))
        i = 0
        while i < len(s):
            if s[i][1] == "B-PESSOA":
                j = i
                while j + 1 < len(s) and s[j + 1][1] == "I-PESSOA": j += 1
                gold.append((pos[i][0], pos[j][1], j - i + 1))
                i = j + 1
            else:
                i += 1
        out.append((text, gold))
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("conll"); ap.add_argument("--saida", default=None)
    a = ap.parse_args()
    data = ler(a.conll)
    det = NerDetector()
    segs = [Segment("lener", str(i), t) for i, (t, _) in enumerate(data)]
    found = {}
    for f in det.detect_many(segs):
        found.setdefault(int(f.location), set()).add((f.start, f.end))
    res = {}

    def medidas(tp, fp, fn):
        P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
        F = 2 * P * R / (P + R) if P + R else 0
        return dict(VP=tp, FP=fp, FN=fn, P=round(P, 3), R=round(R, 3), F1=round(F, 3),
                    R_IC95=[round(x, 3) for x in wilson(tp, tp + fn)],
                    P_IC95=[round(x, 3) for x in wilson(tp, tp + fp)])

    for nome, filtro in (("exato, todas as entidades PESSOA", lambda w: True),
                         ("exato, apenas entidades com 2+ palavras", lambda w: w >= 2)):
        tp = fp = fn = 0
        for i, (t, gold) in enumerate(data):
            g = {(s, e) for s, e, w in gold if filtro(w)}
            p = found.get(i, set())
            tp += len(g & p); fp += len(p - g); fn += len(g - p)
        res[nome] = medidas(tp, fp, fn)
    # critério brando: o trecho previsto conta se sobrepõe a uma entidade do gabarito
    # (ignora diferenças de borda, como "Ministro" ou "Sr." incluídos no nome).
    # Emparelhamento 1 a 1 (máximo): cada predição acerta no máximo um nome e vice-versa,
    # de modo que VP + FP = número de predições, como no critério exato.
    def emparelhar(g, p):
        adj = [[j for j, q in enumerate(p) if q[0] < x[1] and x[0] < q[1]] for x in g]
        dono = {}
        def tenta(i, vistos):
            for j in adj[i]:
                if j in vistos: continue
                vistos.add(j)
                if j not in dono or tenta(dono[j], vistos):
                    dono[j] = i; return True
            return False
        return sum(tenta(i, set()) for i in range(len(g)))
    tp = fp = fn = 0
    for i, (t, gold) in enumerate(data):
        g = [(s, e) for s, e, w in gold]; p = list(found.get(i, set()))
        m = emparelhar(g, p)
        tp += m; fn += len(g) - m; fp += len(p) - m
    res["brando (sobreposição, emparelhamento 1 a 1), todas as entidades PESSOA"] = medidas(tp, fp, fn)
    res["frases"] = len(data)
    res["predicoes"] = sum(len(v) for v in found.values())
    res["entidades_gabarito"] = sum(len(g) for _, g in data)
    res["entidades_gabarito_2mais_palavras"] = sum(1 for _, g in data for x in g if x[2] >= 2)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if a.saida:
        p = pathlib.Path(a.saida); p.mkdir(parents=True, exist_ok=True)
        (p / "lenerbr_pessoa.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


main()
