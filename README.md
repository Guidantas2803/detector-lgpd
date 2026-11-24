# dlgpd — Detector de dados pessoais e sensíveis (LGPD)

Ferramenta de linha de comando que varre uma pasta de arquivos não estruturados
(`.txt`, `.csv`, `.xlsx`, `.docx`, `.pdf`) e gera um relatório indicando **onde** há dados
pessoais e dados pessoais sensíveis (LGPD, Art. 5º, I e II), para apoiar o mapeamento de
dados (inventário/ROPA) em auditorias de conformidade.

## Instalação
```bash
pip install -r requirements.txt
pip install https://github.com/explosion/spacy-models/releases/download/pt_core_news_lg-3.8.0/pt_core_news_lg-3.8.0-py3-none-any.whl
```

## Uso
```bash
export PYTHONPATH=src                        # Windows (PowerShell): $env:PYTHONPATH="src"
python -m dlgpd scan <pasta> --out relatorio   # gera relatorio.xlsx, .html e .json
python -m dlgpd scan <pasta> --sem-ner         # só regex + contexto (mais rápido)
python -m dlgpd evaluate samples_teste --out resultados   # precisão/recall/F1
python tools/generate_samples.py samples 42    # gera documentos fictícios + gabarito
python -m pytest -q                            # testes automatizados
```

## Arquitetura
```
Arquivos -> extractors -> Segment(arquivo, local, texto)
                              |-> RegexDetector    (CPF, CNPJ, e-mail, telefone, CEP, RG, placa,
                              |                     data de nascimento, endereço) + dígito verificador
                              |-> ContextDetector  (dados sensíveis por termos: saúde, religião...)
                              |-> NerDetector      (nomes de pessoas, spaCy pt_core_news_lg)
                          scanner.resolve_overlaps (prioridade entre detectores)
                          -> report (XLSX/HTML/JSON, só dados mascarados)
                          -> evaluation (VP/FP/FN, precisão, recall, F1)
```
Cada detector é independente e implementa `detect(segment)`: adicionar um novo tipo de dado
não exige alterar os demais módulos.

## Decisões de projeto ligadas à LGPD
- **Minimização (Art. 6º, III):** relatórios gravam somente valores mascarados
  (`***.982.247-**`, `Maria S.`); dados sensíveis mostram apenas o termo que disparou a detecção.
  Há teste automatizado garantindo que nenhum valor bruto vaza para os relatórios.
- **CNPJ como "Potencial":** pessoa jurídica não é dado pessoal, mas o CNPJ de MEI/empresário
  individual pode identificar pessoa natural. Por isso ele não pontua no risco, não entra na
  contagem de "arquivos com dados pessoais" e fica fora das médias de dado pessoal na avaliação
  (nível "entidade (PJ)"). Reconhece o formato numérico e o alfanumérico (IN RFB nº 2.229/2024;
  o alfanumérico só é reconhecido com pontuação completa, para evitar falsos positivos).
- **Pontuação de risco por arquivo (heurística):** conta TIPOS distintos, não ocorrências.
  Alto = qualquer dado sensível (art. 11); Médio = sem sensível e 3+ tipos pessoais; Baixo = 1 ou 2 tipos.
  Pontuação = 10 × categorias sensíveis + 1 × tipos pessoais (nenhum arquivo sem sensível passa de um com sensível).
  Efeito conhecido: um único termo sensível (inclusive falso positivo) já deixa o arquivo em "Alto".

## Avaliação
Critério de acerto (entidades): por **arquivo + valor** normalizado (a posição não é exigida); cada
ocorrência esperada consome uma detectada (CPF repetido conta duas vezes); nomes/endereços aceitam
casamento tolerante (sem acento/caixa, um contendo o outro; "Maria Silva" não casa com "Maria da Silva").
Dados sensíveis: por arquivo + categoria. A tabela traz n, IC95% de Wilson do recall e marca n < 10 como
amostra insuficiente. Médias macro são calculadas por nível (entidade / arquivo); o CNPJ fica fora.
- Conjunto de **desenvolvimento** (semente 42): usado para analisar erros e ajustar o detector.
- Conjunto de **teste** (semente 7, nunca visto no ajuste): usado para os números finais.
- Pastas: `resultados_v1_baseline/` (antes dos ajustes), `resultados/` (dev, depois),
  `resultados_teste/` (conjunto de teste). Cada uma traz `avaliacao.md`, `.csv` e `analise_de_erros.json`.

## Comparação com o Presidio (baseline)
`python tools/baseline_presidio.py samples_teste resultados_baseline_presidio` (requer `pip install presidio-analyzer`).
Presidio 2.2.364 com spaCy `pt_core_news_lg` como motor de NLP para o idioma `pt` e os reconhecedores
**padrão** (lista em `resultados_baseline_presidio/reconhecedores_pt.txt`), sem nenhum reconhecedor brasileiro.
O Presidio tem `DATE_TIME` e `LOCATION`, então a comparação usa duas tabelas de mapeamento
(`mapeamento.json`): **estrito** (e-mail, telefone, pessoa) e **ampliado** (acrescenta `DATE_TIME` →
data de nascimento e `LOCATION` → endereço). Conjunto de teste (P / R / F1):

