# Central Inteligente de Atendimento e Comunicação Institucional

Desafios Práticos 01 e 02 — FIC_DEV · Inteligência Artificial Generativa (Aulas 01 a 14).

Protótipo local que recebe solicitações **fictícias** em texto, áudio e imagem, valida a solicitação em três camadas, consulta um acervo normativo indexado localmente com RAG fundamentado, gera minuta de resposta institucional com citações verificáveis, versão em áudio e peça visual sintética. **Nenhuma resposta é enviada automaticamente**: toda saída nasce retida e depende de decisão formal de um servidor responsável.

| Integrante | Responsabilidade | Situação |
|---|---|---|
| Estudante 1 | Prompts, avaliação, esquemas (`src/schemas.py`), NLP (`src/nlp.py`), dados fictícios e gabaritos | Desafio 01 e Desafio 02 (RF14, RF15) implementados |
| Estudante 2 | Ingestão (`src/ingestion.py`), embeddings e índice FAISS (`src/embeddings.py`), chunking/métricas (`src/metrics.py`), RAG (`src/rag.py`), abstração de provedor (`src/llm_client.py`), auditoria/retenção (`src/audit.py`) e fluxo integrado (`src/main.py`, `src/web.py`) | Desafio 01 e Desafio 02 (RF17, RF18, RF19, RF21, RF23-RAG, RF24-exclusão/revisão) implementados |
| Estudante 3 | Áudio (`src/audio.py`), visão/OCR (`src/vision.py`), imagem (`src/image_generation.py`); Desafio 02: guardrails, Streamlit, sentimentos e painel | Desafio 01 concluído (RF06, RF07, RF08, RF10); Desafio 02 pendente de consolidação pelo Estudante 3 |

## Instalação

Base do projeto: Python 3.13 (testado em Python 3.13.5 / 3.13.14 no Windows 11 e 3.14.7 no macOS).

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

Versões principais (`requirements.txt`): `httpx 0.28.1`, `python-dotenv 1.2.1`, `pydantic 2.14.1`, `pypdf 6.21.4`, `faiss-cpu 1.15.1`, `fastembed 0.9.1`, `Pillow 13.0.0` e `piper-tts 1.8.0`. O modelo de embeddings multilíngue (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `384d`) roda localmente em ONNX com cache em `.cache/fastembed/`.

## Execução — Fluxo Geral e Multimodal (Desafio 01 + Integração)

| Comando | O que faz |
|---|---|
| `python -m unittest discover -s testes -t .` | Suíte completa de testes offline (150 testes) — não chama API externa |
| `python -m src.audio transcrever` | Transcreve o áudio fictício no Groq; salva evidências e comparação, sem aprovar a transcrição |
| `python -m src.audio revisar --help` | Instruções para confirmar os campos críticos após ouvir o áudio e revisar o texto |
| `python -m src.audio sintetizar --caso caso02_audio` | Gera localmente um WAV Piper da última minuta comprovadamente aprovada; bloqueia minutas pendentes, corrigidas ou rejeitadas |
| `python -m src.audio revisar-voz --help` | Registra a escuta humana e a decisão sobre o WAV gerado |
| `python -m src.vision extrair` | Renderiza o PDF, mascara a assinatura e extrai texto com visão/OCR no Groq, sem aprovar o resultado |
| `python -m src.vision revisar --help` | Instruções para conferir a ficha original e confirmar o OCR revisado |
| `python -m src.image_generation importar resultados/imagens/<png>.png` | Importa o PNG gerado localmente pelo Draw Things, monta a peça 16:9 e preserva a evidência para revisão humana |
| `python -m src.image_generation revisar --help` | Instruções para registrar a revisão obrigatória da peça visual do RF10 |
| `python -m src.main` | Inicia o fluxo completo e abre a **Interface Web de Revisão Humana** (`http://127.0.0.1:8000`) |
| `python -m src.main --dry-run --nao-interativo` | Executa todo o fluxo em lote sem chamar a API e gera os PDFs das minutas |
| `python -m src.main --caso caso01_texto --nao-interativo` | Executa o fluxo integrado real (compreensão RF14/RF15 → RAG RF19 → minuta PDF pendente de revisão) |
| `python -m src.main --caso caso01_texto --registrar-decisao aprovada --revisor "<Nome>" --justificativa "<Motivo>"` | Registra decisão formal de revisão humana (`pendente`, `aprovada`, `rejeitada`, `revisar`) sem envio automático (RF24) |
| `python -m src.experimento_prompts listar --provedor groq` | Lista os modelos disponíveis para a sua chave |
| `python -m src.experimento_prompts prompts [--reusar-prompt-c]` | **RF02**: experimento comparativo de prompts A, B e C |
| `python -m src.experimento_prompts modelos` | Compara modelos com os prompts de produção nos casos 01, 04 e 05 |

