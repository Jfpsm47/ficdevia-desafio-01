"""Testes unitários offline de ingestão documental, embeddings, índice FAISS, chunking e exclusão (RF17, RF18, RF24).

Cobre os cenários da matriz:
- T06 (RF17): persistência, reutilização após reinício sem reprocessamento, reindexação sem duplicatas e
  exigência de reindexação ao trocar modelo/dimensão de embedding;
- T07 (RF18): comparação entre duas configurações de chunking com unidade declarada e acerto de recuperação;
- T14 (RF24): exclusão de documento, remoção de vetores e resultados derivados, persistência após recarga e auditoria.

Não realiza chamadas de rede nem carrega modelos pesados (usa `EmbeddingsDeterministicoTeste`).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import audit, embeddings, ingestion, metrics, schemas


class TestIngestaoAcervo(unittest.TestCase):
    """Valida extração de `.txt` e `.pdf` com páginas, seções, SHA-256 e contrato `TrechoIndexado`."""

    def test_carregar_catalogo_e_ingerir_acervo_txt_e_pdf(self):
        docs, trechos = ingestion.ingerir_acervo(tamanho=700, sobreposicao=120)
        self.assertEqual(len(docs), 6)
        self.assertGreaterEqual(len(trechos), 10)

        por_doc: dict[str, list[schemas.TrechoIndexado]] = {}
        for t in trechos:
            self.assertIsInstance(t, schemas.TrechoIndexado)
            self.assertEqual(t.configuracao_chunking, "caracteres-700-sobreposicao-120")
            self.assertEqual(len(t.hash_documento), 64)
            por_doc.setdefault(t.documento_id, []).append(t)

        # ACV-01 é PDF multipágina: deve preservar número de página >= 1 e seção numerada
        paginas_acv01 = {t.pagina for t in por_doc["ACV-01"]}
        self.assertIn(1, paginas_acv01)
        self.assertIn(2, paginas_acv01)
        self.assertTrue(any(t.secao and "Documentos" in t.secao for t in por_doc["ACV-01"]))

        # ACV-02 é TXT: pagina deve ser None e secao deve estar preenchida
        self.assertTrue(all(t.pagina is None for t in por_doc["ACV-02"]))
        self.assertTrue(any(t.secao for t in por_doc["ACV-02"]))

    def test_construir_e_incluir_documento_avulso_para_interface(self):
        with tempfile.TemporaryDirectory() as tmp:
            arq = Path(tmp) / "norma_teste.txt"
            arq.write_text("1. Regra Geral\n\nPrazo institucional fictício de 10 dias úteis.\n", encoding="utf-8")
            doc, paginas, hash_doc = ingestion.construir_documento_avulso(
                arq,
                documento_id="ACV-90",
                titulo="Norma Fictícia Avulsa",
                versao="1.0",
                tema="documentacao_escolar",
            )
            trechos = ingestion.dividir_documento_em_chunks(doc, paginas, hash_doc)
            self.assertEqual(doc.documento_id, "ACV-90")
            self.assertEqual(len(trechos), 1)
            self.assertEqual(trechos[0].secao, "1. Regra Geral")


class TestIndiceVetorialPersistente(unittest.TestCase):
    """Valida T06 (RF17): persistência, recarga após reinício, deduplicação e bloqueio por mudança de modelo."""

    def test_persistencia_recarga_deduplicacao_e_mudanca_modelo(self):
        embedder_v1 = embeddings.EmbeddingsDeterministicoTeste(modelo="emb-teste-v1", dimensao=64)

        with tempfile.TemporaryDirectory() as tmp:
            dir_idx = Path(tmp) / "indice_t06"
            idx = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embedder_v1,
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            res_1 = idx.indexar_acervo()
            self.assertEqual(res_1["indexados_ou_atualizados"], 6)
            self.assertEqual(res_1["reutilizados_sem_duplicar"], 0)
            self.assertTrue((dir_idx / "index.faiss").is_file())
            self.assertTrue((dir_idx / "trechos.json").is_file())
            self.assertTrue((dir_idx / "manifesto.json").is_file())

            total_vetores_inicial = idx.total_vetores
            versao_inicial = idx.versao_indice

            # Simula reinício de processo: recarrega do disco sem re-gerar vetores
            idx_reiniciado = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embedder_v1,
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            self.assertTrue(idx_reiniciado.carregado_do_disco)
            self.assertFalse(idx_reiniciado.desatualizado)
            self.assertEqual(idx_reiniciado.total_vetores, total_vetores_inicial)
            self.assertEqual(idx_reiniciado.versao_indice, versao_inicial)

            achados = idx_reiniciado.buscar("Quais documentos são exigidos para a matrícula?", top_k=3)
            self.assertEqual(len(achados), 3)
            self.assertEqual(achados[0].metrica, "similaridade_cosseno")
            self.assertGreaterEqual(achados[0].similaridade, achados[1].similaridade)

            # T06: reindexar o mesmo acervo reutiliza todos os documentos pelo SHA-256 sem duplicar entradas
            res_2 = idx_reiniciado.indexar_acervo()
            self.assertEqual(res_2["indexados_ou_atualizados"], 0)
            self.assertEqual(res_2["reutilizados_sem_duplicar"], 6)
            self.assertEqual(idx_reiniciado.total_vetores, total_vetores_inicial)
            self.assertEqual(idx_reiniciado.versao_indice, versao_inicial)

            # Troca de modelo ou dimensão de embedding marca índice como desatualizado e bloqueia busca até reindexar
            embedder_v2 = embeddings.EmbeddingsDeterministicoTeste(modelo="emb-teste-v2", dimensao=128)
            idx_desatualizado = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embedder_v2,
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            self.assertTrue(idx_desatualizado.desatualizado)
            with self.assertRaises(embeddings.ErroIndiceDesatualizado):
                idx_desatualizado.buscar("Qualquer pergunta", top_k=2)


class TestComparacaoChunking(unittest.TestCase):
    """Valida T07 (RF18): comparação entre duas configurações de chunking preservando metadados."""

    def test_duas_configuracoes_preservam_metadados_e_calculam_acerto(self):
        embedder = embeddings.EmbeddingsDeterministicoTeste(dimensao=64)
        gab = metrics.carregar_perguntas_rag()
        perguntas_resp = [p for p in gab["perguntas"] if p["tipo"] == "respondivel"]
        self.assertEqual(len(perguntas_resp), 5)

        with tempfile.TemporaryDirectory() as tmp:
            resultados = {}
            for nome, tam, sob in (("granular", 320, 50), ("contextual", 700, 120)):
                rotulo = ingestion.formatar_config_chunking("caracteres", tam, sob)
                idx = embeddings.IndiceVetorial(
                    diretorio=Path(tmp) / nome,
                    embedder=embedder,
                    tamanho_chunk=tam,
                    sobreposicao_chunk=sob,
                )
                idx.indexar_acervo()
                self.assertTrue(all(t.configuracao_chunking == rotulo for t in idx.trechos))
                buscas = {p["id"]: [r.para_dict() for r in idx.buscar(p["pergunta"], top_k=4)] for p in perguntas_resp}
                av = metrics.calcular_acerto_recuperacao(buscas, perguntas_resp)
                self.assertEqual(av["acerto_recuperacao"]["denominador"], 5)
                resultados[nome] = av

            self.assertIn("resultados_por_pergunta", resultados["granular"])
            self.assertIn("resultados_por_pergunta", resultados["contextual"])


class TestExclusaoDocumentoEDerivados(unittest.TestCase):
    """Valida T14 (RF24): exclusão de documento, vetores e derivados + registro de auditoria."""

    def test_excluir_documento_remove_vetores_derivados_e_registra_log(self):
        embedder = embeddings.EmbeddingsDeterministicoTeste(dimensao=64)

        with tempfile.TemporaryDirectory() as tmp:
            raiz_tmp = Path(tmp)
            dir_idx = raiz_tmp / "indice"
            dir_derivados = raiz_tmp / "derivados"
            log_audit = raiz_tmp / "execucoes.jsonl"
            dir_derivados.mkdir(parents=True)

            idx = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embedder,
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            idx.indexar_acervo()
            total_antes = idx.total_vetores
            qtd_acv03 = sum(1 for t in idx.trechos if t.documento_id == "ACV-03")
            self.assertGreater(qtd_acv03, 0)

            # Cria dois arquivos derivados: um citando ACV-03 (deve ser excluído) e outro citando ACV-01 (preservado)
            arq_del = dir_derivados / "consulta_acv03.derivado.json"
            arq_keep = dir_derivados / "consulta_acv01.derivado.json"
            arq_del.write_text(
                json.dumps({"documentos_relacionados": ["ACV-03"], "resposta_rag": {"citacoes": []}}),
                encoding="utf-8",
            )
            arq_keep.write_text(
                json.dumps({"documentos_relacionados": ["ACV-01"], "resposta_rag": {"citacoes": []}}),
                encoding="utf-8",
            )

            res = idx.excluir_documento(
                "ACV-03",
                motivo="Teste unitário de retenção e descarte T14.",
                operador="Operador Teste",
                diretorios_derivados=[dir_derivados],
                caminho_log=log_audit,
            )
            self.assertEqual(res["trechos_removidos"], qtd_acv03)
            self.assertEqual(idx.total_vetores, total_antes - qtd_acv03)
            self.assertFalse(arq_del.exists())
            self.assertTrue(arq_keep.exists())

            # Recarrega o índice do disco e confirma ausência absoluta de ACV-03
            idx_recarregado = embeddings.IndiceVetorial(
                diretorio=dir_idx,
                embedder=embedder,
                tamanho_chunk=700,
                sobreposicao_chunk=120,
            )
            self.assertEqual(idx_recarregado.total_vetores, total_antes - qtd_acv03)
            self.assertFalse(any(t.documento_id == "ACV-03" for t in idx_recarregado.trechos))
            top_todos = idx_recarregado.buscar("declaração de matrícula prazo 3 dias úteis", top_k=20)
            self.assertFalse(any(r.trecho.documento_id == "ACV-03" for r in top_todos))

            registros = audit.ler_registros(log_audit)
            self.assertEqual(len(registros), 1)
            self.assertEqual(registros[0]["etapa"], "exclusao_documento_indice")
            self.assertEqual(registros[0]["detalhes_exclusao"]["documento_id"], "ACV-03")


if __name__ == "__main__":
    unittest.main()
