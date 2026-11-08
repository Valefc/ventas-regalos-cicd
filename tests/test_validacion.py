"""Pruebas automatizadas con datos pequeños e independientes."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validar import COLUMNAS, validar_archivo, validar_df  # noqa: E402


def fila(**kw):
    base = {
        "InvoiceNo": "550001", "StockCode": "85123A", "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
        "InvoiceDate": "2011-10-05 09:30:00", "Quantity": "6", "UnitPrice": "2.55", "lote": "control",
    }
    base.update(kw)
    return base


def df_de(*filas):
    return pd.DataFrame(list(filas), columns=COLUMNAS, dtype=str)


def test_archivo_valido():
    df = df_de(fila(), fila(InvoiceNo="550002", InvoiceDate="2011-10-31 23:59:59"))
    assert validar_df(df, "valido.csv") == []


def test_encabezado_faltante():
    df = df_de(fila()).drop(columns=["UnitPrice"])
    errores = validar_df(df, "sin_precio.csv")
    assert errores and "UnitPrice" in errores[0]


def test_fecha_imposible():
    df = df_de(fila(), fila(InvoiceNo="550002", InvoiceDate="2011-10-31 09:00:00"),
               fila(InvoiceNo="550003", InvoiceDate="2011-11-31 09:00:00", lote="nuevo"))
    errores = validar_df(df, "fecha.csv")
    assert any("InvoiceDate" in e and "fila 4" in e for e in errores)


def test_fecha_imposible_noviembre_31():
    df = df_de(fila(InvoiceDate="2011-11-31 09:00:00", lote="nuevo"))
    errores = validar_df(df, "nov31.csv")
    assert any("inválida" in e and "InvoiceDate" in e for e in errores)


@pytest.mark.parametrize("valor", ["0", "-3", "2.5", "abc", ""])
def test_cantidad_no_valida(valor):
    errores = validar_df(df_de(fila(Quantity=valor)), "cantidad.csv")
    assert any("Quantity" in e for e in errores)


@pytest.mark.parametrize("valor", ["-1.25", "0", "inf", "nan", "gratis"])
def test_precio_no_valido(valor):
    errores = validar_df(df_de(fila(UnitPrice=valor)), "precio.csv")
    assert any("UnitPrice" in e for e in errores)


def test_factura_repetida_se_acepta():
    df = df_de(fila(InvoiceNo="550010", StockCode="A1"), fila(InvoiceNo="550010", StockCode="B2"))
    assert validar_df(df, "repetida.csv") == []


def test_campos_de_texto_vacios():
    errores = validar_df(df_de(fila(Description="  ")), "vacio.csv")
    assert any("Description" in e for e in errores)


def test_fecha_fuera_del_mes_del_lote():
    errores = validar_df(df_de(fila(InvoiceDate="2011-09-30 10:00:00")), "mes.csv")
    assert any("no corresponde al mes" in e for e in errores)


def test_archivo_con_dos_lotes():
    df = df_de(fila(), fila(InvoiceNo="2", InvoiceDate="2011-11-02 10:00:00", lote="nuevo"))
    assert any("mezcla varios lotes" in e for e in validar_df(df, "mezcla.csv"))


def test_lote_no_permitido_en_actual(tmp_path):
    p = tmp_path / "actual.csv"
    df_de(fila(InvoiceDate="2011-09-10 10:00:00", lote="referencia")).to_csv(p, index=False)
    errores = validar_archivo(p, lotes_permitidos={"control", "nuevo"})
    assert any("no está permitido" in e for e in errores)


def test_archivo_inexistente(tmp_path):
    assert validar_archivo(tmp_path / "no_existe.csv")


def test_archivo_sin_filas(tmp_path):
    p = tmp_path / "vacio.csv"
    pd.DataFrame(columns=COLUMNAS).to_csv(p, index=False)
    assert any("no tiene filas" in e for e in validar_archivo(p))
