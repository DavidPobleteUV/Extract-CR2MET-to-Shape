# Extracción de Series Climáticas CR2MET v2.5 por Subcuenca

**Script:** `CR2Met_bestday_extraccion_1959_2025_cr2met2_5_v4_web_DPL.Rmd`
**Autores:** Simón Caneo & David Poblete — Escuela de Ingeniería Civil, Universidad de Valparaíso
**Fuente de datos:** [CR2MET v2.5 — Centro de Ciencia del Clima y la Resiliencia (CR)²](https://www.cr2.cl/datos-productos-grillados/)
**Salida compatible con:** WEAP (Water Evaluation And Planning System)

---

## ¿Qué hace este script?

Descarga archivos NetCDF del repositorio público CR2MET v2.5 (resolución espacial 0.05°, ~5 km, paso de tiempo diario) y extrae series de tiempo de variables climáticas para cada subcuenca definida en un shapefile. Las series se exportan en formato compatible con WEAP y como CSV estándar.

```
FTP CR2MET (NetCDF mensual)
        ↓
  Descarga con caché local (nc_cache/)
        ↓
  Extracción por polígono — media areal PONDERADA POR ÁREA
        ↓
  Tabla larga → agregación diaria/mensual
        ↓
  CSV formato WEAP  +  CSV estándar
```

---

## Variables procesadas

| Variable | Nombre CR2MET | Directorio remoto | Agregación diaria | Agregación mensual |
|----------|--------------|-------------------|-------------------|--------------------|
| Precipitación | `pr` | `pr/v2.5_best_day/` | Suma | Suma |
| Temperatura mínima | `tmin` | `txn/v2.5_best_day/` | Media | Media |
| Temperatura máxima | `tmax` | `txn/v2.5_best_day/` | Media | Media |
| Temperatura media | *(tmin + tmax) / 2* | — | Media | Media |
| Evapotranspiración de referencia | `et0` | `et0/v2.5_best_day/` | Suma | Suma |

> `tmin` y `tmax` vienen en el mismo archivo NetCDF dentro del directorio `txn/`.
> La temperatura media se calcula como el promedio aritmético de tmin y tmax (no es la T media diaria "real" del modelo).

---

## Detalles metodológicos importantes

### Media areal ponderada por fracción de área (`exact = TRUE`)

A partir de esta versión, la extracción usa:

```r
terra::extract(r, v, fun = mean, na.rm = TRUE, exact = TRUE, ID = FALSE)
```

`exact = TRUE` calcula la **fracción exacta** de cada celda raster cubierta por el polígono y pondera la media por esa fracción. Esto es importante porque:

- Sin pesos, `terra::extract` aplica la regla **"centroid-in"**: cada celda cuyo centroide cae dentro del polígono cuenta con peso 1, sin importar si el polígono cubre 5% o 95% de ella; las celdas cuyo centroide queda fuera se descartan aunque parte importante de la cuenca caiga sobre ellas.
- En cuencas grandes y de poco gradiente orográfico el sesgo es pequeño.
- En **cuencas chicas** (pocas celdas CR2MET) o con **gradiente orográfico fuerte** (cordillera), el sesgo es apreciable y no aleatorio: si el polígono está sesgado hacia altura, se incluyen/excluyen celdas frías o lluviosas que cambian la media. En precipitación mensual acumulada el sesgo se amplifica.

`exact = TRUE` corrige ambos problemas.

### Fechas a partir del NetCDF

Las fechas diarias se leen directamente desde `terra::time(r)` cuando el NetCDF expone la dimensión temporal correctamente. Si no, se usa fallback parseando el nombre del archivo (`*_YYYY_MM_005deg.nc`, días consecutivos desde el día 1).

### Caché local de descargas

Los NetCDF descargados se guardan en `nc_cache/<variable>/` y se reutilizan en re-ejecuciones. Para forzar re-descarga, borrar la carpeta `nc_cache/` o el archivo correspondiente.

---

## Requisitos

### Paquetes R

```r
install.packages(c("tidyverse", "lubridate", "janitor",
                   "sf", "terra", "rvest", "stringr", "xml2"))
```

`terra` debe ser ≥ 1.7 para soporte completo de `exact = TRUE`.

### Estructura de archivos

```
/
├── Cuenca/
│   └── <cuenca_nombre>/
│       └── <archivo_shp>          ← Shapefile de subcuencas
├── nc_cache/                      ← Se crea automáticamente (NetCDF descargados)
├── Results/                       ← Se crea automáticamente
└── CR2Met_bestday_extraccion_1959_2025_cr2met2_5_v4_web_DPL.Rmd
```

### Conexión a internet

El script descarga los NetCDF directamente desde `ftp.cr2.cl`. Se requiere acceso sin proxy bloqueante a ese dominio.

---

## Configuración

Todos los parámetros ajustables están en el **Chunk 1**:

```r
cuenca_nombre    <- "Aculeo"                          # Nombre de la cuenca
archivo_shp      <- "Subcuencas_bandas_Aculeo.shp"
cuenca_shp       <- file.path(getwd(), "Cuenca", cuenca_nombre, archivo_shp)
nombre_subcuenca <- "layer"                           # Columna con nombre de cada subcuenca

years_to_keep    <- 1970:2025                         # Rango de años
months_to_keep   <- NULL                              # NULL = todos; ej. c(12,1,2) solo DJF
```

Para cambiar de cuenca basta con modificar esos cinco parámetros.

---

## Estructura del shapefile

- Una columna con el nombre de cada subcuenca (definida en `nombre_subcuenca`).
- CRS definido. Si viene sin CRS, el script intenta inferirlo (`EPSG:4326` si las coords parecen lon/lat, `EPSG:32719`/UTM 19S como fallback proyectado — ajustar manualmente si la cuenca está en otra zona).
- El script aplica reparación automática de geometrías (`st_make_valid`, dissolve por subcuenca, cast a MULTIPOLYGON) y guarda una copia con sufijo `_mejorado.shp` en la misma carpeta.

---

## Archivos de salida

Los resultados se guardan en `Results/<cuenca_nombre>/`:

```
<cuenca>_pp_diaria_cr2met2.5_<año_ini>_<año_fin>.csv      ← formato WEAP
<cuenca>_pp_mensual_cr2met2.5_<año_ini>_<año_fin>.csv     ← CSV estándar
<cuenca>_tn_diaria_...csv         /  _tn_mensual_...csv
<cuenca>_tx_diaria_...csv         /  _tx_mensual_...csv
<cuenca>_tav_diaria_...csv        /  _tav_mensual_...csv
<cuenca>_et0_diaria_...csv        /  _et0_mensual_...csv
```

### Formato WEAP (archivos diarios)

```
#,1,2,...,N
$Columns = Date,SubC_1,SubC_2,...,SubC_N
01/01/1970,3.2,1.8,...
01/02/1970,0.0,0.0,...
```

Los archivos mensuales se exportan como CSV estándar.

---

## Estructura del script (chunks)

| Chunk | Contenido |
|-------|-----------|
| 1 | Librerías, directorio de trabajo y parámetros de la cuenca |
| 2 | URLs del FTP CR2MET y funciones para listar/filtrar archivos remotos |
| 3 | Lectura y reparación robusta del shapefile; dissolve por subcuenca; transformación a WGS84; export `_mejorado.shp` |
| 4 | `fn_extract_from_nc()` — extrae media areal **ponderada por fracción de área** (`exact = TRUE`) y construye fechas desde `terra::time()` |
| 5 | Loops de descarga (con caché local) y extracción para PR, temperatura y ET0 |
| 6 | Agregaciones diarias y mensuales (formato largo → ancho) |
| 7–8 | Función de exportación custom (formato WEAP) y escritura de archivos de salida |

---

## Notas y limitaciones conocidas

- La extracción se hace polígono por polígono dentro de un loop. Para cuencas con muchas subcuencas (>50) podría vectorizarse pasando todos los polígonos a `terra::extract` en una sola llamada.
- `setwd(dirname(rstudioapi::getActiveDocumentContext()$path))` requiere ejecución en RStudio. Para ejecuciones desde CLI / `Rscript`, fijar `setwd()` manualmente.
- El script ejecuta `rm(list = ls())` al inicio: limpia el workspace global.
- El cálculo de área por subcuenca usa la zona UTM inferida desde el centroide del shapefile completo (válido para cuencas que no crucen zonas UTM).

---

## Licencia

GNU General Public License v3.0

Copyright (c) 2026 Simón Caneo & David Poblete
Escuela de Ingeniería Civil, Universidad de Valparaíso

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la Licencia Pública General de GNU publicada por la Free Software Foundation, ya sea la versión 3 de la Licencia, o cualquier versión posterior.

Este programa se distribuye con la esperanza de que sea útil, pero **sin ninguna garantía**; sin siquiera la garantía implícita de comerciabilidad o idoneidad para un propósito particular.

**Condición clave:** cualquier trabajo derivado que se distribuya públicamente debe hacerse bajo esta misma licencia GPL v3.

Texto completo: https://www.gnu.org/licenses/gpl-3.0.html
