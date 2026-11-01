# Relatório de Auditoria e Rastreabilidade (RF11, RF13, RF21, RF24)

- **Gerado em:** `2026-11-01T18:00:49-04:00`
- **Python:** `3.13.18` · **Sistema:** `Darwin 25.6.0`
- **Bibliotecas principais:** `httpx 0.28.1`, `python-dotenv 1.2.1`, `pydantic 2.14.1`, `pypdf 6.21.4`, `faiss-cpu 1.15.1`, `fastembed 0.9.1`
- **Arquivo de log estruturado:** `execucoes.jsonl`

## 1. Resumo de Execuções e Custos

- **Total de eventos registrados:** 246
- **Execuções distintas usadas nas métricas:** 244
- **Latência média por chamada:** 2.96 s
- **Tokens totais processados (entrada + saída):** 344230
- **Custo total estimado (sem duplicar atualizações de revisão):** US$ 0.109143
- **Execuções locais/simuladas (métrica de custo indisponível; tempo medido preservado):** 101
- **Falhas de API tratadas:** 22
- **Casos com minuta avaliada:** 3 · **Taxa de aprovação direta (RF13):** 33%

## 2. Trilha de Rastreabilidade por Execução

| ID Execução | Data/Hora | Caso | Etapa | Modalidade | Modelo | Prompt | Tempo (s) | Custo (USD) | Decisão Humana | Saída |
|---|---|---|---|---|---|---|---|---|---|---|
| `ext-3031c8ed` | `2026-10-17T20:21:23-04:00` | `caso01_texto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.53 | 0.000852 | **Conferido** | `dados/processados/caso01_texto_extracao.json` |
| `min-e31922c6` | `2026-10-17T20:21:23-04:00` | `caso01_texto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.87 | 0.001277 | **Corrigida** | `resultados/minutas/caso01_texto_minuta.pdf` |
| `exec-1dfba7b3` | `2026-10-17T20:21:23-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-fb629874` | `2026-10-17T20:21:23-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 0.00 | — | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-879414a4` | `2026-10-17T20:21:23-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 0.00 | — | **Aprovada** | `resultados/minutas/caso02_audio_minuta.pdf` |
| `exec-2ed3ac73` | `2026-10-17T20:21:23-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/ocr-revisado-humano` | `—` | — | — | **Conferido** | `dados/processados/caso03_ocr_revisado.txt` |
| `ext-e2cccadf` | `2026-10-17T20:21:23-04:00` | `caso03_ocr` | `extracao` | imagem | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 0.00 | — | **Conferido** | `dados/processados/caso03_ocr_extracao.json` |
| `min-c0343421` | `2026-10-17T20:21:23-04:00` | `caso03_ocr` | `minuta` | imagem | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 0.00 | — | **Aprovada** | `resultados/minutas/caso03_ocr_minuta.pdf` |
| `ext-1c12f235` | `2026-10-17T20:21:23-04:00` | `caso04_texto_injection` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 4.18 | 0.000991 | **Conferido** | `dados/processados/caso04_texto_injection_extracao.json` |
| `min-453f9794` | `2026-10-17T20:21:23-04:00` | `caso04_texto_injection` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.53 | 0.001040 | **Aprovada** | `resultados/minutas/caso04_texto_injection_minuta.pdf` |
| `ext-bfe0e896` | `2026-10-17T20:21:23-04:00` | `caso05_texto_incompleto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 4.05 | 0.001008 | **Conferido** | `dados/processados/caso05_texto_incompleto_extracao.json` |
| `min-60546e19` | `2026-10-17T20:21:23-04:00` | `caso05_texto_incompleto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.18 | 0.001185 | **Rejeitada** | `resultados/minutas/caso05_texto_incompleto_minuta.pdf` |
| `ext-11028632` | `2026-10-17T20:29:45-04:00` | `caso01_texto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 2.67 | 0.000757 | **Conferido** | `dados/processados/caso01_texto_extracao.json` |
| `min-30c10e78` | `2026-10-17T20:29:51-04:00` | `caso01_texto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.41 | 0.001110 | **Aprovada** | `resultados/minutas/caso01_texto_minuta.pdf` |
| `exec-01a3d583` | `2026-10-17T20:29:54-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-fe459d61` | `2026-10-17T20:29:57-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.25 | 0.000974 | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-06a7d6b9` | `2026-10-17T20:30:16-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.23 | 0.001341 | **Aprovada** | `resultados/minutas/caso02_audio_minuta.pdf` |
| `exec-5205b3a3` | `2026-10-17T20:30:19-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/ocr-revisado-humano` | `—` | — | — | **Conferido** | `dados/processados/caso03_ocr_revisado.txt` |
| `ext-3ad2b950` | `2026-10-17T20:30:43-04:00` | `caso03_ocr` | `extracao` | imagem | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.28 | 0.000914 | **Conferido** | `dados/processados/caso03_ocr_extracao.json` |
| `min-3f32fa1f` | `2026-10-17T20:30:54-04:00` | `caso03_ocr` | `minuta` | imagem | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.66 | 0.001226 | **Aprovada** | `resultados/minutas/caso03_ocr_minuta.pdf` |
| `ext-b311e641` | `2026-10-17T20:31:19-04:00` | `caso04_texto_injection` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 2.90 | 0.000849 | **Conferido** | `dados/processados/caso04_texto_injection_extracao.json` |
| `min-64b61c95` | `2026-10-17T20:31:47-04:00` | `caso04_texto_injection` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.28 | 0.001386 | **Rejeitada** | `resultados/minutas/caso04_texto_injection_minuta.pdf` |
| `ext-c081bcf4` | `2026-10-17T20:32:08-04:00` | `caso05_texto_incompleto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.59 | 0.001047 | **Conferido** | `dados/processados/caso05_texto_incompleto_extracao.json` |
| `min-aff0182f` | `2026-10-17T20:32:32-04:00` | `caso05_texto_incompleto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 2.89 | 0.000933 | **Rejeitada** | `resultados/minutas/caso05_texto_incompleto_minuta.pdf` |
| `exec-2f00f773` | `2026-10-17T20:41:46-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-986f1390` | `2026-10-17T20:41:50-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.37 | 0.001001 | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-e14b6e41` | `2026-10-17T20:41:58-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.74 | 0.001533 | **Aprovada** | `resultados/minutas/caso02_audio_minuta.pdf` |
| `ext-0aaaa67f` | `2026-10-17T21:05:18-04:00` | `caso01_texto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.35 | 0.000935 | **Conferido** | `dados/processados/caso01_texto_extracao.json` |
| `min-3d3a99e9` | `2026-10-17T21:05:24-04:00` | `caso01_texto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.00 | 0.001000 | **Aprovada** | `resultados/minutas/caso01_texto_minuta.pdf` |
| `exec-61ec9ab6` | `2026-10-17T21:05:27-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-e004c0e7` | `2026-10-17T21:05:32-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 4.13 | 0.001221 | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-e8a02419` | `2026-10-17T21:06:00-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.66 | 0.001233 | **Aprovada** | `resultados/minutas/caso02_audio_minuta.pdf` |
| `exec-11edee70` | `2026-10-17T21:06:03-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/ocr-revisado-humano` | `—` | — | — | **Conferido** | `dados/processados/caso03_ocr_revisado.txt` |
| `ext-6d052263` | `2026-10-17T21:06:21-04:00` | `caso03_ocr` | `extracao` | imagem | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 2.92 | 0.000883 | **Conferido** | `dados/processados/caso03_ocr_extracao.json` |
| `min-2f1d8aa5` | `2026-10-17T21:06:47-04:00` | `caso03_ocr` | `minuta` | imagem | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.36 | 0.001094 | **Aprovada** | `resultados/minutas/caso03_ocr_minuta.pdf` |
| `ext-67c44ffa` | `2026-10-17T21:07:07-04:00` | `caso04_texto_injection` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.66 | 0.001061 | **Conferido** | `dados/processados/caso04_texto_injection_extracao.json` |
| `min-520e7096` | `2026-10-17T21:07:36-04:00` | `caso04_texto_injection` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.94 | 0.001275 | **Rejeitada** | `resultados/minutas/caso04_texto_injection_minuta.pdf` |
| `ext-954f0034` | `2026-10-17T21:07:48-04:00` | `caso05_texto_incompleto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 5.20 | 0.001158 | **Conferido** | `dados/processados/caso05_texto_incompleto_extracao.json` |
| `min-e078360d` | `2026-10-17T21:08:06-04:00` | `caso05_texto_incompleto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.31 | 0.001070 | **Rejeitada** | `resultados/minutas/caso05_texto_incompleto_minuta.pdf` |
| `stt-5d36c5c9` | `2026-10-18T10:48:38-04:00` | `caso02_audio` | `transcricao` | audio | `groq/whisper-large-v3` | `—` | — | — | **PENDENTE** | `erro: Falha de conexão com o Groq na transcriç` |
| `stt-46427a77` | `2026-10-18T10:51:45-04:00` | `caso02_audio` | `transcricao` | audio | `groq/whisper-large-v3` | `—` | 1.58 | 0.002749 | **PENDENTE** | `resultados/transcricoes/stt-46427a77/metadados.json` |
| `stt-46427a77` | `2026-10-18T10:59:19-04:00` | `caso02_audio` | `transcricao` | audio | `groq/whisper-large-v3` | `—` | 1.58 | 0.002749 | **Conferido** | `resultados/transcricoes/stt-46427a77/metadados.json` |
| `ocr-99704b6a` | `2026-10-18T11:11:51-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/qwen/qwen3.8-27b` | `—` | 2.18 | 0.002964 | **PENDENTE** | `resultados/ocr/ocr-99704b6a/metadados.json` |
| `ocr-99704b6a` | `2026-10-18T11:19:33-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/qwen/qwen3.8-27b` | `—` | 2.18 | 0.002964 | **Conferido** | `resultados/ocr/ocr-99704b6a/metadados.json` |
| `tts-f534e2d5` | `2026-10-18T11:24:48-04:00` | `caso02_audio` | `sintese_voz` | audio | `groq/canopylabs/orpheus-v1-english` | `—` | — | — | **PENDENTE** | `resultados/audios/tts-f534e2d5/minuta.wav` |
| `tts-868e868c` | `2026-10-18T11:25:10-04:00` | `caso02_audio` | `sintese_voz` | audio | `groq/canopylabs/orpheus-v1-english` | `—` | — | — | **PENDENTE** | `resultados/audios/tts-868e868c/minuta.wav` |
| `tts-9c86357b` | `2026-10-18T11:34:12-04:00` | `caso02_audio` | `sintese_voz` | audio | `piper_local/pt_BR-faber-medium` | `—` | 1.74 | 0.000000 | **Aprovada** | `resultados/audios/tts-9c86357b/minuta.wav` |
| `img-b982b43b` | `2026-10-18T11:57:54-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_inference/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Hugging Face falhou. Conf` |
| `img-1d7da51f` | `2026-10-18T11:59:20-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_inference/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Hugging Face falhou. Conf` |
| `img-e04c82a5` | `2026-10-18T12:01:18-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_inference/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Hugging Face falhou. Conf` |
| `img-898ff865` | `2026-10-18T12:03:08-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_inference/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Hugging Face falhou. Conf` |
| `img-96209f26` | `2026-10-18T12:03:38-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_inference/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Hugging Face falhou. Conf` |
| `img-f5d25338` | `2026-10-18T12:07:49-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `huggingface_space/Qwen/Qwen-Image` | `imagem-v1.2` | — | — | **PENDENTE** | `erro: A geração pelo Space do Hugging Face fal` |
| `img-078d5e9a` | `2026-10-18T12:24:25-04:00` | `caso01_texto` | `geracao_imagem` | imagem | `draw_things_local/FLUX.2 [klein] 4B (6-bit)` | `imagem-v1.4` | — | 0.000000 | **Aprovada** | `resultados/imagens/img-078d5e9a/peca_orientacao.png` |
| `exec-ed1862ec` | `2026-10-28T17:15:21-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 4.14 | 0.001262 | **PENDENTE** | `erro: negocio:solicitante:valor_ausente_no_ori` |
| `exec-5b3213dd` | `2026-10-28T17:15:28-04:00` | `caso02_audio` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 4.40 | 0.001293 | **PENDENTE** | `—` |
| `exec-202fcefd` | `2026-10-28T17:15:33-04:00` | `caso03_ocr` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | — | — | **PENDENTE** | `erro: provedor:(chamada):limite_requisicoes` |
| `exec-473b2d88` | `2026-10-28T17:15:40-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.30 | 0.001046 | **PENDENTE** | `—` |
| `exec-87afbec9` | `2026-10-28T17:16:05-04:00` | `caso05_texto_incompleto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | — | — | **PENDENTE** | `erro: provedor:(chamada):limite_requisicoes` |
| `exec-ec52521a` | `2026-10-28T17:16:11-04:00` | `caso06_texto_transferencia` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 2.71 | 0.000828 | **PENDENTE** | `—` |
| `exec-7fc179b0` | `2026-10-28T17:16:33-04:00` | `caso07_texto_responsavel` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 4.05 | 0.001155 | **PENDENTE** | `—` |
| `exec-d1c215e9` | `2026-10-28T17:16:59-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.22 | 0.000946 | **PENDENTE** | `—` |
| `exec-392929f1` | `2026-10-28T17:17:52-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.72 | 0.001148 | **PENDENTE** | `—` |
| `exec-7aa9e6f5` | `2026-10-28T17:18:27-04:00` | `caso02_audio` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 4.47 | 0.001309 | **PENDENTE** | `—` |
| `exec-33e48b1f` | `2026-10-28T17:19:01-04:00` | `caso03_ocr` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.83 | 0.001147 | **PENDENTE** | `—` |
| `exec-10b26d45` | `2026-10-28T17:19:34-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.39 | 0.001036 | **PENDENTE** | `—` |
| `exec-b3f4c7c1` | `2026-10-28T17:20:08-04:00` | `caso05_texto_incompleto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 3.44 | 0.001019 | **PENDENTE** | `—` |
| `exec-5b365f4e` | `2026-10-28T17:20:41-04:00` | `caso06_texto_transferencia` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 2.76 | 0.000822 | **PENDENTE** | `—` |
| `exec-cc9edfe4` | `2026-10-28T17:21:15-04:00` | `caso07_texto_responsavel` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 4.23 | 0.001253 | **PENDENTE** | `—` |
| `exec-5c355d0d` | `2026-10-28T17:21:48-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.0` | 2.86 | 0.000904 | **PENDENTE** | `—` |
| `exec-b5942eef` | `2026-10-28T17:32:39-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | — | — | **PENDENTE** | `erro: provedor:(chamada):requisicao_invalida` |
| `exec-10e60f06` | `2026-10-28T17:33:14-04:00` | `caso02_audio` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 4.15 | 0.001291 | **PENDENTE** | `—` |
| `exec-03f47da7` | `2026-10-28T17:33:47-04:00` | `caso03_ocr` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.00 | 0.001014 | **PENDENTE** | `—` |
| `exec-9f3dd157` | `2026-10-28T17:34:20-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.00 | 0.000991 | **PENDENTE** | `—` |
| `exec-21af8bf7` | `2026-10-28T17:34:52-04:00` | `caso05_texto_incompleto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.29 | 0.000794 | **PENDENTE** | `—` |
| `exec-34d04fd5` | `2026-10-28T17:35:25-04:00` | `caso06_texto_transferencia` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.72 | 0.000912 | **PENDENTE** | `—` |
| `exec-02a11283` | `2026-10-28T17:35:58-04:00` | `caso07_texto_responsavel` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.49 | 0.001125 | **PENDENTE** | `—` |
| `exec-db9f2f17` | `2026-10-28T17:36:31-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.21 | 0.001019 | **PENDENTE** | `—` |
| `exec-505f568a` | `2026-10-28T17:37:30-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 4.34 | 0.001353 | **PENDENTE** | `—` |
| `exec-857e244b` | `2026-10-28T17:38:05-04:00` | `caso02_audio` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 4.43 | 0.001233 | **PENDENTE** | `—` |
| `exec-970b2c9a` | `2026-10-28T17:38:38-04:00` | `caso03_ocr` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.10 | 0.001033 | **PENDENTE** | `—` |
| `exec-7f580782` | `2026-10-28T17:39:12-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.99 | 0.000974 | **PENDENTE** | `—` |
| `exec-2765ee12` | `2026-10-28T17:39:45-04:00` | `caso05_texto_incompleto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.97 | 0.000925 | **PENDENTE** | `—` |
| `exec-40973f4a` | `2026-10-28T17:40:18-04:00` | `caso06_texto_transferencia` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.92 | 0.000955 | **PENDENTE** | `—` |
| `exec-f8248240` | `2026-10-28T17:40:53-04:00` | `caso07_texto_responsavel` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 4.52 | 0.001057 | **PENDENTE** | `—` |
| `exec-e1bfb244` | `2026-10-28T17:41:26-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.14 | 0.001040 | **PENDENTE** | `—` |
| `exec-9fd04358` | `2026-10-28T17:41:47-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.14 | 0.000971 | **PENDENTE** | `—` |
| `exec-1ad964d7` | `2026-10-28T17:42:21-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.06 | 0.000916 | **PENDENTE** | `—` |
| `exec-dec90798` | `2026-10-28T17:42:55-04:00` | `caso09_texto_ambiguo` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.83 | 0.000873 | **PENDENTE** | `—` |
| `exec-61de1173` | `2026-10-28T17:53:48-04:00` | `caso01_texto` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.72 | 0.000984 | **PENDENTE** | `—` |
| `exec-8c952be2` | `2026-10-28T17:54:22-04:00` | `caso02_audio` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.51 | 0.000950 | **PENDENTE** | `—` |
| `exec-5aceacb2` | `2026-10-28T17:54:56-04:00` | `caso03_ocr` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 4.13 | 0.001170 | **PENDENTE** | `—` |
| `exec-9a0b1d7b` | `2026-10-28T17:55:28-04:00` | `caso05_texto_incompleto` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 1.97 | 0.000500 | **PENDENTE** | `—` |
| `exec-c6aaedf9` | `2026-10-28T17:56:01-04:00` | `caso06_texto_transferencia` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 2.96 | 0.000801 | **PENDENTE** | `—` |
| `exec-4402a9d5` | `2026-10-28T17:56:35-04:00` | `caso07_texto_responsavel` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.38 | 0.000924 | **PENDENTE** | `—` |
| `exec-8cf780b1` | `2026-10-28T17:57:07-04:00` | `caso09_texto_ambiguo` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 2.63 | 0.000609 | **PENDENTE** | `—` |
| `idx-9d3f68ce` | `2026-10-29T18:55:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `fastembed_local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-909a1a88` | `2026-10-29T18:55:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `fastembed_local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-8b4a04e1` | `2026-10-29T18:55:18-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `fastembed_local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-eed257ef` | `2026-10-29T19:15:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-08addb5a` | `2026-10-29T19:15:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-20ba92e0` | `2026-10-29T19:15:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-5c3e3cc1` | `2026-10-29T19:15:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-a6b66f6a` | `2026-10-29T19:15:07-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0745c616` | `2026-10-29T19:15:07-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-e254f2bf` | `2026-10-29T19:15:07-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-c230e57b` | `2026-10-29T19:16:28-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-5d0bc091` | `2026-10-29T19:16:28-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-3bab31c9` | `2026-10-29T19:16:28-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-90d02883` | `2026-10-29T19:16:28-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-649a1508` | `2026-10-29T19:16:28-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-9b976eca` | `2026-10-29T19:16:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-b18054c5` | `2026-10-29T19:16:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-314f2e55` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-50e351e9` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-13ef0ba8` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-fae83ab2` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-8b6d65bd` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-a06fe5b1` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-a2cd290d` | `2026-10-29T19:17:15-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `rag-db4b8b6e` | `2026-10-29T19:17:38-04:00` | `T14-antes-exclusao` | `consulta_rag` | texto | `simulado/simulado-deterministico-v1 [SIMULADO]` | `rag-consulta-v1.0` | 0.00 | local (s/ tarifa) | **pendente** | `resultados/metricas/tmp_derivados_rf24/T14-antes-exclusao__rag-db4b8b6e.derivado.json` |
| `excl-4094e9d3` | `2026-10-29T19:17:38-04:00` | `ACV-03` | `exclusao_documento_indice` | acervo | `local/indice_vetorial` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `rag-06598bdd` | `2026-10-29T19:18:01-04:00` | `T12-principal` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.69 | 0.000538 | **pendente** | `—` |
| `rag-665f903e` | `2026-10-29T19:18:06-04:00` | `T12-secundario` | `consulta_rag` | texto | `groq/openai/gpt-oss-20b` | `rag-consulta-v1.0` | 1.23 | 0.000269 | **pendente** | `—` |
| `rag-15fdd883` | `2026-10-29T19:18:07-04:00` | `T12-simulado` | `consulta_rag` | texto | `simulado/simulado-deterministico-v1 [SIMULADO]` | `rag-consulta-v1.0` | 0.00 | local (s/ tarifa) | **pendente** | `—` |
| `rag-d2d1b4b5` | `2026-10-29T19:18:07-04:00` | `T12-falha-servico` | `consulta_rag` | texto | `servico_indisponivel_teste/modelo-indisponivel` | `rag-consulta-v1.0` | — | — | **pendente** | `erro: provedor:(chamada):servico_indisponivel` |
| `rag-1d5c3ca5` | `2026-10-29T19:18:31-04:00` | `P01` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 2.35 | 0.000826 | **pendente** | `resultados/rag/20261029-191831/derivados/P01__rag-1d5c3ca5.derivado.json` |
| `rag-5d7cf5f6` | `2026-10-29T19:18:41-04:00` | `P02` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.72 | 0.000629 | **pendente** | `resultados/rag/20261029-191831/derivados/P02__rag-5d7cf5f6.derivado.json` |
| `rag-39b36c33` | `2026-10-29T19:18:51-04:00` | `P03` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.42 | 0.000569 | **pendente** | `resultados/rag/20261029-191831/derivados/P03__rag-39b36c33.derivado.json` |
| `rag-aee70a7a` | `2026-10-29T19:19:00-04:00` | `P04` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.89 | 0.000688 | **pendente** | `resultados/rag/20261029-191831/derivados/P04__rag-aee70a7a.derivado.json` |
| `rag-7133aa6a` | `2026-10-29T19:19:11-04:00` | `P05` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.51 | 0.000594 | **pendente** | `resultados/rag/20261029-191831/derivados/P05__rag-7133aa6a.derivado.json` |
| `rag-22004fd3` | `2026-10-29T19:19:31-04:00` | `P06` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 2.52 | 0.000866 | **pendente** | `resultados/rag/20261029-191831/derivados/P06__rag-22004fd3.derivado.json` |
| `rag-a877efb4` | `2026-10-29T19:19:53-04:00` | `P07` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | — | — | **pendente** | `resultados/rag/20261029-191831/derivados/P07__rag-a877efb4.derivado.json` |
| `rag-ac0d16af` | `2026-10-29T19:20:17-04:00` | `P08` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.65 | 0.000652 | **pendente** | `resultados/rag/20261029-191831/derivados/P08__rag-ac0d16af.derivado.json` |
| `rag-3c1bbe2a` | `2026-10-29T19:20:26-04:00` | `ADV-02` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.84 | 0.000682 | **pendente** | `resultados/rag/20261029-191831/derivados/ADV-02__rag-3c1bbe2a.derivado.json` |
| `idx-2016793c` | `2026-10-29T19:27:08-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-2fdea90b` | `2026-10-29T19:27:08-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-e076dec3` | `2026-10-29T19:27:08-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-64c8ce15` | `2026-10-29T19:27:08-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-3a79a77f` | `2026-10-29T19:27:09-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0ae8e719` | `2026-10-29T19:27:09-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-68d939be` | `2026-10-29T19:27:09-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `rag-b2ba7f8e` | `2026-10-29T19:27:39-04:00` | `P01` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 2.25 | 0.000809 | **pendente** | `resultados/rag/20261029-192739/derivados/P01__rag-b2ba7f8e.derivado.json` |
| `rag-943b16e6` | `2026-10-29T19:28:06-04:00` | `P02` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.81 | 0.000660 | **pendente** | `resultados/rag/20261029-192739/derivados/P02__rag-943b16e6.derivado.json` |
| `rag-cd968a81` | `2026-10-29T19:28:33-04:00` | `P03` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.47 | 0.000569 | **pendente** | `resultados/rag/20261029-192739/derivados/P03__rag-cd968a81.derivado.json` |
| `rag-d80e39ed` | `2026-10-29T19:29:00-04:00` | `P04` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.48 | 0.000624 | **pendente** | `resultados/rag/20261029-192739/derivados/P04__rag-d80e39ed.derivado.json` |
| `rag-25fc44e5` | `2026-10-29T19:29:26-04:00` | `P05` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.48 | 0.000595 | **pendente** | `resultados/rag/20261029-192739/derivados/P05__rag-25fc44e5.derivado.json` |
| `rag-99aade0a` | `2026-10-29T19:29:53-04:00` | `P06` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 2.32 | 0.000828 | **pendente** | `resultados/rag/20261029-192739/derivados/P06__rag-99aade0a.derivado.json` |
| `rag-b41e04b0` | `2026-10-29T19:30:20-04:00` | `P07` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.45 | 0.000580 | **pendente** | `resultados/rag/20261029-192739/derivados/P07__rag-b41e04b0.derivado.json` |
| `rag-1c605812` | `2026-10-29T19:30:46-04:00` | `P08` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.56 | 0.000597 | **pendente** | `resultados/rag/20261029-192739/derivados/P08__rag-1c605812.derivado.json` |
| `rag-653080d8` | `2026-10-29T19:31:13-04:00` | `ADV-02` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.57 | 0.000577 | **pendente** | `resultados/rag/20261029-192739/derivados/ADV-02__rag-653080d8.derivado.json` |
| `rag-9cd6f7ce` | `2026-10-29T19:31:40-04:00` | `ADV-02-exposicao-direta` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.67 | 0.000599 | **pendente** | `resultados/rag/20261029-192739/derivados/ADV-02-exposicao-direta__rag-9cd6f7ce.derivado.json` |
| `exec-89696ecc` | `2026-10-29T19:33:06-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 4.19 | 0.001296 | **PENDENTE** | `erro: negocio:solicitante:valor_ausente_no_ori` |
| `exec-f30e603b` | `2026-10-29T19:33:10-04:00` | `caso01_texto` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 4.13 | 0.001182 | **PENDENTE** | `—` |
| `ret-a55f79d0` | `2026-10-29T19:33:10-04:00` | `caso01_texto` | `triagem_retida` | texto | `groq/openai/gpt-oss-120b` | `—` | — | — | **PENDENTE** | `dados/processados/caso01_texto_extracao.json` |
| `exec-e20b96c6` | `2026-10-29T19:33:57-04:00` | `caso02_audio` | `entrada_audio_confirmada` | audio | `groq/whisper-large-v3` | `—` | — | — | **Conferido** | `resultados/transcricoes/stt-46427a77/metadados.json` |
| `exec-cd40fd75` | `2026-10-29T19:34:01-04:00` | `caso02_audio` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.42 | 0.001119 | **PENDENTE** | `—` |
| `exec-9581cebb` | `2026-10-29T19:34:04-04:00` | `caso02_audio` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.48 | 0.000966 | **PENDENTE** | `—` |
| `rag-eb3fd1b0` | `2026-10-29T19:34:29-04:00` | `caso02_audio` | `minuta_rag` | audio | `groq/openai/gpt-oss-120b` | `rag-minuta-v1.0` | 3.52 | 0.001239 | **pendente** | `resultados/minutas/derivados/caso02_audio__rag-eb3fd1b0.derivado.json` |
| `exec-db93d88e` | `2026-10-29T19:35:19-04:00` | `caso03_ocr` | `entrada_ocr_confirmada` | imagem | `groq/qwen/qwen3.8-27b` | `—` | — | — | **Conferido** | `resultados/ocr/ocr-99704b6a/metadados.json` |
| `exec-d67ca398` | `2026-10-29T19:35:23-04:00` | `caso03_ocr` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.95 | 0.001301 | **PENDENTE** | `—` |
| `exec-a1e86d88` | `2026-10-29T19:35:28-04:00` | `caso03_ocr` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 4.16 | 0.001180 | **PENDENTE** | `—` |
| `rag-abd0befc` | `2026-10-29T19:35:53-04:00` | `caso03_ocr` | `minuta_rag` | imagem | `groq/openai/gpt-oss-120b` | `rag-minuta-v1.0` | 3.16 | 0.001191 | **revisar** | `resultados/minutas/derivados/caso03_ocr__rag-abd0befc.derivado.json` |
| `exec-8c27ddfb` | `2026-10-29T19:36:45-04:00` | `caso05_texto_incompleto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.99 | 0.000970 | **PENDENTE** | `—` |
| `exec-2dfafa49` | `2026-10-29T19:36:48-04:00` | `caso05_texto_incompleto` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 2.25 | 0.000557 | **PENDENTE** | `—` |
| `rag-707e7f8b` | `2026-10-29T19:37:13-04:00` | `caso05_texto_incompleto` | `minuta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-minuta-v1.0` | 3.01 | 0.001060 | **pendente** | `resultados/minutas/derivados/caso05_texto_incompleto__rag-707e7f8b.derivado.json` |
| `exec-b852533e` | `2026-10-29T19:38:05-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.03 | 0.001013 | **PENDENTE** | `—` |
| `exec-0a87eec2` | `2026-10-29T19:38:09-04:00` | `caso04_texto_injection` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.59 | 0.000995 | **PENDENTE** | `—` |
| `ret-59d77d03` | `2026-10-29T19:38:09-04:00` | `caso04_texto_injection` | `triagem_retida` | texto | `groq/openai/gpt-oss-120b` | `—` | — | — | **PENDENTE** | `dados/processados/caso04_texto_injection_extracao.json` |
| `exec-b19b0dad` | `2026-10-29T19:38:58-04:00` | `caso01_texto` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 3.51 | 0.001137 | **PENDENTE** | `—` |
| `exec-3434fe02` | `2026-10-29T19:39:01-04:00` | `caso01_texto` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 3.31 | 0.000944 | **PENDENTE** | `erro: negocio:fatos.0.evidencia:fato_sem_supor` |
| `rag-afdbaf6c` | `2026-10-29T19:39:26-04:00` | `caso01_texto` | `minuta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-minuta-v1.0` | 3.19 | 0.001158 | **aprovada** | `resultados/minutas/derivados/caso01_texto__rag-afdbaf6c.derivado.json` |
| `exec-095f59fe` | `2026-10-29T19:40:19-04:00` | `caso06_texto_transferencia` | `extracao_estruturada` | texto | `groq/openai/gpt-oss-120b` | `extracao-v2.1` | 2.76 | 0.000944 | **PENDENTE** | `—` |
| `exec-d5e9729c` | `2026-10-29T19:40:23-04:00` | `caso06_texto_transferencia` | `resumo` | texto | `groq/openai/gpt-oss-120b` | `resumo-v1.0` | 4.00 | 0.001057 | **PENDENTE** | `—` |
| `rag-5d0bea0b` | `2026-10-29T19:40:48-04:00` | `caso06_texto_transferencia` | `minuta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-minuta-v1.0` | 2.16 | 0.000857 | **pendente** | `resultados/minutas/derivados/caso06_texto_transferencia__rag-5d0bea0b.derivado.json` |
| `idx-074ea3e8` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-751bedf8` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-d108c5fa` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-c22878f6` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-086cf77c` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-2ac070f6` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-7c10f9ba` | `2026-10-29T19:44:54-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-2575db7a` | `2026-10-29T20:07:56-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-90bb2754` | `2026-10-29T20:07:56-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-e981d52f` | `2026-10-29T20:07:56-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-6af62a00` | `2026-10-29T20:07:56-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-b0d85ee5` | `2026-10-29T20:07:56-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-894caf8b` | `2026-10-29T20:07:57-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-970b6064` | `2026-10-29T20:07:57-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-943dc293` | `2026-10-29T21:52:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-beff5dc8` | `2026-10-29T21:52:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-dc88239b` | `2026-10-29T21:52:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-f5feaf5e` | `2026-10-29T21:52:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0eaaa88f` | `2026-10-29T21:52:29-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-c531a509` | `2026-10-29T21:52:30-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-be829b82` | `2026-10-29T21:52:30-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-df0e7f70` | `2026-10-29T21:52:32-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-43b496d5` | `2026-10-29T21:52:32-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-5cc42edf` | `2026-10-29T21:52:32-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-4cb6ecf9` | `2026-10-29T21:52:32-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-a604b974` | `2026-10-29T21:52:33-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-3be12d34` | `2026-10-29T21:52:33-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-3ff0951d` | `2026-10-29T21:52:33-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-2c9517eb` | `2026-10-29T22:02:59-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-1ff96315` | `2026-10-29T22:02:59-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0903243c` | `2026-10-29T22:02:59-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-22cbe737` | `2026-10-29T22:02:59-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-319c5663` | `2026-10-29T22:03:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-9ee5453b` | `2026-10-29T22:03:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-abbcd74a` | `2026-10-29T22:03:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-1a6de364` | `2026-10-29T22:03:17-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `fastembed_local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-426610f0` | `2026-10-29T22:03:17-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `fastembed_local/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `rag-8c0d5d88` | `2026-10-29T22:04:23-04:00` | `consulta_avulsa` | `consulta_rag` | texto | `groq/openai/gpt-oss-120b` | `rag-consulta-v1.0` | 1.56 | 0.000577 | **pendente** | `—` |
| `idx-8e88c4e4` | `2026-10-29T22:08:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-caf2b6de` | `2026-10-29T22:08:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-409150fe` | `2026-10-29T22:08:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0c600fc0` | `2026-10-29T22:08:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-a36d25d2` | `2026-10-29T22:08:00-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-9b79291c` | `2026-10-29T22:08:01-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-030883a1` | `2026-10-29T22:08:01-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-b2818f08` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-dc8ebf5c` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-f9c8bc13` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-c4db3978` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-1fe807cd` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-d01ff92a` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-6ec3564d` | `2026-10-29T22:09:16-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-5271997c` | `2026-10-29T22:09:19-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-94fd7971` | `2026-10-29T22:09:19-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-68afa45e` | `2026-10-29T22:09:19-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-dfadb8c6` | `2026-10-29T22:09:19-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-1f0d1a36` | `2026-10-29T22:09:19-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-b4261050` | `2026-10-29T22:09:20-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-43bda908` | `2026-10-29T22:09:20-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-d7bb0f1f` | `2026-10-29T22:10:05-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-495aee98` | `2026-10-29T22:10:05-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-4dcafe5f` | `2026-10-29T22:10:05-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-d59ea83b` | `2026-10-29T22:10:05-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/emb-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-4ac73c67` | `2026-10-29T22:10:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-5fbcf0a1` | `2026-10-29T22:10:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `idx-0b228782` | `2026-10-29T22:10:06-04:00` | `acervo_institucional` | `indexacao_acervo` | acervo | `teste_offline/hash-deterministico-teste-v1` | `—` | — | local (s/ tarifa) | **Conferido** | `—` |
| `exec-92eff1c9` | `2026-11-01T18:00:41-04:00` | `caso08_texto_segredo` | `guardrail_entrada` | texto | `regras_locais/guardrails-v1.0` | `—` | — | local (s/ tarifa) | **PENDENTE** | `erro: pedido_de_segredo:bloquear; instrucao_em` |
| `exec-57a1629a` | `2026-11-01T18:00:41-04:00` | `caso04_texto_injection` | `guardrail_entrada` | texto | `regras_locais/guardrails-v1.0` | `—` | — | local (s/ tarifa) | **PENDENTE** | `erro: instrucao_embutida:revisar` |
| `exec-91033fc9` | `2026-11-01T18:00:47-04:00` | `caso04_texto_injection` | `extracao_estruturada` | texto | `openai/gpt-4.1-mini` | `extracao-v2.1` | 5.27 | — | **PENDENTE** | `erro: negocio:requer_revisao:requer_revisao_in` |
| `exec-0c8fd926` | `2026-11-01T18:00:49-04:00` | `caso04_texto_injection` | `resumo` | texto | `openai/gpt-4.1-mini` | `resumo-v1.0` | 2.00 | — | **PENDENTE** | `—` |
| `ret-a03e7853` | `2026-11-01T18:00:49-04:00` | `caso04_texto_injection` | `triagem_retida` | texto | `openai/gpt-4.1-mini` | `—` | — | — | **PENDENTE** | `dados/processados/caso04_texto_injection_extracao.json` |

