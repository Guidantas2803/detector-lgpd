"""Geração dos relatórios (XLSX, HTML e JSON). Somente dados MASCARADOS são gravados."""
import html
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from .models import KIND_LABELS, PESSOAL, SENSIVEL, POTENCIAL

# Regra de risco por arquivo (heurística; os limiares são uma proposta do autor):
#   pontuação = 10 x categorias sensíveis distintas + 1 x tipos pessoais distintos
#   Alto  : qualquer dado sensível (LGPD, art. 11), independentemente do volume
#   Médio : sem sensível, com 3 ou mais tipos distintos de dado pessoal
#   Baixo : sem sensível, com 1 ou 2 tipos de dado pessoal
# Conta TIPOS e não ocorrências, para que o tamanho do arquivo não decida o nível, e o peso 10
# (maior que o número de tipos pessoais possíveis) garante que nenhum arquivo sem dado
# sensível fique à frente de um arquivo com dado sensível na ordenação.


def risk_level(sensitive_kinds: int, personal_kinds: int) -> str:
    if sensitive_kinds:
        return "Alto"
    if personal_kinds >= 3:
        return "Médio"
    return "Baixo" if personal_kinds else "Nenhum"


# Rótulo exibido nos relatórios: o nível ordena a revisão, não mede risco jurídico.
PRIORIDADE = {"Alto": "Alta", "Médio": "Média", "Baixo": "Baixa", "Nenhum": "Nenhuma"}


def summarize(result) -> dict:
    per_file = defaultdict(lambda: {"Pessoal": 0, "Sensível": 0, "Potencial": 0, "kinds": Counter(),
                                    "tp": set(), "ts": set()})
    for f in result.findings:
        per_file[f.file][f.category] += 1
        per_file[f.file]["kinds"][f.label] += 1
        if f.category == PESSOAL:
            per_file[f.file]["tp"].add(f.kind)
        elif f.category == SENSIVEL:
            per_file[f.file]["ts"].add(f.kind)
    files = []
    for name in result.files_scanned:
        d = per_file[name]
        score = 10 * len(d["ts"]) + len(d["tp"])
        files.append({"arquivo": result.shown(name), "pessoais": d["Pessoal"], "sensiveis": d["Sensível"],
                      "potenciais": d["Potencial"], "pontuacao": score, "risco": risk_level(len(d["ts"]), len(d["tp"])),
                      "tipos": ", ".join(f"{k} ({v})" for k, v in d["kinds"].most_common())})
    files.sort(key=lambda x: (-x["pontuacao"], x["arquivo"]))
    return {
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        # só o nome da pasta analisada: o caminho completo pode expor usuário ou estrutura interna
        "pasta": Path(result.root).name or result.root,
        "arquivos_varridos": len(result.files_scanned),
        "arquivos_com_pessoais": sum(1 for f in files if f["pessoais"]),
        "arquivos_com_achados": sum(1 for f in files if f["pessoais"] or f["sensiveis"] or f["potenciais"]),
        "arquivos_com_sensiveis": sum(1 for f in files if f["sensiveis"]),
        "arquivos_ignorados": len(result.skipped),
        "total_achados": len(result.findings),
        "ner": result.ner_enabled,
        "por_tipo": Counter(f.label for f in result.findings).most_common(),
        "arquivos": files,
    }


def _rows(result):
    for f in sorted(result.findings, key=lambda x: (x.file, x.location, x.kind)):
        yield [result.shown(f.file), f.location, f.label, f.category, f.masked, f.detector]


HEADERS = ["Arquivo", "Local", "Tipo de dado", "Categoria LGPD", "Trecho (mascarado)", "Detector"]


