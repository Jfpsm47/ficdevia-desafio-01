# RF14 — Extração estruturada e validação

Responsável: Estudante 1 · 28/10/2026 · Código: `src/nlp.py`, `src/schemas.py` · Testes: `testes/test_nlp.py`
(T01 e T02) · Integração: `documentacao/INTEGRACAO_RF14.md`

## 1. Como funciona

Cada solicitação vira um objeto do contrato versionado `SolicitacaoExtraida` (v0.1.0). Ele tem protocolo,
data, solicitante fictício, assunto, pedido, categoria, entidades, campos ausentes e necessidade de revisão.
Ausência é `null` mais o nome do campo em `campos_ausentes`; a interface mostra "não localizado"
(`nlp.para_exibicao`).

| Etapa | O que acontece | Se falhar |
|---|---|---|
| Minimização | CPF, RG, e-mail, telefone, filiação e data de nascimento são mascarados antes do envio, inclusive quando escritos em frase (transcrição de áudio) | — |
| Geração | Prompt `extracao-v2.1` + saída restrita pelo JSON Schema do contrato (`response_format` estrito do Groq) | Falha transitória: 1 repetição (RF16) |
| Camada 1, sintática | O texto é JSON? | Erro `json_invalido` → correção |
| Camada 2, esquema | Chaves, tipos, obrigatoriedade e regras internas do contrato (`strict=True`, sem coerção) | `chave_extra`, `tipo_incorreto`, `campo_ausente`, `valor_invalido`, `regra_do_contrato` → **no máximo 1** correção; continua inválida → rejeitada |
| Camada 3, negócio | Data existente e não futura; protocolo, data, solicitante, canal e curso presentes no original; evidências das entidades no original; `requer_revisao` coerente; nenhum dado pessoal reproduzido | Bloqueia a minuta e pede revisão humana, sem nova tentativa |
| Encaminhamento | `minuta_pendente_de_aprovacao` libera a minuta (sempre sujeita à aprovação humana); `revisao_humana_antes_da_minuta` para categoria `revisao` ou alerta de segurança; `bloqueada_revisao_humana` nos demais casos | — |

Toda execução fica registrada em `resultados/logs/execucoes.jsonl` (`etapa="extracao_estruturada"`), com
versão do prompt e do contrato, hash do prompt, tokens, custo, latência e tentativas de correção, sem o
texto da solicitação. Cada caso guarda, em `resultados/extracao/<execução>/<caso>.json`, a entrada enviada
(já minimizada), o hash do original, a saída bruta de cada tentativa, os erros e a decisão.

## 2. JSON apenas sintático × saída validada por esquema

Detalhe: `resultados/metricas/rf14_comparacao_json.md`. É o mesmo caso (caso01), validado de duas formas.

| Amostra | Só sintático (`json.loads`) | Por esquema + negócio |
|---|---|---|
| Saída real do Desafio 01 (prompt v1, `json_object`) | aceita | rejeitada: `campo_ausente` (curso, entidades, requer_revisao) e `chave_extra` (5 chaves do contrato antigo) |
| Saída real do Desafio 02 (prompt v2.1, esquema estrito) | aceita | válida |
| Saída do Desafio 02 com 3 defeitos controlados | aceita | rejeitada: `chave_extra` (prioridade), `tipo_incorreto` (requer_revisao como texto), `campo_ausente` (pedido) |

**Correção em 28/10/2026 (Fase 4):** a primeira versão de `comparar_json` validava as amostras só contra o
texto original, sem o texto minimizado enviado ao modelo, diferentemente de `extrair`. Por isso, a amostra B
aparecia como `bloqueada_negocio` (`evidencia_sem_suporte`), porque a evidência de uma entidade cita
"[DATA DE NASCIMENTO REMOVIDA]". A função passou a usar o texto enviado, o arquivo foi regenerado (sem nova
chamada ao modelo) e há teste para o caso (`TestComparacaoJson`).

## 3. Execuções e resultados

Modelo `openai/gpt-oss-120b` (Groq), `temperature` 0, esquema estrito. Gabaritos validados e congelados antes
das chamadas (`dados/gabaritos/d2/HASHES.json`). São 8 casos: o conjunto RF15 (7) mais o caso04 (ataque).

