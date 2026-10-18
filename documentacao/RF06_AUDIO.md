# RF06 — Transcrição de áudio

Implementação do Estudante 3, 18/10/2026. Código e teste real concluídos;
amostra **CORRIGIDA E CONFERIDA** pelo integrante 3 em 18/10/2026, conforme confirmação no chat. Nenhum commit feito pelo assistente.

## Decisão técnica

- Provedor: Groq; modelo configurável `whisper-large-v3`; idioma solicitado `pt`.
- HTTP multipart com `httpx`, já utilizado pelo projeto; sem SDK adicional.
- Resposta `verbose_json` para preservar idioma, duração e segmentos.
- Limite local conservador de 25.000.000 bytes; extensões aceitas estão em `src/audio.py`.
- Temperatura zero; timeout de 90 s; até três tentativas para 429, 5xx, rede, timeout e resposta inválida.
  Erros 400/401/403/413 não são repetidos. Esperas limitadas a 30 s; `Retry-After` numérico é considerado.
- Configuração e preço estimado estão em `config.json`, seção `transcricao`.
- Fonte consultada: https://console.groq.com/docs/speech-to-text (18/10/2026).
- Credencial lida do `.env` da raiz do projeto: `GROQ_API_KEY`. Não é gravada nos artefatos.

## Como executar e conferir

Execute na raiz do repositório com o ambiente virtual ativado.

```bash
python -m src.audio transcrever
```

O comando usa `dados/originais/entrada_audio.mp3` e cria uma pasta exclusiva
`resultados/transcricoes/stt-<id>/` contendo:

| Arquivo | Finalidade |
|---|---|
| `bruta.txt` | Texto retornado pelo modelo, preservado sem correções |
| `revisada.txt` | Cópia editável para a revisão; inicialmente igual à bruta, ainda não validada |
| `comparacao.json` | WER, diferenças normalizadas/literais e conferência textual de campos críticos |
| `metadados.json` | Origem, hashes, modelo, idioma, duração, parâmetros, segmentos, latência, custo e decisão |

Para outra entrada fictícia: `python -m src.audio transcrever --arquivo CAMINHO --caso IDENTIFICADOR`.
A comparação só é gerada quando há gabarito e referência correspondentes ao arquivo de origem.
Não fornecer dados esperados ao modelo: o gabarito é lido apenas depois da chamada.

1. Ouvir o áudio original e confrontar com `bruta.txt` e a referência humana.
2. Editar somente `revisada.txt`, preservando o sentido e documentando incertezas.
3. Conferir obrigatoriamente nomes, número de protocolo e datas. Conferir também e-mail e demais divergências.
4. Registrar a revisão com identificador fictício e justificativa específica:

```bash
python -m src.audio revisar resultados/transcricoes/stt-<id> --revisor "Revisor 3" --justificativa "Descrever o que foi ouvido, confirmado e corrigido." --confirmar-campos
```

O comando registra uma declaração humana; não comprova automaticamente que a pessoa ouviu o áudio.
Não executar essa confirmação sem a conferência efetiva. Para a amostra desta implementação,
substituir `stt-<id>` por `stt-46427a77`.

Após confirmar, gerar uma **nova** minuta com o texto revisado:

```bash
python -m src.main --caso caso02_audio --nao-interativo
python -m src.main --caso caso02_audio
```

O primeiro comando processa o caso, mesmo quando já existe um PDF antigo. A nova minuta fica
PENDENTE de aprovação, inclusive com `--nao-interativo`. O segundo abre a interface de revisão.
Conferência da transcrição e aprovação da minuta são decisões diferentes.

O fluxo principal reutiliza uma transcrição confirmada vinculada ao hash do áudio e registra
seu identificador no log. Se os textos forem alterados depois da conferência, a utilização é bloqueada.
Para nova revisão após confirmação, executar outra transcrição; as evidências anteriores permanecem.
No modo `--dry-run`, o fluxo legado usa a referência humana somente como demonstração offline,
explicitamente identificada no log; isso não comprova a execução do RF06.

## Evidência real: stt-46427a77

| Medida | Resultado informado/medido |
|---|---|
| Modelo | `whisper-large-v3` |
| Idioma retornado | `Portuguese` |
| Duração do áudio | 89,160 s |
| Tempo da chamada | 1,584 s |
| Tentativas | 1 |
| Custo estimado | US$ 0,002749; não é confirmação de cobrança |
| WER normalizado | 0,0896 (12 edições / 134 palavras da referência) |
| Decisão humana | Conferido após correções — Integrante 3, 18/10/2026 |

