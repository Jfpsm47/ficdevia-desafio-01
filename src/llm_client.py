"""Cliente oficial e adaptadores configuráveis de geração LLM (RF01, RF04, RF12, RF16, RF21).

Responsabilidade: Estudante 2.
Realiza chamadas programáticas configuráveis e isola o serviço de geração da recuperação vetorial:
- Carregamento seguro de credenciais via variáveis de ambiente / .env;
- Sanitização automática de segredos em mensagens de erro e logs;
- Timeout configurável, no máximo 1 repetição por falha transitória no fluxo D2 (RF16) e backoff;
- Controle de orçamento (teto de chamadas e de tokens por execução — RF16);
- Tratamento explícito para chave ausente, autenticação inválida (401/403), limite de
  requisições (429), indisponibilidade do provedor (5xx/rede), timeout e resposta vazia;
- Registro de tempo de resposta (latência), uso de tokens, custo estimado em USD e indicação
  explícita de indisponibilidade de métrica em execução local (RF21);
- Adaptador de geração configurável (`AdaptadorOpenAICompativel` e `AdaptadorSimulado`),
  permitindo trocar o serviço de geração sem reconstruir o índice vetorial (RF21).
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Padrões de chaves de API conhecidas e cabeçalhos Bearer para sanitização preventiva (RF04, RF11, RF16).
_RE_PADROES_SEGREDO = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I),
    re.compile(r"\bgsk_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9._\-]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{12,}\b"),
]

AVISO_ADAPTADOR_SIMULADO = (
    "Adaptador simulado local identificado como tal (RF21): utilizado apenas para verificação "
    "de portabilidade/contingência offline; NÃO possui equivalência de qualidade com provedor real."
)


def ocultar_segredos(texto: str) -> str:
    """Remove ou mascara chaves de API e tokens de qualquer texto antes de exibir ou registrar."""
    if not texto:
        return ""
    resultado = str(texto)
    for nome_var, valor in os.environ.items():
        if any(suf in nome_var.upper() for suf in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
            val_limpo = (valor or "").strip()
            if len(val_limpo) >= 6 and val_limpo in resultado:
                resultado = resultado.replace(val_limpo, "[CREDENCIAL_OCULTADA]")
    resultado = _RE_PADROES_SEGREDO[0].sub(r"\1[CREDENCIAL_OCULTADA]", resultado)
    for padrao in _RE_PADROES_SEGREDO[1:]:
        resultado = padrao.sub("[CREDENCIAL_OCULTADA]", resultado)
    return resultado


class ErroProvedor(Exception):
    """Falha tratada na comunicação com o provedor de IA, com mensagem segura e compreensível."""

    def __init__(self, mensagem: str, codigo_erro: str = "erro_provedor", status_code: int | None = None):
        mensagem_segura = ocultar_segredos(mensagem)
        super().__init__(mensagem_segura)
        self.codigo_erro = codigo_erro
        self.status_code = status_code


@dataclass
class ControladorOrcamento:
    """Impõe teto de chamadas e de tokens por execução para controle de recursos (RF16)."""

    max_chamadas: int | None = 12
    max_tokens_total: int | None = 45_000
    chamadas_realizadas: int = 0
    tokens_acumulados: int = 0

    def verificar_disponibilidade(self) -> None:
        if self.max_chamadas is not None and self.chamadas_realizadas >= self.max_chamadas:
            raise ErroProvedor(
                f"Limite de chamadas por execução atingido ({self.chamadas_realizadas}/{self.max_chamadas}).",
                codigo_erro="limite_chamadas_excedido",
            )
        if self.max_tokens_total is not None and self.tokens_acumulados >= self.max_tokens_total:
            raise ErroProvedor(
                f"Limite de tokens por execução atingido ({self.tokens_acumulados}/{self.max_tokens_total}).",
                codigo_erro="limite_tokens_excedido",
            )

    def registrar_chamada(self, tokens_total: int | None = None) -> None:
        self.chamadas_realizadas += 1
        if isinstance(tokens_total, int) and tokens_total > 0:
            self.tokens_acumulados += tokens_total

    def resumo(self) -> dict[str, int | None]:
        return {
            "chamadas_realizadas": self.chamadas_realizadas,
            "max_chamadas": self.max_chamadas,
            "tokens_acumulados": self.tokens_acumulados,
            "max_tokens_total": self.max_tokens_total,
        }


def verificar_chave(perfil: dict[str, Any]) -> str:
    """Obtém e valida a chave de API do provedor a partir do ambiente (RF01, RF04).

    Provedores locais ou simulados (onde `env_chave` é None) não exigem chave.
    """
    if perfil.get("simulado"):
        return "simulado"
    variavel = perfil.get("env_chave")
    if not variavel:
        return "local"
    chave = os.getenv(variavel, "").strip()
    if not chave:
        raise ErroProvedor(
            f"Chave ausente: defina a variável {variavel} no arquivo .env (consulte o .env.example).",
            codigo_erro="chave_ausente",
        )
    return chave


def custo_estimado(
    precos: dict[str, Any],
    modelo: str,
    tokens_entrada: int | None,
    tokens_saida: int | None,
) -> float | None:
    """Calcula o custo estimado em USD com base na tabela `precos_usd_por_milhao_tokens` do config.json."""
    if not precos or tokens_entrada is None or tokens_saida is None:
        return None
    tabela_modelo = precos.get(modelo)
    if not isinstance(tabela_modelo, dict):
        return None
    preco_in = tabela_modelo.get("entrada")
    preco_out = tabela_modelo.get("saida")
    if preco_in is None or preco_out is None:
        return None
    return round((tokens_entrada * preco_in + tokens_saida * preco_out) / 1_000_000, 6)


def status_metrica_custo(
    perfil: dict[str, Any],
    tokens_total: int | None,
    custo_usd: float | None,
) -> str:
    """Classifica a disponibilidade das métricas de uso e custo (RF21)."""
    if perfil.get("simulado"):
        return "indisponivel_execucao_local_simulada"
    if not perfil.get("env_chave"):
        if tokens_total is None:
            return "indisponivel_execucao_local"
        return "execucao_local_sem_tarifa_api"
    if tokens_total is None:
        return "tokens_nao_informados_pelo_provedor"
    if custo_usd is None:
        return "tarifa_nao_cadastrada_para_modelo"
    return "disponivel"


def listar_modelos(perfil: dict[str, Any], timeout_s: float = 30) -> list[str]:
    """Consulta o endpoint /models do provedor configurado com tratamento de falhas."""
    if perfil.get("simulado"):
        return sorted(str(m) for m in perfil.get("modelos", ["simulado-deterministico-v1"]) if m)

    chave = verificar_chave(perfil)
    url = perfil["base_url"].rstrip("/") + "/models"
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {chave}"}, timeout=timeout_s)
    except httpx.TimeoutException:
        raise ErroProvedor(
            f"Tempo limite de {timeout_s}s excedido ao listar modelos do provedor.",
            codigo_erro="timeout",
        ) from None
    except httpx.HTTPError as e:
        raise ErroProvedor(
            f"Serviço indisponível ou falha de conexão ({type(e).__name__}).",
            codigo_erro="servico_indisponivel",
        ) from None

    if r.status_code in (401, 403):
        raise ErroProvedor(
            "Autenticação recusada pelo provedor (HTTP 401/403): verifique a chave no arquivo .env.",
            codigo_erro="autenticacao_invalida",
            status_code=r.status_code,
        )
    if r.status_code == 429:
        raise ErroProvedor(
            "Limite de requisições atingido ao listar modelos (HTTP 429). Tente novamente em instantes.",
            codigo_erro="limite_requisicoes",
            status_code=429,
        )
    if r.status_code >= 500:
        raise ErroProvedor(
            f"Provedor temporariamente indisponível (HTTP {r.status_code}).",
            codigo_erro="servico_indisponivel",
            status_code=r.status_code,
        )
    if r.status_code >= 400:
        raise ErroProvedor(
            f"Requisição recusada pelo provedor (HTTP {r.status_code}): {ocultar_segredos(r.text[:300])}",
            codigo_erro="requisicao_invalida",
            status_code=r.status_code,
        )
    dados = r.json()
    return sorted(m.get("id", "") for m in dados.get("data", []) if m.get("id"))


def _resposta_simulada_deterministica(
    modelo: str,
    mensagens: list[dict[str, str]],
    parametros: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Gera saída estruturada determinística claramente marcada como simulada (RF21)."""
    inicio = time.perf_counter()
    texto_usuario = "\n".join(m.get("content", "") for m in mensagens if m.get("role") == "user")
    esquema_nome = (((parametros or {}).get("response_format") or {}).get("json_schema") or {}).get("name", "")

    # 1. Saída RAG (consulta ou minuta fundamentada)
    if esquema_nome == "saida_geracao_rag" or "<acervo_recuperado" in texto_usuario:
        ids_chunks = re.findall(r'chunk_id="(ACV-\d{2}#c\d+)"', texto_usuario)
        docs_distintos = sorted({cid.split("#")[0] for cid in ids_chunks})
        # Detecta conflito explícito de trancamento (30 dias vs 60 dias) se ambos recuperados
        tem_30 = bool(re.search(r"30\s*\(trinta\)\s*dias\s*corridos", texto_usuario, re.I))
        tem_60 = bool(re.search(r"60\s*\(sessenta\)\s*dias\s*corridos", texto_usuario, re.I))
        if tem_30 and tem_60 and len(docs_distintos) >= 2:
            c_30 = next((c for c in ids_chunks if c.startswith("ACV-04")), ids_chunks[0])
            c_60 = next((c for c in ids_chunks if c.startswith("ACV-05")), ids_chunks[-1])
            corpo = {
                "status": "conflito_fontes",
                "resposta": (
                    "[SIMULAÇÃO LOCAL IDENTIFICADA] Há divergência entre os documentos recuperados quanto ao prazo "
                    "(ACV-04 indica 30 dias corridos e ACV-05 indica 60 dias corridos). Encaminhado à revisão humana."
                ),
                "afirmacoes": [
                    {"texto": "ACV-04 indica prazo de até 30 dias corridos.", "chunk_ids": [c_30]},
                    {"texto": "ACV-05 indica prazo de até 60 dias corridos.", "chunk_ids": [c_60]},
                ],
                "requer_revisao": True,
                "motivo_revisao": "Conflito entre fontes vigentes (gerado por adaptador simulado local).",
            }
        elif not ids_chunks:
            corpo = {
                "status": "sem_evidencia",
                "resposta": (
                    "[SIMULAÇÃO LOCAL IDENTIFICADA] Não foram localizadas evidências suficientes no acervo para "
                    "responder à solicitação. Caso encaminhado para revisão humana."
                ),
                "afirmacoes": [],
                "requer_revisao": True,
                "motivo_revisao": "Ausência de trechos recuperados (adaptador simulado local).",
            }
        else:
            cid_principal = ids_chunks[0]
            corpo = {
                "status": "fundamentada",
                "resposta": (
                    f"[SIMULAÇÃO LOCAL IDENTIFICADA] Orientação preliminar baseada no trecho recuperado ({cid_principal}). "
                    "Saída de contingência sem equivalência de qualidade com o modelo principal; exige revisão humana."
                ),
                "afirmacoes": [
                    {
                        "texto": f"Registro recuperado no acervo institucional ({cid_principal}).",
                        "chunk_ids": [cid_principal],
                    }
                ],
                "requer_revisao": True,
                "motivo_revisao": "Saída produzida por adaptador simulado local (RF21); revisão obrigatória.",
            }
    else:
        corpo = {
            "aviso_simulacao": AVISO_ADAPTADOR_SIMULADO,
            "status": "simulado",
        }

    latencia = round(time.perf_counter() - inicio, 4)
    return {
        "texto": json.dumps(corpo, ensure_ascii=False),
        "latencia_s": latencia,
        "tokens_entrada": None,
        "tokens_saida": None,
        "tokens_total": None,
        "custo_usd": None,
        "tentativas": 1,
        "modelo_resposta": modelo,
        "simulado": True,
        "aviso_simulacao": AVISO_ADAPTADOR_SIMULADO,
        "metrica_custo_status": "indisponivel_execucao_local_simulada",
    }


