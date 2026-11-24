"""Gera documentos FICTÍCIOS (txt, csv, xlsx, docx, pdf) com gabarito (ground truth).

Todos os dados são sintéticos (CPFs/CNPJs válidos pelo dígito verificador, mas inexistentes).
Inclui de propósito casos difíceis: CPFs inválidos, números de processo, valores, nomes de
órgãos e frases com palavras-chave fora de contexto médico, para medir falsos positivos.

Uso: python tools/generate_samples.py [pasta_saida] [semente]
"""
import csv
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from dlgpd.validators import cpf_valid, phone_valid  # noqa: E402

FIRST = ["Maria", "José", "Ana", "João", "Francisca", "Antônio", "Luciana", "Carlos", "Raimunda",
         "Pedro", "Juliana", "Marcos", "Fernanda", "Paulo", "Camila", "Rafael", "Beatriz", "Lucas",
         "Aline", "Gabriel", "Helena", "Davi", "Larissa", "Mateus", "Isabela", "Thiago"]
LAST = ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa", "Carvalho", "Almeida",
        "Ribeiro", "Barbosa", "Nogueira", "Araújo", "Moura", "Cardoso", "Teixeira", "Rocha", "Mendes",
        "Batista", "Fonseca"]
PARTICLES = ["", "", "da", "de", "dos", "das"]
STREETS = ["das Flores", "Sete de Setembro", "Coelho Rodrigues", "Frei Serafim", "Barroso",
           "Álvaro Mendes", "Simplício Mendes", "João XXIII", "Elias Ximenes", "Desembargador Freitas",
           "Rui Barbosa", "Miguel Rosa", "Pires de Castro"]
PREFIXES = ["Rua", "Rua", "Av.", "Avenida", "Travessa", "Alameda"]
DOMAINS = ["gmail.com", "hotmail.com", "outlook.com", "yahoo.com.br", "uol.com.br"]
DDDS = [86, 86, 86, 85, 89, 98, 88, 11, 21]
ORGS = ["Secretaria Municipal de Educação", "Banco do Brasil S.A.", "Hospital Getúlio Vargas",
        "Universidade Federal do Piauí", "Câmara Municipal de Teresina", "Tribunal de Justiça do Estado do Piauí",
        "Fundação Municipal de Saúde", "Companhia de Água e Esgoto"]
CARGOS = ["Analista Administrativo", "Técnico de Enfermagem", "Professor", "Assistente Social",
          "Motorista", "Auxiliar de Serviços Gerais", "Engenheiro Civil", "Contador"]

SENSITIVE = {
    "SAUDE": ["O paciente apresenta diagnóstico de diabetes tipo 2 e faz uso contínuo de medicamento.",
              "Laudo médico: CID-10 I10 (hipertensão arterial).",
              "Atestado médico emitido por quadro de depressão.",
              "Encaminhado para quimioterapia após diagnóstico de câncer."],
    "RELIGIAO": ["Declara-se católico praticante.", "Solicitou dispensa por convicção religiosa (evangélico).",
                 "Informou que frequenta o culto aos sábados por ser adventista da religião cristã."],
    "SINDICATO": ["Consta filiação sindical ativa desde 2019.", "O servidor é sindicalizado e contribui mensalmente."],
    "POLITICA": ["Registra filiação partidária em partido local.", "Manifestou opinião política durante o evento."],
    "ETNIA": ["Cor: parda (autodeclarado).", "Origem racial ou étnica: indígena."],
    "SEXUAL": ["Registrou orientação sexual homossexual no formulário.", "Cadastro com campo de vida sexual preenchido."],
    "BIOMETRICO": ["Cadastro de impressão digital e reconhecimento facial para controle de acesso.",
                   "Anexado exame de DNA para fins de comprovação de filiação."],
}
HARD_NEGATIVES = [  # contêm palavra-chave, mas NÃO são dado sensível
    "A obra causou transtorno aos moradores da região.",
    "O diagnóstico organizacional do setor foi concluído em março.",
]


def _plain(s):
    s = unicodedata.normalize("NFKD", s)
    return re.sub(r"[^a-z]", "", "".join(c for c in s if not unicodedata.combining(c)).lower())


