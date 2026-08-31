# Agregação SQL usando DuckDB
gold_path = "/content/lakehouse/gold/sales_by_category"

df_gold = con.execute(f"""
    SELECT 
        category,
        COUNT(order_id) AS total_pedidos,
        ROUND(SUM(amount), 2) AS receita_total,
        ROUND(AVG(amount), 2) AS ticket_medio
    FROM delta_scan('{silver_path}')
    GROUP BY category
""").df()

# Gravando na Gold
write_deltalake(gold_path, df_gold, mode="overwrite")

print("--- Camada Gold (Visão Executiva / BI) ---")
con.execute(f"SELECT * FROM delta_scan('{gold_path}')").df()Camada Gold (Agregações de Negócio)

