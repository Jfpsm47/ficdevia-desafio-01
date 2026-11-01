"""Teste de fumaça offline da interface Streamlit (RF20 — Estudante 3).

Renderiza o app com `streamlit.testing` (sem navegador e sem chamar provedor de IA) e confere que as cinco
abas carregam sem exceção, que o painel mostra denominador e aviso de confiança e que o formulário de
revisão não registra decisão sem servidor e justificativa.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "src" / "app.py")


class TestInterfaceStreamlit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.at = AppTest.from_file(APP, default_timeout=120).run()

    def test_cinco_abas_sem_excecao(self):
        self.assertFalse(self.at.exception, [e.value for e in self.at.exception])
        self.assertEqual([t.label for t in self.at.tabs],
                         ["Solicitação e revisão", "Consulta ao acervo", "Acervo e índice", "Painel de sentimentos", "Auditoria"])

    def test_aviso_de_envio_bloqueado_na_barra_lateral(self):
        self.assertTrue(any("enviada ao cidadão automaticamente" in i.value for i in self.at.sidebar.info))

    def test_painel_mostra_denominador_e_confianca_nao_calibrada(self):
        rotulos = [m.label for m in self.at.metric]
        self.assertIn("Avaliações no filtro", rotulos)
        self.assertTrue(any("NÃO calibrada" in i.value for i in self.at.info))

    def test_revisao_sem_servidor_e_justificativa_nao_registra(self):
        at = AppTest.from_file(APP, default_timeout=120).run()
        botoes = [b for b in at.button if b.label == "Registrar decisão"]
        if not botoes:
            self.skipTest("Caso padrão sem minuta salva para revisar")
        botoes[0].click().run()
        self.assertTrue(any("não foi registrada" in e.value for e in at.error))


if __name__ == "__main__":
    unittest.main()