def write_xlsx(result, path: Path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    s = summarize(result)
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    bold = Font(bold=True)
    ws.append(["Relatório de varredura de dados pessoais (LGPD)"]); ws["A1"].font = Font(bold=True, size=14)
    for k, v in [("Gerado em", s["gerado_em"]), ("Pasta analisada", s["pasta"]),
                 ("Arquivos varridos", s["arquivos_varridos"]),
                 ("Arquivos com dados pessoais", s["arquivos_com_pessoais"]),
                 ("Arquivos com indícios sensíveis", s["arquivos_com_sensiveis"]),
                 ("Arquivos ignorados", s["arquivos_ignorados"]),
                 ("Total de achados", s["total_achados"]),
                 ("NER (spaCy) ativo", "sim" if s["ner"] else "não")]:
        ws.append([k, v])
    ws.append([])
    ws.append(["Achados por tipo", "Quantidade"]); ws.cell(ws.max_row, 1).font = bold; ws.cell(ws.max_row, 2).font = bold
    for k, v in s["por_tipo"]:
        ws.append([k, v])
    ws.column_dimensions["A"].width = 38; ws.column_dimensions["B"].width = 40

    wa = wb.create_sheet("Arquivos por risco")
    wa.title = "Prioridade de revisão"
    wa.append(["Arquivo", "Pessoais", "Indícios sensíveis", "Potenciais", "Pontuação", "Prioridade de revisão", "Tipos encontrados"])
    for f in s["arquivos"]:
        wa.append([f["arquivo"], f["pessoais"], f["sensiveis"], f["potenciais"], f["pontuacao"], PRIORIDADE[f["risco"]], f["tipos"]])
    colors = {"Alta": "F8CBAD", "Média": "FFE699", "Baixa": "C6E0B4"}
    for row in wa.iter_rows(min_row=2):
        fill = colors.get(row[5].value)
        if fill:
            row[5].fill = PatternFill("solid", fgColor=fill)

    wf = wb.create_sheet("Achados")
    wf.append(HEADERS)
    for r in _rows(result):
        wf.append(r)
    for sheet, widths in ((wa, [34, 10, 10, 10, 10, 10, 60]), (wf, [34, 30, 36, 14, 34, 12])):
        for c in sheet[1]:
            c.font = bold
        for i, w in enumerate(widths):
            sheet.column_dimensions["ABCDEFG"[i]].width = w
        sheet.freeze_panes = "A2"
    wi = wb.create_sheet("Ignorados")
    wi.append(["Arquivo", "Motivo"])
    for r in result.skipped:
        wi.append(list(r))
    wb.save(path)


def write_json(result, path: Path):
    s = summarize(result)
    s["achados"] = [dict(zip(["arquivo", "local", "tipo", "categoria", "trecho_mascarado", "detector"], r))
                    for r in _rows(result)]
    s["ignorados"] = [{"arquivo": result.shown(a), "motivo": b} for a, b in result.skipped]
    path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def write_html(result, path: Path):
    s = summarize(result)
    e = html.escape
    badge = {"Alto": "#c0392b", "Médio": "#e0a800", "Baixo": "#2e8b57", "Nenhum": "#7f8c8d"}
    files = "".join(
        f"<tr><td>{e(f['arquivo'])}</td><td>{f['pessoais']}</td><td>{f['sensiveis']}</td>"
        f"<td>{f['pontuacao']}</td><td><span class='b' style='background:{badge[f['risco']]}'>{PRIORIDADE[f['risco']]}</span></td>"
        f"<td>{e(f['tipos'])}</td></tr>" for f in s["arquivos"])
    rows = "".join("<tr>" + "".join(f"<td>{e(str(c))}</td>" for c in r) + "</tr>" for r in _rows(result))
    types = "".join(f"<li>{e(k)}: <b>{v}</b></li>" for k, v in s["por_tipo"])
    doc = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório de varredura LGPD</title><style>
body{{font-family:system-ui,Arial,sans-serif;margin:2rem;color:#222}}
h1{{margin-bottom:.2rem}} .cards{{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}}
.card{{background:#f4f6f8;border-radius:8px;padding:.8rem 1.2rem;min-width:140px}}
.card b{{display:block;font-size:1.6rem}} table{{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}}
th,td{{border:1px solid #d5d9dd;padding:.35rem .6rem;text-align:left}} th{{background:#eef1f4}}
.b{{color:#fff;padding:.1rem .5rem;border-radius:10px;font-size:.8rem}}
.note{{background:#fff8e1;border-left:4px solid #e0a800;padding:.6rem 1rem;margin:1rem 0}}
</style></head><body>
<h1>Relatório de varredura de dados pessoais (LGPD)</h1>
<small>Gerado em {s['gerado_em']} &middot; Pasta: {e(s['pasta'])}</small>
<div class="cards">
<div class="card"><b>{s['arquivos_varridos']}</b>arquivos varridos</div>
<div class="card"><b>{s['arquivos_com_pessoais']}</b>com dados pessoais</div>
<div class="card"><b>{s['arquivos_com_sensiveis']}</b>com indícios sensíveis</div>
<div class="card"><b>{s['total_achados']}</b>achados</div>
<div class="card"><b>{s['arquivos_ignorados']}</b>ignorados</div></div>
<div class="note">Os trechos aparecem mascarados (minimização de dados). A ferramenta apoia o mapeamento,
mas não substitui a análise humana: pode haver falsos positivos e falsos negativos. Termos de
categorias sensíveis são indícios: o dado só é sensível quando ligado a uma pessoa natural (LGPD, art. 5º, II).</div>
<h2>Achados por tipo</h2><ul>{types}</ul>
<h2>Arquivos por prioridade de revisão</h2>
<table><tr><th>Arquivo</th><th>Pessoais</th><th>Indícios sensíveis</th><th>Pontuação</th><th>Prioridade</th><th>Tipos</th></tr>{files}</table>
<h2>Todos os achados</h2>
<table><tr>{''.join(f'<th>{h}</th>' for h in HEADERS)}</tr>{rows}</table>
</body></html>"""
    path.write_text(doc, encoding="utf-8")


def write_all(result, out_dir, formats=("xlsx", "html", "json")) -> list:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    writers = {"xlsx": write_xlsx, "html": write_html, "json": write_json}
    paths = []
    if result.display and any(v.startswith("ARQ-") for v in result.display.values()):
        # tabela de correspondência código -> caminho real: fica separada do relatório e
        # não deve ser compartilhada junto com ele
        m = out / "mapa_de_caminhos_CONFIDENCIAL.json"
        m.write_text(json.dumps({v: k for k, v in result.display.items()}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
        paths.append(m)
    for fmt in formats:
        p = out / f"relatorio.{fmt}"
        writers[fmt](result, p)
        paths.append(p)
    return paths
