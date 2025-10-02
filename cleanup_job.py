# cleanup_job.py
from app import app, db, Missa # Importe do seu app principal
from datetime import date, timedelta

def run_cleanup():
    """Encontra e arquiva missas antigas."""
    with app.app_context():
        cutoff_date = date.today() - timedelta(days=15)
        
        # Esta é uma forma mais eficiente de atualizar, não carrega todos os objetos na memória
        masses_updated = db.session.query(Missa).filter(
            Missa.data < cutoff_date,
            Missa.arquivada == False
        ).update({"arquivada": True})

        if masses_updated > 0:
            db.session.commit()
            print(f"Arquivadas {masses_updated} missas antigas com sucesso.")
        else:
            print("Nenhuma missa antiga para arquivar.")

if __name__ == '__main__':
    print("Iniciando tarefa de limpeza...")
    run_cleanup()
    print("Tarefa de limpeza finalizada.")