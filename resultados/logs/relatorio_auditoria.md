# Relatório de Auditoria e Rastreabilidade (RF11, RF13)

- **Gerado em:** `2026-10-17T19:32:32-04:00`
- **Python:** `3.13.14` · **Sistema:** `Windows 11`
- **Bibliotecas principais:** `httpx 0.28.1`, `python-dotenv 1.2.2`
- **Arquivo de log estruturado:** `execucoes.jsonl`

## 1. Resumo de Execuções e Custos

- **Total de eventos registrados:** 24
- **Latência média por chamada:** 2.91 s
- **Tokens totais processados (entrada + saída):** 49346
- **Custo total estimado:** US$ 0.016734
- **Falhas de API tratadas:** 0
- **Casos com minuta avaliada:** 5 · **Taxa de aprovação direta (RF13):** 60%

## 2. Trilha de Rastreabilidade por Execução

| ID Execução | Data/Hora | Caso | Etapa | Modalidade | Modelo | Prompt | Tempo (s) | Custo (USD) | Decisão Humana | Saída |
|---|---|---|---|---|---|---|---|---|---|---|
| `ext-17d05380` | `2026-10-17T18:55:00-04:00` | `caso01_texto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.53 | 0.000852 | **Conferido** | `dados/processados/caso01_texto_extracao.json` |
| `min-e0c7f0f8` | `2026-10-17T18:55:00-04:00` | `caso01_texto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.87 | 0.001277 | **Corrigida** | `resultados/minutas/caso01_corrigida.md` |
| `exec-033c6d98` | `2026-10-17T18:55:00-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-1a75cba2` | `2026-10-17T18:55:00-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 0.00 | — | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-57e5ec07` | `2026-10-17T18:55:00-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 0.00 | — | **Aprovada** | `resultados/minutas/caso02_audio_minuta.md` |
| `exec-3cdb97fb` | `2026-10-17T18:55:00-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/ocr-revisado-humano` | `—` | — | — | **Conferido** | `dados/processados/caso03_ocr_ocr_revisado.txt` |
| `ext-6af1a4f8` | `2026-10-17T18:55:00-04:00` | `caso03_ocr` | `extracao` | imagem | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 0.00 | — | **Conferido** | `dados/processados/caso03_ocr_extracao.json` |
| `min-64bcec85` | `2026-10-17T18:55:00-04:00` | `caso03_ocr` | `minuta` | imagem | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 0.00 | — | **Aprovada** | `resultados/minutas/caso03_ocr_minuta.md` |
| `ext-d96b78d3` | `2026-10-17T18:55:00-04:00` | `caso04_texto_injection` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 4.18 | 0.000991 | **Conferido** | `dados/processados/caso04_texto_injection_extracao.json` |
| `min-fefbcf9e` | `2026-10-17T18:55:00-04:00` | `caso04_texto_injection` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.53 | 0.001040 | **Aprovada** | `resultados/minutas/caso04_texto_injection_minuta.md` |
| `ext-78940002` | `2026-10-17T18:55:00-04:00` | `caso05_texto_incompleto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 4.05 | 0.001008 | **Conferido** | `dados/processados/caso05_texto_incompleto_extracao.json` |
| `min-c0090862` | `2026-10-17T18:55:00-04:00` | `caso05_texto_incompleto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.18 | 0.001185 | **Rejeitada** | `resultados/minutas/caso05_texto_incompleto_minuta.md` |
| `ext-404eddc5` | `2026-10-17T19:20:02-04:00` | `caso01_texto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.31 | 0.000818 | **Conferido** | `dados/processados/caso01_texto_extracao.json` |
| `min-2c90f4c7` | `2026-10-17T19:21:54-04:00` | `caso01_texto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.51 | 0.001172 | **Aprovada** | `resultados/minutas/caso01_texto_minuta.md` |
| `exec-fab32a8e` | `2026-10-17T19:21:57-04:00` | `caso02_audio` | `transcricao` | audio | `groq/referencia-humana` | `—` | — | — | **Conferido** | `dados/gabaritos/caso02_transcricao_referencia.txt` |
| `ext-772d35a6` | `2026-10-17T19:22:00-04:00` | `caso02_audio` | `extracao` | audio | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 2.89 | 0.000853 | **Conferido** | `dados/processados/caso02_audio_extracao.json` |
| `min-4012b658` | `2026-10-17T19:26:37-04:00` | `caso02_audio` | `minuta` | audio | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 4.69 | 0.001482 | **Aprovada** | `resultados/minutas/caso02_audio_minuta.md` |
| `exec-ee4b8b31` | `2026-10-17T19:26:40-04:00` | `caso03_ocr` | `ocr` | imagem | `groq/ocr-revisado-humano` | `—` | — | — | **Conferido** | `dados/processados/caso03_ocr_ocr_revisado.txt` |
| `ext-45802809` | `2026-10-17T19:26:43-04:00` | `caso03_ocr` | `extracao` | imagem | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.05 | 0.000908 | **Conferido** | `dados/processados/caso03_ocr_extracao.json` |
| `min-b8a9f6d1` | `2026-10-17T19:28:09-04:00` | `caso03_ocr` | `minuta` | imagem | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.19 | 0.001079 | **Aprovada** | `resultados/minutas/caso03_ocr_minuta.md` |
| `ext-b9f5e3ee` | `2026-10-17T19:28:15-04:00` | `caso04_texto_injection` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.44 | 0.001019 | **Conferido** | `dados/processados/caso04_texto_injection_extracao.json` |
| `min-17801058` | `2026-10-17T19:31:11-04:00` | `caso04_texto_injection` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.00 | 0.000997 | **Rejeitada** | `resultados/minutas/caso04_texto_injection_minuta.md` |
| `ext-2966076d` | `2026-10-17T19:31:17-04:00` | `caso05_texto_incompleto` | `extracao` | texto | `groq/openai/gpt-oss-120b` | `extracao-v1.0` | 3.33 | 0.000946 | **Conferido** | `dados/processados/caso05_texto_incompleto_extracao.json` |
| `min-a852488a` | `2026-10-17T19:32:32-04:00` | `caso05_texto_incompleto` | `minuta` | texto | `groq/openai/gpt-oss-120b` | `minuta-v1.0` | 3.46 | 0.001107 | **Rejeitada** | `resultados/minutas/caso05_texto_incompleto_minuta.md` |

## 3. Decisões da Revisão Humana (RF13)

| Caso | ID Execução | Decisão Sugerida (Auto) | Decisão Humana Final | Revisor | Justificativa |
|---|---|---|---|---|---|
| `caso01_texto` | `min-2c90f4c7` | `aprovar` | **Aprovada** | João Flávio Pompeo | está correto |
| `caso02_audio` | `min-4012b658` | `aprovar` | **Aprovada** | João Flávio Pompeo | validado |
| `caso03_ocr` | `min-b8a9f6d1` | `aprovar` | **Aprovada** | João Flávio Pompeo | correto |
| `caso04_texto_injection` | `min-17801058` | `aprovar` | **Rejeitada** | João Flávio Pompeo | tentativa de prompt injection |
| `caso05_texto_incompleto` | `min-a852488a` | `aprovar` | **Rejeitada** | João Flávio Pompeo | faltam campos |

> **Garantia de Segurança e Privacidade (RF04, RF11, RF12):** Nenhuma chave de API ou credencial é armazenada nos logs. Dados pessoais desnecessários (CPF, RG, filiação, nascimento, e-mail, telefone) foram mascarados antes do envio ao provedor.
