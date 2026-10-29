# Registro do uso de IA no desenvolvimento (seção 10 do enunciado)

## Atualização do Estudante 3 — 18/10/2026 — RF06, RF07, RF08 e RF10

- Ferramenta de desenvolvimento: Codex desktop.
- Trabalho produzido: transcrição e revisão em `src/audio.py` (RF06), síntese local Piper no mesmo módulo
  (RF07), OCR/visão em `src/vision.py` (RF08), geração local de imagem em `src/image_generation.py` (RF10),
  documentação específica, evidências versionadas e testes offline.
- Decisões aceitas após validação humana: Groq/Whisper Large V3 para STT; preservação das saídas brutas;
  Piper local para TTS; cópia com assinatura mascarada para OCR; e Draw Things local com FLUX.2 klein 4B
  para a imagem, após a alternativa hospedada gratuita não ficar disponível.
- Problemas encontrados: o STT retornou o e-mail sem `@` e repetiu o turno; o OCR trouxe quatro campos
  divergentes; o TTS da Groq exigia aceitação de termos e não era adequado ao português; e as tentativas
  hospedadas de imagem falharam por disponibilidade/cota. Nenhum valor foi corrigido automaticamente.
- Validação humana: o integrante 3 ouviu o áudio original e o WAV sintetizado, conferiu visualmente o
  documento de OCR e aprovou a peça visual final. As correções ficaram restritas às versões revisadas,
  preservando as saídas brutas. As decisões e os hashes estão em `resultados/logs/execucoes.jsonl`.

## Atualização do Estudante 1 — 28/10/2026 — Desafio 02 (esquemas, NLP, dados fictícios e gabaritos)

- **Ferramenta de desenvolvimento:** Claude Code (CLI), modelo Claude Opus 5.5 (`claude-opus-5-5`).
- **IA do produto:** GroqCloud, `openai/gpt-oss-120b`, nas execuções reais do RF14 e do RF15 (custos em
  `documentacao/RF14_EXTRACAO.md` e `documentacao/RF15_FICHAS.md`).
- **Trabalho produzido:** contratos em `src/schemas.py` e JSON Schema em `prompts/esquemas/`; acervo,
  solicitações, perguntas, avaliações, ataques e gabaritos em `dados/` (`src/dados_ficticios.py`); prompts
  `extracao-v2.0`, `extracao-v2.1`, `correcao-esquema-v1.0` e `resumo-v1.0`; extração, validação em três
  camadas, resumo, ficha e ponto de integração em `src/nlp.py`; testes `test_schemas.py`,
  `test_dados_ficticios.py`, `test_nlp.py` e `test_fichas.py`; documentação do Desafio 02.
- **Método de trabalho:** plano em 5 fases aprovado pelo revisor; a IA não registrou decisões humanas por
  conta própria. Nas avaliações humanas, a IA mostrava o conteúdo real e, só a pedido do revisor, os pontos de
  atenção num bloco recolhido do chat ("leia depois de formar sua opinião"); os formulários ficaram neutros e
  o registro trouxe somente o que o revisor decidiu. Os commits foram feitos pelo revisor.
- **Serviço real × simulação:** as execuções em `resultados/extracao/` e `resultados/fichas/` são chamadas
  reais ao Groq. Os testes automatizados usam um provedor simulado (`ProvedorFalso` em `testes/test_nlp.py`),
  identificado como tal, e o `--dry-run` não chama o provedor; nenhum resultado simulado foi apresentado como
  medida do modelo.

### Solicitações relevantes (Desafio 02)

1. **28/10/2026:** "avalie o estado atual do projeto, entenda o contexto do desafio atual e me proponha o
   plano completo de implementação de forma didatica" → plano em 5 fases (contratos; dados e gabaritos com
   Checkpoint 1; RF14; RF15 com Checkpoint 2; integração e documentação) e três decisões para o revisor.
2. **28/10/2026:** "1-A, 2-A e 3-B, pode começar a Fase 0" → contratos versionados para toda a equipe, par
   contraditório sem regra de prioridade e integração entregue como funções prontas mais nota para o
   Estudante 2.
3. **28/10/2026:** "Podemos fazer uma sessão de avaliação? você me resume tudo oque eu devo avaliar, eu avalio
   e você vai marcado como avaliado" e "Pode colocar seus pontos de atenção em cada um dos itens daqui do
   bloco?" → sessões por blocos nos Checkpoints 1 e 2, com o registro restrito às decisões do revisor.
4. **28/10/2026:** "vamos com a sua recomendação" → prompt `extracao-v2.1` adotado, com a execução v2.0
   preservada como linha de base e o risco de sobreajuste documentado.
5. **28/10/2026:** "pode começar a Fase 4" → ponto único de integração `nlp.compreender`, nota de integração
   atualizada, matriz de testes, métricas do RF23, README e relatório técnico.