def chamar_chat(
    perfil: dict[str, Any],
    modelo: str,
    mensagens: list[dict[str, str]],
    parametros: dict[str, Any],
    timeout_s: float = 60,
    tentativas: int = 3,
    json_mode: bool = False,
    precos: dict[str, Any] | None = None,
    dry_run: bool = False,
    pausa_base_s: float = 2.0,
) -> dict[str, Any]:
    """Envia mensagens ao endpoint /chat/completions com proteção de credenciais e tratamento de falhas (RF04)."""
    if dry_run:
        return {
            "texto": "",
            "latencia_s": 0.0,
            "tokens_entrada": None,
            "tokens_saida": None,
            "tokens_total": None,
            "custo_usd": None,
            "tentativas": 0,
            "modelo_resposta": modelo,
            "simulado": False,
            "metrica_custo_status": "dry_run_sem_chamada",
            "erro": "dry-run (nenhuma chamada realizada)",
        }

    if perfil.get("simulado"):
        return _resposta_simulada_deterministica(modelo, mensagens, parametros)

    chave = verificar_chave(perfil)
    corpo: dict[str, Any] = {"model": modelo, "messages": mensagens, **(parametros or {})}
    if json_mode and "response_format" not in corpo:
        corpo["response_format"] = {"type": "json_object"}
    cabecalhos = {"Authorization": f"Bearer {chave}"}
    url = perfil["base_url"].rstrip("/") + "/chat/completions"

    max_tentativas = max(1, int(tentativas))
    ultimo_erro = "erro desconhecido"
    ultimo_codigo = "erro_provedor"
    ultimo_status: int | None = None

    for tentativa in range(1, max_tentativas + 1):
        inicio = time.perf_counter()
        try:
            r = httpx.post(url, headers=cabecalhos, json=corpo, timeout=timeout_s)
        except httpx.TimeoutException:
            ultimo_erro = f"Tempo limite de {timeout_s}s excedido na comunicação com o modelo '{modelo}'."
            ultimo_codigo = "timeout"
            if tentativa < max_tentativas and pausa_base_s > 0:
                time.sleep(pausa_base_s * tentativa)
            continue
        except httpx.HTTPError as e:
            ultimo_erro = (
                f"Serviço indisponível ou sem conexão com o provedor ({type(e).__name__}). "
                "Verifique a conexão de rede ou a URL base configurada."
            )
            ultimo_codigo = "servico_indisponivel"
            if tentativa < max_tentativas and pausa_base_s > 0:
                time.sleep(pausa_base_s * tentativa)
                continue
            raise ErroProvedor(ultimo_erro, codigo_erro=ultimo_codigo) from None

        latencia = time.perf_counter() - inicio
        ultimo_status = r.status_code

        # 1. Autenticação inválida: falha imediata sem repetir chamadas
        if r.status_code in (401, 403):
            raise ErroProvedor(
                "Autenticação recusada pelo provedor: verifique se a chave de API no .env é válida.",
                codigo_erro="autenticacao_invalida",
                status_code=r.status_code,
            )

        # 2. Limite de requisições (429) ou indisponibilidade do servidor (5xx): aguarda e tenta novamente
        if r.status_code == 429 or r.status_code >= 500:
            if r.status_code == 429:
                ultimo_erro = "Limite de requisições atingido na API do provedor (HTTP 429)."
                ultimo_codigo = "limite_requisicoes"
            else:
                ultimo_erro = f"Provedor temporariamente indisponível (HTTP {r.status_code})."
                ultimo_codigo = "servico_indisponivel"
            if tentativa < max_tentativas:
                try:
                    retry_after = float(r.headers.get("retry-after", 0) or 0)
                except ValueError:
                    retry_after = 0.0
                espera = retry_after if retry_after > 0 else (2.5 * pausa_base_s * tentativa)
                if pausa_base_s > 0:
                    time.sleep(min(espera, 60.0))
            continue

        # 3. Demais erros de cliente (HTTP 4xx)
        if r.status_code >= 400:
            detalhe = ocultar_segredos(r.text[:300])
            raise ErroProvedor(
                f"Requisição rejeitada pelo provedor (HTTP {r.status_code}): {detalhe}",
                codigo_erro="requisicao_invalida",
                status_code=r.status_code,
            )

        # 4. Leitura e validação de conteúdo não vazio
        try:
            dados = r.json()
        except ValueError:
            ultimo_erro = "Resposta do provedor não está em formato JSON válido."
            ultimo_codigo = "resposta_vazia"
            continue

        escolhas = dados.get("choices") or []
        texto = ((escolhas[0].get("message") or {}).get("content") or "").strip() if escolhas else ""
        if not texto:
            ultimo_erro = "Resposta vazia retornada pelo modelo."
            ultimo_codigo = "resposta_vazia"
            if tentativa < max_tentativas and pausa_base_s > 0:
                time.sleep(pausa_base_s)
            continue

        uso = dados.get("usage") or {}
        tok_in = uso.get("prompt_tokens")
        tok_out = uso.get("completion_tokens")
        tok_total = uso.get("total_tokens")
        if tok_total is None and tok_in is not None and tok_out is not None:
            tok_total = tok_in + tok_out

        modelo_resp = dados.get("model", modelo)
        custo = custo_estimado(precos or {}, modelo, tok_in, tok_out)
        status_custo = status_metrica_custo(perfil, tok_total, custo)

        return {
            "texto": texto,
            "latencia_s": round(latencia, 2),
            "tokens_entrada": tok_in,
            "tokens_saida": tok_out,
            "tokens_total": tok_total,
            "custo_usd": custo,
            "tentativas": tentativa,
            "modelo_resposta": modelo_resp,
            "simulado": False,
            "metrica_custo_status": status_custo,
        }

    raise ErroProvedor(
        f"Falha após {max_tentativas} tentativa(s): {ultimo_erro}",
        codigo_erro=ultimo_codigo,
        status_code=ultimo_status,
    )


