"""Registro estruturado, rastreabilidade, proteção de logs e relatório de auditoria (RF01, RF04, RF11, RF12, RF13).

Responsabilidade: Estudante 2.
Garante que cada execução relevante produza um registro reconstruível em JSONL sem expor
chaves de API ou dados pessoais brutos, registrando versões do ambiente, parâmetros, tempos,
custos, erros e decisões da revisão humana.
"""
from __future__ import annotations

import importlib.metadata
import json
import platform
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src import avaliacao, prompts
from src.llm_client import ocultar_segredos

RAIZ = prompts.RAIZ
DIR_LOGS_PADRAO = RAIZ / "resultados" / "logs"
ARQUIVO_LOG_PADRAO = DIR_LOGS_PADRAO / "execucoes.jsonl"
ARQUIVO_RELATORIO_PADRAO = DIR_LOGS_PADRAO / "relatorio_auditoria.md"

_CHAVES_PROIBIDAS = {
    "api_key",
    "apikey",
    "chave_api",
    "chave",
    "authorization",
    "secret",
    "password",
    "senha",
    "credencial",
    "groq_api_key",
    "gemini_api_key",
    "openai_api_key",
    "openrouter_api_key",
}

_BIBLIOTECAS_PRINCIPAIS = ("httpx", "python-dotenv")


