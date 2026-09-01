# Leitura da Bronze
df_bronze = con.execute(f"SELECT * FROM delta_scan('{bronze_path}')").df()

# Limpeza e Deduplicação
df_silver = df_bronze.dropna(subset=["customer_id"]).drop_duplicates(
    subset=["order_id"]
)

# Gravando na Silver
silver_path = "/content/lakehouse/silver/orders"
write_deltalake(silver_path, df_silver, mode="overwrite")

print("--- Camada Silver (Dados Tratados) ---")
con.execute(f"SELECT * FROM delta_scan('{silver_path}')").df()
