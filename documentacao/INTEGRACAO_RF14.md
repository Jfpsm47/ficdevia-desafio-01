# Integração do RF14 no fluxo principal — nota para o Estudante 2

Autor: Estudante 1 · 28/10/2026 · Decisão de equipe 3-B: o Estudante 1 entrega as funções prontas e o
Estudante 2 faz o encaixe em `src/main.py`, para que quem mantém o fluxo também o entenda e possa
demonstrá-lo.

## O que já está pronto (sem alterar arquivos do Estudante 2)

| Peça | Onde | O que faz |
|---|---|---|
| Contrato `SolicitacaoExtraida` | `src/schemas.py` | Ausência = `null` + `campos_ausentes`; categoria só da lista v2.0 |
| Prompt `extracao-v2.0` | `prompts/producao/sistema_extracao_v2.md` | Carregado por `prompts.montar_mensagens_extracao_v2` |
| `nlp.extrair(...)` | `src/nlp.py` | Chama o modelo (esquema estrito), valida em 3 camadas, faz no máximo 1 correção, registra auditoria |
| `nlp.validar_extracao(...)` | `src/nlp.py` | Só valida (sem chamar o provedor) uma saída já recebida |
| `nlp.para_exibicao(...)` | `src/nlp.py` | Converte `null` em "não localizado" para a interface |

O `src/llm_client.py` **não precisa mudar**: o esquema estrito vai em `parametros["response_format"]`, que
o cliente já repassa ao provedor.

## Encaixe sugerido em `processar_caso` (`src/main.py`)

Substituir a etapa 3 (extração v1 + `normalizar_extracao`) por:

```python
from src import nlp

res = nlp.extrair(texto_entrada, arquivo_origem, caso_id, dry_run=dry_run, caminho_log=log_alvo)
if not res.libera_minuta:
    # RF14: estrutura inválida ou incoerente é bloqueada ANTES da minuta.
    # Preservar entrada, erro e decisão: res.meta (versões, hash da origem, texto enviado),
    # res.erros (camada, campo, categoria, motivo) e res.encaminhamento.
    ...  # gravar res.para_json() em dados/processados/ e encerrar o caso sem gerar minuta
extracao_json = res.extracao              # null = ausente (persistência)
exibicao = nlp.para_exibicao(extracao_json)  # "não localizado" (interface)
```

### Encaminhamentos

| `res.encaminhamento` | Significado | Minuta |
|---|---|---|
| `minuta_pendente_de_aprovacao` | Extração válida | Pode ser gerada; continua sujeita à aprovação humana |
| `revisao_humana_antes_da_minuta` | Categoria `revisao` ou alerta de segurança | Não gerar antes da triagem humana |
| `bloqueada_revisao_humana` | Esquema rejeitado após a correção, regra de negócio violada ou falha do provedor | Não gerar |

### Pontos de atenção no encaixe

- O fallback `categoria = "informacoes_gerais"` em `normalizar_extracao` (`src/main.py:143`) deixa de ser
  necessário e não deve ser reaproveitado: essa categoria não existe em `prompts/categorias.json`, e o
  contrato v2 recusa qualquer categoria fora da lista.
- Os campos do v1 que saíram do contrato (`dados_do_curso`, `evidencias`, `confianca`,
  `perguntas_do_cidadao`) não existem mais. O curso está em `curso`, e as evidências, em `entidades`.
- `nlp.extrair` nunca levanta `ErroProvedor`: a falha vira `estado="erro_provedor"` com encaminhamento
  bloqueado e fica registrada na auditoria.
- A auditoria (`etapa="extracao_estruturada"`) já grava versão do prompt, versão do contrato, hash do prompt,
  tokens, custo, latência e número de tentativas de correção, sem o texto da solicitação.
