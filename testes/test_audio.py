"""RF06: testes offline de transcrição, evidências e bloqueio antes da revisão."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from src import audio, main
from src.llm_client import ErroProvedor


class TestAudio(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.patch_raiz = patch.object(audio, "RAIZ", self.raiz)
        self.patch_raiz.start()
        self.addCleanup(self.patch_raiz.stop)
        self.config = copy.deepcopy(main.CONFIG)
        self.config["transcricao"]["pausa_base_s"] = 0
        self.log = self.raiz / "resultados/logs/teste.jsonl"
        self.origem = self.raiz / "dados/originais/voz.mp3"
        self.origem.parent.mkdir(parents=True)
        self.origem.write_bytes(b"audio ficticio para testes HTTP simulados")
        self.chave = patch("src.audio.verificar_chave", return_value="credencial-ficticia")
        self.chave.start()
        self.addCleanup(self.chave.stop)

    def resposta(self, status=200, dados=None, **kwargs):
        return httpx.Response(status, json=dados if dados is not None else {
            "text": "Olá. Meu protocolo é 2026-000142.", "language": "portuguese", "duration": 8.0,
            "segments": [{"start": 0, "end": 8, "text": "Olá."}],
        }, **kwargs)

    def transcrever(self):
        return audio.transcrever_audio(self.origem, config=self.config, caminho_log=self.log)

    def test_validacao_antes_da_rede(self):
        with patch("src.audio.httpx.post") as post:
            for caminho, limite in [(self.origem.with_suffix(".txt"), 100), (self.origem, 1)]:
                with self.subTest(caminho=caminho), self.assertRaises(ValueError):
                    audio.validar_audio(caminho, limite)
            self.origem.write_bytes(b"")
            with self.assertRaises(ValueError):
                self.transcrever()
            post.assert_not_called()

    def test_extensao_nao_suportada(self):
        arquivo = self.raiz / "arquivo.txt"
        arquivo.write_text("conteudo")
        with self.assertRaisesRegex(ValueError, "Extensão"):
            audio.validar_audio(arquivo, 100)

    def test_envia_audio_sem_gabarito_e_preserva_evidencias(self):
        gab_dir = self.raiz / "dados/gabaritos"
        gab_dir.mkdir()
        (gab_dir / "referencia.txt").write_text("NAO_ENVIAR_AO_MODELO", encoding="utf-8")
        (gab_dir / "caso02_audio.json").write_text(json.dumps({
            "arquivo_origem": "dados/originais/voz.mp3",
            "transcricao_referencia": "dados/gabaritos/referencia.txt",
        }))
        original = self.origem.read_bytes()
        def verificar_upload(*args, **kwargs):
            self.assertEqual(kwargs["files"]["file"][1].read(), original)
            self.assertEqual(kwargs["data"]["response_format"], "verbose_json")
            self.assertNotIn("prompt", kwargs["data"])
            self.assertNotIn("NAO_ENVIAR_AO_MODELO", str(kwargs["data"]))
            return self.resposta()
        with patch("src.audio.httpx.post", side_effect=verificar_upload):
            res = self.transcrever()
        pasta = (self.raiz / res["arquivo_metadados"]).parent
        self.assertEqual(self.origem.read_bytes(), original)
        self.assertEqual((pasta / "bruta.txt").read_text(encoding="utf-8"), res["texto"])
        self.assertEqual((pasta / "revisada.txt").read_bytes(), (pasta / "bruta.txt").read_bytes())
        self.assertTrue((pasta / "comparacao.json").exists())
        self.assertEqual(res["decisao_humana"], "PENDENTE")
        self.assertEqual(res["duracao_audio_s"], 8)
        self.assertAlmostEqual(res["custo_usd"], 10 / 3600 * .111, places=6)
        self.assertNotIn("credencial-ficticia", self.log.read_text())

    def test_erros_http_sem_retentativa(self):
        for status, codigo in [(401, "autenticacao_invalida"), (403, "autenticacao_invalida"),
                               (400, "requisicao_invalida"), (413, "requisicao_invalida")]:
            with self.subTest(status=status), patch("src.audio.httpx.post", return_value=self.resposta(status)) as post:
                with self.assertRaises(ErroProvedor) as ctx:
                    self.transcrever()
                self.assertEqual(ctx.exception.codigo_erro, codigo)
                self.assertEqual(post.call_count, 1)
        self.assertIn("HTTP 413", self.log.read_text())

    def test_retry_reabre_audio(self):
        leituras = []
        respostas = iter([self.resposta(429, headers={"retry-after": "0"}), self.resposta(503), self.resposta()])
        def responder(*args, **kwargs):
            leituras.append(kwargs["files"]["file"][1].read())
            return next(respostas)
        with patch("src.audio.httpx.post", side_effect=responder):
            res = self.transcrever()
        self.assertEqual(res["tentativas"], 3)
        self.assertEqual(leituras, [self.origem.read_bytes()] * 3)

    def test_timeout_rede_e_respostas_invalidas(self):
        for efeito in [httpx.TimeoutException("segredo"), httpx.ConnectError("segredo")]:
            with patch("src.audio.httpx.post", side_effect=efeito) as post:
                with self.assertRaises(ErroProvedor) as ctx:
                    self.transcrever()
                self.assertNotIn("segredo", str(ctx.exception))
                self.assertEqual(post.call_count, 3)
        for dados in [{}, [], {"text": "", "duration": 1, "language": "pt"},
                      {"text": "oi", "duration": -1, "language": "pt"}]:
            with self.subTest(dados=dados), patch("src.audio.httpx.post", return_value=self.resposta(dados=dados)):
                with self.assertRaises(ErroProvedor):
                    self.transcrever()

    def test_chave_ausente_nao_chama_rede(self):
        with patch("src.audio.verificar_chave", side_effect=ErroProvedor("Chave ausente", "chave_ausente")), \
                patch("src.audio.httpx.post") as post:
            with self.assertRaises(ErroProvedor):
                self.transcrever()
            post.assert_not_called()

    def test_revisao_explicita_e_invalidacao_por_mudanca(self):
        with patch("src.audio.httpx.post", return_value=self.resposta()):
            res = self.transcrever()
        pasta = (self.raiz / res["arquivo_metadados"]).parent
        def obter():
            return audio.obter_transcricao_confirmada(self.origem, caso_id="caso02_audio", config=self.config)
        with self.assertRaisesRegex(ValueError, "sem transcrição confirmada"):
            obter()
        with self.assertRaises(ValueError):
            audio.confirmar_revisao(pasta, "Revisor fictício", "Ouvido", campos_confirmados=False, caminho_log=self.log)
        (pasta / "revisada.txt").write_text("Texto corrigido pelo revisor.", encoding="utf-8")
        audio.confirmar_revisao(pasta, "Revisor fictício", "Ouvi e conferi os dados críticos.",
                               campos_confirmados=True, caminho_log=self.log)
        self.assertEqual(obter()["texto"], "Texto corrigido pelo revisor.")
        (pasta / "revisada.txt").write_text("Modificado depois da aprovação.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "alterada"):
            obter()
        self.origem.write_bytes(b"outro audio")
        with self.assertRaisesRegex(ValueError, "sem transcrição confirmada"):
            obter()

    def test_impede_aprovar_bruta_modificada(self):
        with patch("src.audio.httpx.post", return_value=self.resposta()):
            res = self.transcrever()
        pasta = (self.raiz / res["arquivo_metadados"]).parent
        (pasta / "bruta.txt").write_text("alterada")
        with self.assertRaisesRegex(ValueError, "bruta foi alterada"):
            audio.confirmar_revisao(pasta, "Revisor fictício", "Conferido", campos_confirmados=True, caminho_log=self.log)

    def test_comparacao_destaca_erro_de_protocolo(self):
        res = audio.comparar_transcricao("Olá protocolo 456", "TRANCRIÇÃO DO ARQUIVO\n= =\nOlá protocolo 123\n= =",
                                        {"numeros_de_protocolo": ["123"]})
        self.assertEqual(res["distancia_edicao"], 1)
        self.assertEqual(res["palavras_referencia"], 3)
        self.assertFalse(res["campos_criticos"][0]["correspondencia_textual"])
        self.assertTrue(res["campos_criticos"][0]["requer_conferencia_humana"])
        self.assertIsNone(audio.comparar_transcricao("oi", "")["wer"])

    def test_comparacao_literal_preserva_erro_no_email(self):
        res = audio.comparar_transcricao("teste.exemplo.com", "teste@exemplo.com")
        self.assertEqual(res["wer"], 0)
        self.assertEqual(res["diferencas_literais"][0]["referencia"], "teste@exemplo.com")
        self.assertEqual(res["diferencas_literais"][0]["obtido"], "teste.exemplo.com")

    def test_minuta_nova_nao_herda_aprovacao_do_exemplo(self):
        transcricao = {"texto": "Pedido fictício de matrícula.", "provedor": "groq", "modelo": "whisper-large-v3",
                      "arquivo_metadados": "resultados/transcricoes/teste/metadados.json",
                      "revisor": "Revisor fictício", "justificativa_humana": "Conferi o áudio.",
                      "id_execucao": "stt-teste", "sha256_origem": "hash-audio", "sha256_revisado": "hash-texto"}
        caminhos = {**main.CONFIG["caminhos"], "processados": str(self.raiz / "processados"),
                    "minutas": str(self.raiz / "minutas")}
        with patch.dict(main.CONFIG, {"caminhos": caminhos}), \
                patch("src.audio.obter_transcricao_confirmada", return_value=transcricao), \
                patch("src.llm_client.chamar_chat", return_value={"texto": "{}"}):
            res = main.processar_caso("caso02_audio", "groq", "modelo", main.CONFIG["producao"],
                                      nao_interativo=True, caminho_log=self.log)
        self.assertEqual(res["decisao_humana"], "PENDENTE")
        self.assertIn('"id_transcricao": "stt-teste"', self.log.read_text())

    def test_fluxo_real_nao_usa_gabarito_se_faltar_revisao(self):
        with patch("src.audio.obter_transcricao_confirmada", side_effect=ValueError("revisão pendente")), \
                patch("src.llm_client.chamar_chat") as chat:
            with self.assertRaisesRegex(ValueError, "revisão pendente"):
                main.processar_caso("caso02_audio", "groq", "modelo", main.CONFIG["producao"],
                                    caminho_log=self.log)
            chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()
