"""Ingestão de documentos institucionais fictícios e divisão em chunks com metadados (RF17, RF18, RF20).

Responsabilidade: Estudante 2.
Lê o catálogo validado (`dados/acervo/catalogo.json`) ou arquivos avulsos (`.txt` e `.pdf` textual),
calcula o hash SHA-256 do arquivo de origem, preserva página (nos PDFs) e seção numerada, e divide o
conteúdo em trechos validados pelo contrato `TrechoIndexado` (`src/schemas.py`).
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

from src import prompts, schemas

RAIZ = prompts.RAIZ
ARQUIVO_CATALOGO_PADRAO = RAIZ / "dados" / "acervo" / "catalogo.json"
FORMATOS_SUPORTADOS = {".txt": "txt", ".pdf": "pdf"}
MAX_BYTES_DOCUMENTO_ACERVO = 10_000_000  # 10 MB

_RE_TITULO_SECAO = re.compile(r"^\s*(\d+\.\s+\S.*)$")
_RE_CABECALHO_CAMPO = re.compile(r"^\s*(Identificador|Título|Titulo|Versão|Versao|Tema|Vigência|Vigencia)\s*:\s*(.+)$", re.I)


def formatar_config_chunking(unidade: str, tamanho: int, sobreposicao: int) -> str:
    """Gera o identificador canônico da configuração de chunking (ex.: 'caracteres-700-sobreposicao-120')."""
    unidade_limpa = unidade.strip().lower()
    if unidade_limpa not in ("caracteres", "palavras"):
        raise ValueError(f"Unidade de chunking inválida: '{unidade}'. Use 'caracteres' ou 'palavras'.")
    if tamanho < 50:
        raise ValueError(f"Tamanho de chunk deve ser >= 50 ({tamanho} informado).")
    if sobreposicao < 0 or sobreposicao >= tamanho:
        raise ValueError(
            f"Sobreposição ({sobreposicao}) deve ser >= 0 e estritamente menor que o tamanho ({tamanho})."
        )
    return f"{unidade_limpa}-{tamanho}-sobreposicao-{sobreposicao}"


def calcular_hash_arquivo(caminho: Path) -> str:
    """Retorna o SHA-256 hexadecimal dos bytes originais do arquivo."""
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def carregar_catalogo(caminho_catalogo: Path | None = None) -> list[schemas.DocumentoAcervo]:
    """Lê e valida todos os documentos registrados em `dados/acervo/catalogo.json`."""
    alvo = Path(caminho_catalogo) if caminho_catalogo else ARQUIVO_CATALOGO_PADRAO
    dados = json.loads(alvo.read_text(encoding="utf-8"))
    return [schemas.DocumentoAcervo.model_validate(item) for item in dados.get("documentos", [])]


def extrair_paginas_arquivo(caminho: Path, formato: str | None = None) -> list[tuple[int | None, str]]:
    """Extrai o texto de um arquivo `.txt` (página None) ou `.pdf` textual (páginas 1..N via pypdf)."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Documento do acervo não encontrado: {caminho}")
    tamanho_bytes = caminho.stat().st_size
    if tamanho_bytes == 0:
        raise ValueError(f"Documento do acervo está vazio: {caminho}")
    if tamanho_bytes > MAX_BYTES_DOCUMENTO_ACERVO:
        raise ValueError(
            f"Documento excede o limite de {MAX_BYTES_DOCUMENTO_ACERVO} bytes ({tamanho_bytes} bytes): {caminho.name}"
        )

    fmt = (formato or FORMATOS_SUPORTADOS.get(caminho.suffix.lower()) or "").lower()
    if fmt == "txt":
        texto = caminho.read_text(encoding="utf-8")
        return [(None, _limpar_texto(texto))]
    if fmt == "pdf":
        from pypdf import PdfReader

        leitor = PdfReader(io.BytesIO(caminho.read_bytes()))
        paginas: list[tuple[int | None, str]] = []
        for indice, pagina in enumerate(leitor.pages, start=1):
            extraido = _limpar_texto(pagina.extract_text() or "")
            if extraido:
                paginas.append((indice, extraido))
        if not paginas:
            raise ValueError(f"Nenhum texto extraível encontrado no PDF: {caminho.name}")
        return paginas
    raise ValueError(f"Formato de documento não suportado para ingestão: '{fmt or caminho.suffix}'")


