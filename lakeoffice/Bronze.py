# Ingestão para DataFrame
df_raw = pd.read_json("/content/raw_events.json")

# Gravando na Bronze com Delta Lake
bronze_path = "/content/lakehouse/bronze/orders"
write_deltalake(bronze_path, df_raw, mode="append")

# Consultando via DuckDB
con = duckdb.connect()
print("--- Camada Bronze (Tabela Delta) ---")
con.execute(f"SELECT * FROM delta_scan('{bronze_path}')").df()
