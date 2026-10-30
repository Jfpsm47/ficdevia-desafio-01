# RF17 e RF18 — Embeddings, Índice Vetorial Persistente e Comparação de Chunking

Responsável: Estudante 2 · 29/10/2026 · Código: `src/ingestion.py`, `src/embeddings.py`, `src/metrics.py` ·
Testes: `testes/test_ingestion_embeddings.py` (`T06`, `T07`, `T14`) ·
Evidências: `indice/padrao/`, `resultados/metricas/rf17_reindexacao_t06.json`,
`resultados/metricas/rf18_comparacao_chunking.{json,md}`, `resultados/metricas/rf24_exclusao_documento.json`.

---

## 1. Arquitetura de Ingestão e Indexação Vetorial (RF17)

O acervo institucional fictício (`dados/acervo/catalogo.json`) reúne **6 documentos** em dois formatos
(`ACV-01.pdf`, `ACV-02.txt`, `ACV-03.txt`, `ACV-04.pdf`, `ACV-05.txt` e `ACV-06.pdf`).

### 1.1 Extração e Preservação de Metadados (`src/ingestion.py`)

- **Formatos suportados:** arquivos `.txt` (UTF-8) e `.pdf` com camada textual (`pypdf.PdfReader`).
- **Metadados preservados em cada `TrechoIndexado` (`src/schemas.py`):**
  - `chunk_id` no padrão `<documento_id>#c<n>` (ex.: `ACV-01#c2`);
  - `documento_id` e `versao_documento` validados contra `DocumentoAcervo`;
  - `hash_documento` (SHA-256 hexadecimal do arquivo original);
  - `pagina` (`>= 1` nos PDFs multipágina; `null` nos arquivos `.txt`) — o divisor **nunca mistura páginas distintas de um PDF** no mesmo chunk;
  - `secao` extraída automaticamente dos títulos numerados (`1. Finalidade`, `2. Documentos exigidos...`);
  - `configuracao_chunking` declarando unidade, tamanho e sobreposição (`caracteres-700-sobreposicao-120`).
- **Inclusão avulsa para interface (RF20):** `construir_documento_avulso` e `IndiceVetorial.incluir_arquivo_avulso` permitem indexar novos arquivos `.txt`/`.pdf` sem editar o catálogo congelado.

### 1.2 Embeddings e Persistência FAISS (`src/embeddings.py`)

| Item | Escolha Técnica | Justificativa |
|---|---|---|
| **Modelo de embedding** | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo multilíngue leve com bom desempenho semântico em português |
| **Execução** | Local em CPU via `fastembed` (`ONNX Runtime`, cache em `.cache/fastembed/`) | Custo de API zero, reprodutível offline após o download inicial |
| **Dimensão vetorial** | `384` (registrada e validada em `manifesto.json`) | Verificada na inicialização contra o índice persistido |
| **Índice persistente** | `faiss.IndexFlatIP` (`indice/padrao/index.faiss` + `trechos.json` + `manifesto.json`) | Busca exata sobre vetores `float32` normalizados em norma $L_2$ |
| **Métrica de similaridade** | `similaridade_cosseno` (produto interno sobre vetores com $\|v\|_2 = 1$) | Valores em $[-1, 1]$: quanto mais próximo de `1.0`, maior a proximidade semântica; **não é probabilidade de verdade** |
| **Versão do índice oficial** | `idx-008437e371` (`16` vetores, `6` documentos) | Hash determinístico sobre modelo, dimensão, chunking e hashes dos chunks ativos |

### 1.3 Reutilização após Reinício, Deduplicação e Mudança de Modelo (`T06`)

1. **Reutilização após reinício:** ao instanciar `embeddings.obter_indice()`, o sistema carrega `index.faiss`, `trechos.json` e `manifesto.json` diretamente do disco (`carregado_do_disco=True`), sem regerar embeddings.
2. **Prevenção de duplicatas na reindexação (`T06`):** `indexar_acervo()` compara `(documento_id, versao, hash_documento, configuracao_chunking)` com `manifesto.json`. Na execução real registrada em `resultados/metricas/rf17_reindexacao_t06.json`, os **6/6 documentos** foram identificados como `reutilizados_sem_duplicar` (`indexados_ou_atualizados = 0`), mantendo exatamente `16` vetores e `versao_indice = idx-008437e371`.
3. **Mudança de modelo/dimensão/chunking:** se `modelo_embedding`, `dimensao` ou `configuracao_chunking` divergirem do `manifesto.json`, o índice marca `desatualizado = True` e lança `ErroIndiceDesatualizado` em qualquer tentativa de busca até que uma reindexação completa (`--forcar`) seja executada.

---

## 2. Comparação Experimental de Chunking e Recuperação (RF18 — `T07`)

