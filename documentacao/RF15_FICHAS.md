# RF15 — Sumarização, classificação e entidades (ficha de compreensão)

Responsável: Estudante 1 · 28/10/2026 · Código: `src/nlp.py` (seção RF15), `src/schemas.py` · Prompt:
`prompts/producao/sistema_resumo_v1.md` (`resumo-v1.0`) · Testes: `testes/test_fichas.py` · Conferência humana:
`documentacao/AVALIACAO_HUMANA.md`, seção 7 (Checkpoint 2)

## 1. Como funciona

A ficha de compreensão (contrato `FichaCompreensao`) junta duas saídas validadas:

- **Extração** (RF14, contrato `SolicitacaoExtraida`): categoria, entidades com origem `literal` ou `inferida` e
  evidência, campos ausentes.
- **Resumo** (contrato `ResumoSolicitacao`): texto de até 100 palavras mais a lista de fatos, cada um com o
  trecho do original que o sustenta.

O resumo passa pelas mesmas três camadas da extração, com no máximo 1 correção de esquema:

| Camada | Verificação | Se falhar |
|---|---|---|
| 1, sintática | O texto é JSON? | `json_invalido` → correção |
| 2, esquema | Chaves, tipos e limite de 100 palavras (`regra_do_contrato`) | 1 correção; continua inválido → rejeitado |
| 3, negócio | `fato_sem_suporte`: evidência que não aparece no original · `valor_sem_suporte`: número ou data do resumo que não aparece no original (aceita data por extenso e ponto de milhar) · `dado_pessoal_no_resumo`: CPF, RG, e-mail, telefone, filiação ou data de nascimento | Ficha retida para revisão humana, sem nova tentativa |

A ficha só é montada quando extração **e** resumo estão válidos (`nlp.montar_ficha`); caso contrário, fica
retida. O texto do cidadão é minimizado e delimitado antes do envio, como na extração. A categoria vem da lista
documentada em `prompts/categorias.json` (v2.0), que inclui `outros` (assunto claro, fora das categorias) e
`revisao` (assunto incerto ou pedido que mistura categorias).

Toda chamada fica em `resultados/logs/execucoes.jsonl` (`etapa="resumo"`), com versão do prompt e do contrato,
hash do prompt, tipos de dado minimizados (sem os valores), tokens, custo e latência.

## 2. Conferência com o gabarito

A conferência tem uma parte automática (`nlp.avaliar_ficha`) e uma humana:

| Item | Como é conferido |
|---|---|
| Categoria | Automática: igual à do gabarito? Confirmada pelo revisor |
| Entidades | Automática: esperadas encontradas (tipo e valor; datas comparadas como data), omitidas, extraídas a mais e origem divergente. Confirmada pelo revisor |
| Resumo: padrões proibidos e dados que não devem aparecer | Automática, com os padrões do gabarito (por exemplo, afirmar que há vaga no caso06) |
| Resumo: fidelidade aos fatos essenciais, omissões e fatos sem suporte | **Humana**, com ficha e gabarito lado a lado (`fichas_para_revisao.md`) |

## 3. Execução e resultados

Execução `resultados/fichas/20261028-175345`: resumo `resumo-v1.0`, categoria e entidades reaproveitadas da
extração final do RF14 (`resultados/extracao/20261028-173726`, prompt `extracao-v2.1`), modelo
`openai/gpt-oss-120b` (Groq), `temperature` 0, esquema estrito. Conjunto RF15: 7 solicitações (4 completas,
1 incompleta, 1 de responsável, 1 ambígua). Os gabaritos foram validados e congelados antes das chamadas.

| Métrica (numerador/denominador) | Automática | Conferida pelo revisor |
|---|---|---|
| Resumo válido nas três camadas, na 1ª tentativa | 7/7 | — |
| Fichas montadas | 7/7 | — |
| Resumo fiel aos fatos essenciais | — | 6/7 (1 parcial: caso03) |
| Fatos sem suporte ou inventados | 0 | 0 |
| Padrões proibidos ou dado proibido no resumo | 0/7 casos | — |
| **Acurácia de categoria** | **6/7** | **6/7** |
| Entidades esperadas encontradas | 24/26 | 24/26 |
| Entidades extraídas a mais | 0 | — |
| Origem (literal/inferida) divergente | 0 | — |

Custo da execução: US$ 0,0059 em 7 chamadas de resumo (preços de 16/10/2026 no `config.json`); latência de
1,97 s a 4,13 s por chamada. O custo da extração reaproveitada está no `RF14_EXTRACAO.md`.

### Erros e correções registrados

| Caso | Erro | Correção registrada (Checkpoint 2) |
|---|---|---|
| caso03_ocr | O resumo omite a carga horária (1200 horas); a extração omite a data 01/02/2027 (início do curso) e o órgão Secretaria Escolar | Ficha corrigida deve incluir "1200 horas" no resumo e as duas entidades, ambas literais |
| caso09_texto_ambiguo | Categoria `outros` em vez de `revisao`. Com isso, o encaminhamento foi `minuta_pendente_de_aprovacao` em vez de `revisao_humana_antes_da_minuta` | Categoria corrigida para `revisao`, conforme o gabarito |

O erro do caso09 vem da extração: é a mesma instabilidade medida no RF14 (`revisao` em 3 de 5 execuções com o
prompt v2.1). O resumo do caso09 foi considerado fiel; ele não atribui um tipo à pendência que o texto não
especifica.

## 4. Limitações e riscos residuais

- **A fidelidade do resumo não é medida automaticamente.** As regras da camada 3 pegam evidência inexistente,
  número ou data sem suporte e dado pessoal, mas não detectam omissão de fato essencial (caso03) nem paráfrase
  que mude o sentido. A conferência humana continua obrigatória.
- **`valor_sem_suporte` olha só números e datas.** Um nome, curso ou órgão inventado no texto do resumo, sem
  número, passa pela camada 3; os padrões proibidos do gabarito cobrem apenas os riscos previstos em cada caso.
- **Categoria de casos de fronteira não é estável** (caso09). Como a categoria `revisao` é a que manda o caso
  para triagem humana antes da minuta, um erro nesse sentido reduz a proteção; o risco fica registrado para a
  integração com o Estudante 2.
- **Amostra pequena:** 7 solicitações fictícias e uma execução. As métricas descrevem este conjunto, não o
  desempenho geral do modelo.
- **As correções ficam registradas, não aplicadas.** Os arquivos da execução são preservados como saíram do
  modelo; a correção vale para a revisão humana e para a próxima versão dos prompts.

## 5. Como reproduzir

```
python -m unittest testes.test_fichas                                     # testes offline do RF15
python -m src.nlp fichas --todos --dry-run                                # monta as mensagens sem chamar o provedor
python -m src.nlp fichas --todos --reusar-extracao resultados/extracao/20261028-173726   # execução usada aqui
python -m src.nlp fichas --todos                                          # extração e resumo novos
```