# ---------------------------------------------------------------- Abstração de Provedor (RF21, RF16)


class AdaptadorGeracao(ABC):
    """Interface isolada do serviço de geração textual, independente do índice vetorial (RF21)."""

    provedor: str
    modelo: str
    modo_saida: str
    parametros: dict[str, Any]
    timeout_s: float
    tentativas_transitorias: int
    eh_simulado: bool
    orcamento: ControladorOrcamento

    @abstractmethod
    def gerar(
        self,
        mensagens: list[dict[str, str]],
        *,
        parametros_extras: dict[str, Any] | None = None,
        json_mode: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Executa uma geração respeitando timeout, limite de repetição e orçamento de execução."""

    def configuracao_publica(self) -> dict[str, Any]:
        """Retorna os parâmetros auditáveis do adaptador sem expor credenciais."""
        return {
            "provedor": self.provedor,
            "modelo": self.modelo,
            "modo_saida": self.modo_saida,
            "parametros": dict(self.parametros),
            "timeout_s": self.timeout_s,
            "tentativas_transitorias": self.tentativas_transitorias,
            "simulado": self.eh_simulado,
            "orcamento": self.orcamento.resumo(),
        }


class AdaptadorOpenAICompativel(AdaptadorGeracao):
    """Adaptador para provedores compatíveis com a API OpenAI (`groq`, `gemini`, `openai`, `openrouter`, `ollama`)."""

    def __init__(
        self,
        *,
        provedor: str,
        perfil: dict[str, Any],
        modelo: str,
        parametros: dict[str, Any] | None = None,
        modo_saida: str = "json_schema_estrito",
        timeout_s: float = 60.0,
        tentativas_transitorias: int = 2,
        precos: dict[str, Any] | None = None,
        orcamento: ControladorOrcamento | None = None,
        pausa_base_s: float = 2.0,
    ) -> None:
        self.provedor = provedor
        self.perfil = dict(perfil)
        self.modelo = modelo
        self.parametros = dict(parametros or {"temperature": 0, "top_p": 1.0, "max_tokens": 4096})
        self.modo_saida = modo_saida
        self.timeout_s = float(timeout_s)
        # RF16: no máximo 1 repetição por falha transitória (total máximo = 2 chamadas HTTP por invocação)
        self.tentativas_transitorias = max(1, min(int(tentativas_transitorias), 2))
        self.precos = dict(precos or {})
        self.eh_simulado = False
        self.orcamento = orcamento or ControladorOrcamento()
        self.pausa_base_s = pausa_base_s

    def gerar(
        self,
        mensagens: list[dict[str, str]],
        *,
        parametros_extras: dict[str, Any] | None = None,
        json_mode: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if not dry_run:
            self.orcamento.verificar_disponibilidade()
        params = {**self.parametros, **(parametros_extras or {})}
        try:
            resposta = chamar_chat(
                perfil=self.perfil,
                modelo=self.modelo,
                mensagens=mensagens,
                parametros=params,
                timeout_s=self.timeout_s,
                tentativas=self.tentativas_transitorias,
                json_mode=json_mode,
                precos=self.precos,
                dry_run=dry_run,
                pausa_base_s=self.pausa_base_s,
            )
        except ErroProvedor:
            if not dry_run:
                self.orcamento.registrar_chamada(0)
            raise
        if not dry_run:
            self.orcamento.registrar_chamada(resposta.get("tokens_total"))
        return {**resposta, "provedor": self.provedor}


class AdaptadorSimulado(AdaptadorGeracao):
    """Adaptador simulado explicitamente identificado para contingência e testes de troca (RF21)."""

    def __init__(
        self,
        *,
        modelo: str = "simulado-deterministico-v1",
        parametros: dict[str, Any] | None = None,
        orcamento: ControladorOrcamento | None = None,
        gerador_customizado: Any | None = None,
    ) -> None:
        self.provedor = "simulado"
        self.modelo = modelo
        self.parametros = dict(parametros or {"temperature": 0})
        self.modo_saida = "json_object"
        self.timeout_s = 5.0
        self.tentativas_transitorias = 1
        self.eh_simulado = True
        self.orcamento = orcamento or ControladorOrcamento()
        self._gerador_customizado = gerador_customizado

    def gerar(
        self,
        mensagens: list[dict[str, str]],
        *,
        parametros_extras: dict[str, Any] | None = None,
        json_mode: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if dry_run:
            return {
                "texto": "",
                "latencia_s": 0.0,
                "tokens_entrada": None,
                "tokens_saida": None,
                "tokens_total": None,
                "custo_usd": None,
                "tentativas": 0,
                "modelo_resposta": self.modelo,
                "provedor": self.provedor,
                "simulado": True,
                "aviso_simulacao": AVISO_ADAPTADOR_SIMULADO,
                "metrica_custo_status": "dry_run_sem_chamada",
                "erro": "dry-run (nenhuma chamada realizada)",
            }
        self.orcamento.verificar_disponibilidade()
        params = {**self.parametros, **(parametros_extras or {})}
        if callable(self._gerador_customizado):
            inicio = time.perf_counter()
            saida_custom = self._gerador_customizado(mensagens, params)
            lat = round(time.perf_counter() - inicio, 4)
            texto = saida_custom if isinstance(saida_custom, str) else json.dumps(saida_custom, ensure_ascii=False)
            resp = {
                "texto": texto,
                "latencia_s": lat,
                "tokens_entrada": None,
                "tokens_saida": None,
                "tokens_total": None,
                "custo_usd": None,
                "tentativas": 1,
                "modelo_resposta": self.modelo,
                "simulado": True,
                "aviso_simulacao": AVISO_ADAPTADOR_SIMULADO,
                "metrica_custo_status": "indisponivel_execucao_local_simulada",
            }
        else:
            resp = _resposta_simulada_deterministica(self.modelo, mensagens, params)
        self.orcamento.registrar_chamada(None)
        return {**resp, "provedor": self.provedor}


def criar_adaptador_geracao(
    config: dict[str, Any],
    *,
    provedor: str | None = None,
    modelo: str | None = None,
    modo_saida: str | None = None,
    secao: str = "geracao_rag",
    usar_secundaria: bool = False,
    usar_contingencia_simulada: bool = False,
    orcamento: ControladorOrcamento | None = None,
    pausa_base_s: float = 2.0,
) -> AdaptadorGeracao:
    """Fábrica centralizada que instancia o adaptador de geração a partir do `config.json` (RF21)."""
    bloco_base = dict(config.get(secao) or config.get("extracao_estruturada") or config.get("producao") or {})
    sub_bloco: dict[str, Any] = {}
    if usar_contingencia_simulada:
        sub_bloco = dict(bloco_base.get("configuracao_contingencia_local") or {"provedor": "simulado"})
    elif usar_secundaria:
        sub_bloco = dict(bloco_base.get("configuracao_secundaria") or {})

    prov_efetivo = provedor or sub_bloco.get("provedor") or bloco_base.get("provedor", "groq")
    provedores_cfg = config.get("provedores", {})
    if prov_efetivo not in provedores_cfg and prov_efetivo != "simulado":
        raise ErroProvedor(f"Provedor '{prov_efetivo}' não encontrado em config.json.", codigo_erro="provedor_invalido")

    perfil = dict(provedores_cfg.get(prov_efetivo) or {"simulado": True, "modelos": ["simulado-deterministico-v1"]})
    mod_padrao = (perfil.get("modelos") or ["simulado-deterministico-v1"])[0]
    mod_efetivo = modelo or sub_bloco.get("modelo") or (
        bloco_base.get("modelo") if prov_efetivo == bloco_base.get("provedor") else mod_padrao
    ) or mod_padrao

    cfg_orc = bloco_base.get("orcamento_execucao") or {}
    ctrl_orc = orcamento or ControladorOrcamento(
        max_chamadas=cfg_orc.get("max_chamadas", 12),
        max_tokens_total=cfg_orc.get("max_tokens_total", 45_000),
    )

    parametros = dict(sub_bloco.get("parametros") or bloco_base.get("parametros") or {"temperature": 0})
    if prov_efetivo == "simulado" or perfil.get("simulado"):
        return AdaptadorSimulado(modelo=mod_efetivo, parametros=parametros, orcamento=ctrl_orc)

    # Provedores locais como Ollama frequentemente não suportam json_schema estrito: ajusta para json_object se não forçado
    modo_efetivo = modo_saida or sub_bloco.get("modo_saida") or bloco_base.get("modo_saida", "json_schema_estrito")
    if prov_efetivo == "ollama" and modo_saida is None:
        modo_efetivo = "json_object"

    return AdaptadorOpenAICompativel(
        provedor=prov_efetivo,
        perfil=perfil,
        modelo=mod_efetivo,
        parametros=parametros,
        modo_saida=modo_efetivo,
        timeout_s=float(bloco_base.get("timeout_s", 60)),
        tentativas_transitorias=int(bloco_base.get("tentativas_transitorias", 2)),
        precos=config.get("precos_usd_por_milhao_tokens", {}),
        orcamento=ctrl_orc,
        pausa_base_s=pausa_base_s,
    )
