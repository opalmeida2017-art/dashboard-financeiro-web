# logic.py
import pandas as pd
import matplotlib.pyplot as plt
import io

def processar_ficheiro_excel(caminho_ficheiro):
    """
    Lê um ficheiro Excel e retorna um DataFrame do pandas.
    Esta função é idêntica à sua lógica de desktop.
    """
    try:
        df = pd.read_excel(caminho_ficheiro)
        #... aqui pode adicionar mais lógica de processamento de dados...
        return df
    except Exception as e:
        print(f"Erro ao processar o ficheiro: {e}")
        return None

def criar_grafico_matplotlib(df):
    """
    Cria um gráfico matplotlib a partir de um DataFrame e retorna o objeto da figura.
    """
    fig, ax = plt.subplots()
    # Exemplo simples: gráfico de barras da primeira coluna numérica
    coluna_numerica = df.select_dtypes(include='number').columns.FirstOrDefault()
    if coluna_numerica:
        df.plot(kind='bar', x=df.columns, y=coluna_numerica, ax=ax)
    else:
        # Fallback se não houver colunas numéricas
        ax.text(0.5, 0.5, 'Não foram encontrados dados numéricos para o gráfico', ha='center')
    
    plt.tight_layout()
    return fig