| Tipo | Presidio estrito | Presidio ampliado | Este trabalho |
|---|---|---|---|
| CPF, CNPJ, CEP, RG, placa | R = 0 (sem reconhecedor) | R = 0 | 1,00 |
| E-mail | 1,00 / 1,00 / 1,00 | idem | 1,00 / 1,00 / 1,00 |
| Telefone | 0,71 / 1,00 / 0,83 | idem | 1,00 / 1,00 / 1,00 |
| Data de nascimento | R = 0 (sem mapeamento) | 0,63 / 1,00 / 0,77 | 1,00 / 1,00 / 1,00 |
| Endereço | R = 0 (sem mapeamento) | 0,09 / 0,89 / 0,17 | 1,00 / 1,00 / 1,00 |
| Nome de pessoa | 0,86 / 0,90 / 0,88 | idem | 1,00 / 0,97 / 0,99 |
| MICRO (PF, nomes, endereços) | 0,84 / 0,48 / 0,61 | 0,56 / 0,61 / 0,58 | 1,00 / 0,99 / 1,00 |

Como ler: o Presidio é extensível e ACHA datas e locais; ele não distingue data de nascimento de outra
data nem endereço de cidade, por isso a precisão cai. A diferença nos identificadores brasileiros existe
porque ele não traz reconhecedores para eles, não porque o motor seja inferior. Dos 20 falsos positivos de
telefone, 17 são CPFs sem pontuação lidos como celular e 3 são números de 10 dígitos. Nos nomes, parte da vantagem vem de ajustes deste
trabalho (2+ palavras, CAIXA ALTA, prefixos institucionais) desenvolvidos olhando o conjunto de
desenvolvimento. A comparação não prova superioridade: o gabarito foi escrito para os tipos deste trabalho.

## Nomes de arquivo e caminhos
O nome do arquivo e o nome das pastas também podem conter dado pessoal (ex.: `laudo_529.982.247-25.pdf`,
`Contrato_Maria_da_Silva.docx`). Por isso:
- cada parte do caminho é analisada pelos mesmos detectores (com `_` lido como espaço); o que for
  encontrado vira achado com local "nome do arquivo" e aparece **mascarado** no relatório
  (`laudo_***.982.247-**.pdf`, `Contrato_Maria S.docx`);
- o relatório mostra só o nome da pasta analisada, e não o caminho completo (que pode expor usuário ou estrutura interna);
- `--pseudonimizar-caminhos` troca todo nome de arquivo por um código (`ARQ-001.pdf`) e grava a
  correspondência em `mapa_de_caminhos_CONFIDENCIAL.json`, que deve ficar com o auditor e não acompanhar o relatório.
A detecção de nomes de pessoa em nomes de arquivo depende do NER e falha em nomes sem acento, abreviados
ou em minúsculas; quando o relatório for compartilhado, a pseudonimização é a opção segura.

## Versão avaliada
O desenvolvimento não usou controle de versão; o repositório foi criado com a tag `v1.0-tcc` na versão final.
Os três ajustes do detector de nomes foram feitos olhando só o conjunto de desenvolvimento (semente 42).
Mudanças posteriores à primeira avaliação no teste (CNPJ alfanumérico, regra de risco, métricas, nomes de
arquivo) foram reexecutadas e não alteraram nenhuma detecção do conjunto de teste.

## Limitações (importante para a defesa)
1. **Dados sintéticos:** os documentos de teste são fictícios e gerados com os mesmos formatos
   que os detectores conhecem, e o conjunto de desenvolvimento e o de teste vêm do mesmo gerador
   (mesmos modelos de documento, só mudam os valores). Por isso identificadores com formato fixo chegam perto de 100%;
   em documentos reais (OCR ruim, formatos variados) o desempenho será menor.
2. **Poucos exemplos de dados sensíveis** (13 arquivos): as métricas dessa categoria têm
   alta variância e são indicativas, não conclusivas.
3. **Dados sensíveis por palavra-chave:** "transtorno" ou "diagnóstico organizacional" fora de
   contexto médico geram falso positivo; colunas como `filiado_sindicato` (snake_case) não são reconhecidas.
4. **Não lê imagens nem PDF escaneado** (exigiria OCR).
5. **Nomes:** só entidades com 2+ palavras; nomes isolados ("Maria") são ignorados de propósito.
6. A ferramenta **apoia** o mapeamento; a análise e a decisão jurídica continuam humanas.

## Trabalhos futuros
OCR para PDFs escaneados; modelo BERTimbau ajustado (ver Souza et al., 2025; Lucena, 2024);
avaliação em corpus real anonimizado; classificação de contexto para reduzir falsos positivos.


## Avaliação em corpus real (LeNER-Br)

`python tools/avaliar_lenerbr.py CAMINHO/leNER-Br/test/test.conll --saida resultados_lenerbr`

No conjunto de teste do LeNER-Br (textos jurídicos reais, entidade PESSOA), o detector de nomes obteve F1 de 0,49 (comparação exata) e 0,71 (por sobreposição, com emparelhamento 1 a 1 entre predições e nomes do gabarito), muito abaixo do resultado sintético. Os dois critérios usam a mesma lista de 220 predições; o filtro de 2+ palavras restringe só o gabarito. Ver `resultados_lenerbr/`.
