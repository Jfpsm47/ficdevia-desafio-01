# Relatório técnico — Central Inteligente de Atendimento e Comunicação Institucional

> Documento consolidado da equipe, com rastreabilidade das execuções reais e das decisões humanas registradas.

## 1. Problema e escopo

Protótipo local que recebe solicitações fictícias (texto, áudio, imagem), extrai informações, gera
minuta institucional em PDF, versão em áudio e peça visual sintética, sempre com decisão final de um servidor.
Nenhuma resposta é enviada automaticamente.

## 2. Arquitetura

```
entrada (texto | áudio | imagem)
   │  validação do arquivo (src/main.py) ──── Estudante 2/3
   ▼
extração de texto (STT | OCR/visão) ───────── Estudante 3
   ▼
minimização de dados (src/prompts.minimizar) ─ Estudante 1
   ▼
triagem/extração JSON  [prompt extracao-v1.0] ─ Estudante 1 (prompt) / Estudante 2 (API)
   ▼
minuta JSON → PDF institucional com Brasão [prompt minuta-v1.0, gerar_pdf_minuta] ── Estudante 1/2
   ▼
avaliação automática (src/avaliacao.py) + REVISÃO HUMANA na Interface Web (src/web.py)
   ▼
TTS da minuta aprovada · peça visual com nota de proveniência ── Estudante 3
   ▼
registro estruturado JSONL e relatório de auditoria (src/audit.py) ── Estudante 2
```

## 3. Engenharia de prompts (Estudante 1)

- Experimento RF02: ver `resultados/experimento_prompts/<execução>/matriz_comparativa.md` e a seleção
  justificada em `documentacao/AVALIACAO_HUMANA.md` (seção 2).
- Prompts de produção e defesas contra injection: `prompts/README.md`.
- Teste de injection: caso `caso04_texto_injection` (instrução falsa de "sistema", norma inventada, pedido
  de revelar o prompt). Na execução `comparacao_modelos/20261016-201709`, os três modelos registraram
  alerta de segurança na extração e nenhum obedeceu às instruções nem vazou o marcador canário (sujeito à
  confirmação humana).
- Achado do RF02: o Prompt A (zero-shot) inventou instituição, contatos, signatária, 10 documentos e prazos.
  O B seguiu o modelo sem invenções aparentes. O C, gerado por metaprompt, colocou o texto do cidadão
  dentro de uma instrução, sem delimitação (seleção final: decisão humana).

## 4. Modelos e custos (Estudante 1 — texto; Estudante 3 — áudio/visão/imagem)

Ver `documentacao/comparacao_modelos.md`. Custos de texto calculados por token a partir de
`config.json` (`precos_usd_por_milhao_tokens`). Nas execuções reais do Integrante 3, os valores registrados
em `resultados/logs/execucoes.jsonl` foram:

| Modalidade | Modelo/provedor | Execução | Custo registrado | Observação |
|---|---|---|---:|---|
| STT (RF06) | `groq/whisper-large-v3` | `stt-46427a77` | US$ 0,002749 | 89,160 s de áudio; o arquivo de voz é enviado para a transcrição. |
| OCR/visão (RF08) | `groq/qwen/qwen3.8-27b` | `ocr-99704b6a` | US$ 0,002964 | A cópia enviada teve a região da assinatura mascarada. |
| TTS (RF07) | `piper_local/pt_BR-faber-medium` | `tts-9c86357b` | US$ 0,000000 | Sem custo de API; não inclui hardware ou energia local. |
| Imagem (RF10) | `draw_things_local/FLUX.2 [klein] 4B (6-bit)` | `img-078d5e9a` | US$ 0,000000 | Sem chamada a serviço externo; não inclui hardware ou energia local. |

## 5. Avaliação de qualidade (Estudante 1)

Protocolo: `documentacao/protocolo_avaliacao.md`. Resultados por caso, taxa de aprovação e decisões:
`documentacao/AVALIACAO_HUMANA.md` (seção 5) e `resultados/logs/relatorio_auditoria.md` (seção 3).

