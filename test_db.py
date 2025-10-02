# test_db.py
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    print("ERRO: Variável de ambiente DATABASE_URL não encontrada.")
else:
    # Corrige o prefixo para o SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    print("Tentando conectar ao banco de dados...")
    print(f"URL: {DATABASE_URL.split('@')[0]}@...") # Imprime a URL sem a senha

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as connection:
            print("Conexão bem-sucedida!")
            result = connection.execute(text("SELECT 1"))
            for row in result:
                print("Teste de query bem-sucedido:", row)
        print("Teste finalizado com sucesso.")

    except Exception as e:
        print("\n--- FALHA AO CONECTAR ---")
        print(f"Ocorreu um erro: {e}")
        print("--------------------------")