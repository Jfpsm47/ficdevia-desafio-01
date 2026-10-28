"""Dados fictícios e gabaritos do Desafio 02: geração, verificação e congelamento (seção 6).

Responsabilidade: Estudante 1.
- `gerar-pdfs`: recria os PDFs textuais do acervo a partir de dados/acervo_fontes/ (bytes reprodutíveis).
- `verificar`: confere quantidades da seção 6, contratos (src/schemas.py) e coerência dos gabaritos com
  as fontes (todo trecho de referência e toda entidade literal precisam existir no original).
- `congelar`: depois da validação humana, grava o SHA-256 de dados e gabaritos, para provar que os
  resultados de referência precederam as chamadas ao modelo.

Uso:
  python -m src.dados_ficticios verificar
  python -m src.dados_ficticios gerar-pdfs
  python -m src.dados_ficticios congelar
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src import prompts, schemas

RAIZ = prompts.RAIZ
DIR_ACERVO = RAIZ / "dados/acervo"
DIR_FONTES = RAIZ / "dados/acervo_fontes"
DIR_GABARITOS = RAIZ / "dados/gabaritos/d2"
ARQ_CATALOGO = DIR_ACERVO / "catalogo.json"
ARQ_AVALIACOES = RAIZ / "dados/avaliacoes/avaliacoes.csv"
ARQ_HASHES = DIR_GABARITOS / "HASHES.json"

QUEBRA_PAGINA = "[[QUEBRA DE PÁGINA]]"
DATA_FIXA_PDF = datetime(2026, 10, 28, tzinfo=timezone.utc)  # fixa os bytes do PDF entre gerações

# Quantidades mínimas da seção 6 do enunciado.
PERFIS_SOLICITACOES = {"completa": 4, "incompleta": 1, "ambigua": 1}
TIPOS_PERGUNTAS = {"respondivel": 5, "sem_resposta": 2, "contraditoria": 1}
GRUPOS_AVALIACOES = {"positiva": 3, "negativa": 3, "neutra": 3, "ambigua_ou_mista": 3}
ALVOS_ADVERSARIAIS = {"solicitacao", "acervo", "segredo"}


def normalizar(texto: str) -> str:
    """Comparação tolerante a quebras de linha, caixa e acentos (o PDF quebra linhas ao extrair)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


def relativo(caminho: Path) -> str:
    """Caminho relativo à raiz do projeto, para registros portáveis (absoluto se estiver fora dela)."""
    try:
        return caminho.relative_to(RAIZ).as_posix()
    except ValueError:
        return caminho.as_posix()


# ---------------------------------------------------------------- Acervo

def ler_catalogo() -> list[schemas.DocumentoAcervo]:
    return [schemas.DocumentoAcervo.model_validate(d) for d in ler_json(ARQ_CATALOGO)["documentos"]]


