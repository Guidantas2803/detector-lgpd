"""Gera os diagramas UML (classes, componentes, casos de uso) em Graphviz."""
import subprocess

FONT = "DejaVu Sans"
HDR = f'''digraph G {{
  graph [fontname="{FONT}", pad=0.3, bgcolor="white"];
  node  [fontname="{FONT}", fontsize=11];
  edge  [fontname="{FONT}", fontsize=10, color="#444444"];
'''


def cls(name, attrs=(), methods=(), stereotype=None, fill="#F4F6F8", head="#D6E4F0"):
    def lines(xs):
        return "".join(f'{x}<BR ALIGN="LEFT"/>' for x in xs) or " "
    st = f'<FONT POINT-SIZE="9">«{stereotype}»</FONT><BR/>' if stereotype else ""
    return (f'  {name} [shape=plain, label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="5" BGCOLOR="{fill}">'
            f'<TR><TD BGCOLOR="{head}">{st}<B>{name}</B></TD></TR><HR/>'
            f'<TR><TD ALIGN="LEFT">{lines(attrs)}</TD></TR><HR/>'
            f'<TR><TD ALIGN="LEFT">{lines(methods)}</TD></TR></TABLE>>];\n')


def classes():
    d = HDR + '  rankdir=TB; nodesep=0.55; ranksep=1.0; splines=polyline;\n'
    d += cls("Scanner", ["- detectors : list&lt;Detector&gt;", "- pseudonymize_paths : bool"],
             ["+ scan(root) : ScanResult", "- _detect(list&lt;Segment&gt;) : list&lt;Finding&gt;", "- _path_findings(rel) : list&lt;Finding&gt;", "- _mask_path(rel, achados) : str"])
    d += cls("Detector", ["+ name : str"], ["+ detect(Segment) : list&lt;Finding&gt;  {abstrato}", "+ detect_many(list&lt;Segment&gt;) : list&lt;Finding&gt;"], "classe abstrata", "#FFF6DD", "#F5E3A8")
    d += cls("RegexDetector", ['+ name = "regex"'], ["+ detect(Segment) : list&lt;Finding&gt;"])
    d += cls("ContextDetector", ['+ name = "contexto"'], ["+ detect(Segment) : list&lt;Finding&gt;"])
    d += cls("NerDetector", ['+ name = "ner-spacy"', "- min_words : int", "- include_locations : bool"],
             ["+ detect(Segment) : list&lt;Finding&gt;", "+ detect_many(list&lt;Segment&gt;) : list&lt;Finding&gt;  {em lote}"])
    d += cls("ScanResult", ["+ root : str", "+ files_scanned : list", "+ findings : list", "+ skipped : list", "+ ner_enabled : bool", "+ display : dict"], ["+ shown(rel) : str"])
    d += cls("Finding", ["+ file : str", "+ location : str", "+ kind : str", "+ category : str", "+ value : str",
                         "+ masked : str", "+ detector : str", "+ priority : int"], [])
    d += cls("Segment", ["+ file : str", "+ location : str", "+ text : str"], [])
    d += '  {rank=same; Scanner; Detector;}\n  {rank=same; ScanResult; RegexDetector; ContextDetector; NerDetector; Segment;}\n'
    d += '  ScanResult -> RegexDetector -> ContextDetector -> NerDetector -> Segment [style=invis];\n'
    # composição / agregação (losango no lado do todo)
    d += '  Scanner -> Detector [dir=both, arrowtail=odiamond, arrowhead=vee, taillabel="1", headlabel="1..*  "];\n'
    # herança (triângulo vazado na classe abstrata)
    for c in ("RegexDetector", "ContextDetector", "NerDetector"):
        d += f'  Detector -> {c} [dir=back, arrowtail=empty];\n'
    d += '  Scanner -> ScanResult [style=dashed, arrowhead=vee, label=" cria"];\n'
    d += '  ScanResult -> Finding [dir=both, arrowtail=odiamond, arrowhead=none, taillabel="1", headlabel="0..*"];\n'
    d += '  Detector -> Segment [style=dashed, arrowhead=vee, label=" lê"];\n'
    d += '  Detector -> Finding [style=dashed, arrowhead=vee, label=" produz", constraint=false];\n'
    return d + "}\n"


