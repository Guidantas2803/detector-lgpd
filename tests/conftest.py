import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    """Documentos fictícios gerados com uma semente própria dos testes."""
    from generate_samples import build
    out = tmp_path_factory.mktemp("samples")
    build(out, seed=2024)
    return out


@pytest.fixture(scope="session")
def ner_available():
    try:
        import spacy
        spacy.load("pt_core_news_lg")
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def scan_result(samples, ner_available):
    from dlgpd.scanner import Scanner
    return Scanner(use_ner=ner_available).scan(samples)
