# Matriz de testes — Desafio 02 (seção 11 do enunciado)

Documento da equipe. Linhas T01 a T03 e métricas de categoria: Estudante 1, 28/10/2026. As demais linhas
ficam com o responsável inicial (seção 5 do enunciado) e são preenchidas depois da execução.

**Resultados de referência antes das chamadas:** todos os gabaritos do Desafio 02 foram validados pelo
revisor e congelados em `dados/gabaritos/d2/HASHES.json` às 17:05:05 de 28/10/2026 (SHA-256 de 28 arquivos).
A primeira chamada ao modelo no Desafio 02 está registrada às 17:15:21 (`resultados/logs/execucoes.jsonl`).
Para conferir se nada mudou: `python -m src.dados_ficticios verificar`.

**Rótulos de requisito:** no enunciado, T01 e T02 aparecem como "RF15" e T03 como "RF16", mas os cenários
correspondem ao RF14 (T01, T02) e ao RF15 (T03). A coluna "Requisito" usa o requisito do cenário.

## Matriz

| ID | Requisito | Entrada | Resultado esperado | Resultado obtido | Evidência | Situação |
|---|---|---|---|---|---|---|
| T01 | RF14 | JSON válido com tipo incorreto (`requer_revisao` como texto) e campo obrigatório ausente (`pedido`); recusa do modo estrito do provedor | Rejeição pelo esquema ou ausência explícita; nenhuma minuta a partir de estrutura inválida | **Offline:** `rejeitada_esquema` com `tipo_incorreto` e `campo_ausente`, após exatamente 1 correção; `extracao = null`; `libera_minuta = false`. **Real:** a amostra com 3 defeitos controlados é aceita pela validação só sintática e rejeitada pelo esquema (`chave_extra`, `tipo_incorreto`, `campo_ausente`); a recusa HTTP 400 do modo estrito (execução `173235`) revelou que ela era tratada como falha do provedor, sem a correção; corrigido e coberto por teste | `testes/test_nlp.py` (`TestT01EsquemaECorrecao`, 6 testes); `resultados/metricas/rf14_comparacao_json.md`; `resultados/extracao/20261028-173235/`; `documentacao/RF14_EXTRACAO.md` §2 e §3 | Atendido no módulo `src/nlp.py`. Encaixe em `src/main.py` pendente (Estudante 2, `INTEGRACAO_RF14.md`) |
| T02 | RF14 | Data impossível (31/02/2026); protocolo ausente do original; nome escrito diferente do original | Regra de negócio bloqueia e solicita revisão | **Offline:** `bloqueada_negocio` com `data_inexistente` e com `valor_ausente_no_original`, encaminhamento `bloqueada_revisao_humana`, sem nova tentativa. **Real:** na execução `171517`, o modelo escreveu o solicitante do caso01 como "Marcos Vinício" (o original diz "Vinícius"); JSON válido no esquema, bloqueado pela camada 3 (`valor_ausente_no_original`) | `testes/test_nlp.py` (`TestT02RegrasDeNegocio`, 7 testes); `resultados/extracao/20261028-171517/matriz_rf14.md` e `caso01_texto.json` | Atendido no módulo `src/nlp.py`. Encaixe em `src/main.py` pendente (Estudante 2) |
| T03 | RF15 | 7 solicitações com gabarito (4 completas, 2 incompletas, 1 ambígua; inclui áudio e OCR reaproveitados) | Resumo fiel, categoria e entidades avaliados | Resumo fiel: 6/7 (caso03 parcial). Fatos sem suporte: 0. Categoria: 6/7 (caso09 `outros` em vez de `revisao`). Entidades: 24/26 (caso03 sem 2). Erros e correções registrados pelo revisor | `resultados/fichas/20261028-175345/` (`matriz_rf15.md`, `fichas_para_revisao.md`); `documentacao/AVALIACAO_HUMANA.md` §7; `documentacao/RF15_FICHAS.md`; `testes/test_fichas.py` | Atendido, com 2 erros registrados |
| T04 | RF16 | 3 entradas adversariais (solicitação, acervo, segredo) | Instruções não executadas e segredo não revelado | — | Referência: `dados/gabaritos/d2/adversariais.json` | Pendente (Estudante 3) |
| T05 | RF16 | Fora de escopo, arquivo excessivo e limite de chamadas | Bloqueio ou revisão; limite respeitado | — | — | Pendente (Estudante 3) |
| T06 | RF17 | Reinício e reindexação do mesmo acervo | Índice reutilizado, sem duplicação | — | Acervo: `dados/acervo/catalogo.json` | Pendente (Estudante 2) |
| T07 | RF18 | 2 configurações de chunking e 5 perguntas | Top-k comparado e acerto calculado | — | Referência: `dados/gabaritos/d2/rag_perguntas.json` (P01 a P05) | Pendente (Estudante 2) |
| T08 | RF19 | 5 perguntas respondíveis | Respostas e citações verificadas contra fontes | — | Referência: `rag_perguntas.json` (P01 a P05) | Pendente (Estudante 2) |
| T09 | RF19 | 2 perguntas sem evidência | Abstenção e encaminhamento ao operador | — | Referência: `rag_perguntas.json` (P07, P08) | Pendente (Estudante 2) |
| T10 | RF19 | Fontes contraditórias | Prioridade documentada ou conflito e revisão | — | Referência: `rag_perguntas.json` (P06; ACV-04 × ACV-05, sem regra de prioridade → `conflito_fontes` + revisão) | Pendente (Estudante 2) |
| T11 | RF20/RF24 | Aprovação e rejeição na interface | Estados e justificativas persistidos; sem envio automático | — | Contrato: `DecisaoRevisao` (`src/schemas.py`) | Pendente (Estudante 3) |
| T12 | RF21 | Troca de geração e falha do serviço | Índice preservado; falha tratada e auditada | — | — | Pendente (Estudante 2) |
| T13 | RF23 | Filtro, duplicata e conjunto vazio | Totais corretos, denominador visível, sem divisão por zero | — | Referência: `dados/gabaritos/d2/sentimentos.json`, `dados/avaliacoes/avaliacoes.csv` | Pendente (Estudante 3) |
| T14 | RF24 | Exclusão de documento e derivados | Trechos removidos da busca e exclusão registrada | — | — | Pendente (Estudante 2) |
| T15 | RF23 | Regressão textual e áudio ou OCR | Entradas anteriores seguem até minuta e revisão | Parcial (só compreensão): caso01 (texto), caso02 (transcrição revisada do áudio) e caso03 (OCR revisado) passaram pela extração v2.1 e pelo resumo; caso01 e caso02 completos, caso03 com 2 entidades omitidas. Falta a minuta e a revisão no fluxo integrado | `resultados/extracao/20261028-173726/`; `resultados/fichas/20261028-175345/` | Pendente (Estudante 2, após o encaixe do RF14) |

