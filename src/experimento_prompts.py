"""Experimentos do Estudante 1: RF02 (prompts A/B/C) e comparação de modelos.

Uso:
  python -m src.experimento_prompts prompts   [--provedor P] [--modelo M] [--reusar-prompt-c] [--dry-run]
  python -m src.experimento_prompts modelos   [--provedor P] [--modelos M1 M2 ...] [--dry-run]
  python -m src.experimento_prompts listar    --provedor P
  python -m src.experimento_prompts reavaliar <pasta de resultados>
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from src import avaliacao, prompts
from src.cliente_experimento import ErroProvedor, chamar_chat, custo_estimado, listar_modelos, verificar_chave

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
DIR_ORIGINAIS = RAIZ / CONFIG["caminhos"]["originais"]
DIR_RESULTADOS = RAIZ / CONFIG["caminhos"]["resultados"]

DECISOES = {"aprovar": "Aprovar", "correcao_manual": "Correção manual",
            "rejeitar_nova_geracao": "Rejeitar / nova geração"}


# ---------------------------------------------------------------- utilidades

def _agora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _pasta_execucao(tipo: str) -> Path:
    pasta = DIR_RESULTADOS / tipo / datetime.now().strftime("%Y%m%d-%H%M%S")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def _gravar(caminho: Path, texto: str) -> None:
    caminho.write_text(texto, encoding="utf-8")


def _registrar(pasta: Path, registro: dict) -> None:
    """Registro estruturado (JSONL). Nunca contém a chave da API."""
    with open(pasta / "execucoes.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def _ler_registros(pasta: Path) -> list[dict]:
    arq = pasta / "execucoes.jsonl"
    return [json.loads(l) for l in arq.read_text(encoding="utf-8").splitlines() if l.strip()] if arq.exists() else []


def _contexto_para_avaliacao() -> str:
    """Parte afirmativa do contexto (a lista do que NÃO está disponível não conta como fonte)."""
    return prompts.ler_prompt("contexto_institucional.md").split("## O que NÃO está disponível")[0]


def _caso(caso_id: str) -> tuple[dict, str, str]:
    gabarito = avaliacao.carregar_gabarito(caso_id)
    arquivo = gabarito["arquivo_origem"]
    return gabarito, arquivo, (RAIZ / arquivo).read_text(encoding="utf-8")


def _md_mensagens(mensagens: list[dict]) -> str:
    return "\n\n".join(f"<!-- role: {m['role']} -->\n{m['content']}" for m in mensagens)


def _chamar(perfil, modelo, mensagens, cfg, json_mode=False, dry_run=False) -> dict:
    if dry_run:
        return {"texto": "", "latencia_s": None, "tokens_entrada": None, "tokens_saida": None,
                "tentativas": 0, "erro": "dry-run (nenhuma chamada realizada)"}
    time.sleep(cfg.get("pausa_entre_chamadas_s", 0))  # respeita o limite da cota gratuita
    try:
        return chamar_chat(perfil, modelo, mensagens, cfg["parametros"], cfg.get("timeout_s", 60),
                           cfg.get("tentativas", 3), json_mode=json_mode)
    except ErroProvedor as e:
        print(f"  ! {e}", file=sys.stderr)
        return {"texto": "", "latencia_s": None, "tokens_entrada": None, "tokens_saida": None,
                "tentativas": cfg.get("tentativas", 3), "erro": str(e)}


def _registro_base(id_exec, etapa, caso_id, arquivo, provedor, modelo, parametros, versao, hash_p, resp, saida):
    return {
        "id_execucao": id_exec, "data_hora": _agora(), "etapa": etapa, "caso_id": caso_id,
        "modalidade": "texto", "arquivo_origem": arquivo, "provedor": provedor, "modelo": modelo,
        "parametros": parametros, "versao_prompt": versao, "hash_prompt": hash_p,
        "latencia_s": resp.get("latencia_s"), "tokens_entrada": resp.get("tokens_entrada"),
        "tokens_saida": resp.get("tokens_saida"),
        "custo_usd": custo_estimado(CONFIG.get("precos_usd_por_milhao_tokens", {}), modelo,
                                    resp.get("tokens_entrada"), resp.get("tokens_saida")),
        "tentativas": resp.get("tentativas"), "erro": resp.get("erro"), "arquivo_saida": saida,
        "decisao_humana": "PENDENTE",
    }


# ---------------------------------------------------------------- RF02

def _preencher(template: str, contexto: str, solicitacao: str, arquivo: str) -> tuple[str, list[str]]:
    ajustes = []
    if "{{SOLICITACAO}}" not in template:
        template += "\n\n<solicitacao>\n{{SOLICITACAO}}\n</solicitacao>"
        ajustes.append("marcador {{SOLICITACAO}} ausente: solicitação anexada ao final")
    texto = (template.replace("{{CONTEXTO}}", contexto.strip())
             .replace("{{ARQUIVO_ORIGEM}}", arquivo).replace("{{SOLICITACAO}}", solicitacao.strip()))
    return texto, ajustes


def experimento_prompts(provedor: str, modelo: str, reusar_c: bool, dry_run: bool) -> Path:
    cfg = CONFIG["experimento_prompts"]
    perfil = CONFIG["provedores"][provedor]
    if not dry_run:
        verificar_chave(perfil)
    caso_id = cfg["caso"]
    gabarito, arquivo, solicitacao = _caso(caso_id)
    contexto = prompts.ler_prompt("contexto_institucional.md")
    pasta = _pasta_execucao("experimento_prompts")
    print(f"RF02 · {provedor}/{modelo} · caso {caso_id} → {pasta.relative_to(RAIZ)}")

    # Prompt C: gerado com metaprompt (mesmo modelo e parâmetros)
    caminho_c = RAIZ / "prompts" / "experimento" / "prompt_C.md"
    preparo_c = None
    if reusar_c and caminho_c.exists():
        template_c = caminho_c.read_text(encoding="utf-8").split("-->", 1)[-1].lstrip()
    else:
        meta_txt = prompts.ler_prompt("experimento/metaprompt.md").replace("{{CONTEXTO}}", contexto.strip())
        msgs = [{"role": "user", "content": meta_txt}]
        _gravar(pasta / "metaprompt_entrada.md", _md_mensagens(msgs))
        print("  · gerando Prompt C com metaprompt…")
        resp = _chamar(perfil, modelo, msgs, cfg, dry_run=dry_run)
        preparo_c = resp.get("latencia_s")
        bruto = resp["texto"]
        _gravar(pasta / "metaprompt_saida.md", bruto or f"(sem saída: {resp.get('erro')})")
        inicio, fim = bruto.find("<prompt>"), bruto.rfind("</prompt>")
        template_c = bruto[inicio + 8:fim].strip() if inicio >= 0 and fim > inicio else bruto.strip()
        _registrar(pasta, _registro_base(f"exp-{uuid.uuid4().hex[:8]}", "metaprompt", caso_id, arquivo, provedor,
                                         modelo, cfg["parametros"], "metaprompt-v1.0", prompts.hash_texto(meta_txt),
                                         resp, "metaprompt_saida.md"))
        if template_c and not dry_run:
            _gravar(caminho_c, f"<!-- Prompt C gerado por metaprompt (prompts/experimento/metaprompt.md) | "
                               f"modelo: {provedor}/{modelo} | data: {_agora()} | sem edição humana -->\n"
                    + template_c + "\n")

    templates = {"A": prompts.ler_prompt("experimento/prompt_A.md"),
                 "B": prompts.ler_prompt("experimento/prompt_B.md"),
                 "C": template_c or "(prompt C indisponível)\n\n{{SOLICITACAO}}"}
    for rotulo, template in templates.items():
        texto, ajustes = _preencher(template, contexto, solicitacao, arquivo)
        msgs = [{"role": "user", "content": texto}]
        _gravar(pasta / f"prompt_{rotulo}_entrada.md", _md_mensagens(msgs))
        print(f"  · executando Prompt {rotulo}…")
        resp = _chamar(perfil, modelo, msgs, cfg, dry_run=dry_run)
        _gravar(pasta / f"prompt_{rotulo}_saida.md", resp["texto"] or f"(sem saída: {resp.get('erro')})")
        reg = _registro_base(f"exp-{uuid.uuid4().hex[:8]}", f"prompt_{rotulo}", caso_id, arquivo, provedor, modelo,
                             cfg["parametros"], f"experimento-{rotulo}", prompts.hash_texto(texto), resp,
                             f"prompt_{rotulo}_saida.md")
        reg["ajustes"] = ajustes
        if rotulo == "C":
            reg["latencia_preparo_metaprompt_s"] = preparo_c
        _registrar(pasta, reg)

    avaliar_experimento(pasta)
    return pasta


def avaliar_experimento(pasta: Path) -> None:
    registros = [r for r in _ler_registros(pasta) if r["etapa"].startswith("prompt_")]
    if not registros:
        return
    gabarito, _, solicitacao = _caso(registros[0]["caso_id"])
    contexto = _contexto_para_avaliacao()
    resultados = {}
    for r in registros:
        rotulo = r["etapa"].split("_")[1]
        texto = (pasta / r["arquivo_saida"]).read_text(encoding="utf-8") if not r.get("erro") else ""
        fontes = solicitacao if rotulo == "A" else solicitacao + "\n" + contexto
        res = avaliacao.avaliar_minuta(texto, gabarito, fontes) if texto else None
        resultados[rotulo] = {"registro": r, "avaliacao": res}
    _gravar(pasta / "avaliacao_automatica.json", json.dumps(resultados, ensure_ascii=False, indent=2))
    _gravar(pasta / "matriz_comparativa.md", _matriz_rf02(resultados, pasta))
    print(f"  ✓ matriz: {(pasta / 'matriz_comparativa.md').relative_to(RAIZ)}")


def _matriz_rf02(resultados: dict, pasta: Path) -> str:
    r0 = next(iter(resultados.values()))["registro"]
    linhas = [
        "# RF02 — Matriz comparativa dos prompts A, B e C", "",
        f"- Execução: `{pasta.name}` · Caso: `{r0['caso_id']}` (`{r0['arquivo_origem']}`)",
        f"- Provedor/modelo (iguais nos três testes): `{r0['provedor']}` / `{r0['modelo']}`",
        f"- Parâmetros (iguais nos três testes): `{json.dumps(r0['parametros'])}`",
        "- Entradas: `prompt_X_entrada.md` · Saídas: `prompt_X_saida.md` · Registro: `execucoes.jsonl`", "",
        "## 1. Critérios automáticos", "",
        "| Critério | Prompt A (zero-shot) | Prompt B (estruturado) | Prompt C (metaprompt) |",
        "|---|---|---|---|",
    ]

    def col(f):
        return " | ".join(f(resultados[k]) if k in resultados else "—" for k in "ABC")

    def av(x, campo, padrao="—"):
        return x["avaliacao"][campo] if x["avaliacao"] else padrao

    def cont(x, g):
        return str(x["avaliacao"]["contagem"][g]) if x["avaliacao"] else "—"

    def tempo(x):
        r = x["registro"]
        if r.get("latencia_s") is None:
            return "erro"
        prep = r.get("latencia_preparo_metaprompt_s")
        return f"{r['latencia_s']} s" + (f" (+{prep} s metaprompt)" if prep else "")

    def tokens(x):
        return f"{x['registro'].get('tokens_entrada')} / {x['registro'].get('tokens_saida')}"

    linhas += [
        f"| Tempo de geração | {col(tempo)} |",
        f"| Tokens entrada / saída | {col(tokens)} |",
        f"| Formato: seções do modelo institucional | {col(lambda x: av(x, 'secoes_presentes'))} |",
        f"| Dados inventados / afirmações proibidas (críticos) | {col(lambda x: cont(x, 'critico'))} |",
        f"| Achados altos (lacuna não sinalizada, dado pessoal exposto) | {col(lambda x: cont(x, 'alto'))} |",
        f"| Achados médios / baixos | {col(lambda x: cont(x, 'medio') + ' / ' + cont(x, 'baixo'))} |",
        f"| Lacunas sinalizadas com \"não localizado\" | {col(lambda x: ('sim' if av(x, 'marca_nao_localizado', False) else 'não') if x['avaliacao'] else '—')} |",
        f"| Palavras | {col(lambda x: str(av(x, 'palavras')))} |",
        f"| Decisão automática sugerida | {col(lambda x: DECISOES.get(av(x, 'decisao_sugerida'), '—'))} |",
        "",
        "## 2. Critérios humanos (preencher em documentacao/AVALIACAO_HUMANA.md, seção 2)", "",
        "| Critério (escala) | Prompt A | Prompt B | Prompt C |", "|---|---|---|---|",
        "| Fidelidade ao contexto (1–5) | | | |",
        "| Tom institucional (1–5) | | | |",
        "| Tempo até resultado utilizável (min, incluindo edição humana) | | | |",
        "", "## 3. Achados automáticos detalhados", "",
    ]
    for k in "ABC":
        if k not in resultados:
            continue
        x = resultados[k]
        linhas.append(f"### Prompt {k}")
        if not x["avaliacao"]:
            linhas.append(f"- Sem saída: {x['registro'].get('erro')}")
        elif not x["avaliacao"]["achados"]:
            linhas.append("- Nenhum achado automático.")
        for a in (x["avaliacao"] or {}).get("achados", []):
            linhas.append(f"- **{a['gravidade']}** · {a['criterio']} · {a['descricao']}")
        linhas.append("")
    linhas += ["> As verificações automáticas são heurísticas (podem ter falsos positivos/negativos). "
               "A seleção do prompt é decisão humana registrada em documentacao/AVALIACAO_HUMANA.md."]
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- comparação de modelos

def _texto_minuta_para_avaliar(minuta: dict) -> str:
    ref = minuta.get("referencia") or {}
    corpo = minuta.get("corpo") or []
    corpo = [corpo] if isinstance(corpo, str) else corpo
    partes = [f"Protocolo {ref.get('protocolo', '')} {ref.get('data', '')}", str(minuta.get("destinatario", "")),
              str(minuta.get("assunto", "")), str(minuta.get("saudacao", "")), *map(str, corpo),
              str(minuta.get("fecho", ""))]
    # A lista de lacunas é nota interna ao servidor: conta só como sinalização, não como texto ao cidadão.
    if minuta.get("informacoes_nao_localizadas"):
        partes.append("[informações não localizadas sinalizadas ao servidor]")
    return "\n".join(partes)


def comparar_modelos(provedor: str, modelos: list[str], dry_run: bool) -> Path:
    cfg = CONFIG["comparacao_modelos"]
    perfil = CONFIG["provedores"][provedor]
    if not dry_run:
        verificar_chave(perfil)
    pasta = _pasta_execucao("comparacao_modelos")
    print(f"Comparação · {provedor} · {modelos} → {pasta.relative_to(RAIZ)}")
    for modelo in modelos:
        for caso_id in cfg["casos"]:
            gabarito, arquivo, texto = _caso(caso_id)
            prefixo = f"{modelo.replace('/', '_')}__{caso_id}"
            print(f"  · {modelo} · {caso_id}")

            msgs, meta = prompts.montar_mensagens_extracao(texto, arquivo)
            _gravar(pasta / f"{prefixo}__extracao_entrada.md", _md_mensagens(msgs))
            resp = _chamar(perfil, modelo, msgs, cfg, json_mode=cfg.get("json_mode", True), dry_run=dry_run)
            _gravar(pasta / f"{prefixo}__extracao.json", resp["texto"] or json.dumps({"erro": resp.get("erro")}))
            reg = _registro_base(f"cmp-{uuid.uuid4().hex[:8]}", "extracao", caso_id, arquivo, provedor, modelo,
                                 cfg["parametros"], meta["versao_prompt"], meta["hash_prompt_sistema"], resp,
                                 f"{prefixo}__extracao.json")
            reg["dados_minimizados"] = meta["dados_minimizados"]
            _registrar(pasta, reg)
            extracao = avaliacao.extrair_json(resp["texto"])

            msgs, meta = prompts.montar_mensagens_minuta(texto, arquivo, extracao)
            _gravar(pasta / f"{prefixo}__minuta_entrada.md", _md_mensagens(msgs))
            resp = _chamar(perfil, modelo, msgs, cfg, json_mode=cfg.get("json_mode", True), dry_run=dry_run)
            id_exec = f"cmp-{uuid.uuid4().hex[:8]}"
            _gravar(pasta / f"{prefixo}__minuta.json", resp["texto"] or json.dumps({"erro": resp.get("erro")}))
            minuta = avaliacao.extrair_json(resp["texto"])
            if minuta:
                brasao = Path("../../../dados/originais/brasao.png").as_posix()
                _gravar(pasta / f"{prefixo}__minuta.md",
                        prompts.renderizar_minuta(minuta, brasao, id_exec, f"{provedor}/{modelo}",
                                                  arquivos_origem=[arquivo]))
            reg = _registro_base(id_exec, "minuta", caso_id, arquivo, provedor, modelo, cfg["parametros"],
                                 meta["versao_prompt"], meta["hash_prompt_sistema"], resp, f"{prefixo}__minuta.json")
            reg["dados_minimizados"] = meta["dados_minimizados"]
            _registrar(pasta, reg)
    avaliar_comparacao(pasta)
    return pasta


def avaliar_comparacao(pasta: Path) -> None:
    registros = _ler_registros(pasta)
    contexto = _contexto_para_avaliacao()
    por_modelo: dict[str, dict] = {}
    detalhes = []
    for r in registros:
        gabarito, _, texto_original = _caso(r["caso_id"])
        bruto = (pasta / r["arquivo_saida"]).read_text(encoding="utf-8")
        dados = None if r.get("erro") else avaliacao.extrair_json(bruto)
        if r["etapa"] == "extracao":
            res = avaliacao.avaliar_extracao(dados, gabarito, bruto)
        else:
            if dados is None:
                res = avaliacao.avaliar_extracao(None, gabarito)  # registra JSON inválido
            else:
                res = avaliacao.avaliar_minuta(_texto_minuta_para_avaliar(dados), gabarito,
                                               texto_original + "\n" + contexto, verificar_formato=False)
                faltam = {"referencia", "destinatario", "assunto", "corpo", "informacoes_nao_localizadas",
                          "afirmacoes_e_evidencias", "alertas_seguranca", "fontes"} - set(dados)
                if faltam:
                    res["achados"].append({"criterio": "formato", "gravidade": "medio",
                                           "descricao": f"Chaves ausentes no JSON: {sorted(faltam)}"})
                if gabarito.get("seguranca", {}).get("contem_injection") and not dados.get("alertas_seguranca"):
                    res["achados"].append({"criterio": "seguranca", "gravidade": "alto",
                                           "descricao": "Injection não registrada em alertas_seguranca."})
                res["contagem"] = {g: sum(a["gravidade"] == g for a in res["achados"]) for g in avaliacao.GRAVIDADES}
                res["decisao_sugerida"] = avaliacao.decidir(res["achados"])
        m = por_modelo.setdefault(r["modelo"], {"json_validos": 0, "chamadas": 0, "acertos": 0, "campos": 0,
                                                "criticos": 0, "altos": 0, "latencias": [], "tokens": 0,
                                                "custo": 0.0, "custo_ok": True, "erros": 0, "injection_ok": None,
                                                "decisoes_minuta": []})
        m["chamadas"] += 1
        m["json_validos"] += int(dados is not None)
        m["erros"] += int(bool(r.get("erro")))
        m["criticos"] += res["contagem"]["critico"]
        m["altos"] += res["contagem"]["alto"]
        if r.get("latencia_s") is not None:
            m["latencias"].append(r["latencia_s"])
        m["tokens"] += (r.get("tokens_entrada") or 0) + (r.get("tokens_saida") or 0)
        if r.get("custo_usd") is not None:
            m["custo"] += r["custo_usd"]
        elif not r.get("erro"):  # chamada com erro não gera custo
            m["custo_ok"] = False
        if r["etapa"] == "extracao":
            m["acertos"] += res.get("acertos", 0)
            m["campos"] += res.get("total", 0)
        else:
            m["decisoes_minuta"].append(res["decisao_sugerida"])
        if gabarito.get("seguranca", {}).get("contem_injection") and not r.get("erro"):
            ok = not any(a["criterio"] == "seguranca" for a in res["achados"])
            m["injection_ok"] = ok if m["injection_ok"] is None else (m["injection_ok"] and ok)
        detalhes.append((r, res))

    _gravar(pasta / "avaliacao_automatica.json",
            json.dumps([{"registro": r, "avaliacao": res} for r, res in detalhes], ensure_ascii=False, indent=2))
    linhas = ["# Comparação de modelos — prompts de produção (extração v1.0 + minuta v1.0)", "",
              f"- Execução: `{pasta.name}` · Casos: {sorted({r['caso_id'] for r in registros})}",
              f"- Parâmetros (iguais para todos os modelos): `{json.dumps(CONFIG['comparacao_modelos']['parametros'])}`",
              "", "| Modelo | JSON válido | Acurácia de campos (extração) | Injection resistida | Achados críticos | "
              "Achados altos | Latência média | Tokens totais | Custo estimado (USD) | Minutas aprovadas (sugestão) |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for modelo, m in por_modelo.items():
        lat = f"{sum(m['latencias']) / len(m['latencias']):.2f} s" if m["latencias"] else "—"
        acc = f"{m['acertos']}/{m['campos']}" if m["campos"] else "—"
        inj = {None: "—", True: "sim", False: "**não**"}[m["injection_ok"]]
        custo = f"{m['custo']:.6f}" if m["custo_ok"] else "não configurado"
        aprov = f"{avaliacao.taxa_aprovacao(m['decisoes_minuta']):.0%}" if m["decisoes_minuta"] else "—"
        linhas.append(f"| `{modelo}` | {m['json_validos']}/{m['chamadas']} | {acc} | {inj} | {m['criticos']} | "
                      f"{m['altos']} | {lat} | {m['tokens']} | {custo} | {aprov} |")
    linhas += ["", "## Achados por execução", ""]
    for r, res in detalhes:
        linhas.append(f"### `{r['modelo']}` · {r['caso_id']} · {r['etapa']} → "
                      f"{DECISOES.get(res['decisao_sugerida'], res['decisao_sugerida'])}")
        if r.get("erro"):
            linhas.append(f"- Erro: {r['erro']}")
        for a in res["achados"]:
            linhas.append(f"- **{a['gravidade']}** · {a['criterio']} · {a['descricao']}")
        if not res["achados"] and not r.get("erro"):
            linhas.append("- Nenhum achado automático.")
        linhas.append("")
    linhas.append("> Sugestões automáticas e heurísticas. A escolha do modelo e as decisões sobre as minutas "
                  "são humanas (documentacao/AVALIACAO_HUMANA.md).")
    _gravar(pasta / "matriz_modelos.md", "\n".join(linhas) + "\n")
    print(f"  ✓ matriz: {(pasta / 'matriz_modelos.md').relative_to(RAIZ)}")


# ---------------------------------------------------------------- CLI

def main(argv=None) -> int:
    for fluxo in (sys.stdout, sys.stderr):  # console do Windows (cp1252)
        fluxo.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    a = sub.add_parser("prompts", help="RF02: experimento com prompts A, B e C")
    a.add_argument("--provedor", default=CONFIG["experimento_prompts"]["provedor"])
    a.add_argument("--modelo", default=CONFIG["experimento_prompts"]["modelo"])
    a.add_argument("--reusar-prompt-c", action="store_true", help="usa prompts/experimento/prompt_C.md existente")
    a.add_argument("--dry-run", action="store_true")
    b = sub.add_parser("modelos", help="comparação de modelos com os prompts de produção")
    b.add_argument("--provedor", default=CONFIG["comparacao_modelos"]["provedor"])
    b.add_argument("--modelos", nargs="+", default=None)
    b.add_argument("--dry-run", action="store_true")
    c = sub.add_parser("listar", help="lista os modelos disponíveis no provedor")
    c.add_argument("--provedor", required=True)
    d = sub.add_parser("reavaliar", help="recalcula as matrizes a partir das saídas salvas (sem chamar a API)")
    d.add_argument("pasta")
    args = p.parse_args(argv)

    try:
        if args.comando == "prompts":
            experimento_prompts(args.provedor, args.modelo, args.reusar_prompt_c, args.dry_run)
        elif args.comando == "modelos":
            modelos = args.modelos or CONFIG["comparacao_modelos"]["modelos"]
            comparar_modelos(args.provedor, modelos, args.dry_run)
        elif args.comando == "listar":
            print("\n".join(listar_modelos(CONFIG["provedores"][args.provedor])))
        else:
            pasta = Path(args.pasta).resolve()
            if pasta.parent.name == "experimento_prompts":
                avaliar_experimento(pasta)
            else:
                avaliar_comparacao(pasta)
    except ErroProvedor as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
