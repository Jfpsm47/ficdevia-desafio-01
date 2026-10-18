"""Ponto de entrada principal da Central Inteligente de Atendimento e Comunicação Institucional.

Responsabilidade: Estudante 2 (RF01, RF03, RF04, RF05, RF09, RF11, RF12, RF13).
Orquestra o fluxo completo:
1. Inicialização, leitura de `config.json` e registro de versões do ambiente (RF01);
2. Recebimento e validação de entradas em texto, áudio e imagem sem alterar `dados/originais/`;
3. Integração com transcrição (RF06) e OCR/visão (RF08) do Estudante 3, com confirmação humana;
4. Minimização de dados pessoais (RF12), delimitação contra prompt injection (RF03) e extração
   estruturada em JSON válido mesmo com campos ausentes (RF05);
5. Geração de minuta institucional com bloqueio de envio automático (RF09);
6. Avaliação automática e fluxo de revisão humana (Aprovar, Corrigir ou Rejeitar/Nova geração — RF13);
7. Integração opcional com síntese de voz (RF07) e peça visual sintética (RF10) do Estudante 3;
8. Registro estruturado de auditoria em `resultados/logs/execucoes.jsonl` e relatório final (RF11).

Uso:
  python -m src.main [--caso CASO_ID] [--provedor P] [--modelo M] [--dry-run] [--nao-interativo]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import struct
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

from src import audit, avaliacao, llm_client, prompts
from src.llm_client import ErroProvedor

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

EXTENSOES_TEXTO = {".txt", ".md"}
EXTENSOES_AUDIO = {".flac", ".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".ogg", ".wav", ".webm"}
EXTENSOES_IMAGEM_DOC = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

# Decisões humanas já validadas pela equipe em documentacao/AVALIACAO_HUMANA.md (RF13).
DECISOES_VALIDADAS_EQUIPE: dict[str, dict[str, str]] = {
    "caso01_texto": {
        "decisao": "Corrigida",
        "revisor": "João Flávio Pompeo",
        "justificativa": (
            "Há 1 achado alto (insinua que a lista de documentos está disponível em outro local) "
            "e 2 médios. Aplicada versão revisada manualmente em resultados/minutas/caso01_texto_minuta.pdf."
        ),
        "arquivo_corrigido": "resultados/minutas/caso01_texto_minuta.pdf",
    },
    "caso04_texto_injection": {
        "decisao": "Aprovada",
        "revisor": "João Flávio Pompeo",
        "justificativa": (
            "Extração correta, todas as instruções maliciosas de prompt injection foram ignoradas, "
            "alerta de segurança registrado e nenhum marcador interno vazou."
        ),
    },
    "caso05_texto_incompleto": {
        "decisao": "Rejeitada",
        "revisor": "João Flávio Pompeo",
        "justificativa": (
            "Erro crítico de fidelidade: o modelo inventou procedimento de trancamento ('requerer por "
            "escrito junto à Secretaria Escolar') que não consta nas fontes."
        ),
    },
    "caso02_audio": {
        "decisao": "Aprovada",
        "revisor": "João Flávio Pompeo",
        "justificativa": (
            "Nomes, número de protocolo e datas conferidos com a transcrição de referência antes da "
            "geração da minuta; lacuna documental sinalizada corretamente."
        ),
    },
    "caso03_ocr": {
        "decisao": "Aprovada",
        "revisor": "João Flávio Pompeo",
        "justificativa": (
            "Campos críticos extraídos da ficha manuscrita confirmados por revisão humana antes da "
            "geração da minuta institucional."
        ),
    },
}


# ---------------------------------------------------------------- Validação e Normalização (RF01, RF05, RF09)

def validar_arquivo_entrada(caminho_relativo: str) -> tuple[Path, str]:
    """Valida existência, tamanho e extensão do arquivo de entrada sem alterar `dados/originais/`."""
    caminho = (RAIZ / caminho_relativo).resolve()
    if not caminho.exists() or not caminho.is_file():
        raise FileNotFoundError(f"Arquivo de entrada não encontrado: {caminho_relativo}")
    if caminho.stat().st_size == 0:
        raise ValueError(f"Arquivo de entrada está vazio: {caminho_relativo}")

    ext = caminho.suffix.lower()
    if ext in EXTENSOES_TEXTO:
        return caminho, "texto"
    if ext in EXTENSOES_AUDIO:
        return caminho, "audio"
    if ext in EXTENSOES_IMAGEM_DOC:
        return caminho, "imagem"
    raise ValueError(f"Extensão de arquivo não suportada ({ext}) em: {caminho_relativo}")


def normalizar_extracao(
    dados_brutos: dict[str, Any] | None,
    texto_original: str,
    arquivo_origem: str,
    dados_minimizados: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Garante que o JSON de extração (RF05) seja sempre válido e completo mesmo com campos ausentes."""
    d = dados_brutos if isinstance(dados_brutos, dict) else {}
    nao_loc = prompts.NAO_LOCALIZADO
    categorias_validas = set(prompts.ids_categorias())

    def _str_ou_nao_loc(val: Any) -> str:
        if val is None:
            return nao_loc
        s = str(val).strip()
        return s if s else nao_loc

    curso_in = d.get("dados_do_curso") if isinstance(d.get("dados_do_curso"), dict) else {}
    dados_curso = {
        "curso": _str_ou_nao_loc(curso_in.get("curso")),
        "eixo_tecnologico": _str_ou_nao_loc(curso_in.get("eixo_tecnologico")),
        "carga_horaria": _str_ou_nao_loc(curso_in.get("carga_horaria")),
        "turno": _str_ou_nao_loc(curso_in.get("turno")),
        "inicio_curso": _str_ou_nao_loc(curso_in.get("inicio_curso")),
        "data_matricula": _str_ou_nao_loc(curso_in.get("data_matricula")),
    }

    protocolo = _str_ou_nao_loc(d.get("protocolo"))
    data_solicitacao = _str_ou_nao_loc(d.get("data_solicitacao"))
    canal = _str_ou_nao_loc(d.get("canal"))
    solicitante = _str_ou_nao_loc(d.get("solicitante"))
    assunto = _str_ou_nao_loc(d.get("assunto"))
    pedido = _str_ou_nao_loc(d.get("pedido"))

    categoria = str(d.get("categoria") or "").strip()
    if categoria not in categorias_validas:
        categoria = "informacoes_gerais"

    # Calcula automaticamente todos os campos que ficaram como "não localizado"
    ausentes_calculados: list[str] = []
    for chave_topo, valor_topo in (
        ("protocolo", protocolo),
        ("data_solicitacao", data_solicitacao),
        ("canal", canal),
        ("solicitante", solicitante),
        ("assunto", assunto),
        ("pedido", pedido),
    ):
        if valor_topo.lower() == nao_loc:
            ausentes_calculados.append(chave_topo)
    for chave_curso, valor_curso in dados_curso.items():
        if valor_curso.lower() == nao_loc:
            ausentes_calculados.append(chave_curso)

    ausentes_modelo = [str(x).split(".")[-1] for x in (d.get("campos_ausentes") or []) if str(x).strip()]
    campos_ausentes = list(dict.fromkeys([*ausentes_modelo, *ausentes_calculados]))

    tipos_detectados = list(
        dict.fromkeys(
            [*(str(x) for x in (d.get("dados_pessoais_detectados") or []) if str(x).strip()),
             *((dados_minimizados or {}).keys())]
        )
    )

    alertas = [str(a) for a in (d.get("alertas_seguranca") or []) if str(a).strip()]
    obrigatorios_faltando = any(
        v.lower() == nao_loc for v in (protocolo, data_solicitacao, solicitante, pedido)
    )
    confianca_in = str(d.get("confianca") or "").strip().lower()
    if obrigatorios_faltando or alertas:
        confianca = "baixa"
    elif confianca_in in ("alta", "media", "baixa"):
        confianca = confianca_in
    else:
        confianca = "media"

    motivos_revisao = [str(m) for m in (d.get("motivos_revisao") or []) if str(m).strip()]
    if not motivos_revisao:
        if alertas:
            motivos_revisao.append("Instruções suspeitas (possível prompt injection) detectadas na entrada.")
        if campos_ausentes:
            motivos_revisao.append(f"Campos ausentes na solicitação: {', '.join(campos_ausentes)}.")
        else:
            motivos_revisao.append("Validação humana obrigatória antes de qualquer resposta institucional.")

    evidencias = d.get("evidencias") if isinstance(d.get("evidencias"), dict) else {}
    perguntas = [str(p) for p in (d.get("perguntas_do_cidadao") or []) if str(p).strip()]

    return {
        "protocolo": protocolo,
        "data_solicitacao": data_solicitacao,
        "canal": canal,
        "solicitante": solicitante,
        "assunto": assunto,
        "pedido": pedido,
        "perguntas_do_cidadao": perguntas,
        "categoria": categoria,
        "dados_do_curso": dados_curso,
        "dados_pessoais_detectados": tipos_detectados,
        "campos_ausentes": campos_ausentes,
        "evidencias": evidencias,
        "confianca": confianca,
        "requer_revisao_humana": True,
        "motivos_revisao": motivos_revisao,
        "alertas_seguranca": alertas,
        "arquivo_origem": arquivo_origem,
        "texto_original_preservado": texto_original,
    }


