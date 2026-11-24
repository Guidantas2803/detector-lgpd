"""Interface comum dos detectores.

Todo detector recebe segmentos de texto e devolve achados (Finding). O Scanner só conhece
esta interface: para acrescentar um detector, basta escrever uma classe que herde de
Detector e passá-la ao Scanner (Scanner(detectors=[...])), sem alterar o Scanner.
"""
from abc import ABC, abstractmethod


class Detector(ABC):
    name = "detector"

    @abstractmethod
    def detect(self, seg) -> list:
        """Achados em um segmento."""

    def detect_many(self, segments: list) -> list:
        """Achados em vários segmentos. Padrão: um a um; detectores caros (NER) processam em lote."""
        found = []
        for seg in segments:
            found += self.detect(seg)
        return found
