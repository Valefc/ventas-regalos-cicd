"""Validador de lotes de ventas (Online Retail, UCI).

Uso:
    python scripts/validar.py datos/referencia.csv datos/actual.csv

Termina con código 1 si encuentra errores, indicando archivo, fila y campo.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

COLUMNAS = ["InvoiceNo", "StockCode", "Description", "InvoiceDate", "Quantity", "UnitPrice", "lote"]
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
LOTES_VALIDOS = {"referencia": (2011, 9), "control": (2011, 10), "nuevo": (2011, 11)}


class ErrorValidacion(Exception):
    """Error de validación con archivo, fila y campo."""


def _error(archivo, mensaje, fila=None, campo=None):
    partes = [f"Archivo: {archivo}"]
    if fila is not None:
        partes.append(f"fila {fila}")  # fila del archivo (encabezado = 1)
    if campo is not None:
        partes.append(f"campo {campo}")
    return f"{' | '.join(partes)} -> {mensaje}"


def leer_csv(ruta) -> pd.DataFrame:
    ruta = Path(ruta)
    try:
        df = pd.read_csv(ruta, dtype=str, keep_default_na=False, sep=",", encoding="utf-8")
    except FileNotFoundError:
        raise ErrorValidacion(_error(ruta, "el archivo no existe"))
    except Exception as exc:  # archivo ilegible o mal formado
        raise ErrorValidacion(_error(ruta, f"no se pudo leer el CSV ({exc})"))
    return df


def validar_df(df: pd.DataFrame, archivo="(memoria)", lotes_permitidos=None) -> list[str]:
    """Devuelve la lista de errores encontrados (vacía si todo es válido)."""
    errores: list[str] = []

    faltantes = [c for c in COLUMNAS if c not in df.columns]
    if faltantes:
        errores.append(_error(archivo, f"faltan columnas en el encabezado: {', '.join(faltantes)}"))
        return errores
    if list(df.columns) != COLUMNAS:
        errores.append(_error(archivo, f"las columnas deben ser exactamente {COLUMNAS} y están {list(df.columns)}"))
        return errores
    if len(df) < 1:
        errores.append(_error(archivo, "el archivo no tiene filas de datos"))
        return errores

    for idx, row in df.iterrows():
        fila = idx + 2  # +1 por índice base 0, +1 por el encabezado
        for campo in ("InvoiceNo", "StockCode", "Description"):
            if row[campo].strip() == "":
                errores.append(_error(archivo, "el campo está vacío", fila, campo))

        # Fecha real y con formato exacto AAAA-MM-DD HH:MM:SS
        fecha = None
        try:
            fecha = datetime.strptime(row["InvoiceDate"], FORMATO_FECHA)
            if row["InvoiceDate"] != fecha.strftime(FORMATO_FECHA):
                raise ValueError("formato")
        except ValueError:
            errores.append(
                _error(archivo, f"fecha u hora inválida '{row['InvoiceDate']}' (se espera AAAA-MM-DD HH:MM:SS real)", fila, "InvoiceDate")
            )
            fecha = None

        # Cantidad: entero positivo
        q = row["Quantity"].strip()
        if not q.lstrip("+").isdigit() or int(q) <= 0:
            errores.append(_error(archivo, f"debe ser un entero positivo y es '{row['Quantity']}'", fila, "Quantity"))

        # Precio: número finito > 0
        try:
            p = float(row["UnitPrice"])
            if not math.isfinite(p) or p <= 0:
                raise ValueError
        except ValueError:
            errores.append(_error(archivo, f"debe ser un número finito mayor que cero y es '{row['UnitPrice']}'", fila, "UnitPrice"))

        # Fecha coherente con el lote de la fila
        lote = row["lote"].strip()
        if lote not in LOTES_VALIDOS:
            errores.append(_error(archivo, f"lote desconocido '{row['lote']}'", fila, "lote"))
        elif fecha is not None and (fecha.year, fecha.month) != LOTES_VALIDOS[lote]:
            a, m = LOTES_VALIDOS[lote]
            errores.append(
                _error(archivo, f"la fecha {row['InvoiceDate']} no corresponde al mes {a}-{m:02d} del lote '{lote}'", fila, "InvoiceDate")
            )

    # Un solo lote por archivo
    lotes_presentes = set(df["lote"].str.strip())
    if len(lotes_presentes) > 1:
        errores.append(_error(archivo, f"el archivo mezcla varios lotes: {sorted(lotes_presentes)}", campo="lote"))
    elif lotes_permitidos is not None and lotes_presentes and not lotes_presentes <= set(lotes_permitidos):
        errores.append(
            _error(archivo, f"el lote {sorted(lotes_presentes)} no está permitido; se esperaba {sorted(lotes_permitidos)}", campo="lote")
        )
    return errores


def validar_archivo(ruta, lotes_permitidos=None) -> list[str]:
    try:
        df = leer_csv(ruta)
    except ErrorValidacion as exc:
        return [str(exc)]
    return validar_df(df, archivo=ruta, lotes_permitidos=lotes_permitidos)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ref = argv[0] if len(argv) > 0 else "datos/referencia.csv"
    act = argv[1] if len(argv) > 1 else "datos/actual.csv"

    errores = validar_archivo(ref, lotes_permitidos={"referencia"})
    errores += validar_archivo(act, lotes_permitidos={"control", "nuevo"})

    if errores:
        print("VALIDACIÓN FALLIDA")
        for e in errores[:50]:
            print(" -", e)
        if len(errores) > 50:
            print(f" ... y {len(errores) - 50} errores más")
        return 1
    print(f"VALIDACIÓN CORRECTA: {ref} y {act}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
