"""Classificação de sentimentos das avaliações de atendimento e agregação por código (RF22, RF23/T13).

Responsabilidade: Estudante 3 (Desafio 02).
- Cada avaliação é enviada sozinha ao provedor, só com ID e texto (data, canal e categoria ficam fora),
  delimitada como conteúdo não confiável (`prompts.montar_mensagens_sentimento`);
- Saída restrita ao contrato `ClassificacaoSentimento` com no máximo 1 tentativa de correção (mesmo ciclo
  do RF14, `nlp._gerar_com_correcao`);
- Regras locais depois do esquema: ID tem de bater com a entrada, a justificativa não pode descrever o autor
  (personalidade, emoção, diagnóstico...) e não pode vazar segredo; casos incertos ficam explícitos;
- `confianca_declarada` é estimativa NÃO calibrada do modelo: é exibida como tal e nunca entra em total;
- Totais e proporções são contados por código (`metrics.agregar_registros_deterministico`), com filtro,
  remoção de duplicatas e denominador visível, sem divisão por zero.

Uso via CLI:
  python -m src.sentiment classificar [--provedor openai] [--modelo gpt-4.1-mini] [--dry-run]
  python -m src.sentiment agregar [--execucao resultados/sentimentos/<exec>] [--canal "Presencial"]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src import audit, guardrails, llm_client, metrics, nlp, prompts, schemas

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
ARQ_AVALIACOES = RAIZ / "dados" / "avaliacoes" / "avaliacoes.csv"
ARQ_GABARITO = RAIZ / "dados" / "gabaritos" / "d2" / "sentimentos.json"
POLARIDADES = ("positiva", "negativa", "neutra", "indeterminada")
SEM_ROTULO = "sem_classificacao_valida"

AVISO_CONFIANCA = ("Confiança declarada pelo modelo: estimativa NÃO calibrada; não é probabilidade de acerto "
                   "nem medida do sentimento da população.")

# Justificativa que descreve a pessoa, e não o texto, viola o RF22 (Seção 16 do enunciado).
_RE_INFERENCIA_AUTOR = re.compile(
    r"\b(?:personalidade|diagn[óo]stic\w*|ansios\w*|deprimid\w*|depress\w*|estressad\w*|nervos\w*|"
    r"emocionalmente|(?:o|a)\s+(?:autor|autora|pessoa|cidad[ãa]o?|aluno|aluna)\s+(?:é|parece|est[áa]|sente))",
    re.I,
)


def _cfg(provedor: str | None = None, modelo: str | None = None) -> dict[str, Any]:
    cfg = dict(CONFIG["sentimentos"])
    if provedor:
        cfg["provedor"] = provedor
    if modelo:
        cfg["modelo"] = modelo
    return cfg


# ---------------------------------------------------------------- Entrada

def carregar_avaliacoes(caminho: Path | None = None) -> list[schemas.AvaliacaoAtendimento]:
    """Lê o CSV de avaliações e valida cada linha no contrato `AvaliacaoAtendimento`."""
    with open(caminho or ARQ_AVALIACOES, encoding="utf-8", newline="") as f:
        return [schemas.AvaliacaoAtendimento.model_validate(linha) for linha in csv.DictReader(f)]


def carregar_gabarito(caminho: Path | None = None) -> dict[str, dict[str, Any]]:
    dados = json.loads((caminho or ARQ_GABARITO).read_text(encoding="utf-8"))
    return {r["id_avaliacao"]: r for r in dados["rotulos"]}


# ---------------------------------------------------------------- Classificação

@dataclass
class ResultadoSentimento:
    id_avaliacao: str
    estado: str  # valida | bloqueada_negocio | rejeitada_esquema | erro_provedor | dry_run
    classificacao: dict[str, Any] | None = None
    alertas: list[str] = field(default_factory=list)
    erros: list[dict[str, Any]] = field(default_factory=list)
    tentativas: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def polaridade(self) -> str:
        return self.classificacao["polaridade"] if self.estado == "valida" and self.classificacao else SEM_ROTULO

    @property
    def incerto(self) -> bool:
        """Caso incerto = vai para leitura humana: sem rótulo válido, indeterminada, revisão, confiança baixa ou alerta."""
        c = self.classificacao or {}
        return (self.estado != "valida" or c.get("polaridade") == "indeterminada" or bool(c.get("requer_revisao"))
                or c.get("confianca_declarada") == "baixa" or bool(self.alertas))

    def para_json(self) -> dict[str, Any]:
        return {**asdict(self), "polaridade_final": self.polaridade, "incerto": self.incerto}


def validar_classificacao(texto_json: str, id_esperado: str) -> tuple[str, schemas.ClassificacaoSentimento | None, list[dict]]:
    """Camadas 1 e 2 (JSON e contrato) + camada 3 (regras locais). Só a 2 dá direito à correção."""
    res = schemas.validar_texto_json(schemas.ClassificacaoSentimento, texto_json)
    if not res.valido:
        return "rejeitada_esquema", None, [
            {**e, "camada": "sintatica" if e["categoria"] == "json_invalido" else "esquema"} for e in res.erros]
    obj: schemas.ClassificacaoSentimento = res.objeto  # type: ignore[assignment]
    erros: list[dict[str, str]] = []
    if obj.id_avaliacao.strip() != id_esperado:
        erros.append({"camada": "negocio", "campo": "id_avaliacao", "categoria": "id_divergente",
                      "detalhe": f"o modelo devolveu id '{obj.id_avaliacao[:20]}' para a avaliação {id_esperado}"})
    saida = guardrails.verificar_saida(obj.justificativa)
    if "vazamento_segredo" in saida.categorias:
        erros.append({"camada": "seguranca", "campo": "justificativa", "categoria": "vazamento_segredo",
                      "detalhe": "a justificativa contém credencial ou marcador interno"})
    if erros:
        return "bloqueada_negocio", obj, erros
    return "valida", obj, []


def classificar_avaliacao(
    avaliacao: schemas.AvaliacaoAtendimento,
    cfg: dict[str, Any] | None = None,
    *,
    chamar: Callable[..., dict[str, Any]] = llm_client.chamar_chat,
    dry_run: bool = False,
    caminho_log: Path | None = None,
) -> ResultadoSentimento:
    """Classifica uma avaliação. Nunca levanta erro do provedor: devolve estado `erro_provedor`."""
    cfg = cfg or _cfg()
    msgs, meta = prompts.montar_mensagens_sentimento(avaliacao.id_avaliacao, avaliacao.texto)
    params, json_mode = nlp.parametros_saida(cfg["modo_saida"], cfg["parametros"],
                                             schemas.ClassificacaoSentimento, "classificacao_sentimento")
    meta.update({
        "versao_contrato": f"classificacao_sentimento-v{schemas.ClassificacaoSentimento.VERSAO}",
        "provedor": cfg["provedor"], "modelo": cfg["modelo"], "modo_saida": cfg["modo_saida"],
        "arquivo_origem": f"dados/avaliacoes/avaliacoes.csv#{avaliacao.id_avaliacao}",
    })
    if dry_run:
        return ResultadoSentimento(avaliacao.id_avaliacao, "dry_run", meta=meta)

    estado, objeto, erros, tentativas = nlp._gerar_com_correcao(
        msgs, lambda s: validar_classificacao(s, avaliacao.id_avaliacao), cfg, params, json_mode, chamar)
    classif = objeto.model_dump() if objeto else None
    alertas: list[str] = []
    if classif and _RE_INFERENCIA_AUTOR.search(classif["justificativa"]):
        alertas.append("inferencia_sobre_autor: a justificativa descreve a pessoa, não o texto; revisão obrigatória")
        classif["requer_revisao"] = True
    resultado = ResultadoSentimento(avaliacao.id_avaliacao, estado, classif, alertas, erros, tentativas, meta)
    nlp._auditar("sentimento", avaliacao.id_avaliacao,
                 f"{estado} -> {resultado.polaridade}{' (incerto)' if resultado.incerto else ''}",
                 erros, tentativas, meta, cfg, caminho_log)
    return resultado


# ---------------------------------------------------------------- Comparação com o gabarito

def comparar_com_gabarito(resultados: list[ResultadoSentimento], gabarito: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Confere rótulo e indicação de revisão contra o gabarito validado; denominadores sempre explícitos."""
    linhas = []
    for r in resultados:
        g = gabarito.get(r.id_avaliacao, {})
        rev_obtido = bool((r.classificacao or {}).get("requer_revisao"))
        linhas.append({
            "id_avaliacao": r.id_avaliacao, "grupo": g.get("grupo"),
            "esperado": g.get("polaridade_esperada"), "obtido": r.polaridade,
            "acerto": r.polaridade == g.get("polaridade_esperada"),
            "revisao_esperada": g.get("requer_revisao_esperado"), "revisao_obtida": rev_obtido,
            "incerto": r.incerto, "estado": r.estado,
            "confianca_declarada": (r.classificacao or {}).get("confianca_declarada"),
            "justificativa": (r.classificacao or {}).get("justificativa"),
            "alertas": r.alertas,
        })
    ambiguos = [x for x in linhas if x["revisao_esperada"]]
    return {
        "linhas": linhas,
        "acuracia_polaridade": metrics.razao_segura(sum(x["acerto"] for x in linhas), len(linhas)),
        "concordancia_revisao": metrics.razao_segura(
            sum(x["revisao_obtida"] == x["revisao_esperada"] for x in linhas), len(linhas)),
        "ambiguos_sinalizados": metrics.razao_segura(sum(x["incerto"] for x in ambiguos), len(ambiguos)),
        "saidas_validas": metrics.razao_segura(sum(x["estado"] == "valida" for x in linhas), len(linhas)),
        "erros": [x["id_avaliacao"] for x in linhas if not x["acerto"]],
    }