def components():
    d = HDR + '  rankdir=TB; nodesep=0.5; ranksep=0.8; compound=true;\n'
    comp = lambda n, l, fill="#DCEBF7": f'  {n} [shape=component, style=filled, fillcolor="{fill}", label="{l}"];\n'
    ext = lambda n, l: f'  {n} [shape=folder, style=filled, fillcolor="#EFEFEF", label="{l}"];\n'
    d += comp("cli", "CLI\\n(cli.py)")
    d += comp("scanner", "Scanner\\n(scanner.py)")
    d += comp("report", "Relatório\\n(report.py)")
    d += comp("evaluation", "Avaliação\\n(evaluation.py)")
    d += comp("extractors", "Extratores de arquivo\\n(extractors.py)")
    d += '  subgraph cluster_det { label="Detectores (detectors/)"; style="rounded,dashed"; color="#888888"; fontname="%s";\n' % FONT
    d += comp("base", "Detector\\n(base.py, interface)", "#FFF6DD")
    d += comp("regex", "RegexDetector", "#E3F1DF") + comp("context", "ContextDetector", "#E3F1DF") + comp("ner", "NerDetector", "#E3F1DF") + '  }\n'
    d += comp("validators", "Validadores\\n(validators.py)", "#FFF6DD") + comp("masking", "Mascaramento\\n(masking.py)", "#FFF6DD")
    d += comp("models", "Modelos\\n(models.py)", "#FFF6DD")
    d += ext("fs", "Arquivos\\n(txt, csv, xlsx, docx, pdf)")
    d += ext("spacy", "spaCy\\npt_core_news_lg")
    d += ext("libs", "openpyxl · python-docx\\n· pypdf")
    d += ext("out", "Relatórios\\n(xlsx, html, json)")
    d += ext("mapa", "mapa_de_caminhos_\\nCONFIDENCIAL.json")
    d += ext("gt", "Gabarito\\n(ground_truth.json)")
    E = lambda a, b, l="": f'  {a} -> {b} [arrowhead=vee, style=dashed{", label=\" "+l+"\"" if l else ""}];\n'
    d += E("cli", "scanner") + E("cli", "report") + E("cli", "evaluation")
    d += E("scanner", "extractors") + E("scanner", "base", "lista de") 
    d += E("regex", "base", "herda") + E("context", "base", "herda") + E("ner", "base", "herda")
    d += E("scanner", "masking", "nomes de arquivo")
    d += E("regex", "validators") + E("regex", "masking") + E("ner", "masking") + E("ner", "spacy")
    d += E("extractors", "fs", "lê") + E("extractors", "libs", "usa")
    d += E("report", "out", "grava") + E("report", "mapa", "grava (opcional)") + E("evaluation", "gt", "lê")
    d += E("scanner", "models") 
    d += '  {rank=same; report; evaluation; scanner;}\n  {rank=same; fs; libs; spacy; out; mapa; gt;}\n'
    return d + "}\n"


def usecases():
    d = HDR + '  rankdir=LR; nodesep=0.45; ranksep=1.3;\n'
    actor = lambda n, l: f'  {n} [shape=box, style="rounded,filled", fillcolor="#F4F6F8", label=<<FONT POINT-SIZE="9">«ator»</FONT><BR/><B>{l}</B>>];\n'
    uc = lambda n, l: f'  {n} [shape=ellipse, style=filled, fillcolor="#E8F1FB", label="{l}"];\n'
    d += actor("analista", "Analista de<BR/>conformidade<BR/>(DPO / auditor)")
    d += actor("pesq", "Pesquisador<BR/>(autor do TCC)")
    d += '  subgraph cluster_sys { label="Sistema dlgpd"; style=rounded; color="#555555"; fontname="%s";\n' % FONT
    d += uc("uc1", "UC01  Varrer pasta ou arquivo") + uc("uc2", "UC02  Gerar relatórios\\n(XLSX, HTML, JSON)")
    d += uc("uc3", "UC03  Consultar prioridade\\nde revisão por arquivo") + uc("uc4", "UC04  Avaliar o detector\\ncontra um gabarito")
    d += uc("uc5", "UC05  Gerar documentos\\nfictícios de teste")
    d += uc("uc6", "UC06  Detectar dados\\npessoais") + uc("uc7", "UC07  Sinalizar indícios de\\ncategorias sensíveis") + uc("uc8", "UC08  Mascarar valores\\ne nomes de arquivo")
    d += uc("uc9", "UC09  Pseudonimizar\\ncaminhos")
    d += '  }\n'
    A = lambda a, b: f'  {a} -> {b} [arrowhead=none];\n'
    I = lambda a, b, k="include": f'  {a} -> {b} [style=dashed, arrowhead=vee, label="«{k}»"];\n'
    d += A("analista", "uc1") + A("analista", "uc2") + A("analista", "uc3") + A("pesq", "uc4") + A("pesq", "uc5")
    d += I("uc1", "uc6") + I("uc1", "uc7") + I("uc2", "uc8") + I("uc4", "uc1")
    d += I("uc3", "uc2", "extend") + I("uc9", "uc2", "extend")
    return d + "}\n"


for name, fn in (("01_casos_de_uso", usecases), ("02_componentes", components), ("03_classes", classes)):
    open(f"{name}.dot", "w", encoding="utf-8").write(fn())
    subprocess.run(["dot", "-Tpng", "-Gdpi=170", f"{name}.dot", "-o", f"../{name}.png"], check=True)
    subprocess.run(["dot", "-Tsvg", f"{name}.dot", "-o", f"../{name}.svg"], check=True)
print("ok")