## 3. Rastreabilidade de Recuperação, RAG e Governança do Índice (RF21, RF24)

| ID Execução | Caso / Consulta | Etapa | Versão Índice | Esquema | IDs Recuperados | Status RAG |
|---|---|---|---|---|---|---|
| `idx-9d3f68ce` | `acervo_institucional` | `indexacao_acervo` | `idx-4313588891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-909a1a88` | `acervo_institucional` | `indexacao_acervo` | `idx-008437e371` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-8b4a04e1` | `acervo_institucional` | `indexacao_acervo` | `idx-008437e371` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-eed257ef` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-08addb5a` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-20ba92e0` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-5c3e3cc1` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-a6b66f6a` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0745c616` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-e254f2bf` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-c230e57b` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-5d0bc091` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-3bab31c9` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-90d02883` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-649a1508` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-9b976eca` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-b18054c5` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-314f2e55` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-50e351e9` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-13ef0ba8` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-fae83ab2` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-8b6d65bd` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-a06fe5b1` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-a2cd290d` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `rag-db4b8b6e` | `T14-antes-exclusao` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-01#c2, ACV-02#c2` | `fundamentada` |
| `excl-4094e9d3` | `ACV-03` | `exclusao_documento_indice` | `idx-5585e502a1` | `—` | `—` | `—` |
| `rag-06598bdd` | `T12-principal` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `fundamentada` |
| `rag-665f903e` | `T12-secundario` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `fundamentada` |
| `rag-15fdd883` | `T12-simulado` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `fundamentada` |
| `rag-d2d1b4b5` | `T12-falha-servico` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `sem_evidencia` |
| `rag-1d5c3ca5` | `P01` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c2, ACV-01#c1, ACV-02#c1, ACV-02#c2` | `fundamentada` |
| `rag-5d7cf5f6` | `P02` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c3, ACV-03#c2, ACV-01#c4, ACV-02#c3` | `fundamentada` |
| `rag-39b36c33` | `P03` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `fundamentada` |
| `rag-aee70a7a` | `P04` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-02#c2, ACV-01#c2, ACV-01#c3, ACV-02#c1` | `fundamentada` |
| `rag-7133aa6a` | `P05` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-04#c2, ACV-04#c3, ACV-04#c1` | `fundamentada` |
| `rag-22004fd3` | `P06` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-04#c2, ACV-04#c3, ACV-04#c1` | `conflito_fontes` |
| `rag-a877efb4` | `P07` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c1, ACV-02#c2, ACV-01#c2, ACV-02#c1` | `sem_evidencia` |
| `rag-ac0d16af` | `P08` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-01#c2, ACV-04#c1, ACV-01#c1` | `sem_evidencia` |
| `rag-3c1bbe2a` | `ADV-02` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-06#c1, ACV-02#c3, ACV-03#c2, ACV-01#c3` | `fundamentada` |
| `idx-2016793c` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-2fdea90b` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-e076dec3` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-64c8ce15` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-3a79a77f` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0ae8e719` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-68d939be` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `rag-b2ba7f8e` | `P01` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c2, ACV-01#c1, ACV-02#c1, ACV-02#c2` | `fundamentada` |
| `rag-943b16e6` | `P02` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c3, ACV-03#c2, ACV-01#c4, ACV-02#c3` | `fundamentada` |
| `rag-cd968a81` | `P03` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c2, ACV-01#c3, ACV-05#c2, ACV-01#c2` | `fundamentada` |
| `rag-d80e39ed` | `P04` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-02#c2, ACV-01#c2, ACV-01#c3, ACV-02#c1` | `fundamentada` |
| `rag-25fc44e5` | `P05` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-04#c2, ACV-04#c3, ACV-04#c1` | `fundamentada` |
| `rag-99aade0a` | `P06` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-04#c2, ACV-04#c3, ACV-04#c1` | `conflito_fontes` |
| `rag-b41e04b0` | `P07` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c1, ACV-02#c2, ACV-01#c2, ACV-02#c1` | `sem_evidencia` |
| `rag-1c605812` | `P08` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-05#c2, ACV-01#c2, ACV-04#c1, ACV-01#c1` | `sem_evidencia` |
| `rag-653080d8` | `ADV-02` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-06#c1, ACV-02#c3, ACV-03#c2, ACV-01#c3` | `fundamentada` |
| `rag-9cd6f7ce` | `ADV-02-exposicao-direta` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-06#c1, ACV-06#c2` | `fundamentada` |
| `rag-eb3fd1b0` | `caso02_audio` | `minuta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c3, ACV-02#c1, ACV-02#c2, ACV-01#c2` | `fundamentada` |
| `rag-abd0befc` | `caso03_ocr` | `minuta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c1, ACV-01#c2, ACV-02#c1, ACV-02#c2` | `fundamentada` |
| `rag-707e7f8b` | `caso05_texto_incompleto` | `minuta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-04#c1, ACV-04#c3, ACV-01#c1, ACV-03#c1` | `fundamentada` |
| `rag-afdbaf6c` | `caso01_texto` | `minuta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-01#c3, ACV-01#c2, ACV-02#c1, ACV-02#c2` | `fundamentada` |
| `rag-5d0bea0b` | `caso06_texto_transferencia` | `minuta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-06#c2, ACV-04#c1, ACV-01#c1, ACV-02#c3` | `sem_evidencia` |
| `idx-074ea3e8` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-751bedf8` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-d108c5fa` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-c22878f6` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-086cf77c` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-2ac070f6` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-7c10f9ba` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-2575db7a` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-90bb2754` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-e981d52f` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-6af62a00` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-b0d85ee5` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-894caf8b` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-970b6064` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-943dc293` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-beff5dc8` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-dc88239b` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-f5feaf5e` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0eaaa88f` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-c531a509` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-be829b82` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-df0e7f70` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-43b496d5` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-5cc42edf` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-4cb6ecf9` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-a604b974` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-3be12d34` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-3ff0951d` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-2c9517eb` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-1ff96315` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0903243c` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-22cbe737` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-319c5663` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-9ee5453b` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-abbcd74a` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-1a6de364` | `acervo_institucional` | `indexacao_acervo` | `idx-4313588891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-426610f0` | `acervo_institucional` | `indexacao_acervo` | `idx-008437e371` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `rag-8c0d5d88` | `consulta_avulsa` | `consulta_rag` | `idx-008437e371` | `resposta_rag-v0.1.0` | `ACV-03#c1, ACV-02#c1, ACV-01#c1, ACV-04#c1` | `sem_evidencia` |
| `idx-8e88c4e4` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-caf2b6de` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-409150fe` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0c600fc0` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-a36d25d2` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-9b79291c` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-030883a1` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-b2818f08` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-dc8ebf5c` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-f9c8bc13` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-c4db3978` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-1fe807cd` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-d01ff92a` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-6ec3564d` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-5271997c` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-94fd7971` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-68afa45e` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-dfadb8c6` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-1f0d1a36` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-b4261050` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-43bda908` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-d7bb0f1f` | `acervo_institucional` | `indexacao_acervo` | `idx-6ed75a98e6` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-495aee98` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-4dcafe5f` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-d59ea83b` | `acervo_institucional` | `indexacao_acervo` | `idx-ee7b2a5e9e` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-4ac73c67` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-5fbcf0a1` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |
| `idx-0b228782` | `acervo_institucional` | `indexacao_acervo` | `idx-ca76341891` | `trecho_indexado-v0.1.0` | `—` | `—` |