def _limpar_texto(texto: str) -> str:
    """Normaliza quebras de linha e espaços supérfluos preservando parágrafos e seções."""
    normalizado = texto.replace("\r\n", "\n").replace("\r", "\n")
    linhas = [re.sub(r"[ \t]+", " ", ln).strip() for ln in normalizado.split("\n")]
    resultado: list[str] = []
    em_branco_anterior = False
    for ln in linhas:
        if not ln:
            if not em_branco_anterior and resultado:
                resultado.append("")
            em_branco_anterior = True
        else:
            resultado.append(ln)
            em_branco_anterior = False
    return "\n".join(resultado).strip()


def extrair_blocos_secao(paginas: list[tuple[int | None, str]]) -> list[dict[str, Any]]:
    """Separa cada página em blocos semânticos associados à sua seção numerada ou ao cabeçalho."""
    blocos: list[dict[str, Any]] = []
    ultima_secao: str | None = None

    for num_pagina, texto_pagina in paginas:
        secao_corrente: str | None = ultima_secao if num_pagina and num_pagina > 1 else "Cabeçalho institucional"
        acumulador: list[str] = []

        for linha in texto_pagina.split("\n"):
            m = _RE_TITULO_SECAO.match(linha)
            if m:
                texto_bloco = "\n".join(acumulador).strip()
                if texto_bloco:
                    blocos.append({"pagina": num_pagina, "secao": secao_corrente, "texto": texto_bloco})
                acumulador = [linha]
                secao_corrente = m.group(1).strip()
                ultima_secao = secao_corrente
            else:
                acumulador.append(linha)

        texto_final = "\n".join(acumulador).strip()
        if texto_final:
            blocos.append({"pagina": num_pagina, "secao": secao_corrente, "texto": texto_final})

    return blocos


def _medir_unidade(texto: str, unidade: str) -> int:
    if unidade == "palavras":
        return len(re.findall(r"\S+", texto))
    return len(texto)


def _fatiar_texto_longo(texto: str, tamanho: int, sobreposicao: int, unidade: str) -> list[str]:
    """Divide um bloco maior que `tamanho` com janela deslizante respeitando fronteiras de palavras."""
    texto = texto.strip()
    if not texto:
        return []
    if _medir_unidade(texto, unidade) <= tamanho:
        return [texto]

    if unidade == "palavras":
        palavras = re.findall(r"\S+", texto)
        passo = max(1, tamanho - sobreposicao)
        fatias: list[str] = []
        inicio = 0
        while inicio < len(palavras):
            trecho = " ".join(palavras[inicio : inicio + tamanho]).strip()
            if trecho:
                fatias.append(trecho)
            if inicio + tamanho >= len(palavras):
                break
            inicio += passo
        return fatias

    # Unidade = caracteres, buscando quebra limpa em espaço ou quebra de linha próxima ao limite
    fatias_chars: list[str] = []
    inicio = 0
    n = len(texto)
    while inicio < n:
        fim_alvo = min(inicio + tamanho, n)
        if fim_alvo < n:
            margem_minima = inicio + max(int(tamanho * 0.55), 1)
            melhor_quebra = max(
                texto.rfind("\n", margem_minima, fim_alvo),
                texto.rfind(". ", margem_minima, fim_alvo),
                texto.rfind("; ", margem_minima, fim_alvo),
                texto.rfind(" ", margem_minima, fim_alvo),
            )
            fim = (melhor_quebra + 1) if melhor_quebra > inicio else fim_alvo
        else:
            fim = n

        fatia = texto[inicio:fim].strip()
        if fatia:
            fatias_chars.append(fatia)
        if fim >= n:
            break

        novo_inicio = max(inicio + 1, fim - sobreposicao)
        # Ajusta início da sobreposição para não cortar palavra ao meio
        if 0 < novo_inicio < n and not texto[novo_inicio - 1].isspace():
            prox_espaco = texto.find(" ", novo_inicio, min(novo_inicio + 35, fim))
            if prox_espaco != -1:
                novo_inicio = prox_espaco + 1
        inicio = novo_inicio

    return fatias_chars


def _sufixo_sobreposicao(texto: str, sobreposicao: int, unidade: str) -> str:
    """Extrai o final de um bloco anterior para manter continuidade semântica entre chunks."""
    if sobreposicao <= 0 or not texto:
        return ""
    if unidade == "palavras":
        palavras = re.findall(r"\S+", texto)
        return " ".join(palavras[-sobreposicao:]).strip()
    if len(texto) <= sobreposicao:
        return texto.strip()
    corte = len(texto) - sobreposicao
    if corte > 0 and not texto[corte - 1].isspace():
        espaco = texto.find(" ", corte)
        if espaco != -1:
            corte = espaco + 1
    return texto[corte:].strip()


