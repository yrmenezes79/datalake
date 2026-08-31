import json
import os
import duckdb
import pandas as pd
from deltalake import DeltaTable, write_deltalake

# Criar diretórios do Lakehouse
os.makedirs("/content/lakehouse/bronze", exist_ok=True)
os.makedirs("/content/lakehouse/silver", exist_ok=True)
os.makedirs("/content/lakehouse/gold", exist_ok=True)

# Simulação de lote de dados brutos (Raw/Landing)
raw_data = [
    {
        "order_id": 101,
        "customer_id": "C1",
        "category": "Eletronicos",
        "amount": 1200.50,
        "ts": "2026-08-30 10:00:00",
    },
    {
        "order_id": 102,
        "customer_id": "C2",
        "category": "Moveis",
        "amount": 450.00,
        "ts": "2026-08-30 10:05:00",
    },
    {
        "order_id": 103,
        "customer_id": None,
        "category": "Livros",
        "amount": 80.00,
        "ts": "2026-08-30 10:10:00",
    },  # Dado inconsistente (sem customer)
    {
        "order_id": 101,
        "customer_id": "C1",
        "category": "Eletronicos",
        "amount": 1200.50,
        "ts": "2026-08-30 10:00:00",
    },  # Duplicata
    {
        "order_id": 104,
        "customer_id": "C3",
        "category": "Eletronicos",
        "amount": 2300.00,
        "ts": "2026-08-30 10:15:00",
    },
]

with open("/content/raw_events.json", "w") as f:
  json.dump(raw_data, f)

print("✅ Ambiente e dados brutos gerados com sucesso!")
