"""Testes automatizados offline do cliente de API, auditoria e fluxo de atendimento (RF01, RF04, RF05, RF09, RF11, RF12, RF13).

Não realizam chamadas de rede reais.
Executar: python -m unittest discover -s testes -t .
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx

from src import audit, llm_client, main, prompts
from src.llm_client import ErroProvedor


class TestClienteAPI(unittest.TestCase):
    """Testa chamadas de API, tratamento de falhas e proteção de credenciais (RF04)."""

    perfil_teste = {
        "base_url": "https://api.exemplo.local/v1",
        "env_chave": "CHAVE_TESTE_FICTICIA_API_KEY",
    }

    def test_chave_ausente_gera_erro_compreensivel(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CHAVE_TESTE_FICTICIA_API_KEY", None)
            with self.assertRaises(ErroProvedor) as ctx:
                llm_client.verificar_chave(self.perfil_teste)
            self.assertEqual(ctx.exception.codigo_erro, "chave_ausente")
            self.assertIn("CHAVE_TESTE_FICTICIA_API_KEY", str(ctx.exception))

    def test_provedor_local_nao_exige_chave(self):
        self.assertEqual(
            llm_client.verificar_chave({"base_url": "http://localhost:11434/v1", "env_chave": None}),
            "local",
        )

    def test_ocultar_segredos_remove_chaves_e_bearer(self):
        chave_falsa = "gsk_ChaveFicticiaDeTesteSegura123456"
        with patch.dict(os.environ, {"CHAVE_TESTE_FICTICIA_API_KEY": chave_falsa}):
            texto = f"Erro com Authorization: Bearer {chave_falsa} e chave direta {chave_falsa}"
            limpo = llm_client.ocultar_segredos(texto)
            self.assertNotIn(chave_falsa, limpo)
            self.assertIn("[CREDENCIAL_OCULTADA]", limpo)

    @patch("src.llm_client.httpx.post")
    def test_autenticacao_invalida_401_falha_sem_retentativa(self, mock_post):
        resposta_401 = MagicMock()
        resposta_401.status_code = 401
        resposta_401.text = "Invalid API key gsk_SegredoFalso9999999999"
        mock_post.return_value = resposta_401

        with patch.dict(os.environ, {"CHAVE_TESTE_FICTICIA_API_KEY": "gsk_SegredoFalso9999999999"}):
            with self.assertRaises(ErroProvedor) as ctx:
                llm_client.chamar_chat(
                    self.perfil_teste,
                    "modelo-x",
                    [{"role": "user", "content": "oi"}],
                    {"temperature": 0.2},
                    tentativas=3,
                    pausa_base_s=0,
                )
            self.assertEqual(ctx.exception.codigo_erro, "autenticacao_invalida")
            self.assertEqual(mock_post.call_count, 1)
            self.assertNotIn("gsk_SegredoFalso9999999999", str(ctx.exception))

    @patch("src.llm_client.httpx.post")
    def test_rate_limit_429_faz_retry_e_calcula_custo(self, mock_post):
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.headers = {"retry-after": "0"}

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "model": "openai/gpt-oss-120b",
            "choices": [{"message": {"content": '{"status": "ok"}'}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
        }
        mock_post.side_effect = [resp_429, resp_200]
        precos = {"openai/gpt-oss-120b": {"entrada": 0.15, "saida": 0.60}}

        with patch.dict(os.environ, {"CHAVE_TESTE_FICTICIA_API_KEY": "chave_ficticia_teste"}):
            res = llm_client.chamar_chat(
                self.perfil_teste,
                "openai/gpt-oss-120b",
                [{"role": "user", "content": "teste"}],
                {"temperature": 0.2},
                tentativas=3,
                json_mode=True,
                precos=precos,
                pausa_base_s=0,
            )
        self.assertEqual(res["tentativas"], 2)
        self.assertEqual(res["texto"], '{"status": "ok"}')
        self.assertEqual(res["tokens_entrada"], 1000)
        self.assertEqual(res["tokens_saida"], 500)
        self.assertAlmostEqual(res["custo_usd"], 0.00045, places=6)

    @patch("src.llm_client.httpx.post")
    def test_timeout_e_resposta_vazia_tratados(self, mock_post):
        mock_post.side_effect = httpx.TimeoutException("timeout")
        with patch.dict(os.environ, {"CHAVE_TESTE_FICTICIA_API_KEY": "chave_ficticia_teste"}):
            with self.assertRaises(ErroProvedor) as ctx:
                llm_client.chamar_chat(
                    self.perfil_teste,
                    "modelo-x",
                    [{"role": "user", "content": "teste"}],
                    {},
                    tentativas=2,
                    pausa_base_s=0,
                )
            self.assertEqual(ctx.exception.codigo_erro, "timeout")

        resp_vazia = MagicMock()
        resp_vazia.status_code = 200
        resp_vazia.json.return_value = {"choices": [{"message": {"content": "   "}}]}
        mock_post.side_effect = None
        mock_post.return_value = resp_vazia
        with patch.dict(os.environ, {"CHAVE_TESTE_FICTICIA_API_KEY": "chave_ficticia_teste"}):
            with self.assertRaises(ErroProvedor) as ctx2:
                llm_client.chamar_chat(
                    self.perfil_teste,
                    "modelo-x",
                    [{"role": "user", "content": "teste"}],
                    {},
                    tentativas=2,
                    pausa_base_s=0,
                )
            self.assertEqual(ctx2.exception.codigo_erro, "resposta_vazia")


class TestRegistroAuditoria(unittest.TestCase):
    """Testa registro estruturado, rastreabilidade, versões e sanitização de logs (RF01, RF11, RF13)."""

    def test_coletar_ambiente_registra_python_e_bibliotecas(self):
        amb = audit.coletar_ambiente()
        self.assertTrue(amb["python"].startswith("3."))
        self.assertIn("httpx", amb["bibliotecas"])
        self.assertIn("python-dotenv", amb["bibliotecas"])

    def test_registro_estruturado_nao_armazena_credenciais(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho_log = Path(tmp) / "execucoes.jsonl"
            caminho_rel = Path(tmp) / "relatorio.md"
            segredo_falso = "gsk_SegredoSuperSensivel123456789"
            reg = audit.criar_registro(
                id_execucao="exec-teste01",
                caso_id="caso01_texto",
                etapa="minuta",
                modalidade="texto",
                arquivo_origem="dados/originais/entrada_texto.txt",
                provedor="groq",
                modelo="openai/gpt-oss-120b",
                parametros={"temperature": 0.2, "api_key": segredo_falso},
                versao_prompt="minuta-v1.0",
                hash_prompt="abc123456789",
                dados_minimizados={"CPF": 1},
                resposta_llm={"latencia_s": 1.5, "tokens_entrada": 100, "tokens_saida": 50, "custo_usd": 0.000045},
                arquivo_saida="resultados/minutas/caso01_texto_minuta.md",
                resumo_resultado=f"Teste com tentativa de vazar {segredo_falso}",
                decisao_humana="PENDENTE",
            )
            audit.registrar_execucao(reg, caminho_log=caminho_log)
            audit.atualizar_decisao_humana(
                "exec-teste01",
                decisao="Aprovada",
                revisor="Servidor Teste",
                justificativa="Conferido com sucesso.",
                caminho_log=caminho_log,
            )

            conteudo_bruto = caminho_log.read_text(encoding="utf-8")
            self.assertNotIn(segredo_falso, conteudo_bruto)
            registros = audit.ler_registros(caminho_log)
            self.assertEqual(len(registros), 1)
            self.assertEqual(registros[0]["decisao_humana"], "Aprovada")
            self.assertEqual(registros[0]["revisor"], "Servidor Teste")
            self.assertEqual(registros[0]["parametros"]["api_key"], "[CREDENCIAL_OCULTADA]")

            md = audit.gerar_relatorio_auditoria(caminho_log=caminho_log, caminho_relatorio=caminho_rel)
            self.assertIn("100%", md)
            self.assertNotIn(segredo_falso, md)


class TestFluxoAtendimento(unittest.TestCase):
    """Testa extração estruturada com campos ausentes, minuta e execução dry-run (RF05, RF09, RF13)."""

    def test_normalizar_extracao_mantem_json_valido_com_campos_ausentes(self):
        parcial = {"solicitante": "Carlos Eduardo Nunes", "categoria": "inexistente"}
        norm = main.normalizar_extracao(
            dados_brutos=parcial,
            texto_original="Texto original de teste",
            arquivo_origem="dados/originais/caso05_texto_incompleto.txt",
            dados_minimizados={},
        )
        # Garante que serializa como JSON válido e marca campos ausentes como 'não localizado' (RF05)
        serializado = json.loads(json.dumps(norm, ensure_ascii=False))
        self.assertEqual(serializado["protocolo"], prompts.NAO_LOCALIZADO)
        self.assertEqual(serializado["data_solicitacao"], prompts.NAO_LOCALIZADO)
        self.assertEqual(serializado["solicitante"], "Carlos Eduardo Nunes")
        self.assertIn("protocolo", serializado["campos_ausentes"])
        self.assertIn("data_solicitacao", serializado["campos_ausentes"])
        self.assertEqual(serializado["confianca"], "baixa")
        self.assertTrue(serializado["requer_revisao_humana"])
        self.assertEqual(serializado["texto_original_preservado"], "Texto original de teste")

    def test_processar_caso_dry_run_bloqueia_envio_e_preserva_originais(self):
        caminho_original = prompts.RAIZ / "dados/originais/entrada_texto.txt"
        hash_antes = prompts.hash_texto(caminho_original.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            tmp_rel = Path(tmp)
            log_temp = tmp_rel / "execucoes.jsonl"
            caminhos_temp = {
                **main.CONFIG["caminhos"],
                "processados": str(tmp_rel / "processados"),
                "minutas": str(tmp_rel / "minutas"),
            }
            with patch.dict(main.CONFIG, {"caminhos": caminhos_temp}):
                res = main.processar_caso(
                    caso_id="caso01_texto",
                    provedor="groq",
                    modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"],
                    dry_run=True,
                    nao_interativo=True,
                    caminho_log=log_temp,
                )
                self.assertEqual(res["decisao_humana"], "Corrigida")
                arq_minuta = tmp_rel / "minutas" / "caso01_texto_minuta.md"
                self.assertTrue(arq_minuta.exists())
                texto_minuta = arq_minuta.read_text(encoding="utf-8")
                self.assertIn("ENVIO AUTOMÁTICO BLOQUEADO", texto_minuta)
                self.assertIn("Status: **Corrigida**", texto_minuta)

        hash_depois = prompts.hash_texto(caminho_original.read_text(encoding="utf-8"))
        self.assertEqual(hash_antes, hash_depois)


if __name__ == "__main__":
    unittest.main()
