import sys
import os
from pathlib import Path
from typing import List, Tuple, Optional
import statistics

'''
Este codigo analiza los datos de flx.dat para encontrar el tamaño medio de avalancha, 
como función del orificio de descarga del silo.

'''


# --- CONFIGURACIÓN ---
INPUT_FILENAME = "flx.dat"  # Nombre del archivo raw dentro de cada carpeta
OUTPUT_SUMMARY_FILE = "resumen_tamano_medio_vs_outlet.csv"
DT_THRESHOLD = 0.5         # Ajustar según tu simulación (segundos)
TARGET_TYPE = 0            # ID del tipo de partícula a analizar
BASE_DIR = "."             # Directorio raíz donde buscar las carpetas outlet_*

def get_outlet_size_from_folder(folder_name: str) -> float:
    """
    Parsea el nombre del directorio (ej: 'outlet_R0p75') para obtener el valor numérico (0.75).
    """
    try:
        # Esperamos formato 'outlet_R0p75' -> split('_') -> 'R0p75'
        part = folder_name.split("_")[-1] 
        if part.startswith("R"):
            part = part[1:]  # Quitar la 'R'
        part = part.replace("p", ".")
        return float(part)
    except (IndexError, ValueError):
        raise ValueError(f"Formato de carpeta desconocido: {folder_name}")

def compute_mean_avalanche_size(
    flx_path: Path, 
    dt_threshold: float, 
    target_type: int
) -> Optional[float]:
    """
    Lee un flx.dat, detecta avalanchas y devuelve el tamaño medio de las mismas.
    Retorna None si no hay datos válidos.
    """
    exit_times: List[float] = []

    # 1. LECTURA: Extraer tiempos de salida
    try:
        with open(flx_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                try:
                    # Estructura asuimda: [0]grainDesc [1]type [2]time ...
                    p_type = int(parts[1])
                    p_time = float(parts[2])
                    
                    if p_type == target_type:
                        exit_times.append(p_time)
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        print(f"[ERROR] No se encontró: {flx_path}")
        return None

    if not exit_times:
        return None

    # 2. PROCESAMIENTO: Detectar avalanchas
    avalanche_sizes: List[int] = []
    
    current_end = exit_times[0]
    particle_count = 1
    
    # Iterar desde el segundo elemento
    for t in exit_times[1:]:
        dt = t - current_end
        
        if dt > dt_threshold:
            # Fin de la avalancha anterior
            # Solo guardamos si count > 0 (ignoramos atascos de 0 partículas si los hubiera)
            if particle_count > 0:
                avalanche_sizes.append(particle_count)
            
            # Reset para nueva avalancha
            particle_count = 1
            current_end = t
        else:
            # Continuidad de la avalancha
            current_end = t
            particle_count += 1
            
    # Registrar el último evento pendiente
    if particle_count > 0:
        avalanche_sizes.append(particle_count)

    # 3. CÁLCULO: Media
    if not avalanche_sizes:
        return 0.0
    
    return statistics.mean(avalanche_sizes)

def main():
    base_path = Path(BASE_DIR)
    results: List[Tuple[float, float]] = [] # Lista de tuplas (outlet, mean_size)

    print(f"Iniciando análisis en: {base_path.resolve()}")
    print(f"Buscando archivos '{INPUT_FILENAME}' en carpetas 'outlet_*'...")

    # Recorrer directorios
    for entry in sorted(base_path.iterdir()):
        if entry.is_dir() and entry.name.startswith("outlet_"):
            
            # 1. Obtener tamaño del outlet
            try:
                outlet_val = get_outlet_size_from_folder(entry.name)
            except ValueError as e:
                print(f"[SKIP] {e}")
                continue

            # 2. Ruta al archivo flx.dat
            flx_file = entry / INPUT_FILENAME
            
            # 3. Procesar y calcular media
            mean_size = compute_mean_avalanche_size(flx_file, DT_THRESHOLD, TARGET_TYPE)
            
            if mean_size is not None:
                results.append((outlet_val, mean_size))
                print(f"[OK] {entry.name}: Outlet={outlet_val} -> Media={mean_size:.4f}")
            else:
                print(f"[WARN] {entry.name}: Sin datos válidos o archivo no encontrado.")

    # Guardar resultados
    if results:
        # Ordenar por tamaño de outlet
        results.sort(key=lambda x: x[0])
        
        output_path = base_path / OUTPUT_SUMMARY_FILE
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("tamaño_medio_de_avalancha,outlet\n")
                for outlet, mean_sz in results:
                    f.write(f"{mean_sz:.6f},{outlet:.3f}\n")
            
            print("-" * 40)
            print(f"¡Éxito! Archivo generado: {output_path}")
        except IOError as e:
            print(f"Error escribiendo archivo de salida: {e}")
    else:
        print("No se generaron resultados. Verifica la ruta y los nombres de archivo.")

if __name__ == "__main__":
    # Puedes sobreescribir BASE_DIR aquí si pasas argumentos, 
    # o simplemente dejarlo configurado arriba.
    # Ejemplo: BASE_DIR = "/home/usuario/datos"
    main()