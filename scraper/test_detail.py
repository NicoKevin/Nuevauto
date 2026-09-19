"""Script de purge: vide la table annonces dans Supabase."""
import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]

client = create_client(url, key)

# Compter les records actuels
result = client.table("annonces").select("id", count="exact").execute()
print(f"Records avant purge: {result.count}")

# Supprimer tous les records
client.table("annonces").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

# Vérifier
result2 = client.table("annonces").select("id", count="exact").execute()
print(f"Records après purge: {result2.count}")
print("Table annonces vidée avec succès!")
