"""Adiciona arquitetura multi-tenant com apartamentos e usuarios

Revision ID: 2b1a8f9c7d4e  # O seu ID será diferente
Revises: # (Este campo pode ter o ID da migração anterior, se houver) 
Create Date: 2025-08-13 02:00:00.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b1a8f9c7d4e' # O seu ID será diferente
down_revision: Union[str, None] = None # O seu ID "down" será diferente
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Esta função aplica todas as alterações para transformar a base de dados
    numa arquitetura multi-tenant.
    """
    print("Iniciando migração para arquitetura multi-tenant...")

    # --- PASSO 1: Criar as novas tabelas de gestão (apartamentos, usuarios, configs) ---
    print("-> Criando tabela 'apartamentos'...")
    op.execute('''
        CREATE TABLE "apartamentos" (
            "id" SERIAL PRIMARY KEY,
            "nome_empresa" TEXT NOT NULL,
            "status" TEXT DEFAULT 'ativo',
            "data_criacao" TEXT NOT NULL,
            "data_vencimento" TEXT, 
            "notas_admin" TEXT
        )
    ''')

    print("-> Criando tabela 'usuarios'...")
    op.execute('''
        CREATE TABLE "usuarios" (
            "id" SERIAL PRIMARY KEY,
            "apartamento_id" INTEGER NOT NULL,
            "email" TEXT UNIQUE NOT NULL,
            "password_hash" TEXT NOT NULL,
            "nome" TEXT,
            "role" TEXT DEFAULT 'usuario',
            FOREIGN KEY("apartamento_id") REFERENCES "apartamentos"("id")
        )
    ''')

    print("-> Criando tabela 'configuracoes_robo'...")
    op.execute('''
        CREATE TABLE "configuracoes_robo" (
            "apartamento_id" INTEGER NOT NULL,
            "chave" TEXT NOT NULL,
            "valor" TEXT,
            PRIMARY KEY ("apartamento_id", "chave")
        )
    ''')
    
    # --- PASSO 2: Adicionar a coluna 'apartamento_id' a todas as tabelas de dados ---
    tabelas_de_dados = [
        "relFilViagensFatCliente",
        "relFilViagensCliente",
        "relFilDespesasGerais",
        "relFilContasReceber",
        "relFilContasPagarDet"
    ]
    for tabela in tabelas_de_dados:
        print(f"-> Adicionando coluna 'apartamento_id' à tabela '{tabela}'...")
        op.execute(f'''
            ALTER TABLE "{tabela}"
            ADD COLUMN "apartamento_id" INTEGER;
        ''')
        # NOTA: Em um cenário real com dados existentes, você precisaria de uma lógica
        # para preencher este campo com um valor padrão, por exemplo:
        # op.execute(f'UPDATE "{tabela}" SET apartamento_id = 1 WHERE apartamento_id IS NULL')

    # --- PASSO 3: Recriar a tabela 'static_expense_groups' com a nova estrutura ---
    print("-> Recriando a tabela 'static_expense_groups' com suporte multi-tenant...")
    op.execute('DROP TABLE "static_expense_groups";')
    op.execute('''
        CREATE TABLE "static_expense_groups" (
            "apartamento_id" INTEGER NOT NULL, 
            "group_name" TEXT NOT NULL,
            "is_despesa" TEXT DEFAULT 'S',
            "is_custo_viagem" TEXT DEFAULT 'N',
            PRIMARY KEY ("apartamento_id", "group_name")
        )
    ''')

    print("Migração para multi-tenant concluída com sucesso!")


def downgrade() -> None:
    """
    Esta função reverte todas as alterações, retornando a base de dados
    ao estado de inquilino único (single-tenant).
    """
    print("Revertendo migração multi-tenant...")

    # --- PASSO 1 (reverso): Recriar a versão antiga da 'static_expense_groups' ---
    print("-> Recriando a tabela antiga 'static_expense_groups'...")
    op.execute('DROP TABLE "static_expense_groups";')
    op.execute('''
        CREATE TABLE "static_expense_groups" (
            "group_name" TEXT PRIMARY KEY,
            "is_despesa" TEXT DEFAULT 'S',
            "is_custo_viagem" TEXT DEFAULT 'N'
        )
    ''')

    # --- PASSO 2 (reverso): Remover a coluna 'apartamento_id' das tabelas de dados ---
    tabelas_de_dados = [
        "relFilViagensFatCliente",
        "relFilViagensCliente",
        "relFilDespesasGerais",
        "relFilContasReceber",
        "relFilContasPagarDet"
    ]
    for tabela in tabelas_de_dados:
        print(f"-> Removendo coluna 'apartamento_id' da tabela '{tabela}'...")
        op.execute(f'ALTER TABLE "{tabela}" DROP COLUMN "apartamento_id";')

    # --- PASSO 3 (reverso): Apagar as novas tabelas de gestão ---
    print("-> Apagando tabelas de gestão...")
    op.execute('DROP TABLE "configuracoes_robo";')
    op.execute('DROP TABLE "usuarios";')
    op.execute('DROP TABLE "apartamentos";')

    print("Reversão da migração concluída teste.")
    
    