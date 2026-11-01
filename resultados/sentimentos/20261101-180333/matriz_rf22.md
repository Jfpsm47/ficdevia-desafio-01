# RF22 — Classificação de sentimentos (12 avaliações fictícias)

- Execução: 2026-11-01T18:03:33-04:00 · `openai/gpt-4.1-mini` · prompt `sentimento-v1.0` · contrato `classificacao_sentimento-v0.1.0`
- Gabarito: dados/gabaritos/d2/sentimentos.json (validado e congelado antes das chamadas)
- Uso: 12 chamadas, 12618+737 tokens, 12.61 s; custo: tarifa não cadastrada

| Métrica | Resultado |
|---|---|
| Saídas válidas no contrato | 12/12 (100%) |
| **Acurácia de polaridade** | **12/12 (100%)** |
| Concordância da indicação de revisão | 11/12 (92%) |
| Ambíguos/mistos sinalizados como incertos | 2/3 (67%) |
| Erros de polaridade | nenhum |

> Confiança declarada pelo modelo: estimativa NÃO calibrada; não é probabilidade de acerto nem medida do sentimento da população.

| ID | Grupo | Esperado | Obtido | Acerto | Revisão esp./obt. | Incerto | Confiança (estimativa) | Justificativa do modelo |
|---|---|---|---|---|---|---|---|---|
| AV-01 | positiva | positiva | positiva | ✔ | não/não | não | alta | O texto elogia o atendimento, destacando que foi feito com calma e explicações claras. |
| AV-02 | positiva | positiva | positiva | ✔ | não/não | não | alta | O texto elogia a rapidez e a facilidade do atendimento, expressando agradecimento. |
| AV-03 | positiva | positiva | positiva | ✔ | não/não | não | alta | O texto elogia o atendimento por telefone como excelente e destaca que todas as dúvidas foram esclarecidas. |
| AV-04 | negativa | negativa | negativa | ✔ | não/não | não | alta | O texto relata demora excessiva no atendimento e falta de informação clara sobre documentos necessários, indicando falha no atendimento. |
| AV-05 | negativa | negativa | negativa | ✔ | não/não | não | alta | O texto relata falha no atendimento pela falta de resposta às mensagens, avaliando-o de forma desfavorável. |
| AV-06 | negativa | negativa | negativa | ✔ | não/não | não | alta | O texto relata uma falha no atendimento, pois a declaração veio com erro no nome do curso, causando a necessidade de retorno à escola para correção. |
| AV-07 | neutra | neutra | neutra | ✔ | não/não | não | alta | O texto relata um fato simples e objetivo sobre o atendimento, sem expressar avaliação favorável ou desfavorável. |
| AV-08 | neutra | neutra | neutra | ✔ | não/não | não | alta | O texto relata um fato objetivo sobre o horário de atendimento, sem expressar avaliação favorável ou desfavorável. |
| AV-09 | neutra | neutra | neutra | ✔ | não/não | não | alta | O texto relata um fato sobre o atendimento (preenchimento da pré-matrícula e recebimento do protocolo) sem emitir avaliação positiva ou negativa. |
| AV-10 | ambigua_ou_mista | indeterminada | indeterminada | ✔ | sim/sim | **sim** | media | O texto elogia a atendente, mas relata falhas no processo que causaram transtornos, apresentando avaliação mista sem indicação clara de prevalência. |
| AV-11 | ambigua_ou_mista | negativa | negativa | ✔ | sim/não | não | alta | O texto elogia a agilidade, mas relata falha no atendimento pois as faltas não foram registradas como justificadas, indicando prejuízo. |
| AV-12 | ambigua_ou_mista | indeterminada | indeterminada | ✔ | sim/sim | **sim** | media | O texto é muito curto e depende de contexto externo não fornecido para entender a avaliação do atendimento. |

## Agregação por código

Recebidos: 12 · duplicatas ignoradas: 0 · denominador: 12 · incertos: 2/12 (17%)

| Polaridade | Contagem | Proporção |
|---|---|---|
| positiva | 3 | 3/12 (25%) |
| negativa | 4 | 4/12 (33%) |
| neutra | 3 | 3/12 (25%) |
| indeterminada | 2 | 2/12 (17%) |
| sem_classificacao_valida | 0 | 0/12 (0%) |