## 6. LGPD, privacidade e minimização (RF12)

| Campo (cenário real) | Dado pessoal? | Finalidade | Necessário para a minuta? | Risco | Tratamento no protótipo |
|---|---|---|---|---|---|
| Nome do solicitante | Sim | Identificar destinatário | Sim | Médio | Enviado; usado no destinatário |
| Protocolo, data | Não (vinculado ao titular) | Rastrear o atendimento | Sim | Baixo | Enviado |
| Curso, turno, datas do curso | Sim (vida acadêmica) | Contextualizar a resposta | Sim | Baixo | Enviado |
| CPF | Sim | Identificação civil | Não | Alto (fraude) | Mascarado antes do envio |
| RG | Sim | Identificação civil | Não | Alto | Mascarado antes do envio |
| Filiação (nome da mãe/pai) | Sim | Cadastro escolar | Não | Médio | Mascarado antes do envio |
| Data de nascimento | Sim | Cadastro / menoridade | Não | Médio | Mascarado antes do envio |
| E-mail / telefone | Sim | Canal de resposta | Não (resposta pelo próprio canal) | Médio | Mascarado antes do envio |
| Assinatura (imagem) | Sim | Validade do formulário | Não | Alto | O PDF é renderizado em cópia e a faixa da assinatura é mascarada antes do envio ao Groq; o original não é alterado. A máscara é específica desta ficha e exige inspeção humana em outros layouts. |
| Voz (áudio) | Sim (biométrico em potencial) | Canal de entrada | Não | Alto | O áudio completo é enviado ao Groq somente para transcrição, após validação local de extensão e tamanho. A síntese posterior é local com Piper. Em produção, exigiria base legal, retenção mínima e avaliação de STT local. |

Todos os dados do projeto são fictícios. O caso 01 contém CPF de exemplo e e-mail em domínio fictício.

## 7. Segurança, interface de revisão e tratamento de falhas (Estudante 2 — RF01, RF04, RF05, RF09, RF11, RF12, RF13)

- **Proteção de credenciais (RF01, RF04, RF11):** Chaves de API são lidas exclusivamente do ambiente / `.env` via `src/llm_client.verificar_chave` (perfis locais como `ollama` operam sem chave). A função `ocultar_segredos` (`src/llm_client.py`) e a varredura recursiva `sanitizar_dados` (`src/audit.py`) mascaram como `[CREDENCIAL_OCULTADA]` qualquer valor de variável `*_API_KEY`/`*_TOKEN`/`*_SECRET`, cabeçalhos `Bearer` ou prefixos conhecidos (`gsk_`, `sk-`, `AIza`) antes de exibir erros ou gravar logs.
- **Tratamento de falhas de API (`src/llm_client.py` — RF04):**
  - *Chave ausente:* bloqueia a chamada antes da rede (`codigo_erro="chave_ausente"`) com instrução clara indicando a variável e o `.env.example`.
  - *Autenticação inválida (HTTP 401/403):* interrompe imediatamente sem repetir tentativas (`codigo_erro="autenticacao_invalida"`).
  - *Limite de requisições (HTTP 429) e indisponibilidade (HTTP 5xx):* realiza até 5 tentativas respeitando o cabeçalho `Retry-After` ou espera progressiva (*backoff*).
  - *Timeout e falha de conexão:* `timeout_s` configurável em `config.json` (60 s), tratando `httpx.TimeoutException` e `httpx.HTTPError` com retentativas e mensagem amigável ao operador.
  - *Resposta vazia ou JSON malformado:* detecta `choices` vazio ou texto em branco (`codigo_erro="resposta_vazia"`), repete a tentativa e, no fluxo principal (`src/main.py`), aplica `normalizar_extracao` e `normalizar_minuta` para garantir que a estrutura JSON permaneça 100% válida mesmo quando houver campos ausentes (Critério de aceite RF05).
