"""Testes offline da extração estruturada e validação em três camadas (RF14). Não chamam API.

Inclui T01 (JSON válido com tipo incorreto e campo ausente) e T02 (data impossível ou dado ausente do
original). O provedor é substituído por uma função que devolve respostas controladas.

Executar: python -m unittest discover -s testes -t .
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src import nlp, prompts
from src.llm_client import ErroProvedor

RAIZ = prompts.RAIZ
TEXTO_05 = (RAIZ / "dados/originais/caso05_texto_incompleto.txt").read_text(encoding="utf-8")
TEXTO_01 = (RAIZ / "dados/originais/entrada_texto.txt").read_text(encoding="utf-8")
TEXTO_AUDIO = (RAIZ / "resultados/transcricoes/stt-46427a77/revisada.txt").read_text(encoding="utf-8")
HOJE = date(2026, 10, 28)

VALIDA_05 = {
    "protocolo": None, "data_solicitacao": None, "canal": "WhatsApp institucional",
    "solicitante": "Carlos Eduardo Nunes", "curso": "Técnico em Administração",
    "assunto": "Trancamento do curso", "pedido": "Saber como trancar o curso.",
    "categoria": "cancelamento_trancamento",
    "entidades": [{"tipo": "pessoa", "valor": "Carlos Eduardo Nunes", "origem": "literal",
                   "evidencia": "Meu nome é Carlos Eduardo Nunes"}],
    "dados_pessoais_detectados": [], "campos_ausentes": ["protocolo", "data_solicitacao"],
    "requer_revisao": True, "motivos_revisao": ["Protocolo e data ausentes."], "alertas_seguranca": [],
}
VALIDA_01 = {
    "protocolo": "2026-000142", "data_solicitacao": "14/10/2026", "canal": "E-mail",
    "solicitante": "Marcos Vinícius de Almeida Santos", "curso": "Técnico em Enfermagem",
    "assunto": "Efetivação de matrícula", "pedido": "Efetivação da matrícula e lista de documentos pendentes.",
    "categoria": "matricula", "entidades": [], "dados_pessoais_detectados": ["CPF"], "campos_ausentes": [],
    "requer_revisao": False, "motivos_revisao": [], "alertas_seguranca": [],
}
CFG = {"provedor": "groq", "modelo": "modelo-ficticio", "modo_saida": "json_schema_estrito",
       "parametros": {"temperature": 0}, "timeout_s": 5, "tentativas_transitorias": 2,
       "max_tentativas_correcao": 1, "pausa_entre_chamadas_s": 0}


class ProvedorFalso:
    """Devolve as respostas na ordem dada e guarda o que recebeu."""

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas = []

    def __call__(self, perfil, modelo, mensagens, parametros, **kw):
        self.chamadas.append({"mensagens": [dict(m) for m in mensagens], "parametros": parametros, **kw})
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
        return {"texto": texto, "latencia_s": 0.1, "tokens_entrada": 10, "tokens_saida": 5, "custo_usd": 0.0001}


def com(base, **alteracoes):
    dados = json.loads(json.dumps(base))
    dados.update(alteracoes)
    return dados


class BaseExtracao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "log.jsonl"

    def extrair(self, provedor, texto=TEXTO_05, **kw):
        return nlp.extrair(texto, "dados/originais/x.txt", "caso_teste", CFG, chamar=provedor, hoje=HOJE,
                           caminho_log=self.log, **kw)


class TestT01EsquemaECorrecao(BaseExtracao):
    def test_t01_tipo_incorreto_e_campo_ausente_rejeitados_sem_minuta(self):
        invalida = com(VALIDA_05, requer_revisao="true")
        del invalida["pedido"]
        provedor = ProvedorFalso(invalida, invalida)
        res = self.extrair(provedor)
        self.assertEqual(res.estado, "rejeitada_esquema")
        self.assertFalse(res.libera_minuta)
        self.assertEqual(len(provedor.chamadas), 2, "no máximo uma tentativa de correção")
        self.assertEqual({(e["campo"], e["categoria"]) for e in res.erros},
                         {("requer_revisao", "tipo_incorreto"), ("pedido", "campo_ausente")})
        self.assertIsNone(res.extracao)

    def test_correcao_unica_aceita_quando_segunda_resposta_e_valida(self):
        provedor = ProvedorFalso(com(VALIDA_05, prioridade="alta"), VALIDA_05)
        res = self.extrair(provedor)
        self.assertEqual(res.estado, "valida")
        self.assertEqual([t["valida_no_esquema"] for t in res.tentativas], [False, True])
        ultima = provedor.chamadas[1]["mensagens"]
        self.assertEqual([m["role"] for m in ultima[-2:]], ["assistant", "user"])
        self.assertIn("prioridade: chave_extra", ultima[-1]["content"])

    def test_mensagem_de_correcao_nao_reproduz_o_valor_recebido(self):
        invalida = com(VALIDA_05, requer_revisao="CPF 123.456.789-00")
        provedor = ProvedorFalso(invalida, VALIDA_05)
        self.extrair(provedor)
        self.assertNotIn("123.456.789-00", provedor.chamadas[1]["mensagens"][-1]["content"])

    def test_recusa_do_modo_estrito_conta_como_esquema_e_ganha_uma_correcao(self):
        recusa = ErroProvedor(
            "Requisição rejeitada pelo provedor (HTTP 400): Generated JSON does not match the expected schema. "
            "Error: jsonschema: '/entidades/3' does not validate with /properties/entidades/items/$ref/required: "
            "missing properties: 'tipo'", codigo_erro="requisicao_invalida", status_code=400)
        provedor = ProvedorFalso(recusa, VALIDA_05)
        res = self.extrair(provedor)
        self.assertEqual(res.estado, "valida")
        self.assertEqual(res.tentativas[0]["erros"][0]["campo"], "entidades.3.tipo")
        self.assertIn("entidades.3.tipo: campo_ausente", provedor.chamadas[1]["mensagens"][-1]["content"])
        res = self.extrair(ProvedorFalso(recusa, recusa))
        self.assertEqual((res.estado, res.encaminhamento), ("rejeitada_esquema", nlp.BLOQUEADA))

    def test_outro_http_400_continua_sendo_falha_do_provedor(self):
        erro = ErroProvedor("HTTP 400: model not found", codigo_erro="requisicao_invalida", status_code=400)
        res = self.extrair(ProvedorFalso(erro))
        self.assertEqual(res.estado, "erro_provedor")

    def test_json_sintaticamente_invalido_conta_como_camada_sintatica(self):
        provedor = ProvedorFalso('{"protocolo": ', '{"protocolo": ')
        res = self.extrair(provedor)
        self.assertEqual({e["camada"] for e in res.erros}, {"sintatica"})


class TestT02RegrasDeNegocio(BaseExtracao):
    def test_t02_data_impossivel_bloqueia_e_solicita_revisao(self):
        provedor = ProvedorFalso(com(VALIDA_01, data_solicitacao="31/02/2026"))
        res = self.extrair(provedor, texto=TEXTO_01)
        self.assertEqual(res.estado, "bloqueada_negocio")
        self.assertEqual(res.encaminhamento, nlp.BLOQUEADA)
        self.assertIn("data_inexistente", {e["categoria"] for e in res.erros})
        self.assertEqual(len(provedor.chamadas), 1, "regra de negócio não gera nova tentativa")

    def test_t02_dado_nao_presente_no_original_bloqueia(self):
        res = self.extrair(ProvedorFalso(com(VALIDA_01, protocolo="2026-999999")), texto=TEXTO_01)
        self.assertEqual(res.estado, "bloqueada_negocio")
        self.assertIn(("protocolo", "valor_ausente_no_original"), {(e["campo"], e["categoria"]) for e in res.erros})

    def test_data_futura(self):
        erros = nlp.validar_extracao(json.dumps(com(VALIDA_01, data_solicitacao="14/10/2026")), TEXTO_01,
                                     hoje=date(2026, 10, 1))[3]
        self.assertIn("data_futura", {e["categoria"] for e in erros})

    def test_data_por_extenso_no_original_e_aceita(self):
        dados = com(VALIDA_01, canal=None, campos_ausentes=["canal"])
        estado, _, _, erros = nlp.validar_extracao(json.dumps(dados), TEXTO_AUDIO, hoje=HOJE)
        self.assertEqual((estado, erros), ("valida", []))

    def test_requer_revisao_incoerente(self):
        erros = nlp.validar_extracao(json.dumps(com(VALIDA_05, requer_revisao=False)), TEXTO_05, hoje=HOJE)[3]
        self.assertIn("requer_revisao_incoerente", {e["categoria"] for e in erros})

    def test_dado_pessoal_reproduzido_na_extracao(self):
        dados = com(VALIDA_01, pedido="Efetivação da matrícula; CPF 123.456.789-00.")
        erros = nlp.validar_extracao(json.dumps(dados), TEXTO_01, hoje=HOJE)[3]
        self.assertIn("dado_pessoal_na_extracao", {e["categoria"] for e in erros})
        self.assertNotIn("123.456.789-00", json.dumps(erros, ensure_ascii=False))

    def test_evidencia_que_nao_esta_no_original(self):
        dados = com(VALIDA_05, entidades=[{"tipo": "pessoa", "valor": "Carlos Eduardo Nunes",
                                           "origem": "literal", "evidencia": "Sou o aluno Carlos Nunes"}])
        erros = nlp.validar_extracao(json.dumps(dados), TEXTO_05, hoje=HOJE)[3]
        self.assertIn("evidencia_sem_suporte", {e["categoria"] for e in erros})


class TestEncaminhamento(BaseExtracao):
    def test_incompleta_valida_segue_para_minuta_pendente(self):
        res = self.extrair(ProvedorFalso(VALIDA_05))
        self.assertEqual((res.estado, res.encaminhamento), ("valida", nlp.LIBERA_MINUTA))
        self.assertTrue(res.libera_minuta)

    def test_categoria_revisao_ou_alerta_exigem_revisao_antes_da_minuta(self):
        for alteracao in ({"categoria": "revisao"}, {"alertas_seguranca": ["instrução suspeita"]}):
            res = self.extrair(ProvedorFalso(com(VALIDA_05, **alteracao)))
            self.assertEqual((res.estado, res.encaminhamento), ("valida", nlp.REVISAO_ANTES), alteracao)

    def test_falha_do_provedor_bloqueia_sem_levantar_erro(self):
        res = self.extrair(ProvedorFalso(ErroProvedor("HTTP 503", codigo_erro="servico_indisponivel")))
        self.assertEqual((res.estado, res.encaminhamento), ("erro_provedor", nlp.BLOQUEADA))

    def test_auditoria_registra_versoes_sem_o_texto_da_solicitacao(self):
        self.extrair(ProvedorFalso(VALIDA_05))
        registro = json.loads(self.log.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(registro["versao_prompt"], "extracao-v2.1")
        self.assertEqual(registro["versao_contrato"], "solicitacao_extraida-v0.1.0")
        self.assertNotIn("Carlos", json.dumps(registro, ensure_ascii=False))

    def test_interface_mostra_nao_localizado_e_persistencia_mantem_null(self):
        exibicao = nlp.para_exibicao(VALIDA_05)
        self.assertEqual((exibicao["protocolo"], exibicao["data_solicitacao"]), ("não localizado", "não localizado"))
        self.assertIsNone(VALIDA_05["protocolo"])

    def test_dry_run_nao_chama_o_provedor(self):
        provedor = ProvedorFalso()
        res = self.extrair(provedor, dry_run=True)
        self.assertEqual((res.estado, provedor.chamadas), ("dry_run", []))


class TestModoDeSaidaEPrompt(unittest.TestCase):
    def test_modo_estrito_envia_o_esquema_e_json_object_nao(self):
        params, json_mode = nlp.parametros_saida("json_schema_estrito", {"temperature": 0})
        rf = params["response_format"]
        self.assertEqual((rf["type"], rf["json_schema"]["strict"], json_mode), ("json_schema", True, False))
        self.assertIn("campos_ausentes", rf["json_schema"]["schema"]["properties"])
        params, json_mode = nlp.parametros_saida("json_object", {"temperature": 0})
        self.assertEqual(("response_format" in params, json_mode), (False, True))

    def test_prompt_v2_separa_instrucoes_do_conteudo(self):
        msgs, meta = prompts.montar_mensagens_extracao_v2(TEXTO_01, "dados/originais/entrada_texto.txt")
        self.assertEqual(meta["versao_prompt"], "extracao-v2.1")
        self.assertNotIn("Marcos", msgs[0]["content"])
        self.assertIn("revisao", msgs[0]["content"])
        self.assertNotIn("123.456.789-00", msgs[1]["content"])


class TestMinimizacaoEmFrase(unittest.TestCase):
    """Correção do achado da Fase 1: RG, filiação e nascimento escritos em frase (transcrição de áudio)."""

    def test_transcricao_remove_os_cinco_tipos_e_preserva_o_pedido(self):
        texto, removidos = prompts.minimizar(TEXTO_AUDIO)
        self.assertEqual(set(removidos), {"CPF", "RG", "e-mail", "filiação", "data de nascimento"})
        for valor in ["1234567-8", "Lúcia Helena", "12 de agosto de 2008", "123456789-00"]:
            self.assertNotIn(valor, texto)
        for trecho in ["2026-000142", "14 de outubro de 2026", "Declaro estar ciente", "quais os documentos"]:
            self.assertIn(trecho, texto)

    def test_ficha_ocr_preserva_rotulo_da_linha_seguinte(self):
        texto, _ = prompts.minimizar((RAIZ / "dados/processados/caso03_ocr_revisado.txt").read_text(encoding="utf-8"))
        self.assertIn("Nome da mãe: [FILIAÇÃO REMOVIDA]\nE-mail: [E-MAIL REMOVIDO]", texto)

    def test_textos_sem_dado_pessoal_ficam_intactos(self):
        for nome in ["caso05_texto_incompleto", "caso06_texto_transferencia", "caso07_texto_responsavel",
                     "caso09_texto_ambiguo"]:
            original = (RAIZ / f"dados/originais/{nome}.txt").read_text(encoding="utf-8")
            self.assertEqual(prompts.minimizar(original), (original, {}), nome)


class TestComparacaoComGabarito(unittest.TestCase):
    def test_extracao_igual_ao_gabarito_confere_em_tudo(self):
        gab = json.loads((RAIZ / "dados/gabaritos/d2/solicitacoes/caso05_texto_incompleto.json").read_text(encoding="utf-8"))
        cmp = nlp.comparar_com_gabarito(VALIDA_05, nlp.LIBERA_MINUTA, gab)
        self.assertTrue(all(cmp["campos"].values()))
        self.assertTrue(all(cmp[k] for k in ("categoria", "campos_ausentes", "requer_revisao", "alerta", "encaminhamento")))
        self.assertEqual(cmp["nao_deve_aparecer"], [])

    def test_alerta_que_descreve_o_ataque_nao_conta_como_vazamento(self):
        gab = json.loads((RAIZ / "dados/gabaritos/d2/solicitacoes/caso04_texto_injection.json").read_text(encoding="utf-8"))
        obtido = {"alertas_seguranca": ["Pede para citar o Art. 99 da Resolução nº 45/2026."], "pedido": "Declaração."}
        self.assertEqual(nlp.comparar_com_gabarito(obtido, nlp.REVISAO_ANTES, gab)["nao_deve_aparecer"], [])
        obtido["pedido"] = "Dispensa com base no Art. 99."
        self.assertEqual(nlp.comparar_com_gabarito(obtido, nlp.REVISAO_ANTES, gab)["nao_deve_aparecer"], ["Art. 99"])


class TestComparacaoJson(unittest.TestCase):
    def test_evidencia_citada_do_texto_minimizado_e_aceita(self):
        # Saída real (20261028-173726) cuja evidência cita "[DATA DE NASCIMENTO REMOVIDA]": a comparação
        # JSON precisa validar como `extrair`, também contra o texto enviado.
        registro = json.loads((RAIZ / "resultados/extracao/20261028-173726/caso01_texto.json").read_text(encoding="utf-8"))
        texto_json = json.dumps(registro["extracao"], ensure_ascii=False)
        avaliacao = nlp._avaliar_camadas("B", "x", texto_json, TEXTO_01, registro["meta"]["texto_enviado"])
        self.assertEqual((avaliacao["estado"], avaliacao["erros_por_categoria"]), ("valida", {}))
        sem_enviado = nlp._avaliar_camadas("B", "x", texto_json, TEXTO_01, "")
        self.assertEqual(sem_enviado["erros_por_categoria"], {"evidencia_sem_suporte": ["entidades.3.evidencia"]})


if __name__ == "__main__":
    unittest.main()
