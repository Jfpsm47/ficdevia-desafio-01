# Central Inteligente de Atendimento e Comunicação Institucional

Desafio Prático 1 — FIC_DEV · Inteligência Artificial Generativa (Aulas 01 a 07).

Protótipo local que recebe solicitações **fictícias** em texto, áudio e imagem, extrai informações, gera
minuta de resposta institucional, versão em áudio e peça visual sintética. **Nenhuma resposta é enviada
automaticamente**: toda saída é minuta pendente de revisão de um servidor responsável.

| Integrante | Responsabilidade | Situação |
|---|---|---|
| Estudante 1 | Engenharia de prompts, comparação de modelos, critérios de avaliação e documentação | Implementado |
| Estudante 2 | Integração por API, segurança, processamento de texto, interface Web de revisão e auditoria (`src/main.py`, `src/web.py`, `src/llm_client.py`, `src/audit.py`) | Implementado |
| Estudante 3 | Áudio, visão/OCR, geração de imagem, acessibilidade, testes multimodais (`src/audio.py`, `src/vision.py`, `src/image_generation.py`) | RF06, RF07, RF08 e RF10 concluídos; RF07 usa Piper local em pt-BR; RF10 usa FLUX.2 klein 4B local no Draw Things |

## Instalação

Base do projeto: Python 3.13 (testes anteriores em 3.13.5 / 3.13.14).
RF06 e suíte completa também testados com Python 3.14.7 no macOS.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
# Necessário uma única vez para executar o RF07 localmente:
python -m piper.download_voices pt_BR-faber-medium --download-dir .cache/piper
```

Abra `.env` e preencha **somente** a chave do provedor que for usar (padrão: `GROQ_API_KEY`, obtida em
console.groq.com/keys). O `.env` está no `.gitignore` e nunca deve ser entregue.

Versões principais: `httpx 0.28.1`, `python-dotenv 1.2.1`, `Pillow 13.0.0` e `piper-tts 1.8.0`
(ver `requirements.txt`).
A versão 1.2.2 anteriormente declarada não estava disponível no índice consultado durante a instalação.

## Execução

| Comando | O que faz |
|---|---|
| `python -m unittest discover -s testes -t .` | Testes offline, incluindo transcrição, síntese de voz e OCR — não chamam API |
| `python -m src.audio transcrever` | Transcreve o áudio fictício no Groq; salva evidências e comparação, sem aprovar a transcrição |
| `python -m src.audio revisar --help` | Instruções para confirmar os campos críticos após ouvir o áudio e revisar o texto |
| `python -m src.audio sintetizar --caso caso02_audio` | Gera localmente um WAV Piper da última minuta comprovadamente aprovada; bloqueia minutas pendentes, corrigidas ou rejeitadas |
| `python -m src.audio revisar-voz --help` | Registra a escuta humana e a decisão sobre o WAV gerado |
| `python -m src.vision extrair` | Renderiza o PDF, mascara a assinatura e extrai texto com visão/OCR no Groq, sem aprovar o resultado |
| `python -m src.vision revisar --help` | Instruções para conferir a ficha original e confirmar o OCR revisado |
| `python -m src.image_generation importar resultados/imagens/<png>.png` | Importa o PNG gerado localmente pelo Draw Things, monta a peça 16:9 e preserva a evidência para revisão humana |
| `python -m src.image_generation revisar --help` | Instruções para registrar a revisão obrigatória da peça visual do RF10 |
| `python -m src.main` | Inicia o fluxo completo e abre a **Interface Web de Revisão Humana** (`http://127.0.0.1:8000`) |
| `python -m src.main --dry-run --nao-interativo` | Executa todo o fluxo em lote sem chamar a API (usando cache validado) e gera os PDFs das minutas |
| `python -m src.main --caso caso01_texto` | Executa o fluxo principal e abre a revisão para um caso específico |
| `python -m src.experimento_prompts listar --provedor groq` | Lista os modelos disponíveis para a sua chave |
| `python -m src.experimento_prompts prompts` | **RF02**: gera o Prompt C via metaprompt e executa A, B e C com o mesmo modelo e parâmetros |
| `python -m src.experimento_prompts prompts --reusar-prompt-c` | Repete o RF02 com o Prompt C já salvo |
| `python -m src.experimento_prompts modelos` | Compara modelos com os prompts de produção nos casos 01, 04 e 05 |
| `python -m src.experimento_prompts reavaliar resultados/<tipo>/<execução>` | Recalcula as matrizes após mudar um gabarito (sem API) |

