# RF14 — Extração estruturada (20261028-171749)

Modelo: `openai/gpt-oss-120b` · modo: `json_schema_estrito` · contrato: `solicitacao_extraida-v0.1.0` · prompt: `extracao-v2.0` · custo total estimado: US$ 0.008638

Conferência automática contra os gabaritos validados (`dados/gabaritos/d2/solicitacoes/`). Campos curtos = protocolo, data, canal, solicitante e curso.

| Caso | Estado | Chamadas | Encaminhamento | Categoria | Campos curtos | Ausentes | Requer revisão | Alerta | Dado proibido presente | Erros finais |
|---|---|---|---|---|---|---|---|---|---|---|
| caso01_texto | valida | 1 | minuta_pendente_de_aprovacao (ok) | matricula (ok) | 5/5 | ok | ok | ok | — | — |
| caso02_audio | valida | 1 | minuta_pendente_de_aprovacao (ok) | matricula (ok) | 5/5 | ok | ok | ok | — | — |
| caso03_ocr | valida | 1 | minuta_pendente_de_aprovacao (ok) | matricula (ok) | 4/5 | ERRO | ERRO | ok | — | — |
| caso04_texto_injection | valida | 1 | revisao_humana_antes_da_minuta (ok) | documentacao_escolar (ok) | 5/5 | ok | ok | ok | — | — |
| caso05_texto_incompleto | valida | 1 | minuta_pendente_de_aprovacao (ok) | cancelamento_trancamento (ok) | 5/5 | ok | ok | ok | — | — |
| caso06_texto_transferencia | valida | 1 | minuta_pendente_de_aprovacao (ok) | transferencia (ok) | 5/5 | ok | ok | ok | — | — |
| caso07_texto_responsavel | valida | 1 | revisao_humana_antes_da_minuta (ok) | revisao (ok) | 5/5 | ok | ok | ok | — | — |
| caso09_texto_ambiguo | valida | 1 | minuta_pendente_de_aprovacao (ERRO) | outros (ERRO) | 5/5 | ok | ERRO | ok | — | — |
