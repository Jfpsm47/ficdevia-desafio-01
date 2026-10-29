"""Compreensão das solicitações (Desafio 02): extração estruturada e validação em três camadas (RF14).

Responsabilidade: Estudante 1. Fluxo de `extrair`:
1. minimiza dados pessoais e monta as mensagens (prompt extracao-v2.0, conteúdo delimitado);
2. pede saída restrita pelo JSON Schema do contrato (modo estrito) ou apenas JSON (`json_object`);
3. valida as camadas 1 (sintática) e 2 (contrato); se falhar, faz no máximo UMA tentativa de correção e
   rejeita a saída que continuar inválida;
4. aplica as regras de negócio (camada 3) contra o texto original;
5. decide o encaminhamento: só `minuta_pendente_de_aprovacao` libera a geração da minuta, que continua
   sujeita à aprovação humana.

`validar_extracao` (camadas 1 a 3, sem chamar o provedor) é o ponto de integração com o fluxo principal.

Uso:
  python -m src.nlp extrair --todos [--modo json_schema_estrito|json_object] [--dry-run]
  python -m src.nlp extrair --caso caso05_texto_incompleto
  python -m src.nlp comparar-json
  python -m src.nlp fichas --todos --reusar-extracao resultados/extracao/<execução>   # RF15
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from src import audit, llm_client, prompts, schemas
from src.dados_ficticios import DIR_GABARITOS, normalizar, relativo
from src.llm_client import ErroProvedor

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]
CAMPOS_OBRIGATORIOS = ("protocolo", "data_solicitacao", "solicitante", "pedido")
CAMPOS_CURTOS = ("protocolo", "data_solicitacao", "canal", "solicitante", "curso")

LIBERA_MINUTA = "minuta_pendente_de_aprovacao"
REVISAO_ANTES = "revisao_humana_antes_da_minuta"
BLOQUEADA = "bloqueada_revisao_humana"


@dataclass
class ResultadoExtracao:
    """Resultado de uma extração: estado da validação, encaminhamento e evidências de cada tentativa."""
    caso_id: str
    estado: str  # valida | bloqueada_negocio | rejeitada_esquema | erro_provedor | dry_run
    encaminhamento: str
    extracao: dict[str, Any] | None = None
    erros: list[dict[str, Any]] = field(default_factory=list)
    tentativas: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def libera_minuta(self) -> bool:
        return self.encaminhamento == LIBERA_MINUTA

    def para_json(self) -> dict[str, Any]:
        return {**asdict(self), "libera_minuta": self.libera_minuta}


# ---------------------------------------------------------------- Camada 3: regras de negócio

def _formas_data(d: date) -> list[str]:
    """Formas em que uma data pode aparecer no original (numérica ou por extenso, como em transcrições)."""
    mes = MESES[d.month - 1]
    return [f"{d:%d/%m/%Y}", f"{d.day}/{d.month}/{d.year}", f"{d.day} de {mes} de {d.year}",
            f"{d:%d} de {mes} de {d.year}"]


def _presente(valor: str, textos: tuple[str, ...]) -> bool:
    alvo = normalizar(valor)
    return bool(alvo) and any(alvo in normalizar(t) for t in textos if t)


def _erro_negocio(regra: str, campo: str, detalhe: str) -> dict[str, str]:
    return {"camada": "negocio", "campo": campo, "categoria": regra, "detalhe": detalhe}


def requer_revisao_pela_regra(extracao: schemas.SolicitacaoExtraida) -> bool:
    """Mesma regra do prompt extracao-v2.0 e dos gabaritos validados."""
    return (any(getattr(extracao, c) is None for c in CAMPOS_OBRIGATORIOS)
            or extracao.categoria == "revisao" or bool(extracao.alertas_seguranca))


def regras_negocio(extracao: schemas.SolicitacaoExtraida, texto_original: str, texto_enviado: str = "",
                   hoje: date | None = None) -> list[dict[str, str]]:
    """Camada 3: o que o esquema não consegue garantir (datas, coerência com o original, dados pessoais).

    Os detalhes citam campo e motivo, nunca o valor, porque o registro de erro não pode vazar dado pessoal.
    """
    hoje = hoje or date.today()
    textos = (texto_original, texto_enviado)
    erros: list[dict[str, str]] = []

    if extracao.data_solicitacao is not None:
        try:
            d = datetime.strptime(extracao.data_solicitacao, "%d/%m/%Y").date()
        except ValueError:
            erros.append(_erro_negocio("data_inexistente", "data_solicitacao", "a data não existe no calendário"))
        else:
            if d > hoje:
                erros.append(_erro_negocio("data_futura", "data_solicitacao", "a data é posterior à data de hoje"))
            if not any(_presente(forma, textos) for forma in _formas_data(d)):
                erros.append(_erro_negocio("valor_ausente_no_original", "data_solicitacao",
                                           "a data não aparece no texto original"))

    for campo in ("protocolo", "solicitante", "canal", "curso"):
        valor = getattr(extracao, campo)
        if valor is None:
            continue
        if campo == "curso":
            valor = re.sub(r"^curso\s+(de\s+)?", "", valor, flags=re.I)
        if not _presente(valor, textos):
            erros.append(_erro_negocio("valor_ausente_no_original", campo, "o valor não aparece no texto original"))

    for i, ent in enumerate(extracao.entidades):
        if not _presente(ent.evidencia, textos):
            erros.append(_erro_negocio("evidencia_sem_suporte", f"entidades.{i}.evidencia",
                                       "o trecho citado não aparece no texto original"))
        elif ent.origem == "literal" and ent.tipo != "data" and not _presente(ent.valor, textos):
            erros.append(_erro_negocio("entidade_literal_sem_suporte", f"entidades.{i}.valor",
                                       "entidade marcada como literal, mas o valor não está no texto"))

    if requer_revisao_pela_regra(extracao) and not extracao.requer_revisao:
        erros.append(_erro_negocio("requer_revisao_incoerente", "requer_revisao",
                                   "há campo obrigatório ausente, categoria 'revisao' ou alerta, mas requer_revisao=false"))

    valores = json.dumps(extracao.model_dump(exclude={"dados_pessoais_detectados"}), ensure_ascii=False)
    _, detectados = prompts.minimizar(valores)
    if detectados:
        erros.append(_erro_negocio("dado_pessoal_na_extracao", "(extração)",
                                   f"a extração reproduz dado pessoal: {', '.join(sorted(detectados))}"))
    return erros


def decidir_encaminhamento(estado: str, extracao: schemas.SolicitacaoExtraida | None) -> str:
    if estado != "valida" or extracao is None:
        return BLOQUEADA
    if extracao.categoria == "revisao" or extracao.alertas_seguranca:
        return REVISAO_ANTES
    return LIBERA_MINUTA


def validar_extracao(texto_json: str, texto_original: str, texto_enviado: str = "",
                     hoje: date | None = None) -> tuple[str, str, schemas.SolicitacaoExtraida | None, list[dict]]:
    """Camadas 1, 2 e 3 sobre uma saída já recebida. Retorna (estado, encaminhamento, objeto, erros).

    Ponto de integração (decisão 3-B): o fluxo principal só gera a minuta se o encaminhamento for
    `minuta_pendente_de_aprovacao`.
    """
    res = schemas.validar_texto_json(schemas.SolicitacaoExtraida, texto_json)
    if not res.valido:
        erros = [{**e, "camada": "sintatica" if e["categoria"] == "json_invalido" else "esquema"} for e in res.erros]
        return "rejeitada_esquema", BLOQUEADA, None, erros
    erros = regras_negocio(res.objeto, texto_original, texto_enviado, hoje)
    estado = "bloqueada_negocio" if erros else "valida"
    return estado, decidir_encaminhamento(estado, res.objeto), res.objeto, erros


def para_exibicao(extracao: dict[str, Any]) -> dict[str, Any]:
    """Cópia para a interface: null vira "não localizado" (RF14). O JSON persistido mantém null."""
    return {k: prompts.NAO_LOCALIZADO if v is None else v for k, v in extracao.items()}


# ---------------------------------------------------------------- Chamada ao modelo

def parametros_saida(modo: str, parametros: dict[str, Any],
                     contrato: type[schemas.Contrato] = schemas.SolicitacaoExtraida,
                     nome: str = "solicitacao_extraida") -> tuple[dict[str, Any], bool]:
    """Devolve (parametros, json_mode). O esquema estrito vai em `response_format`, sem alterar o cliente."""
    params = dict(parametros)
    if modo == "json_schema_estrito":
        params["response_format"] = {"type": "json_schema", "json_schema": {
            "name": nome, "strict": True, "schema": contrato.model_json_schema()}}
        return params, False
    if modo == "json_object":
        return params, True
    raise ValueError(f"modo de saída desconhecido: {modo}")


def erros_do_modo_estrito(exc: ErroProvedor) -> list[dict[str, str]] | None:
    """Converte a recusa do modo estrito (HTTP 400) em erro de esquema; devolve None para outras falhas.

    No Groq, o modo estrito valida a saída no servidor depois de gerá-la: uma saída fora do esquema volta
    como HTTP 400, e não como JSON inválido. Por isso essa recusa conta como camada 2 e dá direito à única
    tentativa de correção. Só o caminho e a propriedade são aproveitados, nunca o texto gerado.
    """
    mensagem = str(exc)
    if exc.status_code != 400 or "does not match the expected schema" not in mensagem:
        return None
    m = re.search(r"'(/[^']*)' does not validate with \S+: missing properties: '(\w+)'", mensagem)
    if m:
        caminho = ".".join(p for p in m.group(1).split("/") if p)
        campo, categoria = (f"{caminho}.{m.group(2)}" if caminho else m.group(2)), "campo_ausente"
    else:
        campo, categoria = "(raiz)", "esquema_estrito_provedor"
    return [{"camada": "esquema", "campo": campo, "categoria": categoria,
             "detalhe": "saída recusada pelo modo estrito do provedor"}]


def _somar_uso(tentativas: list[dict[str, Any]]) -> dict[str, Any]:
    def soma(chave):
        valores = [t[chave] for t in tentativas if t.get(chave) is not None]
        return round(sum(valores), 6) if valores else None
    return {"latencia_s": soma("latencia_s"), "tokens_entrada": soma("tokens_entrada"),
            "tokens_saida": soma("tokens_saida"), "custo_usd": soma("custo_usd"), "tentativas": len(tentativas)}


def extrair(texto: str, arquivo_origem: str, caso_id: str, cfg: dict[str, Any] | None = None, *,
            modo: str | None = None, chamar: Callable[..., dict[str, Any]] = llm_client.chamar_chat,
            dry_run: bool = False, hoje: date | None = None, caminho_log: Path | None = None) -> ResultadoExtracao:
    """Extrai e valida uma solicitação. Nunca levanta erro do provedor: devolve estado `erro_provedor`."""
    cfg = cfg or CONFIG["extracao_estruturada"]
    modo = modo or cfg["modo_saida"]
    msgs, meta = prompts.montar_mensagens_extracao_v2(texto, arquivo_origem)
    texto_enviado = meta.pop("texto_enviado")
    params, json_mode = parametros_saida(modo, cfg["parametros"])
    meta.update({
        "versao_contrato": f"solicitacao_extraida-v{schemas.SolicitacaoExtraida.VERSAO}",
        "versao_prompt_correcao": prompts.VERSOES["correcao_esquema"][1],
        "provedor": cfg["provedor"], "modelo": cfg["modelo"], "modo_saida": modo,
        "arquivo_origem": arquivo_origem,
        "sha256_origem": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "texto_enviado": texto_enviado,
    })
    if dry_run:
        return ResultadoExtracao(caso_id, "dry_run", BLOQUEADA, meta=meta)

    def validar(saida: str):
        estado_v, _, objeto_v, erros_v = validar_extracao(saida, texto, texto_enviado, hoje)
        return estado_v, objeto_v, erros_v

    estado, objeto, erros, tentativas = _gerar_com_correcao(msgs, validar, cfg, params, json_mode, chamar)
    resultado = ResultadoExtracao(caso_id, estado, decidir_encaminhamento(estado, objeto),
                                  objeto.model_dump() if objeto else None, erros, tentativas, meta)
    _auditar("extracao_estruturada", caso_id, f"{resultado.estado} -> {resultado.encaminhamento}",
             erros, tentativas, meta, cfg, caminho_log)
    return resultado


def _gerar_com_correcao(msgs: list[dict[str, str]], validar: Callable[[str], tuple[str, Any, list[dict]]],
                        cfg: dict[str, Any], params: dict[str, Any], json_mode: bool,
                        chamar: Callable[..., dict[str, Any]]) -> tuple[str, Any, list[dict], list[dict]]:
    """Gera e valida com no máximo uma tentativa de correção. Devolve (estado, objeto, erros, tentativas).

    `validar(saida)` devolve (estado, objeto, erros); só o estado `rejeitada_esquema` gera nova tentativa.
    """
    perfil = CONFIG["provedores"][cfg["provedor"]]
    conversa = list(msgs)
    tentativas: list[dict[str, Any]] = []
    erros: list[dict[str, Any]] = []
    estado, objeto = "rejeitada_esquema", None
    for n in range(1, 2 + cfg.get("max_tentativas_correcao", 1)):
        try:
            resp = chamar(perfil, cfg["modelo"], conversa, params, timeout_s=cfg["timeout_s"],
                          tentativas=cfg["tentativas_transitorias"], json_mode=json_mode,
                          precos=CONFIG.get("precos_usd_por_milhao_tokens"))
        except ErroProvedor as exc:
            erros_estrito = erros_do_modo_estrito(exc)
            if erros_estrito is None:
                estado = "erro_provedor"
                erros = [{"camada": "provedor", "campo": "(chamada)", "categoria": exc.codigo_erro,
                          "detalhe": llm_client.ocultar_segredos(str(exc))}]
                break
            estado, objeto, erros = "rejeitada_esquema", None, erros_estrito
            tentativas.append({"numero": n, "texto_bruto": "", "valida_no_esquema": False, "erros": erros,
                               "recusada_pelo_provedor": True})
            conversa += [{"role": "user", "content": prompts.mensagem_correcao_esquema(erros)}]
            continue
        estado, objeto, erros = validar(resp.get("texto", ""))
        tentativas.append({"numero": n, "texto_bruto": resp.get("texto", ""),
                           "valida_no_esquema": estado != "rejeitada_esquema", "erros": erros,
                           **{k: resp.get(k) for k in ("latencia_s", "tokens_entrada", "tokens_saida", "custo_usd")}})
        if estado != "rejeitada_esquema":
            break
        conversa += [{"role": "assistant", "content": resp.get("texto", "")},
                     {"role": "user", "content": prompts.mensagem_correcao_esquema(erros)}]
    return estado, objeto, erros, tentativas


def _auditar(etapa: str, caso_id: str, resumo_resultado: str, erros: list[dict], tentativas: list[dict],
             meta: dict[str, Any], cfg: dict[str, Any], caminho_log: Path | None) -> None:
    """Registra a execução no log de auditoria (RF21), sem o texto da solicitação."""
    registro = audit.criar_registro(
        caso_id=caso_id, etapa=etapa, modalidade="texto",
        arquivo_origem=meta["arquivo_origem"], provedor=cfg["provedor"], modelo=cfg["modelo"],
        parametros={**cfg["parametros"], "modo_saida": meta["modo_saida"]},
        versao_prompt=meta["versao_prompt"], hash_prompt=meta["hash_prompt_sistema"],
        dados_minimizados=meta["dados_minimizados"], resposta_llm=_somar_uso(tentativas),
        resumo_resultado=resumo_resultado,
        erro="; ".join(f"{e['camada']}:{e['campo']}:{e['categoria']}" for e in erros) or None)
    registro.update({"versao_contrato": meta["versao_contrato"],
                     "tentativas_correcao": max(0, len(tentativas) - 1)})
    audit.registrar_execucao(registro, caminho_log)


# ---------------------------------------------------------------- RF15: resumo e ficha de compreensão

_NUMERO = re.compile(r"\d[\d./:-]*\d")


@dataclass
class ResultadoResumo:
    caso_id: str
    estado: str  # valida | bloqueada_negocio | rejeitada_esquema | erro_provedor | dry_run
    resumo: dict[str, Any] | None = None
    erros: list[dict[str, Any]] = field(default_factory=list)
    tentativas: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def _sem_ponto_de_milhar(texto: str) -> str:
    return re.sub(r"(?<=\d)\.(?=\d{3}\b)", "", texto)


def _ler_data(valor: str) -> date | None:
    """Data em DD/MM/AAAA ou por extenso ("14 de outubro de 2026"); None se não for data válida."""
    try:
        return datetime.strptime(valor.strip(), "%d/%m/%Y").date()
    except ValueError:
        pass
    m = re.fullmatch(r"(\d{1,2})o? de ([a-z]+) de (\d{4})", normalizar(valor))
    meses = [normalizar(x) for x in MESES]
    if m and m.group(2) in meses:
        try:
            return date(int(m.group(3)), meses.index(m.group(2)) + 1, int(m.group(1)))
        except ValueError:
            return None
    return None


def regras_resumo(resumo: schemas.ResumoSolicitacao, texto_original: str,
                  texto_enviado: str = "") -> list[dict[str, str]]:
    """Camada 3 do resumo: fatos sem trecho no original, números ou datas sem suporte e dado pessoal."""
    textos = (texto_original, texto_enviado)
    erros = [_erro_negocio("fato_sem_suporte", f"fatos.{i}.evidencia", "o trecho citado não aparece no texto original")
             for i, fato in enumerate(resumo.fatos) if not _presente(fato.evidencia, textos)]
    corpo = " ".join([resumo.resumo, *(f.afirmacao for f in resumo.fatos)])
    base = " ".join(_sem_ponto_de_milhar(normalizar(t)) for t in textos if t)
    for token in sorted(set(_NUMERO.findall(corpo))):
        d = _ler_data(token)
        if d and any(_presente(forma, textos) for forma in _formas_data(d)):
            continue
        if _sem_ponto_de_milhar(normalizar(token)) not in base:
            erros.append(_erro_negocio("valor_sem_suporte", "resumo", "número ou data que não aparece no texto original"))
    _, detectados = prompts.minimizar(corpo)
    if detectados:
        erros.append(_erro_negocio("dado_pessoal_no_resumo", "resumo",
                                   f"o resumo reproduz dado pessoal: {', '.join(sorted(detectados))}"))
    return erros


def validar_resumo(texto_json: str, texto_original: str,
                   texto_enviado: str = "") -> tuple[str, schemas.ResumoSolicitacao | None, list[dict]]:
    """Camadas 1, 2 e 3 do resumo. Retorna (estado, objeto, erros)."""
    res = schemas.validar_texto_json(schemas.ResumoSolicitacao, texto_json)
    if not res.valido:
        return "rejeitada_esquema", None, [
            {**e, "camada": "sintatica" if e["categoria"] == "json_invalido" else "esquema"} for e in res.erros]
    erros = regras_resumo(res.objeto, texto_original, texto_enviado)
    return ("bloqueada_negocio" if erros else "valida"), res.objeto, erros


def resumir(texto: str, arquivo_origem: str, caso_id: str, cfg: dict[str, Any] | None = None, *,
            modo: str | None = None, chamar: Callable[..., dict[str, Any]] = llm_client.chamar_chat,
            dry_run: bool = False, caminho_log: Path | None = None) -> ResultadoResumo:
    """Resume a solicitação (RF15) com a mesma disciplina da extração: esquema, 1 correção e regras."""
    cfg = cfg or CONFIG["extracao_estruturada"]
    modo = modo or cfg["modo_saida"]
    msgs, meta = prompts.montar_mensagens_resumo(texto, arquivo_origem)
    texto_enviado = meta.pop("texto_enviado")
    params, json_mode = parametros_saida(modo, cfg["parametros"], schemas.ResumoSolicitacao, "resumo_solicitacao")
    meta.update({
        "versao_contrato": f"resumo_solicitacao-v{schemas.ResumoSolicitacao.VERSAO}",
        "versao_prompt_correcao": prompts.VERSOES["correcao_esquema"][1],
        "provedor": cfg["provedor"], "modelo": cfg["modelo"], "modo_saida": modo,
        "arquivo_origem": arquivo_origem,
        "sha256_origem": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "texto_enviado": texto_enviado,
    })
    if dry_run:
        return ResultadoResumo(caso_id, "dry_run", meta=meta)
    estado, objeto, erros, tentativas = _gerar_com_correcao(
        msgs, lambda saida: validar_resumo(saida, texto, texto_enviado), cfg, params, json_mode, chamar)
    _auditar("resumo", caso_id, estado, erros, tentativas, meta, cfg, caminho_log)
    return ResultadoResumo(caso_id, estado, objeto.model_dump() if objeto else None, erros, tentativas, meta)


def montar_ficha(caso_id: str, extracao: dict[str, Any] | None, estado_extracao: str, versao_prompt_extracao: str,
                 resumo: ResultadoResumo) -> dict[str, Any] | None:
    """Ficha exibida ao operador; só existe quando extração e resumo passaram nas três camadas."""
    if extracao is None or estado_extracao != "valida" or resumo.estado != "valida":
        return None
    ficha = schemas.FichaCompreensao.model_validate({
        "id_caso": caso_id, "extracao": extracao, "resumo": resumo.resumo,
        "versao_prompt_extracao": versao_prompt_extracao, "versao_prompt_resumo": resumo.meta["versao_prompt"]})
    return ficha.model_dump()


def _mesmo_valor(esperado: str, obtido: str) -> bool:
    de, do = _ler_data(esperado), _ler_data(obtido)
    if de and do:
        return de == do
    return _confere(esperado, obtido) or _confere(obtido, esperado)


def avaliar_ficha(extracao: dict[str, Any] | None, resumo: dict[str, Any] | None, gab: dict[str, Any]) -> dict[str, Any]:
    """Parte automática da conferência do RF15. Fidelidade do resumo aos fatos essenciais é avaliação humana."""
    obtidas = (extracao or {}).get("entidades") or []
    esperadas = gab["entidades_esperadas"]

    def mesmo(e, o):
        return e["tipo"] == o["tipo"] and _mesmo_valor(e["valor"], o["valor"])

    pares = [(e, next((o for o in obtidas if mesmo(e, o)), None)) for e in esperadas]
    corpo = " ".join([(resumo or {}).get("resumo", ""), *(f["afirmacao"] for f in (resumo or {}).get("fatos", []))])
    categoria = (extracao or {}).get("categoria")
    return {
        "categoria": {"obtida": categoria, "esperada": gab["extracao_esperada"]["categoria"],
                      "correta": categoria == gab["extracao_esperada"]["categoria"]},
        "entidades": {
            "esperadas": len(esperadas),
            "encontradas": sum(o is not None for _, o in pares),
            "omitidas": [f"{e['tipo']}: {e['valor']}" for e, o in pares if o is None],
            "a_mais": [f"{o['tipo']}: {o['valor']} ({o['origem']})" for o in obtidas
                       if not any(mesmo(e, o) for e in esperadas)],
            "origem_divergente": [f"{e['tipo']}: {e['valor']} (esperado {e['origem']}, obtido {o['origem']})"
                                  for e, o in pares if o is not None and o["origem"] != e["origem"]],
        },
        "resumo": {
            "palavras": schemas.contar_palavras(resumo["resumo"]) if resumo else None,
            "padroes_proibidos": [p for p in gab.get("padroes_proibidos_resumo", []) if re.search(p, corpo, re.I)],
            "nao_deve_aparecer": [v for v in gab.get("nao_deve_aparecer_na_extracao", [])
                                  if normalizar(v) in normalizar(corpo)],
        },
    }


# ---------------------------------------------------------------- Comparação com o gabarito

def _confere(esperado: Any, obtido: Any) -> bool:
    if esperado is None:
        return obtido is None
    if obtido is None:
        return False
    e, o = normalizar(str(esperado)), normalizar(str(obtido))
    return e == o or e in o


def comparar_com_gabarito(extracao: dict[str, Any] | None, encaminhamento: str, gab: dict[str, Any]) -> dict[str, Any]:
    """Confere os campos do RF14 contra o gabarito validado (convenções: DADOS_E_GABARITOS_D2.md, seção 7)."""
    esp = gab["extracao_esperada"]
    obt = extracao or {}
    campos = {c: _confere(esp[c], obt.get(c)) for c in CAMPOS_CURTOS}
    ignorados = set(gab.get("campos_ignorados_em_nao_deve_aparecer", []))
    texto_obtido = normalizar(json.dumps({k: v for k, v in obt.items() if k not in ignorados}, ensure_ascii=False))
    vazados = [v for v in gab.get("nao_deve_aparecer_na_extracao", []) if normalizar(v) in texto_obtido]
    return {
        "campos": campos,
        "categoria": obt.get("categoria") == esp["categoria"],
        "campos_ausentes": set(obt.get("campos_ausentes") or []) == set(esp["campos_ausentes"]),
        "requer_revisao": obt.get("requer_revisao") == esp["requer_revisao"],
        "alerta": bool(obt.get("alertas_seguranca")) == esp["deve_ter_alerta_seguranca"],
        "encaminhamento": encaminhamento == gab["resultado_esperado_fluxo"]["encaminhamento"],
        "nao_deve_aparecer": vazados,
    }


# ---------------------------------------------------------------- Execução em lote (CLI)

def carregar_casos(caso: str | None = None) -> list[dict[str, Any]]:
    gabaritos = sorted((DIR_GABARITOS / "solicitacoes").glob("*.json"))
    casos = [json.loads(p.read_text(encoding="utf-8")) for p in gabaritos]
    if caso:
        casos = [g for g in casos if g["caso_id"] == caso]
        if not casos:
            raise SystemExit(f"Caso sem gabarito do Desafio 02: {caso}")
    return casos


def _marca(ok: bool) -> str:
    return "ok" if ok else "ERRO"


def executar_lote(caso: str | None, modo: str | None, dry_run: bool) -> Path:
    cfg = CONFIG["extracao_estruturada"]
    destino = RAIZ / cfg["diretorio"] / datetime.now().strftime("%Y%m%d-%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    linhas, total_custo = [], 0.0
    for i, gab in enumerate(carregar_casos(caso)):
        if i and not dry_run:
            time.sleep(cfg["pausa_entre_chamadas_s"])
        texto = (RAIZ / gab["arquivo_origem"]).read_text(encoding="utf-8")
        res = extrair(texto, gab["arquivo_origem"], gab["caso_id"], cfg, modo=modo, dry_run=dry_run)
        cmp = comparar_com_gabarito(res.extracao, res.encaminhamento, gab)
        (destino / f"{gab['caso_id']}.json").write_text(
            json.dumps({**res.para_json(), "comparacao_gabarito": cmp}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        uso = _somar_uso(res.tentativas)
        total_custo += uso["custo_usd"] or 0
        print(f"  {gab['caso_id']}: {res.estado} -> {res.encaminhamento} (chamadas: {len(res.tentativas)})")
        acertos = sum(cmp["campos"].values())
        linhas.append(
            f"| {gab['caso_id']} | {res.estado} | {len(res.tentativas)} | "
            f"{res.encaminhamento} ({_marca(cmp['encaminhamento'])}) | "
            f"{(res.extracao or {}).get('categoria', '—')} ({_marca(cmp['categoria'])}) | "
            f"{acertos}/{len(cmp['campos'])} | {_marca(cmp['campos_ausentes'])} | {_marca(cmp['requer_revisao'])} | "
            f"{_marca(cmp['alerta'])} | {', '.join(cmp['nao_deve_aparecer']) or '—'} | "
            f"{'; '.join(e['categoria'] + ' em ' + e['campo'] for e in res.erros) or '—'} |")
    cabecalho = (
        f"# RF14 — Extração estruturada ({destino.name})\n\n"
        f"Modelo: `{cfg['modelo']}` · modo: `{modo or cfg['modo_saida']}` · contrato: "
        f"`solicitacao_extraida-v{schemas.SolicitacaoExtraida.VERSAO}` · prompt: `{prompts.VERSOES['extracao_v2'][1]}`"
        f"{' · DRY-RUN (nenhuma chamada)' if dry_run else ''} · custo total estimado: US$ {total_custo:.6f}\n\n"
        "Conferência automática contra os gabaritos validados (`dados/gabaritos/d2/solicitacoes/`). "
        "Campos curtos = protocolo, data, canal, solicitante e curso.\n\n"
        "| Caso | Estado | Chamadas | Encaminhamento | Categoria | Campos curtos | Ausentes | Requer revisão "
        "| Alerta | Dado proibido presente | Erros finais |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
    (destino / "matriz_rf14.md").write_text(cabecalho + "\n".join(linhas) + "\n", encoding="utf-8", newline="\n")
    return destino


def _secao_revisao(gab: dict[str, Any], extracao: dict[str, Any] | None, resumo: dict[str, Any] | None) -> str:
    """Ficha e gabarito lado a lado, sem os resultados automáticos, para a conferência humana (Checkpoint 2)."""
    resumo = resumo or {}
    fatos = "\n".join(f"- {f['afirmacao']} — evidência: \"{f['evidencia']}\"" for f in resumo.get("fatos", [])) or "- (nenhum)"
    entidades = "\n".join(f"- {e['tipo']} · {e['valor']} · {e['origem']} · \"{e['evidencia']}\""
                          for e in (extracao or {}).get("entidades", [])) or "- (nenhuma)"
    essenciais = "\n".join(f"- {f}" for f in gab["fatos_essenciais"])
    esperadas = "\n".join(f"- {e['tipo']} · {e['valor']} · {e['origem']}" for e in gab["entidades_esperadas"])
    palavras = schemas.contar_palavras(resumo["resumo"]) if resumo.get("resumo") else 0
    return (f"## {gab['caso_id']}\n\nTexto original: `{gab['arquivo_origem']}`\n\n"
            f"### Ficha gerada\n\n**Resumo ({palavras} palavras):** {resumo.get('resumo', '(sem resumo)')}\n\n"
            f"**Fatos citados:**\n{fatos}\n\n**Categoria:** {(extracao or {}).get('categoria', '—')}\n\n"
            f"**Entidades (tipo · valor · origem · evidência):**\n{entidades}\n\n"
            f"### Gabarito validado\n\n**Fatos essenciais:**\n{essenciais}\n\n"
            f"**Categoria:** {gab['extracao_esperada']['categoria']}\n\n"
            f"**Entidades esperadas (tipo · valor · origem):**\n{esperadas}\n")


def executar_fichas(caso: str | None, reusar: Path | None, dry_run: bool) -> Path:
    """Gera as fichas do conjunto RF15. Com `reusar`, aproveita a extração de uma execução do RF14."""
    cfg = CONFIG["extracao_estruturada"]
    destino = RAIZ / cfg["diretorio_fichas"] / datetime.now().strftime("%Y%m%d-%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)
    casos = [g for g in carregar_casos(caso) if g.get("conjunto_rf15")]
    linhas, secoes, corretas, custo = [], [], 0, 0.0
    for i, gab in enumerate(casos):
        if i and not dry_run:
            time.sleep(cfg["pausa_entre_chamadas_s"])
        texto = (RAIZ / gab["arquivo_origem"]).read_text(encoding="utf-8")
        if reusar:
            ext = json.loads((reusar / f"{gab['caso_id']}.json").read_text(encoding="utf-8"))
            extracao, estado_ext, versao_ext = ext["extracao"], ext["estado"], ext["meta"]["versao_prompt"]
        else:
            r = extrair(texto, gab["arquivo_origem"], gab["caso_id"], cfg, dry_run=dry_run)
            extracao, estado_ext, versao_ext = r.extracao, r.estado, r.meta["versao_prompt"]
            custo += _somar_uso(r.tentativas)["custo_usd"] or 0
        res = resumir(texto, gab["arquivo_origem"], gab["caso_id"], cfg, dry_run=dry_run)
        custo += _somar_uso(res.tentativas)["custo_usd"] or 0
        ficha = montar_ficha(gab["caso_id"], extracao, estado_ext, versao_ext, res)
        av = avaliar_ficha(extracao, res.resumo, gab)
        corretas += av["categoria"]["correta"]
        (destino / f"{gab['caso_id']}.json").write_text(json.dumps({
            "caso_id": gab["caso_id"], "origem_extracao": relativo(reusar) if reusar else "nova",
            "estado_extracao": estado_ext, "versao_prompt_extracao": versao_ext, "extracao": extracao,
            "resumo": asdict(res), "ficha": ficha, "avaliacao_automatica": av,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"  {gab['caso_id']}: extração {estado_ext}, resumo {res.estado}, ficha {'ok' if ficha else 'retida'}")
        ent, rs = av["entidades"], av["resumo"]
        sem_suporte = [e["categoria"] for e in res.erros if e["camada"] == "negocio"]
        linhas.append(
            f"| {gab['caso_id']} | {av['categoria']['obtida']} ({_marca(av['categoria']['correta'])}) | "
            f"{ent['encontradas']}/{ent['esperadas']} | {'; '.join(ent['omitidas']) or '—'} | "
            f"{'; '.join(ent['a_mais']) or '—'} | {'; '.join(ent['origem_divergente']) or '—'} | "
            f"{res.estado} | {rs['palavras'] if rs['palavras'] is not None else '—'} | {', '.join(sem_suporte) or '—'} | "
            f"{len(rs['padroes_proibidos'])} | {', '.join(rs['nao_deve_aparecer']) or '—'} |")
        secoes.append(_secao_revisao(gab, extracao, res.resumo))
    origem = f"extração reaproveitada de `{relativo(reusar)}`" if reusar else "extração nova"
    (destino / "matriz_rf15.md").write_text(
        f"# RF15 — Ficha de compreensão ({destino.name})\n\n"
        f"Resumo: `{prompts.VERSOES['resumo'][1]}` · {origem} · modelo `{cfg['modelo']}`"
        f"{' · DRY-RUN' if dry_run else ''} · custo estimado: US$ {custo:.6f}\n\n"
        f"**Acurácia de categoria: {corretas}/{len(casos)}.** Conferência automática; a fidelidade do resumo aos "
        "fatos essenciais é avaliada por pessoa (Checkpoint 2).\n\n"
        "| Caso | Categoria | Entidades esperadas encontradas | Omitidas | A mais (a conferir) | Origem divergente "
        "| Resumo | Palavras | Sem suporte | Padrões proibidos | Dado proibido |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n" + "\n".join(linhas) + "\n",
        encoding="utf-8", newline="\n")
    (destino / "fichas_para_revisao.md").write_text(
        f"# Fichas para conferência humana ({destino.name})\n\n" + "\n---\n\n".join(secoes),
        encoding="utf-8", newline="\n")
    return destino


# ---------------------------------------------------------------- Comparação JSON sintático × esquema

def _avaliar_camadas(rotulo: str, origem: str, texto_json: str, texto_original: str) -> dict[str, Any]:
    try:
        json.loads(texto_json)
        sintatico = True
    except json.JSONDecodeError:
        sintatico = False
    estado, _, _, erros = validar_extracao(texto_json, texto_original)
    por_categoria: dict[str, list[str]] = {}
    for e in erros:
        por_categoria.setdefault(e["categoria"], []).append(e["campo"])
    return {"rotulo": rotulo, "origem": origem, "aceito_so_sintatico": sintatico, "estado": estado,
            "erros_por_categoria": por_categoria}


def comparar_json(execucao: Path | None = None) -> Path:
    """Mesmo caso (caso01) sob validação só sintática e validação por esquema (RF14, terceiro item)."""
    texto_original = (RAIZ / "dados/originais/entrada_texto.txt").read_text(encoding="utf-8")
    d1 = RAIZ / "resultados/comparacao_modelos/20261016-201709/openai_gpt-oss-120b__caso01_texto__extracao.json"
    pastas = sorted(p for p in (RAIZ / CONFIG["extracao_estruturada"]["diretorio"]).glob("*") if p.is_dir())
    execucao = execucao or next((p for p in reversed(pastas) if (p / "caso01_texto.json").exists()
                                 and json.loads((p / "caso01_texto.json").read_text(encoding="utf-8"))["extracao"]),
                                None)
    if execucao is None:
        raise SystemExit("Rode antes: python -m src.nlp extrair --caso caso01_texto")
    v2 = json.loads((execucao / "caso01_texto.json").read_text(encoding="utf-8"))["extracao"]

    # Defeitos controlados sobre a saída válida: os três tipos de erro que o RF14 manda diferenciar.
    mutada = copy.deepcopy(v2)
    mutada["prioridade"] = "alta"
    mutada["requer_revisao"] = "false"
    del mutada["pedido"]

    amostras = [
        _avaliar_camadas("A. Saída real do Desafio 01 (prompt v1, modo json_object)", relativo(d1),
                         d1.read_text(encoding="utf-8"), texto_original),
        _avaliar_camadas("B. Saída real do Desafio 02 (prompt v2, esquema estrito)",
                         relativo(execucao / "caso01_texto.json"), json.dumps(v2, ensure_ascii=False), texto_original),
        _avaliar_camadas("C. Saída B com três defeitos controlados", "chave extra 'prioridade'; "
                         "requer_revisao como texto; 'pedido' removido", json.dumps(mutada, ensure_ascii=False),
                         texto_original),
    ]
    destino = RAIZ / "resultados/metricas"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "rf14_comparacao_json.json").write_text(json.dumps(amostras, ensure_ascii=False, indent=2) + "\n",
                                                        encoding="utf-8", newline="\n")
    linhas = []
    for a in amostras:
        detalhes = "<br>".join(f"**{cat}**: {', '.join(campos)}" for cat, campos in a["erros_por_categoria"].items()) or "—"
        linhas.append(f"| {a['rotulo']} | `{a['origem']}` | {'aceito' if a['aceito_so_sintatico'] else 'recusado'} "
                      f"| {a['estado']} | {detalhes} |")
    md = ("# RF14 — JSON apenas sintático × saída validada por esquema (caso01)\n\n"
          "Mesmo caso, duas formas de validar. A validação **só sintática** pergunta apenas se o texto é JSON "
          "(`json.loads`). A validação **por esquema** confere o contrato `SolicitacaoExtraida` (chaves, tipos, "
          "obrigatoriedade e regras internas) e, se ele passar, as regras de negócio contra o texto original.\n\n"
          "| Amostra | Origem | Só sintático | Por esquema + negócio | Erros encontrados (categoria: campos) |\n"
          "|---|---|---|---|---|\n" + "\n".join(linhas) + "\n\n"
          "Leitura: `chave_extra` = chave que o contrato não prevê; `tipo_incorreto` = valor de tipo errado "
          "(ex.: texto no lugar de booleano); `campo_ausente` = campo obrigatório que não veio; `valor_invalido` = "
          "tipo certo com valor fora do permitido (ex.: data fora do formato, categoria fora da lista); "
          "`regra_do_contrato` = regra interna do contrato (ex.: `campos_ausentes` diferente dos campos nulos). "
          "As três amostras passam na validação só sintática; só a B obedece ao contrato.\n")
    (destino / "rf14_comparacao_json.md").write_text(md, encoding="utf-8", newline="\n")
    return destino / "rf14_comparacao_json.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extração estruturada e validação (RF14).")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_ext = sub.add_parser("extrair", help="Extrai e valida as solicitações com gabarito do Desafio 02")
    alvo = p_ext.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--caso", help="ID do caso (ex.: caso05_texto_incompleto)")
    alvo.add_argument("--todos", action="store_true", help="Todos os casos com gabarito")
    p_ext.add_argument("--modo", choices=["json_schema_estrito", "json_object"], help="Sobrescreve config.json")
    p_ext.add_argument("--dry-run", action="store_true", help="Monta as mensagens sem chamar o provedor")
    sub.add_parser("comparar-json", help="Gera a comparação JSON sintático × esquema (resultados/metricas)")
    p_fic = sub.add_parser("fichas", help="Gera as fichas de compreensão do conjunto RF15 (resumo + extração)")
    alvo_f = p_fic.add_mutually_exclusive_group(required=True)
    alvo_f.add_argument("--caso", help="ID do caso")
    alvo_f.add_argument("--todos", action="store_true", help="Todos os casos do conjunto RF15")
    p_fic.add_argument("--reusar-extracao", type=Path, help="Pasta de uma execução do RF14 (resultados/extracao/...)")
    p_fic.add_argument("--dry-run", action="store_true", help="Monta as mensagens sem chamar o provedor")
    args = parser.parse_args(argv)

    if args.comando in ("extrair", "fichas"):
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    if args.comando == "extrair":
        destino = executar_lote(args.caso, args.modo, args.dry_run)
        print(f"[OK] Resultados em {relativo(destino)} (matriz_rf14.md)")
    elif args.comando == "fichas":
        reusar = (RAIZ / args.reusar_extracao) if args.reusar_extracao and not args.reusar_extracao.is_absolute() \
            else args.reusar_extracao
        destino = executar_fichas(args.caso, reusar, args.dry_run)
        print(f"[OK] Resultados em {relativo(destino)} (matriz_rf15.md, fichas_para_revisao.md)")
    else:
        print(f"[OK] {relativo(comparar_json())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
