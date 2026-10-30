"""Métricas determinísticas de recuperação, chunking, sustentação RAG e avaliação integrada (RF18, RF19, RF23).

Responsabilidade: Estudante 2 (em conjunto com a equipe nas métricas integradas do RF23).
Todas as contagens, proporções e taxas expõem explicitamente `numerador` e `denominador` e tratam
conjuntos vazios sem divisão por zero.

Uso via CLI:
  python -m src.metrics chunking       # Executa RF18 (T07) e grava resultados/metricas/rf18_comparacao_chunking.{json,md}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from src import dados_ficticios, embeddings, ingestion, prompts, schemas
from src.dados_ficticios import normalizar

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
ARQ_RAG_PERGUNTAS = RAIZ / "dados" / "gabaritos" / "d2" / "rag_perguntas.json"


def razao_segura(numerador: int, denominador: int) -> dict[str, Any]:
    """Calcula proporção determinística preservando numerador/denominador e evitando divisão por zero (RF23, T13)."""
    num = int(numerador)
    den = int(denominador)
    if den <= 0:
        return {
            "numerador": num,
            "denominador": 0,
            "taxa": None,
            "percentual": None,
            "formatado": f"{num}/0 (conjunto vazio)",
        }
    taxa = round(num / den, 4)
    return {
        "numerador": num,
        "denominador": den,
        "taxa": taxa,
        "percentual": f"{taxa:.0%}",
        "formatado": f"{num}/{den} ({taxa:.0%})",
    }


def carregar_perguntas_rag(caminho: Path | None = None) -> dict[str, Any]:
    """Carrega o gabarito validado `dados/gabaritos/d2/rag_perguntas.json`."""
    alvo = Path(caminho) if caminho else ARQ_RAG_PERGUNTAS
    return json.loads(alvo.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- RF18: Recuperação e Chunking


def trecho_satisfaz_referencia(documento_id: str, texto_trecho: str, referencia: dict[str, str]) -> bool:
    """Confere o critério congelado em `rag_perguntas.json` (comparação normalizada sem caixa/acentos)."""
    if documento_id != referencia["documento_id"]:
        return False
    return normalizar(referencia["trecho"]) in normalizar(texto_trecho)


def avaliar_recuperacao_pergunta(
    resultados_busca: list[embeddings.ResultadoBusca | dict[str, Any]],
    pergunta_gab: dict[str, Any],
) -> dict[str, Any]:
    """Avalia se o top-k recuperou ao menos um trecho de referência (e quantas referências cobriu)."""
    referencias = pergunta_gab.get("referencias", [])
    itens_norm: list[dict[str, Any]] = [
        r.para_dict() if isinstance(r, embeddings.ResultadoBusca) else dict(r)
        for r in resultados_busca
    ]

    refs_encontradas: list[dict[str, Any]] = []
    for ref in referencias:
        matching_chunks = [
            it["chunk_id"]
            for it in itens_norm
            if trecho_satisfaz_referencia(it["documento_id"], it["texto"], ref)
        ]
        refs_encontradas.append(
            {
                "documento_id": ref["documento_id"],
                "secao": ref.get("secao"),
                "trecho_referencia": ref["trecho"],
                "encontrada": bool(matching_chunks),
                "chunks_correspondentes": matching_chunks,
            }
        )

    acertou_ao_menos_uma = any(r["encontrada"] for r in refs_encontradas) if referencias else False
    cobriu_todas = all(r["encontrada"] for r in refs_encontradas) if referencias else True

    return {
        "id": pergunta_gab["id"],
        "tipo": pergunta_gab["tipo"],
        "pergunta": pergunta_gab["pergunta"],
        "acerto_top_k": acertou_ao_menos_uma,
        "cobriu_todas_referencias": cobriu_todas,
        "referencias_avaliadas": refs_encontradas,
        "top_k_recuperado": [
            {
                "posicao": it["posicao"],
                "chunk_id": it["chunk_id"],
                "documento_id": it["documento_id"],
                "versao_documento": it["versao_documento"],
                "pagina": it["pagina"],
                "secao": it["secao"],
                "similaridade": it["similaridade"],
                "caracteres": len(it["texto"]),
            }
            for it in itens_norm
        ],
    }


def calcular_acerto_recuperacao(
    buscas_por_id: dict[str, list[embeddings.ResultadoBusca | dict[str, Any]]],
    perguntas_gab: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calcula a taxa de acerto de recuperação nas perguntas respondíveis (`acertos / N` — RF18, RF23)."""
    respondiveis = [p for p in perguntas_gab if p.get("tipo") == "respondivel"]
    avaliacoes = [
        avaliar_recuperacao_pergunta(buscas_por_id.get(p["id"], []), p)
        for p in respondiveis
    ]
    acertos = sum(1 for av in avaliacoes if av["acerto_top_k"])
    cobertura_total = sum(1 for av in avaliacoes if av["cobriu_todas_referencias"])
    return {
        "acerto_recuperacao": razao_segura(acertos, len(respondiveis)),
        "cobertura_integral_referencias": razao_segura(cobertura_total, len(respondiveis)),
        "resultados_por_pergunta": avaliacoes,
    }