class F:
    """Contexto de um arquivo: gera valores e registra o gabarito."""

    def __init__(self, rnd, name, gt):
        self.r, self.name, self.gt = rnd, name, gt

    def _add(self, kind, value=""):
        self.gt.append({"file": self.name, "kind": kind, "value": value})

    # ---- entidades com gabarito ----
    def nome(self, upper=False):
        n = f"{self.r.choice(FIRST)} {self.r.choice(PARTICLES)} {self.r.choice(LAST)}".replace("  ", " ")
        if self.r.random() < 0.3:
            n += f" {self.r.choice(LAST)}"
        self._add("PESSOA", n)
        return n.upper() if upper else n

    def cpf(self, raw=None):
        d = [self.r.randint(0, 9) for _ in range(9)]
        for i in (9, 10):
            d.append((sum(d[j] * (i + 1 - j) for j in range(i)) * 10 % 11) % 10)
        s = "".join(map(str, d))
        if len(set(s)) == 1:
            return self.cpf(raw)
        raw = self.r.random() < 0.15 if raw is None else raw
        out = s if raw else f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}"
        self._add("CPF", out)
        return out

    def cnpj(self):
        d = [self.r.randint(0, 9) for _ in range(8)] + [0, 0, 0, self.r.randint(1, 9)]
        for n, w in ((12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]), (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])):
            r = sum(d[i] * w[i] for i in range(n)) % 11
            d.append(0 if r < 2 else 11 - r)
        s = "".join(map(str, d))
        out = f"{s[:2]}.{s[2:5]}.{s[5:8]}/{s[8:12]}-{s[12:]}"
        self._add("CNPJ", out)
        return out

    def tel(self):
        ddd = self.r.choice(DDDS)
        cel = f"9{self.r.randint(1000, 9999)}{self.r.randint(1000, 9999)}"
        fixo = f"{self.r.randint(2, 5)}{self.r.randint(100, 999)}{self.r.randint(1000, 9999)}"
        kind = self.r.choice(["par", "esp", "mais55", "raw", "fixo"])
        out = {"par": f"({ddd}) {cel[:5]}-{cel[5:]}", "esp": f"{ddd} {cel[:5]}-{cel[5:]}",
               "mais55": f"+55 {ddd} {cel[:5]}-{cel[5:]}", "raw": f"{ddd}{cel}",
               "fixo": f"({ddd}) {fixo[:4]}-{fixo[4:]}"}[kind]
        self._add("TELEFONE", out)
        return out

    def email(self, nome=None):
        base = ".".join(_plain(p) for p in (nome or f"{self.r.choice(FIRST)} {self.r.choice(LAST)}").split()
                        if _plain(p) not in ("da", "de", "dos", "das"))[:28]
        out = f"{base}@{self.r.choice(DOMAINS)}"
        if self.r.random() < 0.15:
            out = out.upper()
        self._add("EMAIL", out)
        return out

    def cep(self, labeled=False):
        n = f"{self.r.randint(64000, 64099)}{self.r.randint(0, 999):03d}"
        out = f"{n[:5]}-{n[5:]}"
        if labeled and self.r.random() < 0.3:
            out = n
        self._add("CEP", out)
        return out

    def rg(self):
        n = f"{self.r.randint(1, 9)}.{self.r.randint(100, 999)}.{self.r.randint(100, 999)}"
        out = f"{n}-{self.r.randint(0, 9)}" if self.r.random() < 0.5 else n.replace(".", "")
        self._add("RG", out)
        return out

    def placa(self):
        L = "ABCDEFGHJKLMNPRSTUVXZ"
        a = "".join(self.r.choice(L) for _ in range(3))
        out = f"{a}{self.r.randint(0, 9)}{self.r.choice(L)}{self.r.randint(10, 99)}" if self.r.random() < 0.6 \
            else f"{a}-{self.r.randint(1000, 9999)}"
        self._add("PLACA", out)
        return out

    def nasc(self):
        out = f"{self.r.randint(1, 28):02d}/{self.r.randint(1, 12):02d}/{self.r.randint(1955, 2003)}"
        self._add("DATA_NASCIMENTO", out)
        return out

    def endereco(self):
        num = self.r.randint(1, 3000)
        out = f"{self.r.choice(PREFIXES)} {self.r.choice(STREETS)}, {'nº ' if self.r.random() < 0.2 else ''}{num}"
        self._add("ENDERECO", out)
        return out

    def sens(self, kind):
        self._add(kind)
        return self.r.choice(SENSITIVE[kind])

    # ---- ruído (sem gabarito: qualquer detecção vira falso positivo) ----
    def cpf_invalido(self):
        while True:
            s = "".join(str(self.r.randint(0, 9)) for _ in range(11))
            if not cpf_valid(s) and not phone_valid(s):
                return f"{s[:3]}.{s[3:6]}.{s[6:9]}-{s[9:]}" if self.r.random() < 0.7 else s

    def processo(self):
        return f"{self.r.randint(1, 9999999):07d}-{self.r.randint(10, 99)}.{self.r.randint(2019, 2025)}.8.18.{self.r.randint(1, 9999):04d}"

    def protocolo(self):
        return f"Protocolo nº {self.r.randint(2022, 2025)}/{self.r.randint(1, 99999):06d}"

    def valor(self):
        return f"R$ {self.r.randint(1, 99)}.{self.r.randint(100, 999)},{self.r.randint(10, 99)}"

    def data(self):
        return f"{self.r.randint(1, 28):02d}/{self.r.randint(1, 12):02d}/{self.r.randint(2023, 2025)}"

    def org(self):
        return self.r.choice(ORGS)

    def ruido(self):
        return self.r.choice([
            f"Conforme {self.protocolo()}, o valor de {self.valor()} foi empenhado em {self.data()}.",
            f"Processo {self.processo()} em tramitação na {self.org()}.",
            f"Código de rastreio {self.cpf_invalido()} informado no sistema.",
            f"A reunião com a {self.org()} foi remarcada para {self.data()}.",
            f"Nota fiscal nº {self.r.randint(1000, 99999)} no valor de {self.valor()}.",
        ])