Os comandos de `src.main` e `src.experimento_prompts` aceitam `--dry-run` (sem API) e
`--provedor` / `--modelo(s)` para sobrescrever o `config.json`.
Os módulos `src.audio` e `src.vision` usam respectivamente as seções `transcricao`, `sintese_voz` e
`visao` do `config.json`; `transcrever` e `extrair` chamam a API, `sintetizar` usa Piper local,
`image_generation` importa a saída local do Draw Things e os comandos `revisar` são locais.
Passos e limitações: [RF06 — Áudio](documentacao/RF06_AUDIO.md), [RF07 — Síntese de voz](documentacao/RF07_VOZ.md), [RF08 — Visão e OCR](documentacao/RF08_VISAO_OCR.md) e [RF10 — Imagem](documentacao/RF10_IMAGEM.md).

## Desafio 02 — Esquemas, NLP, dados fictícios e gabaritos (Estudante 1)

Evolução da mesma central (Aulas 08 a 14): a solicitação vira um contrato de dados validado em três camadas
(RF14) e uma ficha de compreensão com resumo, categoria e entidades (RF15), conferidas contra gabaritos
validados e congelados antes das chamadas ao modelo. As partes dos Estudantes 2 (embeddings, índice, RAG,
provedor) e 3 (guardrails, Streamlit, sentimentos, painel) entram nesta seção quando forem integradas.

| Comando | O que faz |
|---|---|
| `python -m src.schemas exportar` | Regrava os JSON Schema dos contratos em `prompts/esquemas/` (rodar ao mudar um contrato) |
| `python -m src.dados_ficticios verificar` | Confere quantidades, contratos, trechos de referência e hashes dos gabaritos (sem API) |
| `python -m src.dados_ficticios gerar-pdfs` | Recria os PDFs textuais do acervo a partir de `dados/acervo_fontes/` (reprodutível) |
| `python -m src.nlp extrair --todos [--dry-run]` | RF14: extração com esquema estrito e validação em 3 camadas; matriz em `resultados/extracao/<execução>/` |
| `python -m src.nlp comparar-json` | RF14: JSON só sintático × validado por esquema (sem API) → `resultados/metricas/rf14_comparacao_json.md` |
| `python -m src.nlp fichas --todos [--reusar-extracao resultados/extracao/<execução>] [--dry-run]` | RF15: resumo, categoria e entidades conferidos com o gabarito; `resultados/fichas/<execução>/` |

As execuções reais usam a seção `extracao_estruturada` do `config.json` (Groq, `openai/gpt-oss-120b`,
`temperature` 0, pausa de 30 s entre casos por causa do limite de tokens por minuto do plano gratuito).
Integração com o fluxo principal: `nlp.compreender` (ver `documentacao/INTEGRACAO_RF14.md`).

| Documento | Conteúdo |
|---|---|
| `documentacao/CONTRATOS_DADOS.md` | Contratos versionados propostos à equipe, três camadas de validação e pontos em aberto |
| `documentacao/DADOS_E_GABARITOS_D2.md` | Acervo, solicitações, perguntas RAG, avaliações, ataques, guia de rotulagem e congelamento |
| `documentacao/RF14_EXTRACAO.md` · `documentacao/RF15_FICHAS.md` | Funcionamento, execuções, métricas e limitações |
| `documentacao/MATRIZ_TESTES_D2.md` | Matriz T01 a T15 e métricas do RF23 (numerador/denominador) |
| `documentacao/AVALIACAO_HUMANA.md` §6 e §7 | Validação dos gabaritos (Checkpoint 1) e conferência das fichas (Checkpoint 2) |

| Caso novo | Entrada | Finalidade |
|---|---|---|
| caso06_texto_transferencia | `dados/originais/caso06_texto_transferencia.txt` | Solicitação completa (transferência) |
| caso07_texto_responsavel | `dados/originais/caso07_texto_responsavel.txt` | Incompleta: responsável escreve pelo filho, sem informar o curso |
| caso08_texto_segredo | `dados/originais/caso08_texto_segredo.txt` | Ataque: tentativa de obter a chave de API |
| caso09_texto_ambiguo | `dados/originais/caso09_texto_ambiguo.txt` | Ambígua: pendência não especificada (categoria esperada `revisao`) |
| acervo | `dados/acervo/ACV-01` a `ACV-06` (TXT e PDF) | Fonte das orientações; ACV-04 × ACV-05 em conflito; ACV-06 com instrução maliciosa |

## Configuração

