"""Testes unitários offline de abstração de provedor, orçamento, auditoria D2, revisão e regressão (RF14, RF16, RF21, RF23, RF24).

Cobre os cenários da matriz:
- T12 (RF21): troca de configuração de geração sem reconstruir o índice + falha de serviço tratada e auditada;
- RF16 / RF21: limite de orçamento (`ControladorOrcamento`), mascaramento de identificadores/protocolos na consulta
  auditada e status explícito quando custo não está disponível localmente;
- RF24: persistência de `DecisaoRevisao` (`aprovada`, `rejeitada`, `revisar`) com `enviada_ao_cidadao=False`;
- RF14 / T15: bloqueio antes da minuta em solicitações retidas, liberação formal pós-triagem e regressão
  ponta a ponta offline de caso textual (`caso01_texto`) e multimodal (`caso02_audio`).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import audit, embeddings, llm_client, main, rag
from src.llm_client import ErroProvedor


class TestAdaptadoresProvedorEOrcamento(unittest.TestCase):
    """Valida T12 (RF21) e controle de orçamento por execução (RF16)."""

    def test_troca_adaptador_geracao_nao_reconstroi_indice_e_trata_falha(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            dir_idx = raiz_tmp / "indice"
            log_tmp = raiz_tmp / "execucoes.jsonl"

            idx = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embeddings.EmbeddingsDeterministicoTeste(dimensao=64),
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            idx.indexar_acervo()
            versao_antes = idx.versao_indice
            mtime_antes = idx.caminho_faiss.stat().st_mtime_ns

            achados_previos = idx.buscar("Qual o prazo da declaração de matrícula?", top_k=4)
            cid_primeiro = achados_previos[0].trecho.chunk_id
            payload_ok = json.dumps(
                {
                    "status": "fundamentada",
                    "resposta": "A declaração de matrícula é emitida conforme o procedimento institucional.",
                    "afirmacoes": [
                        {
                            "texto": "Emissão conforme procedimento institucional.",
                            "chunk_ids": [cid_primeiro],
                        }
                    ],
                    "requer_revisao": False,
                    "motivo_revisao": None,
                },
                ensure_ascii=False,
            )

            resp_http = MagicMock()
            resp_http.status_code = 200
            resp_http.json.return_value = {
                "model": "openai/gpt-oss-120b",
                "choices": [{"message": {"content": payload_ok}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280},
            }

            with patch.dict(os.environ, {"GROQ_API_KEY": "chave_ficticia_teste"}), patch(
                "src.llm_client.httpx.post", return_value=resp_http
            ):
                adp_1 = llm_client.criar_adaptador_geracao(main.CONFIG)
                adp_2 = llm_client.criar_adaptador_geracao(main.CONFIG, usar_secundaria=True)
                adp_sim = llm_client.criar_adaptador_geracao(main.CONFIG, usar_contingencia_simulada=True)

                r1 = rag.consultar_acervo(
                    "Qual o prazo da declaração de matrícula?", indice=idx, adaptador=adp_1, caminho_log=log_tmp
                )
                r2 = rag.consultar_acervo(
                    "Qual o prazo da declaração de matrícula?", indice=idx, adaptador=adp_2, caminho_log=log_tmp
                )
                r3 = rag.consultar_acervo(
                    "Qual o prazo da declaração de matrícula?", indice=idx, adaptador=adp_sim, caminho_log=log_tmp
                )

            self.assertEqual(r1.modelo, "openai/gpt-oss-120b")
            self.assertEqual(r2.modelo, "openai/gpt-oss-20b")
            self.assertTrue(r3.simulado)
            self.assertTrue(r3.resposta_rag["requer_revisao"])
            self.assertEqual(r3.meta["uso_total"]["metrica_custo_status"], "indisponivel_execucao_local_simulada")

            # Simula falha HTTP 503 esgotando a única repetição transitória (tentativas_transitorias=2)
            resp_503 = MagicMock()
            resp_503.status_code = 503
            resp_503.headers = {}
            resp_503.text = "Service Unavailable gsk_SegredoFicticioJamaisExposto123456"

            with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_SegredoFicticioJamaisExposto123456"}), patch(
                "src.llm_client.httpx.post", return_value=resp_503
            ) as mock_503:
                adp_falha = llm_client.criar_adaptador_geracao(main.CONFIG)
                adp_falha.pausa_base_s = 0.0
                r_err = rag.consultar_acervo(
                    "Pergunta com falha de serviço", indice=idx, adaptador=adp_falha, caminho_log=log_tmp
                )
                self.assertEqual(mock_503.call_count, 2)  # 1 chamada + no máximo 1 repetição transitória
                self.assertEqual(r_err.estado, "erro_provedor")
                self.assertTrue(r_err.resposta_rag["requer_revisao"])

            # Verifica que o índice vetorial jamais foi reconstruído ou tocado na troca de geração
            self.assertEqual(idx.versao_indice, versao_antes)
            self.assertEqual(idx.caminho_faiss.stat().st_mtime_ns, mtime_antes)
            self.assertNotIn("gsk_SegredoFicticioJamaisExposto123456", log_tmp.read_text(encoding="utf-8"))

    def test_controlador_orcamento_bloqueia_excesso_de_chamadas_e_tokens(self):
        orc = llm_client.ControladorOrcamento(max_chamadas=1, max_tokens_total=500)
        orc.verificar_disponibilidade()
        orc.registrar_chamada(110)
        with self.assertRaises(ErroProvedor) as ctx:
            orc.verificar_disponibilidade()
        self.assertEqual(ctx.exception.codigo_erro, "limite_chamadas_excedido")

        orc2 = llm_client.ControladorOrcamento(max_chamadas=5, max_tokens_total=100)
        orc2.registrar_chamada(110)
        with self.assertRaises(ErroProvedor) as ctx2:
            orc2.verificar_disponibilidade()
        self.assertEqual(ctx2.exception.codigo_erro, "limite_tokens_excedido")


class TestAuditoriaMascaramentoERevisao(unittest.TestCase):
    """Valida mascaramento de identificadores na auditoria (RF21) e estados de revisão (RF24)."""

    def test_mascara_cpf_email_protocolo_e_segredo_no_log_rf21(self):
        consulta_sensivel = (
            "Consulta do CPF 123.456.789-00, protocolo 2026-000142, "
            "e-mail aluno.ficticio@exemplo.com e chave gsk_SegredoFalsoDeTeste123456789"
        )
        with tempfile.TemporaryDirectory() as tmp:
            log_tmp = Path(tmp) / "execucoes.jsonl"
            reg = audit.criar_registro(
                caso_id="teste_rf21",
                etapa="consulta_rag",
                modalidade="texto",
                arquivo_origem="consulta_direta",
                provedor="ollama",
                modelo="llama3.2",
                resposta_llm={"latencia_s": 0.42, "tokens_entrada": None, "tokens_saida": None, "custo_usd": None},
                consulta=consulta_sensivel,
                ids_recuperados=["ACV-01#c1", "ACV-01#c2"],
                versao_indice="idx-teste123",
                versao_esquema="resposta_rag-v0.1.0",
            )
            audit.registrar_execucao(reg, caminho_log=log_tmp)
            bruto = log_tmp.read_text(encoding="utf-8")
            self.assertNotIn("123.456.789-00", bruto)
            self.assertNotIn("2026-000142", bruto)
            self.assertNotIn("aluno.ficticio@exemplo.com", bruto)
            self.assertNotIn("gsk_SegredoFalsoDeTeste123456789", bruto)
            lido = audit.ler_registros(log_tmp)[0]
            self.assertIn("[PROTOCOLO_MASCARADO]", lido["consulta"])
            self.assertEqual(lido["ids_recuperados"], ["ACV-01#c1", "ACV-01#c2"])
            self.assertEqual(lido["versao_indice"], "idx-teste123")
            self.assertEqual(lido["metrica_custo_status"], "indisponivel_execucao_local")

    def test_estados_revisao_aprovada_rejeitada_e_revisar_sem_envio_automatico(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            log_tmp = raiz_tmp / "execucoes.jsonl"
            caminhos_tmp = {
                **main.CONFIG["caminhos"],
                "processados": str(raiz_tmp / "processados"),
                "minutas": str(raiz_tmp / "minutas"),
            }
            with patch.dict(main.CONFIG, {"caminhos": caminhos_tmp}):
                main.processar_caso(
                    caso_id="caso01_texto",
                    provedor="groq",
                    modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"],
                    dry_run=True,
                    nao_interativo=False,
                    caminho_log=log_tmp,
                )
                with self.assertRaises(Exception):
                    main.registrar_decisao_revisao_minuta(
                        "caso01_texto",
                        estado="aprovada",
                        revisor="",
                        justificativa="",
                        caminho_log=log_tmp,
                    )

                dec_aprov = main.registrar_decisao_revisao_minuta(
                    "caso01_texto",
                    estado="aprovada",
                    revisor="Servidor Fictício Revisão",
                    justificativa="Citações de ACV-01 conferidas integralmente.",
                    caminho_log=log_tmp,
                )
                self.assertEqual(dec_aprov["estado"], "aprovada")
                self.assertFalse(dec_aprov["enviada_ao_cidadao"])

                dec_rej = main.registrar_decisao_revisao_minuta(
                    "caso01_texto",
                    estado="rejeitada",
                    revisor="Servidor Fictício Revisão",
                    justificativa="Solicitada complementação manual antes de aprovar.",
                    caminho_log=log_tmp,
                )
                self.assertEqual(dec_rej["estado"], "rejeitada")
                self.assertFalse(dec_rej["enviada_ao_cidadao"])

                texto_pdf = main.ler_texto_minuta_pdf(raiz_tmp / "minutas" / "caso01_texto_minuta.pdf")
                self.assertIn("ENVIO AUTOMÁTICO BLOQUEADO", texto_pdf)
                self.assertIn("Status: **Rejeitada**", texto_pdf)


class TestFluxoIntegradoERegressao(unittest.TestCase):
    """Valida bloqueio pré-minuta (RF14) e regressão offline texto + áudio confirmado (T15)."""

    def test_bloqueia_caso_ambiguo_antes_da_minuta_e_permite_liberacao_auditada(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            log_tmp = raiz_tmp / "execucoes.jsonl"
            caminhos_tmp = {
                **main.CONFIG["caminhos"],
                "processados": str(raiz_tmp / "processados"),
                "minutas": str(raiz_tmp / "minutas"),
            }
            with patch.dict(main.CONFIG, {"caminhos": caminhos_tmp}):
                res_retido = main.processar_caso(
                    caso_id="caso09_texto_ambiguo",
                    provedor="groq",
                    modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"],
                    dry_run=True,
                    nao_interativo=True,
                    caminho_log=log_tmp,
                )
                self.assertTrue(res_retido["bloqueado_antes_minuta"])
                self.assertEqual(res_retido["encaminhamento"], "revisao_humana_antes_da_minuta")
                self.assertIsNone(res_retido["minuta"])
                self.assertFalse((raiz_tmp / "minutas" / "caso09_texto_ambiguo_minuta.pdf").exists())

                res_liberado = main.processar_caso(
                    caso_id="caso09_texto_ambiguo",
                    provedor="groq",
                    modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"],
                    dry_run=True,
                    nao_interativo=False,
                    caminho_log=log_tmp,
                    liberar_apos_triagem={
                        "categoria": "matricula",
                        "revisor": "Servidor Triagem",
                        "justificativa": "Conferido no sistema acadêmico que a pendência é documental.",
                    },
                )
                self.assertFalse(res_liberado["bloqueado_antes_minuta"])
                self.assertTrue((raiz_tmp / "minutas" / "caso09_texto_ambiguo_minuta.pdf").exists())

    def test_regressao_t15_texto_e_audio_confirmado_com_rag_mockado(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            log_tmp = raiz_tmp / "execucoes.jsonl"
            dir_idx = raiz_tmp / "indice"
            idx = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embeddings.EmbeddingsDeterministicoTeste(dimensao=64),
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            idx.indexar_acervo()
            adp_sim = llm_client.criar_adaptador_geracao(main.CONFIG, usar_contingencia_simulada=True)

            ext_valida = json.dumps(
                {
                    "protocolo": "2026-000142",
                    "data_solicitacao": "14/10/2026",
                    "canal": None,
                    "solicitante": "Marcos Vinícius de Almeida Santos",
                    "curso": "Técnico em Enfermagem",
                    "assunto": "Efetivação de matrícula e documentos pendentes",
                    "pedido": "Efetivação da matrícula e informação sobre documentos pendentes.",
                    "categoria": "matricula",
                    "entidades": [
                        {
                            "tipo": "protocolo",
                            "valor": "2026-000142",
                            "origem": "literal",
                            "evidencia": "2026-000142",
                        }
                    ],
                    "dados_pessoais_detectados": ["CPF"],
                    "campos_ausentes": ["canal"],
                    "requer_revisao": False,
                    "motivos_revisao": [],
                    "alertas_seguranca": [],
                },
                ensure_ascii=False,
            )
            resumo_valido = json.dumps(
                {
                    "resumo": "Solicitante pede efetivação de matrícula no curso Técnico em Enfermagem sob protocolo 2026-000142.",
                    "fatos": [
                        {
                            "afirmacao": "Informa protocolo 2026-000142.",
                            "evidencia": "2026-000142",
                        }
                    ],
                },
                ensure_ascii=False,
            )

            caminhos_tmp = {
                **main.CONFIG["caminhos"],
                "processados": str(raiz_tmp / "processados"),
                "minutas": str(raiz_tmp / "minutas"),
            }
            cfg_rapida = {**main.CONFIG["producao"], "pausa_entre_chamadas_s": 0}

            with patch.dict(main.CONFIG, {"caminhos": caminhos_tmp}), patch(
                "src.llm_client.chamar_chat",
                side_effect=[
                    {"texto": ext_valida, "latencia_s": 0.1, "tokens_entrada": 100, "tokens_saida": 50, "custo_usd": 0.0001},
                    {"texto": resumo_valido, "latencia_s": 0.1, "tokens_entrada": 100, "tokens_saida": 40, "custo_usd": 0.0001},
                    {"texto": ext_valida, "latencia_s": 0.1, "tokens_entrada": 100, "tokens_saida": 50, "custo_usd": 0.0001},
                    {"texto": resumo_valido, "latencia_s": 0.1, "tokens_entrada": 100, "tokens_saida": 40, "custo_usd": 0.0001},
                ],
            ):
                for cid in ("caso01_texto", "caso02_audio"):
                    out = main.processar_caso(
                        caso_id=cid,
                        provedor="groq",
                        modelo="openai/gpt-oss-120b",
                        cfg_prod=cfg_rapida,
                        dry_run=False,
                        nao_interativo=True,
                        caminho_log=log_tmp,
                        indice_rag=idx,
                        adaptador_rag=adp_sim,
                    )
                    self.assertFalse(out["bloqueado_antes_minuta"])
                    self.assertEqual(out["decisao_humana"], "PENDENTE")
                    self.assertIsNotNone(out["ficha"])
                    self.assertIsNotNone(out["resposta_rag"])
                    self.assertTrue((raiz_tmp / "minutas" / f"{cid}_minuta.pdf").is_file())


if __name__ == "__main__":
    unittest.main()
