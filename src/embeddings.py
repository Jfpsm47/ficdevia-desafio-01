"""Geração de embeddings, índice vetorial persistente em FAISS e governança de exclusão (RF17, RF18, RF20, RF24).

Responsabilidade: Estudante 2.
Implementa:
- `AdaptadorEmbeddings` (modelo local multilíngue via FastEmbed, API compatível opcional e modo determinístico para testes offline);
- `IndiceVetorial` persistido em disco (`index.faiss`, `trechos.json`, `manifesto.json`);
- Reutilização automática após reinício da aplicação sem duplicar documentos ao reindexar (T06);
- Detecção explícita de mudança de modelo/dimensão/chunking exigindo reindexação (RF17, RF20);
- Busca `top-k` configurável retornando trechos, metadados rastreáveis e similaridade de cosseno explicada;
- Exclusão auditável de documentos, vetores e resultados derivados (RF24, T14).

Uso via CLI:
  python -m src.embeddings indexar [--forcar]
  python -m src.embeddings status
  python -m src.embeddings buscar --consulta "Quais documentos são exigidos para a matrícula?" --top-k 4
  python -m src.embeddings excluir --documento ACV-06 --motivo "Demonstração RF24"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from src import audit, ingestion, llm_client, prompts, schemas

RAIZ = prompts.RAIZ
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

SENTIDO_SIMILARIDADE_COSSENO = (
    "Similaridade de cosseno calculada por produto interno sobre vetores normalizados em norma L2 "
    "(intervalo [-1, 1]): quanto maior o valor (mais próximo de 1,0), maior a proximidade semântica "
    "entre a consulta e o trecho. Similaridade vetorial NÃO constitui garantia de verdade (Seção 16)."
)


class ErroIndiceDesatualizado(RuntimeError):
    """Indica que o índice persistido foi criado com outro modelo/dimensão de embedding e exige reindexação."""


def _normalizar_l2(matriz: np.ndarray) -> np.ndarray:
    """Garante dtype float32 contíguo e norma L2 unitária por linha (seguro para vetores nulos)."""
    arr = np.asarray(matriz, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    arr = np.ascontiguousarray(arr, dtype=np.float32)
    normas = np.linalg.norm(arr, axis=1, keepdims=True)
    normas = np.where(normas > 1e-12, normas, 1.0)
    return np.ascontiguousarray(arr / normas, dtype=np.float32)


# ---------------------------------------------------------------- Adaptadores de Embeddings


class AdaptadorEmbeddings(ABC):
    """Interface isolada para geração de vetores densos (RF17)."""

    provedor: str
    modelo: str
    dimensao: int

    @abstractmethod
    def embed_textos(self, textos: list[str]) -> np.ndarray:
        """Converte uma lista de textos em matriz `(N, dimensao)` float32 normalizada em L2."""

    def embed_consulta(self, consulta: str) -> np.ndarray:
        """Converte uma consulta única em matriz `(1, dimensao)` float32 normalizada em L2."""
        return self.embed_textos([consulta])


# Cache em memória para não recarregar o modelo ONNX repetidamente na mesma execução/sessão Streamlit.
_CACHE_MODELOS_FASTEMBED: dict[tuple[str, str], Any] = {}


class EmbeddingsFastEmbedLocal(AdaptadorEmbeddings):
    """Gera embeddings localmente em CPU via ONNX Runtime (`fastembed`), sem custo de API."""

    def __init__(
        self,
        modelo: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: Path | str | None = None,
        dimensao_esperada: int | None = 384,
    ) -> None:
        from fastembed import TextEmbedding

        self.provedor = "fastembed_local"
        self.modelo = modelo
        pasta_cache = Path(cache_dir) if cache_dir else (RAIZ / ".cache" / "fastembed")
        pasta_cache.mkdir(parents=True, exist_ok=True)
        chave_cache = (modelo, str(pasta_cache.resolve()))
        if chave_cache not in _CACHE_MODELOS_FASTEMBED:
            _CACHE_MODELOS_FASTEMBED[chave_cache] = TextEmbedding(
                model_name=modelo,
                cache_dir=str(pasta_cache),
            )
        self._extrator = _CACHE_MODELOS_FASTEMBED[chave_cache]
        amostra = list(self._extrator.embed(["verificação de dimensão"]))
        self.dimensao = int(amostra[0].shape[0])
        if dimensao_esperada is not None and self.dimensao != int(dimensao_esperada):
            raise ValueError(
                f"Dimensão real do modelo '{modelo}' ({self.dimensao}) difere da configurada ({dimensao_esperada})."
            )

    def embed_textos(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimensao), dtype=np.float32)
        vetores = list(self._extrator.embed(textos))
        return _normalizar_l2(np.vstack(vetores))


class EmbeddingsOpenAICompativel(AdaptadorEmbeddings):
    """Adaptador opcional para endpoints HTTP `/embeddings` compatíveis com OpenAI."""

    def __init__(
        self,
        provedor: str,
        perfil: dict[str, Any],
        modelo: str,
        dimensao: int,
        timeout_s: float = 60.0,
    ) -> None:
        import httpx

        self._httpx = httpx
        self.provedor = provedor
        self.perfil = dict(perfil)
        self.modelo = modelo
        self.dimensao = int(dimensao)
        self.timeout_s = timeout_s

    def embed_textos(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimensao), dtype=np.float32)
        chave = llm_client.verificar_chave(self.perfil)
        url = self.perfil["base_url"].rstrip("/") + "/embeddings"
        try:
            r = self._httpx.post(
                url,
                headers={"Authorization": f"Bearer {chave}"},
                json={"model": self.modelo, "input": textos},
                timeout=self.timeout_s,
            )
        except self._httpx.HTTPError as exc:
            raise llm_client.ErroProvedor(
                f"Falha ao obter embeddings ({type(exc).__name__}).",
                codigo_erro="servico_indisponivel",
            ) from None
        if r.status_code >= 400:
            raise llm_client.ErroProvedor(
                f"Erro HTTP {r.status_code} em /embeddings: {llm_client.ocultar_segredos(r.text[:250])}",
                codigo_erro="erro_embeddings",
                status_code=r.status_code,
            )
        dados = sorted(r.json().get("data", []), key=lambda item: item.get("index", 0))
        matriz = np.array([item["embedding"] for item in dados], dtype=np.float32)
        return _normalizar_l2(matriz)


class EmbeddingsDeterministicoTeste(AdaptadorEmbeddings):
    """Embedder leve por hashing de tokens e trigramas exclusivamente para testes unitários offline."""

    def __init__(self, modelo: str = "hash-deterministico-teste-v1", dimensao: int = 128) -> None:
        self.provedor = "teste_offline"
        self.modelo = modelo
        self.dimensao = int(dimensao)

    def embed_textos(self, textos: list[str]) -> np.ndarray:
        if not textos:
            return np.zeros((0, self.dimensao), dtype=np.float32)
        matriz = np.zeros((len(textos), self.dimensao), dtype=np.float32)
        for i, txt in enumerate(textos):
            limpo = re.sub(r"[^\w\s]", " ", txt.lower())
            tokens = [t for t in limpo.split() if len(t) >= 2]
            features = list(tokens)
            compacto = " ".join(tokens)
            features.extend(compacto[j : j + 4] for j in range(max(0, len(compacto) - 3)))
            if not features:
                matriz[i, 0] = 1.0
                continue
            for feat in features:
                digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
                h = int.from_bytes(digest, "little")
                pos = h % self.dimensao
                sinal = 1.0 if ((h >> 32) & 1) == 0 else -1.0
                peso = 2.0 if feat in tokens else 0.5
                matriz[i, pos] += sinal * peso
        return _normalizar_l2(matriz)


def criar_adaptador_embeddings(config: dict[str, Any] | None = None) -> AdaptadorEmbeddings:
    """Cria o gerador de embeddings configurado em `config.json -> indexacao`."""
    cfg_global = config or CONFIG
    cfg_idx = cfg_global.get("indexacao", {})
    prov = cfg_idx.get("provedor_embedding", "fastembed_local")
    modelo = cfg_idx.get("modelo_embedding", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    dim = cfg_idx.get("dimensao", 384)

    if prov == "fastembed_local":
        cache_rel = cfg_idx.get("cache_modelos", ".cache/fastembed")
        caminho_cache = Path(cache_rel) if Path(cache_rel).is_absolute() else (RAIZ / cache_rel)
        return EmbeddingsFastEmbedLocal(modelo=modelo, cache_dir=caminho_cache, dimensao_esperada=dim)
    if prov == "teste_offline":
        return EmbeddingsDeterministicoTeste(modelo=modelo, dimensao=dim)
    provedores = cfg_global.get("provedores", {})
    if prov in provedores:
        return EmbeddingsOpenAICompativel(
            provedor=prov,
            perfil=provedores[prov],
            modelo=modelo,
            dimensao=dim,
        )
    raise ValueError(f"Provedor de embeddings desconhecido: '{prov}'")


# ---------------------------------------------------------------- Estruturas de Busca e Índice


@dataclass
class ResultadoBusca:
    """Item retornado por uma consulta vetorial no índice (RF17, RF19, RF20)."""

    posicao: int
    similaridade: float
    trecho: schemas.TrechoIndexado
    titulo_documento: str | None = None
    tema_documento: str | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    metrica: str = "similaridade_cosseno"
    sentido_metrica: str = SENTIDO_SIMILARIDADE_COSSENO

    def para_dict(self) -> dict[str, Any]:
        return {
            "posicao": self.posicao,
            "similaridade": round(self.similaridade, 4),
            "metrica": self.metrica,
            "sentido_metrica": self.sentido_metrica,
            "titulo_documento": self.titulo_documento,
            "tema_documento": self.tema_documento,
            "vigencia_inicio": self.vigencia_inicio,
            "vigencia_fim": self.vigencia_fim,
            **self.trecho.model_dump(),
        }


class IndiceVetorial:
    """Índice vetorial persistente baseado em FAISS (`IndexFlatIP`) com metadados validados (RF17, RF24)."""

    ARQ_FAISS = "index.faiss"
    ARQ_TRECHOS = "trechos.json"
    ARQ_MANIFESTO = "manifesto.json"

    def __init__(
        self,
        diretorio: Path,
        embedder: AdaptadorEmbeddings,
        *,
        unidade_chunk: str = "caracteres",
        tamanho_chunk: int = 700,
        sobreposicao_chunk: int = 120,
    ) -> None:
        self.diretorio = Path(diretorio)
        self.embedder = embedder
        self.unidade_chunk = unidade_chunk
        self.tamanho_chunk = int(tamanho_chunk)
        self.sobreposicao_chunk = int(sobreposicao_chunk)
        self.configuracao_chunking = ingestion.formatar_config_chunking(
            self.unidade_chunk, self.tamanho_chunk, self.sobreposicao_chunk
        )

        self._index: faiss.IndexFlatIP = faiss.IndexFlatIP(self.embedder.dimensao)
        self.trechos: list[schemas.TrechoIndexado] = []
        self.documentos_meta: dict[str, dict[str, Any]] = {}
        self.historico_exclusoes: list[dict[str, Any]] = []
        self.versao_indice: str = "v0-vazio"
        self.criado_em: str = audit.agora_iso()
        self.atualizado_em: str = self.criado_em
        self.carregado_do_disco: bool = False
        self.desatualizado: bool = False
        self.motivo_desatualizacao: str | None = None

        if self._arquivos_existem():
            self._carregar_do_disco()

    @property
    def caminho_faiss(self) -> Path:
        return self.diretorio / self.ARQ_FAISS

    @property
    def caminho_trechos(self) -> Path:
        return self.diretorio / self.ARQ_TRECHOS

    @property
    def caminho_manifesto(self) -> Path:
        return self.diretorio / self.ARQ_MANIFESTO

    @property
    def total_vetores(self) -> int:
        return int(self._index.ntotal)

    def _arquivos_existem(self) -> bool:
        return (
            self.caminho_faiss.is_file()
            and self.caminho_trechos.is_file()
            and self.caminho_manifesto.is_file()
        )

    def _calcular_versao_indice(self) -> str:
        """Gera identificador determinístico da versão do índice a partir do modelo, chunking e trechos ativos."""
        if not self.trechos:
            return "v0-vazio"
        assinatura = "|".join(
            [
                self.embedder.modelo,
                str(self.embedder.dimensao),
                self.configuracao_chunking,
                *(f"{t.chunk_id}:{t.hash_documento[:12]}" for t in self.trechos),
            ]
        )
        return "idx-" + hashlib.sha256(assinatura.encode("utf-8")).hexdigest()[:10]

    def _carregar_do_disco(self) -> None:
        manifesto = json.loads(self.caminho_manifesto.read_text(encoding="utf-8"))
        brutos_trechos = json.loads(self.caminho_trechos.read_text(encoding="utf-8"))
        trechos_lidos = [schemas.TrechoIndexado.model_validate(item) for item in brutos_trechos]
        indice_lido = faiss.read_index(str(self.caminho_faiss))

        if int(indice_lido.ntotal) != len(trechos_lidos):
            raise RuntimeError(
                f"Índice corrompido em {self.diretorio}: FAISS tem {indice_lido.ntotal} vetores, "
                f"mas trechos.json tem {len(trechos_lidos)} registros."
            )

        self._index = indice_lido
        self.trechos = trechos_lidos
        self.documentos_meta = dict(manifesto.get("documentos", {}))
        self.historico_exclusoes = list(manifesto.get("historico_exclusoes", []))
        self.versao_indice = str(manifesto.get("versao_indice") or self._calcular_versao_indice())
        self.criado_em = str(manifesto.get("criado_em") or self.criado_em)
        self.atualizado_em = str(manifesto.get("atualizado_em") or self.atualizado_em)
        self.carregado_do_disco = True

        # Verifica compatibilidade de modelo, dimensão e configuração de chunking (RF17, RF20)
        mod_salvo = manifesto.get("modelo_embedding")
        dim_salva = int(manifesto.get("dimensao", indice_lido.d))
        chk_salvo = manifesto.get("configuracao_chunking")
        divergencias: list[str] = []
        if mod_salvo != self.embedder.modelo:
            divergencias.append(f"modelo alterado ('{mod_salvo}' -> '{self.embedder.modelo}')")
        if dim_salva != self.embedder.dimensao or int(indice_lido.d) != self.embedder.dimensao:
            divergencias.append(f"dimensão alterada ({dim_salva} -> {self.embedder.dimensao})")
        if chk_salvo and chk_salvo != self.configuracao_chunking:
            divergencias.append(f"chunking alterado ('{chk_salvo}' -> '{self.configuracao_chunking}')")

        if divergencias:
            self.desatualizado = True
            self.motivo_desatualizacao = (
                "Índice desatualizado (" + "; ".join(divergencias) + "). Reindexação completa obrigatória."
            )

    def _extrair_matriz_atual(self) -> np.ndarray:
        """Reconstrói a matriz de vetores diretamente do índice FAISS em memória."""
        n = int(self._index.ntotal)
        d = int(self._index.d)
        if n == 0:
            return np.zeros((0, d), dtype=np.float32)
        vetores = np.zeros((n, d), dtype=np.float32)
        for i in range(n):
            vetores[i] = self._index.reconstruct(i)
        return vetores

    def _salvar_no_disco(self) -> None:
        self.diretorio.mkdir(parents=True, exist_ok=True)
        self.atualizado_em = audit.agora_iso()
        self.versao_indice = self._calcular_versao_indice()

        faiss.write_index(self._index, str(self.caminho_faiss))
        self.caminho_trechos.write_text(
            json.dumps([t.model_dump() for t in self.trechos], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifesto = {
            "versao_indice": self.versao_indice,
            "criado_em": self.criado_em,
            "atualizado_em": self.atualizado_em,
            "provedor_embedding": self.embedder.provedor,
            "modelo_embedding": self.embedder.modelo,
            "dimensao": self.embedder.dimensao,
            "metrica": "similaridade_cosseno",
            "sentido_metrica": SENTIDO_SIMILARIDADE_COSSENO,
            "configuracao_chunking": self.configuracao_chunking,
            "total_documentos": len(self.documentos_meta),
            "total_vetores": self.total_vetores,
            "documentos": self.documentos_meta,
            "historico_exclusoes": self.historico_exclusoes,
        }
        self.caminho_manifesto.write_text(
            json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def _limpar_em_memoria(self) -> None:
        self._index = faiss.IndexFlatIP(self.embedder.dimensao)
        self.trechos = []
        self.documentos_meta = {}
        self.desatualizado = False
        self.motivo_desatualizacao = None

    def verificar_atualizacao_acervo(
        self,
        caminho_catalogo: Path | None = None,
        raiz: Path = RAIZ,
    ) -> dict[str, Any]:
        """Compara o índice atual com o catálogo em disco sem modificá-lo (apoio ao Streamlit RF20)."""
        if self.desatualizado:
            return {"atualizado": False, "motivo": self.motivo_desatualizacao}
        catalogo = ingestion.carregar_catalogo(caminho_catalogo)
        pendentes: list[str] = []
        alterados: list[str] = []
        for doc in catalogo:
            caminho_arq = (raiz / doc.arquivo).resolve()
            if not caminho_arq.is_file():
                continue
            hash_atual = ingestion.calcular_hash_arquivo(caminho_arq)
            reg = self.documentos_meta.get(doc.documento_id)
            if not reg:
                pendentes.append(doc.documento_id)
            elif reg.get("hash_documento") != hash_atual or reg.get("versao") != doc.versao:
                alterados.append(doc.documento_id)
        atualizado = not pendentes and not alterados and self.total_vetores > 0
        motivo = None
        if not atualizado:
            partes = []
            if self.total_vetores == 0:
                partes.append("índice vazio")
            if pendentes:
                partes.append(f"documentos não indexados: {', '.join(pendentes)}")
            if alterados:
                partes.append(f"documentos modificados: {', '.join(alterados)}")
            motivo = "; ".join(partes)
        return {
            "atualizado": atualizado,
            "motivo": motivo,
            "documentos_pendentes": pendentes,
            "documentos_alterados": alterados,
            "versao_indice": self.versao_indice,
            "total_vetores": self.total_vetores,
        }

    def indexar_documento(
        self,
        doc: schemas.DocumentoAcervo,
        trechos_doc: list[schemas.TrechoIndexado],
        *,
        forcar: bool = False,
        salvar: bool = True,
    ) -> dict[str, Any]:
        """Indexa ou atualiza um único documento impedindo duplicatas por hash SHA-256 (RF17, T06)."""
        if self.desatualizado and not forcar:
            raise ErroIndiceDesatualizado(
                self.motivo_desatualizacao or "Índice incompatível; use forcar=True ou reindexar_acervo."
            )
        if not trechos_doc:
            return {"documento_id": doc.documento_id, "acao": "ignorado_vazio", "chunks": 0}

        hash_novo = trechos_doc[0].hash_documento
        reg_existente = self.documentos_meta.get(doc.documento_id)
        mesmo_conteudo = (
            not forcar
            and not self.desatualizado
            and reg_existente is not None
            and reg_existente.get("hash_documento") == hash_novo
            and reg_existente.get("versao") == doc.versao
            and reg_existente.get("configuracao_chunking") == self.configuracao_chunking
            and sum(1 for t in self.trechos if t.documento_id == doc.documento_id) == len(trechos_doc)
        )
        if mesmo_conteudo:
            return {
                "documento_id": doc.documento_id,
                "acao": "reutilizado_sem_duplicar",
                "chunks": len(trechos_doc),
            }

        # Se o índice estava marcado como desatualizado (outro modelo/dimensão) e forcar=True, zera tudo antes
        if self.desatualizado and forcar:
            self._limpar_em_memoria()

        # Remove vetores anteriores deste mesmo documento (se existiam) para impedir duplicação
        indices_manter = [i for i, t in enumerate(self.trechos) if t.documento_id != doc.documento_id]
        matriz_atual = self._extrair_matriz_atual()
        vetores_mantidos = (
            matriz_atual[indices_manter]
            if indices_manter
            else np.zeros((0, self.embedder.dimensao), dtype=np.float32)
        )
        trechos_mantidos = [self.trechos[i] for i in indices_manter]

        novos_vetores = self.embedder.embed_textos([t.texto for t in trechos_doc])
        matriz_final = (
            np.vstack([vetores_mantidos, novos_vetores]) if len(vetores_mantidos) > 0 else novos_vetores
        )

        novo_index = faiss.IndexFlatIP(self.embedder.dimensao)
        novo_index.add(np.ascontiguousarray(matriz_final, dtype=np.float32))

        self._index = novo_index
        self.trechos = [*trechos_mantidos, *trechos_doc]
        self.documentos_meta[doc.documento_id] = {
            "documento_id": doc.documento_id,
            "titulo": doc.titulo,
            "versao": doc.versao,
            "tema": doc.tema,
            "formato": doc.formato,
            "vigencia_inicio": doc.vigencia_inicio,
            "vigencia_fim": doc.vigencia_fim,
            "arquivo": doc.arquivo,
            "hash_documento": hash_novo,
            "configuracao_chunking": self.configuracao_chunking,
            "qtd_trechos": len(trechos_doc),
        }
        if salvar:
            self._salvar_no_disco()
        return {
            "documento_id": doc.documento_id,
            "acao": "substituido" if reg_existente else "indexado",
            "chunks": len(trechos_doc),
        }

    def indexar_acervo(
        self,
        *,
        caminho_catalogo: Path | None = None,
        raiz: Path = RAIZ,
        apenas_ids: set[str] | None = None,
        forcar_reindexacao: bool = False,
        caminho_log: Path | None = None,
    ) -> dict[str, Any]:
        """Indexa todos os documentos do catálogo reutilizando os inalterados e impedindo duplicatas (RF17, T06)."""
        if self.desatualizado and not forcar_reindexacao:
            # Quando mudança de modelo/chunking é detectada, RF17 exige reindexação completa automática ou explícita
            forcar_reindexacao = True

        if forcar_reindexacao and apenas_ids is None:
            self._limpar_em_memoria()

        docs = ingestion.carregar_catalogo(caminho_catalogo)
        if apenas_ids is not None:
            docs = [d for d in docs if d.documento_id in apenas_ids]

        acoes: list[dict[str, Any]] = []
        for doc in docs:
            trechos_doc = ingestion.ingerir_documento(
                doc,
                raiz=raiz,
                tamanho=self.tamanho_chunk,
                sobreposicao=self.sobreposicao_chunk,
                unidade=self.unidade_chunk,
            )
            res = self.indexar_documento(doc, trechos_doc, forcar=forcar_reindexacao, salvar=False)
            acoes.append(res)

        self._salvar_no_disco()

        reutilizados = sum(1 for a in acoes if a["acao"] == "reutilizado_sem_duplicar")
        novos_ou_atualizados = len(acoes) - reutilizados

        if caminho_log is not None or novos_ou_atualizados > 0:
            reg = audit.criar_registro(
                id_execucao=audit.gerar_id_execucao("idx"),
                caso_id="acervo_institucional",
                etapa="indexacao_acervo",
                modalidade="acervo",
                arquivo_origem=str((caminho_catalogo or ingestion.ARQUIVO_CATALOGO_PADRAO).name),
                provedor=self.embedder.provedor,
                modelo=self.embedder.modelo,
                parametros={
                    "dimensao": self.embedder.dimensao,
                    "configuracao_chunking": self.configuracao_chunking,
                },
                versao_esquema=f"trecho_indexado-v{schemas.TrechoIndexado.VERSAO}",
                versao_indice=self.versao_indice,
                resumo_resultado=(
                    f"Índice {self.versao_indice}: {self.total_vetores} vetores em {len(self.documentos_meta)} "
                    f"documentos ({novos_ou_atualizados} indexados/atualizados, {reutilizados} reutilizados)."
                ),
                decisao_humana="Conferido",
                metrica_custo_status="indisponivel_execucao_local",
            )
            audit.registrar_execucao(reg, caminho_log=caminho_log)

        return {
            "versao_indice": self.versao_indice,
            "modelo_embedding": self.embedder.modelo,
            "dimensao": self.embedder.dimensao,
            "configuracao_chunking": self.configuracao_chunking,
            "total_documentos": len(self.documentos_meta),
            "total_vetores": self.total_vetores,
            "indexados_ou_atualizados": novos_ou_atualizados,
            "reutilizados_sem_duplicar": reutilizados,
            "detalhes": acoes,
        }

    def incluir_arquivo_avulso(
        self,
        caminho_arquivo: Path,
        *,
        documento_id: str,
        titulo: str | None = None,
        versao: str = "1.0",
        tema: str = "Documento incluído pelo operador",
        vigencia_inicio: str = "01/08/2026",
        raiz: Path = RAIZ,
        caminho_log: Path | None = None,
    ) -> dict[str, Any]:
        """Inclui e indexa um documento avulso (ex.: upload no Streamlit RF20)."""
        doc, paginas, hash_doc = ingestion.construir_documento_avulso(
            caminho_arquivo,
            documento_id=documento_id,
            titulo=titulo,
            versao=versao,
            tema=tema,
            vigencia_inicio=vigencia_inicio,
            raiz=raiz,
        )
        trechos_doc = ingestion.dividir_documento_em_chunks(
            doc=doc,
            paginas=paginas,
            hash_documento=hash_doc,
            tamanho=self.tamanho_chunk,
            sobreposicao=self.sobreposicao_chunk,
            unidade=self.unidade_chunk,
        )
        res = self.indexar_documento(doc, trechos_doc, salvar=True)
        if caminho_log is not None:
            audit.registrar_execucao(
                audit.criar_registro(
                    id_execucao=audit.gerar_id_execucao("inc"),
                    caso_id=doc.documento_id,
                    etapa="inclusao_documento_indice",
                    modalidade="acervo",
                    arquivo_origem=doc.arquivo,
                    provedor=self.embedder.provedor,
                    modelo=self.embedder.modelo,
                    versao_indice=self.versao_indice,
                    resumo_resultado=f"Documento {doc.documento_id} ({res['acao']}, {res['chunks']} chunks).",
                    decisao_humana="Conferido",
                    metrica_custo_status="indisponivel_execucao_local",
                ),
                caminho_log=caminho_log,
            )
        return {**res, "versao_indice": self.versao_indice, "documento": doc.model_dump()}

    def buscar(self, consulta: str, top_k: int = 4) -> list[ResultadoBusca]:
        """Recupera os `top_k` trechos mais similares à consulta com explicação da métrica (RF17)."""
        if self.desatualizado:
            raise ErroIndiceDesatualizado(
                self.motivo_desatualizacao or "Índice desatualizado; execute a reindexação antes da busca."
            )
        consulta_limpa = (consulta or "").strip()
        if not consulta_limpa:
            raise ValueError("A consulta de busca vetorial não pode ser vazia.")
        if top_k < 1:
            raise ValueError(f"top_k deve ser >= 1 ({top_k} informado).")
        if self.total_vetores == 0:
            return []

        k_efetivo = min(int(top_k), self.total_vetores)
        vetor_q = self.embedder.embed_consulta(consulta_limpa)
        scores, indices = self._index.search(vetor_q, k_efetivo)

        resultados: list[ResultadoBusca] = []
        for pos, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            if idx < 0 or idx >= len(self.trechos):
                continue
            trecho = self.trechos[int(idx)]
            meta_doc = self.documentos_meta.get(trecho.documento_id, {})
            resultados.append(
                ResultadoBusca(
                    posicao=pos,
                    similaridade=float(score),
                    trecho=trecho,
                    titulo_documento=meta_doc.get("titulo"),
                    tema_documento=meta_doc.get("tema"),
                    vigencia_inicio=meta_doc.get("vigencia_inicio"),
                    vigencia_fim=meta_doc.get("vigencia_fim"),
                )
            )
        return resultados

    def excluir_documento(
        self,
        documento_id: str,
        *,
        motivo: str = "Solicitação de governança/retenção (RF24)",
        operador: str = "Operador local",
        diretorios_derivados: list[Path] | None = None,
        caminho_log: Path | None = None,
    ) -> dict[str, Any]:
        """Remove todos os vetores e metadados de `documento_id` e limpa resultados derivados (RF24, T14)."""
        versao_antiga = self.versao_indice
        indices_manter = [i for i, t in enumerate(self.trechos) if t.documento_id != documento_id]
        removidos = len(self.trechos) - len(indices_manter)

        matriz_atual = self._extrair_matriz_atual()
        vetores_mantidos = (
            matriz_atual[indices_manter]
            if indices_manter
            else np.zeros((0, self.embedder.dimensao), dtype=np.float32)
        )
        novo_index = faiss.IndexFlatIP(self.embedder.dimensao)
        if len(vetores_mantidos) > 0:
            novo_index.add(np.ascontiguousarray(vetores_mantidos, dtype=np.float32))

        self._index = novo_index
        self.trechos = [self.trechos[i] for i in indices_manter]
        self.documentos_meta.pop(documento_id, None)

        # Limpa artefatos derivados (caches JSON específicos que dependiam do documento excluído)
        derivados_removidos: list[str] = []
        pastas_alvo = diretorios_derivados if diretorios_derivados is not None else [
            RAIZ / p for p in CONFIG.get("retencao_privacidade", {}).get("diretorios_derivados_exclusao", [])
        ]
        for pasta in pastas_alvo:
            pasta_path = Path(pasta)
            if not pasta_path.is_dir():
                continue
            for arq in pasta_path.rglob("*.derivado.json"):
                try:
                    conteudo = arq.read_text(encoding="utf-8")
                    if f'"{documento_id}"' in conteudo:
                        arq.unlink()
                        try:
                            derivados_removidos.append(arq.relative_to(RAIZ).as_posix())
                        except ValueError:
                            derivados_removidos.append(arq.name)
                except OSError:
                    continue

        evento_exclusao = {
            "documento_id": documento_id,
            "data_hora": audit.agora_iso(),
            "operador": operador,
            "motivo": motivo,
            "trechos_removidos": removidos,
            "derivados_removidos": derivados_removidos,
            "versao_indice_anterior": versao_antiga,
        }
        self.historico_exclusoes.append(evento_exclusao)
        self._salvar_no_disco()
        evento_exclusao["versao_indice_nova"] = self.versao_indice

        audit.registrar_exclusao_documento(
            documento_id=documento_id,
            motivo=motivo,
            operador=operador,
            trechos_removidos=removidos,
            derivados_removidos=derivados_removidos,
            versao_indice_anterior=versao_antiga,
            versao_indice_nova=self.versao_indice,
            caminho_log=caminho_log,
        )
        return {
            **evento_exclusao,
            "total_vetores_restantes": self.total_vetores,
            "total_documentos_restantes": len(self.documentos_meta),
        }

    def resumo_estado(self) -> dict[str, Any]:
        return {
            "diretorio": str(self.diretorio),
            "versao_indice": self.versao_indice,
            "carregado_do_disco": self.carregado_do_disco,
            "desatualizado": self.desatualizado,
            "motivo_desatualizacao": self.motivo_desatualizacao,
            "provedor_embedding": self.embedder.provedor,
            "modelo_embedding": self.embedder.modelo,
            "dimensao": self.embedder.dimensao,
            "configuracao_chunking": self.configuracao_chunking,
            "metrica": "similaridade_cosseno",
            "sentido_metrica": SENTIDO_SIMILARIDADE_COSSENO,
            "total_documentos": len(self.documentos_meta),
            "total_vetores": self.total_vetores,
            "documentos": list(self.documentos_meta.values()),
            "exclusoes_registradas": len(self.historico_exclusoes),
        }


def obter_indice(
    config: dict[str, Any] | None = None,
    *,
    embedder: AdaptadorEmbeddings | None = None,
    diretorio: Path | None = None,
    auto_indexar_se_vazio: bool = False,
) -> IndiceVetorial:
    """Carrega o índice persistente configurado (e opcionalmente indexa o acervo se ainda estiver vazio)."""
    cfg_global = config or CONFIG
    cfg_idx = cfg_global.get("indexacao", {})
    cfg_chk = cfg_idx.get("chunking", {})
    emb = embedder or criar_adaptador_embeddings(cfg_global)

    dir_alvo = diretorio
    if dir_alvo is None:
        rel = cfg_idx.get("diretorio_indice", "indice/padrao")
        dir_alvo = Path(rel) if Path(rel).is_absolute() else (RAIZ / rel)

    indice = IndiceVetorial(
        diretorio=dir_alvo,
        embedder=emb,
        unidade_chunk=cfg_chk.get("unidade", "caracteres"),
        tamanho_chunk=int(cfg_chk.get("tamanho", 700)),
        sobreposicao_chunk=int(cfg_chk.get("sobreposicao", 120)),
    )
    if auto_indexar_se_vazio and (indice.total_vetores == 0 or indice.desatualizado):
        indice.indexar_acervo(forcar_reindexacao=indice.desatualizado)
    return indice


# ---------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Índice vetorial persistente e busca semântica (RF17, RF24).")
    sub = parser.add_subparsers(dest="comando", required=True)

    p_idx = sub.add_parser("indexar", help="Indexa ou atualiza o acervo institucional sem duplicar")
    p_idx.add_argument(
        "--forcar",
        "--forcar-reindexacao",
        dest="forcar",
        action="store_true",
        help="Reconstrói todos os vetores do índice",
    )

    sub.add_parser("status", aliases=["info"], help="Exibe estado, modelo, dimensão e documentos do índice atual")

    p_bus = sub.add_parser("buscar", help="Executa busca top-k por similaridade no índice persistido")
    p_bus.add_argument("--consulta", required=True, help="Pergunta ou termos da busca")
    p_bus.add_argument("--top-k", type=int, default=CONFIG["indexacao"].get("top_k_padrao", 4))

    p_exc = sub.add_parser("excluir", help="Remove documento, vetores e derivados do índice (RF24)")
    p_exc.add_argument("--documento", required=True, help="ID do documento (ex.: ACV-06)")
    p_exc.add_argument("--motivo", default="Exclusão solicitada pelo operador (RF24)")
    p_exc.add_argument("--operador", default="João Flávio Pompeo")

    args = parser.parse_args(argv)
    indice = obter_indice(CONFIG)

    if args.comando == "indexar":
        res = indice.indexar_acervo(forcar_reindexacao=args.forcar)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if args.comando in ("status", "info"):
        est = indice.resumo_estado()
        sinc = indice.verificar_atualizacao_acervo()
        print(json.dumps({**est, "sincronia_catalogo": sinc}, ensure_ascii=False, indent=2))
        return 0

    if args.comando == "buscar":
        if indice.total_vetores == 0:
            indice.indexar_acervo()
        achados = indice.buscar(args.consulta, top_k=args.top_k)
        saida = {
            "consulta": args.consulta,
            "versao_indice": indice.versao_indice,
            "modelo_embedding": indice.embedder.modelo,
            "dimensao": indice.embedder.dimensao,
            "top_k": args.top_k,
            "sentido_metrica": SENTIDO_SIMILARIDADE_COSSENO,
            "resultados": [r.para_dict() for r in achados],
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2))
        return 0

    if args.comando == "excluir":
        res_exc = indice.excluir_documento(args.documento, motivo=args.motivo, operador=args.operador)
        print(json.dumps(res_exc, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