## Métricas do RF23 (numerador/denominador)

| Métrica | Resultado | Conjunto | Evidência | Responsável |
|---|---|---|---|---|
| **Acurácia de categoria** | **6/7** (conferida pelo revisor) | Conjunto RF15, prompt `extracao-v2.1`, execução `173726` | `AVALIACAO_HUMANA.md` §7; `matriz_rf15.md` | Estudante 1 |
| Acurácia de categoria, linha de base | 6/7 (conferência automática) | Mesmo conjunto, prompt `extracao-v2.0`, execução `171749` | `RF14_EXTRACAO.md` §3 | Estudante 1 |
| Campos curtos corretos (protocolo, data, canal, solicitante, curso) | 40/40 | 8 casos (RF15 + caso04) | `RF14_EXTRACAO.md` §3 | Estudante 1 |
| Encaminhamento correto | 7/8 | 8 casos | `RF14_EXTRACAO.md` §3 | Estudante 1 |
| Resumos fiéis aos fatos essenciais | 6/7 | Conjunto RF15 | `AVALIACAO_HUMANA.md` §7 | Estudante 1 |
| Entidades esperadas encontradas | 24/26 | Conjunto RF15 | `matriz_rf15.md` | Estudante 1 |
| Acerto de recuperação | — /5 | P01 a P05 | — | Estudante 2 |
| Respostas institucionais com todas as afirmações sustentadas | — | — | — | Estudante 2 |
| Abstenção correta | — /2 | P07, P08 | — | Estudante 2 |
| Caso contraditório (registrado à parte) | — | P06 | — | Estudante 2 |
| Sentimentos conferidos com o gabarito | — /12 | AV-01 a AV-12 | — | Estudante 3 |

### Estabilidade da categoria (risco residual)

O caso09 (ambíguo) saiu `revisao` em 3 de 5 execuções com o prompt `extracao-v2.1` e em 0 de 2 com o v2.0
(`RF14_EXTRACAO.md` §3). A acurácia de 6/7 vem de uma única execução; em outra execução, o mesmo conjunto
poderia dar 7/7. Por isso, as duas medidas ficam registradas, e a categoria de casos de fronteira continua
dependendo de revisão humana.
