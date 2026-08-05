import os
import sys
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from tqdm import tqdm

# --- CONFIGURACIÓN ---
INPUT_FILE = "muestras_fuerza_normal.csv"
OUTPUT_FILE = "muestras_cuad_disco_0.4.csv"

GEOMETRIA = "Cuad-Disco"
AREA_TARGET = 0.4
EPS = 1e-4             # Tolerancia para números flotantes
CHUNK_SIZE = 1_000_000 # Filas por bloque (ajustable)

# --- FUNCIÓN DE FILTRADO PARALELO ---
def filtrar_bloque(chunk, geometria, area_target, eps):
    # 1. Filtro por geometría
    mask_geom = chunk["geometry_label"].str.strip() == geometria
    
    # 2. Filtro por área objetivo con tolerancia flotante
    area_num = pd.to_numeric(chunk["area_ratio_nominal"], errors="coerce")
    mask_area = (area_num - area_target).abs() < eps
    
    return chunk[mask_geom & mask_area]


# --- CLASE PARA RASTREAR PROGRESO EN BYTES ---
class TqdmFileReader:
    def __init__(self, filename, pbar):
        self.f = open(filename, "r", encoding="utf-8")
        self.pbar = pbar

    def read(self, size=-1):
        data = self.f.read(size)
        self.pbar.update(len(data.encode("utf-8")))
        return data

    def readline(self, size=-1):
        data = self.f.readline(size)
        self.pbar.update(len(data.encode("utf-8")))
        return data

    def __iter__(self):
        return self

    def __next__(self):
        line = self.f.readline()
        if not line:
            raise StopIteration
        self.pbar.update(len(line.encode("utf-8")))
        return line

    def close(self):
        self.f.close()


# --- EJECUCIÓN PRINCIPAL ---
def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: No se encontró el archivo {INPUT_FILE}")
        sys.exit(1)

    # Eliminar archivo de salida si existe previamente
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    file_size = os.path.getsize(INPUT_FILE)
    num_workers = max(1, os.cpu_count() - 1)  # Deja 1 núcleo libre para el sistema
    max_in_flight = num_workers * 2           # Límite de bloques en memoria simultáneos

    print("=" * 65)
    print(f" FILTRADO PARALELO: {INPUT_FILE} ({file_size / (1024**3):.2f} GB)")
    print(f" Geometría: {GEOMETRIA} | Área: {AREA_TARGET}")
    print(f" Procesadores asignados: {num_workers} núcleos")
    print("=" * 65)

    first_chunk = True
    filas_guardadas = 0

    with open(INPUT_FILE, "r", encoding="utf-8") as raw_f, \
         tqdm(total=file_size, unit="B", unit_scale=True, unit_divisor=1024, desc="Procesando GB") as pbar:

        file_wrapper = TqdmFileReader(INPUT_FILE, pbar)
        chunk_iter = pd.read_csv(file_wrapper, chunksize=CHUNK_SIZE, dtype=str, low_memory=False)

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = set()

            def escribir_resultado(future):
                nonlocal first_chunk, filas_guardadas
                res = future.result()
                if not res.empty:
                    res.to_csv(OUTPUT_FILE, mode="a", header=first_chunk, index=False)
                    first_chunk = False
                    filas_guardadas += len(res)

            for chunk in chunk_iter:
                # Enviar tarea a un núcleo secundario
                fut = executor.submit(filtrar_bloque, chunk, GEOMETRIA, AREA_TARGET, EPS)
                futures.add(fut)

                # Mantener la memoria RAM bajo control
                if len(futures) >= max_in_flight:
                    done, futures = wait(futures, return_when=FIRST_COMPLETED)
                    for f in done:
                        escribir_resultado(f)

            # Procesar los bloques restantes al finalizar la lectura
            for fut in futures:
                escribir_resultado(fut)

        file_wrapper.close()

    print("\n" + "=" * 65)
    print(f"¡Proceso completado exitosamente!")
    print(f"Se guardaron {filas_guardadas:,} filas en: {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()