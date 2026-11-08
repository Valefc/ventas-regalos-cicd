# Monitoreo de ventas de una tienda de regalos en línea (CI/CD + Evidently)

Sistema que **valida** lotes de ventas, **compara** sus distribuciones con Evidently y **publica** automáticamente
el informe en GitHub Pages cuando todo es válido.

- Sitio publicado: https://TU_USUARIO.github.io/ventas-regalos-cicd/
- Autora: Valeria Figueroa Camacho
- Fuente de datos: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository. https://archive.ics.uci.edu/dataset/352/online+retail

## Estructura

```
datos/            original/ (CSV de trabajo intacto), referencia.csv (septiembre, fijo), control.csv (octubre), nuevo.csv (noviembre), actual.csv (lote a publicar)
scripts/          validar.py, generar_informe.py, preparar_lotes.py
tests/            pruebas automatizadas (pytest)
evidencias/       informes de Evidently de lotes ya publicados (p. ej. octubre)
.github/workflows/ci-cd.yml
requirements.txt  .gitignore  README.md
```

## Uso local (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m pytest -v                                              # pruebas
python scripts/validar.py datos/referencia.csv datos/actual.csv  # validación
python scripts/generar_informe.py                                # genera public/index.html y el informe de Evidently
```

Preparar los lotes desde el CSV de trabajo (conserva una copia intacta aparte):

```powershell
python scripts/preparar_lotes.py   # lee datos\original\ventas_regalos_2011.csv
```

## Cómo cambia `actual.csv`

- Primera publicación: `actual.csv` es copia de `control.csv` (octubre).
- Actualización: `actual.csv` se reemplaza por una copia de `nuevo.csv` (noviembre).
- `referencia.csv` no se modifica nunca.

## Flujo CI/CD

1. Un `push` a `main` activa el workflow.
2. **CI**: obtiene el commit, instala dependencias, ejecuta pruebas, valida los dos CSV y, solo si todo pasa, genera los HTML y sube el artefacto de Pages.
3. **CD**: `needs: ci`; despliega el artefacto de la misma ejecución. Si CI falla, CD se omite y Pages conserva el último commit válido.

## Evidently

Compara `Quantity` y `UnitPrice` con `DataDriftPreset` (misma configuración en todas las ejecuciones) frente a septiembre.
Un lote válido se publica aunque se detecte drift: el drift es una señal de revisión, no un error de datos.

## Seguridad

El repositorio no contiene credenciales. `.gitignore` excluye entornos virtuales, archivos temporales, claves y la carpeta `public/`.
