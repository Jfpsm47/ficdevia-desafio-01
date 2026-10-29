# Integração do RF14 e do RF15 no fluxo principal — nota para os Estudantes 2 e 3

Autor: Estudante 1 · 28/10/2026 (atualizada na Fase 4) · Decisão de equipe 3-B: o Estudante 1 entrega as
funções prontas e o Estudante 2 faz o encaixe em `src/main.py`, para que quem mantém o fluxo também o entenda
e possa demonstrá-lo. A interface Streamlit (RF20, Estudante 3) usa as mesmas funções para exibir a ficha.

## O que já está pronto (sem alterar arquivos dos colegas)

| Peça | Onde | O que faz |
|---|---|---|
| Contratos `SolicitacaoExtraida`, `ResumoSolicitacao`, `FichaCompreensao` | `src/schemas.py` | Ausência = `null` + `campos_ausentes`; categoria só da lista v2.0; resumo de até 100 palavras |
| Prompts `extracao-v2.1` e `resumo-v1.0` | `prompts/producao/` | Carregados por `src/prompts.py` (conteúdo minimizado e delimitado) |
| **`nlp.compreender(...)`** | `src/nlp.py` | **Ponto único:** extração + resumo + ficha, com auditoria de cada chamada |
| `nlp.extrair(...)` | `src/nlp.py` | Só a extração: esquema estrito, 3 camadas, no máximo 1 correção, auditoria |
| `nlp.resumir(...)` | `src/nlp.py` | Só o resumo, com a mesma disciplina |
| `nlp.validar_extracao(...)` | `src/nlp.py` | Só valida (sem chamar o provedor) uma saída já recebida |
| `nlp.para_exibicao(...)` | `src/nlp.py` | Converte `null` em "não localizado" para a interface |

O `src/llm_client.py` **não precisa mudar**: o esquema estrito vai em `parametros["response_format"]`, que
o cliente já repassa ao provedor. Provedor, modelo e parâmetros vêm de `config.json` →
`extracao_estruturada`.

## Encaixe sugerido em `processar_caso` (`src/main.py`)

Substituir a etapa 3 (extração v1 + `normalizar_extracao`) por:

```python
from src import nlp

c = nlp.compreender(texto_entrada, arquivo_origem, caso_id, dry_run=dry_run, caminho_log=log_alvo)
# c.extracao: ResultadoExtracao (estado, encaminhamento, extracao, erros, tentativas, meta)
# c.resumo:   ResultadoResumo   (estado, resumo, erros, tentativas, meta)
# c.ficha:    dict da FichaCompreensao, ou None se extração ou resumo não passaram nas 3 camadas
if not c.libera_minuta:
    # RF14: estrutura inválida ou incoerente é bloqueada ANTES da minuta.
    # Preservar entrada, erro e decisão: gravar c.extracao.para_json() em dados/processados/
    # (traz versões, hash da origem, texto enviado já minimizado, erros por camada e encaminhamento)
    # e encerrar o caso sem gerar minuta, com decisão pendente do operador.
    ...
extracao_json = c.extracao.extracao   # null = ausente (persistência)
exibicao = c.exibicao                 # "não localizado" (interface)
```

### Encaminhamentos

| `c.extracao.encaminhamento` | Significado | Minuta |
|---|---|---|
| `minuta_pendente_de_aprovacao` | Extração válida | Pode ser gerada; continua sujeita à aprovação humana |
| `revisao_humana_antes_da_minuta` | Categoria `revisao` ou alerta de segurança | Não gerar antes da triagem humana |
| `bloqueada_revisao_humana` | Esquema rejeitado após a correção, regra de negócio violada ou falha do provedor | Não gerar |

**A combinar com o Estudante 2:** o encaminhamento `revisao_humana_antes_da_minuta` já é decidido em
`nlp.decidir_encaminhamento`, mas só tem efeito quando `main.py` deixa de gerar a minuta nesse caso. Falta
definir como o operador libera a minuta depois da triagem (por exemplo, corrigindo a categoria na interface e
registrando a justificativa).

### Pontos de atenção no encaixe

- O fallback `categoria = "informacoes_gerais"` em `normalizar_extracao` (`src/main.py:143`) deixa de ser
  necessário e não deve ser reaproveitado: essa categoria não existe em `prompts/categorias.json`, e o
  contrato v2 recusa qualquer categoria fora da lista.
- Os campos do v1 que saíram do contrato (`dados_do_curso`, `evidencias`, `confianca`,
  `perguntas_do_cidadao`) não existem mais. O curso está em `curso`, e as evidências, em `entidades`. O
  `resumo_resultado` da auditoria em `main.py` usa `extracao_json['confianca']` e precisa mudar.
- O prompt da minuta (`minuta-v1.0`) recebe a extração como JSON em `<dados_extraidos>`; com o contrato v2
  os nomes dos campos mudam, então a minuta deve ser conferida numa execução de regressão (T15).
- A etapa de extração em `main.py` grava `decisao_humana="Conferido"` quando não há erro de API. Com o RF14,
  a decisão humana deveria ficar pendente até o operador conferir a ficha (RF24: preservar a decisão do
  operador).
- `nlp.compreender` nunca levanta `ErroProvedor`: a falha vira `estado="erro_provedor"` com encaminhamento
  bloqueado e fica registrada na auditoria.
- A auditoria (`etapa="extracao_estruturada"` e `etapa="resumo"`) já grava versão do prompt, versão do
  contrato, hash do prompt, tokens, custo, latência e número de tentativas de correção, sem o texto da
  solicitação.
- `compreender` faz 2 chamadas seguidas (cerca de 3.500 tokens cada). No plano gratuito do Groq, chamadas
  muito próximas podem receber HTTP 429; o cliente repete 1 vez e, se falhar, o estado fica `erro_provedor`.

## Exibição da ficha na interface (RF20, Estudante 3)

| Campo da ficha | Origem | Observação |
|---|---|---|
| Resumo e fatos com evidência | `c.ficha["resumo"]` | Cada fato traz o trecho do original que o sustenta |
| Categoria e encaminhamento | `c.extracao.extracao["categoria"]`, `c.extracao.encaminhamento` | `revisao` = triagem humana antes da minuta |
| Entidades | `c.extracao.extracao["entidades"]` | Mostrar `origem` (literal ou inferida) e evidência |
| Campos ausentes | `c.exibicao` | "não localizado" só na tela |
| Ficha retida | `c.ficha is None` | Mostrar `c.extracao.erros` e `c.resumo.erros` (campo, categoria, motivo; nunca o valor) |
