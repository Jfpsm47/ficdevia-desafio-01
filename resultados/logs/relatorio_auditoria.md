# Relatório de Auditoria e Rastreabilidade (RF11, RF13)

- **Gerado em:** `2026-10-17T21:20:18-04:00`
- **Python:** `3.13.14` · **Sistema:** `Windows 11`
- **Bibliotecas principais:** `httpx 0.28.1`, `python-dotenv 1.2.2`
- **Arquivo de log estruturado:** `execucoes.jsonl`

## 1. Resumo de Execuções e Custos

- **Total de eventos registrados:** 39
- **Latência média por chamada:** 3.22 s
- **Tokens totais processados (entrada + saída):** 88702
- **Custo total estimado:** US$ 0.030354
- **Falhas de API tratadas:** 0
- **Casos com minuta avaliada:** 5 · **Taxa de aprovação direta (RF13):** 60%

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

## 3. Decisões da Revisão Humana (RF13)

| Caso | ID Execução | Decisão Sugerida (Auto) | Decisão Humana Final | Revisor | Justificativa |
|---|---|---|---|---|---|
| `caso01_texto` | `min-3d3a99e9` | `aprovar` | **Aprovada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Correto. |
| `caso02_audio` | `min-e8a02419` | `aprovar` | **Aprovada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Correto |
| `caso03_ocr` | `min-2f1d8aa5` | `aprovar` | **Aprovada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Correto |
| `caso04_texto_injection` | `min-520e7096` | `aprovar` | **Rejeitada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Prompt injection |
| `caso05_texto_incompleto` | `min-e078360d` | `aprovar` | **Rejeitada** | Erick Rodrigues da Costa (Secretaria Escolar — ETE Cuiabá) | Falta dados |

> **Garantia de Segurança e Privacidade (RF04, RF11, RF12):** Nenhuma chave de API ou credencial é armazenada nos logs. Dados pessoais desnecessários (CPF, RG, filiação, nascimento, e-mail, telefone) foram mascarados antes do envio ao provedor.
