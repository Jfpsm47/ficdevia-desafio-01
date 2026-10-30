# RF18 — Comparação de Chunking e Recuperação

- **Modelo de embedding:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (`fastembed_local`, dimensão `384`)
- **Busca avaliada:** `top_k = 3` sobre as 5 perguntas respondíveis (`P01` a `P05`)
- **Unidade declarada:** `caracteres`
- **Configuração selecionada:** **`config_b_contextual`** (`caracteres-700-sobreposicao-120`)

## 1. Resumo das Configurações

| Configuração | Parâmetros (`unidade-tam-sobreposicao`) | Total de Chunks | Média (chars) | Acerto Top-k (`P01..P05`) | Cobertura Integral de Refs | Lista integral de `P01` no Top-1 |
|---|---|---:|---:|---|---|---|
| `config_a_granular` | `caracteres-320-sobreposicao-50` | 37 | 225.9 | **4/5 (80%)** | 4/5 (80%) | Não (fragmentada) |
| `config_b_contextual` | `caracteres-700-sobreposicao-120` | 16 | 522.6 | **5/5 (100%)** | 5/5 (100%) | Sim |

## 2. Resultados por Pergunta

| Pergunta | Configuração | Acerto Top-k | Chunks Correspondentes | Top-k Recuperado (`chunk_id` · sim · pág · seção) |
|---|---|---|---|---|
| **P01** | `config_a_granular` | ACERTO | `ACV-01#c3` | `ACV-01#c3` (0.700, pág. 1, *2. Documentos exigidos para a matrícula*)<br>`ACV-02#c3` (0.645, pág. —, *1. Posso fazer a matrícula por meio de outra pessoa?; 2. A matrícula pode ser feita pela internet?*)<br>`ACV-01#c4` (0.588, pág. 1, *2. Documentos exigidos para a matrícula*) |
| **P01** | `config_b_contextual` | ACERTO | `ACV-01#c2` | `ACV-01#c2` (0.689, pág. 1, *1. Finalidade; 2. Documentos exigidos para a matrícula*)<br>`ACV-01#c1` (0.639, pág. 1, *Cabeçalho institucional; 1. Finalidade*)<br>`ACV-02#c1` (0.620, pág. —, *Cabeçalho institucional; 1. Posso fazer a matrícula por meio de outra pessoa?*) |
| **P02** | `config_a_granular` | ACERTO | `ACV-01#c5` | `ACV-01#c5` (0.718, pág. 2, *3. Documentos pendentes*)<br>`ACV-03#c5` (0.651, pág. —, *2. Como solicitar; 3. Prazo de emissão*)<br>`ACV-02#c4` (0.618, pág. —, *2. A matrícula pode ser feita pela internet?; 3. Como sei se a minha matrícula foi efetivada?*) |
| **P02** | `config_b_contextual` | ACERTO | `ACV-01#c3` | `ACV-01#c3` (0.713, pág. 2, *3. Documentos pendentes; 4. Efetivação da matrícula*)<br>`ACV-03#c2` (0.667, pág. —, *2. Como solicitar; 3. Prazo de emissão; 4. Condições para emissão*)<br>`ACV-01#c4` (0.573, pág. 2, *4. Efetivação da matrícula; 5. Cancelamento automático por faltas; 6. Atendimento*) |
| **P03** | `config_a_granular` | ACERTO | `ACV-03#c5` | `ACV-03#c5` (0.731, pág. —, *2. Como solicitar; 3. Prazo de emissão*)<br>`ACV-01#c5` (0.661, pág. 2, *3. Documentos pendentes*)<br>`ACV-05#c4` (0.659, pág. —, *2. Justificativa de faltas; 3. Prazo para trancamento*) |
| **P03** | `config_b_contextual` | ACERTO | `ACV-03#c2` | `ACV-03#c2` (0.693, pág. —, *2. Como solicitar; 3. Prazo de emissão; 4. Condições para emissão*)<br>`ACV-01#c3` (0.666, pág. 2, *3. Documentos pendentes; 4. Efetivação da matrícula*)<br>`ACV-05#c2` (0.551, pág. —, *2. Justificativa de faltas; 3. Prazo para trancamento; 4. Acompanhamento*) |
| **P04** | `config_a_granular` | ACERTO | `ACV-02#c3` | `ACV-02#c3` (0.576, pág. —, *1. Posso fazer a matrícula por meio de outra pessoa?; 2. A matrícula pode ser feita pela internet?*)<br>`ACV-02#c2` (0.524, pág. —, *1. Posso fazer a matrícula por meio de outra pessoa?*)<br>`ACV-02#c4` (0.497, pág. —, *2. A matrícula pode ser feita pela internet?; 3. Como sei se a minha matrícula foi efetivada?*) |
| **P04** | `config_b_contextual` | ACERTO | `ACV-02#c2` | `ACV-02#c2` (0.626, pág. —, *1. Posso fazer a matrícula por meio de outra pessoa?; 2. A matrícula pode ser feita pela internet?; 3. Como sei se a minha matrícula foi efetivada?*)<br>`ACV-01#c2` (0.467, pág. 1, *1. Finalidade; 2. Documentos exigidos para a matrícula*)<br>`ACV-01#c3` (0.461, pág. 2, *3. Documentos pendentes; 4. Efetivação da matrícula*) |
| **P05** | `config_a_granular` | FALHA | — | `ACV-04#c5` (0.793, pág. 1, *2. Como solicitar o trancamento; 3. Prazo para solicitar o trancamento*)<br>`ACV-05#c4` (0.787, pág. —, *2. Justificativa de faltas; 3. Prazo para trancamento*)<br>`ACV-04#c3` (0.675, pág. 1, *1. Finalidade*) |
| **P05** | `config_b_contextual` | ACERTO | `ACV-04#c3` | `ACV-05#c2` (0.786, pág. —, *2. Justificativa de faltas; 3. Prazo para trancamento; 4. Acompanhamento*)<br>`ACV-04#c2` (0.723, pág. 1, *2. Como solicitar o trancamento; 3. Prazo para solicitar o trancamento*)<br>`ACV-04#c3` (0.704, pág. 2, *4. Duração do trancamento; 5. Retorno ao curso; 6. Cancelamento a pedido*) |

## 3. Seleção e Justificativa

A configuração 'config_b_contextual' (caracteres-700-sobreposicao-120) foi selecionada para o índice oficial porque obteve acerto de recuperação de 5/5 (100%) (cobertura integral das referências: 5/5 (100%)) e preserva integralmente as seções normativas críticas em um único trecho — em especial a seção '2. Documentos exigidos para a matrícula' do ACV-01 (~470 caracteres), evitando a fragmentação da lista de documentos e da condição para menores de 18 anos observada na configuração granular de 320 caracteres.

## 4. Falhas e Ajustes Registrados

- Na configuração granular (320 caracteres, sobreposição 50), a seção 2 do ACV-01 foi dividida em dois chunks (ACV-01#c3 e ACV-01#c4), separando os primeiros itens da lista de matrícula da exigência de foto 3x4 e documento do responsável para menores de 18 anos.
- Ajuste aplicado no divisor (`src/ingestion.py`): nunca misturar páginas distintas de um PDF no mesmo chunk para garantir que o metadado `pagina` permaneça exato e conferível nas citações do RF19.
