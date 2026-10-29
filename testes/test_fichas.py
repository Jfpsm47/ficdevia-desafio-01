"""Testes offline da ficha de compreensão (RF15): resumo, regras do resumo e conferência com o gabarito.

Não chamam API: o provedor é substituído por respostas controladas (ProvedorFalso de test_nlp).

Executar: python -m unittest discover -s testes -t .
"""
import json
import tempfile
import unittest
from pathlib import Path

from src import nlp, prompts
from testes.test_nlp import CFG, TEXTO_05, TEXTO_AUDIO, VALIDA_05, ProvedorFalso, com

RAIZ = prompts.RAIZ
GAB_05 = json.loads((RAIZ / "dados/gabaritos/d2/solicitacoes/caso05_texto_incompleto.json").read_text(encoding="utf-8"))
GAB_02 = json.loads((RAIZ / "dados/gabaritos/d2/solicitacoes/caso02_audio.json").read_text(encoding="utf-8"))

RESUMO_05 = {
    "resumo": "Carlos Eduardo Nunes, do curso Técnico em Administração, pergunta como trancar o curso porque "
              "começou a trabalhar à noite. Protocolo e data não foram informados.",
    "fatos": [
        {"afirmacao": "Quer trancar o curso.", "evidencia": "Quero saber como faço pra trancar meu curso"},
        {"afirmacao": "Começou a trabalhar à noite.", "evidencia": "comecei a trabalhar à noite"},
    ],
}


class BaseResumo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "log.jsonl"

    def resumir(self, provedor, texto=TEXTO_05):
        return nlp.resumir(texto, "dados/originais/x.txt", "caso_teste", CFG, chamar=provedor, caminho_log=self.log)


class TestResumo(BaseResumo):
    def test_resumo_fiel_e_valido(self):
        res = self.resumir(ProvedorFalso(RESUMO_05))
        self.assertEqual((res.estado, res.erros), ("valida", []))

    def test_mais_de_100_palavras_ganha_uma_correcao(self):
        longo = com(RESUMO_05, resumo=" ".join(["palavra"] * 101))
        provedor = ProvedorFalso(longo, RESUMO_05)
        res = self.resumir(provedor)
        self.assertEqual((res.estado, len(provedor.chamadas)), ("valida", 2))
        self.assertIn("resumo: regra_do_contrato", provedor.chamadas[1]["mensagens"][-1]["content"])
        res = self.resumir(ProvedorFalso(longo, longo))
        self.assertEqual(res.estado, "rejeitada_esquema")

    def test_fato_sem_trecho_no_original_e_bloqueado(self):
        inventado = com(RESUMO_05, fatos=[{"afirmacao": "Já entregou o requerimento.",
                                           "evidencia": "entreguei o requerimento na secretaria"}])
        res = self.resumir(ProvedorFalso(inventado))
        self.assertEqual(res.estado, "bloqueada_negocio")
        self.assertEqual({e["categoria"] for e in res.erros}, {"fato_sem_suporte"})

    def test_prazo_ou_data_inventados_no_resumo(self):
        inventado = com(RESUMO_05, resumo=RESUMO_05["resumo"] + " O prazo é de 30 dias, até 15/11/2026.")
        erros = nlp.validar_resumo(json.dumps(inventado, ensure_ascii=False), TEXTO_05)[2]
        self.assertEqual([e["categoria"] for e in erros], ["valor_sem_suporte", "valor_sem_suporte"])

    def test_data_por_extenso_e_milhar_do_original_sao_aceitos(self):
        resumo = {"resumo": "Marcos Vinícius de Almeida Santos, protocolo 2026-000142 de 14/10/2026, pede a "
                            "efetivação da matrícula no Técnico em Enfermagem (1200 horas).", "fatos": []}
        self.assertEqual(nlp.validar_resumo(json.dumps(resumo, ensure_ascii=False), TEXTO_AUDIO)[2], [])

    def test_dado_pessoal_no_resumo_e_bloqueado_sem_reproduzir_o_valor(self):
        vazado = com(RESUMO_05, resumo=RESUMO_05["resumo"] + " E-mail: carlos.teste@examplo.com.")
        erros = nlp.validar_resumo(json.dumps(vazado, ensure_ascii=False), TEXTO_05)[2]
        self.assertIn("dado_pessoal_no_resumo", {e["categoria"] for e in erros})
        self.assertNotIn("carlos.teste", json.dumps(erros, ensure_ascii=False))

    def test_prompt_de_resumo_separa_instrucoes_e_minimiza(self):
        msgs, meta = prompts.montar_mensagens_resumo(TEXTO_AUDIO, "x.txt")
        self.assertEqual(meta["versao_prompt"], "resumo-v1.0")
        self.assertNotIn("Marcos", msgs[0]["content"])
        self.assertNotIn("1234567-8", msgs[1]["content"])

    def test_auditoria_do_resumo(self):
        self.resumir(ProvedorFalso(RESUMO_05))
        registro = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((registro["etapa"], registro["versao_prompt"]), ("resumo", "resumo-v1.0"))
        self.assertEqual(registro["versao_contrato"], "resumo_solicitacao-v0.1.0")