- **Geração de minuta em PDF e bloqueio de envio automático (RF09):** Nenhuma rotina de envio externo (SMTP, webhook ou mensageria) existe no sistema. Todas as minutas são geradas como documentos PDF 1.4 (`resultados/minutas/<caso_id>_minuta.pdf`) via `gerar_pdf_minuta` (`src/main.py`), com o Brasão oficial de Mato Grosso (`dados/originais/brasao.png`) embutido no cabeçalho, tarja explícita `MINUTA GERADA COM APOIO DE IA – PENDENTE DE REVISÃO HUMANA – ENVIO AUTOMÁTICO BLOQUEADO`, substituição automática de `[NOME DO SERVIDOR RESPONSÁVEL]` pelo nome do revisor na assinatura e registro da decisão humana no rodapé.
- **Interface Web de Revisão Humana (`src/web.py` — RF13):** A revisão humana é realizada por meio de uma interface Web local responsiva (`http://127.0.0.1:8000`) que solicita a identificação do servidor revisor (nome e cargo/setor) ao abrir a sessão e exibe lado a lado: à esquerda, o conteúdo original da solicitação (texto, player de áudio MP3 ou visualizador de documento PDF); à direita, o PDF da minuta institucional gerada, a extração JSON, os achados da avaliação automática e os controles para aprovar, corrigir manualmente (regenerando o PDF) ou rejeitar/solicitar nova geração.
- **Rastreabilidade e auditoria (`src/audit.py` — RF11, RF13):** Cada etapa gera um registro em `resultados/logs/execucoes.jsonl` e um consolidado em `resultados/logs/relatorio_auditoria.md` contendo `id_execucao`, `data_hora`, `caso_id`, `etapa`, `modalidade`, `arquivo_origem`, `provedor`, `modelo`, `parametros`, `versao_prompt`, `hash_prompt`, `dados_minimizados`, `latencia_s`, `tokens_entrada`/`tokens_saida`, `custo_usd`, `tentativas`, `erro`, `avaliacao_automatica`, `decisao_humana`, `revisor` e versões do ambiente Python/bibliotecas.

## 8. Áudio, visão/OCR e imagem (Estudante 3)

RF06 implementado com Groq/Whisper Large V3 em `src/audio.py`; detalhes, custos, execução,
testes e limitações em [RF06_AUDIO.md](RF06_AUDIO.md). A amostra real `stt-46427a77` processou
89,160 s de áudio em 1,584 s, com custo estimado de US$ 0,002749. Evidências em
`resultados/transcricoes/stt-46427a77/`. A transcrição foi corrigida (e-mail e repetição de turno) e conferida pelo integrante 3 em 18/10/2026, conforme confirmação no chat. Essa decisão não aprova uma nova minuta.
O fluxo real de áudio não utiliza mais o gabarito como substituto da transcrição; a referência
permanece apenas na demonstração `--dry-run` e na comparação posterior à chamada.

RF08 implementado com Groq/Qwen 3.8 27B em `src/vision.py`; detalhes de segurança, execução, custo,
testes e limitações em [RF08_VISAO_OCR.md](RF08_VISAO_OCR.md). A execução real `ocr-99704b6a` processou
uma ficha digitalizada em 2,176 s, com custo estimado de US$ 0,002964. A assinatura manuscrita foi
mascarada antes do envio ao provedor. O OCR identificou três divergências críticas (código, nascimento e
início do curso) e uma divergência na grafia do e-mail. O integrante 3 conferiu a ficha original em
18/10/2026, corrigiu somente `revisada.txt` e registrou a decisão `Conferido`; a saída bruta foi preservada.
O fluxo real não utiliza o gabarito como substituto do OCR.