def build(out: Path, seed: int = 42):
    from docx import Document
    from openpyxl import Workbook
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    rnd = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    gt = []

    def ctx(name):
        return F(rnd, name, gt)

    def write_txt(name, lines):
        (out / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---------------- TXT (8) ----------------
    f = ctx("ata_reuniao_01.txt")
    write_txt(f.name, [f"ATA DE REUNIÃO – {f.org()}", f"Data: {f.data()}", "Participantes:",
                       f"- {f.nome()}", f"- {f.nome()}", f"- {f.nome()}",
                       f.ruido(), f.ruido(), "Pauta: revisão do cronograma e do orçamento do exercício.",
                       "Encaminhamentos: cada setor deverá enviar o relatório até o dia 30."])
    f = ctx("ata_reuniao_02.txt")  # documento sem dados pessoais, com falsos positivos de palavras-chave
    write_txt(f.name, [f"ATA DE REUNIÃO – {f.org()}", f.ruido(), f.ruido(), f.ruido(), HARD_NEGATIVES[0],
                       HARD_NEGATIVES[1], "Aprovado o plano de trabalho para o próximo trimestre."])
    for i in (1, 2, 3):
        f = ctx(f"ficha_cadastro_0{i}.txt")
        nome = f.nome()
        lines = ["FICHA DE CADASTRO", f"Nome: {nome}", f"CPF: {f.cpf()}", f"RG: {f.rg()}",
                 f"Data de nascimento: {f.nasc()}", f"Endereço: {f.endereco()} - Centro, Teresina/PI",
                 f"CEP: {f.cep(labeled=True)}", f"Telefone: {f.tel()}", f"E-mail: {f.email(nome)}"]
        if i == 3:
            lines += [f.sens("RELIGIAO"), f.sens("ETNIA")]
        lines.append(f.ruido())
        write_txt(f.name, lines)
    f = ctx("email_exportado_01.txt")
    a, b = f.nome(), f.nome()
    write_txt(f.name, [f"De: {a} <{f.email(a)}>", f"Para: {b} <{f.email(b)}>", f"Data: {f.data()}",
                       "Assunto: Afastamento e documentação",
                       f"Prezada {b.split()[0]}, conforme conversamos, segue a documentação. {f.sens('SAUDE')}",
                       f"Qualquer dúvida, ligue para {f.tel()}.", "Atenciosamente,", a, f.org()])
    # o nome da assinatura repete o remetente (gabarito)
    f.gt.append({"file": f.name, "kind": "PESSOA", "value": a})
    f = ctx("relato_ocorrencia_01.txt")
    n1, n2 = f.nome(), f.nome()
    write_txt(f.name, [
        f"No dia {f.data()}, o Sr. {n1}, CPF {f.cpf()}, residente na {f.endereco()}, compareceu à {f.org()} "
        f"e relatou que o veículo de placa {f.placa()} foi danificado.",
        f"A testemunha, {n2}, pode ser contatada pelo telefone {f.tel()}.",
        f"Consta no registro o processo {f.processo()}.",
        f.sens("SAUDE")])
    f = ctx("anotacoes_internas_01.txt")  # só ruído
    write_txt(f.name, [f.ruido() for _ in range(6)] + ["Lembrar de revisar o contrato de manutenção."])

    # ---------------- CSV (4) ----------------
    f = ctx("clientes.csv")
    with open(out / f.name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "nome", "cpf", "telefone", "email", "cep", "ultima_compra"])
        for i in range(1, 31):
            nome = f.nome(upper=rnd.random() < 0.25)
            w.writerow([i, nome, f.cpf(), f.tel(), f.email(nome), f.cep(), f.valor()])
    f = ctx("funcionarios.csv")
    with open(out / f.name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["matricula", "nome", "cpf", "rg", "nascimento", "cargo", "filiado_sindicato"])
        for i in range(1, 26):
            w.writerow([1000 + i, f.nome(upper=rnd.random() < 0.25), f.cpf(), f.rg(), f.nasc(),
                        rnd.choice(CARGOS), rnd.choice(["sim", "não"])])
        # A coluna "filiado_sindicato" indica filiação sindical, mas o nome em snake_case não casa
        # com os termos do detector. Mantido no gabarito de propósito: é uma limitação real.
        f._add("SINDICATO")
    f = ctx("atendimentos.csv")
    with open(out / f.name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["paciente", "data", "diagnostico", "observacao"])
        for _ in range(15):
            w.writerow([f.nome(), f.data(), rnd.choice(["diabetes", "hipertensão", "ansiedade", "tuberculose"]),
                        "retorno em 30 dias"])
        f._add("SAUDE")
    f = ctx("estoque.csv")  # sem dados pessoais
    with open(out / f.name, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["codigo", "produto", "quantidade", "valor_unitario", "fornecedor"])
        for i in range(1, 26):
            w.writerow([f"P{i:04d}", rnd.choice(["Papel A4", "Caneta", "Toner", "Cadeira", "Mesa"]),
                        rnd.randint(1, 500), f.valor(), f.org()])

    # ---------------- XLSX (4) ----------------
    f = ctx("folha_pagamento.xlsx")
    wb = Workbook()
    for month in ("Janeiro", "Fevereiro"):
        ws = wb.active if month == "Janeiro" else wb.create_sheet(month)
        ws.title = month
        ws.append(["Nome", "CPF", "Cargo", "Salário bruto"])
        for _ in range(12):
            ws.append([f.nome(upper=rnd.random() < 0.3), f.cpf(), rnd.choice(CARGOS), f.valor()])
    wb.save(out / f.name)
    f = ctx("alunos.xlsx")
    wb = Workbook(); ws = wb.active; ws.title = "Turma A"
    ws.append(["Aluno", "Nascimento", "Endereço", "Responsável", "Telefone", "Religião", "Cor/Raça"])
    for _ in range(12):
        ws.append([f.nome(), f.nasc(), f.endereco(), f.nome(), f.tel(),
                   rnd.choice(["Católica", "Evangélica", "Espírita", "Sem religião"]),
                   rnd.choice(["Parda", "Branca", "Preta"])])
    f._add("RELIGIAO"); f._add("ETNIA")
    wb.save(out / f.name)
    f = ctx("atendimentos.xlsx")
    wb = Workbook(); ws = wb.active; ws.title = "Atendimentos"
    ws.append(["Paciente", "CPF", "CID", "Diagnóstico", "Medicamento"])
    for _ in range(10):
        ws.append([f.nome(), f.cpf(), rnd.choice(["E11", "I10", "F41", "A15"]),
                   rnd.choice(["diabetes", "hipertensão", "ansiedade"]), "uso contínuo"])
    f._add("SAUDE")
    wb.save(out / f.name)
    f = ctx("estoque.xlsx")
    wb = Workbook(); ws = wb.active; ws.title = "Estoque"
    ws.append(["Código", "Produto", "Quantidade", "Fornecedor"])
    for i in range(1, 21):
        ws.append([f"P{i:04d}", rnd.choice(["Papel A4", "Toner", "Cadeira"]), rnd.randint(1, 300), f.org()])
    wb.save(out / f.name)

    # ---------------- DOCX (4) ----------------
    f = ctx("laudo_medico.docx")
    d = Document()
    d.add_heading("Laudo Médico", 1)
    nome = f.nome()
    d.add_paragraph(f"Paciente: {nome}, CPF {f.cpf()}, nascido em {f.nasc()}.")
    d.add_paragraph(f.sens("SAUDE"))
    d.add_paragraph(f.sens("BIOMETRICO"))
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "Exame", "Resultado"
    t.cell(1, 0).text, t.cell(1, 1).text = "Glicemia", "140 mg/dL"
    d.add_paragraph(f"Contato: {f.tel()} / {f.email(nome)}")
    d.save(out / f.name)
    f = ctx("contrato_prestacao.docx")
    d = Document()
    d.sections[0].header.paragraphs[0].text = f"{f.org()} – Contrato de prestação de serviços"
    d.add_heading("Contrato de Prestação de Serviços", 1)
    d.add_paragraph(f"CONTRATANTE: {f.org()}, CNPJ {f.cnpj()}, representada por {f.nome()}, CPF {f.cpf()}.")
    d.add_paragraph(f"CONTRATADA: {f.nome()}, MEI, CNPJ {f.cnpj()}, com sede na {f.endereco()}, CEP {f.cep()}.")
    d.add_paragraph(f"O valor total é de {f.valor()}, conforme {f.protocolo()}.")
    d.add_paragraph(f"Testemunhas: {f.nome()}, CPF {f.cpf()}; {f.nome()}, CPF {f.cpf()}.")
    d.save(out / f.name)
    f = ctx("requerimento_sindical.docx")
    d = Document()
    d.add_heading("Requerimento", 1)
    d.add_paragraph(f"Eu, {f.nome()}, matrícula {rnd.randint(1000, 9999)}, venho requerer a atualização cadastral.")
    d.add_paragraph(f.sens("SINDICATO"))
    d.add_paragraph(f.sens("POLITICA"))
    d.add_paragraph(f"Telefone para contato: {f.tel()}. E-mail: {f.email()}.")
    d.save(out / f.name)
    f = ctx("memorando_interno.docx")  # sem dados pessoais
    d = Document()
    d.add_heading("Memorando", 1)
    for _ in range(4):
        d.add_paragraph(f.ruido())
    d.add_paragraph(HARD_NEGATIVES[0])
    d.save(out / f.name)

    # ---------------- PDF (2) ----------------
    def write_pdf(name, lines):
        c = canvas.Canvas(str(out / name), pagesize=A4)
        y = 800
        for line in lines:
            c.drawString(50, y, line)
            y -= 20
        c.save()

    f = ctx("ficha_funcionario.pdf")
    nome = f.nome()
    write_pdf(f.name, ["FICHA DO FUNCIONÁRIO", f"Nome: {nome}", f"CPF: {f.cpf()}", f"RG: {f.rg()}",
                       f"Data de nascimento: {f.nasc()}", f"Endereço: {f.endereco()}, Teresina/PI",
                       f"Telefone: {f.tel()}", f"E-mail: {f.email(nome)}", f.sens("SEXUAL"), f.ruido()])
    f = ctx("relatorio_trimestral.pdf")  # sem dados pessoais
    write_pdf(f.name, ["RELATÓRIO TRIMESTRAL", f.ruido(), f.ruido(), f.ruido(), "Resultados dentro do esperado."])

    (out / "ground_truth.json").write_text(json.dumps(gt, ensure_ascii=False, indent=1), encoding="utf-8")
    n_files = len([p for p in out.iterdir() if p.name != "ground_truth.json"])
    print(f"{n_files} arquivos e {len(gt)} itens de gabarito gerados em {out}")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else "samples"), int(sys.argv[2]) if len(sys.argv) > 2 else 42)
