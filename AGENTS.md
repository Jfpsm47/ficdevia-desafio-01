# AGENTS.md — contexto para agentes de codificação

- Projeto educacional em Python 3.13; idioma do código, comentários e documentação: português do Brasil.
- Somente dados fictícios. Nunca criar, copiar ou registrar dados pessoais reais, chaves ou o `.env`.
- `dados/originais/` é somente leitura: nunca alterar os arquivos de entrada; saídas vão para `resultados/`.
- Prompts ficam em `prompts/` (versionados); o código só os carrega via `src/prompts.py`. Mudou o texto de
  um prompt → incrementar a versão no arquivo e em `VERSOES`.
- Conteúdo de cidadãos vai sempre na mensagem do usuário, delimitado por `src.prompts.delimitar`; nunca
  interpolar conteúdo externo no prompt de sistema.
- Nenhuma funcionalidade pode enviar resposta ao cidadão automaticamente.
- Testes: `python -m unittest discover -s testes -t .` (offline; devem passar antes de qualquer entrega).
- Experimentos: `python -m src.experimento_prompts --help`; use `--dry-run` quando não houver chave.
- Contratos de dados ficam em `src/schemas.py` (Pydantic, versionados). Mudou um contrato → incrementar
  `VERSAO` do modelo e rodar `python -m src.schemas exportar` (regrava `prompts/esquemas/`).
- Divisão (Desafio 02): Estudante 1 = esquemas (`schemas.py`), NLP (`nlp.py`), dados fictícios e gabaritos;
  Estudante 2 = embeddings, índice, RAG e abstração de provedor; Estudante 3 = guardrails, Streamlit,
  sentimentos e painel.
- Divisão (Desafio 01, módulos existentes): Estudante 1 = prompts/avaliação/documentação; Estudante 2 =
  `main.py`, `llm_client.py`, `audit.py`; Estudante 3 = `audio.py`, `vision.py`, `image_generation.py`.