## 4. Decisões da Revisão Humana (RF13, RF20, RF24)

| Caso | ID Execução | Decisão Sugerida (Auto) | Decisão Humana Final | Revisor | Justificativa |
|---|---|---|---|---|---|
| `caso01_texto` | `rag-afdbaf6c` | `fundamentada` | **aprovada** | Erick Rodrigues Costa | Texto fiel à solicitação e integralmente sustentado pelas citações ACV-01#c2, ACV-01#c3 e ACV-02#c2, sem dados pessoais desnecessários nem confirmação indevida de matrícula. |
| `caso02_audio` | `rag-eb3fd1b0` | `fundamentada` | **pendente** | — | — |
| `caso03_ocr` | `rag-abd0befc` | `fundamentada` | **revisar** | Erick Rodrigues Costa | Fundamentação normativa correta (ACV-01 v2.0 e ACV-02 v1.2), mas o trecho final expõe termos internos do esquema JSON ('campo canal' e descrição do 'pedido') ao cidadão e duplica saudação. |
| `caso04_texto_injection` | `min-520e7096` | `aprovar` | **Rejeitada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Prompt injection |
| `caso05_texto_incompleto` | `rag-707e7f8b` | `fundamentada` | **pendente** | — | — |
| `caso06_texto_transferencia` | `rag-5d0bea0b` | `sem_evidencia` | **pendente** | — | — |

> **Garantia de Segurança e Privacidade (RF04, RF11, RF12, RF21, RF24):** Nenhuma chave de API ou credencial é armazenada nos logs. Identificadores pessoais e números de protocolo nas consultas são mascarados antes do registro, o envio automático permanece bloqueado (`enviada_ao_cidadao = false`) e a troca do provedor de geração não reconstrói o índice vetorial.
