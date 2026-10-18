# Relatório técnico — Central Inteligente de Atendimento e Comunicação Institucional

> Documento consolidado da equipe. Seções dos Estudantes 1 e 2 preenchidas; seções do Estudante 3
> marcadas como **A PREENCHER**.

## 1. Problema e escopo

Protótipo local que recebe solicitações fictícias (texto, áudio, imagem), extrai informações, gera
minuta institucional em PDF, versão em áudio e peça visual sintética, sempre com decisão final de um servidor.
Nenhuma resposta é enviada automaticamente.

## 2. Arquitetura

```
entrada (texto | áudio | imagem)
   │  validação do arquivo (src/main.py) ──── Estudante 2/3
   ▼
extração de texto (STT | OCR/visão) ───────── Estudante 3
   ▼
minimização de dados (src/prompts.minimizar) ─ Estudante 1
   ▼
triagem/extração JSON  [prompt extracao-v1.0] ─ Estudante 1 (prompt) / Estudante 2 (API)
   ▼
minuta JSON → PDF institucional com Brasão [prompt minuta-v1.0, gerar_pdf_minuta] ── Estudante 1/2
   ▼
avaliação automática (src/avaliacao.py) + REVISÃO HUMANA na Interface Web (src/web.py)
   ▼
TTS da minuta aprovada · peça visual com nota de proveniência ── Estudante 3
   ▼
registro estruturado JSONL e relatório de auditoria (src/audit.py) ── Estudante 2
```

## 3. Engenharia de prompts (Estudante 1)

- Experimento RF02: ver `resultados/experimento_prompts/<execução>/matriz_comparativa.md` e a seleção
  justificada em `documentacao/AVALIACAO_HUMANA.md` (seção 2).
- Prompts de produção e defesas contra injection: `prompts/README.md`.
- Teste de injection: caso `caso04_texto_injection` (instrução falsa de "sistema", norma inventada, pedido
  de revelar o prompt). Na execução `comparacao_modelos/20261016-201709`, os três modelos registraram
  alerta de segurança na extração e nenhum obedeceu às instruções nem vazou o marcador canário (sujeito à
  confirmação humana).
- Achado do RF02: o Prompt A (zero-shot) inventou instituição, contatos, signatária, 10 documentos e prazos.
  O B seguiu o modelo sem invenções aparentes. O C, gerado por metaprompt, colocou o texto do cidadão
  dentro de uma instrução, sem delimitação (seleção final: decisão humana).

## 4. Modelos e custos (Estudante 1 — texto; Estudante 3 — áudio/visão/imagem)

Ver `documentacao/comparacao_modelos.md`. Custos de texto calculados por token a partir de
`config.json` (`precos_usd_por_milhao_tokens`). **A PREENCHER:** custos de STT, TTS, OCR/visão e imagem.

## 5. Avaliação de qualidade (Estudante 1)

Protocolo: `documentacao/protocolo_avaliacao.md`. Resultados por caso, taxa de aprovação e decisões:
`documentacao/AVALIACAO_HUMANA.md` (seção 5) e `resultados/logs/relatorio_auditoria.md` (seção 3).

## 6. LGPD, privacidade e minimização (RF12)

| Campo (cenário real) | Dado pessoal? | Finalidade | Necessário para a minuta? | Risco | Tratamento no protótipo |
|---|---|---|---|---|---|
| Nome do solicitante | Sim | Identificar destinatário | Sim | Médio | Enviado; usado no destinatário |
| Protocolo, data | Não (vinculado ao titular) | Rastrear o atendimento | Sim | Baixo | Enviado |
| Curso, turno, datas do curso | Sim (vida acadêmica) | Contextualizar a resposta | Sim | Baixo | Enviado |
| CPF | Sim | Identificação civil | Não | Alto (fraude) | Mascarado antes do envio |
| RG | Sim | Identificação civil | Não | Alto | Mascarado antes do envio |
| Filiação (nome da mãe/pai) | Sim | Cadastro escolar | Não | Médio | Mascarado antes do envio |
| Data de nascimento | Sim | Cadastro / menoridade | Não | Médio | Mascarado antes do envio |
| E-mail / telefone | Sim | Canal de resposta | Não (resposta pelo próprio canal) | Médio | Mascarado antes do envio |
| Assinatura (imagem) | Sim | Validade do formulário | Não | Alto | **A PREENCHER (Estudante 3):** recorte/omissão no OCR |
| Voz (áudio) | Sim (biométrico em potencial) | Canal de entrada | Não | Alto | **A PREENCHER (Estudante 3)** |