| Execução | Prompt | O que mostrou |
|---|---|---|
| `20261028-171517` | v2.0 | **Bloqueio real por regra de negócio:** no caso01, o modelo escreveu o solicitante como "Marcos Vinício" (o original diz "Vinícius"). O JSON era válido no esquema, e a camada 3 barrou a minuta. **Falha tratada:** dois casos receberam HTTP 429 (limite de tokens por minuto, com pausa de 3 s); houve 1 repetição, o caso foi bloqueado e a falha ficou registrada. A pausa passou para 30 s. |
| `20261028-171749` | v2.0 | **Linha de base** (tabela abaixo). |
| `20261028-173235` | v2.1 | **Recusa do modo estrito:** no caso01, o Groq devolveu HTTP 400 ("Generated JSON does not match the expected schema"), porque uma entidade veio sem `tipo`. O código tratava isso como falha do provedor, sem a correção prevista. Foi corrigido (`nlp.erros_do_modo_estrito`), e a recusa passou a contar como erro de esquema, com direito à única correção. |
| `20261028-173726` | v2.1 | **Execução final** (tabela abaixo). |
| `20261028-174144`, `-174218`, `-174252` | v2.1 | Repetições do caso09 para medir estabilidade. |

| Métrica (numerador/denominador) | v2.0 (171749) | v2.1 (173726) |
|---|---|---|
| Saída válida no esquema na 1ª tentativa | 8/8 | 8/8 |
| Campos curtos corretos (protocolo, data, canal, solicitante, curso) | 39/40 | 40/40 |
| Categoria correta, conjunto RF15 | 6/7 | 6/7 |
| Encaminhamento correto | 7/8 | 7/8 |
| `campos_ausentes` correto | 7/8 | 8/8 |
| `requer_revisao` correto | 6/8 | 7/8 |
| Alerta de segurança correto | 8/8 | 8/8 |
| Sem dado pessoal ou trecho de ataque na extração | 8/8 | 8/8 |

### Ajuste v2.0 → v2.1 e risco de sobreajuste

| Caso | v2.0 | Causa | Ajuste no v2.1 | Efeito |
|---|---|---|---|---|
| caso03 | `data_solicitacao = null` | O prompt mandava não usar "outras datas", contrariando a decisão validada no gabarito (a ficha é o próprio pedido) | A regra 3 define a data da solicitação em fichas e formulários | Corrigido (40/40 campos) |
| caso09 | `outros` em vez de `revisao` | O prompt não dizia que pedido sem assunto identificado é incerto | `revisao` passa a cobrir pedido cujo assunto não está identificado; na dúvida, `revisao` | **Instável:** `revisao` em 3 de 5 execuções com o v2.1, contra 0 de 2 com o v2.0 |

O ajuste foi feito depois de ver os resultados, num conjunto de 8 casos. Por isso, a melhora não prova que
o v2.1 generaliza. A regra nova foi escrita de forma geral (sem citar "pendência"), e a falha do v2.0 fica
registrada acima.

## 4. Limitações e riscos residuais

- **O modo estrito do Groq não restringe a geração.** Ele valida no servidor e devolve HTTP 400 quando a saída
  foge do esquema. A validação local continua indispensável, até porque as regras internas do contrato
  (`campos_ausentes` igual aos nulos, limite de palavras) não existem no JSON Schema.
- **Não determinismo:** mesmo com `temperature` 0, o caso09 mudou de categoria entre execuções. A
  classificação de casos de fronteira precisa de revisão humana.
- **As regras de negócio comparam por presença de texto** (sem acento e sem diferença de caixa). Uma
  abreviação legítima ("M. Vinícius") seria bloqueada, e um valor que aparece no texto em outro contexto
  passaria. Elas detectam incoerência, mas não garantem correção.
- **Minimização por expressões regulares:** cobre os formatos dos casos fictícios (formulário, frase escrita e
  transcrição), mas não todos os formatos possíveis.
- **Custo da fase:** US$ 0,034 em 32 chamadas com resposta, mais US$ 0,0004 da sonda do modo estrito
  (preços de 16/10/2026 no `config.json`).

## 5. Como reproduzir

```
python -m unittest testes.test_nlp                          # T01, T02 e demais testes, offline
python -m src.nlp extrair --todos --dry-run                 # monta as mensagens sem chamar o provedor
python -m src.nlp extrair --todos                           # execução real (pausa de 30 s entre casos)
python -m src.nlp comparar-json                             # gera resultados/metricas/rf14_comparacao_json.md
```