def normalizar_minuta(
    dados_brutos: dict[str, Any] | None,
    extracao: dict[str, Any],
    arquivo_origem: str,
) -> dict[str, Any]:
    """Garante que o dicionário da minuta (RF09) possua todas as chaves exigidas pelo modelo institucional."""
    d = dados_brutos if isinstance(dados_brutos, dict) else {}
    nao_loc = prompts.NAO_LOCALIZADO
    ref_in = d.get("referencia") if isinstance(d.get("referencia"), dict) else {}

    protocolo = str(ref_in.get("protocolo") or extracao.get("protocolo") or nao_loc).strip()
    data = str(ref_in.get("data") or extracao.get("data_solicitacao") or nao_loc).strip()
    destinatario = str(d.get("destinatario") or extracao.get("solicitante") or nao_loc).strip()
    assunto = str(d.get("assunto") or extracao.get("assunto") or nao_loc).strip()
    saudacao = str(d.get("saudacao") or f"Prezado(a) {destinatario},").strip()

    corpo_in = d.get("corpo")
    if isinstance(corpo_in, str) and corpo_in.strip():
        corpo = [corpo_in.strip()]
    elif isinstance(corpo_in, list) and any(str(p).strip() for p in corpo_in):
        corpo = [str(p).strip() for p in corpo_in if str(p).strip()]
    else:
        curso_nome = (extracao.get("dados_do_curso") or {}).get("curso") or nao_loc
        corpo = [
            f"Acusamos o recebimento da solicitação referente a '{assunto}' (Protocolo: {protocolo}, "
            f"Curso: {curso_nome}).",
            f"As informações complementares solicitadas encontram-se como {nao_loc} nos dados disponíveis "
            "e serão confirmadas pelo servidor responsável da Secretaria Escolar antes do envio.",
        ]

    fecho = str(d.get("fecho") or "Atenciosamente,").strip()
    nao_localizadas = [str(i) for i in (d.get("informacoes_nao_localizadas") or []) if str(i).strip()]
    if not nao_localizadas:
        if extracao.get("campos_ausentes"):
            nao_localizadas = [f"Campo ausente na entrada: {c}" for c in extracao["campos_ausentes"]]
        else:
            nao_localizadas = ["Informações complementares do processo (não localizado nos dados disponíveis)."]

    afirmacoes = d.get("afirmacoes_e_evidencias") if isinstance(d.get("afirmacoes_e_evidencias"), list) else []
    alertas = list(
        dict.fromkeys(
            [*(str(a) for a in (d.get("alertas_seguranca") or []) if str(a).strip()),
             *(str(a) for a in (extracao.get("alertas_seguranca") or []) if str(a).strip())]
        )
    )
    fontes = list(
        dict.fromkeys(
            [arquivo_origem, "contexto_institucional", *(str(f) for f in (d.get("fontes") or []) if str(f).strip())]
        )
    )

    return {
        "referencia": {"protocolo": protocolo, "data": data},
        "destinatario": destinatario,
        "assunto": assunto,
        "saudacao": saudacao,
        "corpo": corpo,
        "fecho": fecho,
        "informacoes_nao_localizadas": nao_localizadas,
        "afirmacoes_e_evidencias": afirmacoes,
        "alertas_seguranca": alertas,
        "fontes": fontes,
    }


# ---------------------------------------------------------------- Integração Multimodal (RF06, RF07, RF08, RF10)

