"""Genera el informe de Evidently y la portada (index.html) del sitio.

Uso:
    python scripts/generar_informe.py            # lee datos/referencia.csv y datos/actual.csv
    python scripts/generar_informe.py --archivar # además guarda el informe en evidencias/

Salida en public/:
    index.html                          portada con el último lote publicado
    evidently_<mes>_vs_septiembre.html  informe de Evidently
    historial/                          informes archivados de lotes anteriores
"""
from __future__ import annotations

import argparse
import html
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from evidently.metric_preset import DataDriftPreset
from evidently.report import Report

RAIZ = Path(__file__).resolve().parents[1]
AUTOR = "Valeria Figueroa"
FUENTE = "Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository."
FUENTE_URL = "https://archive.ics.uci.edu/dataset/352/online+retail"
COLUMNAS_MONITOREO = ["Quantity", "UnitPrice"]
MESES = {"referencia": "septiembre", "control": "octubre", "nuevo": "noviembre"}
BOLIVIA = timezone(timedelta(hours=-4))

BINS_Q = ([0, 1, 2, 3, 4, 6, 12, 24, 48, 100, float("inf")],
          ["1", "2", "3", "4", "5-6", "7-12", "13-24", "25-48", "49-100", ">100"])
BINS_P = ([0, 0.5, 1, 2, 3, 5, 10, 20, float("inf")],
          ["<0,5", "0,5-1", "1-2", "2-3", "3-5", "5-10", "10-20", ">20"])


def num(x, dec=2):
    """Formato con coma decimal."""
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def leer(ruta):
    df = pd.read_csv(ruta)
    df["Quantity"] = df["Quantity"].astype(int)
    df["UnitPrice"] = df["UnitPrice"].astype(float)
    return df


def correr_evidently(ref, act, destino: Path):
    """Misma configuración en todas las ejecuciones: DataDriftPreset sobre Quantity y UnitPrice."""
    cols = COLUMNAS_MONITOREO
    reporte = Report(metrics=[DataDriftPreset(columns=cols)])
    reporte.run(reference_data=ref[cols], current_data=act[cols])
    reporte.save_html(str(destino))
    resultado = reporte.as_dict()
    por_columna = {}
    dataset = None
    for m in resultado["metrics"]:
        r = m["result"]
        if "drift_by_columns" in r:
            for c in cols:
                d = r["drift_by_columns"][c]
                por_columna[c] = {
                    "drift": bool(d["drift_detected"]),
                    "score": float(d["drift_score"]),
                    "test": d["stattest_name"],
                    "umbral": float(d["stattest_threshold"]),
                }
        if "number_of_drifted_columns" in r and dataset is None:
            dataset = {"drift": bool(r["dataset_drift"]), "n": int(r["number_of_drifted_columns"])}
    return por_columna, dataset


def distribucion(serie, bins, etiquetas):
    cortes = pd.cut(serie, bins=bins, labels=etiquetas, right=True, include_lowest=False)
    return (cortes.value_counts(normalize=True).reindex(etiquetas).fillna(0) * 100).tolist()


