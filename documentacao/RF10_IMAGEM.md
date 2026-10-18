# RF10 — Geração de imagem e orientação visual

Implementação do Integrante 3, 18/10/2026. A peça é uma ilustração fictícia para orientar uma solicitação de matrícula. Ela não representa pessoas reais, documentos reais, matrícula deferida ou dados pessoais.

## Decisão técnica

- A geração ocorreu localmente no **Draw Things 26.1013.0**, em macOS, com o modelo aberto `FLUX.2 [klein] 4B (6-bit)`. Não houve chamada a serviço de IA, upload do prompt nem uso de chave de API.
- O modelo `FLUX.2 [klein] 4B` é disponibilizado sob **Apache-2.0**; o repositório oficial também indica que a variante destilada usa quatro passos e guidance 1.0. A quantização 6-bit é a variante distribuída pelo Draw Things para execução local. Consulte o [repositório oficial do FLUX.2](https://github.com/black-forest-labs/flux2).
- A geração usa seed fixa `20261018`, lote 1, `DDIM Trailing`, shift 3.0, quatro passos e CFG 1.0. O prompt está versionado em `prompts/producao/imagem_orientacao_v1.md` e inclui assunto, composição, estilo, iluminação, proporção e restrições.
- O Draw Things exportou a arte base em 1024×1024. O projeto a preserva integralmente e monta a peça de entrega em 1024×576 (16:9), sem corte: centraliza a arte sobre o fundo original e aplica título e proveniência controlados pela equipe.
- A chave da Groq e quaisquer chaves em `.env` não participam deste RF.

## Geração local e evidências

No Draw Things, selecionar `FLUX.2 [klein] 4B (6-bit)`, usar os parâmetros acima e salvar o PNG em `resultados/imagens/`. Em seguida, importar a saída para registrar as evidências:

```bash
python -m src.image_generation importar resultados/imagens/<png-exportado-pelo-draw-things>.png \
  --caso caso01_texto
```

O comando não chama a rede. Ele gera uma pasta `resultados/imagens/img-<id>/`:

| Arquivo | Finalidade |
|---|---|
| `prompt_efetivo.md` | Prompt exatamente inserido no modelo |
| `imagem_base.png` | PNG original exportado pelo Draw Things, preservado sem corte |
| `peca_orientacao.png` | Peça final 16:9, com título e aviso de proveniência |
| `inspecao.json` | Validações de PNG, dimensões, proporção e presença do aviso |
| `metadados.json` | Ferramenta, modelo, licença, data, parâmetros, hashes e decisão humana |
| `revisao.json` | Decisão e declaração humanas, criada somente após inspeção |

A faixa visível da peça final diz `VISUAL GERADO POR IA • MATERIAL FICTÍCIO • REVISÃO HUMANA OBRIGATÓRIA`. Isso preserva a origem mesmo se os metadados do PNG forem removidos em uma futura publicação.

## Revisão humana obrigatória

A execução fica `PENDENTE` até a equipe abrir `imagem_base.png` e `peca_orientacao.png` e conferir:

1. Texto, letras e números indesejados criados pelo modelo, inclusive no fundo.
2. Símbolos, logotipos, brasões, QR codes, selos, assinaturas ou marcas indevidas.
3. Mãos, objetos, documentos, perspectiva e proporções. A peça planejada não deve conter mãos ou pessoas.
4. Coerência com a orientação: comunicar pedido e conferência, sem inventar documentos exigidos nem afirmar matrícula concluída.

Depois de concluir os quatro itens, registrar a decisão, substituindo a pasta pelo identificador efetivamente criado:

```bash
python -m src.image_generation revisar resultados/imagens/img-<id> \
  --revisor "Integrante 3" \
  --justificativa "Textos, símbolos, mãos, objetos e coerência visual conferidos." \
  --decisao Aprovada \
  --confirmar-textos \
  --confirmar-simbolos \
  --confirmar-maos-objetos \
  --confirmar-coerencia
```

O comando confere os hashes do prompt, da imagem base e da peça final. Se algum arquivo for alterado depois da importação, a revisão é bloqueada e deve ser feita sobre uma nova execução. Uma decisão `Rejeitada` também exige a inspeção completa e preserva o motivo no log estruturado.

## Testes e limite conhecido

```bash
python -m unittest discover -s testes -t .
```

Os testes não acessam rede nem usam chaves. Eles validam a configuração local, bloqueiam PNG fora de `resultados/imagens/`, conferem preservação da origem, composição final 16:9, parâmetros e proveniência, exigem quatro confirmações humanas e recusam evidência alterada.

Para a apresentação, a equipe deve registrar que escolheu o modelo aberto compacto `FLUX.2 [klein] 4B` quantizado em 6-bit e executado localmente, após a cota gratuita do serviço hospedado impedir a alternativa inicial. Essa decisão eliminou custo e envio de dados, mas reduziu a capacidade de iterar muitas variações e pode resultar em acabamento visual mais simples do que modelos proprietários maiores ou serviços hospedados. A peça foi aceita porque atende às restrições funcionais e de segurança do RF10; essa limitação estética permanece documentada.

O prompt reduz a chance de texto, pessoas e símbolos indevidos, mas não a elimina. Por isso a inspeção humana é parte obrigatória do RF10 e a peça não deve ser utilizada antes de a decisão `Aprovada` aparecer em `metadados.json`, `revisao.json` e no log estruturado.
