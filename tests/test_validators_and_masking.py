import pytest
from dlgpd.masking import mask
from dlgpd.validators import cnpj_valid, cpf_valid, phone_valid


@pytest.mark.parametrize("v,ok", [
    ("529.982.247-25", True), ("52998224725", True), ("529.982.247-24", False),
    ("111.111.111-11", False), ("123", False), ("", False),
])
def test_cpf(v, ok):
    assert cpf_valid(v) is ok


@pytest.mark.parametrize("v,ok", [
    ("11.222.333/0001-81", True), ("11.222.333/0001-82", False), ("00.000.000/0000-00", False),
])
def test_cnpj(v, ok):
    assert cnpj_valid(v) is ok


@pytest.mark.parametrize("v,ok", [
    ("(86) 99912-3456", True), ("+55 86 3222-1234", True), ("86999123456", True),
    ("(00) 99912-3456", False), ("(86) 89912-3456", False), ("1234", False),
])
def test_phone(v, ok):
    assert phone_valid(v) is ok


def test_masks_hide_the_raw_value():
    assert mask("CPF", "529.982.247-25") == "***.982.247-**"
    assert mask("EMAIL", "maria.silva@gmail.com") == "m***@gmail.com"
    assert mask("PESSOA", "Maria da Silva") == "Maria S."
    assert "123456" not in mask("ENDERECO", "Rua das Flores, 123456")
    assert mask("DATA_NASCIMENTO", "12/03/1985") == "**/**/1985"
    assert "98765" not in mask("TELEFONE", "(86) 99876-5432")
