"""Leitura de arquivos e conversão em segmentos de texto com localização."""
import csv
import re
from pathlib import Path
from .models import Segment

SUPPORTED = {".txt", ".md", ".log", ".csv", ".xlsx", ".docx", ".pdf"}


def _txt(path: Path, name: str):
    text = path.read_text(encoding="utf-8", errors="replace")
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            yield Segment(name, f"linha {i}", line)


# Colunas cujo rótulo é necessário para reconhecer o valor (ex.: coluna "RG" com 1234567).
_CONTEXT_HEADER = re.compile(r"(?i)\b(rg|cep|nasc\w*|data\s+de\s+nasc\w*)\b")


def _with_header(header: str, cell: str) -> str:
    """Contexto de coluna: acrescenta o cabeçalho ao valor quando ele é essencial à detecção."""
    return f"{header}: {cell}" if header and _CONTEXT_HEADER.search(header) else cell


def _csv(path: Path, name: str):
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(raw.splitlines(), dialect))
    header = rows[0] if rows else []
    # Cabeçalhos também são analisados: uma coluna "Diagnóstico" já é um indício.
    for c, h in enumerate(header, 1):
        if h.strip():
            yield Segment(name, f"cabeçalho, coluna {c}", h)
    for r, row in enumerate(rows[1:], 2):
        for c, cell in enumerate(row, 1):
            if cell.strip():
                col = header[c - 1] if c - 1 < len(header) and header[c - 1].strip() else str(c)
                yield Segment(name, f"linha {r}, coluna '{col}'", _with_header(col, cell))


def _xlsx(path: Path, name: str):
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        header = []
        for r, row in enumerate(ws.iter_rows(), 1):
            if r == 1:
                header = [str(c.value).strip() if c.value is not None else "" for c in row]
            for c, cell in enumerate(row):
                if cell.value is None:
                    continue
                text = str(cell.value).strip()
                if text:
                    if r > 1 and c < len(header):
                        text = _with_header(header[c], text)
                    yield Segment(name, f"{ws.title}!{cell.coordinate}", text)
    wb.close()


def _docx(path: Path, name: str):
    from docx import Document
    doc = Document(path)
    for i, p in enumerate(doc.paragraphs, 1):
        if p.text.strip():
            yield Segment(name, f"parágrafo {i}", p.text)
    for t, table in enumerate(doc.tables, 1):
        for r, row in enumerate(table.rows, 1):
            for c, cell in enumerate(row.cells, 1):
                if cell.text.strip():
                    yield Segment(name, f"tabela {t}, linha {r}, coluna {c}", cell.text)
    for s, section in enumerate(doc.sections, 1):  # cabeçalhos e rodapés também guardam dados
        for part, label in ((section.header, "cabeçalho"), (section.footer, "rodapé")):
            for p in part.paragraphs:
                if p.text.strip():
                    yield Segment(name, f"{label} (seção {s})", p.text)


def _pdf(path: Path, name: str):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    for n, page in enumerate(reader.pages, 1):
        for i, line in enumerate((page.extract_text() or "").splitlines(), 1):
            if line.strip():
                yield Segment(name, f"página {n}, linha {i}", line)


_READERS = {".txt": _txt, ".md": _txt, ".log": _txt, ".csv": _csv,
            ".xlsx": _xlsx, ".docx": _docx, ".pdf": _pdf}


def extract(path: Path, root: Path):
    """Gera os segmentos de um arquivo. Lança exceção se o arquivo estiver corrompido."""
    name = str(path.relative_to(root)) if path.is_relative_to(root) else path.name
    yield from _READERS[path.suffix.lower()](path, name)
