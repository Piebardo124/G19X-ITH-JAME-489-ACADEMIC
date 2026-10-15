import sys
from sqlalchemy import text
from app.db.database import engine

def upgrade_database():
    print("Iniciando verificación y migración de esquema...")
    with engine.connect() as conn:
        try:
            # Ejecución de los cambios
            conn.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_by VARCHAR;"))
            conn.commit()
            
            print("Migración exitosa: transacciones confirmadas. Las columnas updated_at y updated_by están listas.")
        except Exception as e:
            conn.rollback()
            print(f"Error crítico en migración: {e}")
            sys.exit(1)
if __name__ == "__main__":
    upgrade_database()