Passos e limitações multimodais: [RF06 — Áudio](documentacao/RF06_AUDIO.md), [RF07 — Síntese de voz](documentacao/RF07_VOZ.md), [RF08 — Visão e OCR](documentacao/RF08_VISAO_OCR.md) e [RF10 — Imagem](documentacao/RF10_IMAGEM.md).

## Desafio 02 — Esquemas, NLP, Índice Vetorial, RAG e Governança (Estudantes 1 e 2)

Evolução da central (Aulas 08 a 14): contratos Pydantic estritos em três camadas (RF14), ficha de compreensão com resumo e entidades (RF15), índice vetorial persistente em FAISS com embeddings locais (RF17), experimento comparativo de chunking (RF18), motor RAG com citações determinísticas, abstenção explícita e detecção de conflito entre fontes vigentes (RF19), abstração de provedor isolada do índice com controle de orçamento e adaptador simulado explícito (RF21), métricas determinísticas (RF23) e exclusão auditada do índice/derivados + estados de revisão humana sem envio automático (RF24).

| Comando | O que faz |
|---|---|
| `python -m src.schemas exportar` | Regrava os JSON Schema dos contratos em `prompts/esquemas/` |
| `python -m src.dados_ficticios verificar` | Confere quantidades, contratos, trechos de referência e hashes SHA-256 dos 28 arquivos congelados (sem API) |
| `python -m src.dados_ficticios gerar-pdfs` | Recria os PDFs textuais do acervo a partir de `dados/acervo_fontes/` |
| `python -m src.nlp extrair --todos [--dry-run]` | RF14: extração com esquema estrito e validação em 3 camadas → `resultados/extracao/<execução>/` |
| `python -m src.nlp comparar-json` | RF14: JSON só sintático × validado por esquema (sem API) → `resultados/metricas/rf14_comparacao_json.md` |
| `python -m src.nlp fichas --todos [--reusar-extracao ...]` | RF15: resumo, categoria e entidades conferidos com o gabarito → `resultados/fichas/<execução>/` |
| `python -m src.embeddings indexar [--forcar-reindexacao]` | RF17: extrai `.txt`/`.pdf` do acervo, gera embeddings `384d` e persiste/atualiza `indice/padrao/` |
| `python -m src.embeddings info` | RF17: exibe versão do índice, modelo, dimensão, chunking e documentos indexados |
| `python -m src.embeddings buscar --consulta "<texto>" --top-k 4` | RF17: busca semântica `top-k` com similaridade de cosseno e explicação da métrica |
| `python -m src.embeddings excluir --documento ACV-03 --motivo "<motivo>"` | RF24: remove documento, vetores e `.derivado.json` associados com registro de auditoria |
| `python -m src.metrics chunking` | RF18 (`T07`): compara `320/50` × `700/120` sobre `P01..P05` → `resultados/metricas/rf18_comparacao_chunking.{json,md}` |
| `python -m src.rag consultar --pergunta "<texto>" [--dry-run]` | RF19: consulta avulsa com citações reconstruídas do índice e checagem de segurança |
| `python -m src.rag avaliar [--pausa 25] [--dry-run]` | RF19/RF23 (`T08..T10`, `ADV-02`): avalia `P01..P08` + `ADV-02` → `resultados/rag/<execução>/matriz_rf19.md` |
| `python -m src.rag demonstrar-provedores [--dry-run]` | RF21 (`T12`): demonstra troca de modelo + adaptador simulado + falha 503 sem reconstruir o índice |
| `python -m src.rag demonstrar-exclusao` | RF24 (`T14`): demonstra exclusão de `ACV-03` e derivados em cópia isolada do índice |

### Documentação do Desafio 02