# ---------------------------------------------------------------- Agregação por código (painel, T13)

def montar_registros(resultados: list[dict[str, Any]], avaliacoes: list[schemas.AvaliacaoAtendimento]) -> list[dict[str, Any]]:
    """Junta o rótulo de cada avaliação com seus metadados (data, canal, categoria) para agregar."""
    por_id = {a.id_avaliacao: a for a in avaliacoes}
    registros = []
    for r in resultados:
        a = por_id.get(r["id_avaliacao"])
        registros.append({
            "id_avaliacao": r["id_avaliacao"],
            "polaridade": r.get("polaridade_final", SEM_ROTULO),
            "incerto": r.get("incerto", True),
            "confianca_declarada": (r.get("classificacao") or {}).get("confianca_declarada"),
            "canal": a.canal if a else None,
            "categoria_atendimento": a.categoria_atendimento if a else None,
            "data": a.data if a else None,
        })
    return registros


def agregar(registros: list[dict[str, Any]], filtros: dict[str, Any] | None = None) -> dict[str, Any]:
    """Totais por polaridade, canal e categoria, contados por código; vazio devolve denominador 0, sem erro."""
    base = metrics.agregar_registros_deterministico(registros, chave_id="id_avaliacao", chave_rotulo="polaridade",
                                                    filtros=filtros)
    vistos: set[str] = set()
    unicos = []
    for r in registros:
        if r["id_avaliacao"] not in vistos:
            vistos.add(r["id_avaliacao"])
            unicos.append(r)
    filtrados = [r for r in unicos
                 if all(v in (None, "", "todos") or r.get(k) == v for k, v in (filtros or {}).items())]
    total = len(filtrados)

    def cruzar(campo: str) -> dict[str, dict[str, int]]:
        tabela: dict[str, dict[str, int]] = {}
        for r in filtrados:
            linha = tabela.setdefault(str(r.get(campo) or "não informado"), {p: 0 for p in (*POLARIDADES, SEM_ROTULO)})
            linha[r["polaridade"]] = linha.get(r["polaridade"], 0) + 1
        return dict(sorted(tabela.items()))

    return {
        **base,
        "contagens": {p: base["contagens"].get(p, 0) for p in (*POLARIDADES, SEM_ROTULO)},
        "incertos": metrics.razao_segura(sum(1 for r in filtrados if r["incerto"]), total),
        "por_canal": cruzar("canal"),
        "por_categoria": cruzar("categoria_atendimento"),
        "confianca_declarada_estimativa": {n: sum(1 for r in filtrados if r.get("confianca_declarada") == n)
                                           for n in ("alta", "media", "baixa")},
        "aviso_confianca": AVISO_CONFIANCA,
        "fonte_totais": "contagem determinística por código a partir dos rótulos; o modelo não calcula totais",
        "filtros": {k: v for k, v in (filtros or {}).items() if v not in (None, "", "todos")},
    }


