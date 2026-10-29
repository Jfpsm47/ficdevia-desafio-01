# RF14 — JSON apenas sintático × saída validada por esquema (caso01)

Mesmo caso, duas formas de validar. A validação **só sintática** pergunta apenas se o texto é JSON (`json.loads`). A validação **por esquema** confere o contrato `SolicitacaoExtraida` (chaves, tipos, obrigatoriedade e regras internas) e, se ele passar, as regras de negócio contra o texto original.

| Amostra | Origem | Só sintático | Por esquema + negócio | Erros encontrados (categoria: campos) |
|---|---|---|---|---|
| A. Saída real do Desafio 01 (prompt v1, modo json_object) | `resultados/comparacao_modelos/20261016-201709/openai_gpt-oss-120b__caso01_texto__extracao.json` | aceito | rejeitada_esquema | **campo_ausente**: curso, entidades, requer_revisao<br>**chave_extra**: perguntas_do_cidadao, dados_do_curso, evidencias, confianca, requer_revisao_humana |
| B. Saída real do Desafio 02 (prompt v2, esquema estrito) | `resultados/extracao/20261028-173726/caso01_texto.json` | aceito | valida | — |
| C. Saída B com três defeitos controlados | `chave extra 'prioridade'; requer_revisao como texto; 'pedido' removido` | aceito | rejeitada_esquema | **campo_ausente**: pedido<br>**tipo_incorreto**: requer_revisao<br>**chave_extra**: prioridade |

Leitura: `chave_extra` = chave que o contrato não prevê; `tipo_incorreto` = valor de tipo errado (ex.: texto no lugar de booleano); `campo_ausente` = campo obrigatório que não veio; `valor_invalido` = tipo certo com valor fora do permitido (ex.: data fora do formato, categoria fora da lista); `regra_do_contrato` = regra interna do contrato (ex.: `campos_ausentes` diferente dos campos nulos). As três amostras passam na validação só sintática; só a B obedece ao contrato.
