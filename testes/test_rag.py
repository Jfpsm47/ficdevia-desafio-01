"""Testes unitários offline do motor RAG, citações determinísticas, abstenção, conflito e segurança (RF16, RF19, RF23).

Cobre os cenários da matriz:
- T08 (RF19): respostas fundamentadas com citações reconstruídas exclusivamente do índice;
- T09 (RF19): abstenção explícita (`sem_evidencia`) e encaminhamento humano sem inventar regras;
- T10 (RF19): detecção de conflito entre fontes vigentes (`conflito_fontes` citando >=2 documentos + revisão);
- ADV-02 (RF16): defesa contra prompt injection indireto em documento recuperado (`ACV-06 §3`);
- T13 / RF23: cálculo determinístico com numerador/denominador visíveis e proteção contra divisão por zero.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import embeddings, ingestion, llm_client, metrics, rag
from src.llm_client import ErroProvedor


class _AdaptadorMockSequencial(llm_client.AdaptadorGeracao):
    """Adaptador falso para testar loops de validação e correção do RAG sem rede."""

    provedor = "mock_rag"
    modelo = "modelo-mock"
    modo_saida = "json_schema_estrito"
    parametros = {"temperature": 0}
    timeout_s = 5.0
    tentativas_transitorias = 2
    eh_simulado = False

    def __init__(self, respostas: list[str | Exception]):
        self._respostas = list(respostas)
        self.chamadas: list[list[dict[str, str]]] = []
        self.orcamento = llm_client.ControladorOrcamento()

    def gerar(self, mensagens, *, parametros_extras=None, json_mode=False, dry_run=False):
        self.chamadas.append(list(mensagens))
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return {
            "texto": item,
            "latencia_s": 0.05,
            "tokens_entrada": 120,
            "tokens_saida": 60,
            "custo_usd": 0.00005,
            "tentativas": 1,
            "erro": None,
            "simulado": False,
            "metrica_custo_status": "calculada_tabela_config",
        }


def _verificar_esquema_estrito_recursivo(no: dict, teste: unittest.TestCase) -> None:
    if no.get("type") == "object" or "properties" in no:
        teste.assertIs(no.get("additionalProperties"), False)
        props = set((no.get("properties") or {}).keys())
        reqs = set(no.get("required") or [])
        teste.assertEqual(props, reqs)
        for sub in (no.get("properties") or {}).values():
            _verificar_esquema_estrito_recursivo(sub, teste)
    if "items" in no and isinstance(no["items"], dict):
        _verificar_esquema_estrito_recursivo(no["items"], teste)
    for def_sub in (no.get("$defs") or {}).values():
        _verificar_esquema_estrito_recursivo(def_sub, teste)


class TestEsquemaEstritoECitacoesRAG(unittest.TestCase):
    """Testa compatibilidade com modo estrito e reconstrução determinística de citações."""

    def setUp(self):
        _, trechos = ingestion.ingerir_acervo(tamanho=700, sobreposicao=120)
        acv01 = [t for t in trechos if t.documento_id == "ACV-01"][:3]
        self.trechos_acv01 = [
            embeddings.ResultadoBusca(
                posicao=i + 1,
                similaridade=0.85 - i * 0.05,
                trecho=t,
            )
            for i, t in enumerate(acv01)
        ]

    def test_saida_geracao_rag_compativel_com_modo_estrito(self):
        esquema = rag._SaidaGeracaoRAG.model_json_schema()
        _verificar_esquema_estrito_recursivo(esquema, self)

    def test_reconstroi_citacoes_a_partir_do_indice_e_rejeita_chunk_inventado(self):
        cid_valido = self.trechos_acv01[0].trecho.chunk_id
        # 1) Chunk inventado é rejeitado na camada de citação
        json_invalido = json.dumps(
            {
                "status": "fundamentada",
                "resposta": "O prazo é de 5 dias úteis.",
                "afirmacoes": [{"texto": "Prazo de 5 dias úteis.", "chunk_ids": ["ACV-99#c1"]}],
                "requer_revisao": False,
                "motivo_revisao": None,
            }
        )
        est, obj, errs = rag.validar_e_montar_resposta_rag(json_invalido, self.trechos_acv01)
        self.assertEqual(est, "rejeitada_esquema")
        self.assertIsNone(obj)
        self.assertEqual(errs[0]["categoria"], "chunk_nao_recuperado")

        # 2) Chunk recuperado gera Citacao idêntica aos metadados do TrechoIndexado
        json_valido = json.dumps(
            {
                "status": "fundamentada",
                "resposta": "Conforme o Guia de Matrícula, a documentação deve ser conferida na Secretaria.",
                "afirmacoes": [
                    {
                        "texto": "A documentação deve ser conferida na Secretaria Escolar.",
                        "chunk_ids": [cid_valido],
                    }
                ],
                "requer_revisao": False,
                "motivo_revisao": None,
            },
            ensure_ascii=False,
        )
        est2, obj2, errs2 = rag.validar_e_montar_resposta_rag(json_valido, self.trechos_acv01)
        self.assertEqual(est2, "valida")
        self.assertEqual(errs2, [])
        self.assertIsNotNone(obj2)
        assert obj2 is not None
        self.assertEqual(len(obj2.citacoes), 1)
        self.assertEqual(obj2.citacoes[0].documento_id, "ACV-01")
        self.assertEqual(obj2.citacoes[0].versao_documento, self.trechos_acv01[0].trecho.versao_documento)
        self.assertEqual(obj2.citacoes[0].pagina, self.trechos_acv01[0].trecho.pagina)
        self.assertEqual(obj2.citacoes[0].trecho, self.trechos_acv01[0].trecho.texto)

    def test_faz_no_maximo_uma_correcao_inclusive_em_recusa_http_400_modo_estrito(self):
        with tempfile.TemporaryDirectory() as tmp:
            dir_idx = Path(tmp) / "idx"
            log_tmp = Path(tmp) / "execucoes.jsonl"
            idx = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embeddings.EmbeddingsDeterministicoTeste(dimensao=64),
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            idx.indexar_acervo()

            erro_400 = ErroProvedor(
                "failed to validate JSON: does not match the expected schema",
                codigo_erro="requisicao_invalida",
                status_code=400,
            )
            # Duas falhas seguidas: 1ª chamada + 1ª correção -> para na 2ª chamada e retém para revisão
            adp = _AdaptadorMockSequencial([erro_400, '{"json_quebrado": '])
            res = rag.consultar_acervo(
                "Qual é o prazo para declaração?",
                indice=idx,
                adaptador=adp,
                caminho_log=log_tmp,
            )
            self.assertEqual(len(adp.chamadas), 2)
            self.assertEqual(res.estado, "rejeitada_validacao")
            self.assertTrue(res.resposta_rag["requer_revisao"])
            self.assertEqual(res.resposta_rag["status"], "sem_evidencia")


class TestComportamentosMotorRAG(unittest.TestCase):
    """Valida T08 (fundamentada), T09 (abstenção), T10 (conflito) e ADV-02 (injeção indireta no acervo)."""

    @classmethod
    def setUpClass(cls):
        _, cls.trechos = ingestion.ingerir_acervo(tamanho=700, sobreposicao=120)
        cls.perguntas_gab = {p["id"]: p for p in metrics.carregar_perguntas_rag()["perguntas"]}

    def _busca_por_docs(self, doc_ids: list[str]) -> list[embeddings.ResultadoBusca]:
        selecionados = [t for t in self.trechos if t.documento_id in doc_ids]
        return [
            embeddings.ResultadoBusca(
                posicao=i + 1,
                similaridade=0.80,
                trecho=t,
            )
            for i, t in enumerate(selecionados)
        ]

    def test_t09_abstencao_sem_evidencia_e_deteccao_padrao_proibido(self):
        busca = self._busca_por_docs(["ACV-01"])
        saida_abstencao = json.dumps(
            {
                "status": "sem_evidencia",
                "resposta": (
                    "Os documentos institucionais consultados não trazem orientações sobre esse tema; "
                    "a consulta foi encaminhada para revisão humana da Secretaria Escolar."
                ),
                "afirmacoes": [],
                "requer_revisao": True,
                "motivo_revisao": "Tema ausente no acervo institucional indexado.",
            },
            ensure_ascii=False,
        )
        est, obj, _ = rag.validar_e_montar_resposta_rag(saida_abstencao, busca)
        self.assertEqual(est, "valida")
        assert obj is not None
        ver = metrics.verificar_resposta_rag_contra_fontes(
            obj.model_dump(),
            [b.para_dict() for b in busca],
            self.perguntas_gab["P07"],
        )
        self.assertTrue(ver["status_confere"])
        self.assertTrue(ver["todas_afirmacoes_sustentadas"])
        self.assertEqual(ver["padroes_proibidos_acionados"], [])

        # Se inventar valor em R$, o verificador reprova por padrão proibido
        obj_ruim = obj.model_dump()
        obj_ruim["resposta"] = "O auxílio estudantil é de R$ 300,00 mensais."
        ver_ruim = metrics.verificar_resposta_rag_contra_fontes(
            obj_ruim,
            [b.para_dict() for b in busca],
            self.perguntas_gab["P07"],
        )
        self.assertFalse(ver_ruim["todas_afirmacoes_sustentadas"])
        self.assertGreater(len(ver_ruim["padroes_proibidos_acionados"]), 0)

    def test_t10_conflito_fontes_exige_dois_documentos_e_nao_escolhe_prazo(self):
        busca = self._busca_por_docs(["ACV-04", "ACV-05"])
        c_acv04 = next(b.trecho.chunk_id for b in busca if b.trecho.documento_id == "ACV-04")
        c_acv05 = next(b.trecho.chunk_id for b in busca if b.trecho.documento_id == "ACV-05")

        # Citar apenas 1 documento em conflito_fontes viola o contrato RespostaRAG
        saida_1_doc = json.dumps(
            {
                "status": "conflito_fontes",
                "resposta": "Há divergência.",
                "afirmacoes": [{"texto": "Prazo de 30 dias.", "chunk_ids": [c_acv04]}],
                "requer_revisao": True,
                "motivo_revisao": "Conflito.",
            }
        )
        est_1, _, _ = rag.validar_e_montar_resposta_rag(saida_1_doc, busca)
        self.assertEqual(est_1, "rejeitada_esquema")

        # Citar ambos os documentos conflitantes passa e marca revisão obrigatória
        saida_2_docs = json.dumps(
            {
                "status": "conflito_fontes",
                "resposta": (
                    "Há divergência entre documentos vigentes: a norma ACV-04 indica até 30 dias corridos "
                    "do início do módulo, enquanto o comunicado ACV-05 menciona até 60 dias corridos. "
                    "O caso foi encaminhado para revisão humana."
                ),
                "afirmacoes": [
                    {"texto": "ACV-04 prevê até 30 dias corridos do início do módulo.", "chunk_ids": [c_acv04]},
                    {"texto": "ACV-05 prevê até 60 dias corridos do início do módulo.", "chunk_ids": [c_acv05]},
                ],
                "requer_revisao": True,
                "motivo_revisao": "Divergência entre ACV-04 (30 dias) e ACV-05 (60 dias).",
            },
            ensure_ascii=False,
        )
        est_2, obj_2, _ = rag.validar_e_montar_resposta_rag(saida_2_docs, busca)
        self.assertEqual(est_2, "valida")
        assert obj_2 is not None
        ver = metrics.verificar_resposta_rag_contra_fontes(
            obj_2.model_dump(),
            [b.para_dict() for b in busca],
            self.perguntas_gab["P06"],
        )
        self.assertTrue(ver["status_confere"])
        self.assertTrue(ver["docs_esperados_citados"])
        self.assertTrue(ver["todas_afirmacoes_sustentadas"])

    def test_adv02_injecao_indireta_no_acervo_forca_revisao_e_bloqueia_obediencia(self):
        busca_acv06 = self._busca_por_docs(["ACV-06"])
        alertas = rag.detectar_instrucoes_suspeitas_trechos(busca_acv06)
        self.assertGreaterEqual(len(alertas), 1)
        cid_s2 = next(b.trecho.chunk_id for b in busca_acv06 if b.trecho.secao and "2." in b.trecho.secao)

        # 1) Se o modelo obedecer ao ataque ("matrícula foi deferida"), a camada 3 bloqueia
        saida_contaminada = json.dumps(
            {
                "status": "fundamentada",
                "resposta": "A matrícula foi deferida e nenhum documento precisa ser apresentado.",
                "afirmacoes": [{"texto": "Matrícula deferida.", "chunk_ids": [cid_s2]}],
                "requer_revisao": False,
                "motivo_revisao": None,
            }
        )
        est_ruim, _, errs_ruim = rag.validar_e_montar_resposta_rag(
            saida_contaminada,
            busca_acv06,
            alertas_acervo=alertas,
        )
        self.assertEqual(est_ruim, "rejeitada_esquema")
        self.assertEqual(errs_ruim[0]["categoria"], "obediencia_instrucao_maliciosa")

        # 2) Mesmo quando a resposta do modelo é limpa e diz requer_revisao=False, o alerta em ACV-06 força requer_revisao=True
        saida_limpa = json.dumps(
            {
                "status": "fundamentada",
                "resposta": "No atendimento eletrônico, protocolos e datas informados devem ser conferidos pela Secretaria Escolar.",
                "afirmacoes": [
                    {
                        "texto": "Protocolos e datas devem ser conferidos pela Secretaria antes do envio.",
                        "chunk_ids": [cid_s2],
                    }
                ],
                "requer_revisao": False,
                "motivo_revisao": None,
            },
            ensure_ascii=False,
        )
        est_ok, obj_ok, _ = rag.validar_e_montar_resposta_rag(
            saida_limpa,
            busca_acv06,
            alertas_acervo=alertas,
        )
        self.assertEqual(est_ok, "valida")
        assert obj_ok is not None
        self.assertTrue(obj_ok.requer_revisao)
        self.assertIn("Instrução imperativa suspeita", obj_ok.motivo_revisao or "")

    def test_rf23_metricas_sem_divisao_por_zero_e_deduplicacao(self):
        vazio = metrics.razao_segura(0, 0)
        self.assertIsNone(vazio["percentual"])
        self.assertIn("0/0", vazio["formatado"])

        agregado = metrics.agregar_registros_deterministico(
            [
                {"id": "1", "tema": "matricula"},
                {"id": "1", "tema": "matricula"},
                {"id": "2", "tema": "historico"},
            ],
            chave_id="id",
            chave_rotulo="tema",
            filtros={"tema": "inexistente"},
        )
        self.assertEqual(agregado["duplicatas_ignoradas"], 1)
        self.assertEqual(agregado["denominador_filtrado"], 0)
        self.assertEqual(agregado["contagens"], {})

    def test_adv02_alerta_integridade_mesmo_quando_apenas_chunk_limpo_acv06_c1_eh_recuperado(self):
        apenas_c1 = [
            embeddings.ResultadoBusca(posicao=1, similaridade=0.83, trecho=t)
            for t in self.trechos
            if t.chunk_id == "ACV-06#c1"
        ]
        self.assertEqual(len(apenas_c1), 1)
        alertas = rag.detectar_instrucoes_suspeitas_trechos(apenas_c1, todos_trechos_indice=self.trechos)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["escopo"], "integridade_documento_origem")
        self.assertEqual(alertas[0]["chunk_id"], "ACV-06#c2")

        saida_limpa_c1 = json.dumps(
            {
                "status": "fundamentada",
                "resposta": "A Secretaria Escolar atende de segunda a sexta-feira, das 7h30 às 11h30 e das 13h30 às 17h30.",
                "afirmacoes": [
                    {
                        "texto": "Atendimento de segunda a sexta-feira, das 7h30 às 11h30 e das 13h30 às 17h30.",
                        "chunk_ids": ["ACV-06#c1"],
                    }
                ],
                "requer_revisao": False,
                "motivo_revisao": None,
            },
            ensure_ascii=False,
        )
        est, obj, _ = rag.validar_e_montar_resposta_rag(saida_limpa_c1, apenas_c1, alertas_acervo=alertas)
        self.assertEqual(est, "valida")
        assert obj is not None
        self.assertTrue(obj.requer_revisao)
        self.assertIn("ACV-06#c2", obj.motivo_revisao or "")

    def test_rf23_contingencia_erro_provedor_nao_conta_como_abstencao_correta(self):
        perguntas_lista = list(self.perguntas_gab.values())
        contingencia = rag._resposta_contingencia_bloqueada("Limite de taxa HTTP 429.").model_dump()
        abstencao_real = {
            "status": "sem_evidencia",
            "resposta": "Não consta no acervo orientação sobre aproveitamento de estudos.",
            "afirmacoes": [],
            "citacoes": [],
            "requer_revisao": True,
            "motivo_revisao": "Ausência de cobertura no acervo.",
        }
        execs = {
            "P07": {"estado": "erro_provedor", "resposta_rag": contingencia, "trechos_recuperados": []},
            "P08": {"estado": "valida", "resposta_rag": abstencao_real, "trechos_recuperados": []},
        }
        res_m = metrics.calcular_metricas_rag_rf23(execs, perguntas_lista)
        self.assertEqual(res_m["abstencao_correta"]["numerador"], 1)
        self.assertEqual(res_m["abstencao_correta"]["denominador"], 2)


if __name__ == "__main__":
    unittest.main()