Todos os dados do projeto são fictícios. O caso 01 contém CPF de exemplo e e-mail em domínio fictício.

## 7. Segurança, interface de revisão e tratamento de falhas (Estudante 2 — RF01, RF04, RF05, RF09, RF11, RF12, RF13)

- **Proteção de credenciais (RF01, RF04, RF11):** Chaves de API são lidas exclusivamente do ambiente / `.env` via `src/llm_client.verificar_chave` (perfis locais como `ollama` operam sem chave). A função `ocultar_segredos` (`src/llm_client.py`) e a varredura recursiva `sanitizar_dados` (`src/audit.py`) mascaram como `[CREDENCIAL_OCULTADA]` qualquer valor de variável `*_API_KEY`/`*_TOKEN`/`*_SECRET`, cabeçalhos `Bearer` ou prefixos conhecidos (`gsk_`, `sk-`, `AIza`) antes de exibir erros ou gravar logs.
- **Tratamento de falhas de API (`src/llm_client.py` — RF04):**
  - *Chave ausente:* bloqueia a chamada antes da rede (`codigo_erro="chave_ausente"`) com instrução clara indicando a variável e o `.env.example`.
  - *Autenticação inválida (HTTP 401/403):* interrompe imediatamente sem repetir tentativas (`codigo_erro="autenticacao_invalida"`).
  - *Limite de requisições (HTTP 429) e indisponibilidade (HTTP 5xx):* realiza até 5 tentativas respeitando o cabeçalho `Retry-After` ou espera progressiva (*backoff*).
  - *Timeout e falha de conexão:* `timeout_s` configurável em `config.json` (60 s), tratando `httpx.TimeoutException` e `httpx.HTTPError` com retentativas e mensagem amigável ao operador.
  - *Resposta vazia ou JSON malformado:* detecta `choices` vazio ou texto em branco (`codigo_erro="resposta_vazia"`), repete a tentativa e, no fluxo principal (`src/main.py`), aplica `normalizar_extracao` e `normalizar_minuta` para garantir que a estrutura JSON permaneça 100% válida mesmo quando houver campos ausentes (Critério de aceite RF05).
- **Geração de minuta em PDF e bloqueio de envio automático (RF09):** Nenhuma rotina de envio externo (SMTP, webhook ou mensageria) existe no sistema. Todas as minutas são geradas como documentos PDF 1.4 (`resultados/minutas/<caso_id>_minuta.pdf`) via `gerar_pdf_minuta` (`src/main.py`), com o Brasão oficial de Mato Grosso (`dados/originais/brasao.png`) embutido no cabeçalho, tarja explícita `MINUTA GERADA COM APOIO DE IA – PENDENTE DE REVISÃO HUMANA – ENVIO AUTOMÁTICO BLOQUEADO`, substituição automática de `[NOME DO SERVIDOR RESPONSÁVEL]` pelo nome do revisor na assinatura e registro da decisão humana no rodapé.
- **Interface Web de Revisão Humana (`src/web.py` — RF13):** A revisão humana é realizada por meio de uma interface Web local responsiva (`http://127.0.0.1:8000`) que solicita a identificação do servidor revisor (nome e cargo/setor) ao abrir a sessão e exibe lado a lado: à esquerda, o conteúdo original da solicitação (texto, player de áudio MP3 ou visualizador de documento PDF); à direita, o PDF da minuta institucional gerada, a extração JSON, os achados da avaliação automática e os controles para aprovar, corrigir manualmente (regenerando o PDF) ou rejeitar/solicitar nova geração.
- **Rastreabilidade e auditoria (`src/audit.py` — RF11, RF13):** Cada etapa gera um registro em `resultados/logs/execucoes.jsonl` e um consolidado em `resultados/logs/relatorio_auditoria.md` contendo `id_execucao`, `data_hora`, `caso_id`, `etapa`, `modalidade`, `arquivo_origem`, `provedor`, `modelo`, `parametros`, `versao_prompt`, `hash_prompt`, `dados_minimizados`, `latencia_s`, `tokens_entrada`/`tokens_saida`, `custo_usd`, `tentativas`, `erro`, `avaliacao_automatica`, `decisao_humana`, `revisor` e versões do ambiente Python/bibliotecas.

## 8. Áudio, visão/OCR e imagem (Estudante 3)

