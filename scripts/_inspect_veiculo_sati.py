"""Inspeciona tabela veiculo SATI — campo tipo frota/terceiro/agregado."""
import paramiko

HOST, USER, PASS = "192.168.100.12", "oitamar", "oitapere"

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=25)

    sql = r"""
sudo -u postgres psql -d bi_rio_bonito -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema='c3219' AND table_name='veiculo'
  AND (column_name ILIKE '%proprio%' OR column_name ILIKE '%tipo%' OR column_name ILIKE '%placa%')
ORDER BY ordinal_position;
"

sudo -u postgres psql -d bi_rio_bonito -c "
SELECT veiculoproprio, count(*) FROM c3219.veiculo GROUP BY 1 ORDER BY 2 DESC;
"

sudo -u postgres psql -d bi_rio_bonito -c "
SELECT v.veiculoproprio, v.placa, count(*) AS viagens
FROM c3219.conhecimento c
JOIN c3219.veiculo v ON v.codveiculo = c.codveiculo
WHERE c.cancelado IS DISTINCT FROM 'S'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15;
"

sudo -u postgres psql -d bi_rio_bonito -c "
SELECT c.tipofrete, v.veiculoproprio, count(*)
FROM c3219.conhecimento c
JOIN c3219.veiculo v ON v.codveiculo = c.codveiculo
WHERE c.cancelado IS DISTINCT FROM 'S'
GROUP BY 1,2 ORDER BY 3 DESC LIMIT 20;
"

sudo -u postgres psql -d bi_rio_bonito -c "
SELECT table_name FROM information_schema.tables
WHERE table_schema='c3219' AND table_name ILIKE '%veic%'
ORDER BY 1;
"
"""
    _, o, e = c.exec_command(sql, timeout=60)
    print((o.read() + e.read()).decode("utf-8", "replace"))
    c.close()

if __name__ == "__main__":
    main()
