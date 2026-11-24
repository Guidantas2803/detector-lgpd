import json

import pytest
from openpyxl import load_workbook

from dlgpd.evaluation import evaluate
from dlgpd.extractors import extract
from dlgpd.report import write_all
from dlgpd.scanner import Scanner

RAW_KINDS = {"CPF", "EMAIL", "TELEFONE", "CEP", "RG", "ENDERECO", "DATA_NASCIMENTO", "PESSOA", "CNPJ", "PLACA"}


def test_extractors_read_every_supported_format(samples):
    for name in ["ficha_cadastro_01.txt", "clientes.csv", "folha_pagamento.xlsx",
                 "laudo_medico.docx", "ficha_funcionario.pdf"]:
        segs = list(extract(samples / name, samples))
        assert segs, f"nenhum texto extraído de {name}"


def test_column_header_gives_context_to_rg_and_birthdate(samples):
    result = Scanner(use_ner=False).scan(samples / "funcionarios.csv")
    kinds = {f.kind for f in result.findings}
    assert {"RG", "DATA_NASCIMENTO", "CPF"} <= kinds


def test_unsupported_and_corrupted_files_are_skipped_not_fatal(tmp_path):
    (tmp_path / "a.xyz").write_text("x")
    (tmp_path / "quebrado.docx").write_text("isto não é um docx")
    (tmp_path / "ok.txt").write_text("CPF 529.982.247-25")
    result = Scanner(use_ner=False).scan(tmp_path)
    assert result.files_scanned == ["ok.txt"]
    assert {name for name, _ in result.skipped} == {"a.xyz", "quebrado.docx"}
    assert len(result.findings) == 1


def test_reports_never_contain_raw_values(scan_result, tmp_path):
    paths = write_all(scan_result, tmp_path)
    blob = ""
    for p in paths:
        if p.suffix == ".xlsx":
            wb = load_workbook(p)
            blob += " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
        else:
            blob += p.read_text(encoding="utf-8")
    leaks = [f.value for f in scan_result.findings if f.kind in RAW_KINDS and f.value in blob]
    assert leaks == [], f"valores brutos vazaram para o relatório: {leaks[:3]}"
    assert json.loads((tmp_path / "relatorio.json").read_text(encoding="utf-8"))["total_achados"] > 0


def test_files_without_personal_data_have_no_risk(scan_result):
    from dlgpd.report import summarize
    files = {f["arquivo"]: f for f in summarize(scan_result)["arquivos"]}
    assert files["estoque.csv"]["risco"] == "Nenhum"
    assert files["anotacoes_internas_01.txt"]["pessoais"] == 0
    assert files["funcionarios.csv"]["risco"] == "Médio"   # muitos tipos pessoais, nenhum sensível


def test_any_sensitive_file_outranks_any_file_without_sensitive(scan_result):
    from dlgpd.report import summarize
    files = summarize(scan_result)["arquivos"]
    com = [f for f in files if f["sensiveis"]]
    sem = [f for f in files if not f["sensiveis"]]
    assert com and all(f["risco"] == "Alto" for f in com)
    assert all(f["risco"] != "Alto" for f in sem)
    assert min(f["pontuacao"] for f in com) > max(f["pontuacao"] for f in sem)


def test_risk_counts_types_not_occurrences():
    from dlgpd.report import risk_level
    assert risk_level(0, 2) == "Baixo" and risk_level(0, 3) == "Médio"
    assert risk_level(1, 0) == "Alto" and risk_level(0, 0) == "Nenhum"


def test_evaluation_cnpj_outside_personal_averages_and_macro_per_level(scan_result, samples):
    ev = evaluate(scan_result, samples / "ground_truth.json")
    rows = {t["tipo"]: t for t in ev["tabela"]}
    assert rows["CNPJ"]["nivel"] == "entidade (PJ)"
    pessoais = [t for t in ev["tabela"] if t["nivel"] == "entidade" and not t["tipo"].startswith(("MICRO", "MACRO"))]
    assert rows["MICRO_ENTIDADE"]["tp"] == sum(t["tp"] for t in pessoais)
    assert "MACRO" not in rows and {"MACRO_ENTIDADE", "MACRO_ARQUIVO"} <= rows.keys()


def test_identifier_quality_on_synthetic_set(scan_result, samples):
    ev = evaluate(scan_result, samples / "ground_truth.json")
    rows = {t["tipo"]: t for t in ev["tabela"]}
    for kind in ("CPF", "EMAIL", "TELEFONE", "CEP", "RG", "DATA_NASCIMENTO", "ENDERECO"):
        assert rows[kind]["precisao"] >= 0.95 and rows[kind]["recall"] >= 0.95, kind


def test_ner_names_quality(scan_result, samples, ner_available):
    if not ner_available:
        pytest.skip("modelo pt_core_news_lg não instalado")
    ev = evaluate(scan_result, samples / "ground_truth.json")
    names = {t["tipo"]: t for t in ev["tabela"]}["PESSOA"]
    assert names["f1"] >= 0.90


def test_file_names_with_personal_data_are_masked_in_reports(tmp_path):
    from dlgpd.scanner import Scanner
    from dlgpd.report import write_all
    import json
    (tmp_path / "laudo_529.982.247-25.txt").write_text("Atendimento de rotina.", encoding="utf-8")
    out = tmp_path / "out"
    res = Scanner(use_ner=False).scan(tmp_path)
    write_all(res, out, ("json", "html"))
    text = (out / "relatorio.json").read_text(encoding="utf-8") + (out / "relatorio.html").read_text(encoding="utf-8")
    assert "529.982.247-25" not in text and "laudo_***.982.247-**.txt" in text
    assert str(tmp_path) not in json.loads((out / "relatorio.json").read_text(encoding="utf-8"))["pasta"]


def test_pseudonymized_paths_keep_mapping_apart(tmp_path):
    from dlgpd.scanner import Scanner
    from dlgpd.report import write_all
    (tmp_path / "Contrato_Joao.txt").write_text("CPF 529.982.247-25", encoding="utf-8")
    out = tmp_path / "out"
    res = Scanner(use_ner=False, pseudonymize_paths=True).scan(tmp_path)
    write_all(res, out, ("json",))
    rel = (out / "relatorio.json").read_text(encoding="utf-8")
    assert "Contrato_Joao" not in rel and "ARQ-001.txt" in rel
    assert "Contrato_Joao" in (out / "mapa_de_caminhos_CONFIDENCIAL.json").read_text(encoding="utf-8")


def test_new_detector_plugs_in_without_changing_scanner(tmp_path):
    """Extensibilidade (RNF03): um quarto detector entra pela lista, sem alterar o Scanner."""
    from dlgpd.scanner import Scanner
    from dlgpd.detectors import Detector, RegexDetector
    from dlgpd.models import Finding, PESSOAL

    class MatriculaDetector(Detector):
        name = "matricula"
        def detect(self, seg):
            i = seg.text.find("MAT-")
            if i < 0:
                return []
            v = seg.text[i:i + 10]
            return [Finding(seg.file, seg.location, "MATRICULA", PESSOAL, v, "MAT-******",
                            self.name, i, i + 10, 5)]

    (tmp_path / "a.txt").write_text("Aluno MAT-123456, CPF 529.982.247-25", encoding="utf-8")
    res = Scanner(detectors=[RegexDetector(), MatriculaDetector()]).scan(tmp_path)
    assert {f.kind for f in res.findings} == {"MATRICULA", "CPF"}


def test_locations_from_ner_are_masked():
    from dlgpd.masking import mask
    assert mask("LOCAL", "Bairro Fátima") == "B***"