| Documento | Conteúdo |
|---|---|
| `documentacao/CONTRATOS_DADOS.md` | Contratos versionados da equipe (`v0.1.0`), três camadas de validação e decisões fechadas |
| `documentacao/DADOS_E_GABARITOS_D2.md` | Acervo (`ACV-01..06`), solicitações, perguntas RAG (`P01..P08`), avaliações, ataques e congelamento |
| `documentacao/RF14_EXTRACAO.md` · `documentacao/RF15_FICHAS.md` | Extração estruturada, fichas de compreensão, métricas e limitações (Estudante 1) |
| `documentacao/RF17_RF18_INDICE_CHUNKING.md` | Ingestão TXT/PDF, embeddings locais, índice FAISS persistente (`T06`) e comparação de chunking (`T07`) |
| `documentacao/RF19_RF21_RAG_PROVEDOR.md` | Motor RAG fundamentado (`T08..T10`, `ADV-02`), provedor configurável (`T12`), exclusão (`T14`) e roteiro de 5 min |
| `documentacao/INTEGRACAO_RF14.md` | Integração de `nlp.compreender` e `rag.gerar_minuta_solicitacao` em `src/main.py` |
| `documentacao/MATRIZ_TESTES_D2.md` | Matriz `T01` a `T15` e métricas consolidadas do RF23 (numerador/denominador) |
| `documentacao/AVALIACAO_HUMANA.md` | Validação dos gabaritos, fichas e decisões humanas de revisão |

## Estrutura

```
dados/originais/     entradas fictícias somente leitura (texto, áudio, PDF-imagem e casos 04 a 09)
dados/acervo/        normas e comunicados fictícios indexáveis (ACV-01 a ACV-06 em TXT e PDF + catalogo.json)
dados/gabaritos/     gabaritos do Desafio 01 e subpasta d2/ congelada por SHA-256 (HASHES.json)
dados/processados/   extrações estruturadas, fichas de compreensão e textos intermediários revisados
indice/padrao/       índice vetorial FAISS persistente (index.faiss + manifesto.json + trechos.json)
prompts/             prompts versionados (produção e experimento) e JSON Schemas exportados (prompts/esquemas/)
src/schemas.py       contratos de dados Pydantic estritos e versionados
src/nlp.py           extração estruturada, validação em 3 camadas, resumo e ficha de compreensão (RF14, RF15)
src/ingestion.py     leitura TXT/PDF, extração por página/seção e divisão configurável em TrechoIndexado (RF17, RF18)
src/embeddings.py    embeddings locais FastEmbed, índice FAISS persistente, busca cosseno e exclusão (RF17, RF24)
src/rag.py           geração RAG com citações do índice, abstenção, conflito e defesa contra injection (RF16, RF19)
src/metrics.py       comparação de chunking, verificação contra fontes e agregações seguras (RF18, RF23)
src/llm_client.py    cliente HTTP OpenAI-compat, AdaptadorGeracao, AdaptadorSimulado e ControladorOrcamento (RF21)
src/audit.py         auditoria JSONL, mascaramento de PII/protocolo na consulta e eventos de revisão/exclusão (RF21, RF24)
src/main.py          orquestração ponta a ponta (compreensão → RAG → minuta PDF → revisão humana)
src/web.py           interface Web de revisão humana lado a lado
src/audio.py         transcrição Groq e síntese local Piper (RF06, RF07)
src/vision.py        renderização de PDF, mascaramento de assinatura e OCR Groq (RF08)
src/image_generation.py  importação e montagem de peça visual local via Draw Things (RF10)
resultados/          minutas PDF/JSON, avaliações RAG (resultados/rag/), métricas (resultados/metricas/) e logs
documentacao/        relatório técnico, matrizes de teste, avaliações humanas e registro de uso de IA
testes/              suíte automatizada offline (150 testes em 13 módulos)
```

## Limitações

Ver `documentacao/relatorio_tecnico.md` (seções 9, 10.6 e 11.5). Principais: similaridade vetorial não é garantia de verdade; extração de acervo em PDF depende de camada de texto embarcada; verificações automáticas são estruturais/heurísticas; adaptador simulado serve apenas para testes/contingência e não equivale a modelo real; toda minuta exige revisão humana obrigatória antes de uso externo.

## Uso de IA no desenvolvimento

Ver `documentacao/registro_uso_ia.md`.