def dividir_documento_em_chunks(
    doc: schemas.DocumentoAcervo,
    paginas: list[tuple[int | None, str]],
    hash_documento: str,
    *,
    tamanho: int = 700,
    sobreposicao: int = 120,
    unidade: str = "caracteres",
) -> list[schemas.TrechoIndexado]:
    """Divide um `DocumentoAcervo` em objetos `TrechoIndexado` preservando página, seção e hash."""
    config_id = formatar_config_chunking(unidade, tamanho, sobreposicao)
    blocos = extrair_blocos_secao(paginas)

    brutos: list[dict[str, Any]] = []
    pagina_atual: int | None = None
    secoes_atuais: list[str] = []
    partes_atuais: list[str] = []

    def _descarregar_acumulado() -> str:
        nonlocal secoes_atuais, partes_atuais
        if not partes_atuais:
            return ""
        texto_unido = "\n\n".join(partes_atuais).strip()
        secao_str = "; ".join(dict.fromkeys(s for s in secoes_atuais if s)) or None
        if texto_unido:
            brutos.append({"pagina": pagina_atual, "secao": secao_str, "texto": texto_unido})
        cauda = _sufixo_sobreposicao(texto_unido, sobreposicao, unidade)
        secoes_atuais = [secoes_atuais[-1]] if (cauda and secoes_atuais) else []
        partes_atuais = [cauda] if cauda else []
        return cauda

    for bloco in blocos:
        pag = bloco["pagina"]
        sec = bloco["secao"]
        txt = bloco["texto"]

        # Nunca mistura páginas distintas no mesmo chunk para preservar rastreabilidade exata de página
        if partes_atuais and pag != pagina_atual:
            partes_atuais_bkp = list(partes_atuais)
            secoes_bkp = list(secoes_atuais)
            texto_pag = "\n\n".join(partes_atuais_bkp).strip()
            secao_pag = "; ".join(dict.fromkeys(s for s in secoes_bkp if s)) or None
            if texto_pag:
                brutos.append({"pagina": pagina_atual, "secao": secao_pag, "texto": texto_pag})
            partes_atuais = []
            secoes_atuais = []

        pagina_atual = pag

        # Se o próprio bloco individual excede `tamanho`, descarrega o anterior e fatia o bloco longo
        if _medir_unidade(txt, unidade) > tamanho:
            if partes_atuais:
                # Se só havia a cauda de sobreposição recém-gerada e mais nada real, descarta duplicata
                if len(partes_atuais) > 1 or not brutos or partes_atuais[0] not in brutos[-1]["texto"]:
                    texto_ant = "\n\n".join(partes_atuais).strip()
                    sec_ant = "; ".join(dict.fromkeys(s for s in secoes_atuais if s)) or None
                    if texto_ant:
                        brutos.append({"pagina": pagina_atual, "secao": sec_ant, "texto": texto_ant})
                partes_atuais = []
                secoes_atuais = []

            fatias = _fatiar_texto_longo(txt, tamanho, sobreposicao, unidade)
            for fatia in fatias:
                brutos.append({"pagina": pag, "secao": sec, "texto": fatia})
            continue

        candidato = "\n\n".join([*partes_atuais, txt]).strip()
        if partes_atuais and _medir_unidade(candidato, unidade) > tamanho:
            # Descarrega o chunk acumulado e inicia o próximo com a cauda de sobreposição + bloco atual
            cauda = _descarregar_acumulado()
            candidato_com_cauda = "\n\n".join([*partes_atuais, txt]).strip()
            if cauda and _medir_unidade(candidato_com_cauda, unidade) > tamanho:
                partes_atuais = [txt]
                secoes_atuais = [sec] if sec else []
            else:
                partes_atuais.append(txt)
                if sec:
                    secoes_atuais.append(sec)
        else:
            partes_atuais.append(txt)
            if sec:
                secoes_atuais.append(sec)

    # Descarrega o último bloco se contiver conteúdo novo além de eventual sobreposição
    if partes_atuais:
        eh_apenas_cauda = (
            len(partes_atuais) == 1
            and bool(brutos)
            and brutos[-1]["pagina"] == pagina_atual
            and partes_atuais[0] in brutos[-1]["texto"]
        )
        if not eh_apenas_cauda:
            texto_fim = "\n\n".join(partes_atuais).strip()
            sec_fim = "; ".join(dict.fromkeys(s for s in secoes_atuais if s)) or None
            if texto_fim:
                brutos.append({"pagina": pagina_atual, "secao": sec_fim, "texto": texto_fim})

    trechos: list[schemas.TrechoIndexado] = []
    for idx, item in enumerate(brutos, start=1):
        trecho = schemas.TrechoIndexado(
            chunk_id=f"{doc.documento_id}#c{idx}",
            documento_id=doc.documento_id,
            versao_documento=doc.versao,
            hash_documento=hash_documento,
            pagina=item["pagina"],
            secao=item["secao"],
            configuracao_chunking=config_id,
            texto=item["texto"],
        )
        trechos.append(trecho)
    return trechos


