"""Testes offline dos contratos de dados versionados (src/schemas.py). Não chamam API.

Executar: python -m unittest discover -s testes -t .
"""
import copy
import json
import unittest

from src import schemas

# Exemplo fictício: protocolo e data ausentes, para exercitar null + campos_ausentes.
SOLICITACAO_VALIDA = {
    "protocolo": None,
    "data_solicitacao": None,
    "canal": "WhatsApp institucional",
    "solicitante": "Carlos Eduardo Nunes",
    "curso": "Técnico em Administração",
    "assunto": "Trancamento do curso por motivo de trabalho",
    "pedido": "Saber como trancar o curso.",
    "categoria": "cancelamento_trancamento",
    "entidades": [{"tipo": "pessoa", "valor": "Carlos Eduardo Nunes", "origem": "literal",
                   "evidencia": "Meu nome é Carlos Eduardo Nunes"}],
    "dados_pessoais_detectados": [],
    "campos_ausentes": ["protocolo", "data_solicitacao"],
    "requer_revisao": True,
    "motivos_revisao": ["Protocolo e data ausentes."],
    "alertas_seguranca": [],
}

CITACAO = {"chunk_id": "ACV-01#c3", "documento_id": "ACV-01", "versao_documento": "2.0", "pagina": 2,
           "secao": "3. Prazos", "trecho": "O trancamento pode ser solicitado até 30 dias."}


def categorias(resultado):
    return {(e["campo"], e["categoria"]) for e in resultado.erros}


class TestSolicitacaoExtraida(unittest.TestCase):
    def test_exemplo_valido(self):
        self.assertTrue(schemas.validar(schemas.SolicitacaoExtraida, SOLICITACAO_VALIDA).valido)

    def test_diferencia_chave_extra_tipo_incorreto_e_campo_ausente(self):
        dados = copy.deepcopy(SOLICITACAO_VALIDA)
        dados["prioridade"] = "alta"            # chave extra
        dados["requer_revisao"] = "true"        # tipo incorreto (texto, não booleano)
        del dados["pedido"]                     # campo obrigatório ausente
        res = schemas.validar(schemas.SolicitacaoExtraida, dados)
        self.assertFalse(res.valido)
        self.assertEqual(categorias(res), {("prioridade", "chave_extra"),
                                           ("requer_revisao", "tipo_incorreto"),
                                           ("pedido", "campo_ausente")})

    def test_json_sintaticamente_invalido_nao_chega_ao_esquema(self):
        res = schemas.validar_texto_json(schemas.SolicitacaoExtraida, '{"protocolo": "2026-000142",')
        self.assertEqual(categorias(res), {("(raiz)", "json_invalido")})

    def test_categoria_fora_da_lista_e_formato_de_data(self):
        dados = copy.deepcopy(SOLICITACAO_VALIDA)
        dados["categoria"] = "informacoes_gerais"
        dados["data_solicitacao"] = "2026-10-14"
        dados["campos_ausentes"] = ["protocolo"]
        res = schemas.validar(schemas.SolicitacaoExtraida, dados)
        self.assertIn(("categoria", "valor_invalido"), categorias(res))
        self.assertIn(("data_solicitacao", "valor_invalido"), categorias(res))

    def test_campos_ausentes_deve_corresponder_aos_nulos(self):
        dados = copy.deepcopy(SOLICITACAO_VALIDA)
        dados["campos_ausentes"] = ["protocolo"]   # data_solicitacao é null, mas não foi declarada
        res = schemas.validar(schemas.SolicitacaoExtraida, dados)
        self.assertEqual(categorias(res), {("(raiz)", "regra_do_contrato")})
        self.assertIn("data_solicitacao", res.erros[0]["detalhe"])

    def test_erros_nao_reproduzem_o_valor_recebido(self):
        dados = copy.deepcopy(SOLICITACAO_VALIDA)
        dados["requer_revisao"] = "CPF 123.456.789-00"
        res = schemas.validar(schemas.SolicitacaoExtraida, dados)
        self.assertNotIn("123.456.789-00", json.dumps(res.erros, ensure_ascii=False))

    def test_categoria_revisao_disponivel(self):
        dados = copy.deepcopy(SOLICITACAO_VALIDA)
        dados["categoria"] = "revisao"
        self.assertTrue(schemas.validar(schemas.SolicitacaoExtraida, dados).valido)


class TestResumo(unittest.TestCase):
    def test_limite_de_100_palavras(self):
        ok = {"resumo": " ".join(["palavra"] * 100), "fatos": []}
        excesso = {"resumo": " ".join(["palavra"] * 101), "fatos": []}
        self.assertTrue(schemas.validar(schemas.ResumoSolicitacao, ok).valido)
        res = schemas.validar(schemas.ResumoSolicitacao, excesso)
        self.assertEqual(categorias(res), {("resumo", "regra_do_contrato")})


