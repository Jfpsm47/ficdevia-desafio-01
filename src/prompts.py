"""Prompts de produção (RF03, RF14, RF15, RF19), minimização de dados (RF12) e modelo institucional da minuta (RF09).

Os textos dos prompts ficam versionados em prompts/; este módulo apenas os carrega e monta as
mensagens, mantendo instruções do sistema separadas do conteúdo não confiável do cidadão e do acervo.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROMPTS = RAIZ / "prompts"
NAO_LOCALIZADO = "não localizado"

VERSOES = {
    "extracao": ("producao/sistema_extracao_v1.md", "extracao-v1.0"),
    "minuta": ("producao/sistema_minuta_v1.md", "minuta-v1.0"),
    "imagem": ("producao/imagem_orientacao_v1.md", "imagem-v1.4"),
    # v2.0 (producao/sistema_extracao_v2.md) fica preservado: é a linha de base da execução de 28/10/2026 17:17.
    "extracao_v2": ("producao/sistema_extracao_v2_1.md", "extracao-v2.1"),
    "correcao_esquema": ("producao/correcao_esquema_v1.md", "correcao-esquema-v1.0"),
    "resumo": ("producao/sistema_resumo_v1.md", "resumo-v1.0"),
    "rag_consulta": ("producao/sistema_rag_consulta_v1.md", "rag-consulta-v1.0"),
    "rag_minuta": ("producao/sistema_rag_minuta_v1.md", "rag-minuta-v1.0"),
    "sentimento": ("producao/sistema_sentimento_v1.md", "sentimento-v1.0"),
}

# Nome próprio: palavras com inicial maiúscula na mesma linha, admitindo "de/da/do/dos/das" entre elas.
# Delimitar o nome assim evita engolir o resto da frase ("... Santos e o meu e-mail é ...", vindo de
# transcrição) ou o rótulo da linha seguinte ("E-mail:", em ficha de OCR).
_NOME = r"[A-ZÀ-Ý][\wÀ-ÿ'-]+(?:[ \t]+(?:d[aeo]s?[ \t]+)?[A-ZÀ-Ý][\wÀ-ÿ'-]+)*"
_DATA = r"(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}º? de [a-zç]+ de \d{4})"

# Ordem importa: o CPF é removido antes do padrão de telefone. Os padrões cobrem o formato de formulário
# ("RG: ...") e o de frase falada ou escrita ("Meu RG é ...", "o nome da minha mãe é ...").
_PADROES_MINIMIZACAO = [
    ("CPF", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF REMOVIDO]"),
    ("e-mail", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[E-MAIL REMOVIDO]"),
    ("RG", re.compile(r"\b(RG)(?:\s*(?:é|e|:|n[º°o]\.?))?\s*[\dxX][\d.\-xX]{3,}[\dxX]", re.I), r"\1 [RG REMOVIDO]"),
    ("filiação", re.compile(r"((?i:nome d[ao] (?:minha |meu )?(?:m[ãa]e|pai)|filia[çc][ãa]o))(?:[ \t]+é)?[,: \t]+" + _NOME),
     r"\1: [FILIAÇÃO REMOVIDA]"),
    ("data de nascimento",
     re.compile(r"(nasci(?:do|da)? em|data de nascimento:?)\s*" + _DATA, re.I),
     r"\1 [DATA DE NASCIMENTO REMOVIDA]"),
    ("telefone", re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[TELEFONE REMOVIDO]"),
]

_TAGS_RESERVADAS = re.compile(
    r"<\s*/?\s*(conteudo_nao_confiavel|contexto_institucional|dados_extraidos|"
    r"acervo_recuperado|consulta_nao_confiavel|dados_solicitacao|trecho_acervo)[^>]*>",
    re.I,
)


def ler_prompt(caminho_relativo: str) -> str:
    return (DIR_PROMPTS / caminho_relativo).read_text(encoding="utf-8")


def hash_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:12]


def categorias_formatadas() -> str:
    dados = json.loads(ler_prompt("categorias.json"))
    return "\n".join(f"- {c['id']}: {c['descricao']}" for c in dados["categorias"])


def ids_categorias() -> list[str]:
    return [c["id"] for c in json.loads(ler_prompt("categorias.json"))["categorias"]]


def minimizar(texto: str) -> tuple[str, dict[str, int]]:
    """Mascara dados pessoais desnecessários antes do envio ao provedor (RF12).

    Retorna o texto mascarado e a contagem por tipo (nunca os valores), para o registro.
    """
    removidos: dict[str, int] = {}
    for tipo, padrao, substituto in _PADROES_MINIMIZACAO:
        texto, n = padrao.subn(substituto, texto)
        if n:
            removidos[tipo] = n
    return texto, removidos


def delimitar(texto: str, arquivo_origem: str) -> str:
    """Envolve o conteúdo externo em tag com id aleatório e neutraliza tags reservadas dentro dele."""
    neutralizado = _TAGS_RESERVADAS.sub("[tag removida]", texto)
    nonce = secrets.token_hex(4)
    return (f'<conteudo_nao_confiavel id="{nonce}" arquivo="{arquivo_origem}">\n'
            f"{neutralizado.strip()}\n</conteudo_nao_confiavel>")


def delimitar_consulta(consulta: str) -> str:
    """Envolve uma pergunta externa ao RAG em tag com nonce e neutraliza tags reservadas (RF16, RF19)."""
    neutralizado = _TAGS_RESERVADAS.sub("[tag removida]", consulta)
    nonce = secrets.token_hex(4)
    return f'<consulta_nao_confiavel id="{nonce}">\n{neutralizado.strip()}\n</consulta_nao_confiavel>'


def delimitar_acervo_recuperado(trechos_busca: list[Any]) -> str:
    """Delimita os trechos recuperados do acervo tratando instruções internas como dados não confiáveis (RF16, RF19)."""
    nonce = secrets.token_hex(4)
    if not trechos_busca:
        return f'<acervo_recuperado id="{nonce}">\n(nenhum trecho recuperado)\n</acervo_recuperado>'

    partes: list[str] = []
    for item in trechos_busca:
        d = item.para_dict() if hasattr(item, "para_dict") else (item.model_dump() if hasattr(item, "model_dump") else dict(item))
        texto_limpo = _TAGS_RESERVADAS.sub("[tag removida]", str(d.get("texto", ""))).strip()
        pag = d.get("pagina")
        pag_str = str(pag) if pag is not None else "nao_aplicavel"
        secao_str = str(d.get("secao") or "sem_secao").replace('"', "'")
        titulo_str = str(d.get("titulo_documento") or "").replace('"', "'")
        vig_str = str(d.get("vigencia_inicio") or "nao_informada")
        sim_val = d.get("similaridade")
        sim_str = f"{sim_val:.4f}" if isinstance(sim_val, (int, float)) else "—"

        atributos = (
            f'chunk_id="{d["chunk_id"]}" '
            f'documento_id="{d["documento_id"]}" '
            f'versao="{d["versao_documento"]}" '
            f'titulo="{titulo_str}" '
            f'vigencia_inicio="{vig_str}" '
            f'pagina="{pag_str}" '
            f'secao="{secao_str}" '
            f'similaridade_vetorial="{sim_str}"'
        )
        partes.append(f"<trecho_acervo {atributos}>\n{texto_limpo}\n</trecho_acervo>")

    corpo = "\n\n".join(partes)
    return f'<acervo_recuperado id="{nonce}">\n{corpo}\n</acervo_recuperado>'


def montar_mensagens_extracao(texto: str, arquivo_origem: str, minimizar_dados: bool = True):
    """Mensagens para a etapa de triagem/extração (RF05). Retorna (mensagens, metadados)."""
    removidos = {}
    if minimizar_dados:
        texto, removidos = minimizar(texto)
    sistema = ler_prompt(VERSOES["extracao"][0]).replace("{{CATEGORIAS}}", categorias_formatadas())
    usuario = ("Analise o conteúdo abaixo e devolva o JSON definido nas instruções.\n\n"
               + delimitar(texto, arquivo_origem))
    meta = {"versao_prompt": VERSOES["extracao"][1], "hash_prompt_sistema": hash_texto(sistema),
            "dados_minimizados": removidos}
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def montar_mensagens_extracao_v2(texto: str, arquivo_origem: str, minimizar_dados: bool = True):
    """Mensagens da extração estruturada do Desafio 02 (RF14, contrato SolicitacaoExtraida).

    Retorna (mensagens, metadados). O texto enviado já minimizado volta nos metadados, para que as
    regras de negócio aceitem evidências citadas a partir dele.
    """
    removidos = {}
    if minimizar_dados:
        texto, removidos = minimizar(texto)
    sistema = ler_prompt(VERSOES["extracao_v2"][0]).replace("{{CATEGORIAS}}", categorias_formatadas())
    usuario = ("Extraia os dados do conteúdo abaixo no formato do esquema.\n\n" + delimitar(texto, arquivo_origem))
    meta = {"versao_prompt": VERSOES["extracao_v2"][1], "hash_prompt_sistema": hash_texto(sistema),
            "dados_minimizados": removidos, "texto_enviado": texto}
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def montar_mensagens_resumo(texto: str, arquivo_origem: str, minimizar_dados: bool = True):
    """Mensagens da sumarização (RF15, contrato ResumoSolicitacao). Retorna (mensagens, metadados)."""
    removidos = {}
    if minimizar_dados:
        texto, removidos = minimizar(texto)
    sistema = ler_prompt(VERSOES["resumo"][0])
    usuario = "Resuma o conteúdo abaixo no formato do esquema.\n\n" + delimitar(texto, arquivo_origem)
    meta = {"versao_prompt": VERSOES["resumo"][1], "hash_prompt_sistema": hash_texto(sistema),
            "dados_minimizados": removidos, "texto_enviado": texto}
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def montar_mensagens_sentimento(id_avaliacao: str, texto: str, minimizar_dados: bool = True):
    """Mensagens da classificação de sentimento (RF22, contrato ClassificacaoSentimento).

    Só o ID e o texto da avaliação vão ao provedor; data, canal e categoria ficam fora (minimização).
    """
    removidos = {}
    if minimizar_dados:
        texto, removidos = minimizar(texto)
    sistema = ler_prompt(VERSOES["sentimento"][0])
    usuario = (f"Classifique a avaliação de atendimento id_avaliacao={id_avaliacao} no formato do esquema.\n\n"
               + delimitar(texto, f"avaliacoes.csv#{id_avaliacao}"))
    meta = {"versao_prompt": VERSOES["sentimento"][1], "hash_prompt_sistema": hash_texto(sistema),
            "dados_minimizados": removidos}
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def montar_mensagens_rag_consulta(
    consulta: str,
    trechos_busca: list[Any],
    minimizar_dados: bool = True,
):
    """Monta mensagens seguras para consulta fundamentada ao acervo com RAG (RF19)."""
    removidos: dict[str, int] = {}
    if minimizar_dados:
        consulta, removidos = minimizar(consulta)
    sistema = ler_prompt(VERSOES["rag_consulta"][0])
    usuario = (
        f"{delimitar_consulta(consulta)}\n\n"
        f"{delimitar_acervo_recuperado(trechos_busca)}\n\n"
        "Responda à consulta no formato estrito do esquema, citando apenas chunk_ids presentes em <acervo_recuperado>."
    )
    meta = {
        "versao_prompt": VERSOES["rag_consulta"][1],
        "hash_prompt_sistema": hash_texto(sistema),
        "dados_minimizados": removidos,
        "consulta_enviada": consulta,
    }
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def montar_mensagens_rag_minuta(
    texto_solicitacao: str,
    arquivo_origem: str,
    dados_solicitacao: dict[str, Any] | None,
    trechos_busca: list[Any],
    minimizar_dados: bool = True,
):
    """Monta mensagens seguras para geração de minuta separando dados do cidadão e orientações do acervo (RF19)."""
    removidos: dict[str, int] = {}
    if minimizar_dados:
        texto_solicitacao, removidos = minimizar(texto_solicitacao)
    sistema = ler_prompt(VERSOES["rag_minuta"][0])
    bloco_dados = _TAGS_RESERVADAS.sub(
        "[tag removida]",
        json.dumps(dados_solicitacao or {}, ensure_ascii=False, indent=2),
    )
    usuario = (
        f"<dados_solicitacao>\n{bloco_dados}\n</dados_solicitacao>\n\n"
        f"{delimitar(texto_solicitacao, arquivo_origem)}\n\n"
        f"{delimitar_acervo_recuperado(trechos_busca)}\n\n"
        "Redija a minuta fundamentada no formato estrito do esquema, separando fatos do caso e normas do acervo."
    )
    meta = {
        "versao_prompt": VERSOES["rag_minuta"][1],
        "hash_prompt_sistema": hash_texto(sistema),
        "dados_minimizados": removidos,
        "texto_enviado": texto_solicitacao,
    }
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def mensagem_correcao_esquema(erros: list[dict[str, str]]) -> str:
    """Mensagem da única tentativa de correção (RF14, RF19). Os erros trazem campo e motivo, nunca valores."""
    linhas = "\n".join(f"- {e['campo']}: {e['categoria']} ({e['detalhe']})" for e in erros)
    return ler_prompt(VERSOES["correcao_esquema"][0]).replace("{{ERROS}}", linhas)


def montar_mensagens_minuta(texto: str, arquivo_origem: str, extracao: dict | None,
                            minimizar_dados: bool = True):
    """Mensagens para a geração da minuta (RF09). Retorna (mensagens, metadados)."""
    removidos = {}
    if minimizar_dados:
        texto, removidos = minimizar(texto)
    sistema = ler_prompt(VERSOES["minuta"][0])
    contexto = ler_prompt("contexto_institucional.md")
    extraidos = json.dumps(extracao or {}, ensure_ascii=False, indent=2)
    usuario = (f"<contexto_institucional>\n{contexto.strip()}\n</contexto_institucional>\n\n"
               f"<dados_extraidos>\n{_TAGS_RESERVADAS.sub('[tag removida]', extraidos)}\n</dados_extraidos>\n\n"
               f"{delimitar(texto, arquivo_origem)}\n\n"
               "Redija a minuta conforme as instruções do sistema e devolva somente o JSON.")
    meta = {"versao_prompt": VERSOES["minuta"][1], "hash_prompt_sistema": hash_texto(sistema),
            "dados_minimizados": removidos}
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}], meta


def _lista_md(itens) -> str:
    itens = [str(i) for i in (itens or []) if str(i).strip()]
    return "\n".join(f"- {i}" for i in itens) if itens else "- nenhuma"


def renderizar_minuta(minuta: dict, caminho_brasao: str, id_execucao: str, modelo: str,
                      versao_prompt: str = VERSOES["minuta"][1], arquivos_origem: list[str] | None = None) -> str:
    """Aplica o JSON da minuta ao modelo institucional (prompts/producao/modelo_minuta.md).

    Os arquivos de origem são incluídos pelo sistema (RF09), sem depender do que o modelo listou.
    """
    ref = minuta.get("referencia") or {}
    corpo = minuta.get("corpo") or []
    if isinstance(corpo, str):
        corpo = [corpo]
    valores = {
        "BRASAO": caminho_brasao,
        "PROTOCOLO": ref.get("protocolo") or NAO_LOCALIZADO,
        "DATA": ref.get("data") or NAO_LOCALIZADO,
        "DESTINATARIO": minuta.get("destinatario") or NAO_LOCALIZADO,
        "ASSUNTO": minuta.get("assunto") or NAO_LOCALIZADO,
        "SAUDACAO": minuta.get("saudacao") or "",
        "CORPO": "\n\n".join(corpo),
        "FECHO": minuta.get("fecho") or "Atenciosamente,",
        "NAO_LOCALIZADAS": _lista_md(minuta.get("informacoes_nao_localizadas")),
        "FONTES": ", ".join(dict.fromkeys([*(arquivos_origem or []), *map(str, minuta.get("fontes") or [])]))
                  or NAO_LOCALIZADO,
        "ID_EXECUCAO": id_execucao,
        "MODELO": modelo,
        "VERSAO_PROMPT": versao_prompt,
    }
    texto = ler_prompt("producao/modelo_minuta.md")
    for chave, valor in valores.items():
        texto = texto.replace("{{" + chave + "}}", str(valor))
    return texto
