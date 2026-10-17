# Central Inteligente de Atendimento e Comunicação Institucional

Desafio Prático 1 — FIC_DEV · Inteligência Artificial Generativa (Aulas 01 a 07).

Protótipo local que recebe solicitações **fictícias** em texto, áudio e imagem, extrai informações, gera
minuta de resposta institucional, versão em áudio e peça visual sintética. **Nenhuma resposta é enviada
automaticamente**: toda saída é minuta pendente de revisão de um servidor responsável.

| Integrante | Responsabilidade | Situação |
|---|---|---|
| Estudante 1 | Engenharia de prompts, comparação de modelos, critérios de avaliação e documentação | Implementado (aguarda avaliação humana) |
| Estudante 2 | Integração por API, segurança, processamento de texto e registro das execuções (`src/main.py`, `src/llm_client.py`, `src/audit.py`) | A FAZER |
| Estudante 3 | Áudio, visão/OCR, geração de imagem, acessibilidade, testes multimodais (`src/audio.py`, `src/vision.py`, `src/image_generation.py`) | A FAZER |

## Instalação

Requer Python 3.13 (testado com 3.13.5).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

Abra `.env` e preencha **somente** a chave do provedor que for usar (padrão: `GROQ_API_KEY`, obtida em
console.groq.com/keys). O `.env` está no `.gitignore` e nunca deve ser entregue.

Versões principais: `httpx 0.28.1`, `python-dotenv 1.2.2` (ver `requirements.txt`).

## Execução

| Comando | O que faz |
|---|---|
| `python -m unittest discover -s testes -t .` | 14 testes offline (prompts, minimização, avaliação) — não chama API |
| `python -m src.experimento_prompts listar --provedor groq` | Lista os modelos disponíveis para a sua chave |
| `python -m src.experimento_prompts prompts` | **RF02**: gera o Prompt C via metaprompt e executa A, B e C com o mesmo modelo e parâmetros |
| `python -m src.experimento_prompts prompts --reusar-prompt-c` | Repete o RF02 com o Prompt C já salvo |
| `python -m src.experimento_prompts modelos` | Compara modelos com os prompts de produção nos casos 01, 04 e 05 |
| `python -m src.experimento_prompts reavaliar resultados/<tipo>/<execução>` | Recalcula as matrizes após mudar um gabarito (sem API) |
| `python -m src.main` | Fluxo completo — **A FAZER (Estudante 2)** |

Qualquer comando de experimento aceita `--dry-run` (monta e salva os prompts sem chamar a API) e
`--provedor` / `--modelo(s)` para sobrescrever o `config.json`.

## Configuração

`config.json` guarda caminhos, provedores (URL base compatível com OpenAI + nome da variável da chave),
modelos, parâmetros de geração, timeout, tentativas e preços por token (com data da consulta).
Provedores prontos: `groq`, `gemini`, `openai`, `openrouter`, `ollama` (local, sem chave).

## Estrutura

```
dados/originais/     entradas fictícias (arquivos fornecidos, inalterados, + casos 04 e 05 criados pela equipe)
dados/gabaritos/     resultado esperado de cada caso, escrito antes da execução
prompts/             todos os prompts versionados (ver prompts/README.md)
src/prompts.py       montagem segura das mensagens, minimização, modelo da minuta
src/avaliacao.py     critérios automáticos de avaliação
src/experimento_prompts.py   RF02 + comparação de modelos
src/cliente_experimento.py   cliente HTTP mínimo dos experimentos (timeout, 401/429/5xx, resposta vazia)
resultados/          saídas, matrizes e registros (execucoes.jsonl) de cada execução
documentacao/        protocolo de avaliação, comparação de modelos, relatório técnico, uso de IA,
                     AVALIACAO_HUMANA.md (decisões humanas)
testes/              testes automatizados
```

## Casos de teste

| Caso | Entrada | Finalidade |
|---|---|---|
| caso01_texto | `entrada_texto.txt` | classificação, extração, minuta (pede lista de documentos que não existe nos dados) |
| caso02_audio | `entrada_audio.mp3` | transcrição e resposta acessível |
| caso03_ocr | `entrada_pdf-imagem.pdf` | OCR/visão de ficha manuscrita (PDF sem camada de texto) |
| caso04_texto_injection | criado pela equipe | prompt injection |
| caso05_texto_incompleto | criado pela equipe | campos ausentes → "não localizado" |
| imagem institucional | `brasao.png` | brasão usado no cabeçalho da minuta (padrão GOV-MT) |

## Decisões, modelos e custos

- Provedor de texto: Groq (cota gratuita, API compatível com OpenAI, modelos de pesos abertos).
- Modelo do experimento RF02: `openai/gpt-oss-120b`. Comparação: `gpt-oss-120b`, `gpt-oss-20b`,
  `qwen/qwen3.8-27b` (`llama-3.3-70b-versatile` não estava disponível para a chave). Ver
  `documentacao/comparacao_modelos.md`.
- Preços (16/10/2026, console.groq.com/docs/models), em US$ por milhão de tokens (entrada/saída):
  gpt-oss-120b 0,15 / 0,60; gpt-oss-20b 0,075 / 0,30; qwen3.8-27b 0,80 / 4,00.
- Custo real em 16/10/2026: RF02 ≈ US$ 0,003 e comparação de modelos ≈ US$ 0,032 (detalhe por chamada em
  `resultados/*/<execução>/execucoes.jsonl`).
- Cota gratuita sujeita a HTTP 429: o cliente faz até 5 tentativas com espera, e há pausa de 3 s entre as chamadas.

## Limitações

Ver `documentacao/relatorio_tecnico.md`, seção 9. Principais: verificações automáticas heurísticas,
minimização por regex, defesa contra injection não é absoluta, gabaritos dependem de validação humana.

## Uso de IA no desenvolvimento

Ver `documentacao/registro_uso_ia.md`.
