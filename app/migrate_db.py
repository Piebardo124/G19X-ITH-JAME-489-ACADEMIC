import logging
import sys
from sqlalchemy import text
from app.db.database import engine

logger = logging.getLogger(__name__)

def upgrade_database():
    logger.info("Iniciando la actualización del esquema de la base de datos.")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;"))
            conn.execute(text("ALTER TABLE alerts ADD COLUMN IF NOT EXISTS updated_by VARCHAR;"))
            conn.commit()

            logger.info("Esquema actualizado correctamente.")
        except Exception:
            conn.rollback()
            logger.exception("No se pudo actualizar el esquema; se revirtieron los cambios.")
            sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    upgrade_database()