RF07 implementado em `src/audio.py` com Piper local e o modelo aberto `pt_BR-faber-medium`. A síntese
gera WAV sem enviar a minuta a um provedor externo e registra modelo, voz, ajustes de ritmo, hashes,
latência e a relação com a minuta de origem. A rotina só aceita uma minuta cuja última decisão de
auditoria **e** cujo próprio PDF indiquem `Aprovada`; preserva em `texto_falado.txt` o conteúdo enviado
e mantém avisos de informações não localizadas. A voz Faber usa ritmo levemente reduzido e pausas entre
blocos; sua inteligibilidade em nomes, siglas, datas e números exige escuta humana antes de aceite.
O Integrante 3 ouviu e aprovou a amostra `tts-9c86357b` em 18/10/2026; a decisão está vinculada ao WAV
e à sua minuta de origem na auditoria.
RF10 implementado em `src/image_generation.py` com geração local no Draw Things e o modelo aberto
`FLUX.2 [klein] 4B (6-bit)`. O fluxo não usa chave nem envia o prompt a provedor externo: importa o PNG
exportado localmente, preserva a imagem-base, compõe a peça final 16:9 com aviso de proveniência e registra
prompt, seed, parâmetros, hashes e revisão humana. A execução `img-078d5e9a` foi aprovada pelo Integrante 3
em 18/10/2026 após conferência de textos, símbolos, mãos/objetos/proporções e coerência. A alternativa
hospedada gratuita teve sua cota limitada; por isso foi adotado o modelo local compacto, cujo acabamento
visual é mais simples do que o de modelos maiores. Detalhes em [RF10_IMAGEM.md](RF10_IMAGEM.md).

## 9. Limitações e riscos residuais

- Verificações automáticas são heurísticas (ver protocolo, seção 6); invenções parafraseadas podem passar
  (constatado: "recomendamos que verifique a lista de documentos exigidos" não é detectado).
- Mesmo com prompt seguro, os modelos gpt-oss inventaram procedimento de trancamento no caso 05: a
  revisão humana continua indispensável.
- A minimização por expressões regulares não cobre todos os formatos (ex.: CPF escrito por extenso,
  nome da mãe sem rótulo).
- Defesas de prompt reduzem, mas não eliminam, o risco de prompt injection; por isso a revisão humana é
  obrigatória.
- Dependência de fornecedor: mitigada pela API compatível com OpenAI (troca por `config.json`) e pelo
  perfil local `ollama`.
- Modelos de raciocínio consomem tokens extras de raciocínio (custo e latência maiores).
- **Integração e operação (Estudante 2):** Cotas gratuitas em nuvem estão sujeitas a limites severos de requisições por minuto (HTTP 429) e variações de latência; embora o cliente aplique retentativas com *backoff* e modo `--dry-run` com cache validado, o uso institucional contínuo exigiria hospedagem local ou contrato dedicado com SLA. Além disso, o arquivo `execucoes.jsonl` é local (sem banco transacional ou controle de acesso multiusuário).
- **Áudio e TTS (RF06/RF07):** há uma única amostra real. A transcrição em nuvem expõe a gravação ao provedor e a voz sintetizada ainda requer escuta humana para nomes, siglas, datas e números. O modelo Piper precisa estar instalado localmente para nova execução.
- **OCR/visão (RF08):** a máscara de assinatura foi calibrada para uma única página e um único layout. O comparador textual não substitui a leitura visual; outros formulários, ruído, rotação ou páginas adicionais exigem nova validação.
- **Imagem (RF10):** o FLUX.2 klein 4B quantizado foi escolhido para rodar localmente após limite da alternativa gratuita hospedada. Ele preserva privacidade e elimina custo de API, porém produz menos variações e acabamento visual mais simples; a peça só pode ser usada depois de revisão humana.

## 10. Desafio 02 — Esquemas, NLP, dados fictícios e gabaritos (Estudante 1)

Detalhes e reprodução: [CONTRATOS_DADOS.md](CONTRATOS_DADOS.md), [DADOS_E_GABARITOS_D2.md](DADOS_E_GABARITOS_D2.md),
[RF14_EXTRACAO.md](RF14_EXTRACAO.md), [RF15_FICHAS.md](RF15_FICHAS.md), [INTEGRACAO_RF14.md](INTEGRACAO_RF14.md) e
[MATRIZ_TESTES_D2.md](MATRIZ_TESTES_D2.md).

