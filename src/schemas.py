"""Contratos de dados versionados do Desafio 02 (RF14, RF15, RF17, RF19, RF20, RF22, RF24).

Responsabilidade: Estudante 1. Os módulos trocam dados por estes modelos Pydantic; assim, uma chave
extra, um tipo incorreto ou um campo obrigatório ausente gera erro explícito na fronteira entre
módulos, em vez de quebrar a integração no fim.

Situação: PROPOSTA 0.x. Os contratos de índice, RAG, sentimento e revisão descrevem o trabalho dos
Estudantes 2 e 3 e só passam a 1.0 depois de acordados (documentacao/CONTRATOS_DADOS.md).

Camadas de validação (RF14):
1. sintática — o texto é JSON? (`validar_texto_json`)
2. esquema   — chaves, tipos, obrigatoriedade e regras internas do contrato conferem? (`validar`)
3. negócio   — os valores fazem sentido e estão no original? (regras do RF14, implementadas à parte)

Uso:
  python -m src.schemas exportar     # regrava prompts/esquemas/*.schema.json
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator

from src import prompts

SITUACAO = "proposta"
DIR_ESQUEMAS = prompts.DIR_PROMPTS / "esquemas"
LIMITE_PALAVRAS_RESUMO = 100

# A lista de categorias continua documentada em prompts/categorias.json (fonte única).
CategoriaId = Literal[tuple(prompts.ids_categorias())]
DataBR = Annotated[str, StringConstraints(pattern=r"^\d{2}/\d{2}/\d{4}$")]
Texto = Annotated[str, StringConstraints(min_length=1)]


def contar_palavras(texto: str) -> int:
    """Unidade do limite do resumo: sequências sem espaço ("2026-000142" conta como uma palavra)."""
    return len(re.findall(r"\S+", texto))


class Contrato(BaseModel):
    """Base de todos os contratos: rejeita chaves extras e expõe a versão.

    `strict=True` impede coerções silenciosas: "true" ou 1 não viram booleano, "3" não vira inteiro.
    """
    model_config = ConfigDict(extra="forbid", strict=True)
    VERSAO: ClassVar[str] = "0.1.0"


# ---------------------------------------------------------------- Solicitação (RF14, RF15)

class Entidade(Contrato):
    """Entidade presente na solicitação. 'literal' = escrita no texto; 'inferida' = deduzida (RF15)."""
    tipo: Literal["pessoa", "orgao", "local", "data", "protocolo"]
    valor: Texto
    origem: Literal["literal", "inferida"]
    evidencia: Texto = Field(description="Trecho literal do original que sustenta a entidade.")


CampoAusente = Literal["protocolo", "data_solicitacao", "canal", "solicitante", "curso", "pedido"]


class SolicitacaoExtraida(Contrato):
    """Contrato de extração de uma solicitação (RF14). Saída do modelo.

    Ausência = null no campo + nome do campo em `campos_ausentes`; a interface exibe "não localizado".
    Todos os campos são obrigatórios (sem valor padrão), o que permite usar o modo estrito do provedor.
    """
    protocolo: str | None
    data_solicitacao: DataBR | None
    canal: str | None
    solicitante: str | None = Field(description="Nome fictício do solicitante.")
    curso: str | None
    assunto: str = Field(min_length=1, max_length=120)
    pedido: str | None
    categoria: CategoriaId
    entidades: list[Entidade]
    dados_pessoais_detectados: list[str] = Field(description="Somente os TIPOS (ex.: 'CPF'), nunca os valores.")
    campos_ausentes: list[CampoAusente]
    requer_revisao: bool
    motivos_revisao: list[str]
    alertas_seguranca: list[str]

    @model_validator(mode="after")
    def _ausencias_coerentes(self) -> SolicitacaoExtraida:
        nulos = {c for c in get_args(CampoAusente) if getattr(self, c) is None}
        declarados = set(self.campos_ausentes)
        if nulos != declarados:
            raise ValueError(
                "campos_ausentes deve listar exatamente os campos nulos; "
                f"nulos sem declaração: {sorted(nulos - declarados)}; "
                f"declarados mas preenchidos: {sorted(declarados - nulos)}")
        return self


class FatoResumo(Contrato):
    afirmacao: Texto
    evidencia: Texto = Field(description="Trecho literal do original que sustenta a afirmação.")


class ResumoSolicitacao(Contrato):
    """Saída do modelo na sumarização (RF15): resumo de até 100 palavras e fatos com evidência literal."""
    resumo: Texto
    fatos: list[FatoResumo]

    @field_validator("resumo")
    @classmethod
    def _limite_palavras(cls, valor: str) -> str:
        n = contar_palavras(valor)
        if n > LIMITE_PALAVRAS_RESUMO:
            raise ValueError(f"resumo com {n} palavras; limite: {LIMITE_PALAVRAS_RESUMO}")
        return valor


class FichaCompreensao(Contrato):
    """Ficha exibida ao operador (RF15, RF20). Montada pelo sistema a partir das duas saídas validadas."""
    id_caso: Texto
    extracao: SolicitacaoExtraida
    resumo: ResumoSolicitacao
    versao_prompt_extracao: Texto
    versao_prompt_resumo: Texto


# ---------------------------------------------------------------- Acervo e índice (RF17, RF18)

class DocumentoAcervo(Contrato):
    """Cabeçalho obrigatório de cada documento do acervo fictício (seção 6 e RF17)."""
    documento_id: str = Field(pattern=r"^ACV-\d{2}$")
    titulo: Texto
    versao: Texto
    tema: Texto
    formato: Literal["txt", "pdf"]
    vigencia_inicio: DataBR
    vigencia_fim: DataBR | None
    arquivo: Texto


class TrechoIndexado(Contrato):
    """Metadados de cada vetor no índice (RF17). Preenchido pelo sistema, nunca pelo modelo."""
    chunk_id: Texto
    documento_id: Texto
    versao_documento: Texto
    hash_documento: Texto = Field(description="SHA-256 do arquivo de origem; detecta reindexação duplicada.")
    pagina: Annotated[int, Field(ge=1)] | None
    secao: str | None
    configuracao_chunking: Texto = Field(description="Ex.: 'caracteres-800-sobreposicao-100'.")
    texto: Texto


# ---------------------------------------------------------------- RAG (RF19)

class Citacao(Contrato):
    """Fonte citada. Os metadados vêm do índice (TrechoIndexado), não do texto gerado pelo modelo."""
    chunk_id: Texto
    documento_id: Texto
    versao_documento: Texto
    pagina: Annotated[int, Field(ge=1)] | None
    secao: str | None
    trecho: Texto = Field(description="Passagem original que permite conferir a afirmação.")


class AfirmacaoInstitucional(Contrato):
    texto: Texto
    chunk_ids: list[Texto] = Field(min_length=1, description="Trechos que sustentam a afirmação.")


class RespostaRAG(Contrato):
    """Resposta ou minuta fundamentada no acervo (RF19).

    'sem_evidencia' não pode trazer afirmação institucional: é assim que o contrato impede que a falta
    de fonte vire resposta inventada. 'conflito_fontes' exige ao menos dois documentos citados.
    """
    status: Literal["fundamentada", "sem_evidencia", "conflito_fontes"]
    resposta: Texto
    afirmacoes: list[AfirmacaoInstitucional]
    citacoes: list[Citacao]
    requer_revisao: bool
    motivo_revisao: str | None

    @model_validator(mode="after")
    def _status_coerente(self) -> RespostaRAG:
        citados = {c.chunk_id for c in self.citacoes}
        sem_fonte = sorted({i for a in self.afirmacoes for i in a.chunk_ids} - citados)
        if sem_fonte:
            raise ValueError(f"afirmações apontam para trechos não citados: {sem_fonte}")
        if self.status == "fundamentada" and not (self.afirmacoes and self.citacoes):
            raise ValueError("status 'fundamentada' exige ao menos uma afirmação e uma citação")
        if self.status == "sem_evidencia" and self.afirmacoes:
            raise ValueError("status 'sem_evidencia' não pode conter afirmações institucionais")
        if self.status == "conflito_fontes" and len({c.documento_id for c in self.citacoes}) < 2:
            raise ValueError("status 'conflito_fontes' exige citações de ao menos dois documentos")
        if self.status != "fundamentada" and not (self.requer_revisao and self.motivo_revisao):
            raise ValueError(f"status '{self.status}' exige requer_revisao=true e motivo_revisao")
        return self


# ---------------------------------------------------------------- Sentimentos (RF22)

class AvaliacaoAtendimento(Contrato):
    """Avaliação fictícia de atendimento (entrada do RF22). A agregação é feita por código, não pelo modelo."""
    id_avaliacao: str = Field(pattern=r"^AV-\d{2}$")
    data: DataBR
    canal: Texto
    categoria_atendimento: CategoriaId
    texto: Texto


class ClassificacaoSentimento(Contrato):
    """Saída do modelo para uma avaliação (RF22). Não descreve o autor, só o texto avaliado."""
    id_avaliacao: Texto
    polaridade: Literal["positiva", "negativa", "neutra", "indeterminada"]
    justificativa: str = Field(min_length=1, max_length=300)
    requer_revisao: bool
    confianca_declarada: Literal["alta", "media", "baixa"] = Field(
        description="Estimativa NÃO calibrada do modelo; não é probabilidade de acerto.")

    @model_validator(mode="after")
    def _indeterminada_exige_revisao(self) -> ClassificacaoSentimento:
        if self.polaridade == "indeterminada" and not self.requer_revisao:
            raise ValueError("polaridade 'indeterminada' exige requer_revisao=true")
        return self


# ---------------------------------------------------------------- Revisão humana (RF20, RF24)

class DecisaoRevisao(Contrato):
    """Estado da minuta. Nenhuma resposta é enviada automaticamente: o campo só admite false."""
    id_minuta: Texto
    estado: Literal["pendente", "aprovada", "rejeitada", "revisar"]
    revisor: str | None = None
    justificativa: str | None = None
    data_hora: str | None = Field(default=None, description="ISO 8601 da decisão.")
    participacao_ia: Texto = "Minuta gerada com apoio de IA; revisão humana obrigatória."
    enviada_ao_cidadao: Literal[False] = False

    @model_validator(mode="after")
    def _decisao_identificada(self) -> DecisaoRevisao:
        if self.estado != "pendente":
            faltando = [c for c in ("revisor", "justificativa", "data_hora") if not (getattr(self, c) or "").strip()]
            if faltando:
                raise ValueError(f"estado '{self.estado}' exige {', '.join(faltando)}")
        return self


ESQUEMAS: dict[str, type[Contrato]] = {
    "solicitacao_extraida": SolicitacaoExtraida,
    "resumo_solicitacao": ResumoSolicitacao,
    "ficha_compreensao": FichaCompreensao,
    "documento_acervo": DocumentoAcervo,
    "trecho_indexado": TrechoIndexado,
    "resposta_rag": RespostaRAG,
    "avaliacao_atendimento": AvaliacaoAtendimento,
    "classificacao_sentimento": ClassificacaoSentimento,
    "decisao_revisao": DecisaoRevisao,
}


# ---------------------------------------------------------------- Validação com erros classificados

def _categoria_erro(tipo: str) -> str:
    """Traduz o tipo de erro do Pydantic nas categorias pedidas pelo RF14."""
    if tipo == "extra_forbidden":
        return "chave_extra"
    if tipo == "missing":
        return "campo_ausente"
    if tipo.endswith("_type") or tipo in ("model_attributes_type", "dict_type"):
        return "tipo_incorreto"
    if tipo == "value_error":
        return "regra_do_contrato"
    return "valor_invalido"


@dataclass
class ResultadoValidacao:
    valido: bool
    objeto: Contrato | None = None
    erros: list[dict[str, str]] = field(default_factory=list)


def validar(modelo: type[Contrato], dados: Any) -> ResultadoValidacao:
    """Camada 2: confere os dados contra o contrato.

    Os erros nunca incluem o valor recebido (pode conter dado pessoal), só o campo e o motivo.
    """
    try:
        return ResultadoValidacao(True, modelo.model_validate(dados))
    except ValidationError as exc:
        erros = []
        for e in exc.errors(include_input=False, include_url=False):
            erros.append({
                "campo": ".".join(map(str, e["loc"])) or "(raiz)",
                "categoria": _categoria_erro(e["type"]),
                "detalhe": e["msg"].removeprefix("Value error, "),
            })
        return ResultadoValidacao(False, erros=erros)


def validar_texto_json(modelo: type[Contrato], texto: str) -> ResultadoValidacao:
    """Camadas 1 e 2: primeiro o texto precisa ser JSON; depois, obedecer ao contrato."""
    try:
        dados = json.loads(texto)
    except (json.JSONDecodeError, TypeError) as exc:
        return ResultadoValidacao(False, erros=[{"campo": "(raiz)", "categoria": "json_invalido",
                                                  "detalhe": str(exc)}])
    return validar(modelo, dados)


# ---------------------------------------------------------------- Exportação do JSON Schema

def esquema_json(nome: str) -> dict[str, Any]:
    modelo = ESQUEMAS[nome]
    esquema = modelo.model_json_schema()
    return {"$id": f"{nome}-v{modelo.VERSAO}", "x-versao": modelo.VERSAO, "x-situacao": SITUACAO, **esquema}


def texto_esquema(nome: str) -> str:
    return json.dumps(esquema_json(nome), ensure_ascii=False, indent=2) + "\n"


def exportar(destino: Path = DIR_ESQUEMAS) -> list[Path]:
    """Regrava os JSON Schemas versionados. O nome do arquivo é estável; a versão fica no conteúdo."""
    destino.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for nome in ESQUEMAS:
        caminho = destino / f"{nome}.schema.json"
        caminho.write_text(texto_esquema(nome), encoding="utf-8", newline="\n")
        caminhos.append(caminho)
    return caminhos


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contratos de dados versionados (Desafio 02).")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("exportar", help="Regrava prompts/esquemas/*.schema.json a partir dos modelos")
    parser.parse_args(argv)
    for caminho in exportar():
        print(f"[OK] {caminho.relative_to(prompts.RAIZ).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