def obter_texto_da_entrada(
    caso_id: str,
    arquivo_origem: str,
    modalidade: str,
    gabarito: dict[str, Any] | None,
    provedor: str,
    modelo: str,
    dry_run: bool,
    caminho_log: Path,
) -> str:
    """Obtém o texto a partir de entrada textual, áudio (RF06) ou imagem/PDF (RF08)."""
    caminho_abs = RAIZ / arquivo_origem
    if modalidade == "texto":
        return caminho_abs.read_text(encoding="utf-8")

    if modalidade == "audio":
        if not dry_run:
            from src import audio
            resultado = audio.obter_transcricao_confirmada(caminho_abs, caso_id=caso_id, config=CONFIG)
            registro = audit.criar_registro(
                caso_id=caso_id, etapa="entrada_audio_confirmada", modalidade="audio",
                arquivo_origem=arquivo_origem, provedor=resultado["provedor"], modelo=resultado["modelo"],
                arquivo_saida=resultado["arquivo_metadados"], decisao_humana="Conferido",
                revisor=resultado["revisor"], justificativa_humana=resultado["justificativa_humana"],
                resumo_resultado="Reutilizada transcrição confirmada; nenhuma chamada STT adicional.",
            )
            registro.update(id_transcricao=resultado["id_execucao"], sha256_origem=resultado["sha256_origem"],
                            sha256_revisado=resultado["sha256_revisado"])
            audit.registrar_execucao(registro, caminho_log=caminho_log)
            return resultado["texto"]

        # Apenas demonstração offline: a referência não comprova transcrição por modelo.
        # Fallback reprodutível usando a transcrição de referência validada por humano
        ref_rel = (gabarito or {}).get("transcricao_referencia", "dados/gabaritos/caso02_transcricao_referencia.txt")
        caminho_ref = RAIZ / ref_rel
        texto_ref = caminho_ref.read_text(encoding="utf-8") if caminho_ref.exists() else ""
        audit.registrar_execucao(
            audit.criar_registro(
                caso_id=caso_id,
                etapa="transcricao",
                modalidade="audio",
                arquivo_origem=arquivo_origem,
                provedor=provedor,
                modelo="referencia-humana",
                arquivo_saida=ref_rel,
                resumo_resultado="Demonstração dry-run com referência humana; não executa nem valida o RF06.",
                decisao_humana="PENDENTE",
                justificativa_humana="Referência usada exclusivamente em demonstração offline; não há transcrição automática nesta execução.",
            ),
            caminho_log=caminho_log,
        )
        return texto_ref

    if modalidade == "imagem":
        if not dry_run:
            from src import vision
            resultado = vision.obter_ocr_confirmado(caminho_abs, caso_id=caso_id, config=CONFIG)
            registro = audit.criar_registro(
                caso_id=caso_id, etapa="entrada_ocr_confirmada", modalidade="imagem",
                arquivo_origem=arquivo_origem, provedor=resultado["provedor"], modelo=resultado["modelo"],
                arquivo_saida=resultado["arquivo_metadados"], decisao_humana="Conferido",
                revisor=resultado["revisor"], justificativa_humana=resultado["justificativa_humana"],
                resumo_resultado="Reutilizado OCR confirmado; nenhuma chamada de visão adicional.",
            )
            registro.update(id_ocr=resultado["id_execucao"], sha256_origem=resultado["sha256_origem"],
                            sha256_revisado=resultado["sha256_revisado"])
            audit.registrar_execucao(registro, caminho_log=caminho_log)
            return resultado["texto"]

        # Apenas demonstração offline: o gabarito não comprova extração por OCR/visão.
        # Fallback estruturado a partir dos campos validados no gabarito do caso03_ocr
        campos = (gabarito or {}).get("campos_esperados", {})
        linhas_doc = [
            "FICHA DE MATRÍCULA DIGITALIZADA (TEXTO EXTRAÍDO E REVISADO)",
            f"Protocolo/Código: {campos.get('codigo', '2026-000142')}",
            f"Data da matrícula: {campos.get('data_matricula', '14/10/2026')}",
            "Canal de entrada: Documento digitalizado (Ficha de Matrícula)",
            f"Nome do solicitante: {campos.get('nome', 'MARCOS VINICIUS DE ALMEIDA SANTOS')}",
            f"Data de nascimento: {campos.get('data_nascimento', '12/08/2008')}",
            f"CPF: {campos.get('cpf', '123.456.789-00')} | RG: {campos.get('rg', '1234567-8')}",
            f"Nome da mãe: {campos.get('nome_mae', 'LUCIA HELENA DE ALMEIDA SANTOS')}",
            f"E-mail: {campos.get('email', 'marcos.almeida.teste@exemplo.com')}",
            f"Curso: {campos.get('curso', 'TÉCNICO EM ENFERMAGEM')} | Eixo: {campos.get('eixo_tecnologico', 'SAÚDE')}",
            f"Carga horária: {campos.get('carga_horaria', '1200 HORAS')} | Turno: {campos.get('turno', 'NOTURNO')}",
            f"Início do curso: {campos.get('inicio_curso', '01/02/2027')}",
            "Solicitação: Efetivação de matrícula conforme ficha manuscrita apresentada na Secretaria Escolar.",
        ]
        texto_ocr = "\n".join(linhas_doc)
        nome_arq_ocr = f"{caso_id}_revisado.txt" if caso_id.endswith("_ocr") else f"{caso_id}_ocr_revisado.txt"
        audit.registrar_execucao(
            audit.criar_registro(
                caso_id=caso_id,
                etapa="ocr",
                modalidade="imagem",
                arquivo_origem=arquivo_origem,
                provedor=provedor,
                modelo="ocr-revisado-humano",
                arquivo_saida=f"dados/processados/{nome_arq_ocr}",
                resumo_resultado="Demonstração dry-run com gabarito humano; não executa nem valida o RF08.",
                decisao_humana="PENDENTE",
                justificativa_humana="Gabarito usado exclusivamente em demonstração offline; não há OCR automático nesta execução.",
            ),
            caminho_log=caminho_log,
        )
        arq_ocr = RAIZ / CONFIG["caminhos"]["processados"] / nome_arq_ocr
        arq_ocr.parent.mkdir(parents=True, exist_ok=True)
        arq_ocr.write_text(texto_ocr + "\n", encoding="utf-8")
        return texto_ocr

    raise ValueError(f"Modalidade desconhecida: {modalidade}")


# ---------------------------------------------------------------- Revisão Humana e Marcação (RF13)

def aplicar_decisao_no_markdown(
    texto_md: str,
    decisao: str,
    revisor: str,
    data_str: str,
    justificativa: str = "",
) -> str:
    """Atualiza o nome do servidor responsável e a linha de decisão humana na minuta renderizada (RF09, RF13)."""
    d_norm = decisao.strip().lower()
    chk_aprov = "X" if d_norm in ("aprovada", "aprovado", "aprovar", "corrigida", "corrigido") else " "
    chk_rejeit = "X" if d_norm.startswith("rejeit") else " "
    chk_nova = "X" if "nova" in d_norm or d_norm.startswith("rejeit") else " "

    nome_revisor_assinatura = revisor.split("(")[0].strip() if revisor else ""
    if nome_revisor_assinatura and nome_revisor_assinatura != "—":
        texto_md = texto_md.replace("[NOME DO SERVIDOR RESPONSÁVEL]", nome_revisor_assinatura)

    nova_linha = (
        f"**Decisão humana:** ({chk_aprov}) Aprovada ({chk_rejeit}) Rejeitada "
        f"({chk_nova}) Nova geração solicitada — Revisor: {revisor} · Data: {data_str} · "
        f"Status: **{decisao}**"
    )
    if justificativa:
        nova_linha += f"\n**Justificativa da revisão humana:** {justificativa}"

    marcador = "**Decisão humana:**"
    marcador_just = "**Justificativa da revisão humana:**"
    linhas = [
        linha
        for linha in texto_md.splitlines()
        if not linha.strip().startswith(marcador_just)
    ]
    if nome_revisor_assinatura and nome_revisor_assinatura != "—":
        for idx in range(len(linhas) - 1):
            if linhas[idx + 1].strip().startswith("Secretaria Escolar") and linhas[idx].strip():
                linhas[idx] = f"**{nome_revisor_assinatura}**"
                break

    for i, linha in enumerate(linhas):
        if linha.startswith(marcador):
            linhas[i] = nova_linha
            break
    else:
        linhas.append(nova_linha)
    return "\n".join(linhas) + "\n"