### Sugestões aceitas, modificadas e rejeitadas (Desafio 02)

| Sugestão da IA | Decisão | Justificativa |
|---|---|---|
| Par ACV-04 × ACV-05 sem regra de prioridade; esperado `conflito_fontes` e revisão | Aceita (1-A) | Caminho mais exigente do RF19 e previsto no enunciado quando falta regra suficiente |
| Estudante 1 rascunhar os contratos de RAG, sentimento e revisão como proposta 0.x | Aceita (2-A) | "Esquemas" é atribuição do Estudante 1; os colegas podem pedir mudança antes da 1.0 |
| Alterar `main.py` diretamente na integração | Rejeitada; adotada a 3-B | O Estudante 2 faz o encaixe com funções prontas e nota, para manter e demonstrar o fluxo |
| ACV-04 e ACV-05 em setores diferentes | Modificada | O revisor colocou os dois no mesmo setor, para que nenhum tenha precedência pela origem |
| caso07 como solicitação ambígua | Modificada | O revisor o considerou só incompleto; foi criado o caso09 como ambíguo |
| Nome real da variável de ambiente do projeto no ataque do caso08 | Modificada | Removido; o ataque pede "a chave de API configurada no sistema" |
| Padrões de verificação (vaga no caso06; P03, P06 e P07; termos dos ataques; AV-06 no guia) | Modificada | Corrigidos a pedido do revisor e testados com frases certas e erradas antes de gravar |
| Contar descrição do ataque em `alertas_seguranca` como vazamento no caso04 | Modificada | O revisor mandou ignorar esse campo: descrever o ataque é o comportamento correto |
| Prompt `extracao-v2.1` com as duas execuções documentadas | Aceita | Corrigiu o caso03; o caso09 ficou instável, registrado como risco residual |
| Fichas do caso03 e do caso09 como saíram do modelo | Modificada | O revisor registrou o caso03 como parcial (carga horária e 2 entidades) e a categoria do caso09 como incorreta |

### Erros encontrados (Desafio 02)

**Encontrados durante o desenvolvimento (pela IA, por testes ou nas execuções):**

- Uma substituição com `sed` trocou o corpo da própria função `relativo` e criou recursão infinita; corrigido.
- Testes que dependiam do estado real dos gabaritos (pendentes, sem hashes) quebraram depois da validação;
  passaram a usar cópias temporárias.
- O hash de `caso03_ocr_revisado.txt` divergiu do repositório por conversão CRLF; foi criado o
  `.gitattributes` e o congelamento foi refeito pelo revisor.
- Minimização: o padrão de filiação engolia o resto da frase, o nome atravessava a quebra de linha e levava o
  rótulo "E-mail:", e o RG levava o ponto final; corrigidos com testes.
- O Pydantic em modo flexível convertia `"talvez"` em booleano; os contratos passaram a `strict=True`.
- A recusa HTTP 400 do modo estrito do Groq era tratada como falha do provedor, sem a correção prevista;
  passou a erro de esquema (execução `20261028-173235`).
- HTTP 429 com pausa de 3 s entre chamadas; a pausa passou a 30 s.
- `comparar_json` validava sem o texto minimizado enviado ao modelo e marcava como bloqueada uma saída real
  válida; corrigido na Fase 4, com teste e arquivo regenerado sem nova chamada.
- Na redação da matriz de testes e do relatório, a IA trocou os identificadores das perguntas contraditória
  e sem resposta e descreveu o caso07 com um perfil inexistente; a conferência contra os gabaritos corrigiu os
  dois pontos antes da entrega.

**Encontrados pelo revisor humano (Estudante 1):** padrões de verificação imprecisos (vaga, P03, P06, P07,
termos dos ataques), rótulo da AV-06 no guia, perfil do caso07, setor dos documentos contraditórios, omissões
do caso03 e categoria do caso09 (registros em `documentacao/AVALIACAO_HUMANA.md`, seções 6 e 7).

### Validação (Desafio 02)

- Código: suíte offline `python -m unittest discover -s testes -t .` em 28/10/2026, com `PYTHONUTF8=1`: 130
  testes, 129 aprovados e 1 erro conhecido fora do escopo do Estudante 1 (`test_sintese_voz`, encoding no
  Windows, a cargo do Estudante 3). Todos os testes de contratos, dados, RF14 e RF15 passam.
- Conteúdo: gabaritos validados e congelados pelo revisor antes das chamadas (Checkpoint 1); fichas conferidas
  pelo revisor (Checkpoint 2); varredura de dados pessoais e segredos nas saídas antes dos commits das Fases 3 e 4.

> Seções marcadas com **[HUMANO]** só podem ser preenchidas pela equipe.

## 1. Ferramentas, modelos e versões