class TestRespostaRAG(unittest.TestCase):
    def base(self, **alteracoes):
        dados = {"status": "fundamentada", "resposta": "Até 30 dias.",
                 "afirmacoes": [{"texto": "O prazo é de 30 dias.", "chunk_ids": ["ACV-01#c3"]}],
                 "citacoes": [CITACAO], "requer_revisao": False, "motivo_revisao": None}
        dados.update(alteracoes)
        return schemas.validar(schemas.RespostaRAG, dados)

    def test_fundamentada_valida(self):
        self.assertTrue(self.base().valido)

    def test_afirmacao_sem_trecho_citado_e_rejeitada(self):
        res = self.base(afirmacoes=[{"texto": "Prazo de 45 dias.", "chunk_ids": ["ACV-09#c1"]}])
        self.assertFalse(res.valido)

    def test_sem_evidencia_nao_admite_afirmacao_institucional(self):
        self.assertFalse(self.base(status="sem_evidencia", requer_revisao=True,
                                   motivo_revisao="Sem fonte no acervo.").valido)
        self.assertTrue(self.base(status="sem_evidencia", afirmacoes=[], citacoes=[], requer_revisao=True,
                                  motivo_revisao="Sem fonte no acervo.").valido)

    def test_conflito_exige_dois_documentos_e_revisao(self):
        outra = dict(CITACAO, chunk_id="ACV-05#c2", documento_id="ACV-05", trecho="Até 60 dias.")
        self.assertFalse(self.base(status="conflito_fontes", requer_revisao=True, motivo_revisao="x").valido)
        self.assertFalse(self.base(status="conflito_fontes", citacoes=[CITACAO, outra]).valido)
        self.assertTrue(self.base(status="conflito_fontes", citacoes=[CITACAO, outra], requer_revisao=True,
                                  motivo_revisao="ACV-01 e ACV-05 divergem sobre o prazo.").valido)


class TestSentimentoERevisao(unittest.TestCase):
    def test_indeterminada_exige_revisao(self):
        dados = {"id_avaliacao": "AV-01", "polaridade": "indeterminada", "justificativa": "Elogio e queixa.",
                 "requer_revisao": False, "confianca_declarada": "baixa"}
        self.assertFalse(schemas.validar(schemas.ClassificacaoSentimento, dados).valido)
        dados["requer_revisao"] = True
        self.assertTrue(schemas.validar(schemas.ClassificacaoSentimento, dados).valido)

    def test_decisao_exige_justificativa_e_nunca_envia(self):
        self.assertTrue(schemas.validar(schemas.DecisaoRevisao, {"id_minuta": "m1", "estado": "pendente"}).valido)
        self.assertFalse(schemas.validar(schemas.DecisaoRevisao, {"id_minuta": "m1", "estado": "aprovada"}).valido)
        aprovada = {"id_minuta": "m1", "estado": "aprovada", "revisor": "Revisor fictício",
                    "justificativa": "Fontes conferidas.", "data_hora": "2026-10-28T10:00:00-04:00"}
        self.assertTrue(schemas.validar(schemas.DecisaoRevisao, aprovada).valido)
        self.assertFalse(schemas.validar(schemas.DecisaoRevisao, dict(aprovada, enviada_ao_cidadao=True)).valido)


class TestEsquemasExportados(unittest.TestCase):
    def test_arquivos_em_sincronia_com_os_modelos(self):
        for nome in schemas.ESQUEMAS:
            caminho = schemas.DIR_ESQUEMAS / f"{nome}.schema.json"
            self.assertTrue(caminho.exists(), f"rode: python -m src.schemas exportar ({nome})")
            self.assertEqual(caminho.read_text(encoding="utf-8"), schemas.texto_esquema(nome),
                             f"{nome} desatualizado: rode python -m src.schemas exportar")

    def test_saidas_do_modelo_sao_compativeis_com_modo_estrito(self):
        """Modo estrito exige todos os campos obrigatórios e nenhuma chave adicional."""
        for nome in ("solicitacao_extraida", "resumo_solicitacao", "classificacao_sentimento"):
            esquema = schemas.esquema_json(nome)
            objetos = [esquema, *esquema.get("$defs", {}).values()]
            for obj in objetos:
                self.assertFalse(obj.get("additionalProperties", True), nome)
                self.assertEqual(set(obj["required"]), set(obj["properties"]), nome)


if __name__ == "__main__":
    unittest.main()
