"""Detector de dados com formato padronizado (expressões regulares + validação)."""
import re
from ..models import Finding, Segment, PESSOAL, POTENCIAL
from ..masking import mask
from ..validators import cpf_valid, cnpj_valid, phone_valid
from .base import Detector

# (tipo, regex, grupo, validador, categoria, prioridade)
# A prioridade resolve sobreposições: número menor vence.
_PATTERNS = [
    ("CNPJ", r"(?<![\d/])\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)", 0, cnpj_valid, POTENCIAL, 1),
    # CNPJ alfanumérico: só com pontuação completa (sem pontuação, uma palavra de 14 letras/dígitos
    # passaria no módulo 11 por acaso em ~1/121 das vezes). Sem pontuação, só o formato numérico.
    ("CNPJ", r"(?<![A-Za-z0-9/])(?=[0-9./-]*[A-Z])[0-9A-Z]{2}\.[0-9A-Z]{3}\.[0-9A-Z]{3}/[0-9A-Z]{4}-\d{2}(?![A-Za-z0-9])", 0, cnpj_valid, POTENCIAL, 1),
    ("CPF", r"(?<![\d.])\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?![\d-])", 0, cpf_valid, PESSOAL, 2),
    ("EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", 0, None, PESSOAL, 3),
    ("TELEFONE", r"(?<![\d.-])(?:\+?55\s?)?(?:\(\d{2}\)\s?|\d{2}\s)9?\d{4}[-\s]?\d{4}(?![\d-])", 0, phone_valid, PESSOAL, 4),
    ("TELEFONE", r"(?<![\d.-])\d{2}9\d{8}(?![\d-])", 0, phone_valid, PESSOAL, 4),
    ("CEP", r"(?<!\d)\d{5}-\d{3}(?!\d)", 0, None, PESSOAL, 5),
    ("CEP", r"(?i)\bCEP\s*:?\s*(\d{8})(?!\d)", 1, None, PESSOAL, 5),
    ("RG", r"(?i)\bRG\s*(?:n[ºo°.]*)?\s*:?\s*(\d{1,2}\.?\d{3}\.?\d{3}-?[\dXx]|\d{5,10})(?![\d])", 1, None, PESSOAL, 6),
    ("PLACA", r"(?<![A-Za-z0-9])[A-Z]{3}-?\d[A-Z0-9]\d{2}(?![A-Za-z0-9])", 0, None, PESSOAL, 7),
    ("DATA_NASCIMENTO",
     r"(?i)(?:data\s+de\s+nasc\w*|nascimento|nasc\.?|nascid[oa]\s+em)\s*:?\s*(?:em\s*)?(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})",
     1, None, PESSOAL, 8),
    ("ENDERECO",
     r"\b(?:Rua|Av\.?|Avenida|Travessa|Alameda|Rodovia|Estrada|Pra[çc]a)\s+"
     r"(?:[A-Za-zÀ-ú0-9.'ºª-]+\s?){1,6}?(?:,\s*|\s+)(?:n[ºo°.]*\s*)?\d{1,5}[A-Za-z]?(?![\d-])",
     0, None, PESSOAL, 9),
]
_COMPILED = [(k, re.compile(p), g, v, c, pr) for k, p, g, v, c, pr in _PATTERNS]


class RegexDetector(Detector):
    name = "regex"

    def detect(self, seg: Segment) -> list:
        findings = []
        for kind, rx, group, validator, category, priority in _COMPILED:
            for m in rx.finditer(seg.text):
                value = m.group(group)
                if validator and not validator(value):
                    continue
                start, end = m.span(group)
                findings.append(Finding(
                    file=seg.file, location=seg.location, kind=kind, category=category,
                    value=value, masked=mask(kind, value), detector=self.name,
                    start=start, end=end, priority=priority,
                ))
        return findings