| Ferramenta                                                  | Modelo / versão                     | Quem usou   | Para quê                                                                                                                                       |
| ----------------------------------------------------------- | ----------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Claude Code (CLI, agente de codificação)                    | Claude Opus 5.5 (`claude-opus-5-5`) | Estudante 1 | Leitura do enunciado, criação de prompts, gabaritos (rascunho), protocolo de avaliação, código de experimento/avaliação, testes e documentação |
| GroqCloud API                                               | ver `config.json`                   | Estudante 1 | Execução dos experimentos (RF02 e comparação de modelos) — é IA do *produto*, não do desenvolvimento                                           |
| Google Antigravity (agente de codificação)                  | Gemini 4 Argon                      | Estudante 2 | Planejamento e implementação de `src/llm_client.py`, `src/audit.py`, `src/main.py`, `src/web.py`, geração de minutas em PDF, `testes/test_api_auditoria_fluxo.py` e documentação técnica (RF01, RF04, RF05, RF09, RF11, RF13) |
| Codex desktop                                                | —                                   | Estudante 3 | Planejamento, implementação, revisão e documentação dos RF06, RF07, RF08 e RF10; sugestões sempre submetidas à confirmação humana            |
| GroqCloud API                                                | `whisper-large-v3`, `qwen/qwen3.8-27b` | Estudante 3 | IA do produto para STT e OCR/visão; as execuções reais e custos estão registrados na auditoria                                                |
| Piper                                                        | `pt_BR-faber-medium`                 | Estudante 3 | Síntese de voz local do RF07, sem envio da minuta a uma API externa                                                                           |
| Draw Things                                                  | FLUX.2 [klein] 4B (6-bit), versão 26.1013.0 | Estudante 3 | Geração local da imagem do RF10, sem chave de API nem envio do prompt a serviço externo                                                       |


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
5. **17/10/2026 – Claude Code:** "Propõe um texto corrigido para a minuta do caso01" → texto revisado na etapa inicial do Estudante 1 (posteriormente consolidado em formato PDF no fluxo final do Estudante 2 em `resultados/minutas/caso01_texto_minuta.pdf`). Também foram pedidos ajustes de redação e consistência no
 formulário de avaliação e a extração dos campos críticos do gabarito do caso02 a partir da transcrição humana.
6. **17/10/2026 – Google Antigravity (Estudante 2):** "fiquei responsável por fazer a parte do estudante 2, faça o planejamento completo e detalhado do que precisa ser feito na minha parte, seguindo os requisitos e especificações do pdf do desafio" e "agora faça tudo que foi planejado" → planejou e implementou `src/llm_client.py`, `src/audit.py`, `src/main.py`, `testes/test_api_auditoria_fluxo.py`, configuração de produção em `config.json` e atualização da documentação.
7. **17/10/2026 – Google Antigravity (Estudante 2):** "eu não quero que a interação do usuário seja pelo terminal, quero fazer isso na web, e sempre antes de começar uma revisão, deve pedir os dados do revisor. na tela de revisão, eu quero que do lado esquerdo fique o conteúdo original e do direito o resultado. quero que seja responsivo, limpo e de fácil utilização" e em seguida "eu só quero que pergunte quem é o revisor uma vez, quando abrir, a minuta deve ser um arquivo pdf e não um .md" e "[NOME DO SERVIDOR RESPONSÁVEL] deve ser substituído pelo nome do revisor" → implementou `src/web.py` e `gerar_pdf_minuta` em `src/main.py`.
8. **18/10/2026 – Codex desktop:** "vamos de Piper mesmo" → substituição do TTS hospedado pelo Piper
   local, com bloqueio de minutas não aprovadas, WAV, hashes, registro de escuta e testes offline.
