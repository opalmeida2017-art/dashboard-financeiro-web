#!/usr/bin/env python
"""Vincula um apartamento do BIWEB ao banco SATI (schema c3332)."""

import argparse
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DEFAULT_CONFIG_KEYS = {
    "USE_SATI_SOURCE": "true",
    "SATI_SCHEMA": "c3332",
}


def get_engine(url: str | None = None):
    db_url = url or os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL não definida no .env")
    return create_engine(db_url)


def list_filiais(engine, schema: str):
    with engine.connect() as conn:
        return conn.execute(
            text(
                f"""
                SELECT codfilial, COALESCE(nome, '') AS nome
                FROM {schema}.filial
                ORDER BY codfilial
                """
            )
        ).fetchall()


def vincular(
    apartamento_id: int,
    cod_filial: int | None,
    schema: str = "c3332",
    db_url: str | None = None,
    force: bool = False,
    todas_filiais: bool = False,
):
    engine = get_engine(db_url)
    sati_url = os.getenv("SATI_DATABASE_URL", "").strip()
    sati_engine = create_engine(sati_url) if sati_url else engine

    with engine.connect() as conn:
        apt = conn.execute(
            text(
                "SELECT id, nome_empresa, slug FROM apartamentos WHERE id = :id"
            ),
            {"id": apartamento_id},
        ).fetchone()
        if not apt:
            raise SystemExit(f"Apartamento id={apartamento_id} não encontrado.")

        filiais = []
        if not force:
            try:
                filiais = list_filiais(sati_engine, schema)
            except Exception as exc:
                print(
                    f"Aviso: não foi possível listar filiais no SATI ({exc}). "
                    "Use --force --cod-filial N ou configure SATI_DATABASE_URL."
                )
                if cod_filial is None:
                    cod_filial = 1
                    force = True

        if not force and filiais:
            if cod_filial is None:
                if len(filiais) == 1:
                    cod_filial = int(filiais[0][0])
                else:
                    print("Filiais disponíveis no SATI:")
                    for f in filiais:
                        print(f"  codfilial={f[0]}  {f[1]}")
                    raise SystemExit(
                        "Informe --cod-filial (ex.: --cod-filial 1)"
                    )

            filial_ok = any(int(f[0]) == cod_filial for f in filiais)
            if not filial_ok:
                raise SystemExit(f"codfilial {cod_filial} não existe em {schema}.filial")

        if cod_filial is None:
            cod_filial = 1

        slug = apt[2] or f"apt-{apartamento_id}"
        if slug != "c3332":
            conn.execute(
                text(
                    "UPDATE apartamentos SET slug = :slug WHERE id = :id"
                ),
                {"slug": "c3332", "id": apartamento_id},
            )

        configs = dict(DEFAULT_CONFIG_KEYS)
        if not todas_filiais:
            configs["SATI_COD_FILIAL"] = str(cod_filial)
        for chave, valor in configs.items():
            conn.execute(
                text(
                    """
                    INSERT INTO configuracoes_robo (apartamento_id, chave, valor)
                    VALUES (:apt_id, :chave, :valor)
                    ON CONFLICT (apartamento_id, chave)
                    DO UPDATE SET valor = EXCLUDED.valor
                    """
                ),
                {"apt_id": apartamento_id, "chave": chave, "valor": valor},
            )
        conn.commit()

    print(f"Apartamento {apartamento_id} ({apt[1]}) vinculado ao SATI.")
    print(f"  schema: {schema}")
    print(f"  codfilial: {cod_filial if not todas_filiais else '(todas — sem SATI_COD_FILIAL)'}")
    print(f"  slug: c3332")
    for chave, valor in configs.items():
        print(f"  configuracoes_robo.{chave} = {valor}")
    print()
    print(
        "Confirme no .env: DATABASE_URL apontando para sat1_sati_is "
        "(ex.: postgresql://postgres:SENHA@localhost:5433/sat1_sati_is)"
    )
    print("e USE_SATI_SOURCE=true. Reinicie o app.")


def main():
    parser = argparse.ArgumentParser(description="Vincula apartamento ao SATI")
    parser.add_argument("apartamento_id", type=int, help="ID do apartamento (ex.: 10)")
    parser.add_argument(
        "--cod-filial",
        type=int,
        default=None,
        help="codfilial no SATI (opcional se houver só uma filial)",
    )
    parser.add_argument(
        "--todas-filiais",
        action="store_true",
        help="Não grava SATI_COD_FILIAL (carrega todas as filiais do schema)",
    )
    parser.add_argument("--schema", default="c3332")
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL do banco BIWEB (default: DATABASE_URL do .env)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Grava config sem validar filiais no SATI",
    )
    args = parser.parse_args()
    vincular(
        args.apartamento_id,
        args.cod_filial,
        schema=args.schema,
        db_url=args.database_url,
        force=args.force,
        todas_filiais=args.todas_filiais,
    )


if __name__ == "__main__":
    main()
