"""Cliente HTTP dos experimentos do Estudante 1 (RF02 e comparação de modelos).

Delega ao cliente oficial `src/llm_client.py` (Estudante 2), preservando a mesma interface pública.
"""
from __future__ import annotations

from src.llm_client import (
    ErroProvedor,
    chamar_chat,
    custo_estimado,
    listar_modelos,
    ocultar_segredos,
    verificar_chave,
)

__all__ = [
    "ErroProvedor",
    "chamar_chat",
    "custo_estimado",
    "listar_modelos",
    "ocultar_segredos",
    "verificar_chave",
]