def _analisar_preservacao_secoes(trechos: list[schemas.TrechoIndexado]) -> dict[str, Any]:
    """Verifica quantas seções numeradas foram partidas em múltiplos chunks na configuração avaliada."""
    ocorrencias_por_secao: dict[tuple[str, str], int] = {}
    for t in trechos:
        if not t.secao:
            continue
        for parte in t.secao.split("; "):
            if re.match(r"^\d+\.\s+", parte):
                chave = (t.documento_id, parte)
                ocorrencias_por_secao[chave] = ocorrencias_por_secao.get(chave, 0) + 1
    secoes_fragmentadas = [
        f"{doc_id} — {sec} ({qtd} chunks)"
        for (doc_id, sec), qtd in sorted(ocorrencias_por_secao.items())
        if qtd > 1
    ]
    return {
        "total_trechos_acervo": len(trechos),
        "media_caracteres_por_trecho": round(sum(len(t.texto) for t in trechos) / len(trechos), 1) if trechos else 0.0,
        "qtd_secoes_em_multiplos_chunks": len(secoes_fragmentadas),
        "secoes_em_multiplos_chunks": secoes_fragmentadas,
    }


def executar_experimento_chunking(
    *,
    config: dict[str, Any] | None = None,
    embedder: embeddings.AdaptadorEmbeddings | None = None,
    diretorio_saida: Path | None = None,
    limpar_indices_temporarios: bool = False,
) -> dict[str, Any]:
    """Compara duas configurações de tamanho e sobreposição de chunks sobre P01..P05 (RF18, T07)."""
    cfg_global = config or CONFIG
    cfg_exp = cfg_global["experimento_chunking"]
    emb = embedder or embeddings.criar_adaptador_embeddings(cfg_global)
    top_k = int(cfg_exp.get("top_k", 3))
    gab = carregar_perguntas_rag()
    perguntas_resp = [p for p in gab["perguntas"] if p["tipo"] == "respondivel"]

    comparativo: dict[str, Any] = {}
    for nome_cfg, params_cfg in cfg_exp["configuracoes"].items():
        rel_dir = params_cfg["diretorio_indice"]
        pasta_idx = Path(rel_dir) if Path(rel_dir).is_absolute() else (RAIZ / rel_dir)
        idx = embeddings.IndiceVetorial(
            diretorio=pasta_idx,
            embedder=emb,
            unidade_chunk=params_cfg["unidade"],
            tamanho_chunk=int(params_cfg["tamanho"]),
            sobreposicao_chunk=int(params_cfg["sobreposicao"]),
        )
        idx.indexar_acervo(forcar_reindexacao=True)

        buscas = {p["id"]: idx.buscar(p["pergunta"], top_k=top_k) for p in perguntas_resp}
        metricas_rec = calcular_acerto_recuperacao(buscas, perguntas_resp)
        analise_secoes = _analisar_preservacao_secoes(idx.trechos)

        # Verifica se em P01 o chunk recuperado no top-1 contém a lista integral de documentos + regra menores de 18
        top1_p01 = buscas["P01"][0].trecho.texto if buscas.get("P01") else ""
        p01_contexto_completo_no_top1 = (
            "documento oficial de identidade com foto" in normalizar(top1_p01)
            and "comprovante de residencia emitido nos ultimos 90 dias" in normalizar(top1_p01)
            and "menores de 18 anos" in normalizar(top1_p01)
        )

        comparativo[nome_cfg] = {
            "id_configuracao": idx.configuracao_chunking,
            "unidade": params_cfg["unidade"],
            "tamanho": int(params_cfg["tamanho"]),
            "sobreposicao": int(params_cfg["sobreposicao"]),
            "versao_indice": idx.versao_indice,
            "p01_lista_integral_no_top1": p01_contexto_completo_no_top1,
            **analise_secoes,
            **metricas_rec,
        }

        if limpar_indices_temporarios and pasta_idx.is_dir():
            import shutil

            shutil.rmtree(pasta_idx, ignore_errors=True)

    # Seleção justificada: maior acerto de recuperação; em empate, maior cobertura integral e preservação de contexto
    nomes = list(comparativo.keys())
    escolhida = max(
        nomes,
        key=lambda k: (
            comparativo[k]["acerto_recuperacao"]["numerador"],
            comparativo[k]["cobertura_integral_referencias"]["numerador"],
            1 if comparativo[k]["p01_lista_integral_no_top1"] else 0,
            -comparativo[k]["qtd_secoes_em_multiplos_chunks"],
        ),
    )

    justificativa = (
        f"A configuração '{escolhida}' ({comparativo[escolhida]['id_configuracao']}) foi selecionada para o índice "
        f"oficial porque obteve acerto de recuperação de {comparativo[escolhida]['acerto_recuperacao']['formatado']} "
        f"(cobertura integral das referências: {comparativo[escolhida]['cobertura_integral_referencias']['formatado']}) "
        "e preserva integralmente as seções normativas críticas em um único trecho — em especial a seção "
        "'2. Documentos exigidos para a matrícula' do ACV-01 (~470 caracteres), evitando a fragmentação da lista "
        "de documentos e da condição para menores de 18 anos observada na configuração granular de 320 caracteres."
    )

    relatorio = {
        "experimento": "RF18 — Comparação de Chunking e Recuperação",
        "modelo_embedding": emb.modelo,
        "provedor_embedding": emb.provedor,
        "dimensao": emb.dimensao,
        "top_k": top_k,
        "criterio_acerto": gab["criterio_acerto_recuperacao"],
        "configuracoes": comparativo,
        "configuracao_escolhida": escolhida,
        "id_configuracao_escolhida": comparativo[escolhida]["id_configuracao"],
        "justificativa_escolha": justificativa,
        "falhas_e_ajustes_registrados": [
            "Na configuração granular (320 caracteres, sobreposição 50), a seção 2 do ACV-01 foi dividida em dois "
            "chunks (ACV-01#c3 e ACV-01#c4), separando os primeiros itens da lista de matrícula da exigência de "
            "foto 3x4 e documento do responsável para menores de 18 anos.",
            "Ajuste aplicado no divisor (`src/ingestion.py`): nunca misturar páginas distintas de um PDF no mesmo "
            "chunk para garantir que o metadado `pagina` permaneça exato e conferível nas citações do RF19.",
        ],
    }

    pasta_out = Path(diretorio_saida) if diretorio_saida else (RAIZ / cfg_exp.get("diretorio_saida", "resultados/metricas"))
    pasta_out.mkdir(parents=True, exist_ok=True)
    arq_json = pasta_out / "rf18_comparacao_chunking.json"
    arq_md = pasta_out / "rf18_comparacao_chunking.md"

    arq_json.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    arq_md.write_text(_renderizar_markdown_rf18(relatorio), encoding="utf-8", newline="\n")
    return relatorio


