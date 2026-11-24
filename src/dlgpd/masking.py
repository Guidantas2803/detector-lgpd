"""Mascaramento de dados para relatórios (princípio da minimização, LGPD Art. 6º, III)."""
import re
from .validators import only_digits


def mask(kind: str, value: str) -> str:
    v = value.strip()
    d = only_digits(v)
    if kind == "CPF" and len(d) == 11:
        # mesmo padrão do Portal da Transparência (***.XXX.XXX-**): nunca revela mais
        # dígitos do que já é público, evitando reconstruir o CPF por cruzamento de fontes
        return f"***.{d[3:6]}.{d[6:9]}-**"
    if kind == "CNPJ":
        c = re.sub(r"[^0-9A-Za-z]", "", v).upper()
        if len(c) == 14:
            return f"{c[:2]}.***.***/****-{c[-2:]}"
    if kind == "EMAIL":
        user, _, domain = v.partition("@")
        return f"{user[:1]}***@{domain}"
    if kind == "TELEFONE":
        core = d[2:] if d.startswith("55") and len(d) in (12, 13) else d
        return f"({core[:2]}) *****-**{core[-2:]}"
    if kind == "CEP":
        return f"{d[:5]}-***" if len(d) == 8 else "*****-***"
    if kind == "RG":
        return "*" * max(len(v) - 1, 3) + v[-1:]
    if kind == "PLACA":
        return f"{v[:3].upper()}-****"
    if kind == "DATA_NASCIMENTO":
        return re.sub(r"^\d{1,2}[/.-]\d{1,2}[/.-]", "**/**/", v)
    if kind == "ENDERECO":
        return v.split()[0] + " ****"
    if kind == "PESSOA":
        parts = v.split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[-1][:1].upper()}."
        return parts[0] if parts else "***"
    if kind == "LOCAL":
        # local detectado pelo NER (opção --locais): só a inicial, pois pode ser endereço ou bairro
        return f"{v[:1]}***" if v else "***"
    return v  # tipos sensíveis exibem apenas o termo que disparou a detecção
