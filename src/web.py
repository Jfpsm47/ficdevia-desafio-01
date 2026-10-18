"""Interface Web local para Revisão Humana e Auditoria da Central Inteligente (RF01, RF05, RF09, RF11, RF13).

Responsabilidade: Estudante 2.
Substitui a interação via terminal por uma aplicação web responsiva servida localmente:
- Solicita a identificação do revisor uma única vez ao abrir a interface;
- Exibe lado a lado: Conteúdo Original da Solicitação (esquerda, com suporte a texto, player de
  áudio MP3 e visualizador de PDF/imagem) e Resultado em PDF da Minuta + Revisão Humana (direita);
- Permite aprovar, editar/corrigir manualmente (regenerando o PDF) ou rejeitar/solicitar nova geração;
- Registra todas as decisões no log estruturado (`resultados/logs/execucoes.jsonl`) e no relatório.
"""
from __future__ import annotations

import json
import mimetypes
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from src import audit, avaliacao, main, prompts

RAIZ = prompts.RAIZ


def _carregar_estado_caso(caso_id: str) -> dict[str, Any]:
    """Reúne os dados originais, extração, minuta PDF e histórico de auditoria de um caso para a UI web."""
    caminho_gab = RAIZ / main.CONFIG["caminhos"]["gabaritos"] / f"{caso_id}.json"
    gabarito = avaliacao.carregar_gabarito(caso_id) if caminho_gab.exists() else {}
    arquivo_origem = gabarito.get("arquivo_origem", "")
    _, modalidade = main.validar_arquivo_entrada(arquivo_origem) if arquivo_origem else (None, "texto")

    # Conteúdo textual original ou transcrição/OCR intermediário
    texto_original = ""
    caminho_orig = RAIZ / arquivo_origem if arquivo_origem else None
    if modalidade == "texto" and caminho_orig and caminho_orig.exists():
        texto_original = caminho_orig.read_text(encoding="utf-8")
    elif modalidade == "audio":
        ref_rel = gabarito.get("transcricao_referencia", "dados/gabaritos/caso02_transcricao_referencia.txt")
        if (RAIZ / ref_rel).exists():
            texto_original = (RAIZ / ref_rel).read_text(encoding="utf-8")
    elif modalidade == "imagem":
        nome_arq_ocr = f"{caso_id}_revisado.txt" if caso_id.endswith("_ocr") else f"{caso_id}_ocr_revisado.txt"
        arq_ocr = RAIZ / main.CONFIG["caminhos"]["processados"] / nome_arq_ocr
        if arq_ocr.exists():
            texto_original = arq_ocr.read_text(encoding="utf-8")

    # Extração JSON (RF05)
    arq_ext = RAIZ / main.CONFIG["caminhos"]["processados"] / f"{caso_id}_extracao.json"
    extracao = json.loads(arq_ext.read_text(encoding="utf-8")) if arq_ext.exists() else None
    if not texto_original and extracao and extracao.get("texto_original_preservado"):
        texto_original = extracao["texto_original_preservado"]

    # Minuta JSON e PDF (RF09)
    rel_dir_minutas = main.CONFIG["caminhos"].get("minutas", "resultados/minutas")
    dir_minutas = RAIZ / rel_dir_minutas
    arq_min_json = dir_minutas / f"{caso_id}_minuta.json"
    arq_min_pdf = dir_minutas / f"{caso_id}_minuta.pdf"
    prefixo_curto = caso_id.split("_")[0]
    arq_corrigida_pdf = dir_minutas / f"{prefixo_curto}_corrigida.pdf"
    arq_corrigida_md = dir_minutas / f"{prefixo_curto}_corrigida.md"

    minuta_json = json.loads(arq_min_json.read_text(encoding="utf-8")) if arq_min_json.exists() else None
    minuta_md = main.ler_texto_minuta_pdf(arq_min_pdf) if arq_min_pdf.exists() else ""
    if arq_corrigida_pdf.exists():
        minuta_corrigida_md = main.ler_texto_minuta_pdf(arq_corrigida_pdf)
    elif arq_corrigida_md.exists():
        minuta_corrigida_md = arq_corrigida_md.read_text(encoding="utf-8")
    else:
        minuta_corrigida_md = ""

    # Avaliação automática (RF13)
    av_minuta = None
    if minuta_json:
        contexto_afirm = prompts.ler_prompt("contexto_institucional.md").split("## O que NÃO está disponível")[0]
        fontes_av = texto_original + "\n" + contexto_afirm
        if modalidade in ("audio", "imagem") and extracao:
            fontes_av += f"\n{extracao.get('protocolo', '')}\n{extracao.get('data_solicitacao', '')}"
        av_minuta = avaliacao.avaliar_minuta(
            main._texto_minuta_para_avaliacao(minuta_json),
            gabarito or {},
            fontes_av,
            verificar_formato=False,
        )
        if gabarito.get("seguranca", {}).get("contem_injection") and not minuta_json.get("alertas_seguranca"):
            av_minuta["achados"].append(
                {
                    "criterio": "seguranca",
                    "gravidade": "alto",
                    "descricao": "Injection presente, mas não registrada em alertas_seguranca da minuta.",
                }
            )
            av_minuta["contagem"] = {
                g: sum(a["gravidade"] == g for a in av_minuta["achados"]) for g in avaliacao.GRAVIDADES
            }
            av_minuta["decisao_sugerida"] = avaliacao.decidir(av_minuta["achados"])

    # Último registro de auditoria da minuta
    registros = [r for r in audit.ler_registros() if r.get("caso_id") == caso_id and r.get("etapa") == "minuta"]
    ultimo_reg = registros[-1] if registros else {}
    decisao_humana = ultimo_reg.get("decisao_humana", "PENDENTE")

    if decisao_humana == "Corrigida" and arq_corrigida_pdf.exists():
        url_minuta_pdf = f"/arquivos/{rel_dir_minutas}/{prefixo_curto}_corrigida.pdf"
    elif arq_min_pdf.exists():
        url_minuta_pdf = f"/arquivos/{rel_dir_minutas}/{caso_id}_minuta.pdf"
    else:
        url_minuta_pdf = None

    return {
        "caso_id": caso_id,
        "modalidade": modalidade,
        "finalidade": gabarito.get("finalidade", ""),
        "arquivo_origem": arquivo_origem,
        "url_arquivo_origem": f"/arquivos/{arquivo_origem}" if arquivo_origem else None,
        "texto_original": texto_original,
        "campos_esperados_ocr": gabarito.get("campos_esperados") if modalidade == "imagem" else None,
        "extracao": extracao,
        "minuta_json": minuta_json,
        "minuta_md": minuta_md,
        "minuta_corrigida_md": minuta_corrigida_md,
        "url_minuta_pdf": url_minuta_pdf,
        "avaliacao_minuta": av_minuta,
        "id_execucao": ultimo_reg.get("id_execucao"),
        "decisao_humana": decisao_humana,
        "revisor": ultimo_reg.get("revisor") or "",
        "justificativa_humana": ultimo_reg.get("justificativa_humana") or "",
        "data_hora": ultimo_reg.get("data_hora") or "",
        "modelo": f"{ultimo_reg.get('provedor', 'groq')}/{ultimo_reg.get('modelo', 'openai/gpt-oss-120b')}",
        "latencia_s": ultimo_reg.get("latencia_s"),
        "custo_usd": ultimo_reg.get("custo_usd"),
    }


