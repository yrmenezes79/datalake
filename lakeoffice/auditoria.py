# 1. Simular uma alteração acidental / atualização na camada Silver
df_update = df_silver.copy()
df_update["amount"] = (
    df_update["amount"] * 2
)  # Dobrando valores indevidamente
write_deltalake(silver_path, df_update, mode="overwrite")

# 2. Inspecionar o histórico da tabela Delta
dt = DeltaTable(silver_path)
history = dt.history()
print(
    f"Versões registradas na tabela: {len(history)} transações no log Delta."
)

# 3. Time Travel: Consultando a versão original (Versão 0)
df_original = con.execute(
    f"SELECT * FROM delta_scan('{silver_path}')"
).df()  # Versão atual (alterada)
dt.load_as_version(0)  # Carrega o estado da Versão 0

print("\n--- Dados da Versão 0 (Antes do update indevido) ---")
display(dt.to_pandas())Ponto Alto da Aula — Time Travel & Log de Auditoria
