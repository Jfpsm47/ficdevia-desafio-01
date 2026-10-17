"""Cliente HTTP mínimo (API compatível com OpenAI /chat/completions) usado nos experimentos do
Estudante 1 (RF02 e comparação de modelos).

Fica separado de src/llm_client.py (Estudante 2) para não haver conflito de responsabilidades;
os experimentos podem passar a usar o cliente oficial sem alterar os prompts.
A chave é lida do ambiente e nunca é registrada.
"""
from __future__ import annotations

import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


class ErroProvedor(Exception):
    """Falha do provedor com mensagem compreensível para o operador."""


def verificar_chave(perfil: dict) -> str:
    variavel = perfil.get("env_chave")
    if not variavel:  # provedor local (ex.: Ollama)
        return "local"
    chave = os.getenv(variavel, "").strip()
    if not chave:
        raise ErroProvedor(f"Chave ausente: defina {variavel} no arquivo .env (veja .env.example).")
    return chave


def listar_modelos(perfil: dict, timeout_s: float = 30) -> list[str]:
    r = httpx.get(perfil["base_url"].rstrip("/") + "/models",
                  headers={"Authorization": f"Bearer {verificar_chave(perfil)}"}, timeout=timeout_s)
    r.raise_for_status()
    return sorted(m.get("id", "") for m in r.json().get("data", []))


def chamar_chat(perfil: dict, modelo: str, mensagens: list[dict], parametros: dict,
                timeout_s: float = 60, tentativas: int = 3, json_mode: bool = False) -> dict:
    """Envia a conversa e devolve {texto, latencia_s, tokens_entrada, tokens_saida, tentativas}."""
    corpo = {"model": modelo, "messages": mensagens, **parametros}
    if json_mode:
        corpo["response_format"] = {"type": "json_object"}
    cabecalhos = {"Authorization": f"Bearer {verificar_chave(perfil)}"}
    url = perfil["base_url"].rstrip("/") + "/chat/completions"

    ultimo_erro = "erro desconhecido"
    for tentativa in range(1, tentativas + 1):
        inicio = time.perf_counter()
        try:
            r = httpx.post(url, headers=cabecalhos, json=corpo, timeout=timeout_s)
        except httpx.TimeoutException:
            ultimo_erro = f"Tempo limite de {timeout_s}s excedido."
            time.sleep(2 * tentativa)
            continue
        except httpx.HTTPError as e:
            raise ErroProvedor(f"Serviço indisponível ou sem conexão ({type(e).__name__}).") from None
        latencia = time.perf_counter() - inicio

        if r.status_code in (401, 403):
            raise ErroProvedor("Autenticação recusada pelo provedor: verifique a chave no .env.")
        if r.status_code == 429 or r.status_code >= 500:
            ultimo_erro = ("Limite de requisições atingido (HTTP 429)." if r.status_code == 429
                           else f"Provedor indisponível (HTTP {r.status_code}).")
            espera = float(r.headers.get("retry-after", 0) or 0) or 5 * tentativa
            time.sleep(min(espera, 60))
            continue
        if r.status_code >= 400:
            raise ErroProvedor(f"Requisição rejeitada (HTTP {r.status_code}): {r.text[:300]}")

        dados = r.json()
        escolhas = dados.get("choices") or []
        texto = ((escolhas[0].get("message") or {}).get("content") or "").strip() if escolhas else ""
        if not texto:
            ultimo_erro = "Resposta vazia do modelo."
            continue
        uso = dados.get("usage") or {}
        return {"texto": texto, "latencia_s": round(latencia, 2),
                "tokens_entrada": uso.get("prompt_tokens"), "tokens_saida": uso.get("completion_tokens"),
                "tentativas": tentativa, "modelo_resposta": dados.get("model", modelo)}
    raise ErroProvedor(f"Falha após {tentativas} tentativas: {ultimo_erro}")


def custo_estimado(precos: dict, modelo: str, tokens_entrada, tokens_saida):
    """Custo em USD a partir de config.json (precos_usd_por_milhao_tokens); None se não configurado."""
    p = precos.get(modelo)
    if not p or tokens_entrada is None or tokens_saida is None:
        return None
    return round((tokens_entrada * p["entrada"] + tokens_saida * p["saida"]) / 1_000_000, 6)
