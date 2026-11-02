# RF22 — Classificação de sentimentos e painel (com RF23/T13)

**Responsável:** Estudante 3 · **Data:** 01/11/2026  
**Módulo:** `src/sentiment.py` · **Prompt:** `prompts/producao/sistema_sentimento_v1.md` (`sentimento-v1.0`)  
**Contrato:** `ClassificacaoSentimento` v0.1.0 (Estudante 1) · **Configuração:** seção `sentimentos` do `config.json`  
**Testes:** `testes/test_sentimentos.py` (14 testes offline com provedor falso)  
**Evidência:** `resultados/sentimentos/20261101-180333/` (`classificacoes.json`, `matriz_rf22.md`)

---

## 1. Como funciona

1. `carregar_avaliacoes` lê `dados/avaliacoes/avaliacoes.csv` e valida as 12 linhas no contrato `AvaliacaoAtendimento`.
2. **Uma chamada por avaliação.** Vão ao provedor só o ID e o texto, minimizados (`prompts.minimizar`) e delimitados
   como conteúdo não confiável. Data, canal e categoria não são enviados.
3. A saída é restrita ao JSON Schema estrito, com **no máximo 1 tentativa de correção** (mesmo ciclo do RF14,
   `nlp._gerar_com_correcao`) e no máximo 1 repetição por falha transitória.
4. Regras locais depois do esquema:
   - o `id_avaliacao` devolvido tem de ser igual ao enviado; se não for, `bloqueada_negocio`;
   - a justificativa passa pelo guardrail de saída, e segredo ou marcador interno resulta em `bloqueada_negocio`;
   - se a justificativa descrever a pessoa (personalidade, emoção, diagnóstico...), o rótulo é mantido, mas com
     `requer_revisao=true` e alerta `inferencia_sobre_autor`;
   - `indeterminada` exige `requer_revisao=true`, regra do próprio contrato.
5. **Caso incerto** = sem rótulo válido, `indeterminada`, `requer_revisao`, confiança declarada `baixa` ou alerta.
   Os incertos aparecem em destaque na matriz e no painel.
6. **Confiança declarada** é exibida como "estimativa NÃO calibrada; não é probabilidade de acerto nem medida do
   sentimento da população". Ela nunca entra em total.
7. **Totais por código:** `sentiment.agregar` usa `metrics.agregar_registros_deterministico` (Estudante 2) e
   acrescenta cruzamentos por canal e categoria, a contagem de incertos e o filtro. Duplicatas por ID são ignoradas e
   contadas, o denominador é sempre exibido e o conjunto vazio dá `n/0 (conjunto vazio)`, sem divisão por zero.

O prompt traz as regras do guia de rotulagem (`DADOS_E_GABARITOS_D2.md` §5): mensagem mista, ironia, falta de
contexto, relato de falha ou prejuízo e preferência por `indeterminada` em vez de forçar rótulo. Ele também proíbe
inferir características do autor.

## 2. Resultados (API real, `openai/gpt-4.1-mini`, temperatura 0)

Gabarito: `dados/gabaritos/d2/sentimentos.json`, validado e congelado (SHA-256) em 28/10/2026, antes das chamadas.

| Métrica | Resultado |
|---|---|
| Saídas válidas no contrato | **12/12** |
| **Acurácia de polaridade** | **12/12 (100%)** |
| Concordância da indicação de revisão | 11/12 (92%) |
| Ambíguos/mistos sinalizados como incertos | **2/3 (67%)** |
| Uso | 12 chamadas, 12.618 + 737 tokens, 12,6 s; custo não estimado (tarifa do modelo não cadastrada) |

| ID | Grupo | Esperado | Obtido | Revisão esp./obt. | Observação |
|---|---|---|---|---|---|
| AV-01..03 | positiva | positiva | positiva | não/não | — |
| AV-04..05 | negativa | negativa | negativa | não/não | — |
| AV-06 | negativa (regra 4) | negativa | negativa | não/não | relato de falha sem palavra avaliativa, reconhecido |
| AV-07..09 | neutra | neutra | neutra | não/não | — |
| AV-10 | mista | indeterminada | indeterminada | sim/sim | incerto |
| **AV-11** | **ironia** | negativa | negativa | **sim/não** | **rótulo certo, mas não marcada para revisão** |
| AV-12 | falta de contexto | indeterminada | indeterminada | sim/sim | incerto |

Agregação (sem filtro): positiva 3/12 (25%), negativa 4/12 (33%), neutra 3/12 (25%), indeterminada 2/12 (17%),
sem classificação válida 0/12. Incertos: 2/12.

## 3. Erros encontrados e correções

| Execução | Erro | Correção |
|---|---|---|
| `20261101-180242` | Falso positivo da regra de inferência sobre o autor: a justificativa do AV-10 dizia "causaram **transtornos**" (incômodo), e o termo `transtorno` estava na lista por causa do sentido clínico | O termo ambíguo saiu da regra; teste `test_transtornos_no_sentido_de_incomodo_nao_e_inferencia`; nova execução `20261101-180333`, com o mesmo rótulo e sem o alerta indevido |
| ambas | AV-11 (ironia) recebe `negativa` sem `requer_revisao` | **Não corrigido** de propósito: ajustar o prompt para este único item seria ajustar ao gabarito. Fica como limitação registrada |

## 4. T13: filtro, duplicata e conjunto vazio

| Cenário | Resultado |
|---|---|
| 4 registros com 1 duplicata | `total_recebidos=4`, `duplicatas_ignoradas=1`, denominador 3 |
| Filtro `canal=E-mail` | denominador 1, `indeterminada=1`, filtro registrado no resultado |
| Lista vazia ou filtro sem correspondência | denominador 0, `taxa=None`, "0/0 (conjunto vazio)", soma das contagens 0 |
| No painel (navegador) | E-mail + positiva → "Conjunto vazio para os filtros escolhidos: denominador 0, proporções não calculadas." |

Testes: `testes/test_sentimentos.py` (`TestT13Agregacao`); utilitários de base em `testes/test_rag.py` (Estudante 2).

## 5. Como executar

```bash
python -m src.sentiment classificar                       # 12 chamadas; grava resultados/sentimentos/<execução>/
python -m src.sentiment classificar --provedor simulado   # contingência local, identificada como simulada
python -m src.sentiment agregar --canal "E-mail"          # agrega a última execução por código
python -m unittest testes.test_sentimentos
```

## 6. Limitações

- **Amostra pequena** (12 avaliações fictícias). A acurácia de 100% não mede desempenho em dados reais.
- **Ironia** depende de interpretação, e o modelo não pediu revisão no único caso irônico.
- **A regra de inferência sobre o autor é por palavra-chave**: pode deixar passar paráfrases e gerar falso positivo
  com palavras ambíguas (o caso de "transtornos" foi corrigido).
- **A confiança declarada não é calibrada**: em AV-10, a execução final declarou `media` e a anterior declarou `alta`
  para o mesmo rótulo.
- **Os rótulos descrevem textos, não pessoas**: não podem ser usados para caracterizar cidadãos nem como medida do
  sentimento da população atendida.
