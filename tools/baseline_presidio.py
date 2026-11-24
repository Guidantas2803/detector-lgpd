"""Baseline: Microsoft Presidio configurado para português, SEM recognizers brasileiros.

Compara o desempenho "de fábrica" do Presidio (spaCy pt_core_news_lg + reconhecedores
padrão) com o detector deste trabalho, no mesmo conjunto de teste e com o mesmo gabarito.
Uso: python tools/baseline_presidio.py samples_teste [pasta_saida]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from dlgpd.evaluation import ENTITY_KINDS, evaluate, to_markdown
from dlgpd.extractors import SUPPORTED, extract
from dlgpd.models import Finding, PESSOAL, ScanResult
from dlgpd.scanner import Scanner

# Tabela de mapeamento entidade do Presidio -> tipo do gabarito (documentada no Apêndice do TCC).
# ESTRITO: só entidades com equivalência semântica direta.
# AMPLIADO: aproxima as entidades genéricas do Presidio dos tipos do gabarito (generoso com o
#   baseline: toda data vira "data de nascimento" e todo local vira "endereço").
MAPPINGS = {
    "estrito": {"EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "TELEFONE", "PERSON": "PESSOA"},
    "ampliado": {"EMAIL_ADDRESS": "EMAIL", "PHONE_NUMBER": "TELEFONE", "PERSON": "PESSOA",
                 "DATE_TIME": "DATA_NASCIMENTO", "LOCATION": "ENDERECO"},
}


def build_analyzer():
    cfg = {"nlp_engine_name": "spacy", "models": [{"lang_code": "pt", "model_name": "pt_core_news_lg"}]}
    nlp = NlpEngineProvider(nlp_configuration=cfg).create_engine()
    registry = RecognizerRegistry(supported_languages=["pt"])
    registry.load_predefined_recognizers(languages=["pt"], nlp_engine=nlp)
    return AnalyzerEngine(nlp_engine=nlp, registry=registry, supported_languages=["pt"])


def scan_with_presidio(root: Path, analyzer, mapping) -> ScanResult:
    result = ScanResult(root=str(root), ner_enabled=True)
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in SUPPORTED:
            continue
        result.files_scanned.append(path.name)
        for seg in extract(path, root):
            for r in analyzer.analyze(text=seg.text, language="pt"):
                kind = mapping.get(r.entity_type)
                if kind:
                    value = seg.text[r.start:r.end]
                    result.findings.append(Finding(seg.file, seg.location, kind, PESSOAL, value, "", "presidio"))
    return result


if __name__ == "__main__":
    samples = Path(sys.argv[1])
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "resultados_baseline_presidio")
    out.mkdir(parents=True, exist_ok=True)
    gt = samples / "ground_truth.json"
    analyzer = build_analyzer()
    print("Reconhecedores carregados:", sorted({r.name for r in analyzer.registry.recognizers}))
    mine = evaluate(Scanner(use_ner=True).scan(samples), gt)
    bases = {}
    for name, mapping in MAPPINGS.items():
        bases[name] = evaluate(scan_with_presidio(samples, analyzer, mapping), gt)
        (out / f"presidio_{name}_avaliacao.md").write_text(to_markdown(bases[name]) + "\n", encoding="utf-8")
        (out / f"presidio_{name}_erros.json").write_text(
            json.dumps(bases[name]["erros"], ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "reconhecedores_pt.txt").write_text("\n".join(
        f"{r.name}\t{r.supported_language}\t{','.join(r.supported_entities)}" for r in analyzer.registry.recognizers) + "\n")
    (out / "mapeamento.json").write_text(json.dumps(MAPPINGS, indent=1), encoding="utf-8")

    def cell(t):
        return f"{t['precisao']:.2f} / {t['recall']:.2f} / {t['f1']:.2f}" if t else "0.00 / 0.00 / 0.00"
    rows = {n: {t["tipo"]: t for t in b["tabela"]} for n, b in bases.items()}
    mrows = {t["tipo"]: t for t in mine["tabela"]}
    lines = ["| Tipo de dado | Presidio, mapeamento estrito (P / R / F1) | Presidio, mapeamento ampliado | Este trabalho |",
             "|---|---|---|---|"]
    for k in ENTITY_KINDS:
        if k not in mrows:
            continue
        lines.append(f"| {mrows[k]['rotulo']} | {cell(rows['estrito'].get(k))} | {cell(rows['ampliado'].get(k))} | {cell(mrows[k])} |")
    for k, lab in (("MICRO_ENTIDADE", "MICRO (identificadores PF, nomes, endereços)"),):
        lines.append(f"| {lab} | {cell(rows['estrito'].get(k))} | {cell(rows['ampliado'].get(k))} | {cell(mrows[k])} |")
    md = "\n".join(lines)
    (out / "comparacao.md").write_text(md + "\n", encoding="utf-8")
    print(md)
