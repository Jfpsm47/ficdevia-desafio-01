# RF20 — Assistente de documentos em Streamlit

**Responsável:** Estudante 3 · **Data:** 02/11/2026  
**Módulo:** `src/app.py` (só orquestra funções testadas de `main`, `nlp`, `rag`, `embeddings`, `guardrails`,
`sentiment` e `audit`) · **Teste:** `testes/test_app.py` (fumaça offline com `streamlit.testing`)  
**Dependências:** `streamlit==1.66.1`, `pandas==3.1.0`

---

## 1. Como executar

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
streamlit run src/app.py --server.address 127.0.0.1
```

Abra `http://localhost:8501`. `--server.address 127.0.0.1` mantém o protótipo só na máquina local; sem ele, o
Streamlit também escuta na rede. Na barra lateral aparecem apenas os provedores com chave no `.env` (o valor
nunca é exibido), além do `simulado`, que é identificado como tal e serve para uso sem internet.

## 2. Abas e requisitos atendidos

| Aba | O operador faz | Requisitos |
|---|---|---|
| **Solicitação e revisão** | Escolhe um caso fictício cadastrado ou digita/envia um `.txt` e clica em **Processar**. Vê as decisões dos guardrails, a ficha (categoria, protocolo, data, resumo, campos, entidades literal/inferida, campos não localizados, motivos e alertas), os trechos top-k com similaridade, a resposta com status, as afirmações com o trecho que as sustenta, a minuta e o PDF. Registra **Aprovar / Rejeitar / Solicitar revisão** com nome e justificativa | RF14, RF15, RF16, RF19, RF20, RF24 |
| **Consulta ao acervo** | Faz uma pergunta, escolhe o top-k e "só buscar trechos" ou "buscar e gerar resposta fundamentada" | RF17, RF19 |
| **Acervo e índice** | Vê versão, modelo, dimensão, chunking e documentos do índice; reindexa sem duplicar; inclui documento fictício (TXT/PDF) com identificador e versão; exclui documento com confirmação, motivo e operador | RF17, RF20, RF24 |
| **Painel de sentimentos** | Escolhe a execução, filtra por canal, categoria e polaridade e vê totais com denominador, gráficos, tabela conferida com o gabarito e a confiança como estimativa não calibrada; pode disparar nova classificação | RF22, RF23 (T13) |
| **Auditoria** | Filtra a trilha por caso ou etapa (provedor, modelo, versões, índice, status, latência, tokens, custo, decisão) | RF21 |

Cada consulta é independente: a interface não usa memória conversacional.

## 3. Mensagens ao operador

| Situação | Mensagem |
|---|---|
| Carregamento | "Carregando índice vetorial e modelo de embeddings local…" e o status de processamento por etapa |
| Caso ainda não processado | "Este caso ainda não foi processado. Clique em Processar solicitação." |
| Bloqueio na entrada | "Solicitação bloqueada pelos guardrails de entrada: nenhuma chamada ao provedor, nenhuma minuta." |
| Retenção antes da minuta | "Solicitação retida antes da minuta (`<encaminhamento>`)", com os erros de camada |
| Sem evidência / conflito | Status "Sem evidência suficiente no acervo: encaminhada ao operador" ou "Conflito entre fontes: encaminhada à revisão" |
| Índice desatualizado | "Índice desatualizado: … Use a aba Acervo e índice para reindexar." |
| Índice vazio | "Índice vazio: clique em Indexar / atualizar acervo." |
| Falha do provedor | "Falha do provedor de IA (`<código>`): … Nada foi enviado ao cidadão" (credenciais ocultadas) |
| Revisão incompleta | "Informe o nome do servidor e a justificativa: a decisão não foi registrada." |
| Filtro sem resultado | "Conjunto vazio para os filtros escolhidos: denominador 0, proporções não calculadas." |

## 4. T11: aprovação e rejeição pela interface (02/11/2026)

| Caso | Minuta | Decisão | Revisor | Justificativa (resumo) | Persistência |
|---|---|---|---|---|---|
| `caso07_texto_responsavel` | `rag-aa1528ad` (gerada pela interface em 01/11, `openai/gpt-4.1-mini`) | **aprovada** 09:49:53 | Caio Lopes | Fundamentada em ACV-04/ACV-05, cobre as três dúvidas, informa a falta de regra sobre mudança de horário e não inventa prazos | `resultados/minutas/caso07_texto_responsavel_decisao_revisao.json`, `_rag.json`, PDF "(X) Aprovada", registro `rag-aa1528ad` no `execucoes.jsonl` |
| `caso05_texto_incompleto` | `rag-707e7f8b` (Estudante 2, 29/10) | **rejeitada** 09:50:26 | Caio Lopes | Pede ao cidadão protocolo e data, que são atribuídos pela Secretaria | `caso05_texto_incompleto_decisao_revisao.json`, `_rag.json`, PDF "(X) Rejeitada", registro `rag-707e7f8b` |

Nas duas, `enviada_ao_cidadao=false`, que é o único valor aceito pelo contrato `DecisaoRevisao`. As decisões foram
tomadas pelo Estudante 3 e digitadas no formulário da interface pelo agente de codificação, a pedido dele (ver
`registro_uso_ia.md`). O envio sem nome ou justificativa foi testado e não registra nada.

**Ocorrência durante o teste:** às 09:46 de 02/11 os dois casos foram reprocessados pela interface, gerando
`rag-95573c97` (caso07) e `rag-72395c69` (caso05) e sobrescrevendo os arquivos. As versões versionadas no
repositório foram restauradas antes da decisão, porque a do caso05 é evidência do T15. As execuções novas
continuam na auditoria, e a do caso05 está em `resultados/metricas/risco_conflito_minuta_caso05/` (ver §6).

## 5. Outras verificações feitas no navegador (01/11/2026)

- Fluxo completo do `caso07` pela interface: guardrails `permitir`, ficha `frequencia_justificativa`, 4 trechos
  (ACV-05 0,645; ACV-04 0,592...), resposta "fundamentada" citando ACV-05#c1, ACV-04#c1 e ACV-04#c3.
- Reindexar pela interface: `idx-008437e371` com 16 vetores, 0 indexados e 6 reutilizados sem duplicar (T06).
- Busca "Qual o prazo para entregar documento pendente da matrícula?": 1º lugar ACV-01 §3, similaridade 0,720.
- Painel: 12 avaliações com 3/12 positivas, 4/12 negativas, 3/12 neutras e 2/12 incertas; o filtro
  E-mail + positiva dá conjunto vazio com denominador 0 e sem erro (T13).

## 6. Limitações

- **"Processar solicitação" sobrescreve** os resultados salvos do caso (`dados/processados/`, `resultados/minutas/`).
  Para demonstrar, use texto digitado ou um caso sem minuta.
- **Inclusão e exclusão alteram o índice oficial** (`indice/padrao/`). Para demonstrar, inclua e depois exclua um
  `ACV-90` de teste.
- **Conflito não detectado no modo minuta:** no reprocessamento de 02/11, a minuta do `caso05` (`rag-72395c69`)
  afirmou "até 60 dias corridos" (ACV-05 §3) sem expor o prazo de 30 dias do ACV-04, embora a consulta direta P06
  detecte o conflito. A revisão humana é a barreira que resta; o caso está registrado como risco residual na matriz.
- O teste automático da interface é de fumaça: as interações foram verificadas manualmente no navegador.
- O Streamlit roda localmente, sem autenticação de operador; o nome do revisor é declarado no formulário.
