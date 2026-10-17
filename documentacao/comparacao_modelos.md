# Seleção e comparação de modelos (Estudante 1)

Versão 1.0 · 16/10/2026. Preços consultados em [https://console.groq.com/docs/models](https://console.groq.com/docs/models) em 16/10/2026.

## 1. Critérios de seleção


| Critério                | Por que importa neste projeto                                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Finalidade              | Extração estruturada (JSON) e redação institucional em português; não exige raciocínio longo.                                      |
| Custo                   | Protótipo educacional: prioridade para cota gratuita e preço público por token.                                                    |
| Privacidade             | Dados de cidadãos seriam pessoais em cenário real: minimização antes do envio e preferência por modelo que possa rodar localmente. |
| Abertura                | Modelos de pesos abertos podem ser hospedados pela própria instituição (soberania, menor dependência de fornecedor).               |
| Multimodalidade         | Áudio e imagem são tratados pelo Estudante 3; para texto, basta um modelo de linguagem.                                            |
| Conformidade de formato | Suporte a saída JSON (`response_format`) e obediência a instruções de sistema.                                                     |


## 2. Candidatos (texto)


| Modelo (Groq)         | Tipo                                            | Pesos abertos    | Preço entrada / saída (USD por 1M tokens) | Observação                                                                                                                      |
| --------------------- | ----------------------------------------------- | ---------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `openai/gpt-oss-120b` | Modelo de raciocínio (MoE, 120B)                | Sim (Apache 2.0) | 0,15 / 0,60                               | Modelo principal do experimento RF02                                                                                            |
| `openai/gpt-oss-20b`  | Modelo de raciocínio (MoE, 20B)                 | Sim (Apache 2.0) | 0,075 / 0,30                              | Pequeno o bastante para rodar localmente em GPU de consumo                                                                      |
| `qwen/qwen3.8-27b`    | Modelo de linguagem denso 27B (preview no Groq) | Sim              | 0,80 / 4,00                               | Substituiu `llama-3.3-70b-versatile`, que não está disponível para a chave usada ("Contact Sales"); preview = só para avaliação |


Distinção usada no relatório: **IA** (campo amplo) ⊃ **aprendizado de máquina** (aprende com dados) ⊃
**aprendizado profundo** (redes neurais profundas) ⊃ **IA generativa** (gera conteúdo novo) ⊃ **modelos de
linguagem** (geram texto, prevendo tokens) ⊃ **modelos de raciocínio** (LLMs treinados para produzir uma
cadeia de raciocínio interna antes da resposta — mais lentos e com mais tokens de saída, em geral mais
precisos em instruções complexas).

## 3. Experimento comparativo

Comando: `python -m src.experimento_prompts modelos`

Mesmos prompts de produção (extração v1.0 + minuta v1.0) e mesmos parâmetros (`temperature 0.2`,
`top_p 1.0`, `max_tokens 4096`, JSON mode), mesmos casos (01 texto, 04 injection, 05 incompleto).
Métricas: JSON válido, acurácia de campos contra o gabarito, resistência a injection, achados críticos e
altos, latência, tokens e custo estimado. Resultado: `resultados/comparacao_modelos/<execução>/matriz_modelos.md`.

## 4. Resultado e escolha

Execução principal: `resultados/comparacao_modelos/20261016-201709/` (16/10/2026, 18 chamadas, US$ 0,032 no total).


| Modelo                | JSON válido | Acurácia de campos (extração) | Injection resistida | Achados críticos | Achados altos | Latência média | Tokens totais | Custo estimado (USD) | Minutas aprovadas (sugestão automática) |
| --------------------- | ----------- | ----------------------------- | ------------------- | ---------------- | ------------- | -------------- | ------------- | -------------------- | --------------------------------------- |
| `openai/gpt-oss-120b` | 6/6         | 33/33                         | sim                 | 0                | 1             | 4,06 s         | 18 235        | 0,006353             | 67%                                     |
| `openai/gpt-oss-20b`  | 6/6         | 32/33                         | sim                 | 0                | 3             | 3,07 s         | 21 750        | 0,004207             | 33%                                     |
| `qwen/qwen3.8-27b`    | 6/6         | 33/33                         | sim                 | 0                | 0             | 2,64 s         | 13 739        | 0,021305             | 100%                                    |


Execução anterior `20261016-201019` (guardada como evidência): uma chamada do Qwen falhou com HTTP 429
(limite da cota gratuita) após 3 tentativas, e o gpt-oss-20b devolveu um JSON inválido uma vez. Ambas as
falhas foram detectadas e registradas sem interromper o experimento. Depois disso, a configuração passou a
usar 5 tentativas e uma pausa de 3 s entre as chamadas.

Observações (não são decisão):

- Os modelos gpt-oss (raciocínio) gastam de 2 a 3 vezes mais tokens de saída por causa do raciocínio interno.
- O Qwen é o mais caro por token (preview), embora gere menos tokens.
- Os dois gpt-oss inventaram procedimento de trancamento no caso 05.

## 5. Quando preferir processamento local

Em produção, solicitações de cidadãos contêm dados pessoais (e às vezes sensíveis). Um modelo aberto
servido na infraestrutura do órgão (ex.: `gpt-oss-20b` via Ollama/vLLM) evita a transferência desses dados
para terceiros e reduz a dependência de fornecedor, ao custo de manter hardware e atualizações. O código
já aceita o perfil `ollama` em `config.json` sem mudanças nos prompts.