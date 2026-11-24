"""Avaliação do detector contra um gabarito: precisão, recall e F1 por tipo de dado.

- Identificadores (CPF, e-mail, telefone...) e nomes/endereços: avaliação por ENTIDADE
  (cada ocorrência esperada precisa ser encontrada no arquivo certo).
- Dados sensíveis (saúde, religião...): avaliação por ARQUIVO+CATEGORIA (o arquivo
  contém ou não aquela categoria), pois o objetivo é sinalizar o documento.

Critério de acerto (entidades): a comparação é por ARQUIVO + VALOR normalizado; a posição
dentro do arquivo não é exigida. Cada ocorrência esperada consome uma ocorrência detectada
(multiconjunto): o mesmo CPF citado duas vezes no gabarito exige duas detecções, e uma
detecção a mais é falso positivo. Nomes e endereços usam casamento tolerante: sem acentos,
sem caixa e aceitando que um valor contenha o outro ("Maria" casa com "Maria da Silva").
"Maria Silva" NÃO casa com "Maria da Silva". O campo `parciais` conta os acertos que só
ocorreram por essa tolerância (valor diferente do esperado).

O CNPJ identifica pessoa jurídica e fica FORA das médias de dado pessoal (nível "entidade (PJ)").
As médias macro são calculadas separadamente para cada nível de avaliação.
"""
import math
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from .models import KIND_LABELS

ENTITY_KINDS = ["CPF", "CNPJ", "EMAIL", "TELEFONE", "CEP", "RG", "PLACA",
                "DATA_NASCIMENTO", "ENDERECO", "PESSOA"]
SENSITIVE_KINDS = ["SAUDE", "RELIGIAO", "SINDICATO", "POLITICA", "ETNIA", "SEXUAL", "BIOMETRICO"]
FUZZY = {"PESSOA", "ENDERECO"}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize(kind: str, value: str) -> str:
    if kind in FUZZY:
        return _plain(value)
    if kind == "EMAIL":
        return value.strip().lower()
    if kind in ("RG", "PLACA"):
        return re.sub(r"[^0-9A-Za-z]", "", value).upper()
    digits = re.sub(r"\D", "", value)
    if kind == "TELEFONE" and digits.startswith("55") and len(digits) in (12, 13):
        digits = digits[2:]
    return digits


def _match(kind: str, a: str, b: str) -> bool:
    if kind in FUZZY:
        return a == b or a in b or b in a
    return a == b