def gerar_pdf(texto_fonte: str, titulo: str) -> bytes:
    """PDF textual simples: títulos numerados em negrito; o marcador de quebra inicia nova página."""
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_creation_date(DATA_FIXA_PDF)
    pdf.set_title(titulo)
    pdf.set_author("Material fictício - Desafio 02")
    pdf.set_margins(20, 20, 20)
    pdf.add_page()
    for bloco in texto_fonte.strip().split("\n\n"):
        bloco = bloco.strip()
        if bloco == QUEBRA_PAGINA:
            pdf.add_page()
            continue
        for linha in bloco.splitlines():
            negrito = bool(re.match(r"^\d+\. ", linha))
            pdf.set_font("Helvetica", "B" if negrito else "", 11)
            pdf.multi_cell(0, 6, linha, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    return bytes(pdf.output())


def gerar_pdfs() -> list[Path]:
    caminhos = []
    for doc in ler_catalogo():
        if doc.formato == "pdf":
            fonte = (DIR_FONTES / f"{doc.documento_id}.txt").read_text(encoding="utf-8")
            destino = RAIZ / doc.arquivo
            destino.write_bytes(gerar_pdf(fonte, doc.titulo))
            caminhos.append(destino)
    return caminhos


def paginas_documento(doc: schemas.DocumentoAcervo) -> list[tuple[int | None, str]]:
    """Texto do documento como (página, texto). TXT não tem página (None)."""
    caminho = RAIZ / doc.arquivo
    if doc.formato == "txt":
        return [(None, caminho.read_text(encoding="utf-8"))]
    from pypdf import PdfReader

    leitor = PdfReader(io.BytesIO(caminho.read_bytes()))
    return [(i, pagina.extract_text() or "") for i, pagina in enumerate(leitor.pages, start=1)]


def texto_documento(doc: schemas.DocumentoAcervo) -> str:
    return "\n".join(texto for _, texto in paginas_documento(doc))


# ---------------------------------------------------------------- Verificações

def _verificar_acervo(problemas: list[str]) -> dict[str, str]:
    try:
        docs = ler_catalogo()
    except Exception as exc:  # contrato violado no catálogo
        problemas.append(f"catálogo inválido: {exc}")
        return {}
    if len(docs) < 6:
        problemas.append(f"acervo com {len(docs)} documentos; mínimo: 6")
    if len({d.tema for d in docs}) < 2:
        problemas.append("acervo precisa de ao menos dois temas")
    if {d.formato for d in docs} != {"txt", "pdf"}:
        problemas.append("acervo precisa de documentos TXT e PDF")
    textos: dict[str, str] = {}
    for doc in docs:
        caminho = RAIZ / doc.arquivo
        if not caminho.is_file():
            problemas.append(f"{doc.documento_id}: arquivo ausente ({doc.arquivo}); rode gerar-pdfs")
            continue
        if doc.formato == "pdf":
            fonte = (DIR_FONTES / f"{doc.documento_id}.txt").read_text(encoding="utf-8")
            if gerar_pdf(fonte, doc.titulo) != caminho.read_bytes():
                problemas.append(f"{doc.documento_id}: PDF desatualizado em relação à fonte; rode gerar-pdfs")
        texto = texto_documento(doc)
        cabecalho = normalizar(texto[:600])
        for rotulo, valor in (("identificador", doc.documento_id), ("versao", doc.versao)):
            if normalizar(f"{rotulo}: {valor}") not in cabecalho:
                problemas.append(f"{doc.documento_id}: cabeçalho sem '{rotulo}: {valor}'")
        textos[doc.documento_id] = texto
    return textos


def _verificar_solicitacoes(problemas: list[str]) -> None:
    perfis: Counter[str] = Counter()
    modalidades: set[str] = set()
    for caminho in sorted((DIR_GABARITOS / "solicitacoes").glob("*.json")):
        gab = ler_json(caminho)
        nome = caminho.name
        origem = RAIZ / gab["arquivo_origem"]
        if not origem.is_file():
            problemas.append(f"{nome}: arquivo de origem ausente ({gab['arquivo_origem']})")
            continue
        texto = normalizar(origem.read_text(encoding="utf-8"))
        if gab.get("conjunto_rf15"):
            perfis[gab["perfil"]] += 1
            modalidades.add(gab["modalidade_original"])
        esperado = gab["extracao_esperada"]
        if esperado["categoria"] not in prompts.ids_categorias():
            problemas.append(f"{nome}: categoria '{esperado['categoria']}' fora de prompts/categorias.json")
        nulos = {c for c in ("protocolo", "data_solicitacao", "canal", "solicitante", "curso", "pedido")
                 if c in esperado and esperado[c] is None}
        if nulos != set(esperado["campos_ausentes"]):
            problemas.append(f"{nome}: campos_ausentes não corresponde aos campos nulos")
        for ent in gab["entidades_esperadas"]:
            if ent["origem"] == "literal" and normalizar(ent["evidencia"]) not in texto:
                problemas.append(f"{nome}: evidência de '{ent['valor']}' não está no original")
        for valor in gab.get("nao_deve_aparecer_na_extracao", []):
            if normalizar(valor) not in texto:
                problemas.append(f"{nome}: item proibido '{valor}' nem existe no original (gabarito inócuo)")
        if gab["perfil"] == "ambigua" and not gab.get("justificativa_rotulo"):
            problemas.append(f"{nome}: rótulo ambíguo sem justificativa")
    for perfil, minimo in PERFIS_SOLICITACOES.items():
        if perfis[perfil] < minimo:
            problemas.append(f"conjunto RF15 com {perfis[perfil]} solicitação(ões) '{perfil}'; mínimo: {minimo}")
    if not {"audio", "ocr"} <= modalidades:
        problemas.append("conjunto RF15 precisa reaproveitar saídas de áudio e de OCR")


def _verificar_perguntas(problemas: list[str], textos: dict[str, str]) -> None:
    gab = ler_json(DIR_GABARITOS / "rag_perguntas.json")
    tipos = Counter(p["tipo"] for p in gab["perguntas"])
    for tipo, minimo in TIPOS_PERGUNTAS.items():
        if tipos[tipo] < minimo:
            problemas.append(f"perguntas RAG com {tipos[tipo]} do tipo '{tipo}'; mínimo: {minimo}")
    for p in gab["perguntas"]:
        if p["tipo"] != "sem_resposta" and not p["referencias"]:
            problemas.append(f"{p['id']}: pergunta '{p['tipo']}' sem trecho de referência")
        if p["tipo"] == "contraditoria" and len({r["documento_id"] for r in p["referencias"]}) < 2:
            problemas.append(f"{p['id']}: conflito precisa de referências em dois documentos")
        for ref in p["referencias"]:
            texto = normalizar(textos.get(ref["documento_id"], ""))
            if normalizar(ref["secao"]) not in texto:
                problemas.append(f"{p['id']}: seção '{ref['secao']}' não encontrada em {ref['documento_id']}")
            if normalizar(ref["trecho"]) not in texto:
                problemas.append(f"{p['id']}: trecho de referência não encontrado em {ref['documento_id']}")


def _verificar_avaliacoes(problemas: list[str]) -> None:
    with ARQ_AVALIACOES.open(encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f))
    ids = []
    for linha in linhas:
        res = schemas.validar(schemas.AvaliacaoAtendimento, linha)
        if not res.valido:
            problemas.append(f"avaliação {linha.get('id_avaliacao')}: {res.erros}")
        ids.append(linha.get("id_avaliacao"))
    if len(ids) != len(set(ids)):
        problemas.append("avaliações com id repetido")
    gab = ler_json(DIR_GABARITOS / "sentimentos.json")
    rotulos = {r["id_avaliacao"]: r for r in gab["rotulos"]}
    if set(rotulos) != set(ids):
        problemas.append("gabarito de sentimentos não cobre exatamente as avaliações do CSV")
    grupos = Counter(r["grupo"] for r in rotulos.values())
    for grupo, minimo in GRUPOS_AVALIACOES.items():
        if grupos[grupo] < minimo:
            problemas.append(f"avaliações do grupo '{grupo}': {grupos[grupo]}; mínimo: {minimo}")
    for r in rotulos.values():
        if r["polaridade_esperada"] not in ("positiva", "negativa", "neutra", "indeterminada"):
            problemas.append(f"{r['id_avaliacao']}: polaridade inválida")
        if r["grupo"] == "ambigua_ou_mista" and not (r.get("justificativa_rotulo") and r["requer_revisao_esperado"]):
            problemas.append(f"{r['id_avaliacao']}: rótulo ambíguo exige justificativa e revisão")


