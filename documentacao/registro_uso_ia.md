# Registro do uso de IA no desenvolvimento (seção 10 do enunciado)

> Seções marcadas com **[HUMANO]** só podem ser preenchidas pela equipe.

## 1. Ferramentas, modelos e versões


| Ferramenta                                                  | Modelo / versão                     | Quem usou   | Para quê                                                                                                                                       |
| ----------------------------------------------------------- | ----------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code (CLI, agente de codificação)                    | Claude Opus 5.5 (`claude-opus-5-5`) | Estudante 1 | Leitura do enunciado, criação de prompts, gabaritos (rascunho), protocolo de avaliação, código de experimento/avaliação, testes e documentação |
| GroqCloud API                                               | ver `config.json`                   | Estudante 1 | Execução dos experimentos (RF02 e comparação de modelos) — é IA do *produto*, não do desenvolvimento                                           |
| Google Antigravity (agente de codificação)                  | Gemini 4 Argon                      | Estudante 2 | Planejamento e implementação de `src/llm_client.py`, `src/audit.py`, `src/main.py`, `testes/test_api_auditoria_fluxo.py` e documentação técnica (RF01, RF04, RF05, RF09, RF11, RF13) |
| \[HUMANO\] outras ferramentas usadas pelo Estudante 3       |                                     |             |                                                                                                                                                |


## 2. Solicitações relevantes feitas à IA (mínimo 3)

1. **16/10/2026 – Claude Code:** "Leia o documento do desafio e execute apenas as responsabilidades do
 Estudante 1 (engenharia de prompts, comparação de modelos, critérios de avaliação e documentação);
 antes de concluir, pare e indique toda avaliação humana necessária." → gerou a estrutura de pastas,
 prompts A/B/metaprompt, prompts de produção, gabaritos-rascunho, `src/avaliacao.py`,
 `src/experimento_prompts.py`, testes e esta documentação.
2. **16/10/2026 – Claude Code (interno ao pedido 1):** projetar um prompt de produção resistente a prompt
 injection com saída JSON verificável → delimitação com id aleatório, marcador canário, evidências literais.
3. **16/10/2026 – Claude Code (interno ao pedido 1):** consultar preços vigentes do provedor → encontrou
 fontes secundárias divergentes; foi usada somente a página oficial (console.groq.com/docs/models).
4. **17/10/2026 – Claude Code:** "Como você avaliaria todos os prompts?" e pedidos equivalentes para as
 tarefas 3 a 5 da avaliação humana → a IA deu uma segunda opinião no chat. As decisões e o registro em
 `AVALIACAO_HUMANA.md` são do revisor humano, que ajustou notas, tempos e justificativas.
5. **17/10/2026 – Claude Code:** "Propõe um texto corrigido para a minuta do caso01" → texto aceito e salvo
 em `resultados/minutas/caso01_corrigida.md`. Também foram pedidos ajustes de redação e consistência no
 formulário de avaliação e a extração dos campos críticos do gabarito do caso02 a partir da transcrição humana.
6. **17/10/2026 – Google Antigravity (Estudante 2):** "fiquei responsável por fazer a parte do estudante 2, faça o planejamento completo e detalhado do que precisa ser feito na minha parte, seguindo os requisitos e especificações do pdf do desafio" e "agora faça tudo que foi planejado" → planejou e implementou `src/llm_client.py`, `src/audit.py`, `src/main.py`, `testes/test_api_auditoria_fluxo.py`, configuração de produção em `config.json` e atualização da documentação.
7. \[HUMANO\] acrescentar as solicitações feitas pelo Estudante 3.

## 3. Sugestões aceitas, modificadas e rejeitadas


| Sugestão da IA                                                                                 | Decisão (aceita / modificada / rejeitada) | Justificativa                                                                                                                                                                                                             |
| ---------------------------------------------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Usar API compatível com OpenAI para trocar de provedor só pelo `config.json`                   | Aceita                                    | Permitiu trocar de modelo (Llama indisponível → Qwen) apenas no `config.json`, sem alterar código nem prompts                                                                                                             |
| Mascarar CPF/RG/e-mail/filiação/nascimento antes de enviar ao provedor                         | Aceita                                    | Atende à minimização do RF12; esses dados não são necessários para a minuta                                                                                                                                               |
| Regra de decisão "1 crítico ou 2 altos → nova geração"                                         | Aceita                                    | Aplicada na revisão dos casos (seção 5 de `AVALIACAO_HUMANA.md`)                                                                                                                                                          |
| Gabaritos rascunhados pela IA a partir da leitura dos arquivos                                 | Modificada                                | Chave "dados sensíveis" renomeada para `dados_pessoais_desnecessarios_na_minuta` (termo incorreto pela LGPD, art. 5º, II); transcrição do caso02 feita por pessoa; títulos do contexto institucional simplificados (v1.1) |
| Modelos `gpt-oss-120b` / `gpt-oss-20b` / `qwen3.8-27b` na comparação                           | Aceita                                    | Conjunto adequado para comparar modelos de raciocínio e modelo denso, todos com pesos abertos                                                                                                                             |
| Heurísticas de avaliação acrescentadas após ler as saídas (verificação, procedimento, negação) | Aceita, com ressalva                      | Corrigiram falsos positivos/negativos reais; o risco de sobreajuste aos casos de teste ficou documentado                                                                                                                  |
| Dicas no formulário de avaliação humana (coluna "O que conferir" e caixas "Pontos de atenção") | Rejeitada                                 | Induziam o avaliador e comprometiam a independência da avaliação humana                                                                                                                                                   |
| Arquivo separado com as observações do assistente para comparar depois                         | Rejeitada                                 | Desnecessário; mantido apenas o formulário de avaliação humana                                                                                                                                                            |
| Avaliações do assistente para as tarefas 2 a 5 (pedidas no chat como segunda opinião)          | Modificada                                | Usadas como segunda opinião; notas, tempos, falsos positivos e justificativas foram revisados e ajustados pelo revisor humano, que tomou as decisões finais                                                               |
| Recomendação do `gpt-oss-120b` como modelo de produção                                         | Aceita                                    | Melhor equilíbrio entre consistência de formato, custo, status de produção e licença aberta                                                                                                                               |
| Texto corrigido da minuta do caso01 proposto pela IA                                           | Aceita                                    | Corrige os erros apontados na revisão; salvo em `resultados/minutas/caso01_corrigida.md`                                                                                                                                  |
| Sanitização recursiva em `src/audit.py` + `ocultar_segredos` em `src/llm_client.py`            | Aceita                                    | Impede vazamento acidental de chaves de API tanto nos registros `execucoes.jsonl` quanto nas mensagens de erro (RF04, RF11)                                                                                               |
| Normalização defensiva do JSON de extração (`normalizar_extracao`) e modo `--nao-interativo`   | Aceita                                    | Garante que a estrutura JSON permaneça sempre válida mesmo com campos ausentes (RF05) e permite reproduzir as decisões da revisão humana automaticamente                                                                  |


