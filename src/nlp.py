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

def parametros_saida(modo: str, parametros: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Devolve (parametros, json_mode). O esquema estrito vai em `response_format`, sem alterar o cliente."""
    params = dict(parametros)
    if modo == "json_schema_estrito":
        params["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "solicitacao_extraida", "strict": True,
            "schema": schemas.SolicitacaoExtraida.model_json_schema()}}
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
        estado, _, objeto, erros = validar_extracao(resp.get("texto", ""), texto, texto_enviado, hoje)
        tentativas.append({"numero": n, "texto_bruto": resp.get("texto", ""),
                           "valida_no_esquema": estado != "rejeitada_esquema", "erros": erros,
                           **{k: resp.get(k) for k in ("latencia_s", "tokens_entrada", "tokens_saida", "custo_usd")}})
        if estado != "rejeitada_esquema":
            break
        conversa += [{"role": "assistant", "content": resp.get("texto", "")},
                     {"role": "user", "content": prompts.mensagem_correcao_esquema(erros)}]

    resultado = ResultadoExtracao(caso_id, estado, decidir_encaminhamento(estado, objeto),
                                  objeto.model_dump() if objeto else None, erros, tentativas, meta)
    _auditar(resultado, cfg, caminho_log)
    return resultado


def _auditar(res: ResultadoExtracao, cfg: dict[str, Any], caminho_log: Path | None) -> None:
    """Registra a execução no log de auditoria (RF21), sem o texto da solicitação."""
    registro = audit.criar_registro(
        caso_id=res.caso_id, etapa="extracao_estruturada", modalidade="texto",
        arquivo_origem=res.meta["arquivo_origem"], provedor=cfg["provedor"], modelo=cfg["modelo"],
        parametros={**cfg["parametros"], "modo_saida": res.meta["modo_saida"]},
        versao_prompt=res.meta["versao_prompt"], hash_prompt=res.meta["hash_prompt_sistema"],
        dados_minimizados=res.meta["dados_minimizados"], resposta_llm=_somar_uso(res.tentativas),
        resumo_resultado=f"{res.estado} -> {res.encaminhamento}",
        erro="; ".join(f"{e['camada']}:{e['campo']}:{e['categoria']}" for e in res.erros) or None)
    registro.update({"versao_contrato": res.meta["versao_contrato"],
                     "tentativas_correcao": max(0, len(res.tentativas) - 1)})
    audit.registrar_execucao(registro, caminho_log)


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
    args = parser.parse_args(argv)

    if args.comando == "extrair":
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
        destino = executar_lote(args.caso, args.modo, args.dry_run)
        print(f"[OK] Resultados em {relativo(destino)} (matriz_rf14.md)")
    else:
        print(f"[OK] {relativo(comparar_json())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