def _verificar_adversariais(problemas: list[str], textos: dict[str, str]) -> None:
    gab = ler_json(DIR_GABARITOS / "adversariais.json")
    alvos = {a["alvo"] for a in gab["ataques"]}
    if not ALVOS_ADVERSARIAIS <= alvos:
        problemas.append(f"ataques adversariais sem os alvos: {sorted(ALVOS_ADVERSARIAIS - alvos)}")
    for ataque in gab["ataques"]:
        if ataque["alvo"] == "acervo":
            texto = textos.get(ataque["documento_id"], "")
        else:
            caminho = RAIZ / ataque["arquivo_origem"]
            texto = caminho.read_text(encoding="utf-8") if caminho.is_file() else ""
        if normalizar(ataque["trecho_malicioso"]) not in normalizar(texto):
            problemas.append(f"{ataque['id']}: trecho malicioso não encontrado na entrada")
        if not set(ataque["decisoes_aceitas"]) <= {"bloquear", "revisar"}:
            problemas.append(f"{ataque['id']}: decisão aceita deve ser 'bloquear' ou 'revisar'")


def verificar() -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = conjunto coerente)."""
    problemas: list[str] = []
    textos = _verificar_acervo(problemas)
    _verificar_solicitacoes(problemas)
    _verificar_perguntas(problemas, textos)
    _verificar_avaliacoes(problemas)
    _verificar_adversariais(problemas, textos)
    return problemas


# ---------------------------------------------------------------- Validação humana e congelamento

def arquivos_gabarito() -> list[Path]:
    return sorted(p for p in DIR_GABARITOS.rglob("*.json") if p != ARQ_HASHES)


def pendentes_validacao() -> list[str]:
    return [relativo(p) for p in arquivos_gabarito()
            if str(ler_json(p).get("status_validacao_humana", "")).upper().startswith("PENDENTE")]


def arquivos_congelados() -> list[Path]:
    dados = [ARQ_CATALOGO, *(RAIZ / d.arquivo for d in ler_catalogo()), ARQ_AVALIACOES]
    entradas = {RAIZ / ler_json(p)["arquivo_origem"] for p in (DIR_GABARITOS / "solicitacoes").glob("*.json")}
    entradas |= {RAIZ / a["arquivo_origem"] for a in ler_json(DIR_GABARITOS / "adversariais.json")["ataques"]
                 if a.get("arquivo_origem")}
    return sorted({*dados, *entradas, *arquivos_gabarito()})


def congelar() -> Path:
    """Grava os hashes. Recusa se houver problema de coerência ou gabarito ainda PENDENTE."""
    problemas = verificar()
    if problemas:
        raise ValueError("Conjunto incoerente; rode 'verificar' e corrija antes de congelar.")
    pendentes = pendentes_validacao()
    if pendentes:
        raise ValueError(f"Gabaritos ainda PENDENTES de validação humana: {', '.join(pendentes)}")
    hashes = {relativo(p): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in arquivos_congelados()}
    registro = {"congelado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
                "observacao": "Resultados de referência congelados antes das chamadas ao modelo.",
                "arquivos": hashes}
    ARQ_HASHES.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
                          newline="\n")
    return ARQ_HASHES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dados fictícios e gabaritos do Desafio 02.")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("verificar", help="Confere quantidades, contratos e coerência dos gabaritos")
    sub.add_parser("gerar-pdfs", help="Recria os PDFs do acervo a partir de dados/acervo_fontes/")
    sub.add_parser("congelar", help="Grava os hashes depois da validação humana")
    args = parser.parse_args(argv)

    if args.comando == "gerar-pdfs":
        for caminho in gerar_pdfs():
            print(f"[OK] {relativo(caminho)}")
        return 0
    if args.comando == "congelar":
        print(f"[OK] Hashes gravados em {relativo(congelar())}")
        return 0
    problemas = verificar()
    for p in problemas:
        print(f"[PROBLEMA] {p}")
    for p in pendentes_validacao():
        print(f"[PENDENTE] validação humana: {p}")
    print("[OK] Conjunto coerente." if not problemas else f"{len(problemas)} problema(s).")
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())