def svg_barras(etiquetas, ref_pct, act_pct, titulo, mes_act):
    ancho, alto = 560, 250
    mi, md, ms, mb = 40, 10, 12, 52
    area_w, area_h = ancho - mi - md, alto - ms - mb
    maximo = max(max(ref_pct), max(act_pct), 1) * 1.1
    n = len(etiquetas)
    grupo = area_w / n
    b = grupo * 0.36
    partes = [f'<svg viewBox="0 0 {ancho} {alto}" role="img" aria-label="{html.escape(titulo)}" class="chart">']
    for t in range(0, 5):
        y = ms + area_h - area_h * t / 4
        v = maximo * t / 4
        partes.append(f'<line x1="{mi}" x2="{ancho - md}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        partes.append(f'<text x="{mi - 6}" y="{y + 4:.1f}" text-anchor="end" class="tick">{v:.0f}%</text>')
    for i, et in enumerate(etiquetas):
        x0 = mi + i * grupo + grupo * 0.12
        for k, (val, clase) in enumerate(((ref_pct[i], "b-ref"), (act_pct[i], "b-act"))):
            h = area_h * val / maximo
            x = x0 + k * (b + 2)
            partes.append(f'<rect x="{x:.1f}" y="{ms + area_h - h:.1f}" width="{b:.1f}" height="{h:.1f}" rx="2" class="{clase}"><title>{et}: {val:.1f}% ({"septiembre" if k == 0 else mes_act})</title></rect>')
        partes.append(f'<text x="{x0 + b:.1f}" y="{alto - mb + 16}" text-anchor="middle" class="tick">{et}</text>')
    partes.append("</svg>")
    return "".join(partes)


def resumen(serie):
    return {"mediana": serie.median(), "media": serie.mean(), "p25": serie.quantile(.25),
            "p75": serie.quantile(.75), "p95": serie.quantile(.95), "max": serie.max()}


def fila_tabla(nombre, r, a, dec, unidad=""):
    celdas = "".join(
        f"<tr><th scope='row'>{etq}</th><td>{num(r[k], dec)}{unidad}</td><td>{num(a[k], dec)}{unidad}</td></tr>"
        for etq, k in (("Mediana", "mediana"), ("Media", "media"), ("Percentil 25", "p25"),
                       ("Percentil 75", "p75"), ("Percentil 95", "p95"), ("Máximo", "max")))
    return celdas


def chip(drift):
    return ('<span class="chip warn">Drift detectado</span>' if drift
            else '<span class="chip ok">Sin drift</span>')


def construir_index(ctx):
    mes = ctx["mes"].capitalize()
    mes_min = ctx["mes"]
    commit = ctx["commit"]
    commit_corto = commit[:7]
    if ctx["repo"] and commit != "local":
        commit_html = f'<a href="https://github.com/{ctx["repo"]}/commit/{commit}">{commit_corto}</a>'
    else:
        commit_html = f"<code>{commit_corto}</code>"
    d = ctx["drift"]
    ds = ctx["dataset"]
    drift_txt = "Evidently señaló un cambio de distribución." if ds["drift"] else "Evidently no señaló cambio de distribución en el conjunto."
    hist = ""
    if ctx["historial"]:
        items = "".join(f'<li><a href="historial/{html.escape(n)}">{html.escape(n.replace("_", " ").replace(".html", "").capitalize())}</a></li>'
                        for n in ctx["historial"])
        hist = f'<section class="card"><h2>Historial de comparaciones</h2><ul class="hist">{items}</ul><p class="muted">Informes archivados de lotes publicados anteriormente.</p></section>'

    def tarjeta_col(col, titulo, dec, unidad):
        info = d[col]
        return (f'<div class="drift-row"><div><strong>{titulo}</strong><span class="muted"> · {html.escape(info["test"])}, '
                f'puntuación {num(info["score"], 4)} (umbral {num(info["umbral"], 2)})</span></div>{chip(info["drift"])}</div>')

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitoreo de ventas · Tienda de regalos en línea</title>
<meta name="description" content="Último lote de ventas validado y su comparación con septiembre de 2011 usando Evidently.">
<style>
:root{{--bg:#0b1020;--bg2:#121a33;--card:#ffffff0d;--line:#ffffff1f;--tx:#eef1fb;--mut:#9aa6c7;--ac:#7c8cff;--ac2:#37d6c4;--warn:#ffb454;--ok:#3ddc97;--ref:#5b6b9a;--act:#7c8cff}}
@media (prefers-color-scheme:light){{:root{{--bg:#f4f6fc;--bg2:#e6ebfa;--card:#ffffff;--line:#d9e0f3;--tx:#141a33;--mut:#5a6584;--ac:#4a5cf0;--ac2:#0ea58f;--warn:#b86a00;--ok:#16895a;--ref:#aab4d4;--act:#4a5cf0}}}}
*{{box-sizing:border-box}}
body{{margin:0;font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;color:var(--tx);background:radial-gradient(1100px 600px at 80% -10%,var(--bg2),transparent),var(--bg);line-height:1.55}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 20px 56px}}
header.hero{{padding:56px 0 28px}}
.eyebrow{{display:inline-flex;gap:8px;align-items:center;font-size:.8rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ac2);font-weight:600}}
.eyebrow i{{width:8px;height:8px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px #3ddc9730}}
h1{{font-size:clamp(1.9rem,4.5vw,3rem);line-height:1.1;margin:.4em 0 .3em;letter-spacing:-.02em}}
h1 span{{background:linear-gradient(90deg,var(--ac),var(--ac2));-webkit-background-clip:text;background-clip:text;color:transparent}}
.lead{{color:var(--mut);max-width:720px;font-size:1.05rem}}
h2{{font-size:1.2rem;margin:0 0 14px}}
.latest{{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:34px 0 14px}}
.latest h2{{margin:0;font-size:1.05rem;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}}
.badge{{font-size:.8rem;padding:4px 10px;border-radius:999px;background:linear-gradient(90deg,var(--ac),var(--ac2));color:#fff;font-weight:600}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}
.kpi,.card{{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;backdrop-filter:blur(6px)}}
.kpi .lab{{font-size:.78rem;text-transform:uppercase;letter-spacing:.07em;color:var(--mut)}}
.kpi .val{{font-size:2.1rem;font-weight:700;letter-spacing:-.02em;margin-top:6px}}
.kpi .sub{{font-size:.85rem;color:var(--mut)}}
.cta{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:22px 0 6px}}
.btn{{display:inline-flex;align-items:center;gap:8px;padding:13px 20px;border-radius:12px;background:linear-gradient(90deg,var(--ac),var(--ac2));color:#fff;text-decoration:none;font-weight:600;box-shadow:0 8px 24px #4a5cf040;transition:transform .15s}}
.btn:hover{{transform:translateY(-2px)}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px;margin-top:18px}}
@media (max-width:520px){{.grid2{{grid-template-columns:1fr}}}}
.chart{{width:100%;height:auto;display:block}}
.chart .grid{{stroke:var(--line);stroke-width:1}}
.chart .tick{{fill:var(--mut);font-size:11px}}
.b-ref{{fill:var(--ref)}}.b-act{{fill:var(--act)}}
.legend{{display:flex;gap:16px;font-size:.85rem;color:var(--mut);margin:6px 0 0}}
.legend span::before{{content:"";display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.legend .l1::before{{background:var(--ref)}}.legend .l2::before{{background:var(--act)}}
table{{width:100%;border-collapse:collapse;font-size:.92rem}}
th,td{{padding:8px 6px;text-align:right;border-bottom:1px solid var(--line)}}
th:first-child,td:first-child{{text-align:left}}
thead th{{color:var(--mut);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}}
tbody th{{font-weight:500}}
.chip{{padding:4px 10px;border-radius:999px;font-size:.78rem;font-weight:700;white-space:nowrap}}
.chip.ok{{background:#3ddc9722;color:var(--ok)}}.chip.warn{{background:#ffb45026;color:var(--warn)}}
.drift-row{{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}}
.muted{{color:var(--mut);font-size:.88rem}}
.note{{border-left:3px solid var(--ac);padding:10px 14px;background:var(--card);border-radius:0 12px 12px 0;margin-top:14px}}
.pipeline{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:6px 0}}
.step{{padding:8px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);font-size:.9rem}}
.arrow{{color:var(--mut)}}
ul.hist{{margin:0;padding-left:18px}}
a{{color:var(--ac)}}
footer{{margin-top:34px;padding-top:20px;border-top:1px solid var(--line);color:var(--mut);font-size:.88rem;display:grid;gap:4px}}
code{{background:var(--card);padding:2px 6px;border-radius:6px;border:1px solid var(--line)}}
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <span class="eyebrow"><i></i> Publicado y validado con CI/CD</span>
  <h1>Monitoreo de ventas de una <span>tienda de regalos en línea</span></h1>
  <p class="lead">Cada lote pasa por pruebas y validación antes de publicarse. Después, Evidently compara las unidades por fila y el precio unitario con septiembre de 2011, el mes de referencia, para que el equipo de ventas revise los productos antes de decidir sobre el inventario.</p>
</header>

<div class="latest"><h2>Último lote publicado</h2><span class="badge">{mes} 2011</span></div>
<section class="kpis">
  <div class="kpi"><div class="lab">Mes actual</div><div class="val">{mes}</div><div class="sub">Lote «{html.escape(ctx['lote'])}» · 2011</div></div>
  <div class="kpi"><div class="lab">Filas analizadas</div><div class="val">{num(ctx['filas'], 0)}</div><div class="sub">Referencia: {num(ctx['filas_ref'], 0)} filas (septiembre)</div></div>
  <div class="kpi"><div class="lab">Mediana de unidades por fila</div><div class="val">{num(ctx['q_act']['mediana'], 0)}</div><div class="sub">Septiembre: {num(ctx['q_ref']['mediana'], 0)}</div></div>
  <div class="kpi"><div class="lab">Mediana del precio unitario</div><div class="val">£ {num(ctx['p_act']['mediana'], 2)}</div><div class="sub">Septiembre: £ {num(ctx['p_ref']['mediana'], 2)}</div></div>
</section>

<div class="cta">
  <a class="btn" href="{html.escape(ctx['informe'])}">Comparar {mes_min} con septiembre →</a>
  <span class="muted">Informe interactivo de Evidently (Quantity y UnitPrice)</span>
</div>

<section class="grid2">
  <div class="card">
    <h2>Señal de monitoreo</h2>
    {tarjeta_col('Quantity', 'Quantity · unidades por fila', 0, '')}
    {tarjeta_col('UnitPrice', 'UnitPrice · precio unitario (£)', 2, '')}
    <div class="note"><strong>{drift_txt}</strong> Un lote válido se publica aunque haya drift: la señal pide revisar productos, no bloquea el despliegue.</div>
  </div>
  <div class="card">
    <h2>Del push a GitHub Pages</h2>
    <div class="pipeline"><span class="step">Push a main</span><span class="arrow">→</span><span class="step">CI: pruebas</span><span class="arrow">→</span><span class="step">CI: validar CSV</span><span class="arrow">→</span><span class="step">Evidently + HTML</span><span class="arrow">→</span><span class="step">CD: Pages</span></div>
    <p class="muted">Si la validación falla, el despliegue se omite y el sitio conserva el último commit publicado correctamente.</p>
  </div>
</section>

<section class="grid2">
  <div class="card">
    <h2>Unidades por fila (Quantity)</h2>
    {ctx['svg_q']}
    <div class="legend"><span class="l1">Septiembre (referencia)</span><span class="l2">{mes}</span></div>
    <p class="muted">Porcentaje de filas en cada rango de unidades.</p>
  </div>
  <div class="card">
    <h2>Precio unitario (UnitPrice, £)</h2>
    {ctx['svg_p']}
    <div class="legend"><span class="l1">Septiembre (referencia)</span><span class="l2">{mes}</span></div>
    <p class="muted">Porcentaje de filas en cada rango de precio.</p>
  </div>
</section>

<section class="grid2">
  <div class="card"><h2>Resumen de Quantity</h2>
    <table><thead><tr><th></th><th>Septiembre</th><th>{mes}</th></tr></thead><tbody>{ctx['tabla_q']}</tbody></table></div>
  <div class="card"><h2>Resumen de UnitPrice (£)</h2>
    <table><thead><tr><th></th><th>Septiembre</th><th>{mes}</th></tr></thead><tbody>{ctx['tabla_p']}</tbody></table></div>
</section>
<br>
{hist}

<footer>
  <div><strong>Autor:</strong> {AUTOR}</div>
  <div><strong>Fuente:</strong> {html.escape(FUENTE)} <a href="{FUENTE_URL}">{FUENTE_URL}</a></div>
  <div><strong>Generado:</strong> {ctx['generado']} (hora de Bolivia) · <strong>Commit:</strong> {commit_html}</div>
</footer>
</div>
</body>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--referencia", default=str(RAIZ / "datos/referencia.csv"))
    ap.add_argument("--actual", default=str(RAIZ / "datos/actual.csv"))
    ap.add_argument("--salida", default=str(RAIZ / "public"))
    ap.add_argument("--archivar", action="store_true", help="copia el informe a evidencias/")
    args = ap.parse_args(argv)

    ref, act = leer(args.referencia), leer(args.actual)
    lote = act["lote"].iloc[0]
    mes = MESES[lote]
    salida = Path(args.salida)
    if salida.exists():
        shutil.rmtree(salida)
    salida.mkdir(parents=True)

    nombre_informe = f"evidently_{mes}_vs_septiembre.html"
    drift, dataset = correr_evidently(ref, act, salida / nombre_informe)

    if args.archivar:
        (RAIZ / "evidencias").mkdir(exist_ok=True)
        shutil.copy(salida / nombre_informe, RAIZ / "evidencias" / nombre_informe)

    historial = []
    carpeta_ev = RAIZ / "evidencias"
    if carpeta_ev.exists():
        (salida / "historial").mkdir()
        for f in sorted(carpeta_ev.glob("evidently_*_vs_septiembre.html")):
            if f.name != nombre_informe:
                shutil.copy(f, salida / "historial" / f.name)
                historial.append(f.name)

    q_r, q_a = resumen(ref["Quantity"]), resumen(act["Quantity"])
    p_r, p_a = resumen(ref["UnitPrice"]), resumen(act["UnitPrice"])
    etq_q, etq_p = BINS_Q[1], BINS_P[1]
    ctx = {
        "mes": mes, "lote": lote, "filas": len(act), "filas_ref": len(ref),
        "q_ref": q_r, "q_act": q_a, "p_ref": p_r, "p_act": p_a,
        "drift": drift, "dataset": dataset, "informe": nombre_informe, "historial": historial,
        "svg_q": svg_barras(etq_q, distribucion(ref["Quantity"], *BINS_Q), distribucion(act["Quantity"], *BINS_Q), "Distribución de Quantity", mes),
        "svg_p": svg_barras(etq_p, distribucion(ref["UnitPrice"], *BINS_P), distribucion(act["UnitPrice"], *BINS_P), "Distribución de UnitPrice", mes),
        "tabla_q": fila_tabla("Quantity", q_r, q_a, 0 if False else 1),
        "tabla_p": fila_tabla("UnitPrice", p_r, p_a, 2),
        "generado": datetime.now(BOLIVIA).strftime("%d/%m/%Y %H:%M:%S"),
        "commit": os.getenv("GITHUB_SHA", "local"),
        "repo": os.getenv("GITHUB_REPOSITORY", ""),
    }
    (salida / "index.html").write_text(construir_index(ctx), encoding="utf-8")
    (salida / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Informe generado en {salida} ({mes}). Drift por columna: "
          + ", ".join(f"{c}={'sí' if v['drift'] else 'no'}" for c, v in drift.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
