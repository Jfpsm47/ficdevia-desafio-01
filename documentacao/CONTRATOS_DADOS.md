# Contratos de dados — Desafio 02

Responsável: Estudante 1 · Situação: **PROPOSTA 0.1.0** (28/10/2026) · Código: `src/schemas.py` ·
JSON Schema: `prompts/esquemas/`

> Os contratos de índice, RAG, sentimento e revisão descrevem o trabalho dos Estudantes 2 e 3. Eles são
> um ponto de partida para não bloquear ninguém: proponham mudanças. Cada contrato passa a 1.0 depois do
> acordo de quem produz e de quem consome.

## 1. Por que contratos

Um contrato é o formulário com campos fixos que um módulo preenche e outro lê. Sem ele, o RAG pode
gravar `fontes`, a interface procurar `citacoes` e a avaliação esperar `referencias`: cada parte
funciona sozinha e a integração quebra no fim. Com Pydantic, qualquer divergência vira erro explícito
na fronteira entre os módulos.

Todos os contratos:

- rejeitam chaves não previstas (`extra="forbid"`);
- não convertem tipos silenciosamente (`strict=True`: `"true"` não vira booleano, `"3"` não vira inteiro);
- têm versão própria (`VERSAO`), registrada no JSON Schema exportado (`x-versao`).

## 2. As três camadas de validação (RF14)

| Camada | Pergunta | Onde | Categoria do erro |
|---|---|---|---|
| 1. Sintática | O texto é JSON? | `schemas.validar_texto_json` | `json_invalido` |
| 2. Esquema | Chaves, tipos e obrigatoriedade conferem? | `schemas.validar` | `chave_extra`, `tipo_incorreto`, `campo_ausente`, `valor_invalido`, `regra_do_contrato` |
| 3. Negócio | O valor faz sentido e está no original? | regras do RF14 (Fase 2) | a definir |

Os erros trazem apenas o campo e o motivo, nunca o valor recebido, que pode conter dado pessoal.

## 3. Contratos

| Contrato | Versão | Quem produz | Quem consome | RF |
|---|---|---|---|---|
| `SolicitacaoExtraida` (+ `Entidade`) | 0.1.0 | modelo, via `nlp.py` (E1) | regras de negócio, minuta, interface | RF14 |
| `ResumoSolicitacao` (+ `FatoResumo`) | 0.1.0 | modelo, via `nlp.py` (E1) | ficha, avaliação | RF15 |
| `FichaCompreensao` | 0.1.0 | sistema (E1) | interface (E3) | RF15, RF20 |
| `DocumentoAcervo` | 0.1.0 | acervo fictício (E1) | ingestão/índice (E2) | RF17 |
| `TrechoIndexado` | 0.1.0 | índice (E2) | RAG (E2), avaliação RF18 (E1) | RF17, RF18 |
| `RespostaRAG` (+ `Citacao`, `AfirmacaoInstitucional`) | 0.1.0 | RAG (E2) | interface (E3), avaliação (E1), auditoria | RF19 |
| `AvaliacaoAtendimento` | 0.1.0 | dados fictícios (E1) | sentimentos e painel (E3) | RF22 |
| `ClassificacaoSentimento` | 0.1.0 | modelo, via `sentiment.py` (E3) | painel (E3), avaliação (E1) | RF22 |
| `DecisaoRevisao` | 0.1.0 | interface (E3) | auditoria (E2) | RF20, RF24 |

### Regras que cada contrato garante sozinho

- **SolicitacaoExtraida:** ausência é `null` e o nome do campo aparece em `campos_ausentes`. A lista
  precisa corresponder exatamente aos campos nulos. A interface exibe "não localizado". A data segue
  `DD/MM/AAAA`. Se a data existe no calendário, quem confere é a camada de negócio. A categoria pertence a
  `prompts/categorias.json` v2.0, que agora inclui `revisao`.
- **Entidade:** a `origem` é `literal` (escrita no texto) ou `inferida` (deduzida), sempre com o trecho
  de `evidencia`.
- **ResumoSolicitacao:** no máximo 100 palavras, contadas como sequências sem espaço.
- **RespostaRAG:**
  - toda afirmação aponta para trechos que estão em `citacoes`;
  - `fundamentada` exige ao menos uma afirmação e uma citação;
  - `sem_evidencia` não pode conter afirmação institucional, e é isso que impede a resposta inventada;
  - `conflito_fontes` exige citações de pelo menos dois documentos;
  - qualquer status diferente de `fundamentada` exige `requer_revisao=true` e motivo.
- **ClassificacaoSentimento:** `indeterminada` exige revisão. `confianca_declarada` é uma estimativa
  não calibrada do modelo e não pode ser usada como probabilidade de acerto.
- **DecisaoRevisao:** os estados são `pendente`, `aprovada`, `rejeitada` e `revisar`. Qualquer estado
  diferente de `pendente` exige revisor, justificativa e data/hora. `enviada_ao_cidadao` só admite `false`.

### Saídas do modelo × objetos montados pelo sistema

`SolicitacaoExtraida`, `ResumoSolicitacao` e `ClassificacaoSentimento` são preenchidos pelo modelo. Por
isso, todos os seus campos são obrigatórios e nenhum tem valor padrão, o que permite usar o modo estrito
de saída estruturada do provedor (verificado por teste). Já `TrechoIndexado` e os metadados de `Citacao`
devem vir do índice, e não do texto gerado: o modelo devolve só os `chunk_id`, e o sistema completa
documento, versão, página e seção.

## 4. Pontos em aberto para combinar

| Ponto | Proposta atual | Com quem |
|---|---|---|
| Formato do `chunk_id` | `<documento_id>#c<n>` (ex.: `ACV-01#c3`) | E2 |
| `configuracao_chunking` | texto livre, ex.: `caracteres-800-sobreposicao-100` | E2 |
| A minuta do RAG usa `RespostaRAG` ou um contrato próprio? | usar `RespostaRAG` (`resposta` = texto da minuta) | E2, E3 |
| `data_hora` da decisão | ISO 8601 com fuso | E3 |
| Campos de filtro do painel | `data`, `canal`, `categoria_atendimento` | E3 |

Para propor uma mudança: altere o modelo em `src/schemas.py`, incremente `VERSAO`, rode
`python -m src.schemas exportar` e os testes (`testes/test_schemas.py`).
