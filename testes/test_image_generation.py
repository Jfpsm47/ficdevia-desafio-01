"""RF10: testes offline da importação local e revisão humana obrigatória."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src import image_generation, main


class TestGeracaoImagem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name).resolve()
        self.patch_raiz = patch.object(image_generation, "RAIZ", self.raiz)
        self.patch_raiz.start()
        self.addCleanup(self.patch_raiz.stop)
        self.config = {"geracao_imagem": copy.deepcopy(main.CONFIG["geracao_imagem"])}
        self.cfg = self.config["geracao_imagem"]
        self.cfg.update({
            "diretorio": "resultados/imagens",
            "titulo": "ORIENTAÇÃO FICTÍCIA",
            "aviso_proveniencia": "VISUAL GERADO POR IA • MATERIAL FICTÍCIO • REVISÃO HUMANA OBRIGATÓRIA",
        })
        self.log = self.raiz / "resultados/logs/teste.jsonl"
        self.origem = self.raiz / "resultados/imagens/saida_draw_things.png"
        self.origem.parent.mkdir(parents=True)
        Image.new("RGB", (1024, 1024), "#82d6d8").save(self.origem)

    def importar(self):
        return image_generation.importar_imagem_draw_things(
            self.origem, "caso01_texto", config=self.config, caminho_log=self.log,
        )

    def test_prompt_versionado_tem_todos_os_campos_e_configuracao_local(self):
        prompt, meta = image_generation.ler_prompt_orientacao()
        image_generation.validar_configuracao(self.cfg)
        self.assertEqual(meta["versao_prompt"], "imagem-v1.4")
        self.assertIn("no people", prompt.casefold())
        self.assertIn("text", prompt.casefold())
        self.assertLessEqual(len(prompt.split()), 220)
        self.assertEqual(self.cfg["provedor"], "draw_things_local")
        self.assertEqual(self.cfg["modo_execucao"], "local_offline")
        self.assertEqual(self.cfg["modelo"], "FLUX.2 [klein] 4B (6-bit)")

    def test_bloqueia_arquivo_fora_da_pasta_de_resultados(self):
        externo = self.raiz / "externo.png"
        Image.new("RGB", (1024, 1024), "white").save(externo)
        with self.assertRaisesRegex(ValueError, "dentro de resultados/imagens"):
            image_generation.importar_imagem_draw_things(
                externo, "caso01_texto", config=self.config, caminho_log=self.log,
            )
        self.assertFalse(self.log.exists())

    def test_importa_sem_rede_e_preserva_origem_parametros_e_proveniencia(self):
        resultado = self.importar()
        pasta = (self.raiz / resultado["arquivo_metadados"]).parent
        self.assertEqual(resultado["decisao_humana"], "PENDENTE")
        self.assertEqual(resultado["custo_usd"], 0.0)
        self.assertEqual(resultado["tentativas"], 1)
        self.assertTrue((pasta / "imagem_base.png").is_file())
        self.assertTrue((pasta / "peca_orientacao.png").is_file())
        self.assertTrue((pasta / "prompt_efetivo.md").is_file())
        self.assertTrue((pasta / "inspecao.json").is_file())
        self.assertEqual(resultado["dimensoes_imagem_base"], [1024, 1024])
        self.assertEqual(resultado["dimensoes_peca"], [1024, 576])
        self.assertTrue(resultado["verificacoes_automaticas"]["proporcao_final_16_9"])
        self.assertIn(self.cfg["aviso_proveniencia"], resultado["textos_sobrepostos"])
        self.assertIn("mãos, objetos e proporções", resultado["verificacoes_automaticas"]["revisao_humana_obrigatoria"])
        log = self.log.read_text(encoding="utf-8")
        self.assertIn('"etapa": "geracao_imagem"', log)
        self.assertNotIn("HF_TOKEN", log)
        self.assertNotIn("GROQ_API_KEY", log)

    def test_configuracao_recusa_execucao_remota_ou_parametros_distintos_do_modelo(self):
        self.cfg["modo_execucao"] = "remota"
        with self.assertRaisesRegex(ValueError, "localmente"):
            image_generation.validar_configuracao(self.cfg)
        self.cfg["modo_execucao"] = "local_offline"
        self.cfg["passos"] = 5
        with self.assertRaisesRegex(ValueError, "quatro passos"):
            image_generation.validar_configuracao(self.cfg)

    def test_revisao_exige_quatro_confirmacoes_e_atualiza_auditoria(self):
        resultado = self.importar()
        pasta = (self.raiz / resultado["arquivo_metadados"]).parent
        with self.assertRaisesRegex(ValueError, "textos e números legíveis"):
            image_generation.confirmar_revisao(
                pasta, "Integrante 3", "Inspeção visual concluída.", decisao="Aprovada",
                textos_confirmados=False, simbolos_confirmados=True, maos_objetos_confirmados=True,
                coerencia_confirmada=True, caminho_log=self.log,
            )
        meta = image_generation.confirmar_revisao(
            pasta, "Integrante 3", "Textos, símbolos, objetos e coerência visual conferidos.", decisao="Aprovada",
            textos_confirmados=True, simbolos_confirmados=True, maos_objetos_confirmados=True,
            coerencia_confirmada=True, caminho_log=self.log,
        )
        self.assertEqual(meta["decisao_humana"], "Aprovada")
        self.assertTrue((pasta / "revisao.json").is_file())
        registros = [json.loads(linha) for linha in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(registros[-1]["decisao_humana"], "Aprovada")
        self.assertEqual(registros[-1]["revisor"], "Integrante 3")

    def test_revisao_recusa_artefato_alterado(self):
        resultado = self.importar()
        peca = self.raiz / resultado["arquivo_peca"]
        peca.write_bytes(b"alterada")
        with self.assertRaisesRegex(ValueError, "evidência visual foi alterada"):
            image_generation.confirmar_revisao(
                peca.parent, "Integrante 3", "Inspeção visual concluída.", decisao="Rejeitada",
                textos_confirmados=True, simbolos_confirmados=True, maos_objetos_confirmados=True,
                coerencia_confirmada=True, caminho_log=self.log,
            )


if __name__ == "__main__":
    unittest.main()