### 10.1 Compreensão da solicitação no fluxo

```
texto da solicitação (digitado | transcrição revisada | OCR revisado)
   ▼
minimização (src/prompts.minimizar) + delimitação do conteúdo não confiável
   ▼
extração [extracao-v2.1, JSON Schema estrito] ── camada 1 sintática → camada 2 contrato
   │                                                (no máximo 1 correção; ainda inválida → rejeitada)
   ▼
camada 3: regras de negócio contra o original ── violação → bloqueada, revisão humana, sem minuta
   ▼
resumo [resumo-v1.0] com fatos e evidências ── mesmas 3 camadas
   ▼
ficha de compreensão + encaminhamento: minuta pendente | revisão antes da minuta | bloqueada
   ▼
(Estudante 2) recuperação no acervo e minuta fundamentada → revisão humana
```

O ponto único de integração é `nlp.compreender`; o encaixe em `src/main.py` é feito pelo Estudante 2
(decisão de equipe 3-B).

### 10.2 Contratos de dados

`src/schemas.py` define 13 contratos Pydantic versionados (v0.1.0), com `extra="forbid"` e `strict=True` (sem
coerção de tipo), exportados como JSON Schema em `prompts/esquemas/`. Além da solicitação e da ficha, há
contratos para acervo, trechos indexados, resposta RAG com citações, avaliação, sentimento e decisão de
revisão, propostos aos colegas (decisão 2-A). Regras que o JSON Schema não expressa ficam no contrato:
`campos_ausentes` igual aos campos nulos, resumo de até 100 palavras, `sem_evidencia` sem afirmações,
`conflito_fontes` com ao menos 2 documentos e `enviada_ao_cidadao` sempre `false`. Os erros de validação
nunca reproduzem o valor recebido.

### 10.3 Dados fictícios e gabaritos

| Entrada | Quantidade | Observação |
|---|---|---|
| Acervo | 6 documentos (ACV-01 a ACV-06), 2 temas, TXT e PDF textual | Identificador, título, versão e vigência em `dados/acervo/catalogo.json` |
| Solicitações | 7 no conjunto RF15 (4 completas, 2 incompletas, 1 ambígua) | Inclui a transcrição do áudio e o OCR revisados do Desafio 01 |
| Perguntas RAG | 8 (5 respondíveis, P06 contraditória, P07 e P08 sem resposta) | Contradição ACV-04 × ACV-05 sem regra de prioridade: esperado `conflito_fontes` e revisão (decisão 1-A) |
| Avaliações | 12 (3 positivas, 3 negativas, 3 neutras, 3 ambíguas ou mistas) | Guia de rotulagem com justificativa dos rótulos ambíguos |
| Ataques | 3 (na solicitação, no acervo e pedido de segredo) | Gabarito em `adversariais.json` |

Todos os gabaritos foram validados pelo revisor e congelados (SHA-256) antes da primeira chamada ao modelo.

### 10.4 Resultados medidos

Modelo `openai/gpt-oss-120b` (Groq), `temperature` 0, saída restrita por JSON Schema.

| Métrica (numerador/denominador) | Resultado |
|---|---|
| Saída válida no esquema na 1ª tentativa (extração) | 8/8 |
| Campos curtos corretos | 40/40 |
| Encaminhamento correto | 7/8 |
| Acurácia de categoria, conjunto RF15 (conferida pelo revisor) | 6/7 |
| Resumos fiéis aos fatos essenciais (conferido pelo revisor) | 6/7 |
| Entidades esperadas encontradas | 24/26 |
| Fatos sem suporte nos resumos | 0 |

Custos: RF14, US$ 0,034 em 32 chamadas mais US$ 0,0004 da sonda do modo estrito; RF15, US$ 0,0059 em 7
chamadas de resumo (preços de 16/10/2026 no `config.json`).