def _listar_todos_casos() -> list[dict[str, Any]]:
    casos_ids = main.CONFIG.get("producao", {}).get(
        "casos",
        ["caso01_texto", "caso02_audio", "caso03_ocr", "caso04_texto_injection", "caso05_texto_incompleto"],
    )
    return [_carregar_estado_caso(cid) for cid in casos_ids]


def registrar_revisao_web(
    *,
    caso_id: str,
    decisao: str,
    revisor_nome: str,
    revisor_cargo: str,
    justificativa: str,
    texto_minuta_editado: str | None = None,
    nova_geracao: bool = False,
    dry_run_padrao: bool = True,
) -> dict[str, Any]:
    """Aplica a decisão humana enviada pela interface web, atualiza o PDF da minuta e grava auditoria."""
    revisor_nome = (revisor_nome or "").strip()
    revisor_cargo = (revisor_cargo or "").strip()
    justificativa = (justificativa or "").strip()
    if not revisor_nome:
        raise ValueError("Informe o nome do revisor antes de registrar a revisão.")
    if not justificativa:
        raise ValueError("Informe a justificativa da revisão humana.")

    revisor_completo = f"{revisor_nome} ({revisor_cargo})" if revisor_cargo else revisor_nome
    cfg_prod = main.CONFIG.get("producao", {})
    provedor = cfg_prod.get("provedor", "groq")
    modelo = cfg_prod.get("modelo", "openai/gpt-oss-120b")

    if nova_geracao:
        # Executa novamente o pipeline para o caso e aplica a decisão informada
        main.processar_caso(
            caso_id=caso_id,
            provedor=provedor,
            modelo=modelo,
            cfg_prod=cfg_prod,
            dry_run=dry_run_padrao,
            nao_interativo=True,
            revisor=revisor_completo,
        )

    rel_dir_minutas = main.CONFIG["caminhos"].get("minutas", "resultados/minutas")
    dir_minutas = RAIZ / rel_dir_minutas
    dir_minutas.mkdir(parents=True, exist_ok=True)
    arq_min_pdf = dir_minutas / f"{caso_id}_minuta.pdf"
    caminho_saida_rel = f"{rel_dir_minutas}/{caso_id}_minuta.pdf"

    data_curta = time.strftime("%d/%m/%Y")
    base_md = (
        texto_minuta_editado.strip()
        if (texto_minuta_editado and texto_minuta_editado.strip())
        else (main.ler_texto_minuta_pdf(arq_min_pdf) if arq_min_pdf.exists() else "")
    )
    md_atualizado = main.aplicar_decisao_no_markdown(
        texto_md=base_md,
        decisao=decisao,
        revisor=revisor_completo,
        data_str=data_curta,
        justificativa=justificativa,
    )
    main.gerar_pdf_minuta(md_atualizado, arq_min_pdf)

    registros = [r for r in audit.ler_registros() if r.get("caso_id") == caso_id and r.get("etapa") == "minuta"]
    if registros:
        id_exec = registros[-1]["id_execucao"]
        audit.atualizar_decisao_humana(
            id_execucao=id_exec,
            decisao=decisao,
            revisor=revisor_completo,
            justificativa=justificativa,
            arquivo_saida_final=caminho_saida_rel,
        )
    else:
        estado = _carregar_estado_caso(caso_id)
        audit.registrar_execucao(
            audit.criar_registro(
                caso_id=caso_id,
                etapa="minuta",
                modalidade=estado["modalidade"],
                arquivo_origem=estado["arquivo_origem"],
                provedor=provedor,
                modelo=modelo,
                parametros=cfg_prod.get("parametros", {}),
                versao_prompt=prompts.VERSOES["minuta"][1],
                arquivo_saida=caminho_saida_rel,
                resumo_resultado=f"Revisão humana via Web: {decisao}",
                avaliacao_auto=estado["avaliacao_minuta"],
                decisao_humana=decisao,
                revisor=revisor_completo,
                justificativa_humana=justificativa,
            )
        )

    audit.gerar_relatorio_auditoria()
    return _carregar_estado_caso(caso_id)


# ---------------------------------------------------------------- HTML / CSS / JS da Aplicação Web