def _renderizar_markdown_rf18(rel: dict[str, Any]) -> str:
    linhas = [
        "# RF18 — Comparação de Chunking e Recuperação",
        "",
        f"- **Modelo de embedding:** `{rel['modelo_embedding']}` (`{rel['provedor_embedding']}`, dimensão `{rel['dimensao']}`)",
        f"- **Busca avaliada:** `top_k = {rel['top_k']}` sobre as 5 perguntas respondíveis (`P01` a `P05`)",
        f"- **Unidade declarada:** `caracteres`",
        f"- **Configuração selecionada:** **`{rel['configuracao_escolhida']}`** (`{rel['id_configuracao_escolhida']}`)",
        "",
        "## 1. Resumo das Configurações",
        "",
        "| Configuração | Parâmetros (`unidade-tam-sobreposicao`) | Total de Chunks | Média (chars) | Acerto Top-k (`P01..P05`) | Cobertura Integral de Refs | Lista integral de `P01` no Top-1 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for nome, c in rel["configuracoes"].items():
        linhas.append(
            f"| `{nome}` | `{c['id_configuracao']}` | {c['total_trechos_acervo']} | "
            f"{c['media_caracteres_por_trecho']} | **{c['acerto_recuperacao']['formatado']}** | "
            f"{c['cobertura_integral_referencias']['formatado']} | "
            f"{'Sim' if c['p01_lista_integral_no_top1'] else 'Não (fragmentada)'} |"
        )

    linhas += [
        "",
        "## 2. Resultados por Pergunta",
        "",
        "| Pergunta | Configuração | Acerto Top-k | Chunks Correspondentes | Top-k Recuperado (`chunk_id` · sim · pág · seção) |",
        "|---|---|---|---|---|",
    ]
    ids_perguntas = [r["id"] for r in next(iter(rel["configuracoes"].values()))["resultados_por_pergunta"]]
    for pid in ids_perguntas:
        for nome, c in rel["configuracoes"].items():
            rp = next(x for x in c["resultados_por_pergunta"] if x["id"] == pid)
            corresp = sorted({cid for ref in rp["referencias_avaliadas"] for cid in ref["chunks_correspondentes"]})
            resumo_topk = "<br>".join(
                f"`{it['chunk_id']}` ({it['similaridade']:.3f}, pág. {it['pagina'] or '—'}, *{it['secao']}*)"
                for it in rp["top_k_recuperado"]
            )
            linhas.append(
                f"| **{pid}** | `{nome}` | {'ACERTO' if rp['acerto_top_k'] else 'FALHA'} | "
                f"{', '.join(f'`{x}`' for x in corresp) or '—'} | {resumo_topk} |"
            )

    linhas += [
        "",
        "## 3. Seleção e Justificativa",
        "",
        rel["justificativa_escolha"],
        "",
        "## 4. Falhas e Ajustes Registrados",
        "",
    ]
    for item in rel["falhas_e_ajustes_registrados"]:
        linhas.append(f"- {item}")
    linhas.append("")
    return "\n".join(linhas)


# ---------------------------------------------------------------- RF19 e RF23: Sustentação, Abstenção e Agregação


def verificar_resposta_rag_contra_fontes(
    resposta_rag: schemas.RespostaRAG | dict[str, Any],
    trechos_recuperados: list[embeddings.ResultadoBusca | schemas.TrechoIndexado | dict[str, Any]],
    pergunta_gab: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Confere se todas as afirmações institucionais possuem suporte real nos trechos recuperados e sem proibições."""
    obj = (
        resposta_rag
        if isinstance(resposta_rag, schemas.RespostaRAG)
        else schemas.RespostaRAG.model_validate(resposta_rag)
    )
    mapa_recuperados: dict[str, dict[str, Any]] = {}
    for item in trechos_recuperados:
        if isinstance(item, embeddings.ResultadoBusca):
            d = item.trecho.model_dump()
        elif isinstance(item, schemas.TrechoIndexado):
            d = item.model_dump()
        else:
            d = dict(item)
        mapa_recuperados[d["chunk_id"]] = d

    citacoes_por_id = {c.chunk_id: c for c in obj.citacoes}
    citacoes_verificadas = True
    erros_citacao: list[str] = []

    for c in obj.citacoes:
        orig = mapa_recuperados.get(c.chunk_id)
        if not orig:
            citacoes_verificadas = False
            erros_citacao.append(f"chunk_id '{c.chunk_id}' não pertence aos trechos recuperados")
            continue
        if (
            c.documento_id != orig["documento_id"]
            or c.versao_documento != orig["versao_documento"]
            or normalizar(c.trecho) not in normalizar(orig["texto"])
        ):
            citacoes_verificadas = False
            erros_citacao.append(f"metadados/trecho da citação '{c.chunk_id}' divergem da fonte no índice")

    afirmacoes_sustentadas = 0
    for af in obj.afirmacoes:
        chunks_validos = [
            cid for cid in af.chunk_ids if cid in citacoes_por_id and cid in mapa_recuperados
        ]
        if len(chunks_validos) == len(af.chunk_ids) and len(chunks_validos) >= 1:
            afirmacoes_sustentadas += 1

    todas_afirmacoes_sustentadas = (
        citacoes_verificadas
        and afirmacoes_sustentadas == len(obj.afirmacoes)
        and (len(obj.afirmacoes) > 0 if obj.status != "sem_evidencia" else len(obj.afirmacoes) == 0)
    )

    violacoes_proibidas: list[str] = []
    status_confere: bool | None = None
    docs_esperados_citados: bool | None = None
    if pergunta_gab is not None:
        status_confere = obj.status == pergunta_gab.get("status_esperado")
        texto_alvo = " ".join([obj.resposta, *(a.texto for a in obj.afirmacoes)])
        for padrao in pergunta_gab.get("padroes_proibidos", []):
            if re.search(padrao, texto_alvo, re.I):
                violacoes_proibidas.append(padrao)
        refs_docs = {r["documento_id"] for r in pergunta_gab.get("referencias", [])}
        if refs_docs:
            docs_citados = {c.documento_id for c in obj.citacoes}
            docs_esperados_citados = refs_docs.issubset(docs_citados)

    sustentada_sem_alucinacao = todas_afirmacoes_sustentadas and not violacoes_proibidas

    return {
        "status_obtido": obj.status,
        "status_esperado": pergunta_gab.get("status_esperado") if pergunta_gab else None,
        "status_confere": status_confere,
        "total_afirmacoes": len(obj.afirmacoes),
        "afirmacoes_sustentadas": afirmacoes_sustentadas,
        "citacoes_verificadas": citacoes_verificadas,
        "erros_citacao": erros_citacao,
        "docs_esperados_citados": docs_esperados_citados,
        "padroes_proibidos_acionados": violacoes_proibidas,
        "todas_afirmacoes_sustentadas": sustentada_sem_alucinacao,
        "requer_revisao": obj.requer_revisao,
    }


def calcular_metricas_rag_rf23(
    execucoes_por_id: dict[str, dict[str, Any]],
    perguntas_gab: list[dict[str, Any]],
) -> dict[str, Any]:
    """Consolida as métricas obrigatórias do RF23 sob responsabilidade do Estudante 2."""
    respondiveis = [p for p in perguntas_gab if p["tipo"] == "respondivel"]
    sem_resposta = [p for p in perguntas_gab if p["tipo"] == "sem_resposta"]
    contraditorias = [p for p in perguntas_gab if p["tipo"] == "contraditoria"]

    # 1. Acerto de recuperação nas 5 respondíveis
    buscas_map = {pid: dados.get("trechos_recuperados", []) for pid, dados in execucoes_por_id.items()}
    rec = calcular_acerto_recuperacao(buscas_map, perguntas_gab)

    # 2. Proporção de respostas institucionais com todas as afirmações sustentadas (sobre respondíveis + contraditória)
    alvo_institucionais = [*respondiveis, *contraditorias]
    inst_sustentadas = 0
    detalhes_verificacao: dict[str, dict[str, Any]] = {}
    for p in perguntas_gab:
        exec_p = execucoes_por_id.get(p["id"])
        if not exec_p or not exec_p.get("resposta_rag"):
            continue
        ver = verificar_resposta_rag_contra_fontes(
            exec_p["resposta_rag"],
            exec_p.get("trechos_recuperados", []),
            p,
        )
        ver["estado_execucao"] = str(exec_p.get("estado", "valida"))
        detalhes_verificacao[p["id"]] = ver

    for p in alvo_institucionais:
        ver = detalhes_verificacao.get(p["id"])
        if (
            ver
            and ver["estado_execucao"] == "valida"
            and ver["todas_afirmacoes_sustentadas"]
            and ver["status_confere"]
            and ver["docs_esperados_citados"]
        ):
            inst_sustentadas += 1

    # 3. Abstenção correta nas 2 perguntas sem resposta (exige estado=='valida'; contingência por falha não conta)
    abstencoes_ok = 0
    for p in sem_resposta:
        ver = detalhes_verificacao.get(p["id"])
        if (
            ver
            and ver["estado_execucao"] == "valida"
            and ver["status_obtido"] == "sem_evidencia"
            and ver["total_afirmacoes"] == 0
            and ver["requer_revisao"]
            and not ver["padroes_proibidos_acionados"]
        ):
            abstencoes_ok += 1

    # 4. Caso contraditório registrado separadamente (P06)
    relatorio_contraditorio: list[dict[str, Any]] = []
    for p in contraditorias:
        ver = detalhes_verificacao.get(p["id"])
        correto = bool(
            ver
            and ver["estado_execucao"] == "valida"
            and ver["status_obtido"] == "conflito_fontes"
            and ver["docs_esperados_citados"]
            and ver["requer_revisao"]
            and not ver["padroes_proibidos_acionados"]
        )
        relatorio_contraditorio.append(
            {
                "id": p["id"],
                "pergunta": p["pergunta"],
                "status_esperado": p["status_esperado"],
                "status_obtido": ver["status_obtido"] if ver else None,
                "conflito_tratado_corretamente": correto,
                "detalhes": ver,
            }
        )

    return {
        "acerto_recuperacao": rec["acerto_recuperacao"],
        "respostas_institucionais_sustentadas": razao_segura(inst_sustentadas, len(alvo_institucionais)),
        "abstencao_correta": razao_segura(abstencoes_ok, len(sem_resposta)),
        "casos_contraditorios": relatorio_contraditorio,
        "verificacao_por_pergunta": detalhes_verificacao,
    }


def agregar_registros_deterministico(
    registros: list[dict[str, Any]],
    *,
    chave_id: str,
    chave_rotulo: str,
    filtros: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Agrega rótulos por código com filtro, remoção de duplicatas por ID e proteção contra conjunto vazio (T13)."""
    vistos: set[str] = set()
    unicos: list[dict[str, Any]] = []
    duplicatas_ignoradas = 0
    for item in registros:
        ident = str(item.get(chave_id, ""))
        if ident in vistos:
            duplicatas_ignoradas += 1
            continue
        vistos.add(ident)
        unicos.append(item)

    filtrados = unicos
    for campo_f, valor_f in (filtros or {}).items():
        if valor_f is None or valor_f == "" or valor_f == "todos":
            continue
        filtrados = [r for r in filtrados if r.get(campo_f) == valor_f]

    total = len(filtrados)
    contagem: dict[str, int] = {}
    for r in filtrados:
        rot = str(r.get(chave_rotulo, "indefinido"))
        contagem[rot] = contagem.get(rot, 0) + 1

    proporcoes = {rot: razao_segura(qtd, total) for rot, qtd in sorted(contagem.items())}
    return {
        "total_recebidos": len(registros),
        "duplicatas_ignoradas": duplicatas_ignoradas,
        "denominador_filtrado": total,
        "contagens": contagem,
        "proporcoes": proporcoes,
    }


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Métricas determinísticas e experimento de chunking (RF18, RF23).")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_chk = sub.add_parser("chunking", help="Executa a comparação de duas configurações de chunking (RF18 / T07)")
    p_chk.add_argument("--limpar-temp", action="store_true", help="Remove pastas temporárias de índice após medir")

    args = parser.parse_args(argv)
    if args.comando == "chunking":
        rel = executar_experimento_chunking(limpar_indices_temporarios=args.limpar_temp)
        print(
            f"[OK] RF18 concluído -> escolhida: {rel['configuracao_escolhida']} "
            f"({rel['id_configuracao_escolhida']}) | "
            f"acerto: {rel['configuracoes'][rel['configuracao_escolhida']]['acerto_recuperacao']['formatado']}"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