Ambas as configurações foram avaliadas com o **mesmo modelo de embedding** (`paraphrase-multilingual-MiniLM-L12-v2`, dimensão `384`), a **mesma unidade declarada** (`caracteres`), **`top_k = 3`** e as **mesmas 5 perguntas respondíveis** (`P01` a `P05` de `dados/gabaritos/d2/rag_perguntas.json`). Detalhes completos em `resultados/metricas/rf18_comparacao_chunking.md`.

### 2.1 Tabela Comparativa

| Configuração | Parâmetros (`unidade-tam-sobreposicao`) | Total de Chunks | Média (chars) | Acerto Top-3 (`P01..P05`) | Cobertura Integral de Refs | Lista integral de `P01` no Top-1 |
|---|---|---:|---:|---|---|---|
| `config_a_granular` | `caracteres-320-sobreposicao-50` | 37 | 225,9 | **4/5 (80%)** | 4/5 (80%) | Não (fragmentada em `#c3` e `#c4`) |
| **`config_b_contextual`** *(selecionada)* | **`caracteres-700-sobreposicao-120`** | **16** | **522,6** | **5/5 (100%)** | **5/5 (100%)** | **Sim (`ACV-01#c2`)** |

### 2.2 Análise de Falhas, Ajustes e Justificativa da Escolha

- **Falha observada na `config_a_granular` (`P05`):** para a pergunta *"Por quanto tempo o curso pode ficar trancado?"*, os 3 primeiros lugares foram ocupados por chunks curtos sobre prazo de solicitação de trancamento (`ACV-04#c5` com `0.793`, `ACV-05#c4` com `0.787` e `ACV-04#c3` com `0.675`), empurrando o chunk da seção `4. Duração do trancamento` para fora do `top-3`.
- **Fragmentação em `P01` na `config_a_granular`:** a seção `2. Documentos exigidos para a matrícula` (`~470` caracteres) foi partida em dois trechos (`ACV-01#c3` e `ACV-01#c4`), separando os primeiros itens da lista da exigência de foto 3x4 e documento do responsável para menores de 18 anos.
- **Justificativa da seleção (`caracteres-700-sobreposicao-120`):** alcançou **5/5 (100%)** de acerto de recuperação no `top-3`, preservou integralmente as listas normativas em um único chunk e reduziu o índice para 16 trechos coesos sem cruzar fronteiras de página nos PDFs.

---

## 3. Política de Retenção e Exclusão no Índice (RF24 — `T14`)

- **Política definida em `config.json -> retencao_privacidade`:**
  - `dados/originais/` permanece estritamente imutável (somente leitura);
  - Documentos do índice, seus vetores FAISS, metadados em `trechos.json`/`manifesto.json` e caches derivados (`*.derivado.json`) podem ser descartados sob comando explícito (`IndiceVetorial.excluir_documento`);
  - Logs de auditoria mantêm apenas metadados sanitizados e consultas com identificadores mascarados (`[CPF REMOVIDO]`, `[PROTOCOLO_MASCARADO]`, etc.).
- **Evidência real de exclusão (`T14` — `resultados/metricas/rf24_exclusao_documento.json`):**
  - Antes da exclusão de `ACV-03`, a consulta *"Qual é o prazo para emitir a declaração de matrícula?"* retornava `ACV-03#c2` em 1º lugar (`similaridade = 0.7232`) e havia 1 resultado derivado salvo (`T14-antes-exclusao__rag-db4b8b6e.derivado.json`).
  - Após `excluir_documento("ACV-03")` e recarga do índice do disco, **2 trechos vetoriais** e o arquivo `.derivado.json` correspondente foram removidos (`total_vetores: 16 -> 14`), `ACV-03` deixou de aparecer em qualquer posição da busca (`acv03_recuperado_depois = false`) e o evento `exclusao_documento_indice` ficou registrado em `resultados/logs/execucoes.jsonl`.

---

## 4. Como Recriar e Consultar o Índice Passo a Passo

```bash
# 1. Ativar ambiente virtual e habilitar UTF-8 no Windows
# PowerShell: $env:PYTHONUTF8="1"; .\.venv\Scripts\Activate.ps1

# 2. Construir (ou reutilizar sem duplicar) o índice persistente oficial em indice/padrao/
python -m src.embeddings indexar

# 3. Forçar reconstrução completa (necessário se mudar modelo ou chunking em config.json)
python -m src.embeddings indexar --forcar

# 4. Inspecionar manifesto, versão do índice e documentos indexados
python -m src.embeddings status

# 5. Executar busca vetorial top-k avulsa com similaridade de cosseno
python -m src.embeddings buscar --consulta "Quais documentos são exigidos para a matrícula?" --top-k 4

# 6. Reexecutar o experimento comparativo de chunking (RF18 / T07)
python -m src.metrics chunking --limpar-temp
```
