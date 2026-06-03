"""
Legado: coleta por planilhas foi descontinuada.
Use logic.executar_atualizacao_bd_sati (robos/coletor_atualizacao_bd.py).
"""

import logic


def executar_todas_as_coletas(apartamento_id: int, start_date_str: str = None, end_date_str: str = None):
    """Redireciona para atualização do banco SATI."""
    return logic.executar_atualizacao_bd_sati(apartamento_id)
