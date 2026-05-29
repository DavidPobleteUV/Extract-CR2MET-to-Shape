"""
Crea sub-ramas de banda de elevación bajo cada catchment existente en WEAP, y
asigna a cada banda:
  - Precipitation  -> ReadFromFile() sobre el CSV diario de pp de CR2Met
  - Temperature    -> ReadFromFile() sobre el CSV diario de tav de CR2Met
  - Area           -> valor (hectáreas) leído del shapefile (.dbf) del catchment

Modelo: Aconcagua Embalse Catemu   |   Método: Rainfall Runoff (Soil Moisture)
Timestep weekly (WEAP agrega los CSV diarios por fecha automáticamente).

Los labels de banda (p.ej. "Aconcagua en Blanco_2") son la llave común entre
las tres fuentes (columna del CSV, campo Subcuenca del DBF, sub-rama en WEAP).

Las rutas para los archivos LOCALES (que este script lee) son absolutas, construidas
desde WEAP.AreasDirectory + ActiveArea.Name.
Las rutas dentro de las expresiones ReadFromFile() son RELATIVAS al area
directory -> el modelo queda portable.

Requisitos: WEAP abierto en el area objetivo + Python con pywin32.
Uso: DRY_RUN = True para revisar; False para aplicar y guardar.
"""

import os
import struct
import win32com.client

# ---------------------------------------------------------------- config
WEAP             = win32com.client.Dispatch("WEAP.WEAPApplication")
area_name        = WEAP.ActiveArea.Name
WEAP_Directorio  = WEAP.AreasDirectory + area_name

DATA_DIR  = os.path.join(WEAP_Directorio, "Datos", "Clima_CR2Met_v2.5")
PP_FILE   = os.path.join(DATA_DIR, "Aconcagua_EmbCatemu_pp_diaria_cr2met2.5_1975_2026.csv")
TAV_FILE  = os.path.join(DATA_DIR, "Aconcagua_EmbCatemu_tav_diaria_cr2met2.5_1975_2026.csv")
AREA_DBF  = os.path.join(WEAP_Directorio, "SIG", "Aconcagua_EmbCatemu_v2.dbf")

# Versiones relativas (lo que se escribe en las expresiones del modelo)
PP_FILE_2   = os.path.join("Datos", "Clima_CR2Met_v2.5", "Aconcagua_EmbCatemu_pp_diaria_cr2met2.5_1975_2026.csv")
TAV_FILE_2  = os.path.join("Datos", "Clima_CR2Met_v2.5", "Aconcagua_EmbCatemu_tav_diaria_cr2met2.5_1975_2026.csv")

CATCHMENTS_ROOT = r"\Demand Sites and Catchments"
AREA_SCALE = 1.0     # multiplica area_ha por este factor (0.01 si la unidad WEAP es km2)
DRY_RUN = False      # True = sólo imprime; False = aplica al modelo y guarda

# ---------------------------------------------------------------- dbf reader
def read_dbf(path):
    """Minimal DBF reader -> list of dict rows (all values as stripped strings)."""
    with open(path, "rb") as f:
        data = f.read()
    nrec  = struct.unpack("<I", data[4:8])[0]
    hsize = struct.unpack("<H", data[8:10])[0]
    rsize = struct.unpack("<H", data[10:12])[0]
    fields, p = [], 32
    while data[p] != 0x0D:
        name = data[p:p + 11].split(b"\x00")[0].decode("latin1")
        flen = data[p + 16]
        fields.append((name, flen))
        p += 32
    rows = []
    for i in range(nrec):
        rec = data[hsize + i * rsize: hsize + (i + 1) * rsize]
        if not rec or rec[0:1] == b"*":   # deleted record
            continue
        off, row = 1, {}
        for name, flen in fields:
            row[name] = rec[off:off + flen].decode("latin1").strip()
            off += flen
        rows.append(row)
    return rows

# ---------------------------------------------------------------- csv header
def read_column_labels(path):
    """Return data column labels (after 'fecha') from a WEAP '$Columns = ...' header."""
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("$columns"):
                labels = [c.strip() for c in line.split("=", 1)[1].split(",")]
                return labels[1:]
    raise RuntimeError(f"No '$Columns' header found in {path}")

