# Prompts (Estudante 1)

Todos os prompts ficam versionados aqui; o código só os carrega (`src/prompts.py`). Toda mudança de texto
deve incrementar a versão no cabeçalho do arquivo e em `VERSOES` de `src/prompts.py`, para que o registro
de execução (versão + hash do prompt) continue reconstruível (RF11).

| Arquivo | Uso | Versão |
|---|---|---|
| `contexto_institucional.md` | Único contexto institucional que o modelo pode usar; lista também o que NÃO está disponível | 1.1 (o RF02 e a comparação de 16/10 usaram a 1.0, registrada nos arquivos `_entrada.md`) |
| `categorias.json` | Lista documentada de categorias (RF05, RF15) | 2.0 (28/10/2026: acrescentada `revisao`; o Desafio 01 usou a 1.0, e a mudança altera o texto montado do `extracao-v1.0`, rastreável pelo hash registrado) |
| `esquemas/*.schema.json` | JSON Schema dos contratos de dados, gerado por `python -m src.schemas exportar` (não editar à mão) | versão em `x-versao` de cada arquivo |
| `experimento/prompt_A.md` | RF02 – zero-shot curto | experimento-A |
| `experimento/prompt_B.md` | RF02 – Persona, Contexto, Tarefa, Formato, Critérios de sucesso | experimento-B |
| `experimento/metaprompt.md` | RF02 – metaprompt que gera o Prompt C | metaprompt-v1.0 |
| `experimento/prompt_C.md` | RF02 – prompt gerado pelo metaprompt em 16/10/2026 por `gpt-oss-120b`, sem edição humana | experimento-C |
| `producao/sistema_extracao_v1.md` | Prompt de sistema da triagem/extração JSON (RF03, RF05) | extracao-v1.0 |
| `producao/sistema_minuta_v1.md` | Prompt de sistema da minuta em JSON (RF03, RF09) | minuta-v1.0 |
| `producao/modelo_minuta.md` | Modelo institucional da minuta (cabeçalho GOV-MT, brasão, aviso de minuta, rastreabilidade) | 1.0 |

## Marcadores

`{{SOLICITACAO}}`, `{{CONTEXTO}}`, `{{ARQUIVO_ORIGEM}}` (experimento) e `{{CATEGORIAS}}` (extração) são
substituídos pelo código. Os prompts de produção NÃO recebem o conteúdo do cidadão por substituição: ele
vai sempre na mensagem do usuário, dentro de `<conteudo_nao_confiavel id="aleatório">`.

## Defesas do prompt de produção (RF03)

1. **Separação de papéis:** instruções na mensagem de sistema; conteúdo externo só na mensagem do usuário.
2. **Delimitação com id aleatório** e neutralização de tags reservadas dentro do conteúdo (impede que o
   texto do cidadão "feche" o bloco e escreva instruções fora dele).
3. **Conteúdo é dado:** instruções encontradas no documento não são executadas e viram `alertas_seguranca`.
4. **Proibição explícita** de inventar fatos, prazos, documentos, autoridades, normas e situação de processo.
5. **"não localizado"** obrigatório para campos ausentes + lista `campos_ausentes` / `informacoes_nao_localizadas`.
6. **Saída verificável:** JSON com `evidencias` / `afirmacoes_e_evidencias` (trecho literal da fonte).
7. **Marcador canário** (`CANARIO-EXT-7F3A`, `CANARIO-MIN-9C2D`): se aparecer na saída, houve vazamento do prompt.
8. **Minimização (RF12):** CPF, RG, e-mail, telefone, filiação e data de nascimento são mascarados antes do envio.
