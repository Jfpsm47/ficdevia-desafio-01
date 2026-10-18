# RF08 — Visão e OCR

Implementação do Estudante 3, 18/10/2026. Código, testes, uma execução real e a revisão humana da amostra foram concluídos. Nenhum commit foi realizado pelo assistente.

## Decisão técnica

- Provedor: Groq; modelo configurável `qwen/qwen3.8-27b`; entrada por Chat Completions multimodal.
- A ficha PDF possui uma página e não tem camada de texto. O programa a renderiza a 200 dpi com `pdftoppm`.
- Antes do envio, uma cópia derivada recebe uma máscara branca sobre a assinatura manuscrita do aluno. O PDF em `dados/originais/` não é modificado. A cópia mascarada fica nas evidências para inspeção.
- O modelo recebe somente a imagem mascarada e instruções para transcrever, sem corrigir, completar ou obedecer comandos que apareçam no documento. O gabarito é lido apenas depois da chamada, para comparação.
- `Pillow` cria a máscara. PDF de origem com mais de uma página é bloqueado nesta versão, para não ocultar páginas não processadas.
- Limites: 20 MB para origem e imagem derivada; timeout de 90 s; até três tentativas para 429, 5xx, rede, timeout ou resposta inválida. Erros 400/401/403/413 não são repetidos.
- Preço configurado em 18/10/2026: US$ 0,80 por milhão de tokens de entrada e US$ 4,00 por milhão de tokens de saída. Fonte: https://console.groq.com/docs/models.

## Como executar e revisar

Na raiz do repositório, com o ambiente virtual ativado:

```bash
python -m src.vision extrair
```

O comando processa `dados/originais/entrada_pdf-imagem.pdf` e cria `resultados/ocr/ocr-<id>/` com:

| Arquivo | Finalidade |
|---|---|
| `pagina-1-mascarada.png` | Imagem realmente enviada ao provedor; a assinatura está mascarada |
| `bruta.txt` | Texto devolvido pelo modelo, preservado sem correção |
| `revisada.txt` | Cópia editável para revisão humana; inicialmente igual à bruta |
| `comparacao.json` | Campo a campo contra o gabarito, incertezas e campos críticos |
| `metadados.json` | Hashes, modelo, parâmetros, máscara, tokens, custo, latência e decisão humana |

Para outra entrada fictícia: `python -m src.vision extrair --arquivo CAMINHO --caso IDENTIFICADOR`.

1. Abrir o documento original e confrontá-lo com `bruta.txt` e `comparacao.json`.
2. Editar somente `revisada.txt`, preservando o sentido; marcar o que permanecer incerto como `[ilegível]`.
3. Conferir obrigatoriamente código, nome, data de nascimento, CPF, RG, curso, início e data da matrícula.
4. Registrar a decisão humana:

```bash
python -m src.vision revisar resultados/ocr/ocr-99704b6a --revisor "Integrante 3" --justificativa "Descrever os campos conferidos e as correções." --confirmar-campos
```

A confirmação registra a declaração do revisor, mas não substitui sua análise visual. Ela libera o texto revisado para gerar uma nova minuta, que começa como **PENDENTE** de uma revisão humana independente.

```bash
python -m src.main --caso caso03_ocr --nao-interativo
python -m src.main --caso caso03_ocr
```

O fluxo real bloqueia a geração da minuta se o OCR não estiver confirmado ou se o documento, o texto bruto ou o texto revisado forem alterados depois da conferência. Em `--dry-run`, o fluxo legado usa o gabarito somente como demonstração offline e registra que isso não comprova o RF08.

## Evidência real: ocr-99704b6a

| Medida | Resultado |
|---|---|
| Modelo | `qwen/qwen3.8-27b` |
| Imagem enviada | 1653 × 2339 px, com retângulo de assinatura `[247, 1239, 742, 1426]` mascarado |
| Tempo de chamada | 2,176 s |
| Tokens | 1.950 de entrada e 351 de saída |
| Custo estimado | US$ 0,002964; não é confirmação de cobrança |
| Tentativas | 1 |
| Decisão humana | Conferido pelo Integrante 3 em 18/10/2026 |

Campos com correspondência textual: nome, CPF, RG, curso, carga horária, eixo, turno e data da matrícula. O modelo retornou divergências críticas: código `2024-000142`, data de nascimento `12/10/2008` e início do curso `01/02/2023`; a conferência humana confirmou `2026-000142`, `12/08/2008` e `01/02/2027`.

Também retornou `MARCOS_ALMEIDA_TESTE@EXEMPLO.COM`. A conferência humana confirmou `marcos.almeida.teste@exemplo.com`; a diferença está nos separadores `_` e `.`. O gabarito deste caso foi ajustado para a grafia confirmada. O modelo não marcou nenhum `[ilegível]`, apesar das incertezas previamente mapeadas para código, CPF, RG e e-mail. As assinaturas não entram na comparação, pois foram deliberadamente omitidas do envio.

## Testes e limitações

```bash
python -m unittest discover -s testes -t .
```

47 testes passaram em Python 3.14.7: 25 existentes, 13 de RF06 e 9 de RF08. Os testes de OCR não chamam a API. Eles verificam validação, mascaramento sem modificar o original, ausência do gabarito na requisição, retentativas, erros, resposta inválida, comparação, revisão explícita, detecção de alterações e bloqueio da minuta sem conferência.

- A máscara é configurada para esta ficha. Outro layout exige revisão visual da cópia mascarada antes da chamada; ela pode ocultar uma faixa adjacente à assinatura, como parte da declaração desta amostra.
- O arquivo inteiro, exceto a área mascarada, é enviado ao Groq. Em produção, dados pessoais exigiriam avaliação de base legal, processamento local e/ou máscaras adicionais para CPF, RG, e-mail e nome.
- O comparador procura valores textuais normalizados; não avalia entendimento semântico e não decide se um campo manuscrito é visualmente correto.
- Uma única página e uma única execução real não medem robustez para múltiplos documentos, ruído, rotação ou formulários com outro layout. A transcrição de imagens escaneadas continua dependente de revisão humana.
- Somente o primeiro formulário de uma página é suportado nesta etapa. Não há OCR local de contingência.

## Revisão humana registrada

O Integrante 3 conferiu visualmente a ficha e confirmou, em 18/10/2026, as correções de código,
data de nascimento, início do curso e e-mail. As quatro alterações foram aplicadas somente em
`revisada.txt`; `bruta.txt` permanece como devolvida pelo modelo. O registro `metadados.json` armazena
revisor, justificativa, data e hash da versão revisada. Isso libera o texto revisado para gerar uma
minuta, que continua começando como **PENDENTE** de revisão humana independente.