def agora_iso() -> str:
    """Retorna data e hora atual em formato ISO 8601 com fuso horário local."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def gerar_id_execucao(prefixo: str = "exec") -> str:
    """Gera identificador único curto e rastreável para uma execução."""
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def coletar_ambiente() -> dict[str, Any]:
    """Registra as versões do Python e das principais bibliotecas instaladas (RF01)."""
    versoes_libs: dict[str, str] = {}
    for pacote in _BIBLIOTECAS_PRINCIPAIS:
        try:
            versoes_libs[pacote] = importlib.metadata.version(pacote)
        except importlib.metadata.PackageNotFoundError:
            versoes_libs[pacote] = "não instalado"
    return {
        "python": platform.python_version(),
        "sistema": f"{platform.system()} {platform.release()}",
        "bibliotecas": versoes_libs,
    }


def sanitizar_dados(dados: Any) -> Any:
    """Remove recursivamente qualquer chave de API ou credencial antes de gravar no disco (RF04, RF11)."""
    if isinstance(dados, dict):
        limpo: dict[str, Any] = {}
        for k, v in dados.items():
            chave_norm = str(k).strip().lower()
            if chave_norm in _CHAVES_PROIBIDAS:
                limpo[k] = "[CREDENCIAL_OCULTADA]"
            else:
                limpo[k] = sanitizar_dados(v)
        return limpo
    if isinstance(dados, list):
        return [sanitizar_dados(item) for item in dados]
    if isinstance(dados, tuple):
        return [sanitizar_dados(item) for item in dados]
    if isinstance(dados, str):
        return ocultar_segredos(dados)
    return dados


def criar_registro(
    *,
    id_execucao: str | None = None,
    caso_id: str,
    etapa: str,
    modalidade: str,
    arquivo_origem: str,
    provedor: str,
    modelo: str,
    parametros: dict[str, Any] | None = None,
    versao_prompt: str = "—",
    hash_prompt: str = "—",
    dados_minimizados: dict[str, int] | None = None,
    resposta_llm: dict[str, Any] | None = None,
    arquivo_saida: str | None = None,
    resumo_resultado: str | None = None,
    avaliacao_auto: dict[str, Any] | None = None,
    decisao_humana: str = "PENDENTE",
    revisor: str | None = None,
    justificativa_humana: str | None = None,
    erro: str | None = None,
) -> dict[str, Any]:
    """Monta um dicionário padronizado de auditoria de execução (RF11)."""
    resp = resposta_llm or {}
    erro_final = erro if erro is not None else resp.get("erro")
    resumo_av = None
    if avaliacao_auto:
        resumo_av = {
            "contagem": avaliacao_auto.get("contagem", {}),
            "decisao_sugerida": avaliacao_auto.get("decisao_sugerida"),
            "total_achados": len(avaliacao_auto.get("achados", [])),
        }

    registro = {
        "id_execucao": id_execucao or gerar_id_execucao(),
        "data_hora": agora_iso(),
        "caso_id": caso_id,
        "etapa": etapa,
        "modalidade": modalidade,
        "arquivo_origem": arquivo_origem,
        "provedor": provedor,
        "modelo": modelo,
        "parametros": parametros or {},
        "versao_prompt": versao_prompt,
        "hash_prompt": hash_prompt,
        "dados_minimizados": dados_minimizados or {},
        "latencia_s": resp.get("latencia_s"),
        "tokens_entrada": resp.get("tokens_entrada"),
        "tokens_saida": resp.get("tokens_saida"),
        "custo_usd": resp.get("custo_usd"),
        "tentativas": resp.get("tentativas"),
        "erro": erro_final,
        "arquivo_saida": arquivo_saida,
        "resumo_resultado": resumo_resultado,
        "avaliacao_automatica": resumo_av,
        "decisao_humana": decisao_humana,
        "revisor": revisor,
        "justificativa_humana": justificativa_humana,
        "ambiente": coletar_ambiente(),
    }
    return sanitizar_dados(registro)


def registrar_execucao(
    registro: dict[str, Any],
    caminho_log: Path | None = None,
) -> dict[str, Any]:
    """Sanitiza e grava o registro em formato JSONL no arquivo de auditoria (RF11)."""
    destino = Path(caminho_log) if caminho_log else ARQUIVO_LOG_PADRAO
    destino.parent.mkdir(parents=True, exist_ok=True)
    seguro = sanitizar_dados(registro)
    if "id_execucao" not in seguro or not seguro["id_execucao"]:
        seguro["id_execucao"] = gerar_id_execucao()
    if "data_hora" not in seguro or not seguro["data_hora"]:
        seguro["data_hora"] = agora_iso()
    if "ambiente" not in seguro:
        seguro["ambiente"] = coletar_ambiente()

    linha = ocultar_segredos(json.dumps(seguro, ensure_ascii=False))
    with open(destino, "a", encoding="utf-8") as f:
        f.write(linha + "\n")
    return json.loads(linha)


def ler_registros(caminho_log: Path | None = None) -> list[dict[str, Any]]:
    """Lê todos os registros estruturados gravados no arquivo JSONL."""
    origem = Path(caminho_log) if caminho_log else ARQUIVO_LOG_PADRAO
    if not origem.exists():
        return []
    registros: list[dict[str, Any]] = []
    for linha in origem.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            registros.append(json.loads(linha))
    return registros


def atualizar_decisao_humana(
    id_execucao: str,
    decisao: str,
    revisor: str,
    justificativa: str,
    arquivo_saida_final: str | None = None,
    caminho_log: Path | None = None,
) -> bool:
    """Atualiza um registro existente com a decisão humana final (RF11, RF13)."""
    alvo = Path(caminho_log) if caminho_log else ARQUIVO_LOG_PADRAO
    registros = ler_registros(alvo)
    atualizado = False
    for reg in registros:
        if reg.get("id_execucao") == id_execucao:
            reg["decisao_humana"] = ocultar_segredos(decisao)
            reg["revisor"] = ocultar_segredos(revisor)
            reg["justificativa_humana"] = ocultar_segredos(justificativa)
            reg["data_revisao_humana"] = agora_iso()
            if arquivo_saida_final:
                reg["arquivo_saida"] = arquivo_saida_final
            atualizado = True
    if atualizado:
        alvo.parent.mkdir(parents=True, exist_ok=True)
        texto = "\n".join(ocultar_segredos(json.dumps(sanitizar_dados(r), ensure_ascii=False)) for r in registros)
        alvo.write_text(texto + "\n", encoding="utf-8")
    return atualizado


def _normalizar_decisao_para_taxa(decisao: str | None) -> str | None:
    """Converte o rótulo humano para o código usado em `avaliacao.taxa_aprovacao`."""
    if not decisao:
        return None
    d = decisao.strip().lower()
    if d in ("aprovar", "aprovada", "aprovado"):
        return "aprovar"
    if d in ("corrigir", "corrigida", "corrigido", "correcao_manual", "correção manual"):
        return "correcao_manual"
    if d.startswith("rejeit") or "nova" in d:
        return "rejeitar_nova_geracao"
    return None


def gerar_relatorio_auditoria(
    caminho_log: Path | None = None,
    caminho_relatorio: Path | None = None,
) -> str:
    """Gera um relatório Markdown consolidado das execuções, custos e decisões humanas (RF11, RF13)."""
    origem = Path(caminho_log) if caminho_log else ARQUIVO_LOG_PADRAO
    destino = Path(caminho_relatorio) if caminho_relatorio else ARQUIVO_RELATORIO_PADRAO
    registros = ler_registros(origem)
    amb = coletar_ambiente()
    libs_fmt = ", ".join(f"`{k} {v}`" for k, v in amb["bibliotecas"].items())

    # Uma execução pode aparecer novamente quando a revisão humana é registrada. A tabela abaixo
    # preserva todo o histórico, mas os totais não podem cobrar a mesma chamada duas vezes.
    ultimos_por_execucao: dict[str, dict[str, Any]] = {}
    for indice, registro in enumerate(registros):
        identificador = str(registro.get("id_execucao") or f"linha-{indice}")
        ultimos_por_execucao[identificador] = registro
    registros_metricas = list(ultimos_por_execucao.values())

    latencias = [r["latencia_s"] for r in registros_metricas if isinstance(r.get("latencia_s"), (int, float))]
    lat_media = f"{sum(latencias) / len(latencias):.2f} s" if latencias else "—"
    tokens_totais = sum((r.get("tokens_entrada") or 0) + (r.get("tokens_saida") or 0) for r in registros_metricas)
    custos = [r["custo_usd"] for r in registros_metricas if isinstance(r.get("custo_usd"), (int, float))]
    custo_total = f"US$ {sum(custos):.6f}" if custos else "US$ 0.000000"
    erros_totais = sum(
        1 for r in registros_metricas if r.get("erro") and not str(r.get("erro")).startswith("dry-run")
    )

    # Taxa de aprovação considerando a última decisão humana de minuta por caso
    ultimas_minutas_por_caso: dict[str, dict[str, Any]] = {}
    for r in registros:
        if r.get("etapa") == "minuta":
            ultimas_minutas_por_caso[r.get("caso_id", "")] = r
    decisoes_cod = [
        _normalizar_decisao_para_taxa(r.get("decisao_humana"))
        for r in ultimas_minutas_por_caso.values()
    ]
    decisoes_validas = [d for d in decisoes_cod if d is not None]
    taxa = avaliacao.taxa_aprovacao(decisoes_validas) if decisoes_validas else 0.0

    linhas = [
        "# Relatório de Auditoria e Rastreabilidade (RF11, RF13)",
        "",
        f"- **Gerado em:** `{agora_iso()}`",
        f"- **Python:** `{amb['python']}` · **Sistema:** `{amb['sistema']}`",
        f"- **Bibliotecas principais:** {libs_fmt}",
        f"- **Arquivo de log estruturado:** `{origem.name}`",
        "",
        "## 1. Resumo de Execuções e Custos",
        "",
        f"- **Total de eventos registrados:** {len(registros)}",
        f"- **Execuções distintas usadas nas métricas:** {len(registros_metricas)}",
        f"- **Latência média por chamada:** {lat_media}",
        f"- **Tokens totais processados (entrada + saída):** {tokens_totais}",
        f"- **Custo total estimado (sem duplicar atualizações de revisão):** {custo_total}",
        f"- **Falhas de API tratadas:** {erros_totais}",
        f"- **Casos com minuta avaliada:** {len(decisoes_validas)} · **Taxa de aprovação direta (RF13):** {taxa:.0%}",
        "",
        "## 2. Trilha de Rastreabilidade por Execução",
        "",
        "| ID Execução | Data/Hora | Caso | Etapa | Modalidade | Modelo | Prompt | Tempo (s) | Custo (USD) | Decisão Humana | Saída |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for r in registros:
        tempo = f"{r['latencia_s']:.2f}" if isinstance(r.get("latencia_s"), (int, float)) else "—"
        custo = f"{r['custo_usd']:.6f}" if isinstance(r.get("custo_usd"), (int, float)) else "—"
        modelo_curto = f"{r.get('provedor', '')}/{r.get('modelo', '')}".strip("/")
        saida = r.get("arquivo_saida") or ("erro: " + str(r.get("erro"))[:40] if r.get("erro") else "—")
        linhas.append(
            f"| `{r.get('id_execucao')}` | `{r.get('data_hora')}` | `{r.get('caso_id')}` | "
            f"`{r.get('etapa')}` | {r.get('modalidade')} | `{modelo_curto}` | "
            f"`{r.get('versao_prompt')}` | {tempo} | {custo} | **{r.get('decisao_humana', 'PENDENTE')}** | `{saida}` |"
        )

    linhas += [
        "",
        "## 3. Decisões da Revisão Humana (RF13)",
        "",
        "| Caso | ID Execução | Decisão Sugerida (Auto) | Decisão Humana Final | Revisor | Justificativa |",
        "|---|---|---|---|---|---|",
    ]
    for caso_id, r in ultimas_minutas_por_caso.items():
        sug = (r.get("avaliacao_automatica") or {}).get("decisao_sugerida") or "—"
        linhas.append(
            f"| `{caso_id}` | `{r.get('id_execucao')}` | `{sug}` | "
            f"**{r.get('decisao_humana', 'PENDENTE')}** | {r.get('revisor') or '—'} | "
            f"{r.get('justificativa_humana') or '—'} |"
        )

    linhas += [
        "",
        "> **Garantia de Segurança e Privacidade (RF04, RF11, RF12):** Nenhuma chave de API ou credencial "
        "é armazenada nos logs. Nos fluxos de texto e visão, os dados pessoais desnecessários são minimizados "
        "ou mascarados antes da chamada; no fluxo de áudio, a gravação original é enviada ao provedor somente "
        "para transcrição e essa limitação está registrada no relatório técnico.",
        "",
    ]

    conteudo = ocultar_segredos("\n".join(linhas))
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(conteudo, encoding="utf-8")
    return conteudo
