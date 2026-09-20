"""Extrai dados abertos do Pix (API Olinda do Bacen) e carrega no DuckDB (schema raw)."""
from datetime import datetime
from pathlib import Path
import json

import duckdb
import requests

BASE_URL = "https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata"
RESOURCE = "EstatisticasTransacoesPix"  # ajuste se a documentação exigir parâmetro
TABLE = "estatisticas_transacoes_pix"
PAGE_SIZE = 10000
MAX_PAGES = 200  # trava de segurança contra loop infinito

RAW_DIR = Path("data/raw")
DB_PATH = "data/pix.duckdb"


def fetch_all(resource: str) -> list[dict]:
    rows: list[dict] = []
    for page in range(MAX_PAGES):
        params = {"$format": "json", "$top": PAGE_SIZE, "$skip": page * PAGE_SIZE}
        resp = requests.get(f"{BASE_URL}/{resource}", params=params, timeout=120)
        resp.raise_for_status()
        batch = resp.json().get("value", [])
        if not batch:
            break
        rows.extend(batch)
        print(f"página {page + 1}: {len(batch)} linhas")
    return rows


def save_json(rows: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RAW_DIR / f"{TABLE}_{stamp}.json"
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def load_to_duckdb(json_path: Path) -> None:
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE raw.{TABLE} AS
        SELECT *, current_timestamp AS _loaded_at
        FROM read_json_auto('{json_path.as_posix()}')
        """
    )
    total = con.execute(f"SELECT count(*) FROM raw.{TABLE}").fetchone()[0]
    print(f"raw.{TABLE}: {total} linhas")
    con.close()


if __name__ == "__main__":
    data = fetch_all(RESOURCE)
    if not data:
        raise SystemExit("A API não retornou linhas. Confira o recurso e os parâmetros.")
    load_to_duckdb(save_json(data))