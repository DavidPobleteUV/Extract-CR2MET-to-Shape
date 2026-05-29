# `scr/` — Scripts auxiliares para el flujo CR2Met → WEAP

Scripts en Python que automatizan la incorporación de los productos CR2Met
(generados con el Rmd del repositorio) en un modelo WEAP a través de la
[WEAP API](https://www.weap21.org/webhelp/weapapplication.htm).

---

## `weap_create_band_branches.py`

Crea las **bandas de elevación como sub-ramas** de cada catchment existente en
un modelo WEAP, y le conecta a cada banda su clima y su área.

### Qué hace

Para cada banda detectada en los CSV de CR2Met:

1. Crea una sub-rama bajo el catchment padre, nombrada `b<n>` (p.ej. `b1`, `b2`).
2. Asigna la expresión de variables del método **Soil Moisture (Rainfall Runoff)**:

   | Variable        | Expresión                                                       |
   | --------------- | --------------------------------------------------------------- |
   | `Precipitation` | `ReadFromFile("Datos\Clima_CR2Met_v2.5\<area>_pp_diaria_*.csv", "<label>")`  |
   | `Temperature`   | `ReadFromFile("Datos\Clima_CR2Met_v2.5\<area>_tav_diaria_*.csv", "<label>")` |
   | `Area`          | valor numérico en hectáreas, desde el `.dbf` del shapefile      |

3. Guarda el modelo (`SaveArea`).

### Cómo mapea labels → ramas

El label de columna en el CSV (p.ej. `Aconcagua en Blanco_2`) es la llave común
entre las tres fuentes:

- columna de los CSV (`$Columns = fecha, Aconcagua en Blanco_2, ...`)
- campo **`Subcuenca`** del `.dbf` (con `area_ha` asociada)
- ruta de la rama en WEAP: `\Demand Sites and Catchments\Aconcagua en Blanco\b2`

El script separa por el último `_`: lo de antes es el catchment padre (debe
existir ya en el modelo), el sufijo es el número de banda.

### Detalles importantes

- **`ReadFromFile` con rutas RELATIVAS** al *area directory* (`Datos\...`).
  WEAP resuelve estas rutas respecto a la carpeta del area, por lo que el
  modelo es portable: copiar el `.areas` a otra PC sigue funcionando.
- **Timestep weekly desde CSV diario**: WEAP agrega solo, por fecha — precipitación
  se suma, temperatura promedia. No hay que pre-procesar nada.
- **Unidad de área**: la unidad del variable `Area` **NO se puede setear via API**
  (intentar `WEAP.BranchVariable(...).Unit = "Hectare"` falla). El script asume
  que el modelo ya tiene la unidad en Hectare y escribe el valor en hectáreas
  directo. Si tu modelo está en km², setea `AREA_SCALE = 0.01` para convertir.
- **Idempotente**: si la rama `b<n>` ya existe, no la duplica; siempre
  re-escribe las expresiones (útil para re-ejecutar tras editar los CSV).
- **Otras variables del Soil Moisture** (Kc, Soil Water Capacity, etc.)
  *no* se tocan — quedan con sus valores por defecto / heredados.

### Requisitos

| Componente | Cómo conseguirlo                              |
| ---------- | --------------------------------------------- |
| WEAP       | Abierto, con el area objetivo como ActiveArea |
| Python     | 3.x                                           |
| `pywin32`  | `pip install pywin32`                         |

Los CSV de clima y el `.dbf` con `area_ha` deben existir dentro del area
directory del modelo:

```
<WEAP.AreasDirectory>\<ActiveArea>\
├── Datos\Clima_CR2Met_v2.5\
│   ├── <ActiveArea>_pp_diaria_cr2met2.5_1975_2026.csv
│   └── <ActiveArea>_tav_diaria_cr2met2.5_1975_2026.csv
└── SIG\
    └── <ActiveArea>_v2.dbf            (campos: Subcuenca, ID, area_ha)
```

Los CSV se generan con el `.Rmd` raíz del repo; el `.dbf` debe ser la
versión "mejorada" con bandas (una fila por `<catchment>_<n>`).

### Uso

1. Abrir WEAP en el area objetivo.
2. Verificar las **3 opciones de configuración** al inicio del script:
   - `CATCHMENTS_ROOT` (por defecto `\Demand Sites and Catchments`)
   - `AREA_SCALE`     (1.0 si la unidad WEAP es hectárea; 0.01 si es km²)
   - `DRY_RUN`        (**dejar en `True` la primera vez**)
3. Correr:
   ```powershell
   python "C:\Users\David\Documents\GitHub_DPL\CR2Met_extraction\scr\weap_create_band_branches.py"
   ```
4. Revisar el log impreso:
   - `[create]` / `[exists]` para cada banda
   - expresiones que se escribirían en cada variable
   - lista de catchments `[MISSING]` (si el nombre del catchment en el modelo
     no coincide con el prefijo del label hay que arreglarlo antes)
5. Si todo se ve bien, cambiar `DRY_RUN = False` y volver a correr.
   El modelo queda guardado al final.

### Salida típica (DRY_RUN)

```
Connected to WEAP. Active area: Aconcagua_EmbCatemu
Area directory:  C:\...\WEAP Areas\Aconcagua_EmbCatemu

[create]  \Demand Sites and Catchments\Aconcagua en Blanco\b2
           Precipitation = ReadFromFile("Datos\Clima_CR2Met_v2.5\...pp_diaria...csv", "Aconcagua en Blanco_2")
           Temperature   = ReadFromFile("Datos\Clima_CR2Met_v2.5\...tav_diaria...csv", "Aconcagua en Blanco_2")
           Area          = 2424.79
...
----- summary -----
branches to create : 28
branches existing  : 0
catchments missing : 0
DRY_RUN = True  (no changes made)
```

### Adaptar a otro modelo / cuenca

El script ya es independiente del nombre del area: usa
`WEAP.ActiveArea.Name` para armar todas las rutas. Para procesar otra cuenca
basta con:

1. Abrirla en WEAP como ActiveArea.
2. Tener los CSV y el `.dbf` con la convención de nombres y carpetas de arriba,
   dentro del area directory.
3. Correr el script.

Si tu modelo usa otra raíz de árbol (no `\Demand Sites and Catchments`),
ajusta `CATCHMENTS_ROOT`.

---

## Troubleshooting

| Síntoma                                       | Causa probable                                                            |
| --------------------------------------------- | ------------------------------------------------------------------------- |
| `[MISSING] catchment not in model: X`         | El nombre del catchment en WEAP no coincide con el prefijo del label CSV. |
| Áreas se ven mil veces más grandes/chicas     | Unidad del Area variable distinta a Hectare → ajusta `AREA_SCALE`.        |
| `pywin32` no encuentra `WEAP.WEAPApplication` | WEAP no está abierto, o no está instalado/registrado COM.                 |
| `ReadFromFile` falla al recalcular            | La ruta relativa no resuelve → verifica que el CSV esté en `Datos\Clima_CR2Met_v2.5\` dentro del area directory. |
| Falta `area_ha` para algún label              | El `.dbf` no tiene una fila por banda. El script lo reporta como `WARNING` y deja Area vacía. |
