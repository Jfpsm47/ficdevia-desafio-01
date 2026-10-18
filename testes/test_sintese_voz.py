"""RF07: síntese de voz Piper testável sem rede nem inferência real."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from src import audio, main


class TestSinteseVoz(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.patch_raiz = patch.object(audio, "RAIZ", self.raiz)
        self.patch_raiz.start()
        self.addCleanup(self.patch_raiz.stop)
        self.config = copy.deepcopy(main.CONFIG)
        self.config["sintese_voz"].update({
            "diretorio": "resultados/audios",
            "arquivo_modelo": ".cache/piper/pt_BR-faber-medium.onnx",
            "arquivo_config_modelo": ".cache/piper/pt_BR-faber-medium.onnx.json",
        })
        cache = self.raiz / ".cache/piper"
        cache.mkdir(parents=True)
        (cache / "pt_BR-faber-medium.onnx").write_bytes(b"modelo-ficticio")
        (cache / "pt_BR-faber-medium.onnx.json").write_text("{}", encoding="utf-8")
        self.log = self.raiz / "resultados/logs/teste.jsonl"
        self.minuta = self.raiz / "resultados/minutas/caso_teste_minuta.pdf"
        self.minuta.parent.mkdir(parents=True)
        self.minuta.write_text(
            "**Referência:** Protocolo nº 2026-000142\n\n"
            "Prezada pessoa,\n\n"
            "Informamos que a lista de documentos não foi localizada nos dados disponíveis.\n\n"
            "**Informações não localizadas (o servidor deve completar ou confirmar antes de aprovar):**\n"
            "- lista de documentos\n\n"
            "**Rastreabilidade:** execução `min-ficticia`\n"
            "**Decisão humana:** Status: **Aprovada**\n",
            encoding="utf-8",
        )
        self.registrar_minuta("Aprovada")

    def registrar_minuta(self, decisao: str):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.log.write_text(json.dumps({
            "id_execucao": "min-ficticia", "caso_id": "caso_teste", "etapa": "minuta",
            "decisao_humana": decisao, "arquivo_saida": "resultados/minutas/caso_teste_minuta.pdf",
            "revisor": "Revisor fictício", "provedor": "groq", "modelo": "modelo-ficticio",
        }) + "\n", encoding="utf-8")

    @staticmethod
    def voz_ficticia():
        trecho = SimpleNamespace(
            sample_width=2,
            sample_channels=1,
            sample_rate=22050,
            audio_float_array=np.array([0.2, -0.2, 0.0], dtype=np.float32),
        )
        voz = Mock()
        voz.synthesize.return_value = iter([trecho])
        return voz

    def test_sintetiza_minuta_aprovada_e_preserva_aviso_de_lacuna_sem_rede(self):
        voz = self.voz_ficticia()
        with patch("src.audio.PiperVoice.load", return_value=voz) as carregar, \
                patch("src.audio.httpx.post") as post:
            resultado = audio.sintetizar_minuta_aprovada("caso_teste", config=self.config, caminho_log=self.log)

        arquivo_audio = self.raiz / resultado["arquivo_audio"]
        texto = (arquivo_audio.parent / "texto_falado.txt").read_text(encoding="utf-8")
        self.assertTrue(arquivo_audio.is_file())
        self.assertIn("Informações não localizadas", texto)
        self.assertIn("não foi localizada", texto)
        self.assertEqual(resultado["decisao_humana_origem"], "Aprovada")
        self.assertEqual(resultado["provedor"], "piper_local")
        self.assertEqual(resultado["custo_usd"], 0.0)
        self.assertGreater(resultado["segmentos_audio"], 0)
        carregar.assert_called_once()
        post.assert_not_called()
        with wave.open(str(arquivo_audio), "rb") as leitor:
            self.assertEqual(leitor.getframerate(), 22050)
            self.assertGreater(leitor.getnframes(), 0)

    def test_bloqueia_minuta_pendente_ou_rejeitada_antes_da_sintese(self):
        for decisao in ("PENDENTE", "Corrigida", "Rejeitada"):
            with self.subTest(decisao=decisao), patch("src.audio.PiperVoice.load") as carregar:
                self.registrar_minuta(decisao)
                with self.assertRaisesRegex(ValueError, "decisão humana Aprovada"):
                    audio.sintetizar_minuta_aprovada("caso_teste", config=self.config, caminho_log=self.log)
                carregar.assert_not_called()

    def test_bloqueia_arquivo_que_nao_comprova_aprovacao(self):
        self.minuta.write_text("Prezado,\n\nTexto pendente.\n", encoding="utf-8")
        with patch("src.audio.PiperVoice.load") as carregar:
            with self.assertRaisesRegex(ValueError, "não comprova a decisão Aprovada"):
                audio.sintetizar_minuta_aprovada("caso_teste", config=self.config, caminho_log=self.log)
            carregar.assert_not_called()

    def test_divisao_nao_descarta_conteudo_nem_excede_limite(self):
        texto = "Primeira frase curta. Segunda frase também curta, porém relevante. Terceira frase final."
        partes = audio._dividir_texto_para_voz(texto, 45)
        self.assertTrue(all(len(p) <= 45 for p in partes))
        self.assertEqual(" ".join(partes), texto)

    def test_recusa_modelo_ausente_ou_fora_do_cache(self):
        cfg = copy.deepcopy(self.config["sintese_voz"])
        cfg["arquivo_modelo"] = "modelo-fora.onnx"
        with self.assertRaisesRegex(ValueError, "devem ficar em .cache/piper"):
            audio._chamar_piper_tts("Texto de teste.", cfg)
        cfg["arquivo_modelo"] = ".cache/piper/ausente.onnx"
        with self.assertRaisesRegex(ValueError, "Arquivo Piper ausente"):
            audio._chamar_piper_tts("Texto de teste.", cfg)

    def test_falha_do_piper_nao_deixa_arquivo_parcial(self):
        with patch("src.audio.PiperVoice.load", side_effect=RuntimeError("falha-ficticia")):
            with self.assertRaisesRegex(ValueError, "falha-ficticia"):
                audio.sintetizar_minuta_aprovada("caso_teste", config=self.config, caminho_log=self.log)
        self.assertFalse((self.raiz / "resultados/audios").exists())

    def test_registra_aprovacao_da_escuta_separada_da_aprovacao_da_minuta(self):
        with patch("src.audio.PiperVoice.load", return_value=self.voz_ficticia()):
            resultado = audio.sintetizar_minuta_aprovada("caso_teste", config=self.config, caminho_log=self.log)
        pasta = (self.raiz / resultado["arquivo_audio"]).parent
        with self.assertRaisesRegex(ValueError, "Confirme a correspondência"):
            audio.confirmar_sintese(pasta, "Revisor fictício", "Escuta concluída.", decisao="Aprovada",
                                    correspondencia_confirmada=False, caminho_log=self.log)
        meta = audio.confirmar_sintese(pasta, "Revisor fictício", "Escuta concluída e conteúdo confirmado.",
                                       decisao="Aprovada", correspondencia_confirmada=True, caminho_log=self.log)
        self.assertEqual(meta["decisao_humana"], "Aprovada")
        sintese_log = [r for r in audio.audit.ler_registros(self.log) if r["etapa"] == "sintese_voz"]
        self.assertEqual(sintese_log[-1]["decisao_humana"], "Aprovada")
        self.assertEqual(sintese_log[-1]["revisor"], "Revisor fictício")


if __name__ == "__main__":
    unittest.main()
