from database.postgres_config import engine, Base
from database.postgres_models import *

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("Creating all tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
