"""Montagem de contexto da página Fluxo de viagem (servidor e API async)."""

from __future__ import annotations



import json

from typing import Any



from app.core import logic

from app.data import data_manager as dm

from app.utils.helpers import normalize_placa_filter, parse_filters


def _listar_placas_fluxo(apartamento_id: int) -> list[dict[str, str]]:
    """Lista placas para a busca do fluxo sem carregar a consulta pesada de MDF-e."""
    try:
        placas = logic.get_unique_plates_with_types(
            apartamento_id=apartamento_id,
            tipo_negocio_filter="Todos",
        )
    except Exception as exc:
        print(f"Aviso: não foi possível carregar placas do fluxo: {exc}")
        return []

    visto: set[str] = set()
    out: list[dict[str, str]] = []
    for item in placas or []:
        if isinstance(item, dict):
            placa = str(item.get("placa") or "").strip().upper()
            tipo = str(item.get("tipo") or "").strip()
        else:
            placa = str(item or "").strip().upper()
            tipo = ""
        if not placa or placa in visto:
            continue
        visto.add(placa)
        out.append({"placa": placa, "tipo": tipo})
    return out





def build_fluxo_viagem_context(

    apartamento_id: int,

    args,

    *,

    salvar_monitor: bool = True,

) -> dict[str, Any]:

    args = dm.extrair_query_fluxo(args)

    filters = parse_filters(args)

    start_eff, end_eff = dm.resolver_intervalo_fluxo(

        apartamento_id, filters["start_date_obj"], filters["end_date_obj"]

    )

    if not filters["start_date_str"]:

        filters["start_date_str"] = start_eff.strftime("%Y-%m-%d")

        filters["end_date_str"] = end_eff.strftime("%Y-%m-%d")



    historico_placa = args.get("historico") == "1"

    placa_arg = normalize_placa_filter(args.get("placa"))



    if historico_placa and placa_arg and placa_arg != "Todos":

        rows = logic.get_fluxo_viagem_historico(

            apartamento_id=apartamento_id,

            start_date=start_eff,

            end_date=end_eff,

            placa=placa_arg,

            filial_filter=[],

        )

        modo = "historico"

        placa_historico = placa_arg

    else:

        rows = logic.get_fluxo_veiculos_resumo(

            apartamento_id=apartamento_id,

            start_date=start_eff,

            end_date=end_eff,

            filial_filter=[],

        )

        modo = "lista"

        placa_historico = None



    comprovante_filtro = dm.normalizar_filtro_comprovante_fluxo(args.get("comprovante"))

    mdfe_filtro = dm.normalizar_filtro_mdfe_fluxo(args.get("mdfe"))

    total_antes_filtro = len(rows)

    rows = dm.filtrar_fluxo_por_comprovante(rows, comprovante_filtro)

    rows = dm.filtrar_fluxo_por_mdfe(rows, mdfe_filtro)



    placas = _listar_placas_fluxo(apartamento_id)



    pendentes_coleta = dm.coletar_numeros_pendentes_comprovante(rows)

    from app.core import logic as logic_core



    coleta_auto = logic_core.coleta_comprovante_automatica_habilitada(apartamento_id)

    if not coleta_auto:

        pendentes_coleta = []



    if salvar_monitor:

        try:

            from infra.cloud.fluxo_monitor import salvar_lista_fluxo



            salvar_lista_fluxo(

                apartamento_id,

                rows,

                start_date=filters["start_date_str"],

                end_date=filters["end_date_str"],

                modo=modo,

                numeros_pendentes=pendentes_coleta,

            )

        except Exception as exc:

            print(f"Aviso: não foi possível salvar lista do fluxo: {exc}")



    return {

        "rows": rows,

        "placas": placas,

        "modo": modo,

        "placa_historico": placa_historico,

        "selected_placa": placa_arg,

        "selected_start_date": filters["start_date_str"],

        "selected_end_date": filters["end_date_str"],

        "selected_comprovante_filtro": comprovante_filtro,

        "selected_mdfe_filtro": mdfe_filtro,

        "total_antes_filtro_comprovante": total_antes_filtro,

        "pendentes_coleta_json": json.dumps(pendentes_coleta),

        "pendentes_coleta": pendentes_coleta,

        "coleta_automatica_habilitada": coleta_auto,

    }

