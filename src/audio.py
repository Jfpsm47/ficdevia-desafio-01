"""RF06: transcrição Groq, evidências e confirmação humana antes da minuta.

O gabarito é lido somente após a chamada: nunca é enviado ao modelo.
Revisão inicial por CLI; nenhuma aprovação é inferida de métricas automáticas.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import math
import re
import time
import unicodedata
import wave
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv
from piper import PiperVoice, SynthesisConfig

from src import audit, prompts
from src.llm_client import ErroProvedor, verificar_chave

RAIZ = prompts.RAIZ
EXTENSOES = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}
DECISAO_APROVADA = "aprovada"


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


# ---------------------------------------------------------------- Síntese de voz e acessibilidade (RF07)

def _limpar_texto_para_voz(texto_minuta: str) -> str:
    """Mantém o conteúdo destinado ao cidadão e remove apenas metadados técnicos da minuta.

    Não elimina a seção de informações não localizadas: ela deve ser ouvida para que uma lacuna
    não seja apresentada como fato. A aprovação humana já aconteceu antes desta função ser usada.
    """
    linhas: list[str] = []
    for linha in texto_minuta.splitlines():
        limpa = linha.strip()
        if limpa.startswith("**Rastreabilidade:**") or limpa.startswith("**Decisão humana:**"):
            break
        if (not limpa or limpa.startswith("![") or "MINUTA GERADA COM APOIO DE IA" in limpa
                or limpa in {"---"}):
            continue
        limpa = re.sub(r"^#{1,6}\s*", "", limpa)
        limpa = re.sub(r"^>\s*", "", limpa)
        limpa = re.sub(r"^[-*]\s+", "", limpa)
        limpa = limpa.replace("**", "").replace("`", "")
        if limpa:
            linhas.append(limpa)
    texto = "\n".join(linhas).strip()
    if not texto:
        raise ValueError("A minuta aprovada não contém texto utilizável para a síntese de voz.")
    return texto


def _dividir_texto_para_voz(texto: str, limite: int) -> list[str]:
    """Divide por frases e palavras sem descartar conteúdo, respeitando o limite da API."""
    if limite < 40:
        raise ValueError("O limite de caracteres por trecho de voz deve ser de pelo menos 40.")
    normalizado = re.sub(r"\s+", " ", texto).strip()
    if not normalizado:
        raise ValueError("O texto para síntese de voz está vazio.")
    partes: list[str] = []
    atual = ""
    for frase in re.split(r"(?<=[.!?;:])\s+", normalizado):
        if len(frase) <= limite and len(atual) + len(frase) + (1 if atual else 0) <= limite:
            atual = f"{atual} {frase}".strip()
            continue
        if atual:
            partes.append(atual)
            atual = ""
        palavras = frase.split()
        while palavras:
            trecho = ""
            while palavras and len(trecho) + len(palavras[0]) + (1 if trecho else 0) <= limite:
                trecho = f"{trecho} {palavras.pop(0)}".strip()
            if not trecho:
                raise ValueError("Há uma palavra maior que o limite de caracteres da síntese de voz.")
            if palavras:
                partes.append(trecho)
            else:
                atual = trecho
    if atual:
        partes.append(atual)
    return partes


def _validar_wav(conteudo: bytes) -> tuple[wave._wave_params, bytes]:
    """Valida um WAV PCM e devolve seus parâmetros e amostras."""
    try:
        with wave.open(io.BytesIO(conteudo), "rb") as leitor:
            parametros = leitor.getparams()
            amostras = leitor.readframes(leitor.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError("O arquivo WAV não é válido.") from exc
    if not amostras or parametros.comptype != "NONE":
        raise ValueError("O arquivo WAV retornado não possui áudio PCM utilizável.")
    return parametros, amostras


def _caminho_modelo_piper(cfg: dict, chave: str) -> Path:
    caminho = (RAIZ / cfg[chave]).resolve()
    cache = (RAIZ / ".cache/piper").resolve()
    if not caminho.is_relative_to(cache):
        raise ValueError("Os arquivos do modelo Piper devem ficar em .cache/piper/.")
    if not caminho.is_file():
        raise ValueError(
            f"Arquivo Piper ausente: {caminho.relative_to(RAIZ)}. Execute o comando de instalação do README "
            "antes de sintetizar."
        )
    return caminho


def _pcm16(audio_float: np.ndarray) -> bytes:
    """Converte a saída normalizada do Piper em PCM 16-bit para WAV."""
    return np.rint(np.clip(audio_float, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def _chamar_piper_tts(texto: str, cfg: dict) -> dict:
    """Sintetiza localmente, sem enviar texto ou credenciais a um serviço externo."""
    modelo = _caminho_modelo_piper(cfg, "arquivo_modelo")
    configuracao = _caminho_modelo_piper(cfg, "arquivo_config_modelo")
    inicio = time.perf_counter()
    try:
        voz = PiperVoice.load(modelo, config_path=configuracao)
        ajustes = SynthesisConfig(
            length_scale=float(cfg["length_scale"]),
            noise_scale=float(cfg["noise_scale"]),
            noise_w_scale=float(cfg["noise_w_scale"]),
            volume=float(cfg["volume"]),
        )
        blocos = _dividir_texto_para_voz(texto, int(cfg["max_caracteres_por_trecho"]))
        amostras: list[bytes] = []
        taxa_amostragem: int | None = None
        segmentos = 0
        for indice, bloco in enumerate(blocos):
            for trecho in voz.synthesize(bloco, syn_config=ajustes):
                if trecho.sample_width != 2 or trecho.sample_channels != 1:
                    raise ValueError("O modelo Piper retornou um formato de áudio não suportado.")
                if taxa_amostragem is None:
                    taxa_amostragem = trecho.sample_rate
                elif taxa_amostragem != trecho.sample_rate:
                    raise ValueError("O modelo Piper retornou taxas de amostragem incompatíveis.")
                amostras.append(_pcm16(trecho.audio_float_array))
                segmentos += 1
            if indice < len(blocos) - 1 and taxa_amostragem is not None:
                pausa_amostras = round(taxa_amostragem * int(cfg["pausa_entre_trechos_ms"]) / 1000)
                amostras.append(b"\x00\x00" * pausa_amostras)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Não foi possível sintetizar com o Piper local: {exc}") from exc
    if taxa_amostragem is None or not amostras:
        raise ValueError("O Piper não retornou áudio utilizável.")
    destino = io.BytesIO()
    with wave.open(destino, "wb") as escritor:
        escritor.setnchannels(1)
        escritor.setsampwidth(2)
        escritor.setframerate(taxa_amostragem)
        escritor.writeframes(b"".join(amostras))
    audio = destino.getvalue()
    _validar_wav(audio)
    return {
        "audio": audio,
        "tentativas": 1,
        "latencia_s": round(time.perf_counter() - inicio, 3),
        "caracteres_entrada": len(texto),
        "custo_usd": 0.0,
        "blocos_texto": len(blocos),
        "segmentos_audio": segmentos,
        "taxa_amostragem_hz": taxa_amostragem,
    }


def obter_minuta_aprovada(caso_id: str, *, caminho_log: Path | None = None) -> dict:
    """Obtém exclusivamente a última minuta com decisão humana Aprovada."""
    registros = [r for r in audit.ler_registros(caminho_log)
                 if r.get("caso_id") == caso_id and r.get("etapa") == "minuta"]
    if not registros:
        raise ValueError("Não há minuta registrada para este caso.")
    minuta = registros[-1]
    if str(minuta.get("decisao_humana", "")).casefold() != DECISAO_APROVADA:
        raise ValueError("A síntese de voz exige uma minuta com decisão humana Aprovada.")
    saida = Path(str(minuta.get("arquivo_saida") or ""))
    caminho = (RAIZ / saida).resolve() if not saida.is_absolute() else saida.resolve()
    minutas = (RAIZ / "resultados/minutas").resolve()
    if not caminho.is_relative_to(minutas) or not caminho.is_file():
        raise ValueError("O arquivo da minuta aprovada não está disponível em resultados/minutas/.")
    from src import main
    texto_minuta = main.ler_texto_minuta_pdf(caminho)
    if not re.search(r"^\*\*Decisão humana:\*\*.*Status:\s*\*\*Aprovada\*\*", texto_minuta,
                     flags=re.IGNORECASE | re.MULTILINE):
        raise ValueError("O arquivo da minuta não comprova a decisão Aprovada registrada na auditoria.")
    texto_falado = _limpar_texto_para_voz(texto_minuta)
    return {"registro": minuta, "caminho": caminho, "texto_falado": texto_falado}


def sintetizar_minuta_aprovada(caso_id: str, *, config: dict | None = None,
                               caminho_log: Path | None = None) -> dict:
    """Gera uma única versão WAV de uma minuta aprovada e registra a evidência (RF07)."""
    config = config or configurar()
    cfg = config["sintese_voz"]
    if cfg["provedor"] != "piper_local" or cfg["formato"].casefold() != "wav":
        raise ValueError("O RF07 está configurado para Piper local e saída WAV.")
    origem = obter_minuta_aprovada(caso_id, caminho_log=caminho_log)
    texto = origem["texto_falado"]
    if len(texto) > int(cfg["max_caracteres_total"]):
        raise ValueError("A minuta aprovada excede o limite total de caracteres para síntese de voz.")
    trechos = _dividir_texto_para_voz(texto, int(cfg["max_caracteres_por_trecho"]))
    id_execucao = audit.gerar_id_execucao("tts")
    pasta = (RAIZ / cfg["diretorio"] / id_execucao).resolve()
    if not pasta.is_relative_to((RAIZ / "resultados").resolve()):
        raise ValueError("As evidências de síntese devem ser salvas dentro de resultados/.")
    arquivo_audio = pasta / "minuta.wav"
    arquivo_texto = pasta / "texto_falado.txt"
    meta = {
        "id_execucao": id_execucao, "data_hora": audit.agora_iso(), "caso_id": caso_id,
        "etapa_origem": "minuta", "id_minuta": origem["registro"].get("id_execucao"),
        "arquivo_minuta": str(origem["caminho"].relative_to(RAIZ)),
        "sha256_minuta": hash_arquivo(origem["caminho"]),
        "sha256_texto_falado": hashlib.sha256((texto + "\n").encode("utf-8")).hexdigest(),
        "provedor": cfg["provedor"], "modelo": cfg["modelo"], "voz": cfg["voz"],
        "direcao": cfg["direcao"], "formato": cfg["formato"], "trechos": len(trechos),
        "decisao_humana_origem": origem["registro"].get("decisao_humana"),
        "revisor_origem": origem["registro"].get("revisor"),
        "decisao_humana": "PENDENTE",
        "revisor": None,
        "justificativa_humana": None,
        "parametros": {k: cfg[k] for k in ("length_scale", "noise_scale", "noise_w_scale", "volume",
                                             "pausa_entre_trechos_ms", "max_caracteres_por_trecho")},
        "arquivo_modelo": cfg["arquivo_modelo"],
        "arquivo_config_modelo": cfg["arquivo_config_modelo"],
        "licenca_modelo": cfg["licenca_modelo"],
        "licenca_runtime": cfg["licenca_runtime"],
        "fonte_modelo": cfg["fonte_modelo"], "data_consulta_modelo": cfg["data_consulta_modelo"],
        "arquivo_texto_falado": str(arquivo_texto.relative_to(RAIZ)),
        "arquivo_audio": str(arquivo_audio.relative_to(RAIZ)),
        "arquivo_metadados": str((pasta / "metadados.json").relative_to(RAIZ)),
    }
    try:
        resposta = _chamar_piper_tts(texto, cfg)
        pasta.mkdir(parents=True)
        arquivo_texto.write_text(texto + "\n", encoding="utf-8")
        arquivo_audio.write_bytes(resposta["audio"])
        meta.update(tentativas=resposta["tentativas"], latencia_s=resposta["latencia_s"],
                    caracteres_entrada=resposta["caracteres_entrada"], custo_usd=resposta["custo_usd"],
                    blocos_texto=resposta["blocos_texto"], segmentos_audio=resposta["segmentos_audio"],
                    taxa_amostragem_hz=resposta["taxa_amostragem_hz"],
                    sha256_audio=hash_arquivo(arquivo_audio))
        _salvar_json(pasta / "metadados.json", meta)
    except (ErroProvedor, ValueError) as exc:
        _registrar_sintese(meta, caminho_log, str(exc))
        raise
    _registrar_sintese(meta, caminho_log)
    return meta


def _registrar_sintese(meta: dict, caminho_log: Path | None, erro: str | None = None) -> None:
    registro = audit.criar_registro(
        id_execucao=meta["id_execucao"], caso_id=meta["caso_id"], etapa="sintese_voz", modalidade="audio",
        arquivo_origem=meta["arquivo_minuta"], provedor=meta["provedor"], modelo=meta["modelo"],
        parametros=meta["parametros"], resposta_llm=meta, arquivo_saida=meta.get("arquivo_audio"),
        resumo_resultado="Versão em áudio de minuta aprovada; sem envio automático.",
        decisao_humana=meta.get("decisao_humana", "PENDENTE"), revisor=meta.get("revisor"),
        justificativa_humana=meta.get("justificativa_humana"), erro=erro,
    )
    registro.update({k: meta.get(k) for k in ("id_minuta", "sha256_minuta", "sha256_texto_falado", "sha256_audio")})
    audit.registrar_execucao(registro, caminho_log=caminho_log)


def confirmar_sintese(pasta: Path, revisor: str, justificativa: str, *, decisao: str,
                      correspondencia_confirmada: bool, caminho_log: Path | None = None) -> dict:
    """Registra a escuta humana do WAV sem confundir a aprovação da minuta com a do áudio."""
    pasta = pasta.resolve()
    audios = (RAIZ / "resultados/audios").resolve()
    if not pasta.is_relative_to(audios):
        raise ValueError("A revisão da síntese deve estar dentro de resultados/audios/.")
    if decisao not in {"Aprovada", "Rejeitada"}:
        raise ValueError("A decisão da síntese deve ser Aprovada ou Rejeitada.")
    if not revisor.strip() or not justificativa.strip():
        raise ValueError("Informe revisor e justificativa para a escuta humana.")
    if decisao == "Aprovada" and not correspondencia_confirmada:
        raise ValueError("Confirme a correspondência com a minuta antes de aprovar o áudio.")
    metadados = pasta / "metadados.json"
    if not metadados.is_file():
        raise ValueError("Metadados da síntese não encontrados.")
    meta = json.loads(metadados.read_text(encoding="utf-8"))
    if meta.get("decisao_humana") not in (None, "PENDENTE"):
        raise ValueError("Esta síntese já possui uma decisão humana final.")
    arquivo_audio = RAIZ / meta["arquivo_audio"]
    arquivo_texto = RAIZ / meta["arquivo_texto_falado"]
    arquivo_minuta = RAIZ / meta["arquivo_minuta"]
    if (not arquivo_audio.is_file() or not arquivo_texto.is_file() or not arquivo_minuta.is_file()
            or hash_arquivo(arquivo_audio) != meta.get("sha256_audio")
            or hash_arquivo(arquivo_texto) != meta.get("sha256_texto_falado")
            or hash_arquivo(arquivo_minuta) != meta.get("sha256_minuta")):
        raise ValueError("A evidência de síntese ou a minuta de origem foi alterada; gere novamente.")
    _validar_wav(arquivo_audio.read_bytes())
    meta.update(decisao_humana=decisao, revisor=revisor.strip(), justificativa_humana=justificativa.strip(),
                data_revisao_humana=audit.agora_iso())
    if not audit.atualizar_decisao_humana(meta["id_execucao"], decisao, revisor.strip(), justificativa.strip(),
                                           caminho_log=caminho_log):
        raise ValueError("Registro de auditoria da síntese não encontrado.")
    _salvar_json(metadados, meta)
    return meta


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
    sintese = sub.add_parser("sintetizar", help="Gera WAV apenas da última minuta aprovada do caso.")
    sintese.add_argument("--caso", default="caso02_audio")
    revisao_voz = sub.add_parser("revisar-voz", help="Registra a escuta humana do WAV gerado.")
    revisao_voz.add_argument("pasta", type=Path)
    revisao_voz.add_argument("--revisor", required=True, help="Identificador fictício do revisor no protótipo.")
    revisao_voz.add_argument("--justificativa", required=True)
    revisao_voz.add_argument("--decisao", required=True, choices=("Aprovada", "Rejeitada"))
    revisao_voz.add_argument("--confirmar-correspondencia", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.comando == "transcrever":
            res = transcrever_audio(args.arquivo, caso_id=args.caso)
            print(f"Transcrição salva: {res['arquivo_metadados']}")
            print("PENDENTE: ouça o original, edite revisada.txt e confirme os campos críticos com o comando revisar.")
        elif args.comando == "revisar":
            confirmar_revisao(args.pasta, args.revisor, args.justificativa, campos_confirmados=args.confirmar_campos)
            print("Conferência humana registrada. A transcrição está disponível para gerar a minuta.")
        elif args.comando == "revisar-voz":
            confirmar_sintese(args.pasta, args.revisor, args.justificativa, decisao=args.decisao,
                              correspondencia_confirmada=args.confirmar_correspondencia)
            print("Escuta humana da síntese registrada.")
        else:
            res = sintetizar_minuta_aprovada(args.caso)
            print(f"Voz salva: {res['arquivo_audio']}")
            print("PENDENTE: ouça o WAV e registre a decisão com o comando revisar-voz.")
    except (ErroProvedor, ValueError, OSError) as exc:
        from src.llm_client import ocultar_segredos
        print(f"Erro: {ocultar_segredos(str(exc))}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