def split_label(label):
    catchment, _, band = label.rpartition("_")
    return (catchment, band) if catchment else (label, "")

# ---------------------------------------------------------------- main
def main():
    pp_labels  = read_column_labels(PP_FILE)
    tav_labels = read_column_labels(TAV_FILE)
    if set(pp_labels) != set(tav_labels):
        print("WARNING: pp and tav column labels differ:",
              set(pp_labels) ^ set(tav_labels))

    # area lookup keyed by the band label (Subcuenca)
    area_by_label = {r["Subcuenca"]: float(r["area_ha"]) for r in read_dbf(AREA_DBF)}
    missing_area = [l for l in pp_labels if l not in area_by_label]
    if missing_area:
        print("WARNING: no area found in DBF for:", missing_area)

    # group bands by catchment, preserving order
    catchments = {}
    for label in pp_labels:
        catch, band = split_label(label)
        catchments.setdefault(catch, []).append((band, label))

    print(f"Connected to WEAP. Active area: {WEAP.ActiveArea.Name}\n")

    created = skipped = 0
    missing_catch = []

    for catch, bands in catchments.items():
        catch_path = f"{CATCHMENTS_ROOT}\\{catch}"
        if not WEAP.BranchExists(catch_path):
            missing_catch.append(catch)
            print(f"[MISSING] catchment not in model: {catch}")
            continue

        parent = WEAP.Branch(catch_path)
        existing = {c.Name for c in parent.Children}

        for band, label in bands:
            child_name = f"b{band}" if band else label
            child_path = f"{catch_path}\\{child_name}"

            b = None
            if child_name in existing:
                print(f"[exists]  {child_path}")
                skipped += 1
                if not DRY_RUN:
                    b = WEAP.Branch(child_path)
            else:
                print(f"[create]  {child_path}")
                created += 1
                if not DRY_RUN:
                    b = parent.AddChild(child_name)
                    if b is None:
                        b = WEAP.Branch(child_path)
                    existing.add(child_name)

            pp_expr   = f'ReadFromFile("{PP_FILE_2}", "{label}")'
            tav_expr  = f'ReadFromFile("{TAV_FILE_2}", "{label}")'
            area_val  = area_by_label.get(label)
            area_val  = None if area_val is None else round(area_val, 2)
            area_expr = None if area_val is None else f"{area_val * AREA_SCALE:.2f}"

            print(f"           Precipitation = {pp_expr}")
            print(f"           Temperature   = {tav_expr}")
            print(f"           Area          = {area_expr}")

            if not DRY_RUN:
                if b is None:
                    print(f"           [WARN] branch object is None, skipping: {child_path}")
                    continue

                # --- Asignar variables via WEAP.BranchVariable con backslash (igual que utils_Q.py) ---
                bv_pp   = f"{child_path}:Precipitation"
                bv_tav  = f"{child_path}:Temperature"
                bv_area = f"{child_path}:Area"

                print(f"           [DEBUG] trying: {bv_pp}")
                WEAP.BranchVariable(bv_pp).Expression  = pp_expr
                print(f"           [OK] Precipitation assigned")
                WEAP.BranchVariable(bv_tav).Expression = tav_expr
                print(f"           [OK] Temperature assigned")
                if area_expr:
                    # WEAP.BranchVariable(bv_area).Unit = "Hectare"   # no se puede setear via API
                    WEAP.BranchVariable(bv_area).Expression = area_expr
                    print(f"           [OK] Area assigned")

    print("\n----- summary -----")
    print(f"branches to create : {created}")
    print(f"branches existing  : {skipped}")
    print(f"catchments missing : {len(missing_catch)} {missing_catch if missing_catch else ''}")
    print(f"DRY_RUN = {DRY_RUN}  ({'no changes made' if DRY_RUN else 'changes applied'})")
    if not DRY_RUN:
        WEAP.SaveArea()
        print("Area saved.")


if __name__ == "__main__":
    main()