RF06 implementado com Groq/Whisper Large V3 em `src/audio.py`; detalhes, custos, execução,
testes e limitações em [RF06_AUDIO.md](RF06_AUDIO.md). A amostra real `stt-46427a77` processou
89,160 s de áudio em 1,584 s, com custo estimado de US$ 0,002749. Evidências em
`resultados/transcricoes/stt-46427a77/`. A transcrição foi corrigida (e-mail e repetição de turno) e conferida pelo integrante 3 em 18/10/2026, conforme confirmação no chat. Essa decisão não aprova uma nova minuta.
O fluxo real de áudio não utiliza mais o gabarito como substituto da transcrição; a referência
permanece apenas na demonstração `--dry-run` e na comparação posterior à chamada.

RF08 implementado com Groq/Qwen 3.8 27B em `src/vision.py`; detalhes de segurança, execução, custo,
testes e limitações em [RF08_VISAO_OCR.md](RF08_VISAO_OCR.md). A execução real `ocr-99704b6a` processou
uma ficha digitalizada em 2,176 s, com custo estimado de US$ 0,002964. A assinatura manuscrita foi
mascarada antes do envio ao provedor. O OCR identificou três divergências críticas (código, nascimento e
início do curso) e uma divergência na grafia do e-mail. O integrante 3 conferiu a ficha original em
18/10/2026, corrigiu somente `revisada.txt` e registrou a decisão `Conferido`; a saída bruta foi preservada.
O fluxo real não utiliza o gabarito como substituto do OCR.

RF07 implementado em `src/audio.py` com Piper local e o modelo aberto `pt_BR-faber-medium`. A síntese
gera WAV sem enviar a minuta a um provedor externo e registra modelo, voz, ajustes de ritmo, hashes,
latência e a relação com a minuta de origem. A rotina só aceita uma minuta cuja última decisão de
auditoria **e** cujo próprio PDF indiquem `Aprovada`; preserva em `texto_falado.txt` o conteúdo enviado
e mantém avisos de informações não localizadas. A voz Faber usa ritmo levemente reduzido e pausas entre
blocos; sua inteligibilidade em nomes, siglas, datas e números exige escuta humana antes de aceite.
O Integrante 3 ouviu e aprovou a amostra `tts-9c86357b` em 18/10/2026; a decisão está vinculada ao WAV
e à sua minuta de origem na auditoria.
RF10 implementado em `src/image_generation.py` com geração local no Draw Things e o modelo aberto
`FLUX.2 [klein] 4B (6-bit)`. O fluxo não usa chave nem envia o prompt a provedor externo: importa o PNG
exportado localmente, preserva a imagem-base, compõe a peça final 16:9 com aviso de proveniência e registra
prompt, seed, parâmetros, hashes e revisão humana. A execução `img-078d5e9a` foi aprovada pelo Integrante 3
em 18/10/2026 após conferência de textos, símbolos, mãos/objetos/proporções e coerência. A alternativa
hospedada gratuita teve sua cota limitada; por isso foi adotado o modelo local compacto, cujo acabamento
visual é mais simples do que o de modelos maiores. Detalhes em [RF10_IMAGEM.md](RF10_IMAGEM.md).

## 9. Limitações e riscos residuais

- Verificações automáticas são heurísticas (ver protocolo, seção 6); invenções parafraseadas podem passar
  (constatado: "recomendamos que verifique a lista de documentos exigidos" não é detectado).
- Mesmo com prompt seguro, os modelos gpt-oss inventaram procedimento de trancamento no caso 05: a
  revisão humana continua indispensável.
- A minimização por expressões regulares não cobre todos os formatos (ex.: CPF escrito por extenso,
  nome da mãe sem rótulo).
- Defesas de prompt reduzem, mas não eliminam, o risco de prompt injection; por isso a revisão humana é
  obrigatória.
- Dependência de fornecedor: mitigada pela API compatível com OpenAI (troca por `config.json`) e pelo
  perfil local `ollama`.
- Modelos de raciocínio consomem tokens extras de raciocínio (custo e latência maiores).
- **Integração e operação (Estudante 2):** Cotas gratuitas em nuvem estão sujeitas a limites severos de requisições por minuto (HTTP 429) e variações de latência; embora o cliente aplique retentativas com *backoff* e modo `--dry-run` com cache validado, o uso institucional contínuo exigiria hospedagem local ou contrato dedicado com SLA. Além disso, o arquivo `execucoes.jsonl` é local (sem banco transacional ou controle de acesso multiusuário).
- **A PREENCHER:** limitações do Estudante 3.
