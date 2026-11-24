# Avaliação do detector

Arquivos avaliados: 22 · NER ativo: sim

| Tipo de dado | Avaliação | n | VP | FP | FN | Precisão | Recall | F1 | IC95% do recall | Obs. |
|---|---|---|---|---|---|---|---|---|---|---|
| CPF | entidade | 98 | 98 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.96-1.00 |  |
| CNPJ | entidade (PJ) | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.34-1.00 | amostra insuficiente (n<10) |
| E-mail | entidade | 38 | 38 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.91-1.00 |  |
| Telefone | entidade | 50 | 50 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.93-1.00 |  |
| CEP | entidade | 34 | 34 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.90-1.00 |  |
| RG | entidade | 29 | 29 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.88-1.00 |  |
| Placa de veículo | entidade | 1 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.21-1.00 | amostra insuficiente (n<10) |
| Data de nascimento | entidade | 42 | 42 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.92-1.00 |  |
| Endereço | entidade | 18 | 18 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.82-1.00 |  |
| Nome de pessoa | entidade | 146 | 145 | 0 | 1 | 1.00 | 0.99 | 1.00 | 0.96-1.00 |  |
| Saúde | arquivo | 5 | 5 | 2 | 0 | 0.71 | 1.00 | 0.83 | 0.57-1.00 | amostra insuficiente (n<10) |
| Convicção religiosa | arquivo | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.34-1.00 | amostra insuficiente (n<10) |
| Filiação sindical | arquivo | 2 | 1 | 0 | 1 | 1.00 | 0.50 | 0.67 | 0.09-0.91 | amostra insuficiente (n<10) |
| Opinião política / filiação partidária | arquivo | 1 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.21-1.00 | amostra insuficiente (n<10) |
| Origem racial ou étnica | arquivo | 2 | 2 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.34-1.00 | amostra insuficiente (n<10) |
| Vida sexual / orientação sexual | arquivo | 1 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.21-1.00 | amostra insuficiente (n<10) |
| Dado biométrico ou genético | arquivo | 1 | 1 | 0 | 0 | 1.00 | 1.00 | 1.00 | 0.21-1.00 | amostra insuficiente (n<10) |
| MICRO (identificadores, nomes, endereços) | entidade | 456 | 455 | 0 | 1 | 1.00 | 1.00 | 1.00 | 0.99-1.00 |  |
| MICRO (dados sensíveis) | arquivo | 14 | 13 | 2 | 1 | 0.87 | 0.93 | 0.90 | 0.69-0.99 |  |
| MACRO (média dos tipos avaliados por entidade) | entidade |  |  |  |  | 1.00 | 1.00 | 1.00 |  |  |
| MACRO (média das categorias avaliadas por arquivo) | arquivo |  |  |  |  | 0.96 | 0.93 | 0.93 |  |  |
