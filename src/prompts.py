"""Prompts de produção (RF03), minimização de dados (RF12) e modelo institucional da minuta (RF09).

Os textos dos prompts ficam versionados em prompts/; este módulo apenas os carrega e monta as
mensagens, mantendo instruções do sistema separadas do conteúdo não confiável do cidadão.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
from pathlib import Path

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
    r"<\s*/?\s*(conteudo_nao_confiavel|contexto_institucional|dados_extraidos)[^>]*>", re.I)


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


def mensagem_correcao_esquema(erros: list[dict[str, str]]) -> str:
    """Mensagem da única tentativa de correção (RF14). Os erros trazem campo e motivo, nunca valores."""
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
