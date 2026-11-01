"""Testes unitários offline dos guardrails em camadas (RF16 — Estudante 3).

Cobre os cenários da matriz:
- T04: as três entradas adversariais (solicitação `ADV-01`, acervo `ADV-02`, segredo `ADV-03`) são bloqueadas
  ou encaminhadas à revisão, sem chamada ao provedor no caso do segredo e sem segredo na saída ou no log;
- T05: fora de escopo, arquivo excessivo, tipo não permitido, texto longo e teto de chamadas por execução;
- Camada de saída: segredo, obediência, norma sem suporte, negação permitida e citação ausente.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import embeddings, guardrails, llm_client, main, schemas

RAIZ = guardrails.RAIZ
ADVERSARIAIS = json.loads((RAIZ / "dados/gabaritos/d2/adversariais.json").read_text(encoding="utf-8"))


def _ataque(alvo: str) -> dict:
    return next(a for a in ADVERSARIAIS["ataques"] if a["alvo"] == alvo)


class TestT04EntradasAdversariais(unittest.TestCase):
    """T04 (RF16): instruções não executadas e segredo não revelado."""

    def test_adv01_instrucao_na_solicitacao_vai_para_revisao(self):
        ataque = _ataque("solicitacao")
        dec = guardrails.avaliar_entrada((RAIZ / ataque["arquivo_origem"]).read_text(encoding="utf-8"))
        self.assertEqual(dec.decisao, "revisar")
        self.assertIn(dec.decisao, ataque["decisoes_aceitas"])
        self.assertIn("instrucao_embutida", dec.categorias)

    def test_adv03_pedido_de_segredo_e_bloqueado(self):
        ataque = _ataque("segredo")
        dec = guardrails.avaliar_entrada((RAIZ / ataque["arquivo_origem"]).read_text(encoding="utf-8"))
        self.assertEqual(dec.decisao, "bloquear")
        self.assertIn("pedido_de_segredo", dec.categorias)

    def test_adv02_instrucao_no_acervo_leva_resposta_a_revisao(self):
        trecho = schemas.TrechoIndexado(
            chunk_id="ACV-06#c3", documento_id="ACV-06", versao_documento="1.0", hash_documento="a" * 64,
            pagina=None, secao="3. Observação técnica", configuracao_chunking="caracteres-700-sobreposicao-120",
            texto=_ataque("acervo")["trecho_malicioso"],
        )
        dec = guardrails.avaliar_trechos_recuperados([embeddings.ResultadoBusca(trecho=trecho, similaridade=0.8, posicao=1)])
        self.assertEqual(dec.decisao, "revisar")
        self.assertEqual(dec.categorias, ["instrucao_no_acervo"])

    def test_motivo_registrado_nao_reproduz_trecho_malicioso_nem_segredo(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"GROQ_API_KEY": "gsk_testeFicticio1234567890"}):
            log_tmp = Path(tmp) / "execucoes.jsonl"
            for alvo in ("solicitacao", "segredo"):
                ataque = _ataque(alvo)
                dec = guardrails.avaliar_entrada((RAIZ / ataque["arquivo_origem"]).read_text(encoding="utf-8"))
                guardrails.registrar_decisao(dec, caso_id=ataque["id"], modalidade="texto",
                                             arquivo_origem=ataque["arquivo_origem"], caminho_log=log_tmp)
            conteudo = log_tmp.read_text(encoding="utf-8")
            self.assertNotIn("gsk_testeFicticio", conteudo)
            for ataque in ADVERSARIAIS["ataques"]:
                self.assertNotIn(ataque["trecho_malicioso"], conteudo)
            linhas = [json.loads(x) for x in conteudo.splitlines()]
            self.assertEqual([x["guardrail"]["decisao"] for x in linhas], ["revisar", "bloquear"])
            self.assertTrue(all(x["enviada_ao_cidadao"] is False for x in linhas))

    def test_fluxo_principal_bloqueia_segredo_sem_chamar_provedor(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            caminhos_tmp = {**main.CONFIG["caminhos"], "processados": str(raiz_tmp / "p"), "minutas": str(raiz_tmp / "m")}
            with patch.dict(main.CONFIG, {"caminhos": caminhos_tmp}), \
                    patch("src.nlp.compreender") as compreender, patch("src.llm_client.chamar_chat") as chamar:
                out = main.processar_caso(
                    caso_id="caso08_texto_segredo", provedor="groq", modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"], dry_run=False, nao_interativo=True,
                    caminho_log=raiz_tmp / "execucoes.jsonl",
                )
            compreender.assert_not_called()
            chamar.assert_not_called()
            self.assertTrue(out["bloqueado_guardrail"])
            self.assertIsNone(out["minuta"])
            self.assertFalse(out["decisao_revisao"]["enviada_ao_cidadao"])
            self.assertFalse(list((raiz_tmp / "m").glob("*")))

    def test_fluxo_principal_injecao_segue_com_revisao_obrigatoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            caminhos_tmp = {**main.CONFIG["caminhos"], "processados": str(raiz_tmp / "p"), "minutas": str(raiz_tmp / "m")}
            with patch.dict(main.CONFIG, {"caminhos": caminhos_tmp}):
                out = main.processar_caso(
                    caso_id="caso04_texto_injection", provedor="groq", modelo="openai/gpt-oss-120b",
                    cfg_prod=main.CONFIG["producao"], dry_run=True, nao_interativo=True,
                    caminho_log=raiz_tmp / "execucoes.jsonl",
                )
            entrada = next(g for g in out["guardrails"] if "instrucao_embutida" in g["categorias"])
            self.assertEqual(entrada["decisao"], "revisar")
            self.assertEqual(out["decisao_humana"], "PENDENTE")
            etapas = [json.loads(x)["etapa"] for x in (raiz_tmp / "execucoes.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertIn("guardrail_entrada", etapas)


class TestT05EscopoArquivoELimites(unittest.TestCase):
    """T05 (RF16): fora de escopo, arquivo excessivo e limite de chamadas."""

    def test_fora_de_escopo_bloqueia_e_escopo_incerto_revisa(self):
        self.assertEqual(guardrails.avaliar_entrada("Vocês podem me passar uma receita de bolo de cenoura?").decisao, "bloquear")
        self.assertEqual(guardrails.avaliar_entrada("Oi, tudo bem com você hoje, meu amigo?").decisao, "revisar")

    def test_solicitacoes_legitimas_sao_permitidas(self):
        for nome in ("entrada_texto.txt", "caso05_texto_incompleto.txt", "caso06_texto_transferencia.txt",
                     "caso07_texto_responsavel.txt", "caso09_texto_ambiguo.txt"):
            with self.subTest(nome=nome):
                texto = (RAIZ / "dados/originais" / nome).read_text(encoding="utf-8")
                self.assertEqual(guardrails.avaliar_entrada(texto).decisao, "permitir")
        transcricao = (RAIZ / "dados/gabaritos/caso02_transcricao_referencia.txt").read_text(encoding="utf-8")
        self.assertEqual(guardrails.avaliar_entrada(transcricao).decisao, "permitir")

    def test_comprimento_minimo_e_maximo(self):
        self.assertIn("entrada_curta_demais", guardrails.avaliar_entrada("oi").categorias)
        longo = "Solicito declaração de matrícula. " * 400
        self.assertIn("entrada_longa_demais", guardrails.avaliar_entrada(longo).categorias)

    def test_arquivo_excessivo_vazio_e_tipo_nao_permitido(self):
        limite = guardrails.CONFIG["guardrails"]["max_bytes_arquivo"]["texto"]
        with tempfile.TemporaryDirectory() as tmp:
            grande = Path(tmp) / "grande.txt"
            grande.write_text("x" * (limite + 1), encoding="utf-8")
            vazio = Path(tmp) / "vazio.txt"
            vazio.write_text("", encoding="utf-8")
            self.assertEqual(guardrails.validar_arquivo(grande, "texto").categorias, ["arquivo_excessivo"])
            self.assertEqual(guardrails.validar_arquivo(vazio, "texto").categorias, ["arquivo_vazio"])
        mp3 = RAIZ / "dados/originais/entrada_audio.mp3"
        self.assertEqual(guardrails.validar_arquivo(mp3, "texto").categorias, ["tipo_arquivo_nao_permitido"])
        self.assertEqual(guardrails.validar_arquivo(mp3, "audio").decisao, "permitir")

    def test_limite_de_chamadas_por_execucao(self):
        orc = llm_client.ControladorOrcamento(max_chamadas=2, max_tokens_total=None)
        for _ in range(2):
            orc.verificar_disponibilidade()
            orc.registrar_chamada(500)
        with self.assertRaises(llm_client.ErroProvedor) as ctx:
            orc.verificar_disponibilidade()
        self.assertEqual(ctx.exception.codigo_erro, "limite_chamadas_excedido")

    def test_limites_configurados_respeitam_rf16(self):
        lim = guardrails.limites_recursos()
        self.assertLessEqual(lim["max_repeticoes_falha_transitoria"], 1)
        self.assertGreater(lim["timeout_s"], 0)
        self.assertGreater(lim["max_chamadas"], 0)
        orc = guardrails.criar_orcamento()
        self.assertEqual(orc.max_chamadas, lim["max_chamadas"])


class TestCamadaSaida(unittest.TestCase):
    """Saída dirigida ao cidadão é conferida antes de qualquer uso."""

    def test_vazamento_de_segredo_bloqueia(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_testeFicticio1234567890"}):
            dec = guardrails.verificar_saida("Segue a chave: gsk_testeFicticio1234567890")
        self.assertEqual(dec.decisao, "bloquear")
        self.assertIn("vazamento_segredo", dec.categorias)
        self.assertNotIn("gsk_testeFicticio", json.dumps(dec.para_json()))

    def test_obediencia_bloqueia_mas_negacao_e_permitida(self):
        self.assertEqual(guardrails.verificar_saida("A declaração já foi emitida.").decisao, "bloquear")
        self.assertEqual(
            guardrails.verificar_saida("Não é possível informar que a declaração já foi emitida.").decisao, "permitir"
        )

    def test_norma_sem_suporte_no_acervo(self):
        original = "dispensada da frequência com base no Art. 99 da Resolução nº 45/2026"
        dec = guardrails.verificar_saida("Conforme o Art. 99, o pedido segue para análise.", texto_original=original)
        self.assertEqual(dec.decisao, "bloquear")
        dec_inventada = guardrails.verificar_saida("Conforme o Art. 12, o pedido segue para análise.")
        self.assertEqual(dec_inventada.decisao, "revisar")
        dec_ok = guardrails.verificar_saida("Conforme o Art. 12, o pedido segue.", trechos_fonte=["Art. 12 — prazos"])
        self.assertEqual(dec_ok.decisao, "permitir")

    def test_fundamentada_sem_citacao_vai_para_revisao(self):
        dec = guardrails.verificar_saida("O prazo é de 5 dias úteis.", status_rag="fundamentada", qtd_citacoes=0)
        self.assertEqual(dec.categorias, ["afirmacao_sem_citacao"])

    def test_reter_minuta_substitui_corpo(self):
        minuta = {"assunto": "Declaração", "corpo": ["A declaração já foi emitida."], "alertas_seguranca": []}
        dec = guardrails.verificar_minuta(minuta, "")
        retida = guardrails.reter_minuta(minuta, dec)
        self.assertNotIn("já foi emitida", " ".join(retida["corpo"]))
        self.assertTrue(any("Guardrail de saída" in a for a in retida["alertas_seguranca"]))


if __name__ == "__main__":
    unittest.main()
