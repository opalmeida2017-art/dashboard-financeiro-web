        import sys
        import os

        # Define o diretório raiz da sua aplicação
        project_home = '/var/www/webroot/ROOT'
        if project_home not in sys.path:
            # Adiciona o diretório raiz ao path do Python para encontrar seus módulos
            sys.path.insert(0, project_home)

        # Tenta encontrar o caminho correto para o ambiente virtual
        # (Ajuste se o caminho for diferente, mas este é o que encontramos)
        venv_path = '/opt/jelastic-python311/lib/python3.11/venv'
        activate_this = os.path.join(venv_path, 'bin', 'activate_this.py')

        try:
            # Ativa o ambiente virtual para este processo WSGI
            if os.path.exists(activate_this):
                with open(activate_this) as f:
                    exec(f.read(), {'__file__': activate_this})
                print("WSGI: Ambiente virtual ativado com sucesso.", file=sys.stderr) # Log para depuração
            else:
                print(f"WSGI WARNING: activate_this.py não encontrado em {activate_this}", file=sys.stderr)
        except Exception as e:
            print(f"WSGI ERROR: Falha ao ativar ambiente virtual: {e}", file=sys.stderr)


        # Importa a instância da aplicação Flask
        # Assumindo que sua instância Flask se chama 'app' dentro de 'app.py'
        try:
            from app import app as application
            print("WSGI: Instância 'app' importada de 'app.py' com sucesso.", file=sys.stderr) # Log para depuração
        except ImportError as e:
            print(f"WSGI ERROR: Falha ao importar 'app' de 'app.py': {e}", file=sys.stderr)
            # Você pode querer definir uma aplicação padrão ou levantar o erro aqui
            # Exemplo de app padrão para erro:
            def application(environ, start_response):
                start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
                return [b'Erro ao carregar a aplicacao WSGI. Verifique os logs.']

        
