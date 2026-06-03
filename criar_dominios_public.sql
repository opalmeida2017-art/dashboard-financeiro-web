-- Copia dominios do schema c3332 para public (necessario para as tabelas do SATI)
DO $$
DECLARE
    r RECORD;
    ddl TEXT;
BEGIN
    FOR r IN
        SELECT
            t.typname,
            format_type(t.typbasetype, t.typtypmod) AS base_type,
            t.typnotnull,
            pg_get_expr(t.typdefaultbin, 0) AS default_expr
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'c3332'
          AND t.typtype = 'd'
        ORDER BY t.typname
    LOOP
        IF EXISTS (
            SELECT 1
            FROM pg_type pt
            JOIN pg_namespace pn ON pn.oid = pt.typnamespace
            WHERE pn.nspname = 'public'
              AND pt.typname = r.typname
              AND pt.typtype = 'd'
        ) THEN
            CONTINUE;
        END IF;

        ddl := format('CREATE DOMAIN public.%I AS %s', r.typname, r.base_type);
        IF r.typnotnull THEN
            ddl := ddl || ' NOT NULL';
        END IF;
        IF r.default_expr IS NOT NULL AND r.default_expr <> '' THEN
            ddl := ddl || ' DEFAULT ' || r.default_expr;
        END IF;

        EXECUTE ddl;
    END LOOP;
END $$;

SELECT count(*) AS dominios_public
FROM pg_type t
JOIN pg_namespace n ON n.oid = t.typnamespace
WHERE n.nspname = 'public' AND t.typtype = 'd';
