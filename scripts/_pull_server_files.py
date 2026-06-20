import paramiko
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.100.12',username='oitamar',password='oitapere',timeout=20)
sftp=c.open_sftp()
for remote, local in [
 ('/home/oitamar/dashboard-financeiro-web/sati_source.py', r'c:\python\BIWEB\scripts\_server_sati_source.py'),
 ('/opt/nfe-web/deploy/provision_bi_tenant.py', r'c:\python\BIWEB\scripts\_server_provision_bi_tenant.py'),
 ('/opt/nfe-web/frontend/painel/painel.js', r'c:\python\BIWEB\scripts\_server_painel.js'),
]:
 try:
  sftp.get(remote, local); print('ok', remote)
 except Exception as e:
  print('fail', remote, e)
sftp.close()
