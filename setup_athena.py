import boto3
import sys
import os
import time
import re
from botocore.exceptions import ClientError


# ============================================================
# CARREGAR CREDENCIAIS
# ============================================================

def carregar_credenciais(caminhos_possiveis=["AWS_CREDENTIAL.env", "AWS_CREDENTIAL"]):
    caminho_encontrado = None
    for caminho in caminhos_possiveis:
        if os.path.exists(caminho):
            caminho_encontrado = caminho
            break

    if not caminho_encontrado:
        print(f"\nERRO: Nenhum arquivo de credenciais encontrado ({', '.join(caminhos_possiveis)}).")
        sys.exit(1)

    credenciais = {}
    with open(caminho_encontrado, "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#") and "=" in linha:
                chave, valor = linha.split("=", 1)
                credenciais[chave.strip()] = valor.strip().strip('"').strip("'")

    chaves_obrigatorias = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
    for chave in chaves_obrigatorias:
        if chave not in credenciais:
            print(f"\nERRO: Chave '{chave}' ausente no arquivo '{caminho_encontrado}'.")
            sys.exit(1)

    return credenciais


# ============================================================
# ARGUMENTO E CONFIGURAÇÃO DINÂMICA
# ============================================================

if len(sys.argv) != 2:
    print()
    print("Uso:")
    print("    python setup_athena.py NOME_DO_BUCKET")
    print()
    print("Exemplo:")
    print("    python setup_athena.py clarayuri12")
    print()
    sys.exit(1)

BUCKET_NAME = sys.argv[1]
CREDS = carregar_credenciais()

