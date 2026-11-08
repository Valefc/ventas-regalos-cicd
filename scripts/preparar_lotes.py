"""Separa ventas_regalos_2011.csv en referencia.csv, control.csv, nuevo.csv y actual.csv (copia de control)."""
import shutil
import sys
from pathlib import Path

import pandas as pd

origen = Path(sys.argv[1] if len(sys.argv) > 1 else "ventas_regalos_2011.csv")
destino = Path("datos")
destino.mkdir(exist_ok=True)

df = pd.read_csv(origen, dtype=str, keep_default_na=False)
for lote in ("referencia", "control", "nuevo"):
    parte = df[df["lote"] == lote]
    parte.to_csv(destino / f"{lote}.csv", index=False)
    print(f"{lote}: {len(parte)} filas -> datos/{lote}.csv")
shutil.copy(destino / "control.csv", destino / "actual.csv")
print("actual.csv = copia de control.csv (primera publicación)")