def wilson(k: int, n: int, z: float = 1.96):
    """Intervalo de confiança de Wilson (95%) para uma proporção k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def evaluate(result, ground_truth_path) -> dict:
    gt = json.loads(Path(ground_truth_path).read_text(encoding="utf-8"))
    rows, errors = [], []
    scanned = set(result.files_scanned)

    for kind in ENTITY_KINDS:
        tp = fp = fn = parc = 0
        files = {g["file"] for g in gt if g["kind"] == kind} | {f.file for f in result.findings if f.kind == kind}
        for file in sorted(files):
            expected = [normalize(kind, g["value"]) for g in gt if g["kind"] == kind and g["file"] == file]
            found = [normalize(kind, f.value) for f in result.findings if f.kind == kind and f.file == file]
            unmatched = list(found)
            for exp in expected:
                hit = next((i for i, got in enumerate(unmatched) if _match(kind, exp, got)), None)
                if hit is None:
                    fn += 1
                    errors.append({"tipo": kind, "erro": "FN (não detectado)", "arquivo": file, "valor": exp})
                else:
                    tp += 1
                    if unmatched[hit] != exp:
                        parc += 1
                    unmatched.pop(hit)
            for extra in unmatched:
                fp += 1
                errors.append({"tipo": kind, "erro": "FP (detectado indevidamente)", "arquivo": file, "valor": extra})
        rows.append((kind, "entidade (PJ)" if kind == "CNPJ" else "entidade", tp, fp, fn, parc))

    for kind in SENSITIVE_KINDS:
        expected = {g["file"] for g in gt if g["kind"] == kind and g["file"] in scanned}
        found = {f.file for f in result.findings if f.kind == kind}
        tp, fp, fn = len(expected & found), len(found - expected), len(expected - found)
        for f in sorted(found - expected):
            errors.append({"tipo": kind, "erro": "FP (detectado indevidamente)", "arquivo": f, "valor": ""})
        for f in sorted(expected - found):
            errors.append({"tipo": kind, "erro": "FN (não detectado)", "arquivo": f, "valor": ""})
        rows.append((kind, "arquivo", tp, fp, fn, 0))

    table = []
    for kind, level, tp, fp, fn, parc in rows:
        if tp + fp + fn == 0:
            continue
        p, r, f = _prf(tp, fp, fn)
        n = tp + fn
        lo, hi = wilson(tp, n)
        table.append({"tipo": kind, "rotulo": KIND_LABELS[kind], "nivel": level, "n": n,
                      "tp": tp, "fp": fp, "fn": fn, "precisao": p, "recall": r, "f1": f,
                      "recall_ic95": f"{lo:.2f}-{hi:.2f}", "parciais": parc,
                      "amostra_insuficiente": n < 10})
    for scope, label in (("entidade", "MICRO (identificadores, nomes, endereços)"), ("arquivo", "MICRO (dados sensíveis)")):
        sub = [t for t in table if t["nivel"] == scope]
        tp, fp, fn = (sum(t[k] for t in sub) for k in ("tp", "fp", "fn"))
        p, r, f = _prf(tp, fp, fn)
        lo, hi = wilson(tp, tp + fn)
        table.append({"tipo": f"MICRO_{scope.upper()}", "rotulo": label, "nivel": scope, "n": tp + fn,
                      "tp": tp, "fp": fp, "fn": fn, "precisao": p, "recall": r, "f1": f,
                      "recall_ic95": f"{lo:.2f}-{hi:.2f}", "parciais": sum(t["parciais"] for t in sub),
                      "amostra_insuficiente": False})
    for scope, label in (("entidade", "MACRO (média dos tipos avaliados por entidade)"),
                         ("arquivo", "MACRO (média das categorias avaliadas por arquivo)")):
        macro = [t for t in table if t["nivel"] == scope and not t["tipo"].startswith("MICRO")]
        table.append({"tipo": f"MACRO_{scope.upper()}", "rotulo": label, "nivel": scope, "n": "",
                      "tp": "", "fp": "", "fn": "",
                      "precisao": sum(t["precisao"] for t in macro) / len(macro),
                      "recall": sum(t["recall"] for t in macro) / len(macro),
                      "f1": sum(t["f1"] for t in macro) / len(macro),
                      "recall_ic95": "", "parciais": "", "amostra_insuficiente": False})
    return {"tabela": table, "erros": errors, "arquivos": len(scanned), "ner": result.ner_enabled}


def to_markdown(ev: dict) -> str:
    lines = ["| Tipo de dado | Avaliação | n | VP | FP | FN | Precisão | Recall | F1 | IC95% do recall | Obs. |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t in ev["tabela"]:
        obs = "amostra insuficiente (n<10)" if t.get("amostra_insuficiente") else ""
        lines.append(f"| {t['rotulo']} | {t['nivel']} | {t['n']} | {t['tp']} | {t['fp']} | {t['fn']} | "
                     f"{t['precisao']:.2f} | {t['recall']:.2f} | {t['f1']:.2f} | {t['recall_ic95']} | {obs} |")
    return "\n".join(lines)


def write_evaluation(ev: dict, out_dir) -> str:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = to_markdown(ev)
    (out / "avaliacao.md").write_text(
        f"# Avaliação do detector\n\nArquivos avaliados: {ev['arquivos']} · NER ativo: {'sim' if ev['ner'] else 'não'}\n\n{md}\n",
        encoding="utf-8")
    with open(out / "avaliacao.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ev["tabela"][0].keys()))
        w.writeheader()
        w.writerows(ev["tabela"])
    (out / "analise_de_erros.json").write_text(json.dumps(ev["erros"], ensure_ascii=False, indent=2), encoding="utf-8")
    return md
