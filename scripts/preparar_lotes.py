"""Separa el CSV original en datos/referencia.csv, datos/control.csv, datos/nuevo.csv
y crea datos/actual.csv como copia de control.csv.

Uso (desde la raíz del proyecto):
    python scripts/preparar_lotes.py
Por defecto lee datos/original/ventas_regalos_2011.csv (o el único .csv de datos/original/).
También se puede indicar otra ruta:
    python scripts/preparar_lotes.py ruta/al/archivo.csv
El archivo original no se modifica.
"""
import shutil
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "datos"
ORIGINAL = DATOS / "original"

if len(sys.argv) > 1:
    origen = Path(sys.argv[1])
else:
    origen = ORIGINAL / "ventas_regalos_2011.csv"
    if not origen.exists():
        candidatos = sorted(ORIGINAL.glob("*.csv"))
        if len(candidatos) != 1:
            sys.exit(f"No encontré {origen}. Pon el CSV en datos/original/ o indica la ruta como argumento.")
        origen = candidatos[0]

print(f"Leyendo: {origen}")
df = pd.read_csv(origen, dtype=str, keep_default_na=False)
for lote in ("referencia", "control", "nuevo"):
    parte = df[df["lote"] == lote]
    destino = DATOS / f"{lote}.csv"
    parte.to_csv(destino, index=False)
    print(f"{lote}: {len(parte)} filas -> {destino.relative_to(RAIZ)}")
shutil.copy(DATOS / "control.csv", DATOS / "actual.csv")
print("actual.csv = copia de control.csv (primera publicación)")