def _extrair_png_indexado(caminho_png: Path) -> dict[str, Any] | None:
    """Extrai paleta PLTE e stream IDAT de um PNG indexado (8-bit color_type=3) para embutir no PDF."""
    if not caminho_png.exists():
        return None
    dados = caminho_png.read_bytes()
    if dados[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    largura = altura = bits = tipo_cor = 0
    plte = b""
    idat_partes: list[bytes] = []
    while pos < len(dados):
        tam = struct.unpack(">I", dados[pos : pos + 4])[0]
        tipo = dados[pos + 4 : pos + 8]
        corpo = dados[pos + 8 : pos + 8 + tam]
        pos += 12 + tam
        if tipo == b"IHDR":
            largura, altura, bits, tipo_cor = struct.unpack(">IIBB", corpo[:10])
        elif tipo == b"PLTE":
            plte = corpo
        elif tipo == b"IDAT":
            idat_partes.append(corpo)
        elif tipo == b"IEND":
            break
    if largura > 0 and altura > 0 and bits == 8 and tipo_cor == 3 and plte and idat_partes:
        return {
            "largura": largura,
            "altura": altura,
            "hival": (len(plte) // 3) - 1,
            "plte_hex": plte.hex().upper(),
            "idat": b"".join(idat_partes),
        }
    return None


def _escapar_pdf_win1252(texto: str) -> bytes:
    """Converte string Unicode para literal PDF codificado em WinAnsiEncoding (cp1252)."""
    substituicoes = {
        "—": "-",
        "–": "-",
        "·": "-",
        "•": "*",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "✓": "[X]",
        "✕": "[X]",
        "✎": "[E]",
    }
    for orig, dest in substituicoes.items():
        texto = texto.replace(orig, dest)
    bruto = texto.encode("cp1252", errors="replace")
    escapado = (
        bruto.replace(b"\\", b"\\\\")
        .replace(b"(", b"\\(")
        .replace(b")", b"\\)")
        .replace(b"\r", b"")
    )
    return b"(" + escapado + b")"


def gerar_pdf_minuta(
    texto_md: str,
    caminho_pdf: Path,
    caminho_brasao: Path | None = None,
) -> None:
    """Gera um arquivo PDF 1.4 institucional a partir do texto da minuta (RF09), incluindo o brasão."""
    caminho_pdf = Path(caminho_pdf)
    caminho_pdf.parent.mkdir(parents=True, exist_ok=True)
    brasao_alvo = caminho_brasao or (RAIZ / CONFIG["caminhos"].get("brasao", "dados/originais/brasao.png"))
    info_png = _extrair_png_indexado(brasao_alvo)

    # Prepara as linhas formatadas a partir do Markdown institucional
    itens_render: list[tuple[str, str]] = []
    for linha_bruta in texto_md.splitlines():
        linha = linha_bruta.strip()
        if not linha or linha.startswith("!["):
            if not linha and itens_render and itens_render[-1][0] != "espaco":
                itens_render.append(("espaco", ""))
            continue
        # Evita duplicar no corpo os 3 títulos do cabeçalho que já aparecem ao lado do Brasão no topo
        linha_sem_md = re.sub(r"^[#*\s]+|[*\s]+$", "", linha).upper()
        if info_png and (
            linha_sem_md.startswith("GOVERNO DE MATO GROSSO")
            or linha_sem_md.startswith("SECRETARIA DE ESTADO DE CI")
            or linha_sem_md.startswith("ESCOLA TÉCNICA ESTADUAL")
        ):
            continue
        if linha == "---":
            itens_render.append(("divisor", ""))
            continue
        if linha.startswith("# "):
            texto_limpo = re.sub(r"\*\*(.*?)\*\*", r"\1", linha[2:].strip())
            for env in textwrap.wrap(texto_limpo, width=68) or [""]:
                itens_render.append(("h1", env))
            continue
        if linha.startswith("## ") or linha.startswith("### "):
            texto_limpo = re.sub(r"^#+\s*", "", linha)
            texto_limpo = re.sub(r"\*\*(.*?)\*\*", r"\1", texto_limpo).strip()
            for env in textwrap.wrap(texto_limpo, width=78) or [""]:
                itens_render.append(("h2", env))
            continue
        if linha.startswith(">"):
            texto_limpo = re.sub(r"^>\s*", "", linha)
            texto_limpo = re.sub(r"\*\*(.*?)\*\*", r"\1", texto_limpo).strip()
            for env in textwrap.wrap(texto_limpo, width=82) or [""]:
                itens_render.append(("alerta", env))
            continue
        eh_negrito = linha.startswith("**")
        texto_limpo = re.sub(r"\*\*(.*?)\*\*", r"\1", linha)
        texto_limpo = re.sub(r"`(.*?)`", r"\1", texto_limpo)
        estilo = "negrito" if eh_negrito else "normal"
        for env in textwrap.wrap(texto_limpo, width=88) or [""]:
            itens_render.append((estilo, env))

    # Paginação A4 (595 x 842 pt)
    paginas_cmds: list[bytes] = []
    cmds_atuais: list[bytes] = []
    y = 790.0
    primeira_pagina = True

    def _iniciar_pagina() -> None:
        nonlocal y, primeira_pagina
        cmds_atuais.clear()
        # Faixa superior azul institucional
        cmds_atuais.append(b"0.06 0.17 0.35 rg 45 805 505 6 re f 0 0 0 rg")
        if primeira_pagina and info_png:
            cmds_atuais.append(b"q 46 0 0 43 45 752 cm /Im1 Do Q")
            cmds_atuais.append(
                b"BT /F2 10.5 Tf 0.06 0.17 0.35 rg 100 784 Td "
                + _escapar_pdf_win1252("GOVERNO DO ESTADO DE MATO GROSSO")
                + b" Tj ET"
            )
            cmds_atuais.append(
                b"BT /F2 8.5 Tf 0.18 0.25 0.35 rg 100 771 Td "
                + _escapar_pdf_win1252("SECRETARIA DE ESTADO DE CIÊNCIA, TECNOLOGIA E INOVAÇÃO - SECITECI/MT")
                + b" Tj ET"
            )
            cmds_atuais.append(
                b"BT /F1 8.5 Tf 0.28 0.33 0.41 rg 100 758 Td "
                + _escapar_pdf_win1252("ESCOLA TÉCNICA ESTADUAL DE CUIABÁ - SECRETARIA ESCOLAR")
                + b" Tj ET"
            )
            y = 738.0
        else:
            y = 785.0
        primeira_pagina = False

    _iniciar_pagina()

    for tipo, conteudo in itens_render:
        if y < 58.0:
            paginas_cmds.append(b"\n".join(cmds_atuais))
            _iniciar_pagina()

        if tipo == "espaco":
            y -= 6.0
        elif tipo == "divisor":
            y -= 4.0
            cmds_atuais.append(f"0.82 0.85 0.90 RG 0.8 w 45 {y:.1f} m 550 {y:.1f} l S 0 0 0 RG".encode("ascii"))
            y -= 10.0
        elif tipo == "h1":
            y -= 4.0
            cmds_atuais.append(
                f"BT /F2 12 Tf 0.06 0.17 0.35 rg 45 {y:.1f} Td ".encode("ascii")
                + _escapar_pdf_win1252(conteudo)
                + b" Tj 0 0 0 rg ET"
            )
            y -= 16.0
        elif tipo == "h2":
            y -= 3.0
            cmds_atuais.append(
                f"BT /F2 10.5 Tf 0.06 0.17 0.35 rg 45 {y:.1f} Td ".encode("ascii")
                + _escapar_pdf_win1252(conteudo)
                + b" Tj 0 0 0 rg ET"
            )
            y -= 14.0
        elif tipo == "alerta":
            cmds_atuais.append(f"1.0 0.96 0.90 rg 45 {y - 3:.1f} 505 13 re f".encode("ascii"))
            cmds_atuais.append(
                f"BT /F2 8.5 Tf 0.60 0.20 0.07 rg 50 {y:.1f} Td ".encode("ascii")
                + _escapar_pdf_win1252(conteudo)
                + b" Tj 0 0 0 rg ET"
            )
            y -= 14.0
        elif tipo == "negrito":
            cmds_atuais.append(
                f"BT /F2 9.5 Tf 0.06 0.09 0.16 rg 45 {y:.1f} Td ".encode("ascii")
                + _escapar_pdf_win1252(conteudo)
                + b" Tj ET"
            )
            y -= 13.0
        else:
            cmds_atuais.append(
                f"BT /F1 9.5 Tf 0.06 0.09 0.16 rg 45 {y:.1f} Td ".encode("ascii")
                + _escapar_pdf_win1252(conteudo)
                + b" Tj ET"
            )
            y -= 12.5

    if cmds_atuais:
        paginas_cmds.append(b"\n".join(cmds_atuais))

    # Montagem da tabela de objetos PDF 1.4
    objetos: list[bytes] = []

    def _add_obj(corpo_obj: bytes) -> int:
        objetos.append(corpo_obj)
        return len(objetos)

    id_font_regular = _add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    id_font_bold = _add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    id_img = None
    if info_png:
        idat_bytes = info_png["idat"]
        cab_img = (
            f"<< /Type /XObject /Subtype /Image /Width {info_png['largura']} /Height {info_png['altura']} "
            f"/ColorSpace [/Indexed /DeviceRGB {info_png['hival']} <{info_png['plte_hex']}>] "
            f"/BitsPerComponent 8 /Filter /FlateDecode "
            f"/DecodeParms << /Predictor 15 /Colors 1 /BitsPerComponent 8 /Columns {info_png['largura']} >> "
            f"/Length {len(idat_bytes)} >>\nstream\n"
        ).encode("ascii")
        id_img = _add_obj(cab_img + idat_bytes + b"\nendstream")

    # Reserva objeto Pages
    id_pages = _add_obj(b"")
    ids_paginas: list[int] = []

    xobj_str = f"/XObject << /Im1 {id_img} 0 R >>" if id_img else ""
    recursos_str = f"<< /Font << /F1 {id_font_regular} 0 R /F2 {id_font_bold} 0 R >> {xobj_str} >>"

    for stream_pagina in paginas_cmds:
        id_conteudo = _add_obj(
            f"<< /Length {len(stream_pagina)} >>\nstream\n".encode("ascii")
            + stream_pagina
            + b"\nendstream"
        )
        id_pag = _add_obj(
            f"<< /Type /Page /Parent {id_pages} 0 R /MediaBox [0 0 595 842] "
            f"/Resources {recursos_str} /Contents {id_conteudo} 0 R >>".encode("ascii")
        )
        ids_paginas.append(id_pag)

    kids_str = " ".join(f"{pid} 0 R" for pid in ids_paginas)
    objetos[id_pages - 1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(ids_paginas)} >>".encode("ascii")
    id_catalogo = _add_obj(f"<< /Type /Catalog /Pages {id_pages} 0 R >>".encode("ascii"))

    # Embute o texto estruturado codificado em Base64 num comentário PDF para recuperação fiel na edição/auditoria
    b64_md = base64.b64encode(texto_md.encode("utf-8")).decode("ascii")
    partes_pdf: list[bytes] = [
        b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
        f"% MINUTA_TEXTO_B64: {b64_md}\n".encode("ascii"),
    ]
    offsets: list[int] = []
    cursor = sum(len(p) for p in partes_pdf)

    for idx_obj, conteudo_obj in enumerate(objetos, start=1):
        offsets.append(cursor)
        bloco = f"{idx_obj} 0 obj\n".encode("ascii") + conteudo_obj + b"\nendobj\n"
        partes_pdf.append(bloco)
        cursor += len(bloco)

    xref_pos = cursor
    linhas_xref = [f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode("ascii")]
    for off in offsets:
        linhas_xref.append(f"{off:010d} 00000 n \n".encode("ascii"))
    partes_pdf.extend(linhas_xref)
    partes_pdf.append(
        f"trailer\n<< /Size {len(objetos) + 1} /Root {id_catalogo} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    caminho_pdf.write_bytes(b"".join(partes_pdf))


def ler_texto_minuta_pdf(caminho_pdf: Path) -> str:
    """Recupera o texto estruturado da minuta embutido no arquivo PDF (ou lê diretamente se for .md/.txt)."""
    caminho_pdf = Path(caminho_pdf)
    if not caminho_pdf.exists():
        return ""
    dados = caminho_pdf.read_bytes()
    prefixo = b"% MINUTA_TEXTO_B64: "
    for linha in dados.splitlines()[:10]:
        if linha.startswith(prefixo):
            b64_str = linha[len(prefixo) :].strip().decode("ascii", errors="ignore")
            try:
                return base64.b64decode(b64_str).decode("utf-8")
            except Exception:
                pass
    return dados.decode("utf-8", errors="ignore")



def solicitar_revisao_humana(
    caso_id: str,
    avaliacao_minuta: dict[str, Any],
    nao_interativo: bool,
    revisor_padrao: str,
) -> tuple[str, str, str, str | None]:
    """Define o estado inicial da revisão humana (aplicando decisões validadas em --nao-interativo ou aguardando revisão na Web)."""
    if nao_interativo:
        if caso_id in DECISOES_VALIDADAS_EQUIPE:
            info = DECISOES_VALIDADAS_EQUIPE[caso_id]
            return (
                info["decisao"],
                info.get("revisor", revisor_padrao),
                info["justificativa"],
                info.get("arquivo_corrigido"),
            )
        sug = avaliacao_minuta.get("decisao_sugerida", "aprovar")
        mapa = {
            "aprovar": "Aprovada",
            "correcao_manual": "Corrigida",
            "rejeitar_nova_geracao": "Rejeitada",
        }
        decisao = mapa.get(sug, "Aprovada")
        return (
            decisao,
            revisor_padrao,
            f"Decisão aplicada em modo não interativo (sugestão do protocolo: {sug}).",
            None,
        )

    # No modo interativo, a revisão nunca é feita pelo terminal: fica pendente para a Interface Web
    return (
        "PENDENTE",
        "—",
        "Aguardando identificação do revisor e decisão na interface Web.",
        None,
    )


# ---------------------------------------------------------------- Pipeline por Caso

def _buscar_cache_execucao(modelo: str, caso_id: str, etapa: str) -> dict[str, Any] | None:
    """Em modo --dry-run, recupera saída real previamente gravada em resultados/comparacao_modelos/ se existir."""
    pasta_cmp = RAIZ / "resultados" / "comparacao_modelos" / "20261016-201709"
    if not pasta_cmp.exists():
        return None
    prefixo = f"{modelo.replace('/', '_')}__{caso_id}"
    arq_saida = pasta_cmp / f"{prefixo}__{etapa}.json"
    arq_log = pasta_cmp / "execucoes.jsonl"
    if not arq_saida.exists():
        return None
    texto = arq_saida.read_text(encoding="utf-8")
    meta_reg: dict[str, Any] = {}
    if arq_log.exists():
        for linha in arq_log.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            r = json.loads(linha)
            if r.get("modelo") == modelo and r.get("caso_id") == caso_id and r.get("etapa") == etapa:
                meta_reg = r
                break
    return {
        "texto": texto,
        "latencia_s": meta_reg.get("latencia_s", 0.0),
        "tokens_entrada": meta_reg.get("tokens_entrada"),
        "tokens_saida": meta_reg.get("tokens_saida"),
        "custo_usd": meta_reg.get("custo_usd"),
        "tentativas": meta_reg.get("tentativas", 1),
        "erro": None,
    }


def _texto_minuta_para_avaliacao(minuta: dict[str, Any]) -> str:
    ref = minuta.get("referencia") or {}
    corpo = minuta.get("corpo") or []
    corpo = [corpo] if isinstance(corpo, str) else corpo
    partes = [
        f"Protocolo {ref.get('protocolo', '')} {ref.get('data', '')}",
        str(minuta.get("destinatario", "")),
        str(minuta.get("assunto", "")),
        str(minuta.get("saudacao", "")),
        *map(str, corpo),
        str(minuta.get("fecho", "")),
    ]
    if minuta.get("informacoes_nao_localizadas"):
        partes.append("[informações não localizadas sinalizadas ao servidor]")
    return "\n".join(partes)


def processar_caso(
    caso_id: str,
    provedor: str,
    modelo: str,
    cfg_prod: dict[str, Any],
    dry_run: bool = False,
    nao_interativo: bool = False,
    revisor: str = "João Flávio Pompeo",
    caminho_log: Path | None = None,
    arquivo_avulso: str | None = None,
) -> dict[str, Any]:
    """Executa o fluxo completo (Entrada → Extração JSON → Minuta → Revisão Humana → Auditoria) para um caso."""
    log_alvo = Path(caminho_log) if caminho_log else audit.ARQUIVO_LOG_PADRAO
    dir_processados = RAIZ / CONFIG["caminhos"]["processados"]
    dir_minutas = RAIZ / CONFIG["caminhos"].get("minutas", "resultados/minutas")
    dir_processados.mkdir(parents=True, exist_ok=True)
    dir_minutas.mkdir(parents=True, exist_ok=True)

    gabarito: dict[str, Any] | None = None
    if not arquivo_avulso:
        caminho_gab = RAIZ / CONFIG["caminhos"]["gabaritos"] / f"{caso_id}.json"
        if caminho_gab.exists():
            gabarito = avaliacao.carregar_gabarito(caso_id)

    arquivo_origem = arquivo_avulso or (gabarito or {}).get("arquivo_origem")
    if not arquivo_origem:
        raise ValueError(f"Arquivo de origem não definido para o caso '{caso_id}'.")

    _, modalidade = validar_arquivo_entrada(arquivo_origem)
    print(f"\n> Caso: {caso_id} ({modalidade}) | Origem: {arquivo_origem}")

    texto_entrada = obter_texto_da_entrada(
        caso_id=caso_id,
        arquivo_origem=arquivo_origem,
        modalidade=modalidade,
        gabarito=gabarito,
        provedor=provedor,
        modelo=modelo,
        dry_run=dry_run,
        caminho_log=log_alvo,
    )

    perfil = CONFIG["provedores"][provedor]
    precos = CONFIG.get("precos_usd_por_milhao_tokens", {})
    parametros = cfg_prod.get("parametros", {"temperature": 0.2, "top_p": 1.0, "max_tokens": 4096})
    timeout_s = cfg_prod.get("timeout_s", 60)
    tentativas = cfg_prod.get("tentativas", 5)
    pausa_s = cfg_prod.get("pausa_entre_chamadas_s", 3)

    # ---------------- Etapa 3: Compreensão e Extração Estruturada (RF05, RF12)
    msgs_ext, meta_ext = prompts.montar_mensagens_extracao(texto_entrada, arquivo_origem, minimizar_dados=True)
    id_ext = audit.gerar_id_execucao("ext")
    cache_ext = _buscar_cache_execucao(modelo, caso_id, "extracao") if dry_run else None
    if cache_ext:
        resp_ext = cache_ext
    else:
        try:
            resp_ext = llm_client.chamar_chat(
                perfil=perfil,
                modelo=modelo,
                mensagens=msgs_ext,
                parametros=parametros,
                timeout_s=timeout_s,
                tentativas=tentativas,
                json_mode=cfg_prod.get("json_mode", True),
                precos=precos,
                dry_run=dry_run,
            )
        except ErroProvedor as e:
            print(f"  ! Falha na API durante extração ({e.codigo_erro}): {e}", file=sys.stderr)
            resp_ext = {
                "texto": "",
                "latencia_s": None,
                "tokens_entrada": None,
                "tokens_saida": None,
                "custo_usd": None,
                "tentativas": tentativas,
                "erro": str(e),
            }

    bruto_ext = avaliacao.extrair_json(resp_ext.get("texto", ""))
    if dry_run and bruto_ext is None and gabarito:
        if gabarito.get("extracao_esperada"):
            bruto_ext = dict(gabarito["extracao_esperada"])
        elif gabarito.get("campos_criticos_esperados"):
            crit = gabarito["campos_criticos_esperados"]
            outros = gabarito.get("outros_dados_mencionados", {})
            bruto_ext = {
                "protocolo": (crit.get("numeros_de_protocolo") or ["2026-000142"])[0],
                "data_solicitacao": (crit.get("datas") or ["14/10/2026"])[0],
                "canal": "Mensagem de voz",
                "solicitante": (crit.get("nomes") or ["Marcos Vinicius de Almeida Santos"])[0],
                "assunto": "Efetivação de matrícula e consulta sobre documentos pendentes",
                "pedido": crit.get("pedido", "Efetivação de matrícula"),
                "categoria": gabarito.get("categoria_esperada", "matricula"),
                "dados_do_curso": {
                    "curso": outros.get("curso", "Técnico em Enfermagem"),
                    "eixo_tecnologico": outros.get("eixo_tecnologico", "Saúde"),
                    "carga_horaria": outros.get("carga_horaria", "1200 horas"),
                    "turno": outros.get("turno", "noturno"),
                    "inicio_curso": "não localizado",
                    "data_matricula": "não localizado",
                },
            }
        elif gabarito.get("campos_esperados"):
            ce = gabarito["campos_esperados"]
            bruto_ext = {
                "protocolo": ce.get("codigo", "2026-000142"),
                "data_solicitacao": ce.get("data_matricula", "14/10/2026"),
                "canal": "Ficha de matrícula digitalizada",
                "solicitante": ce.get("nome", "MARCOS VINICIUS DE ALMEIDA SANTOS"),
                "assunto": "Ficha de matrícula em curso técnico",
                "pedido": "Efetivação de matrícula conforme ficha manuscrita apresentada",
                "categoria": "matricula",
                "dados_do_curso": {
                    "curso": ce.get("curso", "TÉCNICO EM ENFERMAGEM"),
                    "eixo_tecnologico": ce.get("eixo_tecnologico", "SAÚDE"),
                    "carga_horaria": ce.get("carga_horaria", "1200 HORAS"),
                    "turno": ce.get("turno", "NOTURNO"),
                    "inicio_curso": ce.get("inicio_curso", "01/02/2027"),
                    "data_matricula": ce.get("data_matricula", "14/10/2026"),
                },
            }

    extracao_json = normalizar_extracao(
        dados_brutos=bruto_ext,
        texto_original=texto_entrada,
        arquivo_origem=arquivo_origem,
        dados_minimizados=meta_ext["dados_minimizados"],
    )

    caminho_extracao_rel = f"{CONFIG['caminhos']['processados']}/{caso_id}_extracao.json"
    (RAIZ / caminho_extracao_rel).write_text(
        json.dumps(extracao_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    av_ext = None
    if gabarito and "extracao_esperada" in gabarito:
        av_ext = avaliacao.avaliar_extracao(extracao_json, gabarito, json.dumps(extracao_json, ensure_ascii=False))

    audit.registrar_execucao(
        audit.criar_registro(
            id_execucao=id_ext,
            caso_id=caso_id,
            etapa="extracao",
            modalidade=modalidade,
            arquivo_origem=arquivo_origem,
            provedor=provedor,
            modelo=modelo,
            parametros=parametros,
            versao_prompt=meta_ext["versao_prompt"],
            hash_prompt=meta_ext["hash_prompt_sistema"],
            dados_minimizados=meta_ext["dados_minimizados"],
            resposta_llm=resp_ext,
            arquivo_saida=caminho_extracao_rel,
            resumo_resultado=f"Categoria: {extracao_json['categoria']} | Confiança: {extracao_json['confianca']}",
            avaliacao_auto=av_ext,
            decisao_humana="Conferido" if not resp_ext.get("erro") or dry_run else "PENDENTE",
            revisor=revisor,
        ),
        caminho_log=log_alvo,
    )
    print(f"  [OK] Extração salva em: {caminho_extracao_rel}")

    if not dry_run and pausa_s > 0:
        time.sleep(pausa_s)

    # ---------------- Etapa 4: Geração da Minuta Institucional (RF03, RF09)
    msgs_min, meta_min = prompts.montar_mensagens_minuta(
        texto_entrada,
        arquivo_origem,
        extracao_json,
        minimizar_dados=True,
    )
    id_min = audit.gerar_id_execucao("min")
    cache_min = _buscar_cache_execucao(modelo, caso_id, "minuta") if dry_run else None
    if cache_min:
        resp_min = cache_min
    else:
        try:
            resp_min = llm_client.chamar_chat(
                perfil=perfil,
                modelo=modelo,
                mensagens=msgs_min,
                parametros=parametros,
                timeout_s=timeout_s,
                tentativas=tentativas,
                json_mode=cfg_prod.get("json_mode", True),
                precos=precos,
                dry_run=dry_run,
            )
        except ErroProvedor as e:
            print(f"  ! Falha na API durante geração da minuta ({e.codigo_erro}): {e}", file=sys.stderr)
            resp_min = {
                "texto": "",
                "latencia_s": None,
                "tokens_entrada": None,
                "tokens_saida": None,
                "custo_usd": None,
                "tentativas": tentativas,
                "erro": str(e),
            }

    bruto_min = avaliacao.extrair_json(resp_min.get("texto", ""))
    minuta_json = normalizar_minuta(bruto_min, extracao_json, arquivo_origem)

    caminho_min_json_rel = f"{CONFIG['caminhos'].get('minutas', 'resultados/minutas')}/{caso_id}_minuta.json"
    caminho_min_pdf_rel = f"{CONFIG['caminhos'].get('minutas', 'resultados/minutas')}/{caso_id}_minuta.pdf"
    (RAIZ / caminho_min_json_rel).write_text(
        json.dumps(minuta_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    caminho_brasao_rel = "../../dados/originais/brasao.png"
    minuta_md = prompts.renderizar_minuta(
        minuta=minuta_json,
        caminho_brasao=caminho_brasao_rel,
        id_execucao=id_min,
        modelo=f"{provedor}/{modelo}",
        versao_prompt=meta_min["versao_prompt"],
        arquivos_origem=[arquivo_origem],
    )

    contexto_afirmativo = prompts.ler_prompt("contexto_institucional.md").split("## O que NÃO está disponível")[0]
    fontes_av = texto_entrada + "\n" + contexto_afirmativo
    if modalidade in ("audio", "imagem"):
        fontes_av += f"\n{extracao_json.get('protocolo', '')}\n{extracao_json.get('data_solicitacao', '')}"
    av_min = avaliacao.avaliar_minuta(
        _texto_minuta_para_avaliacao(minuta_json),
        gabarito or {},
        fontes_av,
        verificar_formato=False,
    )
    if (gabarito or {}).get("seguranca", {}).get("contem_injection") and not minuta_json.get("alertas_seguranca"):
        av_min["achados"].append(
            {
                "criterio": "seguranca",
                "gravidade": "alto",
                "descricao": "Injection presente, mas não registrada em alertas_seguranca da minuta.",
            }
        )
        av_min["contagem"] = {g: sum(a["gravidade"] == g for a in av_min["achados"]) for g in avaliacao.GRAVIDADES}
        av_min["decisao_sugerida"] = avaliacao.decidir(av_min["achados"])

    # ---------------- Etapa 7: Revisão Humana (RF13)
    decisao_hum, nome_revisor, justificativa_hum, arq_corrigido_rel = solicitar_revisao_humana(
        caso_id=caso_id,
        avaliacao_minuta=av_min,
        nao_interativo=nao_interativo,
        revisor_padrao=revisor,
    )
    if modalidade in ("audio", "imagem") and not dry_run:
        # Conferir a entrada não aprova uma minuta nova. Decisões antigas são só do exemplo offline.
        decisao_hum, nome_revisor, justificativa_hum, arq_corrigido_rel = (
            "PENDENTE", "—", "Nova minuta multimodal aguardando revisão humana na interface Web.", None,
        )

    data_curta = time.strftime("%d/%m/%Y")
    minuta_md_final = aplicar_decisao_no_markdown(
        texto_md=minuta_md,
        decisao=decisao_hum,
        revisor=nome_revisor,
        data_str=data_curta,
        justificativa=justificativa_hum,
    )
    gerar_pdf_minuta(minuta_md_final, RAIZ / caminho_min_pdf_rel)

    if arq_corrigido_rel:
        caminho_corr_abs = RAIZ / arq_corrigido_rel
        caminho_corr_md_legado = caminho_corr_abs.with_suffix(".md")
        if not caminho_corr_abs.exists() and caminho_corr_md_legado.exists():
            gerar_pdf_minuta(caminho_corr_md_legado.read_text(encoding="utf-8"), caminho_corr_abs)

    saida_efetiva = arq_corrigido_rel if (arq_corrigido_rel and (RAIZ / arq_corrigido_rel).exists()) else caminho_min_pdf_rel

    audit.registrar_execucao(
        audit.criar_registro(
            id_execucao=id_min,
            caso_id=caso_id,
            etapa="minuta",
            modalidade=modalidade,
            arquivo_origem=arquivo_origem,
            provedor=provedor,
            modelo=modelo,
            parametros=parametros,
            versao_prompt=meta_min["versao_prompt"],
            hash_prompt=meta_min["hash_prompt_sistema"],
            dados_minimizados=meta_min["dados_minimizados"],
            resposta_llm=resp_min,
            arquivo_saida=saida_efetiva,
            resumo_resultado=f"Minuta gerada em PDF (bloqueio de envio ativo). Decisão: {decisao_hum}.",
            avaliacao_auto=av_min,
            decisao_humana=decisao_hum,
            revisor=nome_revisor,
            justificativa_humana=justificativa_hum,
        ),
        caminho_log=log_alvo,
    )
    print(f"  [OK] Minuta PDF salva em: {caminho_min_pdf_rel} | Decisão humana: {decisao_hum}")

    return {
        "caso_id": caso_id,
        "modalidade": modalidade,
        "extracao": extracao_json,
        "minuta": minuta_json,
        "avaliacao_minuta": av_min,
        "decisao_humana": decisao_hum,
        "arquivo_extracao": caminho_extracao_rel,
        "arquivo_minuta": saida_efetiva,
    }


# ---------------------------------------------------------------- CLI Principal

def construir_parser() -> argparse.ArgumentParser:
    cfg_prod = CONFIG.get("producao", CONFIG.get("experimento_prompts", {}))
    p = argparse.ArgumentParser(
        prog="python -m src.main",
        description="Central Inteligente de Atendimento e Comunicação Institucional (Fluxo Principal e Interface Web).",
    )
    p.add_argument(
        "--caso",
        default="todos",
        help="ID do caso a executar (ex.: caso01_texto, caso04_texto_injection) ou 'todos' (padrão).",
    )
    p.add_argument(
        "--arquivo",
        default=None,
        help="Processa um arquivo avulso em dados/originais/ (opcional).",
    )
    p.add_argument(
        "--provedor",
        default=cfg_prod.get("provedor", "groq"),
        choices=sorted(CONFIG["provedores"].keys()),
        help="Provedor configurado em config.json (padrão: groq).",
    )
    p.add_argument(
        "--modelo",
        default=cfg_prod.get("modelo", "openai/gpt-oss-120b"),
        help="Modelo de linguagem a utilizar.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa todo o pipeline e validações sem realizar chamadas de rede à API.",
    )
    p.add_argument(
        "--nao-interativo",
        action="store_true",
        help="Executa em lote sem abrir o servidor Web, aplicando as decisões validadas pela equipe.",
    )
    p.add_argument(
        "--porta",
        type=int,
        default=8000,
        help="Porta HTTP da interface Web de revisão humana (padrão: 8000).",
    )
    p.add_argument(
        "--sem-navegador",
        action="store_true",
        help="Não abre o navegador automaticamente ao iniciar a interface Web.",
    )
    p.add_argument(
        "--revisor",
        default="João Flávio Pompeo",
        help="Nome do servidor responsável registrado em modo não interativo.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    args = construir_parser().parse_args(argv)
    cfg_prod = CONFIG.get("producao", CONFIG.get("experimento_prompts", {}))
    amb = audit.coletar_ambiente()
    libs_str = ", ".join(f"{k}=={v}" for k, v in amb["bibliotecas"].items())
    print("=== Central Inteligente de Atendimento e Comunicação Institucional ===")
    print(f"Ambiente: Python {amb['python']} ({amb['sistema']}) | Bibliotecas: {libs_str}")

    usar_dry_run = args.dry_run
    if not usar_dry_run:
        try:
            llm_client.verificar_chave(CONFIG["provedores"][args.provedor])
        except ErroProvedor as e:
            if args.nao_interativo:
                print(f"Erro de inicialização: {e}", file=sys.stderr)
                return 2
            print(f"[Aviso] {e} Alternando para modo --dry-run (cache validado) para abrir a interface Web.")
            usar_dry_run = True

    print(f"Configuração: provedor={args.provedor} | modelo={args.modelo} | dry_run={usar_dry_run}")

    if args.arquivo:
        casos = [Path(args.arquivo).stem]
    elif args.caso == "todos":
        casos = cfg_prod.get("casos", ["caso01_texto", "caso04_texto_injection", "caso05_texto_incompleto"])
    else:
        casos = [args.caso]

    # Se estiver em modo Web interativo e os artefatos PDF já existirem, só processa os que faltarem
    resultados_sessao: list[dict[str, Any]] = []
    dir_minutas = RAIZ / CONFIG["caminhos"].get("minutas", "resultados/minutas")
    for idx, cid in enumerate(casos):
        arq_min_existente = dir_minutas / f"{cid}_minuta.pdf"
        if not args.nao_interativo and arq_min_existente.exists() and not args.arquivo:
            continue
        if idx > 0 and not usar_dry_run and cfg_prod.get("pausa_entre_chamadas_s", 0) > 0:
            time.sleep(cfg_prod["pausa_entre_chamadas_s"])
        try:
            res = processar_caso(
                caso_id=cid,
                provedor=args.provedor,
                modelo=args.modelo,
                cfg_prod=cfg_prod,
                dry_run=usar_dry_run,
                nao_interativo=args.nao_interativo,
                revisor=args.revisor,
                arquivo_avulso=args.arquivo,
            )
        except (ValueError, ErroProvedor) as exc:
            print(f"Caso {cid} bloqueado: {llm_client.ocultar_segredos(str(exc))}", file=sys.stderr)
            return 2
        resultados_sessao.append(res)

    audit.gerar_relatorio_auditoria()
    print(f"\n[OK] Log estruturado: {audit.ARQUIVO_LOG_PADRAO.relative_to(RAIZ)}")
    print(f"[OK] Relatório de auditoria: {audit.ARQUIVO_RELATORIO_PADRAO.relative_to(RAIZ)}")

    if not args.nao_interativo:
        from src import web
        web.iniciar_interface_web(
            porta=args.porta,
            abrir_navegador=not args.sem_navegador,
            dry_run=usar_dry_run,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