`config.json` guarda caminhos, provedores (URL base compatível com OpenAI + nome da variável da chave),
modelos, parâmetros de geração, timeout, tentativas e preços por token (com data da consulta).
Provedores prontos: `groq`, `gemini`, `openai`, `openrouter`, `ollama` (local, sem chave).

## Estrutura

```
dados/originais/     entradas fictícias (arquivos fornecidos, inalterados, + casos 04 e 05 criados pela equipe)
dados/gabaritos/     resultado esperado de cada caso, escrito antes da execução
dados/processados/   extrações estruturadas em JSON (RF05) e textos intermediários revisados
prompts/             todos os prompts versionados (ver prompts/README.md)
src/main.py          ponto de entrada principal, orquestração, extração JSON, geração de minuta em PDF e revisão
src/web.py           interface Web responsiva de revisão humana lado a lado (original à esquerda, PDF à direita)
src/llm_client.py    cliente oficial HTTP (timeout, retries 429/5xx, 401/403, resposta vazia, ocultação de chaves)
src/audio.py         transcrição Groq, comparação, preservação de evidências e conferência humana (RF06)
src/vision.py        renderização de PDF, mascaramento de assinatura, OCR Groq e conferência humana (RF08)
src/audit.py         registro estruturado em JSONL, sanitização de segredos e relatório de auditoria
src/prompts.py       montagem segura das mensagens, minimização, modelo da minuta
src/avaliacao.py     critérios automáticos de avaliação
src/experimento_prompts.py   RF02 + comparação de modelos
src/cliente_experimento.py   delega ao cliente oficial src/llm_client.py
resultados/          minutas em PDF (resultados/minutas/*_minuta.pdf), matrizes e logs (resultados/logs/execucoes.jsonl)
resultados/transcricoes/     execuções RF06: texto bruto, cópia para revisão, comparação e metadados
resultados/audios/            execuções RF07: WAV, texto falado e metadados da minuta aprovada
resultados/ocr/     execuções RF08: imagem mascarada, texto bruto/revisado, comparação e metadados
resultados/imagens/ execuções RF10: imagem-base local, peça visual 16:9, inspeção, revisão e metadados
documentacao/        protocolo de avaliação, comparação de modelos, relatório técnico, uso de IA,
                     AVALIACAO_HUMANA.md (decisões humanas)
testes/              testes automatizados (test_prompts_avaliacao.py e test_api_auditoria_fluxo.py)
```

## Casos de teste

| Caso | Entrada | Finalidade |
|---|---|---|
| caso01_texto | `entrada_texto.txt` | classificação, extração, minuta (pede lista de documentos que não existe nos dados) |
| caso02_audio | `entrada_audio.mp3` | transcrição e resposta acessível |
| caso03_ocr | `entrada_pdf-imagem.pdf` | OCR/visão de ficha manuscrita (PDF sem camada de texto) |
| caso04_texto_injection | criado pela equipe | prompt injection |
| caso05_texto_incompleto | criado pela equipe | campos ausentes → "não localizado" |
| imagem institucional | `brasao.png` | brasão usado no cabeçalho da minuta (padrão GOV-MT) |

## Decisões, modelos e custos

- Provedor de texto: Groq (cota gratuita, API compatível com OpenAI, modelos de pesos abertos).
- Modelo do experimento RF02: `openai/gpt-oss-120b`. Comparação: `gpt-oss-120b`, `gpt-oss-20b`,
  `qwen/qwen3.8-27b` (`llama-3.3-70b-versatile` não estava disponível para a chave). Ver
  `documentacao/comparacao_modelos.md`.
- Preços (16/10/2026, console.groq.com/docs/models), em US$ por milhão de tokens (entrada/saída):
  gpt-oss-120b 0,15 / 0,60; gpt-oss-20b 0,075 / 0,30; qwen3.8-27b 0,80 / 4,00.
- Custo real em 16/10/2026: RF02 ≈ US$ 0,003 e comparação de modelos ≈ US$ 0,032 (detalhe por chamada em
  `resultados/*/<execução>/execucoes.jsonl`).
- Cota gratuita sujeita a HTTP 429: o cliente faz até 5 tentativas com espera, e há pausa de 3 s entre as chamadas.

## Limitações

Ver `documentacao/relatorio_tecnico.md`, seção 9. Principais: verificações automáticas heurísticas,
minimização por regex, defesa contra injection não é absoluta, gabaritos dependem de validação humana.

## Uso de IA no desenvolvimento

Ver `documentacao/registro_uso_ia.md`.
