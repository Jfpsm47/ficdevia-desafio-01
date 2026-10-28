# RF14 — Extração estruturada (20261028-174218)

Modelo: `openai/gpt-oss-120b` · modo: `json_schema_estrito` · contrato: `solicitacao_extraida-v0.1.0` · prompt: `extracao-v2.1` · custo total estimado: US$ 0.000916

Conferência automática contra os gabaritos validados (`dados/gabaritos/d2/solicitacoes/`). Campos curtos = protocolo, data, canal, solicitante e curso.

| Caso | Estado | Chamadas | Encaminhamento | Categoria | Campos curtos | Ausentes | Requer revisão | Alerta | Dado proibido presente | Erros finais |
|---|---|---|---|---|---|---|---|---|---|---|
| caso09_texto_ambiguo | valida | 1 | minuta_pendente_de_aprovacao (ERRO) | outros (ERRO) | 5/5 | ok | ERRO | ok | — | — |
