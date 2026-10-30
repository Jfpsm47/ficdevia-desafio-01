"""RF08: testes offline de OCR, mascaramento de assinatura e revisão humana."""
from __future__ import annotations

import base64
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image, ImageDraw

from src import main, vision
from src.llm_client import ErroProvedor


class TestVision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.raiz_patch = patch.object(vision, "RAIZ", self.raiz)
        self.raiz_patch.start()
        self.addCleanup(self.raiz_patch.stop)
        self.config = copy.deepcopy(main.CONFIG)
        self.config["visao"]["pausa_base_s"] = 0
        self.config["visao"]["mascara_assinatura"] = {"x": 0.0, "y": 0.67, "largura": 0.65, "altura": 0.14}
        self.log = self.raiz / "resultados/logs/teste.jsonl"
        self.origem = self.raiz / "dados/originais/ficha.png"
        self.origem.parent.mkdir(parents=True)
        imagem = Image.new("RGB", (200, 300), "black")
        ImageDraw.Draw(imagem).rectangle((5, 205, 120, 240), fill="red")
        imagem.save(self.origem)
        imagem.close()
        self.chave = patch("src.vision.verificar_chave", return_value="credencial-ficticia")
        self.chave.start()
        self.addCleanup(self.chave.stop)

    def resposta(self, status=200, dados=None, **kwargs):
        return httpx.Response(status, json=dados if dados is not None else {
            "model": "qwen/qwen3.8-27b",
            "choices": [{"message": {"content": "CÓDIGO: 2026-000142\nNOME: MARCOS"}}],
            "usage": {"prompt_tokens": 2000, "completion_tokens": 100},
        }, **kwargs)

    def extrair(self):
        return vision.extrair_texto(self.origem, config=self.config, caminho_log=self.log)

    def test_validacao_antes_da_rede(self):
        with patch("src.vision.httpx.post") as post:
            with self.assertRaises(ValueError):
                vision.validar_documento(self.origem.with_suffix(".txt"), 100)
            with self.assertRaises(ValueError):
                vision.validar_documento(self.origem, 1)
            self.origem.write_bytes(b"")
            with self.assertRaises(ValueError):
                self.extrair()
            post.assert_not_called()

    def test_mascara_assinatura_sem_alterar_origem(self):
        destino = self.raiz / "resultado.png"
        original = self.origem.read_bytes()
        meta = vision.renderizar_documento_mascarado(self.origem, destino, self.config["visao"])
        with Image.open(destino) as imagem:
            self.assertEqual(imagem.getpixel((10, 220)), (255, 255, 255))
            self.assertEqual(imagem.getpixel((150, 220)), (0, 0, 0))
        self.assertEqual(self.origem.read_bytes(), original)
        self.assertEqual(meta["retangulo_assinatura_mascarado"], [0, 201, 130, 243])
        self.assertTrue(meta["assinatura_omitida_do_envio"])

    def test_envia_somente_copia_mascarada_e_sem_gabarito(self):
        referencia = "VALOR_DO_GABARITO_NAO_ENVIAR"
        dados = self.raiz / "dados/gabaritos"
        dados.mkdir(parents=True)
        (dados / "caso03_ocr.json").write_text(json.dumps({
            "arquivo_origem": "dados/originais/ficha.png",
            "campos_esperados": {"codigo": referencia},
            "campos_criticos_para_confirmacao_humana": ["codigo"],
        }), encoding="utf-8")
        original = self.origem.read_bytes()
        def verificar(*args, **kwargs):
            corpo = kwargs["json"]
            self.assertNotIn(referencia, str(corpo))
            url = corpo["messages"][1]["content"][1]["image_url"]["url"]
            conteudo = base64.b64decode(url.split(",", 1)[1])
            self.assertNotEqual(conteudo, original)
            with Image.open(io.BytesIO(conteudo)) as imagem:
                self.assertEqual(imagem.getpixel((10, 220)), (255, 255, 255))
            return self.resposta()
        with patch("src.vision.httpx.post", side_effect=verificar):
            resultado = self.extrair()
        pasta = (self.raiz / resultado["arquivo_metadados"]).parent
        self.assertEqual(self.origem.read_bytes(), original)
        self.assertEqual((pasta / "bruta.txt").read_text(encoding="utf-8"), resultado["texto"])
        self.assertEqual((pasta / "revisada.txt").read_bytes(), (pasta / "bruta.txt").read_bytes())
        self.assertTrue((pasta / "comparacao.json").exists())
        self.assertEqual(resultado["decisao_humana"], "PENDENTE")
        self.assertAlmostEqual(resultado["custo_usd"], (2000 * .8 + 100 * 4) / 1_000_000, places=6)
        self.assertNotIn("credencial-ficticia", self.log.read_text())

    def test_erros_e_retentativas(self):
        for status, codigo in [(401, "autenticacao_invalida"), (403, "autenticacao_invalida"),
                               (400, "requisicao_invalida"), (413, "requisicao_invalida")]:
            with self.subTest(status=status), patch("src.vision.httpx.post", return_value=self.resposta(status)) as post:
                with self.assertRaises(ErroProvedor) as contexto:
                    self.extrair()
                self.assertEqual(contexto.exception.codigo_erro, codigo)
                self.assertEqual(post.call_count, 1)
        with patch("src.vision.httpx.post", side_effect=[self.resposta(429, headers={"retry-after": "0"}),
                                                           self.resposta(503), self.resposta()]) as post:
            resultado = self.extrair()
        self.assertEqual(resultado["tentativas"], 3)
        self.assertEqual(post.call_count, 3)

    def test_timeout_resposta_invalida_e_chave_ausente(self):
        for efeito in [httpx.TimeoutException("segredo"), httpx.ConnectError("segredo")]:
            with self.subTest(efeito=type(efeito).__name__), patch("src.vision.httpx.post", side_effect=efeito) as post:
                with self.assertRaises(ErroProvedor) as contexto:
                    self.extrair()
                self.assertNotIn("segredo", str(contexto.exception))
                self.assertEqual(post.call_count, 3)
        with patch("src.vision.httpx.post", return_value=self.resposta(dados={})):
            with self.assertRaises(ErroProvedor) as contexto:
                self.extrair()
            self.assertEqual(contexto.exception.codigo_erro, "resposta_invalida")
        with patch("src.vision.verificar_chave", side_effect=ErroProvedor("Chave ausente", "chave_ausente")), \
                patch("src.vision.httpx.post") as post:
            with self.assertRaises(ErroProvedor):
                self.extrair()
            post.assert_not_called()

    def test_comparacao_ocr_marca_campos_criticos_e_incertezas(self):
        comparacao = vision.comparar_ocr(
            "Código 2026-000142 CPF 123.456.789-00 curso técnico em enfermagem [ilegível]",
            {"codigo": "2026-000142", "cpf": "123.456.789-00", "curso": "TÉCNICO EM ENFERMAGEM",
             "rg": "em branco", "assinatura_aluno": "presente"},
            ["codigo", "cpf"], [{"campo": "cpf", "motivo": "difícil"}],
        )
        self.assertEqual(len(comparacao["campos"]), 3)
        self.assertEqual(len(comparacao["campos_criticos"]), 2)
        self.assertEqual(comparacao["trechos_ilegiveis_marcados"], 1)
        self.assertEqual(comparacao["campos_omitidos_do_envio"], ["assinatura_aluno", "assinatura_secretaria"])
        self.assertIn("Não enviada", comparacao["assinatura"])

    def test_revisao_explicita_e_invalidacao(self):
        with patch("src.vision.httpx.post", return_value=self.resposta()):
            resultado = self.extrair()
        pasta = (self.raiz / resultado["arquivo_metadados"]).parent
        def obter():
            return vision.obter_ocr_confirmado(self.origem, caso_id="caso03_ocr", config=self.config)
        with self.assertRaisesRegex(ValueError, "sem OCR confirmado"):
            obter()
        with self.assertRaises(ValueError):
            vision.confirmar_revisao(pasta, "Revisor fictício", "Revisei", campos_confirmados=False, caminho_log=self.log)
        (pasta / "revisada.txt").write_text("Texto corrigido pelo revisor.", encoding="utf-8")
        vision.confirmar_revisao(pasta, "Revisor fictício", "Conferi os campos críticos na ficha.",
                                 campos_confirmados=True, caminho_log=self.log)
        self.assertEqual(obter()["texto"], "Texto corrigido pelo revisor.")
        (pasta / "revisada.txt").write_text("Mudou depois da conferência.", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "alterado"):
            obter()

    def test_fluxo_real_bloqueia_sem_ocr_confirmado(self):
        with patch("src.vision.obter_ocr_confirmado", side_effect=ValueError("revisão pendente")), \
                patch("src.llm_client.chamar_chat") as chat:
            with self.assertRaisesRegex(ValueError, "revisão pendente"):
                main.processar_caso("caso03_ocr", "groq", "modelo", main.CONFIG["producao"], caminho_log=self.log)
            chat.assert_not_called()

    def test_minuta_nova_nao_herda_aprovacao_do_exemplo(self):
        resultado_ocr = {
            "texto": "Ficha fictícia conferida.", "provedor": "groq", "modelo": "qwen/qwen3.8-27b",
            "arquivo_metadados": "resultados/ocr/teste/metadados.json", "revisor": "Revisor fictício",
            "justificativa_humana": "Conferi a ficha.", "id_execucao": "ocr-teste",
            "sha256_origem": "hash-origem", "sha256_revisado": "hash-texto",
        }
        caminhos = {**main.CONFIG["caminhos"], "processados": str(self.raiz / "processados"),
                    "minutas": str(self.raiz / "minutas")}
        with patch.dict(main.CONFIG, {"caminhos": caminhos}), \
                patch("src.vision.obter_ocr_confirmado", return_value=resultado_ocr), \
                patch("src.llm_client.chamar_chat", return_value={"texto": "{}"}):
            resultado = main.processar_caso("caso03_ocr", "groq", "modelo", main.CONFIG["producao"],
                                           nao_interativo=True, caminho_log=self.log)
        self.assertEqual(resultado["decisao_humana"], "PENDENTE")
        self.assertIn('"id_ocr": "ocr-teste"', self.log.read_text())


if __name__ == "__main__":
    unittest.main()
