"""Testes unitários offline da classificação de sentimentos e da agregação do painel (RF22, RF23/T13 — Estudante 3).

O provedor é substituído por uma função falsa: nenhum teste chama API externa.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import prompts, schemas, sentiment


def _resposta(texto: str) -> dict:
    return {"texto": texto, "latencia_s": 0.1, "tokens_entrada": 100, "tokens_saida": 30, "custo_usd": None}


def _json(id_av: str, polaridade: str, revisao: bool = False, confianca: str = "alta", justificativa: str = "O texto avalia o atendimento.") -> str:
    return json.dumps({"id_avaliacao": id_av, "polaridade": polaridade, "justificativa": justificativa,
                       "requer_revisao": revisao, "confianca_declarada": confianca})


def _chamar_gabarito(perfil, modelo, mensagens, parametros, **kw):
    """Provedor falso que responde o rótulo do gabarito para o ID pedido na mensagem."""
    gab = sentiment.carregar_gabarito()
    id_av = mensagens[-1]["content"].split("id_avaliacao=")[1].split()[0]
    g = gab[id_av]
    return _resposta(_json(id_av, g["polaridade_esperada"], g["requer_revisao_esperado"],
                           "baixa" if g["requer_revisao_esperado"] else "alta"))


class TestEntradaEPrompt(unittest.TestCase):

    def test_doze_avaliacoes_validas_no_contrato(self):
        avs = sentiment.carregar_avaliacoes()
        self.assertEqual(len(avs), 12)
        self.assertEqual(len(sentiment.carregar_gabarito()), 12)

    def test_so_id_e_texto_vao_ao_provedor_delimitados(self):
        av = sentiment.carregar_avaliacoes()[0]
        msgs, meta = prompts.montar_mensagens_sentimento(av.id_avaliacao, av.texto)
        usuario = msgs[1]["content"]
        self.assertIn("<conteudo_nao_confiavel", usuario)
        self.assertNotIn(av.canal, usuario)
        self.assertNotIn(av.data, usuario)
        self.assertNotIn(av.texto, msgs[0]["content"])
        self.assertEqual(meta["versao_prompt"], "sentimento-v1.0")


class TestValidacaoClassificacao(unittest.TestCase):

    def test_json_valido_com_tipo_incorreto_e_rejeitado(self):
        estado, obj, erros = sentiment.validar_classificacao(
            json.dumps({"id_avaliacao": "AV-01", "polaridade": "positiva", "justificativa": "ok",
                        "requer_revisao": "nao", "confianca_declarada": "alta"}), "AV-01")
        self.assertEqual(estado, "rejeitada_esquema")
        self.assertIn("tipo_incorreto", {e["categoria"] for e in erros})

    def test_indeterminada_sem_revisao_viola_contrato(self):
        estado, _, _ = sentiment.validar_classificacao(_json("AV-12", "indeterminada", revisao=False), "AV-12")
        self.assertEqual(estado, "rejeitada_esquema")

    def test_id_divergente_bloqueia(self):
        estado, _, erros = sentiment.validar_classificacao(_json("AV-99", "positiva"), "AV-01")
        self.assertEqual(estado, "bloqueada_negocio")
        self.assertEqual(erros[0]["categoria"], "id_divergente")

    def test_uma_unica_correcao_e_depois_rejeita(self):
        chamadas = []

        def chamar(perfil, modelo, mensagens, parametros, **kw):
            chamadas.append(1)
            return _resposta("{nao é json")

        av = sentiment.carregar_avaliacoes()[0]
        with tempfile.TemporaryDirectory() as tmp:
            r = sentiment.classificar_avaliacao(av, chamar=chamar, caminho_log=Path(tmp) / "log.jsonl")
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(r.estado, "rejeitada_esquema")
        self.assertEqual(r.polaridade, sentiment.SEM_ROTULO)
        self.assertTrue(r.incerto)

    def test_inferencia_sobre_autor_vira_alerta_e_revisao(self):
        def chamar(perfil, modelo, mensagens, parametros, **kw):
            return _resposta(_json("AV-05", "negativa", justificativa="O autor parece ansioso e impaciente."))

        av = sentiment.carregar_avaliacoes()[4]
        with tempfile.TemporaryDirectory() as tmp:
            r = sentiment.classificar_avaliacao(av, chamar=chamar, caminho_log=Path(tmp) / "log.jsonl")
        self.assertEqual(r.estado, "valida")
        self.assertTrue(r.classificacao["requer_revisao"])
        self.assertTrue(r.incerto)
        self.assertIn("inferencia_sobre_autor", r.alertas[0])

    def test_transtornos_no_sentido_de_incomodo_nao_e_inferencia(self):
        # Falso positivo real da execução 20261101-180242 (AV-10): "causaram transtornos" descreve o processo.
        self.assertIsNone(sentiment._RE_INFERENCIA_AUTOR.search("relata falhas no processo que causaram transtornos"))


class TestLoteEComparacao(unittest.TestCase):

    def test_lote_com_respostas_do_gabarito_acerta_12_e_sinaliza_ambiguos(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = sentiment.executar_lote(chamar=_chamar_gabarito, destino=Path(tmp) / "exec",
                                            caminho_log=Path(tmp) / "log.jsonl", provedor="openai")
            pacote = json.loads((pasta / "classificacoes.json").read_text(encoding="utf-8"))
            self.assertTrue((pasta / "matriz_rf22.md").is_file())
        c = pacote["comparacao"]
        self.assertEqual(c["acuracia_polaridade"]["formatado"], "12/12 (100%)")
        self.assertEqual(c["ambiguos_sinalizados"]["formatado"], "3/3 (100%)")
        self.assertEqual(pacote["agregado"]["contagens"]["negativa"], 4)
        self.assertEqual(pacote["agregado"]["contagens"]["indeterminada"], 2)

    def test_erro_de_rotulo_aparece_na_comparacao(self):
        def chamar(perfil, modelo, mensagens, parametros, **kw):
            id_av = mensagens[-1]["content"].split("id_avaliacao=")[1].split()[0]
            pol = "positiva" if id_av == "AV-11" else sentiment.carregar_gabarito()[id_av]["polaridade_esperada"]
            return _resposta(_json(id_av, pol, revisao=pol == "indeterminada"))

        with tempfile.TemporaryDirectory() as tmp:
            pasta = sentiment.executar_lote(chamar=chamar, destino=Path(tmp) / "e", caminho_log=Path(tmp) / "l.jsonl")
            c = json.loads((pasta / "classificacoes.json").read_text(encoding="utf-8"))["comparacao"]
        self.assertEqual(c["erros"], ["AV-11"])
        self.assertEqual(c["acuracia_polaridade"]["numerador"], 11)


class TestT13Agregacao(unittest.TestCase):
    """T13 (RF23): filtro, duplicata e conjunto vazio — totais corretos e denominador visível."""

    def _registros(self):
        return [
            {"id_avaliacao": "AV-01", "polaridade": "positiva", "incerto": False, "canal": "Presencial",
             "categoria_atendimento": "matricula", "confianca_declarada": "alta"},
            {"id_avaliacao": "AV-01", "polaridade": "positiva", "incerto": False, "canal": "Presencial",
             "categoria_atendimento": "matricula", "confianca_declarada": "alta"},
            {"id_avaliacao": "AV-04", "polaridade": "negativa", "incerto": False, "canal": "Presencial",
             "categoria_atendimento": "matricula", "confianca_declarada": "media"},
            {"id_avaliacao": "AV-12", "polaridade": "indeterminada", "incerto": True, "canal": "E-mail",
             "categoria_atendimento": "outros", "confianca_declarada": "baixa"},
        ]

    def test_duplicata_ignorada_e_totais_corretos(self):
        a = sentiment.agregar(self._registros())
        self.assertEqual(a["total_recebidos"], 4)
        self.assertEqual(a["duplicatas_ignoradas"], 1)
        self.assertEqual(a["denominador_filtrado"], 3)
        self.assertEqual(a["contagens"]["positiva"], 1)
        self.assertEqual(a["incertos"]["formatado"], "1/3 (33%)")
        self.assertEqual(a["por_canal"]["Presencial"]["negativa"], 1)

    def test_filtro_por_canal(self):
        a = sentiment.agregar(self._registros(), {"canal": "E-mail"})
        self.assertEqual(a["denominador_filtrado"], 1)
        self.assertEqual(a["contagens"]["indeterminada"], 1)
        self.assertEqual(a["filtros"], {"canal": "E-mail"})

    def test_conjunto_vazio_sem_divisao_por_zero(self):
        for registros, filtros in (([], None), (self._registros(), {"canal": "Inexistente"})):
            a = sentiment.agregar(registros, filtros)
            self.assertEqual(a["denominador_filtrado"], 0)
            self.assertIsNone(a["incertos"]["taxa"])
            self.assertIn("conjunto vazio", a["incertos"]["formatado"])
            self.assertEqual(sum(a["contagens"].values()), 0)

    def test_confianca_e_identificada_como_estimativa(self):
        a = sentiment.agregar(self._registros())
        self.assertIn("NÃO calibrada", a["aviso_confianca"])
        self.assertIn("por código", a["fonte_totais"])


if __name__ == "__main__":
    unittest.main()