AWS_ACCESS_KEY_ID = CREDS["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = CREDS["AWS_SECRET_ACCESS_KEY"]
AWS_SESSION_TOKEN = CREDS.get("AWS_SESSION_TOKEN")
AWS_REGION = CREDS["AWS_REGION"]

# O nome do banco é gerado dinamicamente a partir do nome do bucket (substituindo '-' por '_')
DB_SUFFIX = re.sub(r"[^a-zA-Z0-9_]", "_", BUCKET_NAME).lower()
DATABASE_NAME = f"datalake_db_{DB_SUFFIX}"
OUTPUT_LOCATION = f"s3://{BUCKET_NAME}/athena-results/"


# ============================================================
# CLIENTE ATHENA
# ============================================================

athena = boto3.client(
    "athena",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    aws_session_token=AWS_SESSION_TOKEN
)


# ============================================================
# EXECUTOR DE QUERIES COM POLLING
# ============================================================

def executar_query(query, database=None, descricao="Executando comando"):
    print(f"\n-> {descricao}...")
    
    params = {
        "QueryString": query,
        "ResultConfiguration": {"OutputLocation": OUTPUT_LOCATION}
    }
    if database:
        params["QueryExecutionContext"] = {"Database": database}

    try:
        response = athena.start_query_execution(**params)
        query_execution_id = response["QueryExecutionId"]

        while True:
            status_response = athena.get_query_execution(QueryExecutionId=query_execution_id)
            status = status_response["QueryExecution"]["Status"]["State"]

            if status in ["SUCCEEDED"]:
                print(f"[OK] Sucesso ({query_execution_id})")
                return query_execution_id
            elif status in ["FAILED", "CANCELLED"]:
                motivo = status_response["QueryExecution"]["Status"].get("StateChangeReason", "Erro desconhecido")
                print(f"[ERRO] Falha na query: {motivo}")
                return None

            time.sleep(1)

    except ClientError as e:
        print(f"[ERRO BOTO3]: {e}")
        return None


# ============================================================
# DEFINIÇÕES DDL DINÂMICAS
# ============================================================

QUERIES_SETUP = [
    (
        f"Criando Banco de Dados ({DATABASE_NAME})",
        None,
        f"CREATE DATABASE IF NOT EXISTS {DATABASE_NAME};"
    ),
    (
        "Limpando Tabela Clientes antiga",
        DATABASE_NAME,
        f"DROP TABLE IF EXISTS {DATABASE_NAME}.raw_clientes;"
    ),
    (
        "Limpando Tabela Pedidos antiga",
        DATABASE_NAME,
        f"DROP TABLE IF EXISTS {DATABASE_NAME}.raw_pedidos;"
    ),
    (
        "Limpando Tabela Produtos antiga",
        DATABASE_NAME,
        f"DROP TABLE IF EXISTS {DATABASE_NAME}.raw_produtos;"
    ),
    (
        "Criando Tabela Clientes (JSON Lines)",
        DATABASE_NAME,
        f"""
        CREATE EXTERNAL TABLE {DATABASE_NAME}.raw_clientes (
            cliente_id INT,
            nome STRING,
            cidade STRING,
            estado STRING
        )
        PARTITIONED BY (ingest_date STRING)
        ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
        STORED AS TEXTFILE
        LOCATION 's3://{BUCKET_NAME}/raw/clientes/';
        """
    ),
    (
        "Criando Tabela Pedidos (CSV)",
        DATABASE_NAME,
        f"""
        CREATE EXTERNAL TABLE {DATABASE_NAME}.raw_pedidos (
            pedido_id INT,
            cliente_id INT,
            produto_id INT,
            quantidade INT,
            valor DOUBLE,
            data_pedido STRING
        )
        PARTITIONED BY (ingest_date STRING)
        ROW FORMAT DELIMITED
        FIELDS TERMINATED BY ','
        STORED AS TEXTFILE
        LOCATION 's3://{BUCKET_NAME}/raw/pedidos/'
        TBLPROPERTIES ('skip.header.line.count'='1');
        """
    ),
    (
        "Criando Tabela Produtos (CSV)",
        DATABASE_NAME,
        f"""
        CREATE EXTERNAL TABLE {DATABASE_NAME}.raw_produtos (
            produto_id INT,
            nome STRING,
            categoria STRING,
            preco DOUBLE
        )
        PARTITIONED BY (ingest_date STRING)
        ROW FORMAT DELIMITED
        FIELDS TERMINATED BY ','
        STORED AS TEXTFILE
        LOCATION 's3://{BUCKET_NAME}/raw/produtos/'
        TBLPROPERTIES ('skip.header.line.count'='1');
        """
    ),
    (
        "Reparando Partições de Clientes",
        DATABASE_NAME,
        f"MSCK REPAIR TABLE {DATABASE_NAME}.raw_clientes;"
    ),
    (
        "Reparando Partições de Pedidos",
        DATABASE_NAME,
        f"MSCK REPAIR TABLE {DATABASE_NAME}.raw_pedidos;"
    ),
    (
        "Reparando Partições de Produtos",
        DATABASE_NAME,
        f"MSCK REPAIR TABLE {DATABASE_NAME}.raw_produtos;"
    )
]


# ============================================================
# TESTE ANALÍTICO
# ============================================================

def testar_consulta_analitica():
    query_teste = f"""
    SELECT 
        p.pedido_id,
        c.nome AS cliente,
        c.cidade,
        pr.nome AS produto,
        p.quantidade,
        p.valor AS total_pedido
    FROM {DATABASE_NAME}.raw_pedidos p
    JOIN {DATABASE_NAME}.raw_clientes c ON p.cliente_id = c.cliente_id
    JOIN {DATABASE_NAME}.raw_produtos pr ON p.produto_id = pr.produto_id
    ORDER BY p.pedido_id;
    """
    
    qid = executar_query(query_teste, DATABASE_NAME, "Testando Consulta Analítica (JOIN Clientes + Pedidos + Produtos)")
    if qid:
        resultados = athena.get_query_results(QueryExecutionId=qid)
        print("\n" + "=" * 80)
        print(f"RESULTADO ANALÍTICO - DATA LAKE ({BUCKET_NAME})")
        print("=" * 80)
        for linha in resultados["ResultSet"]["Rows"]:
            valores = [col.get("VarCharValue", "") for col in linha["Data"]]
            print(" | ".join(valores))
        print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("      SETUP DO AMAZON ATHENA / DATA CATALOG")
    print("=" * 60)
    print(f"Bucket Alvo     : {BUCKET_NAME}")
    print(f"Database Gerado : {DATABASE_NAME}")
    print(f"Output Queries  : {OUTPUT_LOCATION}")

    for descricao, db, sql in QUERIES_SETUP:
        res = executar_query(sql, db, descricao)
        if not res:
            print("\nInterrompendo devido a erro no setup.")
            sys.exit(1)

    print("\nEstrutura de tabelas sincronizada com sucesso!")
    testar_consulta_analitica()


if __name__ == "__main__":
    main()