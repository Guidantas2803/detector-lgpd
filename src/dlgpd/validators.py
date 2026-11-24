"""Validação de documentos brasileiros por dígitos verificadores."""
import re

VALID_DDD = {
    11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28, 31, 32, 33, 34, 35, 37, 38,
    41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69,
    71, 73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 92, 93, 94, 95, 96, 97, 98, 99,
}


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def cpf_valid(value: str) -> bool:
    d = only_digits(value)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for i in (9, 10):
        total = sum(int(d[j]) * (i + 1 - j) for j in range(i))
        if (total * 10 % 11) % 10 != int(d[i]):
            return False
    return True


def cnpj_valid(value: str) -> bool:
    """Valida CNPJ numérico e alfanumérico (IN RFB nº 2.229/2024, vigente desde jul/2026).

    As 12 primeiras posições aceitam 0-9 e A-Z (valor = código ASCII - 48); os dois
    últimos caracteres são sempre dígitos verificadores, calculados por módulo 11.
    """
    c = re.sub(r"[.\-/\s]", "", value).upper()
    if len(c) != 14 or not re.fullmatch(r"[0-9A-Z]{12}\d{2}", c) or c == c[0] * 14:
        return False
    v = [ord(ch) - 48 for ch in c]
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    for n, w in ((12, w1), (13, w2)):
        r = sum(v[i] * w[i] for i in range(n)) % 11
        dv = 0 if r < 2 else 11 - r
        if dv != v[n]:
            return False
    return True


def phone_valid(value: str) -> bool:
    d = only_digits(value)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) not in (10, 11):
        return False
    if int(d[:2]) not in VALID_DDD:
        return False
    if len(d) == 11 and d[2] != "9":      # celular começa com 9
        return False
    if len(d) == 10 and d[2] not in "2345":  # fixo começa com 2-5
        return False
    return True
