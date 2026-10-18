"""RF06: transcrição Groq, evidências e confirmação humana antes da minuta.

O gabarito é lido somente após a chamada: nunca é enviado ao modelo.
Revisão inicial por CLI; nenhuma aprovação é inferida de métricas automáticas.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import time
import unicodedata
from pathlib import Path

import httpx
from dotenv import load_dotenv

from src import audit, prompts
from src.llm_client import ErroProvedor, verificar_chave

RAIZ = prompts.RAIZ
EXTENSOES = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}


def configurar() -> dict:
    load_dotenv(RAIZ / ".env")
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def validar_audio(caminho: Path, max_bytes: int) -> Path:
    caminho = Path(caminho).resolve()
    if not caminho.is_file():
        raise ValueError("Arquivo de áudio não encontrado.")
    if caminho.suffix.lower() not in EXTENSOES:
        raise ValueError(f"Extensão de áudio não suportada: {caminho.suffix}.")
    if not 0 < caminho.stat().st_size <= max_bytes:
        raise ValueError(f"O áudio deve ter entre 1 e {max_bytes} bytes.")
    return caminho


def _palavras(texto: str) -> list[str]:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.findall(r"\w+", texto)


def comparar_transcricao(texto: str, referencia: str, campos: dict | None = None) -> dict:
    """WER por distância de edição; diferenças de grafia/números exigem revisão.

    Ignora caixa, acentos e pontuação. Não converte datas/números por extenso.
    As divergências ilustrativas usam alinhamento difflib, não são a decomposição do WER.
    """
    linhas = [l for l in referencia.splitlines() if l.strip()
              and not l.upper().startswith(("TRANCRIÇÃO DO ARQUIVO", "TRANSCRIÇÃO DO ARQUIVO"))
              and not re.fullmatch(r"[=\s]+", l)]
    ref, obt = _palavras("\n".join(linhas)), _palavras(texto)
    anterior = list(range(len(obt) + 1))
    for i, palavra in enumerate(ref, 1):
        atual = [i]
        for j, outra in enumerate(obt, 1):
            atual.append(min(atual[-1] + 1, anterior[j] + 1, anterior[j - 1] + (palavra != outra)))
        anterior = atual
    diferencas = [
        {"tipo": op, "referencia": " ".join(ref[i:j]), "obtido": " ".join(obt[k:l])}
        for op, i, j, k, l in difflib.SequenceMatcher(None, ref, obt, autojunk=False).get_opcodes()
        if op != "equal"
    ]
    # A métrica normalizada perde símbolos importantes, como @ em e-mails.
    ref_literal, obt_literal = "\n".join(linhas).split(), texto.split()
    diferencas_literais = [
        {"tipo": op, "referencia": " ".join(ref_literal[i:j]), "obtido": " ".join(obt_literal[k:l])}
        for op, i, j, k, l in difflib.SequenceMatcher(None, ref_literal, obt_literal, autojunk=False).get_opcodes()
        if op != "equal"
    ]
    conferencia = []
    for grupo in ("nomes", "numeros_de_protocolo", "datas"):
        for valor in (campos or {}).get(grupo, []):
            tokens = _palavras(valor)
            encontrado = any(obt[i:i + len(tokens)] == tokens for i in range(len(obt)))
            conferencia.append({"campo": grupo, "esperado": valor,
                                "correspondencia_textual": encontrado,
                                "requer_conferencia_humana": True})
    return {"distancia_edicao": anterior[-1], "palavras_referencia": len(ref),
            "wer": round(anterior[-1] / len(ref), 4) if ref else None,
            "diferencas": diferencas, "diferencas_literais": diferencas_literais, "campos_criticos": conferencia,
            "aviso": "WER normalizado ignora pontuação; confira diferenças literais (ex.: @). "
                     "Correspondência textual não comprova correção; números por extenso podem divergir."}


def _chamar_groq(caminho: Path, cfg: dict, perfil: dict) -> dict:
    chave = verificar_chave(perfil)
    inicio = time.perf_counter()
    tentativas = max(1, int(cfg["tentativas"]))
    erro = ErroProvedor("Transcrição indisponível.")
    for tentativa in range(1, tentativas + 1):
        espera = min(30, cfg.get("pausa_base_s", 2) * tentativa)
        try:
            with caminho.open("rb") as arquivo:
                resposta = httpx.post(
                    perfil["base_url"].rstrip("/") + "/audio/transcriptions",
                    headers={"Authorization": f"Bearer {chave}"},
                    files={"file": (caminho.name, arquivo)},
                    data={"model": cfg["modelo"], "language": cfg["idioma"],
                          "temperature": str(cfg["temperature"]), "response_format": "verbose_json"},
                    timeout=cfg["timeout_s"],
                )
            status = resposta.status_code
            if status in (401, 403):
                raise ErroProvedor("Autenticação do Groq recusada; confira GROQ_API_KEY.",
                                   "autenticacao_invalida", status)
            if status == 429 or status >= 500:
                erro = ErroProvedor(f"Groq indisponível para transcrição (HTTP {status}).",
                                   "limite_requisicoes" if status == 429 else "servico_indisponivel", status)
                try:
                    espera = min(30, max(0, float(resposta.headers.get("retry-after", espera))))
                except ValueError:
                    pass
            elif status >= 400:
                raise ErroProvedor(f"Groq recusou o áudio (HTTP {status}); confira formato e modelo.",
                                   "requisicao_invalida", status)
            else:
                try:
                    dados = resposta.json()
                    texto = dados.get("text")
                    duracao = float(dados["duration"])
                    idioma = dados.get("language")
                    if (not isinstance(texto, str) or not texto.strip() or not idioma
                            or not math.isfinite(duracao) or duracao <= 0):
                        raise ValueError
                except (ValueError, KeyError, TypeError, AttributeError):
                    erro = ErroProvedor("Transcrição vazia ou sem idioma/duração válidos.", "resposta_invalida")
                else:
                    return {"texto": texto, "idioma": idioma, "duracao_audio_s": duracao,
                            "segmentos": dados.get("segments", []), "tentativas": tentativa,
                            "latencia_s": round(time.perf_counter() - inicio, 3),
                            "custo_usd": round(max(duracao, cfg["minimo_faturado_s"]) / 3600
                                               * cfg["preco_usd_hora"], 6)}
        except httpx.TimeoutException:
            erro = ErroProvedor("Tempo limite excedido na transcrição.", "timeout")
        except httpx.HTTPError:
            erro = ErroProvedor("Falha de conexão com o Groq na transcrição.", "servico_indisponivel")
        if tentativa < tentativas:
            time.sleep(espera)
    raise erro


def _salvar_json(caminho: Path, dados: dict) -> None:
    caminho.write_text(json.dumps(audit.sanitizar_dados(dados), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _registrar(meta: dict, caminho_log: Path | None, erro: str | None = None) -> None:
    registro = audit.criar_registro(
        id_execucao=meta["id_execucao"], caso_id=meta["caso_id"], etapa="transcricao",
        modalidade="audio", arquivo_origem=meta["arquivo_origem"], provedor=meta["provedor"],
        modelo=meta["modelo"], parametros=meta["parametros"], resposta_llm=meta,
        arquivo_saida=meta.get("arquivo_metadados"), decisao_humana=meta.get("decisao_humana", "PENDENTE"),
        revisor=meta.get("revisor"), justificativa_humana=meta.get("justificativa_humana"), erro=erro,
    )
    registro.update({k: meta.get(k) for k in ("sha256_origem", "duracao_audio_s", "idioma", "sha256_revisado")})
    audit.registrar_execucao(registro, caminho_log=caminho_log)


def transcrever_audio(caminho: Path, *, caso_id: str = "caso02_audio", config: dict | None = None,
                      caminho_log: Path | None = None) -> dict:
    config = config or configurar()
    cfg = config["transcricao"]
    if cfg["provedor"] != "groq":
        raise ValueError("O RF06 implementa o provedor Groq; configure transcricao.provedor=groq.")
    caminho = validar_audio(caminho, cfg["max_bytes"])
    id_execucao = audit.gerar_id_execucao("stt")
    pasta = (RAIZ / cfg["diretorio"] / id_execucao).resolve()
    if not pasta.is_relative_to((RAIZ / "resultados").resolve()):
        raise ValueError("As transcrições devem ser salvas dentro de resultados/.")
    origem = str(caminho.relative_to(RAIZ)) if caminho.is_relative_to(RAIZ) else str(caminho)
    meta = {"id_execucao": id_execucao, "data_hora": audit.agora_iso(), "caso_id": caso_id,
            "arquivo_origem": origem, "sha256_origem": hash_arquivo(caminho),
            "provedor": cfg["provedor"], "modelo": cfg["modelo"], "decisao_humana": "PENDENTE",
            "parametros": {k: cfg[k] for k in ("idioma", "temperature", "timeout_s", "tentativas")},
            "preco_usd_hora": cfg["preco_usd_hora"], "fonte_preco": cfg["fonte_preco"],
            "data_consulta_preco": cfg["data_consulta_preco"]}
    try:
        meta.update(_chamar_groq(caminho, cfg, config["provedores"][cfg["provedor"]]))
    except ErroProvedor as exc:
        _registrar(meta, caminho_log, str(exc))
        raise
    pasta.mkdir(parents=True)
    (pasta / "bruta.txt").write_text(meta.pop("texto"), encoding="utf-8")
    # Cópia editável para revisão; não é considerada conferida até a confirmação explícita.
    (pasta / "revisada.txt").write_bytes((pasta / "bruta.txt").read_bytes())
    meta["sha256_bruta"] = hash_arquivo(pasta / "bruta.txt")
    meta["arquivo_metadados"] = str((pasta / "metadados.json").relative_to(RAIZ))
    gab_path = RAIZ / config["caminhos"]["gabaritos"] / f"{caso_id}.json"
    if gab_path.is_file():
        gab = json.loads(gab_path.read_text(encoding="utf-8"))
        ref = RAIZ / gab.get("transcricao_referencia", "")
        if (RAIZ / gab.get("arquivo_origem", "")).resolve() == caminho and ref.is_file():
            meta["referencia"] = str(ref.relative_to(RAIZ))
            meta["sha256_referencia"] = hash_arquivo(ref)
            comparacao = comparar_transcricao((pasta / "bruta.txt").read_text(encoding="utf-8"),
                                             ref.read_text(encoding="utf-8"), gab.get("campos_criticos_esperados"))
            _salvar_json(pasta / "comparacao.json", comparacao)
    _salvar_json(pasta / "metadados.json", meta)
    _registrar(meta, caminho_log)
    return {**meta, "texto": (pasta / "bruta.txt").read_text(encoding="utf-8")}


def confirmar_revisao(pasta: Path, revisor: str, justificativa: str, *,
                      campos_confirmados: bool, caminho_log: Path | None = None) -> dict:
    pasta = pasta.resolve()
    if not pasta.is_relative_to((RAIZ / "resultados").resolve()):
        raise ValueError("A revisão deve estar dentro de resultados/.")
    if not revisor.strip() or not justificativa.strip() or not campos_confirmados:
        raise ValueError("Informe revisor, justificativa e confirme nomes, protocolos e datas após ouvir o áudio.")
    meta = json.loads((pasta / "metadados.json").read_text(encoding="utf-8"))
    if meta.get("decisao_humana") == "Conferido":
        raise ValueError("Esta revisão já foi confirmada. Gere outra transcrição para uma nova revisão.")
    if hash_arquivo(RAIZ / meta["arquivo_origem"]) != meta["sha256_origem"]:
        raise ValueError("O áudio mudou desde a transcrição; processe novamente.")
    if hash_arquivo(pasta / "bruta.txt") != meta["sha256_bruta"]:
        raise ValueError("A transcrição bruta foi alterada; processe novamente.")
    texto = (pasta / "revisada.txt").read_text(encoding="utf-8").strip()
    if not texto:
        raise ValueError("A transcrição revisada não pode estar vazia.")
    meta.update(decisao_humana="Conferido", revisor=revisor.strip(),
                justificativa_humana=justificativa.strip(), data_revisao=audit.agora_iso(),
                sha256_revisado=hash_arquivo(pasta / "revisada.txt"))
    _salvar_json(pasta / "metadados.json", meta)
    _registrar(meta, caminho_log)
    return meta


def obter_transcricao_confirmada(caminho: Path, *, caso_id: str, config: dict | None = None) -> dict:
    config = config or configurar()
    cfg = config["transcricao"]
    caminho = validar_audio(caminho, cfg["max_bytes"])
    candidatos = sorted((RAIZ / cfg["diretorio"]).glob("*/metadados.json"),
                        key=lambda p: p.stat().st_mtime_ns, reverse=True)
    for arquivo in candidatos:
        meta = json.loads(arquivo.read_text(encoding="utf-8"))
        if (meta.get("caso_id") != caso_id or meta.get("sha256_origem") != hash_arquivo(caminho)
                or meta.get("decisao_humana") != "Conferido"):
            continue
        revisada = arquivo.parent / "revisada.txt"
        if (hash_arquivo(revisada) != meta.get("sha256_revisado")
                or hash_arquivo(arquivo.parent / "bruta.txt") != meta.get("sha256_bruta")):
            raise ValueError("Transcrição alterada após conferência; faça uma nova transcrição e revisão.")
        return {**meta, "texto": revisada.read_text(encoding="utf-8")}
    raise ValueError("Áudio sem transcrição confirmada. Execute python -m src.audio transcrever e depois revisar; "
                     "confira nomes, protocolos e datas antes da minuta.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    trans = sub.add_parser("transcrever", help="Transcreve no Groq e salva evidências pendentes de revisão.")
    trans.add_argument("--arquivo", type=Path, default=RAIZ / "dados/originais/entrada_audio.mp3")
    trans.add_argument("--caso", default="caso02_audio")
    revisao = sub.add_parser("revisar", help="Confirma a revisão humana feita ouvindo o áudio original.")
    revisao.add_argument("pasta", type=Path)
    revisao.add_argument("--revisor", required=True, help="Identificador fictício do revisor no protótipo.")
    revisao.add_argument("--justificativa", required=True)
    revisao.add_argument("--confirmar-campos", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.comando == "transcrever":
            res = transcrever_audio(args.arquivo, caso_id=args.caso)
            print(f"Transcrição salva: {res['arquivo_metadados']}")
            print("PENDENTE: ouça o original, edite revisada.txt e confirme os campos críticos com o comando revisar.")
        else:
            confirmar_revisao(args.pasta, args.revisor, args.justificativa, campos_confirmados=args.confirmar_campos)
            print("Conferência humana registrada. A transcrição está disponível para gerar a minuta.")
    except (ErroProvedor, ValueError, OSError) as exc:
        from src.llm_client import ocultar_segredos
        print(f"Erro: {ocultar_segredos(str(exc))}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
