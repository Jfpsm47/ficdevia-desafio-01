"""Testes offline dos dados fictícios e gabaritos do Desafio 02 (src/dados_ficticios.py). Não chamam API.

Executar: python -m unittest discover -s testes -t .
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import dados_ficticios as df


class TestConjuntoReal(unittest.TestCase):
    def test_conjunto_atual_e_coerente(self):
        self.assertEqual(df.verificar(), [])

    def test_pdfs_reprodutiveis_e_paginados(self):
        for doc in df.ler_catalogo():
            if doc.formato != "pdf":
                continue
            fonte = (df.DIR_FONTES / f"{doc.documento_id}.txt").read_text(encoding="utf-8")
            self.assertEqual(df.gerar_pdf(fonte, doc.titulo), df.gerar_pdf(fonte, doc.titulo))
            paginas = df.paginas_documento(doc)
            self.assertEqual([p for p, _ in paginas], list(range(1, len(paginas) + 1)))
            self.assertIn("Identificador: " + doc.documento_id, paginas[0][1])

    def test_normalizacao_tolera_quebra_de_linha_e_acento(self):
        self.assertEqual(df.normalizar("Matrícula\n  EFETIVADA"), df.normalizar("matricula efetivada"))


class TestDefeitosDetectados(unittest.TestCase):
    """Cada teste estraga uma cópia dos gabaritos e confere que `verificar` acusa o defeito."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.gab = self.tmp / "d2"
        shutil.copytree(df.DIR_GABARITOS, self.gab)
        (self.gab / "HASHES.json").unlink(missing_ok=True)  # cada teste parte sem manifesto congelado
        for alvo, valor in (("DIR_GABARITOS", self.gab), ("ARQ_HASHES", self.gab / "HASHES.json")):
            p = patch.object(df, alvo, valor)
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.tmp)

    def editar(self, relativo, funcao):
        caminho = self.gab / relativo
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        funcao(dados)
        caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    def assertProblema(self, trecho):
        problemas = df.verificar()
        self.assertTrue(any(trecho in p for p in problemas), problemas)

    def test_trecho_de_referencia_inexistente(self):
        self.editar("rag_perguntas.json", lambda d: d["perguntas"][0]["referencias"][0].update(trecho="prazo de 45 dias"))
        self.assertProblema("P01: trecho de referência não encontrado")

    def test_falta_pergunta_sem_resposta(self):
        self.editar("rag_perguntas.json", lambda d: d["perguntas"].pop())
        self.assertProblema("'sem_resposta'")

    def test_evidencia_de_entidade_fora_do_original(self):
        self.editar("solicitacoes/caso06_texto_transferencia.json",
                    lambda d: d["entidades_esperadas"][0].update(evidencia="Sou Juliana Rocha Martins"))
        self.assertProblema("caso06_texto_transferencia.json: evidência")

    def test_campos_ausentes_incoerentes(self):
        self.editar("solicitacoes/caso05_texto_incompleto.json",
                    lambda d: d["extracao_esperada"].update(campos_ausentes=["protocolo"]))
        self.assertProblema("campos_ausentes não corresponde")

    def test_rotulo_ambiguo_sem_justificativa(self):
        self.editar("sentimentos.json", lambda d: d["rotulos"][9].pop("justificativa_rotulo"))
        self.assertProblema("AV-10: rótulo ambíguo")

    def test_congelar_recusa_gabarito_pendente(self):
        self.editar("sentimentos.json", lambda d: d.update(status_validacao_humana="PENDENTE"))
        with self.assertRaisesRegex(ValueError, "PENDENTES"):
            df.congelar()
        self.assertFalse((self.gab / "HASHES.json").exists())

    def test_congelar_grava_hashes_quando_validado(self):
        for caminho in df.arquivos_gabarito():
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            dados["status_validacao_humana"] = "VALIDADO - Revisor fictício - 28/10/2026"
            caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        registro = json.loads(df.congelar().read_text(encoding="utf-8"))
        self.assertIn("dados/acervo/ACV-01.pdf", registro["arquivos"])
        self.assertIn("dados/avaliacoes/avaliacoes.csv", registro["arquivos"])
        self.assertTrue(all(len(h) == 64 for h in registro["arquivos"].values()))


if __name__ == "__main__":
    unittest.main()