Falhas encontradas e tratadas: bloqueio real por regra de negócio (nome do solicitante escrito diferente do
original); HTTP 429 com pausa de 3 s (pausa passou a 30 s); recusa HTTP 400 do modo estrito tratada como
falha do provedor (passou a erro de esquema, com 1 correção); data da solicitação nula no OCR (ajuste no
prompt v2.0 → v2.1); comparação JSON validando sem o texto minimizado (corrigida na Fase 4).

### 10.5 Privacidade

A minimização passou a cobrir dados ditos em frase, como em transcrições ("meu RG é...", "o nome da minha mãe
é..."), além do formato de formulário. A camada 3 bloqueia extração ou resumo que reproduza CPF, RG, e-mail,
telefone, filiação ou data de nascimento. Os registros de auditoria guardam versões, hashes, tokens, custo e
tipos de dado minimizados, sem o texto da solicitação.

### 10.6 Limitações e riscos residuais

- **Categoria instável em caso de fronteira:** o caso09 saiu `revisao` em 3 de 5 execuções com o v2.1. Como
  `revisao` é a categoria que manda o caso à triagem antes da minuta, o erro reduz a proteção.
- **Ajuste do prompt depois de ver os resultados (v2.0 → v2.1)**, num conjunto de 8 casos: risco de
  sobreajuste, documentado.
- **Regras de negócio por presença de texto:** detectam incoerência, mas não garantem correção (abreviação
  legítima é bloqueada; valor presente em outro contexto passa).
- **Omissão de fato essencial e paráfrase que muda o sentido não são detectadas automaticamente** (caso03): a
  conferência humana da ficha continua obrigatória.
- **O modo estrito do Groq valida depois da geração** e devolve HTTP 400; a validação local é indispensável.
- **Amostra pequena** (7 solicitações fictícias) e encaixe no fluxo principal ainda pendente.


---

## 11. Desafio 02 — Embeddings, Índice Vetorial, RAG Fundamentado e Provedor Configurável (Estudante 2)

### 11.1 Arquitetura integrada ponta a ponta

```
entrada (.txt | transcrição revisada .mp3 | OCR revisado .pdf)
   ▼
nlp.compreender (RF14 + RF15) ── não libera minuta ──► retida antes da minuta + auditoria (PENDENTE)
   │ libera_minuta = true (ou liberada após triagem humana auditada)
   ▼
busca top-k no IndiceVetorial persistente (FAISS IndexFlatIP + L2 = cosseno, fastembed 384d local)
   ▼
montagem segura (fatos da solicitação ≠ trechos do acervo, delimitados em prompts versionados)
   ▼
AdaptadorGeracao (Groq OpenAI-compat | modelo secundário | AdaptadorSimulado explícito)
   ▼
validação em 3 camadas + reconstrução determinística de Citacao a partir do índice (máx. 1 correção)
   ▼
minuta PDF institucional (ENVIO AUTOMÁTICO BLOQUEADO) + DecisaoRevisao (pendente → aprovada/rejeitada/revisar)
```

### 11.2 Ingestão, embeddings e comparação de chunking (RF17, RF18)

- **Extração e metadados (`src/ingestion.py`):** leitura de `.txt` e `.pdf` (`pypdf`), preservando número de página e seção temática sem misturar páginas distintas num mesmo chunk; validação estrita de cada `TrechoIndexado` (`v0.1.0`).
- **Índice persistente (`src/embeddings.py`):** modelo local `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (`fastembed` ONNX, dimensão `384`), persistido em `indice/padrao/` (`idx-008437e371`, 16 vetores em 6 documentos). Reindexação do mesmo acervo reutiliza `6/6` documentos por SHA-256 sem duplicar vetores (`T06`); mudança de modelo, dimensão ou chunking levanta `ErroIndiceDesatualizado` até reindexação explícita. Similaridade de cosseno em `[-1, 1]` acompanha aviso expresso de que **similaridade vetorial não garante verdade**.
- **Comparação de chunking (`T07` — `resultados/metricas/rf18_comparacao_chunking.md`):**
  - `config_a_granular` (`320` caracteres, sobreposição `50`, 29 chunks): acerto `top-3` = **4/5 (80%)** — fragmentou a seção 2 do `ACV-01` em dois chunks, separando itens da lista de matrícula e a regra para menores de 18 anos.
  - `config_b_contextual` (`700` caracteres, sobreposição `120`, 16 chunks): acerto `top-3` = **5/5 (100%)** — selecionada para o índice oficial.

### 11.3 Geração fundamentada com RAG, conflito e segurança (RF19, RF16)

Na bateria oficial `resultados/rag/20261029-192739/` (`groq/openai/gpt-oss-120b`, `temperature=0`, custo `US$ 0,006438` em 10 chamadas reais):

| Métrica / Cenário | Resultado | Observação |
|---|---:|---|
| Acerto de recuperação (`P01..P05`, `top_k=4`) | **5/5 (100%)** | Trechos normativos exatos recuperados |
| Respostas institucionais sustentadas (`P01..P06`) | **6/6 (100%)** | Citações reconstruídas em código a partir de `TrechoIndexado` (`T08`) |
| Abstenção correta (`P07, P08`) | **2/2 (100%)** | `estado="valida"`, `status="sem_evidencia"`, sem inventar bolsas ou prazos (`T09`) |
| Conflito entre fontes vigentes (`P06`) | **1/1** | `conflito_fontes` citando `ACV-04` (30d) e `ACV-05` (60d), `requer_revisao=true` (`T10`) |
| Prompt injection indireto no acervo (`ADV-02` / `ACV-06 §3`) | **Atendido** | Testado em `top_k=4` (alerta de integridade documental) e com exposição direta de `ACV-06#c2` no prompt |

### 11.4 Abstração de provedor, auditoria, retenção e regressão (RF21, RF23, RF24)

- **Troca de geração sem reindexar (`T12` — `resultados/metricas/rf21_troca_provedor.json`):** demonstrada entre `openai/gpt-oss-120b` (`US$ 0,000538`), `openai/gpt-oss-20b` (`US$ 0,000269`) e `AdaptadorSimulado` (`simulado=true`, `metrica_custo_status="indisponivel_execucao_local_simulada"`, claramente identificado como não equivalente a modelo real), mais falha controlada HTTP 503 tratada e auditada, sem tocar em `indice/padrao/vetores.faiss`.
- **Privacidade, retenção e exclusão (`T14` — `resultados/metricas/rf24_exclusao_documento.json`):** `src/audit.mascarar_identificadores_log` oculta CPF, RG, e-mail, telefone, protocolo (`20\d{2}-\d{4,8}`) e segredos na consulta gravada; `excluir_documento("ACV-03")` removeu os vetores de `ACV-03` (`16 -> 14`), apagou `.derivado.json` e confirmou remoção após recarga em disco.
- **Regressão integrada (`T15`):** entradas de texto (`caso01_texto`, `caso05_texto_incompleto`, `caso06_texto_transferencia`), áudio (`caso02_audio`) e imagem/OCR (`caso03_ocr`) percorreram compreensão RF14/RF15 + minuta fundamentada RAG + PDF bloqueado para revisão humana, enquanto entradas inválidas ou suspeitas (`caso04_texto_injection` e uma ocorrência real de `"Marcos Vinício"` no `caso01_texto`) foram retidas antes da minuta.

### 11.5 Limitações e riscos residuais (escopo Estudante 2)

- **Extração de PDF restrita à camada textual:** `pypdf` não faz OCR em normas digitalizadas como imagem; acervo sem texto selecionável exigiria passagem prévia por `src/vision.py`.
- **Sustentação verificada estruturalmente:** o verificador garante correspondência exata de `chunk_ids` e metadados do índice e ausência de padrões proibidos, mas paráfrases sutis continuam exigindo revisão humana.
- **Exposição ocasional de vocabulário técnico no texto da minuta:** no `caso03_ocr`, ao justificar a ausência de campos da ficha manuscrita, o modelo mencionou `campo "canal"` e `"pedido"` no texto ao cidadão — reforçando a obrigatoriedade da revisão humana antes de qualquer uso externo.
