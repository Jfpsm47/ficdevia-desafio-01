# RF02 — Matriz comparativa dos prompts A, B e C

- Execução: `20261016-200939` · Caso: `caso01_texto` (`dados/originais/entrada_texto.txt`)
- Provedor/modelo (iguais nos três testes): `groq` / `openai/gpt-oss-120b`
- Parâmetros (iguais nos três testes): `{"temperature": 0.2, "top_p": 1.0, "max_tokens": 4096}`
- Entradas: `prompt_X_entrada.md` · Saídas: `prompt_X_saida.md` · Registro: `execucoes.jsonl`

## 1. Critérios automáticos

| Critério | Prompt A (zero-shot) | Prompt B (estruturado) | Prompt C (metaprompt) |
|---|---|---|---|
| Tempo de geração | 3.12 s | 1.88 s | 2.0 s (+4.09 s metaprompt) |
| Tokens entrada / saída | 326 / 1144 | 1258 / 535 | 1412 / 622 |
| Formato: seções do modelo institucional | 1/6 | 6/6 | 2/6 |
| Dados inventados / afirmações proibidas (críticos) | 6 | 0 | 0 |
| Achados altos (lacuna não sinalizada, dado pessoal exposto) | 1 | 0 | 1 |
| Achados médios / baixos | 2 / 1 | 0 / 0 | 2 / 0 |
| Lacunas sinalizadas com "não localizado" | não | sim | não |
| Palavras | 572 | 135 | 168 |
| Decisão automática sugerida | Rejeitar / nova geração | Aprovar | Correção manual |

## 2. Critérios humanos (preencher em documentacao/AVALIACAO_HUMANA.md, seção 2)

| Critério (escala) | Prompt A | Prompt B | Prompt C |
|---|---|---|---|
| Fidelidade ao contexto (1–5) | | | |
| Tom institucional (1–5) | | | |
| Tempo até resultado utilizável (min, incluindo edição humana) | | | |

## 3. Achados automáticos detalhados

### Prompt A
- **medio** · completude · Não contém nenhum de: ['2026-000142']
- **alto** · lacunas · Não contém nenhum de: ['não localizado', 'nao localizado']
- **critico** · fidelidade · Contém termo proibido: 'histórico escolar'
- **critico** · fidelidade · Contém termo proibido: 'comprovante de residência'
- **critico** · fidelidade · Contém termo proibido: 'certidão de nascimento'
- **critico** · fidelidade · Prazo/quantidade possivelmente inventado: '10 dias'
- **critico** · fidelidade · Prazo/quantidade possivelmente inventado: '90 dias'
- **critico** · fidelidade · Prazo/quantidade possivelmente inventado: '3 dias'
- **medio** · formato · Seções do modelo institucional ausentes: ['destinatario', 'fontes', 'informacoes nao localizadas', 'minuta', 'referencia']
- **baixo** · linguagem · Texto longo (572 palavras).

### Prompt B
- Nenhum achado automático.

### Prompt C
- **medio** · completude · Não contém nenhum de: ['Marcos']
- **alto** · lacunas · Não contém nenhum de: ['não localizado', 'nao localizado']
- **medio** · formato · Seções do modelo institucional ausentes: ['destinatario', 'fontes', 'informacoes nao localizadas', 'referencia']

> As verificações automáticas são heurísticas (podem ter falsos positivos/negativos). A seleção do prompt é decisão humana registrada em documentacao/AVALIACAO_HUMANA.md.
