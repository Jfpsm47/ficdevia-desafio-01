"""RF10: importar uma imagem gerada localmente no Draw Things e registrar a revisão humana.

O Draw Things executa o modelo aberto no computador. Este módulo não tenta controlar a interface
gráfica: ele recebe o PNG que a equipe exportou para ``resultados/imagens/``, preserva a imagem
base, aplica a composição institucional em 16:9 e guarda evidências reproduzíveis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from src import audit, prompts
from src.llm_client import ocultar_segredos

RAIZ = prompts.RAIZ
_ID_CASO = re.compile(r"^[a-z0-9_]{3,60}$")
_CAMPOS_PROMPT = (
    "**Assunto:**", "**Composição:**", "**Estilo:**", "**Iluminação:**",
    "**Proporção:**", "**Restrições obrigatórias:**",
)
_ITENS_REVISAO = {
    "textos": "textos e números legíveis",
    "simbolos": "símbolos, logotipos e marcas",
    "maos_objetos": "mãos, objetos e proporções",
    "coerencia": "coerência visual com a orientação",
}


def configurar() -> dict[str, Any]:
    """Lê somente parâmetros não sensíveis do fluxo local de imagem."""
    return json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))


def hash_arquivo(caminho: Path) -> str:
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def _caminho_relativo_seguro(caminho_relativo: str, raiz_permitida: Path) -> Path:
    caminho = (RAIZ / caminho_relativo).resolve()
    if not caminho.is_relative_to(raiz_permitida.resolve()):
        raise ValueError(f"O caminho configurado deve ficar dentro de {raiz_permitida.relative_to(RAIZ)}/.")
    return caminho


def validar_configuracao(cfg: dict[str, Any]) -> None:
    """Valida o fluxo local e os parâmetros registrados no Draw Things."""
    if cfg.get("provedor") != "draw_things_local":
        raise ValueError("O RF10 requer geracao_imagem.provedor=draw_things_local.")
    if cfg.get("modo_execucao") != "local_offline":
        raise ValueError("O RF10 deve ser executado localmente, sem envio a provedor externo.")
    for chave in ("ferramenta", "versao_ferramenta", "modelo", "licenca_modelo", "fonte_modelo",
                  "data_consulta_modelo", "diretorio", "titulo", "aviso_proveniencia", "sampler"):
        if not isinstance(cfg.get(chave), str) or not cfg[chave].strip():
            raise ValueError(f"Configure {chave}.")
    if cfg["ferramenta"] != "Draw Things":
        raise ValueError("O RF10 registra a execução feita no Draw Things.")
    if not isinstance(cfg.get("seed"), int) or cfg["seed"] < 0:
        raise ValueError("A seed da imagem deve ser um inteiro não negativo.")
    if cfg.get("proporcao") != "16:9":
        raise ValueError("A peça final do RF10 deve usar proporção 16:9.")
    for chave in ("largura", "altura"):
        valor = cfg.get(chave)
        if not isinstance(valor, int) or valor < 256 or valor % 8:
            raise ValueError(f"{chave.capitalize()} deve ser inteiro, ao menos 256 e múltiplo de 8.")
    if (cfg["largura"], cfg["altura"]) != (1024, 576):
        raise ValueError("A peça final local deve ser exportada em 1024x576.")
    if not isinstance(cfg.get("passos"), int) or cfg["passos"] != 4:
        raise ValueError("FLUX.2 [klein] 4B usa quatro passos destilados neste fluxo.")
    if cfg.get("guidance_scale") != 1.0:
        raise ValueError("FLUX.2 [klein] 4B usa guidance scale 1.0 neste fluxo.")
    if not isinstance(cfg.get("shift"), (int, float)):
        raise ValueError("Configure o shift usado no Draw Things.")
    if cfg.get("formato") != "PNG":
        raise ValueError("O RF10 salva somente PNG para preservar a peça sem perdas.")
    _caminho_relativo_seguro(cfg["diretorio"], RAIZ / "resultados")


def ler_prompt_orientacao() -> tuple[str, dict[str, str]]:
    """Carrega o prompt versionado e impede importação sem seus campos obrigatórios."""
    caminho, versao = prompts.VERSOES["imagem"]
    especificacao = prompts.ler_prompt(caminho).strip()
    ausentes = [campo for campo in _CAMPOS_PROMPT if campo not in especificacao]
    if ausentes:
        raise ValueError("O prompt de imagem não contém: " + ", ".join(ausentes))
    marcador = "## Prompt efetivo ao modelo"
    if marcador not in especificacao:
        raise ValueError("O prompt de imagem não tem uma versão efetiva para o modelo.")
    texto = especificacao.split(marcador, 1)[1].strip()
    if not texto or len(texto.split()) > 220:
        raise ValueError("O prompt efetivo deve ter no máximo 220 palavras.")
    return texto, {
        "arquivo_prompt": f"prompts/{caminho}", "versao_prompt": versao,
        "hash_prompt": prompts.hash_texto(texto),
        "hash_especificacao_prompt": prompts.hash_texto(especificacao),
    }


def _fonte(tamanho: int, negrito: bool = False) -> ImageFont.ImageFont:
    candidatos = []
    if negrito:
        candidatos += ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]
    candidatos += ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]
    for caminho in candidatos:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default(size=tamanho)


def _texto_centralizado(desenho: ImageDraw.ImageDraw, caixa: tuple[int, int, int, int], texto: str,
                        fonte: ImageFont.ImageFont, preenchimento: str) -> None:
    esquerda, topo, direita, baixo = desenho.textbbox((0, 0), texto, font=fonte)
    largura, altura = direita - esquerda, baixo - topo
    x0, y0, x1, y1 = caixa
    desenho.text((x0 + (x1 - x0 - largura) / 2, y0 + (y1 - y0 - altura) / 2 - topo), texto,
                 font=fonte, fill=preenchimento)


def compor_peca(imagem_base: Image.Image, cfg: dict[str, Any]) -> Image.Image:
    """Monta uma peça 16:9 sem cortar a saída do modelo e identifica sua proveniência."""
    largura, altura = cfg["largura"], cfg["altura"]
    cabecalho, rodape = 64, 44
    area_visual = altura - cabecalho - rodape
    base = imagem_base.convert("RGB")
    try:
        escala = min(area_visual / base.height, largura / base.width)
        tamanho = (round(base.width * escala), round(base.height * escala))
        arte = base.resize(tamanho, Image.Resampling.LANCZOS)
        try:
            cor_fundo = base.getpixel((0, 0))
            peca = Image.new("RGB", (largura, altura), cor_fundo)
            desenho = ImageDraw.Draw(peca)
            desenho.rectangle((0, 0, largura, cabecalho), fill="#073b4c")
            desenho.rectangle((0, altura - rodape, largura, altura), fill="#073b4c")
            x = (largura - arte.width) // 2
            y = cabecalho + (area_visual - arte.height) // 2
            peca.paste(arte, (x, y))
            _texto_centralizado(desenho, (18, 8, largura - 18, cabecalho - 8), cfg["titulo"],
                                _fonte(20, negrito=True), "#ffffff")
            _texto_centralizado(desenho, (12, altura - rodape + 8, largura - 12, altura - 8),
                                cfg["aviso_proveniencia"], _fonte(11), "#ffffff")
            return peca
        finally:
            arte.close()
    finally:
        base.close()
        imagem_base.close()


def _salvar_json(caminho: Path, dados: dict[str, Any]) -> None:
    caminho.write_text(json.dumps(audit.sanitizar_dados(dados), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _inspecionar_png(caminho: Path) -> list[int]:
    try:
        with Image.open(caminho) as imagem:
            imagem.verify()
        with Image.open(caminho) as imagem:
            return [imagem.width, imagem.height]
    except (OSError, ValueError) as exc:
        raise ValueError(f"PNG inválido: {caminho.name}.") from exc


def _registrar(meta: dict[str, Any], caminho_log: Path | None, erro: str | None = None) -> None:
    registro = audit.criar_registro(
        id_execucao=meta["id_execucao"], caso_id=meta["caso_id"], etapa="geracao_imagem", modalidade="imagem",
        arquivo_origem=meta["arquivo_prompt"], provedor=meta["provedor"], modelo=meta["modelo"],
        parametros=meta["parametros"], versao_prompt=meta["versao_prompt"], hash_prompt=meta["hash_prompt"],
        resposta_llm=meta, arquivo_saida=meta.get("arquivo_peca"),
        resumo_resultado="Peça de orientação fictícia gerada localmente; revisão humana obrigatória antes de uso.",
        decisao_humana=meta.get("decisao_humana", "PENDENTE"), revisor=meta.get("revisor"),
        justificativa_humana=meta.get("justificativa_humana"), erro=erro,
    )
    registro.update({chave: meta.get(chave) for chave in (
        "sha256_imagem_base", "sha256_peca", "sha256_prompt_efetivo", "revisao_modelo",
    )})
    audit.registrar_execucao(registro, caminho_log=caminho_log)


def _resolver_origem(caminho_origem: Path, diretorio_saida: Path) -> Path:
    origem = Path(caminho_origem).expanduser().resolve()
    if not origem.is_file() or origem.suffix.casefold() != ".png":
        raise ValueError("Informe um PNG exportado pelo Draw Things.")
    if not origem.is_relative_to(diretorio_saida):
        raise ValueError("O PNG exportado deve estar dentro de resultados/imagens/.")
    _inspecionar_png(origem)
    return origem


def importar_imagem_draw_things(caminho_origem: Path, caso_id: str = "caso01_texto", *,
                                config: dict[str, Any] | None = None,
                                caminho_log: Path | None = None) -> dict[str, Any]:
    """Importa um PNG local do Draw Things, sem rede, e cria evidências pendentes de revisão."""
    if not _ID_CASO.fullmatch(caso_id):
        raise ValueError("caso_id deve conter apenas letras minúsculas, números e _. ")
    config = config or configurar()
    cfg = config["geracao_imagem"]
    validar_configuracao(cfg)
    prompt, prompt_meta = ler_prompt_orientacao()
    diretorio_saida = _caminho_relativo_seguro(cfg["diretorio"], RAIZ / "resultados")
    origem = _resolver_origem(caminho_origem, diretorio_saida)
    id_execucao = audit.gerar_id_execucao("img")
    pasta = (diretorio_saida / id_execucao).resolve()
    meta: dict[str, Any] = {
        "id_execucao": id_execucao, "data_hora": audit.agora_iso(), "caso_id": caso_id,
        "provedor": cfg["provedor"], "modo_execucao": cfg["modo_execucao"],
        "ferramenta": cfg["ferramenta"], "versao_ferramenta": cfg["versao_ferramenta"],
        "modelo": cfg["modelo"], "revisao_modelo": cfg.get("revisao_modelo", "não informada"),
        "decisao_humana": "PENDENTE", **prompt_meta,
        "parametros": {chave: cfg[chave] for chave in ("seed", "proporcao", "largura", "altura", "passos",
                                                         "guidance_scale", "sampler", "shift", "formato")},
        "licenca_modelo": cfg["licenca_modelo"], "fonte_modelo": cfg["fonte_modelo"],
        "data_consulta_modelo": cfg["data_consulta_modelo"],
        "arquivo_origem_draw_things": str(origem.relative_to(RAIZ)), "custo_usd": 0.0,
        "tentativas": 1, "latencia_s": None,
        "edicao_local": "encaixe centralizado sem corte; título e aviso de proveniência aplicados pela equipe",
    }
    try:
        pasta.mkdir(parents=True, exist_ok=False)
        arquivo_prompt = pasta / "prompt_efetivo.md"
        arquivo_base = pasta / "imagem_base.png"
        arquivo_peca = pasta / "peca_orientacao.png"
        arquivo_prompt.write_text(prompt + "\n", encoding="utf-8")
        shutil.copyfile(origem, arquivo_base)
        with Image.open(arquivo_base) as aberta:
            peca = compor_peca(aberta, cfg)
        try:
            peca.save(arquivo_peca, format="PNG", optimize=True)
        finally:
            peca.close()
        dimensoes_base = _inspecionar_png(arquivo_base)
        dimensoes_peca = _inspecionar_png(arquivo_peca)
        meta.update(
            arquivo_prompt_efetivo=str(arquivo_prompt.relative_to(RAIZ)),
            arquivo_imagem_base=str(arquivo_base.relative_to(RAIZ)),
            arquivo_peca=str(arquivo_peca.relative_to(RAIZ)),
            arquivo_metadados=str((pasta / "metadados.json").relative_to(RAIZ)),
            sha256_prompt_efetivo=hash_arquivo(arquivo_prompt), sha256_imagem_base=hash_arquivo(arquivo_base),
            sha256_peca=hash_arquivo(arquivo_peca), dimensoes_imagem_base=dimensoes_base,
            dimensoes_peca=dimensoes_peca, textos_sobrepostos=[cfg["titulo"], cfg["aviso_proveniencia"]],
            verificacoes_automaticas={
                "pngs_validos": True,
                "dimensoes_peca_corretas": dimensoes_peca == [cfg["largura"], cfg["altura"]],
                "proporcao_final_16_9": dimensoes_peca[0] * 9 == dimensoes_peca[1] * 16,
                "proveniencia_visivel_aplicada": True, "imagem_base_preservada_sem_corte": True,
                "revisao_humana_obrigatoria": list(_ITENS_REVISAO.values()),
            },
        )
        _salvar_json(pasta / "inspecao.json", meta["verificacoes_automaticas"])
        _salvar_json(pasta / "metadados.json", meta)
    except (OSError, RuntimeError, ValueError) as exc:
        _registrar(meta, caminho_log, str(exc))
        raise
    _registrar(meta, caminho_log)
    return meta


def _validar_integridade(meta: dict[str, Any], pasta: Path) -> None:
    esperados = {
        "arquivo_prompt_efetivo": "sha256_prompt_efetivo", "arquivo_imagem_base": "sha256_imagem_base",
        "arquivo_peca": "sha256_peca",
    }
    for arquivo_chave, hash_chave in esperados.items():
        arquivo = RAIZ / str(meta.get(arquivo_chave, ""))
        if not arquivo.is_file() or not arquivo.is_relative_to(pasta) or hash_arquivo(arquivo) != meta.get(hash_chave):
            raise ValueError("A evidência visual foi alterada; importe uma nova peça antes da revisão.")
    _inspecionar_png(RAIZ / meta["arquivo_imagem_base"])
    _inspecionar_png(RAIZ / meta["arquivo_peca"])


def confirmar_revisao(pasta: Path, revisor: str, justificativa: str, *, decisao: str,
                      textos_confirmados: bool, simbolos_confirmados: bool,
                      maos_objetos_confirmados: bool, coerencia_confirmada: bool,
                      caminho_log: Path | None = None) -> dict[str, Any]:
    """Registra a inspeção humana exigida pelo RF10 e preserva sua decisão na auditoria."""
    pasta = Path(pasta).resolve()
    raiz_resultados = (RAIZ / "resultados" / "imagens").resolve()
    if not pasta.is_relative_to(raiz_resultados):
        raise ValueError("A revisão deve apontar para uma pasta dentro de resultados/imagens/.")
    if decisao not in {"Aprovada", "Rejeitada"}:
        raise ValueError("A decisão da imagem deve ser Aprovada ou Rejeitada.")
    if not revisor.strip() or not justificativa.strip():
        raise ValueError("Informe revisor e justificativa da inspeção visual.")
    confirmacoes = {"textos": textos_confirmados, "simbolos": simbolos_confirmados,
                    "maos_objetos": maos_objetos_confirmados, "coerencia": coerencia_confirmada}
    faltantes = [_ITENS_REVISAO[chave] for chave, valor in confirmacoes.items() if not valor]
    if faltantes:
        raise ValueError("Confirme a inspeção de: " + ", ".join(faltantes) + ".")
    arquivo_meta = pasta / "metadados.json"
    if not arquivo_meta.is_file():
        raise ValueError("Metadados da geração não encontrados.")
    meta = json.loads(arquivo_meta.read_text(encoding="utf-8"))
    if meta.get("decisao_humana") != "PENDENTE":
        raise ValueError("Esta imagem já possui uma decisão humana final.")
    _validar_integridade(meta, pasta)
    revisao = {
        "id_execucao": meta["id_execucao"], "data_revisao_humana": audit.agora_iso(), "decisao_humana": decisao,
        "revisor": revisor.strip(), "justificativa_humana": justificativa.strip(),
        "itens_confirmados": {chave: True for chave in _ITENS_REVISAO}, "sha256_peca": meta["sha256_peca"],
    }
    if not audit.atualizar_decisao_humana(meta["id_execucao"], decisao, revisor.strip(), justificativa.strip(),
                                           arquivo_saida_final=meta["arquivo_peca"], caminho_log=caminho_log):
        raise ValueError("Registro de auditoria da imagem não encontrado.")
    _salvar_json(pasta / "revisao.json", revisao)
    meta.update(revisao)
    _salvar_json(arquivo_meta, meta)
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    importar = sub.add_parser("importar", help="Importa o PNG local do Draw Things para evidência do RF10.")
    importar.add_argument("arquivo", type=Path, help="PNG exportado em resultados/imagens/.")
    importar.add_argument("--caso", default="caso01_texto")
    revisar = sub.add_parser("revisar", help="Registra a inspeção humana da peça gerada.")
    revisar.add_argument("pasta", type=Path)
    revisar.add_argument("--revisor", required=True, help="Identificador fictício do revisor no protótipo.")
    revisar.add_argument("--justificativa", required=True)
    revisar.add_argument("--decisao", required=True, choices=("Aprovada", "Rejeitada"))
    revisar.add_argument("--confirmar-textos", action="store_true")
    revisar.add_argument("--confirmar-simbolos", action="store_true")
    revisar.add_argument("--confirmar-maos-objetos", action="store_true")
    revisar.add_argument("--confirmar-coerencia", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.comando == "importar":
            res = importar_imagem_draw_things(args.arquivo, args.caso)
            print(f"Peça salva: {res['arquivo_peca']}")
            print("PENDENTE: inspecione a imagem e execute o comando revisar antes de utilizá-la.")
        else:
            confirmar_revisao(
                args.pasta, args.revisor, args.justificativa, decisao=args.decisao,
                textos_confirmados=args.confirmar_textos, simbolos_confirmados=args.confirmar_simbolos,
                maos_objetos_confirmados=args.confirmar_maos_objetos,
                coerencia_confirmada=args.confirmar_coerencia,
            )
            print("Inspeção humana da imagem registrada.")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Erro: {ocultar_segredos(str(exc))}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