9. **18/10/2026 – Codex desktop:** "pode baixar e vamos utilizar e depois apagamos" e a aprovação da
   imagem final → uso local do Draw Things com FLUX.2 klein 4B para o RF10, composição da peça 16:9,
   proveniência visível, inspeção humana e registro de parâmetros e hashes.

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
| Sanitização recursiva em `src/audit.py` + `ocultar_segredos` em `src/llm_client.py`            | Aceita                                    | Impede vazamento acidental de chaves de API tanto nos registros `execucoes.jsonl` quanto nas mensagens de erro (RF04, RF11)                                                                                               |
| Normalização defensiva do JSON de extração (`normalizar_extracao`) e modo `--nao-interativo`   | Aceita                                    | Garante que a estrutura JSON permaneça sempre válida mesmo com campos ausentes (RF05) e permite reproduzir as decisões da revisão humana automaticamente                                                                  |
| Nomes de classes de teste com códigos de requisito (`TestRF04ClienteAPI`, etc.)                | Rejeitada                                 | Substituídos por nomes semânticos claros em português (`TestClienteAPI`, `TestRegistroAuditoria`, `TestFluxoAtendimento`) a pedido do Estudante 2                                                                         |
| Revisão humana interativa via `input()` no terminal e minutas salvas apenas em `.md`           | Rejeitada / Modificada                    | Substituída por interface Web responsiva lado a lado (`src/web.py`), com identificação única do revisor ao abrir a sessão e geração das minutas em PDF (`resultados/minutas/*_minuta.pdf`) com assinatura do revisor      |
| Corrigir automaticamente a transcrição e o OCR a partir do gabarito                             | Rejeitada                                 | As versões brutas foram preservadas. E-mail, turno e campos do formulário foram alterados somente após a conferência explícita do integrante 3 nos arquivos revisados. |
| Usar o TTS Orpheus hospedado pela Groq                                                          | Rejeitada / Modificada                    | A execução exigia aceite de termos e o modelo era em inglês. Foi adotado Piper local `pt_BR-faber-medium`, com custo de API zero e escuta humana obrigatória. |
| Usar apenas geração de imagem hospedada gratuita                                                | Modificada                                | As tentativas falharam por cota/disponibilidade. O RF10 passou a usar Draw Things local com FLUX.2 klein 4B, mantendo a limitação de acabamento documentada. |
| Registrar custo de cada linha de auditoria sem distinguir revisão de nova chamada                | Modificada                                | O consolidado passou a calcular custo, tokens e latência por `id_execucao`, sem duplicar uma chamada quando a decisão humana é atualizada; há teste automatizado para o caso. |


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
- Na transcrição real, o modelo devolveu o e-mail sem `@` e repetiu "noturno". A comparação normalizada
  não capturava a ausência literal do símbolo; a validação passou a preservar diferenças literais e a
  correção ocorreu somente após escuta humana.
- No OCR real, o modelo divergiu no código, na data de nascimento, na data de início do curso e no e-mail.
  A assinatura foi mascarada antes do envio; as quatro correções foram aplicadas somente em `revisada.txt`
  depois da conferência visual humana.
- O TTS da Groq retornou HTTP 400 por aceite de termos do modelo Orpheus. O fallback escolhido foi o Piper
  local, cuja saída WAV foi ouvida e aprovada pelo integrante 3.
- As tentativas com Hugging Face/Space para imagem falharam por crédito, cota ou disponibilidade. A saída
  final veio do Draw Things local; o cache de imagem alternativo, sem uso no artefato aprovado, foi removido.
- O relatório de auditoria somava uma chamada de STT/OCR duas vezes quando a mesma execução recebia revisão
  humana posterior. A regra foi corrigida para usar o último registro de cada `id_execucao` nas métricas,
  mantendo todas as ocorrências na trilha histórica.

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

**Encontrados pelo revisor humano (Estudante 2) ao revisar o trabalho da IA:**

- **Duplicação de cabeçalho e justificativa no PDF da minuta:** na primeira versão do gerador de PDF, as linhas de cabeçalho do Markdown repetiam o texto já desenhado ao lado do Brasão, e ao salvar uma revisão pela interface Web a linha `Justificativa da revisão humana:` anterior não era removida antes de gravar a nova. Ambos os problemas foram corrigidos em `src/main.py`.
- **Placeholder `[NOME DO SERVIDOR RESPONSÁVEL]` na assinatura:** o modelo de minuta mantinha o marcador `[NOME DO SERVIDOR RESPONSÁVEL]` após a revisão; ajustado em `aplicar_decisao_no_markdown` para substituir automaticamente pelo nome do revisor identificado na sessão.
- **Modal de identificação repetitivo:** inicialmente o modal na interface Web solicitava a identificação do revisor a cada troca de caso; ajustado para perguntar apenas uma única vez ao abrir a sessão.

## 5. Forma de validação

- Código: 61 testes automatizados offline aprovados em 18/10/2026 (`python -m unittest discover -s testes -t .`),
  compilação dos módulos e `pip check` sem dependências quebradas. Os testes cobrem credenciais, API,
  prompts, avaliação, fluxo, STT, TTS, OCR/visão, imagem e a métrica de auditoria sem custo duplicado.
- Conteúdo gerado: gabaritos e minutas avaliados por pessoas; verificações automáticas de `src/avaliacao.py`;
  transcrição, OCR, áudio e imagem conferidos pelo integrante 3; e decisões rastreáveis em
  `documentacao/AVALIACAO_HUMANA.md`, nos metadados dos artefatos e em `resultados/logs/relatorio_auditoria.md`.

## 6. Declaração de responsabilidade

> A equipe declara que utilizou as ferramentas de IA acima de forma transparente, revisou, testou e
> compreendeu o código e o conteúdo entregues e assume a responsabilidade pelo resultado final.
> Data de consolidação do registro: **18/10/2026**.
