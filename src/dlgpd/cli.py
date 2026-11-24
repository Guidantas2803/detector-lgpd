"""Interface de linha de comando: python -m dlgpd scan <pasta>"""
import argparse
import sys
import time

from .report import write_all
from .scanner import Scanner


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dlgpd", description="Detector de dados pessoais e sensíveis (LGPD)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="varre uma pasta (ou arquivo) e gera relatório")
    s.add_argument("path")
    s.add_argument("--out", default="relatorio", help="pasta de saída (padrão: relatorio)")
    s.add_argument("--formatos", default="xlsx,html,json")
    s.add_argument("--sem-ner", action="store_true", help="desativa o NER (só regex e contexto)")
    s.add_argument("--locais", action="store_true", help="inclui locais detectados pelo NER")
    s.add_argument("--modelo", default="pt_core_news_lg")
    s.add_argument("--pseudonimizar-caminhos", action="store_true",
                   help="troca nomes de arquivo por códigos (ARQ-001) e grava a correspondência à parte")
    e = sub.add_parser("evaluate", help="avalia o detector contra um gabarito (ground truth)")
    e.add_argument("samples", help="pasta com os documentos de teste")
    e.add_argument("--gabarito", default=None, help="JSON do gabarito (padrão: <samples>/ground_truth.json)")
    e.add_argument("--out", default="resultados")
    e.add_argument("--sem-ner", action="store_true")
    e.add_argument("--modelo", default="pt_core_news_lg")
    args = p.parse_args(argv)

    if args.cmd == "scan":
        t0 = time.time()
        scanner = Scanner(use_ner=not args.sem_ner, include_locations=args.locais, model=args.modelo,
                          pseudonymize_paths=args.pseudonimizar_caminhos)
        result = scanner.scan(args.path)
        paths = write_all(result, args.out, tuple(args.formatos.split(",")))
        print(f"{len(result.files_scanned)} arquivos varridos, {len(result.findings)} achados, "
              f"{len(result.skipped)} ignorados, em {time.time() - t0:.1f}s")
        for path in paths:
            print("  ->", path)
        return 0

    from .evaluation import evaluate, write_evaluation
    gt = args.gabarito or f"{args.samples}/ground_truth.json"
    scanner = Scanner(use_ner=not args.sem_ner, model=args.modelo)
    result = scanner.scan(args.samples)
    table = evaluate(result, gt)
    print(write_evaluation(table, args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
