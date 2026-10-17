"""Cliente oficial de integração com provedores de LLM via API compatível com OpenAI (RF01, RF04, RF12).

Responsabilidade: Estudante 2.
Realiza chamadas programáticas configuráveis com:
- Carregamento seguro de credenciais via variáveis de ambiente / .env;
- Sanitização automática de segredos em mensagens de erro e logs;
- Timeout configurável e retentativas com espera progressiva (backoff);
- Tratamento explícito para chave ausente, autenticação inválida (401/403), limite de
  requisições (429), indisponibilidade do provedor (5xx/rede), timeout e resposta vazia;
- Registro de tempo de resposta (latência), uso de tokens e custo estimado em USD.
"""
from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Padrões de chaves de API conhecidas e cabeçalhos Bearer para sanitização preventiva (RF04, RF11).
_RE_PADROES_SEGREDO = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I),
    re.compile(r"\bgsk_[A-Za-z0-9]{12,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9._\-]{12,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9_\-]{12,}\b"),
]


def ocultar_segredos(texto: str) -> str:
    """Remove ou mascara chaves de API e tokens de qualquer texto antes de exibir ou registrar."""
    if not texto:
        return ""
    resultado = str(texto)
    # Mascara valores reais de variáveis de ambiente sensíveis atualmente carregadas
    for nome_var, valor in os.environ.items():
        if any(suf in nome_var.upper() for suf in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
            val_limpo = (valor or "").strip()
            if len(val_limpo) >= 6 and val_limpo in resultado:
                resultado = resultado.replace(val_limpo, "[CREDENCIAL_OCULTADA]")
    # Mascara padrões de tokens no formato Bearer ou prefixos conhecidos
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


def verificar_chave(perfil: dict[str, Any]) -> str:
    """Obtém e valida a chave de API do provedor a partir do ambiente (RF01, RF04).

    Provedores locais (como Ollama, onde `env_chave` é None) não exigem chave.
    """
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


def listar_modelos(perfil: dict[str, Any], timeout_s: float = 30) -> list[str]:
    """Consulta o endpoint /models do provedor configurado com tratamento de falhas."""
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
    """Envia mensagens ao endpoint /chat/completions com proteção de credenciais e tratamento de falhas (RF04).

    Retorna dicionário contendo:
      - texto: conteúdo textual da resposta do modelo
      - latencia_s: tempo de resposta em segundos
      - tokens_entrada, tokens_saida, tokens_total: contagem de tokens informada pelo provedor
      - custo_usd: custo estimado se a tabela `precos` for fornecida
      - tentativas: número de tentativas realizadas até o sucesso
      - modelo_resposta: identificador do modelo retornado pela API
    """
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
            "erro": "dry-run (nenhuma chamada realizada)",
        }

    chave = verificar_chave(perfil)
    corpo: dict[str, Any] = {"model": modelo, "messages": mensagens, **(parametros or {})}
    if json_mode:
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

        return {
            "texto": texto,
            "latencia_s": round(latencia, 2),
            "tokens_entrada": tok_in,
            "tokens_saida": tok_out,
            "tokens_total": tok_total,
            "custo_usd": custo,
            "tentativas": tentativa,
            "modelo_resposta": modelo_resp,
        }

    raise ErroProvedor(
        f"Falha após {max_tentativas} tentativa(s): {ultimo_erro}",
        codigo_erro=ultimo_codigo,
        status_code=ultimo_status,
    )
