"""Detector de entidades nomeadas (nomes de pessoas e locais) com spaCy."""
import re
from ..models import Finding, Segment, PESSOAL, POTENCIAL
from ..masking import mask
from .base import Detector


# Prefixos que indicam instituição/lugar, não pessoa ("Hospital Getúlio Vargas", "Rua João Pessoa").
_INSTITUTIONAL = {"hospital", "colégio", "colegio", "escola", "universidade", "fundação", "fundacao",
                  "instituto", "clínica", "clinica", "banco", "praça", "praca", "rua", "avenida", "av",
                  "travessa", "alameda", "estádio", "estadio", "ginásio", "ginasio", "aeroporto",
                  "teatro", "museu", "biblioteca", "fórum", "forum", "tribunal", "câmara", "camara",
                  "prefeitura", "secretaria", "ministério", "ministerio", "cemitério", "cemiterio"}


def _normalize_case(text: str) -> str:
    """Textos em CAIXA ALTA (comuns em planilhas) derrubam o NER; título preserva o tamanho."""
    letters = [c for c in text if c.isalpha()]
    return text.title() if letters and all(c.isupper() for c in letters) else text


def _institutional_context(text: str, start: int, ent_text: str) -> bool:
    first = ent_text.split()[0].lower().strip(".,;:")
    before = re.findall(r"[A-Za-zÀ-ú]+", text[max(0, start - 20):start])
    prev = before[-1].lower() if before else ""
    return first in _INSTITUTIONAL or prev in _INSTITUTIONAL


class NerDetector(Detector):
    name = "ner-spacy"

    def __init__(self, model: str = "pt_core_news_lg", min_words: int = 2, include_locations: bool = False):
        import spacy  # import tardio: o restante da ferramenta funciona sem spaCy
        self.nlp = spacy.load(model, disable=["parser", "lemmatizer", "attribute_ruler", "morphologizer"])
        self.min_words = min_words
        self.include_locations = include_locations

    @staticmethod
    def _worth_processing(text: str) -> bool:
        return len(text) >= 5 and len(re.findall(r"[A-Za-zÀ-ú]{2,}", text)) >= 2

    def detect(self, seg: Segment) -> list:
        return self.detect_many([seg])

    def detect_many(self, segments: list) -> list:
        """Processa vários segmentos em lote (muito mais rápido que um a um)."""
        todo = [s for s in segments if self._worth_processing(s.text)]
        findings = []
        for seg, doc in zip(todo, self.nlp.pipe((_normalize_case(s.text) for s in todo), batch_size=64)):
            for ent in doc.ents:
                text = seg.text[ent.start_char:ent.end_char].strip()  # valor original (sem title())
                if ent.label_ == "PER":
                    if len(text.split()) < self.min_words or re.search(r"\d", text):
                        continue
                    if _institutional_context(seg.text, ent.start_char, text):
                        continue
                    findings.append(Finding(
                        file=seg.file, location=seg.location, kind="PESSOA", category=PESSOAL,
                        value=text, masked=mask("PESSOA", text), detector=self.name,
                        start=ent.start_char, end=ent.end_char, priority=20))
                elif ent.label_ == "LOC" and self.include_locations:
                    findings.append(Finding(
                        file=seg.file, location=seg.location, kind="LOCAL", category=POTENCIAL,
                        value=text, masked=mask("LOCAL", text), detector=self.name,
                        start=ent.start_char, end=ent.end_char, priority=21))
        return findings
