"""Orquestra a varredura: extração -> detectores -> resolução de sobreposições."""
from collections import defaultdict
from pathlib import Path

from .detectors import ContextDetector, NerDetector, RegexDetector
from .extractors import SUPPORTED, extract
from .models import ScanResult, Segment
import re


def resolve_overlaps(findings: list) -> list:
    """Dentro de um mesmo trecho, mantém só o achado de maior prioridade em cada região.

    Ex.: um CPF válido não deve ser também listado como telefone; um nome dentro de
    um endereço ("Rua João Pessoa, 10") não deve ser listado como pessoa.
    """
    spanned = sorted((f for f in findings if f.start >= 0),
                     key=lambda f: (f.priority, -(f.end - f.start), f.start))
    kept = []
    for f in spanned:
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return kept + [f for f in findings if f.start < 0]


class Scanner:
    def __init__(self, use_ner: bool = True, include_locations: bool = False,
                 model: str = "pt_core_news_lg", pseudonymize_paths: bool = False,
                 detectors: list = None):
        """`detectors`: lista de objetos com a interface Detector. Se omitida, usa a configuração
        padrão (regex, contexto e, se use_ner, NER). Acrescentar um detector não exige mudar esta classe."""
        self.pseudonymize_paths = pseudonymize_paths
        if detectors is None:
            detectors = [RegexDetector(), ContextDetector()]
            if use_ner:
                detectors.append(NerDetector(model, include_locations=include_locations))
        self.detectors = list(detectors)
        self.ner_enabled = any(isinstance(d, NerDetector) for d in self.detectors)

    def _detect(self, segments: list) -> list:
        found = []
        for d in self.detectors:
            found += d.detect_many(segments)
        return found

    def _files(self, root: Path):
        if root.is_file():
            yield root
            return
        for p in sorted(root.rglob("*")):
            if p.is_file():
                yield p

    def _path_findings(self, rel: str) -> list:
        """O nome do arquivo e as pastas também podem conter dado pessoal
        (ex.: laudo_52998224725.pdf, Contrato Maria da Silva.docx).

        Cada parte do caminho (pasta ou nome sem extensão) é analisada separadamente, com
        "_" trocado por espaço; as posições são reajustadas para o caminho original.
        """
        found, off = [], 0
        parts = re.split(r"([/\\])", rel)
        for i, part in enumerate(parts):
            if part in ("/", "\\") or not part:
                off += len(part)
                continue
            stem = part if i < len(parts) - 1 or "." not in part else part.rsplit(".", 1)[0]
            seg = Segment(rel, "nome do arquivo", stem.replace("_", " "))
            for f in resolve_overlaps(self._detect([seg])):
                if f.start >= 0:
                    f.start += off; f.end += off
                found.append(f)
            off += len(part)
        return found

    def _mask_path(self, rel: str, findings: list) -> str:
        out = rel
        for f in sorted((f for f in findings if f.start >= 0), key=lambda f: -f.start):
            masked = f.masked
            if masked.endswith(".") and out[f.end:f.end + 1] == ".":
                masked = masked[:-1]          # "Maria S." + ".docx" -> "Maria S.docx"
            out = out[:f.start] + masked + out[f.end:]
        return out

    def scan(self, root) -> ScanResult:
        root = Path(root)
        base = root.parent if root.is_file() else root
        result = ScanResult(root=str(root), ner_enabled=self.ner_enabled)
        for path in self._files(root):
            rel = str(path.relative_to(base))
            in_name = self._path_findings(rel)
            if self.pseudonymize_paths:
                n = len(result.display) + 1
                result.display[rel] = f"ARQ-{n:03d}{path.suffix.lower()}"
            elif in_name:
                result.display[rel] = self._mask_path(rel, in_name)
            if path.suffix.lower() not in SUPPORTED:
                result.skipped.append((rel, "formato não suportado"))
                continue
            try:
                segments = list(extract(path, base))
            except Exception as exc:  # arquivo corrompido, protegido por senha etc.
                result.skipped.append((rel, f"erro de leitura: {type(exc).__name__}"))
                continue
            result.files_scanned.append(rel)
            found = list(in_name) + self._detect(segments)
            by_location = defaultdict(list)
            for f in found:
                by_location[f.location].append(f)
            for location in by_location:
                result.findings += resolve_overlaps(by_location[location])
        return result
