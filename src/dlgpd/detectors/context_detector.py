"""Detector de dados pessoais SENSÍVEIS (LGPD, Art. 5º, II) por termos de contexto.

Limitação conhecida: baseia-se em palavras-chave, portanto gera falsos positivos
(ex.: "transtorno" em contexto não médico). O relatório exibe apenas o termo
que disparou a detecção, nunca a frase completa (minimização de dados).
"""
import re
from ..models import Finding, Segment, SENSIVEL
from .base import Detector

_TERMS = {
    "SAUDE": [
        r"diagn[óo]stic[oa]", r"\bCID(?:-?10)?\s*:?\s*[A-Z]\d{2}(?:\.\d)?", r"laudo\s+m[ée]dico",
        r"atestado\s+m[ée]dico", r"prontu[áa]rio", r"medicamento", r"\bHIV\b", r"\bAIDS\b",
        r"c[âa]ncer", r"diabetes", r"hipertens[ãa]o", r"depress[ãa]o", r"ansiedade",
        r"esquizofrenia", r"transtorno", r"doen[çc]a\s+cr[ôo]nica", r"portador(?:a)?\s+de",
        r"interna[çc][ãa]o\s+hospitalar", r"cirurgia", r"quimioterapia", r"epilepsia",
        r"tuberculose", r"hepatite", r"defici[êe]ncia\s+(?:visual|auditiva|f[íi]sica|intelectual)",
    ],
    "RELIGIAO": [
        r"cat[óo]lic[oa]", r"evang[ée]lic[oa]", r"esp[íi]rita", r"umbandista", r"candombl[ée]",
        r"mu[çc]ulman[oa]", r"isl[âa]mic[oa]", r"\bjudeu\b|\bjudia\b", r"budista",
        r"\bateu\b|\bateia\b", r"testemunha\s+de\s+jeov[áa]", r"convic[çc][ãa]o\s+religiosa",
        r"\breligi[ãa]o\b", r"frequenta\s+(?:a\s+)?(?:igreja|culto|templo|terreiro)",
    ],
    "SINDICATO": [
        r"filia[çc][ãa]o\s+sindical", r"filiad[oa]\s+ao\s+sindicato", r"sindicalizad[oa]",
    ],
    "POLITICA": [
        r"filia[çc][ãa]o\s+partid[áa]ria", r"filiad[oa]\s+ao\s+partido",
        r"op[ií]ni[ãa]o\s+pol[ií]tica", r"convic[çc][ãa]o\s+pol[ií]tica",
        r"militante\s+(?:pol[ií]tico|do\s+partido)",
    ],
    "ETNIA": [
        r"origem\s+(?:racial|[ée]tnica)", r"ra[çc]a\s*/?\s*cor", r"cor\s*/\s*ra[çc]a",
        r"\bcor\s*:\s*(?:preta|parda|branca|amarela|ind[ií]gena)", r"autodeclarad[oa]",
        r"afrodescendente", r"ind[ií]gena", r"quilombola", r"\betnia\b",
    ],
    "SEXUAL": [
        r"orienta[çc][ãa]o\s+sexual", r"homossexual", r"bissexual", r"vida\s+sexual",
        r"\bIST\b", r"\bDST\b", r"transg[êe]nero", r"identidade\s+de\s+g[êe]nero",
    ],
    "BIOMETRICO": [
        r"biometria", r"biom[ée]tric[oa]", r"impress[ãa]o\s+digital", r"reconhecimento\s+facial",
        r"exame\s+de\s+DNA", r"gen[ée]tic[oa]", r"\bDNA\b",
    ],
}
_COMPILED = {k: re.compile("|".join(f"(?:{t})" for t in terms), re.IGNORECASE) for k, terms in _TERMS.items()}
# Siglas que só valem em maiúsculas (evita "ist", "dna" em palavras comuns)
_CASE_SENSITIVE = {"HIV", "AIDS", "IST", "DST", "DNA", "CID"}


class ContextDetector(Detector):
    name = "contexto"

    def detect(self, seg: Segment) -> list:
        findings = []
        for kind, rx in _COMPILED.items():
            terms = []
            for m in rx.finditer(seg.text):
                term = m.group(0).strip()
                head = re.sub(r"[^A-Za-z]", "", term.split()[0]) if term.split() else ""
                if head.upper() in _CASE_SENSITIVE and head != head.upper():
                    continue
                if term.lower() not in [t.lower() for t in terms]:
                    terms.append(term)
            if terms:
                joined = ", ".join(terms)
                findings.append(Finding(
                    file=seg.file, location=seg.location, kind=kind, category=SENSIVEL,
                    value=joined, masked=joined, detector=self.name, priority=50,
                ))
        return findings