def ingerir_documento(
    doc: schemas.DocumentoAcervo,
    *,
    raiz: Path = RAIZ,
    tamanho: int = 700,
    sobreposicao: int = 120,
    unidade: str = "caracteres",
) -> list[schemas.TrechoIndexado]:
    """Extrai páginas, calcula hash e retorna os `TrechoIndexado` de um documento do catálogo."""
    caminho = (raiz / doc.arquivo).resolve()
    hash_doc = calcular_hash_arquivo(caminho)
    paginas = extrair_paginas_arquivo(caminho, doc.formato)
    return dividir_documento_em_chunks(
        doc=doc,
        paginas=paginas,
        hash_documento=hash_doc,
        tamanho=tamanho,
        sobreposicao=sobreposicao,
        unidade=unidade,
    )


def ingerir_acervo(
    *,
    caminho_catalogo: Path | None = None,
    raiz: Path = RAIZ,
    tamanho: int = 700,
    sobreposicao: int = 120,
    unidade: str = "caracteres",
    apenas_ids: set[str] | None = None,
) -> tuple[list[schemas.DocumentoAcervo], list[schemas.TrechoIndexado]]:
    """Ingere todo o catálogo (ou um subconjunto selecionado) retornando `(documentos, trechos)`."""
    documentos = carregar_catalogo(caminho_catalogo)
    if apenas_ids is not None:
        documentos = [d for d in documentos if d.documento_id in apenas_ids]

    todos_trechos: list[schemas.TrechoIndexado] = []
    for doc in documentos:
        todos_trechos.extend(
            ingerir_documento(doc, raiz=raiz, tamanho=tamanho, sobreposicao=sobreposicao, unidade=unidade)
        )
    return documentos, todos_trechos


def construir_documento_avulso(
    caminho_arquivo: Path,
    *,
    documento_id: str,
    titulo: str | None = None,
    versao: str = "1.0",
    tema: str = "Documento incluído pelo operador",
    vigencia_inicio: str = "01/08/2026",
    vigencia_fim: str | None = None,
    raiz: Path = RAIZ,
) -> tuple[schemas.DocumentoAcervo, list[tuple[int | None, str]], str]:
    """Lê um arquivo avulso `.txt` ou `.pdf` (ex.: upload no Streamlit RF20) e infere/valida `DocumentoAcervo`."""
    caminho_arquivo = Path(caminho_arquivo).resolve()
    fmt = FORMATOS_SUPORTADOS.get(caminho_arquivo.suffix.lower())
    if not fmt:
        raise ValueError(f"Extensão '{caminho_arquivo.suffix}' não suportada. Use .txt ou .pdf.")

    paginas = extrair_paginas_arquivo(caminho_arquivo, fmt)
    hash_doc = calcular_hash_arquivo(caminho_arquivo)

    campos_cab: dict[str, str] = {}
    primeira_pag = paginas[0][1] if paginas else ""
    for ln in primeira_pag.split("\n")[:12]:
        m = _RE_CABECALHO_CAMPO.match(ln)
        if m:
            chave = m.group(1).lower().replace("í", "i").replace("ã", "a").replace("ê", "e")
            campos_cab[chave] = m.group(2).strip()

    m_data = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", campos_cab.get("vigencia", ""))
    try:
        rel_str = caminho_arquivo.relative_to(raiz).as_posix()
    except ValueError:
        rel_str = caminho_arquivo.name

    doc = schemas.DocumentoAcervo(
        documento_id=documento_id,
        titulo=titulo or campos_cab.get("titulo") or caminho_arquivo.stem,
        versao=campos_cab.get("versao") or versao,
        tema=campos_cab.get("tema") or tema,
        formato=fmt,  # type: ignore[arg-type]
        vigencia_inicio=m_data.group(1) if m_data else vigencia_inicio,
        vigencia_fim=vigencia_fim,
        arquivo=rel_str,
    )
    return doc, paginas, hash_doc