class TestFicha(BaseResumo):
    def test_ficha_so_existe_com_extracao_e_resumo_validos(self):
        res = self.resumir(ProvedorFalso(RESUMO_05))
        ficha = nlp.montar_ficha("caso05", VALIDA_05, "valida", "extracao-v2.1", res)
        self.assertEqual((ficha["id_caso"], ficha["versao_prompt_resumo"]), ("caso05", "resumo-v1.0"))
        self.assertIsNone(nlp.montar_ficha("caso05", VALIDA_05, "bloqueada_negocio", "extracao-v2.1", res))
        retido = self.resumir(ProvedorFalso(com(RESUMO_05, fatos=[{"afirmacao": "x", "evidencia": "não está"}])))
        self.assertIsNone(nlp.montar_ficha("caso05", VALIDA_05, "valida", "extracao-v2.1", retido))


class TestAvaliacaoDaFicha(unittest.TestCase):
    def test_ficha_igual_ao_gabarito(self):
        av = nlp.avaliar_ficha(VALIDA_05, RESUMO_05, GAB_05)
        self.assertTrue(av["categoria"]["correta"])
        self.assertEqual((av["entidades"]["encontradas"], av["entidades"]["esperadas"]), (1, 1))
        self.assertEqual((av["entidades"]["omitidas"], av["entidades"]["a_mais"]), ([], []))
        self.assertEqual(av["resumo"]["padroes_proibidos"], [])

    def test_omissao_entidade_a_mais_e_origem_divergente(self):
        extracao = com(VALIDA_05, entidades=[
            {"tipo": "pessoa", "valor": "Carlos Eduardo Nunes", "origem": "inferida", "evidencia": "Carlos Eduardo Nunes"},
            {"tipo": "orgao", "valor": "Secretaria Escolar", "origem": "inferida", "evidencia": "trancar meu curso"}])
        av = nlp.avaliar_ficha(extracao, RESUMO_05, GAB_02)
        self.assertIn("protocolo: 2026-000142", av["entidades"]["omitidas"])
        self.assertIn("orgao: Secretaria Escolar (inferida)", av["entidades"]["a_mais"])
        av = nlp.avaliar_ficha(extracao, RESUMO_05, GAB_05)
        self.assertEqual(len(av["entidades"]["origem_divergente"]), 1)

    def test_data_esperada_confere_com_data_por_extenso(self):
        extracao = {"categoria": "matricula", "entidades": [
            {"tipo": "data", "valor": "14 de outubro de 2026", "origem": "literal", "evidencia": "14 de outubro de 2026"}]}
        av = nlp.avaliar_ficha(extracao, None, GAB_02)
        self.assertNotIn("data: 14/10/2026", av["entidades"]["omitidas"])

    def test_padrao_proibido_e_dado_proibido_no_resumo(self):
        resumo = com(RESUMO_05, resumo="Protocolo 2026-000999 de 01/01/2026.")
        av = nlp.avaliar_ficha(VALIDA_05, resumo, GAB_05)
        self.assertEqual(len(av["resumo"]["padroes_proibidos"]), 2)


if __name__ == "__main__":
    unittest.main()