PAGINA_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Central Inteligente de Atendimento — Revisão Humana</title>
  <style>
    :root {
      --azul-gov: #0f2c59;
      --azul-secundario: #1d4ed8;
      --azul-claro: #eff6ff;
      --fundo: #f8fafc;
      --superficie: #ffffff;
      --borda: #e2e8f0;
      --texto: #0f172a;
      --texto-suave: #475569;
      --verde: #15803d;
      --verde-claro: #dcfce7;
      --amarelo: #b45309;
      --amarelo-claro: #fef3c7;
      --vermelho: #b91c1c;
      --vermelho-claro: #fee2e2;
      --sombra: 0 1px 3px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04);
      --raio: 10px;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--fundo);
      color: var(--texto);
      line-height: 1.5;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Cabeçalho Institucional */
    header {
      background: var(--azul-gov);
      color: #fff;
      padding: 0.85rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 1rem;
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }
    .marca {
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }
    .marca img {
      height: 40px;
      width: auto;
      background: #fff;
      padding: 3px;
      border-radius: 6px;
    }
    .marca h1 {
      font-size: 1.05rem;
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    .marca p {
      font-size: 0.78rem;
      color: #cbd5e1;
    }
    .indicadores-topo {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .pilula-topo {
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.2);
      padding: 0.35rem 0.75rem;
      border-radius: 999px;
      font-size: 0.8rem;
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }
    .btn-topo {
      background: #fff;
      color: var(--azul-gov);
      border: none;
      padding: 0.4rem 0.85rem;
      border-radius: 6px;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-topo:hover { background: #e2e8f0; }

    /* Barra de seleção de casos */
    .barra-casos {
      background: var(--superficie);
      border-bottom: 1px solid var(--borda);
      padding: 0.65rem 1.5rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      overflow-x: auto;
    }
    .cartao-caso-tab {
      border: 1px solid var(--borda);
      background: var(--fundo);
      padding: 0.5rem 0.9rem;
      border-radius: 8px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.55rem;
      font-size: 0.83rem;
      font-weight: 600;
      color: var(--texto-suave);
      white-space: nowrap;
      transition: all 0.15s;
    }
    .cartao-caso-tab:hover {
      border-color: #94a3b8;
      color: var(--texto);
    }
    .cartao-caso-tab.ativo {
      background: var(--azul-claro);
      border-color: var(--azul-secundario);
      color: var(--azul-secundario);
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge.aprovada { background: var(--verde-claro); color: var(--verde); }
    .badge.corrigida { background: var(--amarelo-claro); color: var(--amarelo); }
    .badge.rejeitada { background: var(--vermelho-claro); color: var(--vermelho); }
    .badge.pendente { background: #e2e8f0; color: #475569; }

    /* Layout Principal Lado a Lado (Esquerda: Original | Direita: Resultado) */
    main.painel-revisao {
      flex: 1;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.25rem;
      padding: 1.25rem 1.5rem;
      max-width: 1680px;
      width: 100%;
      margin: 0 auto;
      align-items: start;
    }
    @media (max-width: 980px) {
      main.painel-revisao {
        grid-template-columns: 1fr;
      }
    }

    .coluna {
      background: var(--superficie);
      border: 1px solid var(--borda);
      border-radius: var(--raio);
      box-shadow: var(--sombra);
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }
    .cabecalho-coluna {
      padding: 0.9rem 1.25rem;
      background: #f1f5f9;
      border-bottom: 1px solid var(--borda);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    }
    .cabecalho-coluna h2 {
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--azul-gov);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .corpo-coluna {
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }

    /* Metadados e caixas de conteúdo */
    .grade-meta {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 0.65rem;
      background: var(--fundo);
      padding: 0.8rem;
      border-radius: 8px;
      border: 1px solid var(--borda);
      font-size: 0.82rem;
    }
    .item-meta span {
      display: block;
      font-size: 0.7rem;
      text-transform: uppercase;
      color: var(--texto-suave);
      font-weight: 600;
    }
    .item-meta strong {
      color: var(--texto);
      word-break: break-all;
    }

    .caixa-texto-original {
      background: #0f172a;
      color: #f8fafc;
      padding: 1rem 1.15rem;
      border-radius: 8px;
      font-family: "JetBrains Mono", Consolas, monospace;
      font-size: 0.84rem;
      white-space: pre-wrap;
      line-height: 1.6;
      max-height: 520px;
      overflow-y: auto;
    }
    .midia-container {
      border: 1px solid var(--borda);
      border-radius: 8px;
      padding: 0.85rem;
      background: var(--fundo);
    }
    .midia-container audio {
      width: 100%;
      margin-top: 0.4rem;
    }
    .midia-container iframe {
      width: 100%;
      height: 420px;
      border: 1px solid var(--borda);
      border-radius: 6px;
      background: #fff;
    }

    /* Abas do lado direito */
    .abas-resultado {
      display: flex;
      gap: 0.4rem;
      border-bottom: 1px solid var(--borda);
      padding-bottom: 0.6rem;
    }
    .btn-aba {
      background: transparent;
      border: 1px solid transparent;
      padding: 0.4rem 0.85rem;
      border-radius: 6px;
      font-size: 0.83rem;
      font-weight: 600;
      color: var(--texto-suave);
      cursor: pointer;
    }
    .btn-aba.ativa {
      background: var(--azul-claro);
      color: var(--azul-secundario);
      border-color: #bfdbfe;
    }

    .alerta-bloqueio {
      background: #fff7ed;
      border-left: 4px solid #ea580c;
      padding: 0.65rem 0.9rem;
      font-size: 0.8rem;
      color: #9a3412;
      border-radius: 4px;
      font-weight: 600;
    }

    .preview-minuta {
      background: #fff;
      border: 1px solid var(--borda);
      border-radius: 8px;
      padding: 1.25rem;
      font-size: 0.88rem;
      white-space: pre-wrap;
      line-height: 1.65;
      max-height: 430px;
      overflow-y: auto;
    }
    textarea.editor-minuta {
      width: 100%;
      min-height: 320px;
      padding: 0.9rem;
      border: 2px solid var(--azul-secundario);
      border-radius: 8px;
      font-family: "JetBrains Mono", Consolas, monospace;
      font-size: 0.83rem;
      line-height: 1.55;
      resize: vertical;
    }

    /* Lista de achados automáticos */
    .lista-achados {
      display: flex;
      flex-direction: column;
      gap: 0.45rem;
    }
    .item-achado {
      padding: 0.55rem 0.8rem;
      border-radius: 6px;
      font-size: 0.82rem;
      border-left: 4px solid #64748b;
      background: var(--fundo);
    }
    .item-achado.critico { border-left-color: var(--vermelho); background: var(--vermelho-claro); color: #7f1d1d; }
    .item-achado.alto { border-left-color: #ea580c; background: #ffedd5; color: #7c2d12; }
    .item-achado.medio { border-left-color: var(--amarelo); background: var(--amarelo-claro); color: #78350f; }
    .item-achado.baixo { border-left-color: #3b82f6; background: #eff6ff; color: #1e3a8a; }

    /* Painel de Revisão Humana */
    .box-revisao {
      border-top: 2px solid var(--borda);
      padding-top: 1rem;
      margin-top: 0.25rem;
      display: flex;
      flex-direction: column;
      gap: 0.85rem;
    }
    .aviso-bloqueio-revisor {
      background: var(--azul-claro);
      border: 1px dashed var(--azul-secundario);
      padding: 1rem;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }
    .botoes-decisao {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 0.6rem;
    }
    @media (max-width: 560px) {
      .botoes-decisao { grid-template-columns: 1fr; }
    }
    .btn-decisao {
      padding: 0.65rem 0.75rem;
      border-radius: 8px;
      border: 2px solid var(--borda);
      background: #fff;
      font-weight: 700;
      font-size: 0.84rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-decisao.aprovar.selecionado {
      border-color: var(--verde);
      background: var(--verde-claro);
      color: var(--verde);
    }
    .btn-decisao.corrigir.selecionado {
      border-color: var(--amarelo);
      background: var(--amarelo-claro);
      color: var(--amarelo);
    }
    .btn-decisao.rejeitar.selecionado {
      border-color: var(--vermelho);
      background: var(--vermelho-claro);
      color: var(--vermelho);
    }

    .campo-form label {
      display: block;
      font-size: 0.8rem;
      font-weight: 600;
      margin-bottom: 0.3rem;
      color: var(--texto);
    }
    .campo-form input, .campo-form textarea {
      width: 100%;
      padding: 0.6rem 0.75rem;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 0.86rem;
      font-family: inherit;
    }
    .btn-primario {
      background: var(--azul-secundario);
      color: #fff;
      border: none;
      padding: 0.7rem 1.2rem;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.88rem;
      cursor: pointer;
      transition: background 0.15s;
    }
    .btn-primario:hover { background: #1e40af; }
    .btn-primario:disabled { background: #94a3b8; cursor: not-allowed; }

    /* Modal de Identificação Obrigatória do Revisor */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.65);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1rem;
      z-index: 100;
    }
    .modal-backdrop.visivel { display: flex; }
    .modal {
      background: #fff;
      border-radius: 12px;
      max-width: 480px;
      width: 100%;
      padding: 1.5rem;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.2);
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .modal h3 {
      font-size: 1.08rem;
      color: var(--azul-gov);
    }
    .modal p {
      font-size: 0.84rem;
      color: var(--texto-suave);
    }
    .rodape-modal {
      display: flex;
      justify-content: flex-end;
      gap: 0.6rem;
      margin-top: 0.25rem;
    }
    .toast {
      position: fixed;
      bottom: 1.25rem;
      right: 1.25rem;
      background: #0f172a;
      color: #fff;
      padding: 0.75rem 1.1rem;
      border-radius: 8px;
      font-size: 0.84rem;
      font-weight: 600;
      box-shadow: 0 10px 15px rgba(0,0,0,0.2);
      display: none;
      z-index: 200;
    }
  </style>
</head>
<body>
  <header>
    <div class="marca">
      <img src="/arquivos/dados/originais/brasao.png" alt="Brasão GOV-MT" onerror="this.style.display='none'" />
      <div>
        <h1>Central Inteligente de Atendimento e Comunicação Institucional</h1>
        <p>Revisão Humana Obrigatória · Envio Automático Bloqueado</p>
      </div>
    </div>
    <div class="indicadores-topo">
      <div class="pilula-topo" id="badgeTaxaAprovacao">Taxa de aprovação: —</div>
      <div class="pilula-topo" id="badgeRevisorAtual">Revisor: não identificado</div>
      <button class="btn-topo" onclick="abrirModalRevisor()">Iniciar / Trocar Revisor</button>
    </div>
  </header>

  <nav class="barra-casos" id="barraCasos"></nav>

  <main class="painel-revisao">
    <!-- COLUNA ESQUERDA: CONTEÚDO ORIGINAL DA SOLICITAÇÃO -->
    <section class="coluna" aria-label="Conteúdo Original">
      <div class="cabecalho-coluna">
        <h2>1. Conteúdo Original da Solicitação (Entrada)</h2>
        <span class="badge pendente" id="badgeModalidade">texto</span>
      </div>
      <div class="corpo-coluna">
        <div class="grade-meta">
          <div class="item-meta">
            <span>Caso de Teste</span>
            <strong id="metaCasoId">—</strong>
          </div>
          <div class="item-meta">
            <span>Arquivo de Origem (Somente Leitura)</span>
            <strong id="metaArquivoOrigem">—</strong>
          </div>
          <div class="item-meta">
            <span>Finalidade</span>
            <strong id="metaFinalidade">—</strong>
          </div>
        </div>

        <div id="containerMidiaOriginal" class="midia-container" style="display:none;"></div>

        <div>
          <div style="font-size:0.78rem; font-weight:700; color:var(--texto-suave); margin-bottom:0.35rem; text-transform:uppercase;">
            Texto Original / Transcrição de Referência
          </div>
          <pre class="caixa-texto-original" id="textoOriginalPre">Carregando...</pre>
        </div>
      </div>
    </section>

    <!-- COLUNA DIREITA: RESULTADO GERADO E REVISÃO HUMANA -->
    <section class="coluna" aria-label="Resultado e Revisão Humana">
      <div class="cabecalho-coluna">
        <h2>2. Resultado Processado &amp; Revisão Humana</h2>
        <span class="badge pendente" id="badgeStatusDecisao">PENDENTE</span>
      </div>
      <div class="corpo-coluna">
        <div class="alerta-bloqueio">
          MINUTA GERADA COM APOIO DE IA — PENDENTE DE REVISÃO HUMANA — ENVIO AUTOMÁTICO BLOQUEADO
        </div>

        <div class="abas-resultado">
          <button class="btn-aba ativa" id="btnAbaMinuta" onclick="alternarAba('minuta')">Minuta Institucional PDF</button>
          <button class="btn-aba" id="btnAbaExtracao" onclick="alternarAba('extracao')">Extração JSON</button>
          <button class="btn-aba" id="btnAbaAvaliacao" onclick="alternarAba('avaliacao')">Avaliação &amp; Segurança</button>
        </div>

        <!-- ABA 1: MINUTA PDF -->
        <div id="abaMinuta">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.45rem; font-size:0.8rem;">
            <span style="font-weight:700; color:var(--azul-gov);" id="lblCaminhoPdfMinuta">Arquivo PDF da Minuta</span>
            <a id="linkBaixarPdfMinuta" href="#" target="_blank" rel="noopener" style="color:var(--azul-secundario); font-weight:600; text-decoration:none;">
              Abrir / Baixar PDF ↗
            </a>
          </div>
          <iframe
            id="iframeMinutaPdf"
            title="Visualização do PDF da Minuta Institucional"
            style="width:100%; height:440px; border:1px solid var(--borda); border-radius:8px; background:#fff;"
          ></iframe>
          <div id="containerEditorMinuta" style="display:none; margin-top:0.65rem;">
            <label style="font-size:0.78rem; font-weight:700; color:var(--azul-secundario); display:block; margin-bottom:0.3rem;">
              Edição Manual da Minuta pelo Servidor (regenera o PDF ao salvar):
            </label>
            <textarea id="editorMinuta" class="editor-minuta"></textarea>
          </div>
        </div>

        <!-- ABA 2: EXTRAÇÃO JSON -->
        <div id="abaExtracao" style="display:none;">
          <div class="grade-meta" id="resumoExtracaoCards" style="margin-bottom:0.75rem;"></div>
          <pre class="caixa-texto-original" id="jsonExtracaoPre" style="max-height:340px;"></pre>
        </div>

        <!-- ABA 3: AVALIAÇÃO AUTOMÁTICA -->
        <div id="abaAvaliacao" style="display:none;">
          <div class="grade-meta" style="margin-bottom:0.75rem;">
            <div class="item-meta">
              <span>Sugestão Automática (Protocolo)</span>
              <strong id="avSugestaoAuto">—</strong>
            </div>
            <div class="item-meta">
              <span>Modelo / Latência / Custo</span>
              <strong id="avMetricasModelo">—</strong>
            </div>
          </div>
          <div class="lista-achados" id="listaAchadosAuto"></div>
        </div>

        <!-- PAINEL DE DECISÃO DO REVISOR -->
        <div class="box-revisao">
          <div id="bloqueioIdentificacaoRevisor" class="aviso-bloqueio-revisor">
            <div>
              <strong style="color:var(--azul-gov); font-size:0.88rem;">Identificação obrigatória do revisor</strong>
              <p style="font-size:0.78rem; color:var(--texto-suave);">
                Informe os dados do revisor responsável para liberar a revisão dos casos.
              </p>
            </div>
            <button class="btn-primario" onclick="abrirModalRevisor()">Informar Dados do Revisor</button>
          </div>

          <div id="formularioDecisaoRevisor" style="display:none; flex-direction:column; gap:0.8rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; color:var(--texto-suave);">
              <span>Revisor ativo na sessão: <strong id="lblRevisorAtivo" style="color:var(--azul-gov);"></strong></span>
              <button type="button" onclick="abrirModalRevisor()" style="background:none; border:none; color:var(--azul-secundario); cursor:pointer; font-weight:600; font-size:0.78rem;">
                Trocar revisor
              </button>
            </div>

            <div class="botoes-decisao">
              <button type="button" class="btn-decisao aprovar" id="btnDecAprovar" onclick="selecionarDecisao('Aprovada')">
                ✓ Aprovar Minuta
              </button>
              <button type="button" class="btn-decisao corrigir" id="btnDecCorrigir" onclick="selecionarDecisao('Corrigida')">
                ✎ Corrigir Manualmente
              </button>
              <button type="button" class="btn-decisao rejeitar" id="btnDecRejeitar" onclick="selecionarDecisao('Rejeitada')">
                ✕ Rejeitar / Nova Geração
              </button>
            </div>

            <div class="campo-form">
              <label for="txtJustificativa">Justificativa da decisão humana (obrigatória):</label>
              <textarea id="txtJustificativa" rows="2" placeholder="Descreva os motivos da aprovação, correção manual ou rejeição..."></textarea>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center; gap:0.75rem; flex-wrap:wrap;">
              <label style="font-size:0.78rem; color:var(--texto-suave); display:flex; align-items:center; gap:0.35rem;">
                <input type="checkbox" id="chkNovaGeracao" />
                Reprocessar caso no pipeline ao salvar
              </label>
              <button type="button" class="btn-primario" id="btnSalvarRevisao" onclick="salvarRevisao()">
                Registrar Decisão Humana
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>

  <!-- MODAL DE DADOS DO REVISOR (SOLICITADO APENAS UMA VEZ AO ABRIR) -->
  <div class="modal-backdrop" id="modalRevisor">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="tituloModalRevisor">
      <h3 id="tituloModalRevisor">Identificação do Servidor Revisor</h3>
      <p>
        Informe os dados do servidor responsável pela sessão de revisão humana.
        Nenhuma resposta é enviada automaticamente ao cidadão.
      </p>
      <div class="campo-form">
        <label for="inputNomeRevisor">Nome completo do revisor *</label>
        <input type="text" id="inputNomeRevisor" placeholder="Ex.: João Flávio Pompeo" required />
      </div>
      <div class="campo-form">
        <label for="inputCargoRevisor">Cargo / Setor *</label>
        <input type="text" id="inputCargoRevisor" placeholder="Ex.: Secretaria Escolar — ETE Cuiabá" value="Secretaria Escolar — ETE Cuiabá" required />
      </div>
      <div class="rodape-modal">
        <button type="button" class="btn-aba" onclick="fecharModalRevisor()">Cancelar</button>
        <button type="button" class="btn-primario" onclick="confirmarRevisor()">Confirmar e Iniciar Revisão</button>
      </div>
    </div>
  </div>

  <div class="toast" id="toastMsg"></div>

  <script>
    let casos = [];
    let casoAtual = null;
    let abaAtual = 'minuta';
    let decisaoSelecionada = 'Aprovada';
    // Pergunta quem é o revisor apenas uma vez ao abrir a interface
    let revisorConfirmado = false;
    let revisorAtual = { nome: '', cargo: 'Secretaria Escolar — ETE Cuiabá' };

    function mostrarToast(msg) {
      const t = document.getElementById('toastMsg');
      t.textContent = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3500);
    }

    function classeBadge(decisao) {
      const d = (decisao || '').toLowerCase();
      if (d.startsWith('aprov')) return 'aprovada';
      if (d.startsWith('corrig')) return 'corrigida';
      if (d.startsWith('rejeit')) return 'rejeitada';
      return 'pendente';
    }

    async function carregarCasos(manterCasoId = null) {
      const resp = await fetch('/api/casos');
      const dados = await resp.json();
      casos = dados.casos || [];
      document.getElementById('badgeTaxaAprovacao').textContent =
        `Taxa de aprovação: ${dados.taxa_aprovacao_pct} (${dados.aprovados}/${dados.total_avaliados})`;

      renderizarBarraCasos();
      const alvo = manterCasoId
        ? casos.find(c => c.caso_id === manterCasoId) || casos[0]
        : casos[0];
      if (alvo) selecionarCaso(alvo.caso_id);

      if (!revisorConfirmado) {
        abrirModalRevisor();
      }
    }

    function renderizarBarraCasos() {
      const nav = document.getElementById('barraCasos');
      nav.innerHTML = '';
      casos.forEach(c => {
        const btn = document.createElement('button');
        btn.className = 'cartao-caso-tab' + (casoAtual && casoAtual.caso_id === c.caso_id ? ' ativo' : '');
        const bClass = classeBadge(c.decisao_humana);
        btn.innerHTML = `
          <span>${c.caso_id}</span>
          <span class="badge ${bClass}">${c.decisao_humana || 'PENDENTE'}</span>
        `;
        btn.onclick = () => selecionarCaso(c.caso_id);
        nav.appendChild(btn);
      });
    }

    function selecionarCaso(casoId) {
      casoAtual = casos.find(c => c.caso_id === casoId);
      if (!casoAtual) return;
      renderizarBarraCasos();

      // Preenche Coluna Esquerda (Conteúdo Original)
      document.getElementById('badgeModalidade').textContent = casoAtual.modalidade;
      document.getElementById('metaCasoId').textContent = casoAtual.caso_id;
      document.getElementById('metaArquivoOrigem').textContent = casoAtual.arquivo_origem;
      document.getElementById('metaFinalidade').textContent = casoAtual.finalidade;
      document.getElementById('textoOriginalPre').textContent = casoAtual.texto_original || '(sem texto)';

      const midiaDiv = document.getElementById('containerMidiaOriginal');
      if (casoAtual.modalidade === 'audio' && casoAtual.url_arquivo_origem) {
        midiaDiv.style.display = 'block';
        midiaDiv.innerHTML = `
          <div style="font-size:0.78rem; font-weight:700; color:var(--azul-gov);">Áudio Original (${casoAtual.arquivo_origem}):</div>
          <audio controls src="${casoAtual.url_arquivo_origem}"></audio>
        `;
      } else if (casoAtual.modalidade === 'imagem' && casoAtual.url_arquivo_origem) {
        midiaDiv.style.display = 'block';
        midiaDiv.innerHTML = `
          <div style="font-size:0.78rem; font-weight:700; color:var(--azul-gov); margin-bottom:0.4rem;">
            Documento Digitalizado Original (${casoAtual.arquivo_origem}):
          </div>
          <iframe src="${casoAtual.url_arquivo_origem}"></iframe>
        `;
      } else {
        midiaDiv.style.display = 'none';
        midiaDiv.innerHTML = '';
      }

      // Preenche Coluna Direita (Resultado em PDF)
      const bStatus = document.getElementById('badgeStatusDecisao');
      bStatus.textContent = casoAtual.decisao_humana || 'PENDENTE';
      bStatus.className = 'badge ' + classeBadge(casoAtual.decisao_humana);

      const urlPdf = casoAtual.url_minuta_pdf
        ? `${casoAtual.url_minuta_pdf}?t=${Date.now()}`
        : '';
      const iframePdf = document.getElementById('iframeMinutaPdf');
      const linkPdf = document.getElementById('linkBaixarPdfMinuta');
      const lblPdf = document.getElementById('lblCaminhoPdfMinuta');
      if (urlPdf) {
        iframePdf.src = urlPdf;
        linkPdf.href = urlPdf;
        linkPdf.style.display = 'inline';
        lblPdf.textContent = casoAtual.url_minuta_pdf.replace('/arquivos/', '');
      } else {
        iframePdf.removeAttribute('src');
        linkPdf.style.display = 'none';
        lblPdf.textContent = '(PDF da minuta ainda não gerado)';
      }

      const textoExibicao = (casoAtual.decisao_humana === 'Corrigida' && casoAtual.minuta_corrigida_md)
        ? casoAtual.minuta_corrigida_md
        : (casoAtual.minuta_md || '');
      document.getElementById('editorMinuta').value = textoExibicao;

      // Extração JSON
      const ext = casoAtual.extracao || {};
      const cardsExt = document.getElementById('resumoExtracaoCards');
      cardsExt.innerHTML = `
        <div class="item-meta"><span>Protocolo</span><strong>${ext.protocolo || '—'}</strong></div>
        <div class="item-meta"><span>Data</span><strong>${ext.data_solicitacao || '—'}</strong></div>
        <div class="item-meta"><span>Solicitante</span><strong>${ext.solicitante || '—'}</strong></div>
        <div class="item-meta"><span>Categoria</span><strong>${ext.categoria || '—'}</strong></div>
        <div class="item-meta"><span>Confiança</span><strong>${ext.confianca || '—'}</strong></div>
        <div class="item-meta"><span>Alertas Segurança</span><strong>${(ext.alertas_seguranca || []).length}</strong></div>
      `;
      document.getElementById('jsonExtracaoPre').textContent = JSON.stringify(ext, null, 2);

      // Avaliação Automática
      const av = casoAtual.avaliacao_minuta || {};
      document.getElementById('avSugestaoAuto').textContent = av.decisao_sugerida || '—';
      const lat = casoAtual.latencia_s != null ? `${casoAtual.latencia_s} s` : 'cache/dry-run';
      const custo = casoAtual.custo_usd != null ? `US$ ${casoAtual.custo_usd}` : '—';
      document.getElementById('avMetricasModelo').textContent = `${casoAtual.modelo} · ${lat} · ${custo}`;

      const listaAchados = document.getElementById('listaAchadosAuto');
      listaAchados.innerHTML = '';
      const achados = av.achados || [];
      if (achados.length === 0) {
        listaAchados.innerHTML = '<div class="item-achado">Nenhum achado automático detectado pelas heurísticas.</div>';
      } else {
        achados.forEach(a => {
          const item = document.createElement('div');
          item.className = `item-achado ${a.gravidade}`;
          item.innerHTML = `<strong>[${a.gravidade.toUpperCase()}] (${a.criterio}):</strong> ${a.descricao}`;
          listaAchados.appendChild(item);
        });
      }

      // Configura estado inicial da decisão
      const decInicial = ['Aprovada', 'Corrigida', 'Rejeitada'].includes(casoAtual.decisao_humana)
        ? casoAtual.decisao_humana
        : 'Aprovada';
      selecionarDecisao(decInicial);
      document.getElementById('txtJustificativa').value = casoAtual.justificativa_humana || '';

      atualizarVisibilidadePainelRevisor();
    }

    function alternarAba(aba) {
      abaAtual = aba;
      document.getElementById('abaMinuta').style.display = aba === 'minuta' ? 'block' : 'none';
      document.getElementById('abaExtracao').style.display = aba === 'extracao' ? 'block' : 'none';
      document.getElementById('abaAvaliacao').style.display = aba === 'avaliacao' ? 'block' : 'none';
      document.getElementById('btnAbaMinuta').classList.toggle('ativa', aba === 'minuta');
      document.getElementById('btnAbaExtracao').classList.toggle('ativa', aba === 'extracao');
      document.getElementById('btnAbaAvaliacao').classList.toggle('ativa', aba === 'avaliacao');
    }

    function selecionarDecisao(decisao) {
      decisaoSelecionada = decisao;
      document.getElementById('btnDecAprovar').classList.toggle('selecionado', decisao === 'Aprovada');
      document.getElementById('btnDecCorrigir').classList.toggle('selecionado', decisao === 'Corrigida');
      document.getElementById('btnDecRejeitar').classList.toggle('selecionado', decisao === 'Rejeitada');
      document.getElementById('containerEditorMinuta').style.display = decisao === 'Corrigida' ? 'block' : 'none';
    }

    function abrirModalRevisor() {
      const inputNome = document.getElementById('inputNomeRevisor');
      if (revisorAtual.nome) {
        inputNome.value = revisorAtual.nome;
      }
      document.getElementById('modalRevisor').classList.add('visivel');
      setTimeout(() => inputNome.focus(), 50);
    }

    function fecharModalRevisor() {
      document.getElementById('modalRevisor').classList.remove('visivel');
    }

    function confirmarRevisor() {
      const nome = document.getElementById('inputNomeRevisor').value.trim();
      const cargo = document.getElementById('inputCargoRevisor').value.trim();
      if (!nome) {
        alert('Por favor, preencha o nome completo do revisor antes de iniciar a revisão.');
        return;
      }
      revisorAtual = { nome, cargo: cargo || 'Secretaria Escolar' };
      revisorConfirmado = true;
      document.getElementById('badgeRevisorAtual').textContent = `Revisor: ${revisorAtual.nome}`;
      fecharModalRevisor();
      atualizarVisibilidadePainelRevisor();
      mostrarToast(`Revisor identificado: ${revisorAtual.nome}`);
    }

    function atualizarVisibilidadePainelRevisor() {
      document.getElementById('bloqueioIdentificacaoRevisor').style.display = revisorConfirmado ? 'none' : 'flex';
      document.getElementById('formularioDecisaoRevisor').style.display = revisorConfirmado ? 'flex' : 'none';
      if (revisorConfirmado) {
        document.getElementById('lblRevisorAtivo').textContent =
          `${revisorAtual.nome} (${revisorAtual.cargo})`;
      }
    }

    async function salvarRevisao() {
      if (!casoAtual) return;
      if (!revisorConfirmado || !revisorAtual.nome) {
        abrirModalRevisor();
        return;
      }
      const justificativa = document.getElementById('txtJustificativa').value.trim();
      if (!justificativa) {
        alert('Informe a justificativa da revisão humana antes de salvar.');
        document.getElementById('txtJustificativa').focus();
        return;
      }
      const btn = document.getElementById('btnSalvarRevisao');
      btn.disabled = true;
      btn.textContent = 'Salvando...';

      try {
        const resp = await fetch('/api/revisar', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            caso_id: casoAtual.caso_id,
            decisao: decisaoSelecionada,
            revisor_nome: revisorAtual.nome,
            revisor_cargo: revisorAtual.cargo,
            justificativa: justificativa,
            texto_minuta_editado: decisaoSelecionada === 'Corrigida'
              ? document.getElementById('editorMinuta').value
              : null,
            nova_geracao: document.getElementById('chkNovaGeracao').checked,
          }),
        });
        const dados = await resp.json();
        if (!resp.ok) {
          alert(dados.erro || 'Erro ao salvar revisão.');
        } else {
          mostrarToast(`Decisão (${decisaoSelecionada}) e PDF atualizados para ${casoAtual.caso_id}!`);
          await carregarCasos(casoAtual.caso_id);
        }
      } finally {
        btn.disabled = false;
        btn.textContent = 'Registrar Decisão Humana';
      }
    }

    window.addEventListener('DOMContentLoaded', () => carregarCasos());
  </script>
</body>
</html>
"""


class ManipuladorWebRevisao(BaseHTTPRequestHandler):
    """Manipulador HTTP da interface de revisão humana."""

    dry_run_padrao: bool = True

    def log_message(self, format: str, *args: Any) -> None:
        # Mantém o console limpo sem poluir durante testes ou uso normal
        return

    def _enviar_json(self, dados: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        rota = urllib.parse.urlparse(self.path).path
        if rota in ("/", "/index.html"):
            corpo = PAGINA_HTML.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)
            return

        if rota == "/api/casos":
            casos = _listar_todos_casos()
            decisoes = [
                audit._normalizar_decisao_para_taxa(c.get("decisao_humana"))
                for c in casos
            ]
            validas = [d for d in decisoes if d is not None]
            aprovados = sum(1 for d in validas if d == "aprovar")
            taxa = avaliacao.taxa_aprovacao(validas) if validas else 0.0
            self._enviar_json(
                {
                    "casos": casos,
                    "aprovados": aprovados,
                    "total_avaliados": len(validas),
                    "taxa_aprovacao": taxa,
                    "taxa_aprovacao_pct": f"{taxa:.0%}",
                }
            )
            return

        if rota.startswith("/arquivos/"):
            rel = urllib.parse.unquote(rota[len("/arquivos/"):]).lstrip("/")
            alvo = (RAIZ / rel).resolve()
            # Proteção contra path traversal: só permite servir arquivos de dados/originais/ ou resultados/
            originais_dir = (RAIZ / "dados" / "originais").resolve()
            resultados_dir = (RAIZ / "resultados").resolve()
            if (originais_dir in alvo.parents or resultados_dir in alvo.parents) and alvo.is_file():
                tipo_mime, _ = mimetypes.guess_type(str(alvo))
                conteudo = alvo.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", tipo_mime or "application/octet-stream")
                self.send_header("Content-Length", str(len(conteudo)))
                self.end_headers()
                self.wfile.write(conteudo)
                return
            self._enviar_json({"erro": "Arquivo não encontrado ou acesso negado."}, status=HTTPStatus.NOT_FOUND)
            return

        self._enviar_json({"erro": "Rota não encontrada."}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        rota = urllib.parse.urlparse(self.path).path
        if rota == "/api/revisar":
            tamanho = int(self.headers.get("Content-Length", "0") or "0")
            bruto = self.rfile.read(tamanho).decode("utf-8") if tamanho > 0 else "{}"
            try:
                payload = json.loads(bruto)
                atualizado = registrar_revisao_web(
                    caso_id=payload.get("caso_id", ""),
                    decisao=payload.get("decisao", "Aprovada"),
                    revisor_nome=payload.get("revisor_nome", ""),
                    revisor_cargo=payload.get("revisor_cargo", ""),
                    justificativa=payload.get("justificativa", ""),
                    texto_minuta_editado=payload.get("texto_minuta_editado"),
                    nova_geracao=bool(payload.get("nova_geracao", False)),
                    dry_run_padrao=self.dry_run_padrao,
                )
                self._enviar_json({"status": "ok", "caso": atualizado})
            except Exception as e:
                self._enviar_json({"erro": str(e)}, status=HTTPStatus.BAD_REQUEST)
            return

        self._enviar_json({"erro": "Rota POST inválida."}, status=HTTPStatus.NOT_FOUND)


def iniciar_interface_web(host: str = "127.0.0.1", porta: int = 8000, abrir_navegador: bool = True, dry_run: bool = True) -> None:
    """Inicia o servidor web local para revisão humana lado a lado."""
    ManipuladorWebRevisao.dry_run_padrao = dry_run
    servidor = ThreadingHTTPServer((host, porta), ManipuladorWebRevisao)
    url = f"http://{host}:{porta}"
    print(f"\n[WEB] Interface de Revisão Humana disponível em: {url}")
    print("[WEB] Pressione Ctrl+C para encerrar o servidor.")
    if abrir_navegador:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\n[WEB] Servidor encerrado pelo operador.")
    finally:
        servidor.server_close()