## 4. Erros ou inadequações encontrados

- O console do Windows (cp1252) quebrava a impressão de caracteres como "→"; corrigido forçando UTF-8.
- A primeira versão do experimento continuava rodando sem chave e gerava pasta só com erros; corrigido
para falhar cedo com mensagem clara.
- A heurística de prazo inicialmente aceitava qualquer algarismo presente na fonte (ex.: dígitos do CPF),
o que escondia prazos inventados; corrigida para exigir o trecho completo ("5 dias") na fonte.
- Os modelos Llama inicialmente configurados passaram a ser "Contact Sales" no provedor; configuração
trocada para `gpt-oss` com preço público.
- A IA não consegue ouvir o áudio: a transcrição de referência do caso 02 deve ser feita por pessoa.
- `llama-3.3-70b-versatile` não estava disponível para a chave usada (`listar`), por isso foi trocado por
`qwen/qwen3.8-27b`.
- **Verificação automática — falso positivo:** "Informações não localizadas" não casava com "não
localizado". A busca passou a aceitar as flexões.
- **Verificação automática — falso negativo:** "Constatamos que a aluna está matriculada" (gpt-oss-120b,
caso04) não foi detectado. Foi criada uma heurística para afirmações de verificação/situação, que
respeita negações ("não consta nos registros").
- **Verificação automática — falso negativo:** procedimentos de trancamento inventados (gpt-oss, caso05)
foram aprovados automaticamente. Foi criada uma heurística para exigências/procedimentos dirigidos ao
cidadão.
- **Verificação automática — falso positivo:** termos proibidos citados só na lista interna de lacunas
(Qwen, caso04) contavam como texto ao cidadão. A avaliação passou a usar apenas o texto da minuta.
- As três correções acima foram feitas **depois de ler as saídas reais**, o que traz risco de ajustar o
avaliador aos próprios dados de teste. As saídas e os gabaritos não foram alterados; as matrizes foram
recalculadas com `reavaliar`.
- Na edição por script, `\b` virou um caractere de controle e quebrou uma regex sem gerar erro; o
problema foi detectado por teste manual e há teste automatizado novo para esse caso.
- O Prompt C gerado pelo metaprompt colocou o texto do cidadão dentro de uma instrução, sem delimitação.
Essa é uma fraqueza de segurança do próprio prompt gerado (achado do experimento, não do código).
- Rate limit (HTTP 429) da cota gratuita em uma chamada: passou-se a usar pausa de 3 s e 5 tentativas.

**Encontrados pelo revisor humano (Estudante 1) ao revisar o trabalho da IA:**

- **Termo incorreto da LGPD no gabarito:** a IA classificou CPF, RG, filiação, data de nascimento e e-mail
como "dados sensíveis". Pelo art. 5º, II da LGPD, nenhum deles é dado pessoal sensível. O critério correto
é minimização (dado pessoal desnecessário na minuta). A chave foi renomeada nos gabaritos e no avaliador,
sem mudança nos resultados.
- **Formulário de avaliação humana enviesado:** a IA incluiu uma coluna "O que conferir" com dicas, e o
revisor apontou que isso induz a avaliação. A partir dessa observação também foram removidas as caixas
"Pontos de atenção", que traziam as conclusões da própria IA sobre as saídas antes da avaliação humana.
- **Divergências com a segunda opinião da IA:** na avaliação dos prompts, o revisor estimou tempos de edição
maiores que os da IA (B: 5 min contra 2–3 min; C: 10 min contra 6–8 min) e não registrou o falso positivo
"discutível" que a IA apontou no Prompt C.
- **Contexto institucional:** os títulos do arquivo foram simplificados na revisão (versão 1.0 → 1.1),
sem mudança nas regras.

## 5. Forma de validação

- Código: 14 testes automatizados offline (`python -m unittest discover -s testes -t .`), execução em
modo `--dry-run` e execução real registrada em `resultados/*/execucoes.jsonl`.
- Conteúdo gerado: gabaritos validados por pessoa, verificações automáticas de `src/avaliacao.py` e
avaliação humana registrada em `documentacao/AVALIACAO_HUMANA.md`.

## 6. Declaração de responsabilidade

> Nós**, declaramos que utilizamos as ferramentas de IA acima de forma**  
> **transparente, que revisamos, testamos e compreendemos todo o código e conteúdo entregues e que**  
> **assumimos a responsabilidade pelo resultado final. Data: */*/**