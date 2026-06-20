import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.100.12", username="oitamar", password="oitapere", timeout=25)
sql = r"""
sudo -u postgres psql -d bi_rio_bonito -c "SELECT * FROM c3219.tipoveiculo ORDER BY 1 LIMIT 20;"
sudo -u postgres psql -d bi_rio_bonito -c "
SELECT tv.codtipoveiculo, tv.descricao, v.veiculoproprio, count(*) 
FROM c3219.veiculo v 
LEFT JOIN c3219.tipoveiculo tv ON tv.codtipoveiculo = v.codtipoveiculo
GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 25;"
sudo -u postgres psql -d bi_rio_bonito -c "
SELECT column_name FROM information_schema.columns WHERE table_schema='c3219' AND table_name='tipoveiculo' ORDER BY ordinal_position;"
"""
_, o, e = c.exec_command(sql, timeout=60)
print((o.read() + e.read()).decode("utf-8", "replace"))
c.close()
