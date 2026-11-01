"""Assistente de documentos em Streamlit: fluxo integrado, evidências, revisão humana e painel (RF20, RF22, RF24).

Responsabilidade: Estudante 3 (Desafio 02).
A interface só orquestra funções já testadas dos outros módulos:
- Solicitação: guardrails (RF16) → compreensão RF14/RF15 → RAG RF19 → minuta PDF pendente (`main.processar_caso`);
- Revisão: `main.registrar_decisao_revisao_minuta` (estados pendente/aprovada/rejeitada/revisar, sem envio);
- Consulta ao acervo: busca top-k com similaridade explicada e resposta RAG com citações (`rag.consultar_acervo`);
- Acervo e índice: estado do índice, reindexação sem duplicar, inclusão e exclusão de documento (RF17, RF24);
- Painel: rótulos de sentimento e totais contados por código (`sentiment.agregar`, T13).

Cada consulta é independente: não há memória conversacional (Aula 15 fica para etapa posterior).

Execução:
  streamlit run src/app.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src import audit, embeddings, guardrails, llm_client, main, prompts, rag, sentiment  # noqa: E402
from src.llm_client import ErroProvedor  # noqa: E402

CONFIG = main.CONFIG
DIR_ENTRADAS_OPERADOR = RAIZ / "resultados" / "entradas_operador"
DIR_ACERVO_OPERADOR = RAIZ / "dados" / "acervo_operador"
NAO_LOC = prompts.NAO_LOCALIZADO
ESTADOS_REVISAO = {"aprovada": "Aprovar", "rejeitada": "Rejeitar", "revisar": "Solicitar revisão"}
ROTULO_STATUS_RAG = {
    "fundamentada": ("Fundamentada no acervo", "success"),
    "sem_evidencia": ("Sem evidência suficiente no acervo: encaminhada ao operador", "warning"),
    "conflito_fontes": ("Conflito entre fontes: encaminhada à revisão", "warning"),
}

st.set_page_config(page_title="Central Inteligente — Assistente de Documentos", page_icon="📄", layout="wide")


# ---------------------------------------------------------------- Recursos compartilhados

@st.cache_resource(show_spinner="Carregando índice vetorial e modelo de embeddings local…")
def _indice() -> embeddings.IndiceVetorial:
    return embeddings.obter_indice(CONFIG)


def _recarregar_indice() -> None:
    _indice.clear()


def _provedores_disponiveis() -> list[str]:
    """Provedores com chave no ambiente (sem expor o valor) + o adaptador simulado, identificado como tal."""
    disponiveis = []
    for nome, perfil in CONFIG["provedores"].items():
        var = perfil.get("env_chave")
        if perfil.get("simulado") or (var and os.getenv(var, "").strip()):
            disponiveis.append(nome)
    return disponiveis


def _barra_lateral() -> tuple[str, str]:
    st.sidebar.header("Configuração da geração")
    provs = _provedores_disponiveis()
    padrao = CONFIG["sentimentos"]["provedor"] if CONFIG["sentimentos"]["provedor"] in provs else provs[0]
    provedor = st.sidebar.selectbox("Provedor", provs, index=provs.index(padrao),
                                    help="Só aparecem provedores com chave no .env. O valor da chave nunca é exibido.")
    modelos = CONFIG["provedores"][provedor]["modelos"]
    modelo = st.sidebar.selectbox("Modelo", modelos)
    if CONFIG["provedores"][provedor].get("simulado"):
        st.sidebar.warning(llm_client.AVISO_ADAPTADOR_SIMULADO)
    lim = guardrails.limites_recursos()
    st.sidebar.caption(
        f"Limites (RF16): timeout {lim['timeout_s']} s · até {lim['max_repeticoes_falha_transitoria']} repetição "
        f"por falha transitória · teto {lim['max_chamadas']} chamadas / {lim['max_tokens_total']} tokens por execução."
    )
    st.sidebar.info("Nenhuma resposta é enviada ao cidadão automaticamente. Toda minuta exige decisão de um servidor.")
    return provedor, modelo


def _ler_json(caminho: Path) -> Any | None:
    return json.loads(caminho.read_text(encoding="utf-8")) if caminho.is_file() else None


def _dir(chave: str) -> Path:
    p = Path(CONFIG["caminhos"][chave])
    return p if p.is_absolute() else RAIZ / p


def _casos_disponiveis() -> dict[str, str]:
    """Casos fictícios do Desafio 01 e 02 (rótulo → caso_id)."""
    ids = list(dict.fromkeys([*CONFIG["producao"]["casos"],
                              *sorted(p.stem for p in (RAIZ / "dados/gabaritos/d2/solicitacoes").glob("*.json")),
                              "caso08_texto_segredo"]))
    return {f"{c} ({'áudio' if 'audio' in c else 'OCR' if 'ocr' in c else 'texto'})": c for c in ids}


def _mostrar_erro(exc: Exception) -> None:
    msg = llm_client.ocultar_segredos(str(exc))
    if isinstance(exc, embeddings.ErroIndiceDesatualizado):
        st.error(f"Índice desatualizado: {msg} Use a aba **Acervo e índice** para reindexar.")
    elif isinstance(exc, ErroProvedor):
        st.error(f"Falha do provedor de IA ({exc.codigo_erro}): {msg} Nada foi enviado ao cidadão; tente novamente "
                 "ou troque o provedor na barra lateral.")
    else:
        st.error(f"Não foi possível concluir a operação: {msg}")


# ---------------------------------------------------------------- Aba 1: solicitação, ficha, minuta e revisão

def _estado_salvo(caso_id: str) -> dict[str, Any]:
    return {
        "compreensao": _ler_json(_dir("processados") / f"{caso_id}_compreensao_d2.json"),
        "rag": _ler_json(_dir("minutas") / f"{caso_id}_rag.json"),
        "minuta": _ler_json(_dir("minutas") / f"{caso_id}_minuta.json"),
        "decisao": _ler_json(_dir("minutas") / f"{caso_id}_decisao_revisao.json"),
        "pdf": _dir("minutas") / f"{caso_id}_minuta.pdf",
    }


def _exibir_guardrails(decisoes: list[dict[str, Any]]) -> None:
    nomes = {"entrada": "entrada", "saida": "saída"}
    for i, d in enumerate(decisoes):
        camada = "entrada (arquivo)" if i == 0 and d["camada"] == "entrada" and len(decisoes) > 1 else nomes.get(d["camada"], d["camada"])
        texto = f"**Guardrail de {camada}:** {d['decisao']}" + (f" — {', '.join(d['categorias'])}" if d["categorias"] else "")
        {"permitir": st.success, "revisar": st.warning, "bloquear": st.error}[d["decisao"]](texto)


def _exibir_ficha(comp: dict[str, Any]) -> None:
    ext = comp.get("exibicao_interface")
    st.subheader("Ficha de compreensão (RF14/RF15)")
    enc = comp.get("encaminhamento_efetivo")
    if not comp.get("libera_minuta"):
        erros = (comp.get("extracao_resultado") or {}).get("erros") or []
        st.warning(f"Solicitação retida antes da minuta (`{enc}`). Erros: "
                   + ("; ".join(f"{e['camada']}/{e['campo']}: {e['categoria']}" for e in erros) or "—"))
    if not ext:
        st.info("A extração não produziu estrutura válida; a entrada e o erro foram preservados para revisão.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Categoria", ext.get("categoria", NAO_LOC))
    c2.metric("Protocolo", ext.get("protocolo", NAO_LOC))
    c3.metric("Data", ext.get("data_solicitacao", NAO_LOC))
    resumo = ((comp.get("resumo_resultado") or {}).get("resumo") or {}).get("resumo")
    st.markdown(f"**Resumo (até 100 palavras):** {resumo or NAO_LOC}")
    campos = ["solicitante", "canal", "curso", "assunto", "pedido"]
    st.table(pd.DataFrame({"Campo": campos, "Valor": [ext.get(c, NAO_LOC) for c in campos]}))
    if ext.get("entidades") and ext["entidades"] != NAO_LOC:
        st.markdown("**Entidades** (literal = copiada do texto; inferida = deduzida)")
        st.dataframe(pd.DataFrame(ext["entidades"]), hide_index=True, width="stretch")
    ausentes = ext.get("campos_ausentes")
    if ausentes and ausentes != NAO_LOC:
        st.info("Campos não localizados no original: " + ", ".join(ausentes))
    for chave, rotulo in (("motivos_revisao", "Motivos de revisão"), ("alertas_seguranca", "Alertas de segurança")):
        if ext.get(chave) and ext[chave] != NAO_LOC:
            st.warning(f"{rotulo}: " + " | ".join(ext[chave]))


def _exibir_trechos(trechos: list[dict[str, Any]]) -> None:
    if not trechos:
        st.info("Nenhum trecho recuperado.")
        return
    st.caption(trechos[0].get("sentido_metrica", embeddings.SENTIDO_SIMILARIDADE_COSSENO))
    for t in trechos:
        cab = (f"#{t['posicao']} · {t['documento_id']} v{t['versao_documento']} · {t.get('secao') or '—'}"
               f"{' · pág. ' + str(t['pagina']) if t.get('pagina') else ''} · similaridade {t['similaridade']:.3f}")
        with st.expander(cab):
            st.caption(f"{t.get('titulo_documento') or ''} · chunk `{t['chunk_id']}`")
            st.text(t["texto"])


def _exibir_resposta_rag(resp: dict[str, Any]) -> None:
    rotulo, tipo = ROTULO_STATUS_RAG.get(resp["status"], (resp["status"], "info"))
    getattr(st, tipo)(f"Status: **{rotulo}**")
    st.markdown(resp["resposta"])
    if resp.get("requer_revisao") and resp.get("motivo_revisao"):
        st.caption(f"Motivo da revisão: {resp['motivo_revisao']}")
    if resp.get("afirmacoes"):
        st.markdown("**Afirmações institucionais e trechos que as sustentam**")
        cit = {c["chunk_id"]: c for c in resp.get("citacoes") or []}
        for af in resp["afirmacoes"]:
            fontes = [cit[c] for c in af["chunk_ids"] if c in cit]
            with st.expander(f"{af['texto']}  ←  {', '.join(af['chunk_ids'])}"):
                for c in fontes:
                    st.caption(f"{c['documento_id']} v{c['versao_documento']} · {c.get('secao') or '—'}"
                               f"{' · pág. ' + str(c['pagina']) if c.get('pagina') else ''}")
                    st.text(c["trecho"])


def _exibir_minuta(minuta: dict[str, Any], pdf: Path) -> None:
    st.subheader("Minuta (pendente de revisão humana)")
    st.error("MINUTA GERADA COM APOIO DE IA — PENDENTE DE REVISÃO HUMANA — ENVIO AUTOMÁTICO BLOQUEADO")
    st.markdown(f"**Assunto:** {minuta.get('assunto', NAO_LOC)}  \n{minuta.get('saudacao', '')}")
    for p in minuta.get("corpo") or []:
        st.markdown(p)
    st.markdown(minuta.get("fecho", ""))
    if minuta.get("informacoes_nao_localizadas"):
        st.warning("Informações não localizadas: " + " | ".join(minuta["informacoes_nao_localizadas"]))
    if minuta.get("alertas_seguranca"):
        st.warning("Alertas: " + " | ".join(minuta["alertas_seguranca"]))
    st.markdown("**Fontes:** " + "; ".join(minuta.get("fontes") or [NAO_LOC]))
    if pdf.is_file():
        st.download_button("Baixar PDF da minuta", pdf.read_bytes(), file_name=pdf.name, mime="application/pdf")


def _formulario_revisao(caso_id: str, estado: dict[str, Any]) -> None:
    st.subheader("Decisão do servidor responsável (RF24)")
    atual = (estado.get("decisao") or (estado.get("rag") or {}).get("decisao_revisao") or {"estado": "pendente"})
    st.markdown(f"Estado atual: **{atual['estado']}**"
                + (f" · {atual.get('revisor')} · {atual.get('data_hora')} — _{atual.get('justificativa')}_"
                   if atual["estado"] != "pendente" else "")
                + f" · enviada ao cidadão: **{'sim' if atual.get('enviada_ao_cidadao') else 'não'}**")
    if not estado.get("minuta"):
        st.info("Não há minuta para decidir: a solicitação foi retida antes da geração.")
        return
    with st.form(f"revisao_{caso_id}", clear_on_submit=False):
        decisao = st.radio("Decisão", list(ESTADOS_REVISAO), format_func=ESTADOS_REVISAO.get, horizontal=True)
        revisor = st.text_input("Nome do servidor responsável")
        justificativa = st.text_area("Justificativa (obrigatória)")
        enviar = st.form_submit_button("Registrar decisão")
    if enviar:
        if not revisor.strip() or not justificativa.strip():
            st.error("Informe o nome do servidor e a justificativa: a decisão não foi registrada.")
            return
        try:
            d = main.registrar_decisao_revisao_minuta(caso_id, estado=decisao, revisor=revisor, justificativa=justificativa)
        except Exception as exc:  # noqa: BLE001 — mensagem compreensível ao operador
            _mostrar_erro(exc)
            return
        st.success(f"Decisão '{d['estado']}' registrada para {d['id_minuta']} às {d['data_hora']}. "
                   "Nada foi enviado ao cidadão (enviada_ao_cidadao = false).")
        time.sleep(0.5)
        st.rerun()


def aba_solicitacao(provedor: str, modelo: str) -> None:
    st.header("Solicitação → ficha → evidências → minuta → revisão")
    origem = st.radio("Entrada", ["Caso fictício cadastrado", "Digitar ou enviar texto"], horizontal=True)
    if origem == "Caso fictício cadastrado":
        casos = _casos_disponiveis()
        caso_id = casos[st.selectbox("Caso", list(casos))]
        arquivo_avulso = None
    else:
        envio = st.file_uploader("Arquivo .txt (opcional)", type=["txt"])
        texto = st.text_area("Texto da solicitação fictícia", value=envio.getvalue().decode("utf-8") if envio else "",
                             height=180)
        caso_id = st.session_state.get("caso_operador") or f"op-{time.strftime('%Y%m%d-%H%M%S')}"
        arquivo_avulso = texto

    if st.button("Processar solicitação", type="primary"):
        try:
            if arquivo_avulso is not None:
                if not arquivo_avulso.strip():
                    st.error("Digite ou envie o texto da solicitação.")
                    return
                caso_id = f"op-{time.strftime('%Y%m%d-%H%M%S')}"
                DIR_ENTRADAS_OPERADOR.mkdir(parents=True, exist_ok=True)
                arq = DIR_ENTRADAS_OPERADOR / f"{caso_id}.txt"
                arq.write_text(arquivo_avulso, encoding="utf-8")
                st.session_state["caso_operador"] = caso_id
                arquivo_avulso = str(arq.relative_to(RAIZ))
            with st.status("Processando: guardrails → compreensão → recuperação → minuta…", expanded=True) as status:
                adp = llm_client.criar_adaptador_geracao(CONFIG, provedor=provedor, modelo=modelo)
                res = main.processar_caso(caso_id, provedor, modelo, CONFIG["producao"], nao_interativo=True,
                                          arquivo_avulso=arquivo_avulso, indice_rag=_indice(), adaptador_rag=adp)
                status.update(label="Processamento concluído", state="complete")
            st.session_state["ultimo_resultado"] = {"caso_id": caso_id, **res}
        except Exception as exc:  # noqa: BLE001
            _mostrar_erro(exc)
            return

    if origem != "Caso fictício cadastrado":
        caso_id = st.session_state.get("caso_operador", caso_id)
    ultimo = st.session_state.get("ultimo_resultado")
    if ultimo and ultimo["caso_id"] == caso_id and ultimo.get("guardrails"):
        _exibir_guardrails(ultimo["guardrails"])
        if ultimo.get("bloqueado_guardrail"):
            st.error("Solicitação bloqueada pelos guardrails de entrada: nenhuma chamada ao provedor, nenhuma minuta.")
            return

    estado = _estado_salvo(caso_id)
    if not estado["compreensao"]:
        st.info("Este caso ainda não foi processado. Clique em **Processar solicitação**.")
        return
    st.caption(f"Caso `{caso_id}` · origem `{estado['compreensao']['arquivo_origem']}` · modalidade "
               f"{estado['compreensao']['modalidade']} · resultados salvos (cada consulta é independente).")
    col_esq, col_dir = st.columns([1, 1])
    with col_esq:
        _exibir_ficha(estado["compreensao"])
    with col_dir:
        if estado["rag"]:
            st.subheader("Trechos recuperados do acervo (top-k)")
            _exibir_trechos(estado["rag"].get("trechos_recuperados") or [])
            st.subheader("Resposta fundamentada")
            _exibir_resposta_rag(estado["rag"]["resposta_rag"])
            st.caption(f"Execução `{estado['rag']['id_execucao']}` · {estado['rag']['provedor']}/{estado['rag']['modelo']}"
                       f"{' · SIMULADO' if estado['rag'].get('simulado') else ''} · índice `{estado['rag']['versao_indice']}`")
    if estado["minuta"] and estado["compreensao"].get("libera_minuta"):
        _exibir_minuta(estado["minuta"], estado["pdf"])
        _formulario_revisao(caso_id, estado)
    else:
        _formulario_revisao(caso_id, {**estado, "minuta": None})


# ---------------------------------------------------------------- Aba 2: consulta ao acervo

def aba_consulta(provedor: str, modelo: str) -> None:
    st.header("Consulta ao acervo (busca vetorial + RAG)")
    pergunta = st.text_input("Pergunta", placeholder="Quais documentos são exigidos para a matrícula?")
    c1, c2 = st.columns([1, 3])
    top_k = c1.number_input("top-k", min_value=1, max_value=10, value=int(CONFIG["indexacao"]["top_k_padrao"]))
    gerar = c2.radio("Ação", ["Só buscar trechos", "Buscar e gerar resposta fundamentada"], horizontal=True)
    if not st.button("Consultar", type="primary"):
        return
    if not pergunta.strip():
        st.error("Digite uma pergunta.")
        return
    dec = guardrails.avaliar_entrada(pergunta if len(pergunta) >= 20 else pergunta + " (consulta ao atendimento escolar)")
    if dec.decisao == "bloquear":
        guardrails.registrar_decisao(dec, caso_id="consulta_streamlit", modalidade="texto", arquivo_origem="interface")
        st.error(f"Consulta bloqueada pelos guardrails: {', '.join(dec.categorias)}.")
        return
    if dec.decisao == "revisar":
        st.warning(f"Consulta marcada para revisão: {', '.join(dec.categorias)}. Instruções no texto são tratadas como dado.")
    try:
        idx = _indice()
        if gerar == "Só buscar trechos":
            achados = idx.buscar(pergunta, top_k=int(top_k))
            _exibir_trechos([{**a.trecho.model_dump(), "posicao": a.posicao, "similaridade": a.similaridade,
                              "titulo_documento": a.titulo_documento} for a in achados])
            return
        with st.spinner("Recuperando trechos e gerando resposta…"):
            adp = llm_client.criar_adaptador_geracao(CONFIG, provedor=provedor, modelo=modelo)
            res = rag.consultar_acervo(pergunta, caso_id="consulta_streamlit", indice=idx, adaptador=adp, top_k=int(top_k))
    except Exception as exc:  # noqa: BLE001
        _mostrar_erro(exc)
        return
    if res.estado == "erro_provedor":
        st.error("Falha do provedor: a consulta foi retida e encaminhada à revisão. " + "; ".join(
            llm_client.ocultar_segredos(e.get("detalhe", "")) for e in res.erros))
    _exibir_resposta_rag(res.resposta_rag)
    for a in res.alertas_seguranca:
        st.warning(a)
    st.subheader("Trechos recuperados")
    _exibir_trechos(res.trechos_recuperados)
    st.caption(f"Execução `{res.id_execucao}` · {res.provedor}/{res.modelo}{' · SIMULADO' if res.simulado else ''} · "
               f"índice `{res.versao_indice}`")


# ---------------------------------------------------------------- Aba 3: acervo e índice

def aba_acervo() -> None:
    st.header("Acervo institucional e índice vetorial (RF17, RF24)")
    try:
        idx = _indice()
        estado = idx.resumo_estado()
    except Exception as exc:  # noqa: BLE001
        _mostrar_erro(exc)
        return
    if estado["desatualizado"]:
        st.error(f"Índice desatualizado: {estado['motivo_desatualizacao']} Reindexe antes de consultar.")
    elif estado["total_vetores"] == 0:
        st.warning("Índice vazio: clique em **Indexar / atualizar acervo**.")
    c = st.columns(4)
    c[0].metric("Versão do índice", estado["versao_indice"].replace("idx-", ""), help=estado["versao_indice"])
    c[1].metric("Documentos", estado["total_documentos"])
    c[2].metric("Vetores", estado["total_vetores"])
    c[3].metric("Dimensão", estado["dimensao"])
    st.caption(f"Modelo de embedding: `{estado['modelo_embedding']}` ({estado['provedor_embedding']}) · chunking "
               f"`{estado['configuracao_chunking']}` · {estado['sentido_metrica']}")
    if estado["documentos"]:
        st.dataframe(pd.DataFrame(estado["documentos"]), hide_index=True, width="stretch")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Indexar / atualizar")
        st.caption("Reutiliza documentos com o mesmo hash: reindexar o mesmo acervo não cria duplicatas.")
        if st.button("Indexar / atualizar acervo"):
            with st.spinner("Indexando…"):
                try:
                    r = idx.indexar_acervo(caminho_log=audit.ARQUIVO_LOG_PADRAO)
                except Exception as exc:  # noqa: BLE001
                    _mostrar_erro(exc)
                    return
            st.success(f"Índice {r['versao_indice']}: {r['total_vetores']} vetores · {r['indexados_ou_atualizados']} "
                       f"indexados/atualizados · {r['reutilizados_sem_duplicar']} reutilizados sem duplicar.")
        st.subheader("Incluir documento fictício")
        with st.form("inclusao"):
            arq = st.file_uploader("Arquivo TXT ou PDF textual", type=["txt", "pdf"])
            doc_id = st.text_input("Identificador", value="ACV-90")
            titulo = st.text_input("Título")
            versao = st.text_input("Versão", value="1.0")
            incluir = st.form_submit_button("Incluir e indexar")
        if incluir:
            if not arq or not re.fullmatch(r"ACV-\d{2}", doc_id or "") or not titulo.strip():
                st.error("Envie o arquivo e informe identificador no formato ACV-NN e título.")
            else:
                DIR_ACERVO_OPERADOR.mkdir(parents=True, exist_ok=True)
                destino = DIR_ACERVO_OPERADOR / f"{doc_id}{Path(arq.name).suffix.lower()}"
                destino.write_bytes(arq.getvalue())
                dec = guardrails.validar_arquivo(destino, "texto" if destino.suffix == ".txt" else "imagem")
                if dec.decisao == "bloquear":
                    destino.unlink(missing_ok=True)
                    st.error(f"Arquivo recusado: {', '.join(dec.categorias)}.")
                else:
                    try:
                        r = idx.incluir_arquivo_avulso(destino, documento_id=doc_id, titulo=titulo, versao=versao,
                                                       caminho_log=audit.ARQUIVO_LOG_PADRAO)
                        st.success(f"{doc_id}: {r['acao']} ({r['chunks']} chunks) · índice {r['versao_indice']}.")
                    except Exception as exc:  # noqa: BLE001
                        _mostrar_erro(exc)
    with col2:
        st.subheader("Excluir documento (RF24)")
        st.caption("Remove vetores, metadados e derivados; a exclusão é auditada e o documento deixa de ser recuperado.")
        ids = [d["documento_id"] for d in estado["documentos"]]
        if ids:
            with st.form("exclusao"):
                alvo = st.selectbox("Documento", ids)
                motivo = st.text_input("Motivo", value="Retenção/governança (RF24)")
                operador = st.text_input("Operador")
                confirmar = st.checkbox("Confirmo a exclusão do documento e de seus derivados")
                excluir = st.form_submit_button("Excluir")
            if excluir:
                if not confirmar or not operador.strip():
                    st.error("Marque a confirmação e informe o operador.")
                else:
                    try:
                        r = idx.excluir_documento(alvo, motivo=motivo, operador=operador,
                                                  diretorios_derivados=[_dir("rag")], caminho_log=audit.ARQUIVO_LOG_PADRAO)
                    except Exception as exc:  # noqa: BLE001
                        _mostrar_erro(exc)
                        return
                    st.success(f"Excluído: {json.dumps(r, ensure_ascii=False, default=str)[:400]}")
                    _recarregar_indice()


# ---------------------------------------------------------------- Aba 4: painel de sentimentos

def aba_painel(provedor: str, modelo: str) -> None:
    st.header("Painel de avaliações de atendimento (RF22, T13)")
    st.caption("Totais e proporções são contados por código a partir dos rótulos; o modelo não calcula totais. "
               "O rótulo descreve o texto avaliado, nunca a pessoa que o escreveu.")
    execucoes = sorted((p for p in _dir("sentimentos").glob("2*") if (p / "classificacoes.json").is_file()), reverse=True) \
        if _dir("sentimentos").is_dir() else []
    c1, c2 = st.columns([3, 1])
    if c2.button("Classificar as 12 avaliações agora", help="12 chamadas ao provedor selecionado"):
        with st.spinner("Classificando…"):
            try:
                pasta = sentiment.executar_lote(provedor=provedor, modelo=modelo)
            except Exception as exc:  # noqa: BLE001
                _mostrar_erro(exc)
                return
        st.success(f"Execução salva em {pasta.relative_to(RAIZ)}")
        st.rerun()
    if not execucoes:
        st.info("Nenhuma classificação registrada. Clique em **Classificar as 12 avaliações agora**.")
        return
    escolha = c1.selectbox("Execução", execucoes, format_func=lambda p: p.name)
    pacote = sentiment.carregar_execucao(escolha)
    registros = sentiment.montar_registros(pacote["resultados"], sentiment.carregar_avaliacoes())
    st.caption(f"`{pacote['provedor']}/{pacote['modelo']}` · prompt `{pacote['versao_prompt']}`"
               f"{' · SIMULADO' if pacote.get('simulado') else ''} · {pacote['uso']['chamadas']} chamadas · "
               f"{pacote['uso']['tokens_entrada'] + pacote['uso']['tokens_saida']} tokens · custo "
               f"{pacote['uso']['custo_usd'] if pacote['uso']['custo_usd'] is not None else 'não disponível (tarifa não cadastrada)'}")

    f1, f2, f3 = st.columns(3)
    opcoes = lambda campo: ["todos", *sorted({str(r[campo]) for r in registros if r[campo]})]  # noqa: E731
    filtros = {"canal": f1.selectbox("Canal", opcoes("canal")),
               "categoria_atendimento": f2.selectbox("Categoria", opcoes("categoria_atendimento")),
               "polaridade": f3.selectbox("Polaridade", opcoes("polaridade"))}
    ag = sentiment.agregar(registros, filtros)
    den = ag["denominador_filtrado"]
    m = st.columns(5)
    m[0].metric("Avaliações no filtro", f"{den}", help=f"Recebidas: {ag['total_recebidos']} · duplicatas ignoradas: {ag['duplicatas_ignoradas']}")
    for i, pol in enumerate(("positiva", "negativa", "neutra")):
        m[i + 1].metric(pol.capitalize(), ag["proporcoes"].get(pol, {"formatado": f"0/{den}"})["formatado"]
                        if den else f"0/0")
    m[4].metric("Incertos (revisão)", f"{ag['incertos']['numerador']}/{den}",
                help="Sem rótulo válido, indeterminada, revisão pedida, confiança baixa ou alerta")
    if den == 0:
        st.warning("Conjunto vazio para os filtros escolhidos: denominador 0, proporções não calculadas.")
        return

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Contagem por polaridade**")
        st.bar_chart(pd.DataFrame({"avaliações": ag["contagens"]}))
    with g2:
        st.markdown("**Polaridade por canal**")
        st.bar_chart(pd.DataFrame(ag["por_canal"]).T, stack=True)
    st.markdown("**Polaridade por categoria do atendimento**")
    st.dataframe(pd.DataFrame(ag["por_categoria"]).T, width="stretch")

    st.subheader("Avaliações e conferência com o gabarito")
    gab = {x["id_avaliacao"]: x for x in pacote["comparacao"]["linhas"]}
    ids_filtrados = {r["id_avaliacao"] for r in registros
                     if all(v in (None, "", "todos") or str(r.get(k)) == v for k, v in filtros.items())}
    textos = {a.id_avaliacao: a.texto for a in sentiment.carregar_avaliacoes()}
    tabela = [{"ID": i, "Texto": textos.get(i, ""), "Rótulo": gab[i]["obtido"], "Gabarito": gab[i]["esperado"],
               "Acerto": "✔" if gab[i]["acerto"] else "✘", "Incerto": "SIM" if gab[i]["incerto"] else "",
               "Confiança (estimativa)": gab[i]["confianca_declarada"], "Justificativa": gab[i]["justificativa"]}
              for i in sorted(ids_filtrados)]
    st.dataframe(pd.DataFrame(tabela), hide_index=True, width="stretch")
    c = pacote["comparacao"]
    st.markdown(f"Acurácia de polaridade: **{c['acuracia_polaridade']['formatado']}** · revisão concordante: "
                f"{c['concordancia_revisao']['formatado']} · ambíguos sinalizados: {c['ambiguos_sinalizados']['formatado']}")
    st.info(sentiment.AVISO_CONFIANCA + " Contagem de confiança no filtro: " + ", ".join(
        f"{k}: {v}" for k, v in ag["confianca_declarada_estimativa"].items()))


# ---------------------------------------------------------------- Aba 5: auditoria

def aba_auditoria() -> None:
    st.header("Trilha de auditoria (RF21)")
    regs = audit.ler_registros()
    if not regs:
        st.info("Nenhum registro.")
        return
    filtro = st.text_input("Filtrar por caso ou etapa")
    linhas = [r for r in reversed(regs) if not filtro or filtro in r.get("caso_id", "") or filtro in r.get("etapa", "")][:200]
    campos = ["data_hora", "id_execucao", "caso_id", "etapa", "provedor", "modelo", "versao_prompt", "versao_indice",
              "status_rag", "latencia_s", "tokens_entrada", "tokens_saida", "custo_usd", "metrica_custo_status",
              "decisao_humana", "erro", "enviada_ao_cidadao"]
    st.dataframe(pd.DataFrame([{k: r.get(k) for k in campos} for r in linhas]), hide_index=True, width="stretch")
    st.caption("Identificadores são mascarados nas consultas e credenciais são removidas antes do registro.")


def principal() -> None:
    st.title("Central Inteligente de Atendimento — Assistente de Documentos")
    st.caption("Protótipo local com dados fictícios · conteúdo gerado com apoio de IA · revisão humana obrigatória")
    provedor, modelo = _barra_lateral()
    abas = st.tabs(["Solicitação e revisão", "Consulta ao acervo", "Acervo e índice", "Painel de sentimentos", "Auditoria"])
    with abas[0]:
        aba_solicitacao(provedor, modelo)
    with abas[1]:
        aba_consulta(provedor, modelo)
    with abas[2]:
        aba_acervo()
    with abas[3]:
        aba_painel(provedor, modelo)
    with abas[4]:
        aba_auditoria()


principal()