Pontos destacados na saída bruta e conferência registrada:

- E-mail: a saída trouxe `marcos.almeida.teste.exemplo.com`; o integrante 3 confirmou o erro. Corrigido para `marcos.almeida.teste@exemplo.com` somente na versão revisada.
- Turno: a saída trouxe `noturno, noturno`; o integrante 3 confirmou a repetição. A versão revisada usa `no turno noturno`.
- Datas saíram por extenso; a comparação contra datas numéricas sinaliza divergência textual,
  mesmo quando representam a mesma data. O integrante 3 confirmou as datas 14/10/2026 e 12/08/2008 após ouvir o áudio.
- `1.200` versus `1200` e `dois/três/dez` versus `2/3/10` também afetam a métrica.
- O integrante 3 confirmou após escuta os nomes Marcos Vinícius de Almeida Santos e Lúcia Helena de Almeida Santos e o protocolo 2026-000142.

A primeira tentativa no sandbox falhou por conexão e ficou registrada como erro no log.
A execução acima ocorreu após liberar acesso de rede. Nenhuma minuta nova foi gerada com essa
transcrição real. A conferência agora está registrada, mas não aprova uma futura minuta.

## Testes e critérios de aceite

```bash
python -m unittest discover -s testes -t .
```

38 testes aprovados: 25 existentes e 13 novos em `testes/test_audio.py`, sem chamadas reais à API.
Verificam extensão/tamanho/vazio, chave ausente, 400/401/403/413, 429/5xx, timeout/rede,
resposta inválida, reenvio completo do arquivo nas retentativas, preservação do original,
ausência do gabarito na requisição, comparação de protocolo/e-mail, registro de evidências,
revisão explícita, invalidação após alteração e bloqueio da minuta sem conferência.
Também verificam que uma minuta nova não herda a aprovação histórica do exemplo.

Ambiente desta validação: Python 3.14.7, httpx 0.28.1 e python-dotenv 1.2.1, macOS.
O Python 3.13 da base do curso não estava instalado nesta máquina; não foi revalidado nesta etapa.
O pin anterior `python-dotenv==1.2.2` não estava disponível no índice consultado; foi ajustado para 1.2.1.

## Limitações e privacidade

- Só dados fictícios. O arquivo de voz completo é enviado ao Groq: mascarar o texto posteriormente
  não remove a voz nem os dados já enviados. Em produção, avaliar transcrição local e recorte do áudio
  para reduzir exposição; não foram implementados nesta etapa.
- WER usa distância de edição de palavras, ignora caixa/acentos/pontuação e não normaliza números
  por extenso. Não é taxa de aprovação nem medida suficiente de qualidade semântica.
- Diferenças literais preservam símbolos como `@`; o alinhamento ilustrativo usa difflib e não
  corresponde necessariamente ao caminho mínimo usado no cálculo de WER.
- Duração/idioma vêm do provedor. Segmentos são preservados, sem interpretar sua probabilidade
  como confirmação de correção.
- A validação local verifica extensão e tamanho; a decodificação do conteúdo é validada pelo provedor.
- Sem divisão de arquivos grandes, diarização, redução de ruído ou TTS nesta etapa.
- O cenário de ruído moderado ainda depende de conferência auditiva da amostra ou de um teste
  adicional com variante controlada, preservando o original.
- A revisão da transcrição é feita via CLI e arquivo de texto; a interface Web continua responsável
  pela revisão da minuta. A interface mostra o texto efetivamente utilizado na extração.
- Hashes detectam alterações acidentais, mas os arquivos locais não constituem uma trilha inviolável.
- Apenas uma amostra real foi executada; as outras validações são testes offline.

## Conferência humana registrada

Em 18/10/2026, o integrante 3 confirmou no chat o erro do e-mail e a repetição de turno.
À pergunta específica sobre a escuta dos nomes, protocolo e datas, respondeu:
“Sim, conferi e estão corretos”.

Com base nessa declaração, o assistente aplicou somente as duas correções em `revisada.txt`
e registrou a decisão `Conferido`, usando o identificador `Integrante 3`, justificativa e hash
por meio da rotina `confirmar_revisao`. A transcrição bruta e o áudio original permanecem intactos.
`comparacao.json` continua descrevendo a saída bruta; `comparacao_revisada.json` documenta a
comparação após as correções. Conferir a transcrição não significa aprovar uma minuta.

Não foi atribuída classificação de ruído à amostra: o usuário confirmou conteúdo, não nível de ruído.
O teste específico de ruído moderado permanece como limitação do conjunto de evidências.
