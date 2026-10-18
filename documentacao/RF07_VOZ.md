# RF07 — Síntese de voz e acessibilidade

Implementação do Estudante 3, 18/10/2026. Nenhum commit foi realizado pelo assistente.

## Decisão técnica

- Modelo aberto local: `pt_BR-faber-medium`, pelo runtime `piper-tts` 1.8.0. O modelo é voltado ao
  português brasileiro e gera WAV PCM sem chamar API nem transmitir a minuta para terceiros.
- Voz selecionada: Faber. Direção de acessibilidade: comunicação institucional clara, ritmo levemente
  reduzido (`length_scale=1.05`) e pausa de 220 ms entre blocos longos.
- O Piper não recebe instruções livres de estilo como uma LLM. A direção é aplicada somente pelos
  controles técnicos de ritmo, volume e pausas; a naturalidade e a pronúncia devem ser avaliadas em
  escuta humana.
- O modelo tem licença `CC0-1.0`; o runtime Piper tem licença `GPL-3.0`. Os pesos baixados ficam em
  `.cache/piper/`, diretório ignorado pelo Git para não versionar aproximadamente 60 MB no repositório.
- A função aceita somente a última minuta cuja auditoria e cujo próprio PDF mostrem decisão humana
  `Aprovada`. Minutas pendentes, corrigidas, rejeitadas, ausentes ou alteradas de modo inconsistente são
  bloqueadas antes da síntese.
- O texto efetivamente falado é salvo em `texto_falado.txt`. Metadados guardam hashes da minuta, do
  texto e do WAV, a identificação da minuta, modelo, voz, ajustes locais, latência e custo estimado de
  US$ 0,00. Não há envio automático ao cidadão.

## Instalação do modelo local

Na raiz do repositório, com o ambiente virtual ativado:

```bash
python -m pip install -r requirements.txt
python -m piper.download_voices pt_BR-faber-medium --download-dir .cache/piper
```

O segundo comando é uma preparação única para baixar os pesos do modelo. A síntese posterior funciona
localmente e não requer chave adicional no `.env`.

## Como executar

```bash
python -m src.audio sintetizar --caso caso02_audio
```

Em caso de sucesso, a execução cria `resultados/audios/tts-<id>/` com:

| Arquivo | Finalidade |
|---|---|
| `minuta.wav` | Versão falada em formato comum |
| `texto_falado.txt` | Conteúdo enviado ao Piper, para conferência humana |
| `metadados.json` | Origem aprovada, hashes, modelo, voz, ajustes, latência e custo |

Minutas superiores a 1.000 caracteres são divididas por frase ou palavra e reunidas em um WAV. A divisão
não descarta conteúdo. Linhas de rastreabilidade e decisão humana não são faladas; o conteúdo
institucional e qualquer aviso de informação não localizada permanecem no texto falado.

## Critério de aceite e revisão

1. Confirmar que a minuta indicada no log está aprovada e que o PDF preserva `Status: **Aprovada**`.
2. Executar a síntese e abrir `texto_falado.txt` ao lado do WAV.
3. Ouvir o WAV inteiro e verificar que protocolo, datas, nomes, informações não localizadas e sentido do
   texto aprovado foram preservados, sem acréscimos relevantes.
4. Registrar a escuta com o comando abaixo, substituindo o caminho pelo diretório gerado:

```bash
python -m src.audio revisar-voz resultados/audios/tts-<id> \
  --revisor "Integrante 3" \
  --justificativa "Conteúdo, datas e aviso de lacuna conferidos na escuta." \
  --decisao Aprovada \
  --confirmar-correspondencia
```

A aprovação da minuta permite gerar o áudio, mas não aprova automaticamente a qualidade do WAV. A decisão
da escuta é mantida separadamente na auditoria.

## Evidência gerada

A execução local `tts-9c86357b` gerou `resultados/audios/tts-9c86357b/minuta.wav` em 1,739 s. O WAV é
PCM mono, 22.050 Hz, dura 74,721 s e contém os mesmos 1.115 caracteres de `texto_falado.txt`, incluindo
o aviso de informação não localizada. A integridade do áudio foi conferida pelo SHA-256 registrado nos
metadados. Em 18/10/2026, o Integrante 3 ouviu a amostra e aprovou conteúdo, nomes, protocolo, datas e
aviso de informação não localizada. A decisão `Aprovada` e a justificativa foram registradas nos
metadados e na auditoria.

O recurso amplia a acessibilidade ao oferecer a minuta em áudio para pessoas que preferem ou necessitam
de conteúdo falado. Ele não substitui texto acessível, revisão humana, leitor de tela nem validação de
pronúncia de nomes, siglas, números e datas.

## Testes e limitações

```bash
python -m unittest discover -s testes -t .
```

Os 7 testes específicos do RF07 não chamam rede nem executam inferência real. Eles verificam bloqueio de
minutas sem aprovação, consistência entre auditoria e PDF, divisão sem perda de texto, manutenção do
aviso de lacuna, geração de WAV, registro da escuta e falha do Piper sem deixar arquivo parcial.

Uma tentativa anterior com o TTS da Groq falhou porque o modelo Orpheus exigia aceitação de termos pela
organização e não declarava suporte a português brasileiro. O registro de falha foi mantido na auditoria.
A implementação adotada para a entrega é o Piper local, com suporte ao idioma e sem dependência de API
para o RF07.

Fontes consultadas em 18/10/2026: [modelo Faber](https://huggingface.co/Trelis/piper-pt-br-faber-medium)
e [catálogo de vozes Piper](https://huggingface.co/rhasspy/piper-voices).