# ---------------------------------------------------------------- Execução em lote

def ultima_execucao() -> Path | None:
    raiz = RAIZ / CONFIG["caminhos"]["sentimentos"]
    execs = sorted(p for p in raiz.glob("2*") if (p / "classificacoes.json").is_file()) if raiz.is_dir() else []
    return execs[-1] if execs else None


def carregar_execucao(diretorio: Path | None = None) -> dict[str, Any] | None:
    d = diretorio or ultima_execucao()
    if d is None or not (d / "classificacoes.json").is_file():
        return None
    return json.loads((d / "classificacoes.json").read_text(encoding="utf-8"))


def executar_lote(
    *,
    provedor: str | None = None,
    modelo: str | None = None,
    dry_run: bool = False,
    chamar: Callable[..., dict[str, Any]] = llm_client.chamar_chat,
    destino: Path | None = None,
    caminho_log: Path | None = None,
) -> Path:
    """Classifica as 12 avaliações, compara com o gabarito e grava JSON + matriz em `resultados/sentimentos/`."""
    cfg = _cfg(provedor, modelo)
    avaliacoes = carregar_avaliacoes()
    gabarito = carregar_gabarito()
    orcamento = llm_client.ControladorOrcamento(max_chamadas=cfg.get("max_chamadas"), max_tokens_total=None)
    resultados: list[ResultadoSentimento] = []
    for i, av in enumerate(avaliacoes):
        if i and not dry_run and chamar is llm_client.chamar_chat:
            time.sleep(float(cfg.get("pausa_entre_chamadas_s", 0)))
        try:
            orcamento.verificar_disponibilidade()
        except llm_client.ErroProvedor as exc:
            resultados.append(ResultadoSentimento(av.id_avaliacao, "erro_provedor", erros=[
                {"camada": "recursos", "campo": "(execução)", "categoria": exc.codigo_erro, "detalhe": str(exc)}]))
            continue
        r = classificar_avaliacao(av, cfg, chamar=chamar, dry_run=dry_run, caminho_log=caminho_log)
        orcamento.registrar_chamada(sum((t.get("tokens_entrada") or 0) + (t.get("tokens_saida") or 0) for t in r.tentativas))
        orcamento.chamadas_realizadas += max(0, len(r.tentativas) - 1)
        resultados.append(r)
        print(f"  {av.id_avaliacao}: {r.estado} -> {r.polaridade}{' (incerto)' if r.incerto else ''}")

    comparacao = comparar_com_gabarito(resultados, gabarito)
    saida_json = [r.para_json() for r in resultados]
    agregado = agregar(montar_registros(saida_json, avaliacoes))
    uso = [t for r in resultados for t in r.tentativas]
    pacote = {
        "gerado_em": audit.agora_iso(), "provedor": cfg["provedor"], "modelo": cfg["modelo"],
        "simulado": cfg["provedor"] == "simulado", "dry_run": dry_run,
        "versao_prompt": prompts.VERSOES["sentimento"][1],
        "versao_contrato": f"classificacao_sentimento-v{schemas.ClassificacaoSentimento.VERSAO}",
        "gabarito": "dados/gabaritos/d2/sentimentos.json (validado e congelado antes das chamadas)",
        "uso": {"chamadas": len(uso), "tokens_entrada": sum(t.get("tokens_entrada") or 0 for t in uso),
                "tokens_saida": sum(t.get("tokens_saida") or 0 for t in uso),
                "latencia_s": round(sum(t.get("latencia_s") or 0 for t in uso), 2),
                "custo_usd": (round(sum(t["custo_usd"] for t in uso), 6)
                              if uso and all(t.get("custo_usd") is not None for t in uso) else None),
                "orcamento": orcamento.resumo()},
        "resultados": saida_json, "comparacao": comparacao, "agregado": agregado,
    }
    pasta = destino or (RAIZ / CONFIG["caminhos"]["sentimentos"] / datetime.now().strftime("%Y%m%d-%H%M%S"))
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "classificacoes.json").write_text(json.dumps(pacote, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8", newline="\n")
    (pasta / "matriz_rf22.md").write_text(_renderizar_matriz(pacote), encoding="utf-8", newline="\n")
    return pasta


def _renderizar_matriz(p: dict[str, Any]) -> str:
    c = p["comparacao"]
    md = [
        "# RF22 — Classificação de sentimentos (12 avaliações fictícias)", "",
        f"- Execução: {p['gerado_em']} · `{p['provedor']}/{p['modelo']}` · prompt `{p['versao_prompt']}` · "
        f"contrato `{p['versao_contrato']}`{' · **SIMULADO**' if p['simulado'] else ''}{' · **DRY-RUN**' if p['dry_run'] else ''}",
        f"- Gabarito: {p['gabarito']}",
        f"- Uso: {p['uso']['chamadas']} chamadas, {p['uso']['tokens_entrada']}+{p['uso']['tokens_saida']} tokens, "
        f"{p['uso']['latencia_s']} s; custo: {p['uso']['custo_usd'] if p['uso']['custo_usd'] is not None else 'tarifa não cadastrada'}",
        "",
        "| Métrica | Resultado |", "|---|---|",
        f"| Saídas válidas no contrato | {c['saidas_validas']['formatado']} |",
        f"| **Acurácia de polaridade** | **{c['acuracia_polaridade']['formatado']}** |",
        f"| Concordância da indicação de revisão | {c['concordancia_revisao']['formatado']} |",
        f"| Ambíguos/mistos sinalizados como incertos | {c['ambiguos_sinalizados']['formatado']} |",
        f"| Erros de polaridade | {', '.join(c['erros']) or 'nenhum'} |",
        "", f"> {AVISO_CONFIANCA}", "",
        "| ID | Grupo | Esperado | Obtido | Acerto | Revisão esp./obt. | Incerto | Confiança (estimativa) | Justificativa do modelo |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for x in c["linhas"]:
        just = (x["justificativa"] or "—").replace("|", "/")
        md.append(f"| {x['id_avaliacao']} | {x['grupo']} | {x['esperado']} | {x['obtido']} | {'✔' if x['acerto'] else '✘'} | "
                  f"{'sim' if x['revisao_esperada'] else 'não'}/{'sim' if x['revisao_obtida'] else 'não'} | "
                  f"{'**sim**' if x['incerto'] else 'não'} | {x['confianca_declarada'] or '—'} | {just} |")
    a = p["agregado"]
    md += ["", "## Agregação por código", "",
           f"Recebidos: {a['total_recebidos']} · duplicatas ignoradas: {a['duplicatas_ignoradas']} · "
           f"denominador: {a['denominador_filtrado']} · incertos: {a['incertos']['formatado']}", "",
           "| Polaridade | Contagem | Proporção |", "|---|---|---|"]
    md += [f"| {k} | {v} | {metrics.razao_segura(v, a['denominador_filtrado'])['formatado']} |" for k, v in a["contagens"].items()]
    return "\n".join(md) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classificação de sentimentos e agregação (RF22).")
    sub = parser.add_subparsers(dest="comando", required=True)
    c = sub.add_parser("classificar", help="Classifica as 12 avaliações e compara com o gabarito.")
    c.add_argument("--provedor", choices=sorted(CONFIG["provedores"]))
    c.add_argument("--modelo")
    c.add_argument("--dry-run", action="store_true")
    a = sub.add_parser("agregar", help="Agrega por código a última execução (ou a indicada).")
    a.add_argument("--execucao")
    a.add_argument("--canal")
    a.add_argument("--categoria")
    a.add_argument("--polaridade")
    args = parser.parse_args(argv)

    if args.comando == "classificar":
        try:
            pasta = executar_lote(provedor=args.provedor, modelo=args.modelo, dry_run=args.dry_run)
        except llm_client.ErroProvedor as exc:
            print(f"Erro: {exc}")
            return 1
        print(f"Resultados salvos em: {pasta.relative_to(RAIZ)}")
        return 0
    pacote = carregar_execucao(RAIZ / args.execucao if args.execucao else None)
    if pacote is None:
        print("Nenhuma execução encontrada. Rode: python -m src.sentiment classificar")
        return 1
    filtros = {"canal": args.canal, "categoria_atendimento": args.categoria, "polaridade": args.polaridade}
    print(json.dumps(agregar(montar_registros(pacote["resultados"], carregar_avaliacoes()), filtros),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
