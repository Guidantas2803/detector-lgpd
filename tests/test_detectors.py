import pytest
from dlgpd.detectors import ContextDetector, RegexDetector
from dlgpd.models import SENSIVEL, Segment
from dlgpd.scanner import resolve_overlaps


def kinds(text):
    return [(f.kind, f.value) for f in RegexDetector().detect(Segment("a", "l", text))]


def test_cpf_formats_and_validation():
    assert ("CPF", "529.982.247-25") in kinds("CPF 529.982.247-25")
    assert ("CPF", "52998224725") in kinds("cpf 52998224725")
    assert not [k for k in kinds("código 123.456.789-00") if k[0] == "CPF"]  # dígito inválido


def test_process_number_is_not_cpf_or_phone():
    assert kinds("Processo 0001234-56.2023.8.18.0001") == []


def test_email_phone_cep_plate_birthdate_address():
    text = ("Contato: ana.lima@uol.com.br, (86) 99912-3456, CEP 64000-123, placa ABC1D23, "
            "nascimento: 05/11/1990, Rua das Flores, 123.")
    found = {k for k, _ in kinds(text)}
    assert {"EMAIL", "TELEFONE", "CEP", "PLACA", "DATA_NASCIMENTO", "ENDERECO"} <= found


def test_rg_requires_label():
    assert any(k == "RG" for k, _ in kinds("RG: 1.234.567-8"))
    assert not any(k == "RG" for k, _ in kinds("pedido 1.234.567-8"))


def test_cnpj_is_potential_not_personal():
    f = RegexDetector().detect(Segment("a", "l", "CNPJ 11.222.333/0001-81"))
    assert f and f[0].kind == "CNPJ" and f[0].category == "Potencial"


def test_alphanumeric_cnpj_from_receita_example():
    from dlgpd.validators import cnpj_valid
    assert cnpj_valid("12.ABC.345/01DE-35") and not cnpj_valid("12.ABC.345/01DE-34")
    f = RegexDetector().detect(Segment("a", "l", "CNPJ 12.ABC.345/01DE-35"))
    assert [x.kind for x in f] == ["CNPJ"] and f[0].masked == "12.***.***/****-35"
    # sem pontuação, uma palavra qualquer de 14 caracteres não pode virar CNPJ
    assert not RegexDetector().detect(Segment("a", "l", "ABCDEFGHIJKLMN"))


def test_overlap_prefers_higher_priority():
    # 11 dígitos que são CPF válido e também têm formato de celular: CPF deve vencer
    findings = RegexDetector().detect(Segment("a", "l", "CPF 52998224725"))
    kept = resolve_overlaps(findings)
    assert [f.kind for f in kept] == ["CPF"]


def test_sensitive_context_detection_and_aggregation():
    f = ContextDetector().detect(Segment("a", "l", "Diagnóstico de diabetes; religião: católico; filiação sindical"))
    by_kind = {x.kind: x for x in f}
    assert {"SAUDE", "RELIGIAO", "SINDICATO"} <= by_kind.keys()
    assert all(x.category == SENSIVEL for x in f)
    assert "diabetes" in by_kind["SAUDE"].value.lower()


def test_case_sensitive_acronyms():
    assert not ContextDetector().detect(Segment("a", "l", "o gerente irá fazer a lista"))  # "ist" não é IST
    assert ContextDetector().detect(Segment("a", "l", "Exame de HIV positivo"))


@pytest.mark.xfail(reason="limitação conhecida: palavra-chave fora de contexto médico gera falso positivo",
                   strict=True)
def test_known_false_positive_transtorno():
    assert not ContextDetector().detect(Segment("a", "l", "A obra causou transtorno aos moradores."))
