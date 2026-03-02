import numpy as np
import matplotlib.pyplot as plt
import os

# ==========================================
# CONFIGURACIÓN DE SALIDA
# ==========================================
# Carpeta donde se guardarán los perfiles, según tu estructura solicitada
PERFILES_DIR = "../processed_data/4_velocity_profiles"

def plot_perfil_horizontal(npz_path, altura_y=10, output_folder=PERFILES_DIR):
    """
    Carga un archivo .npz y genera un gráfico del perfil de velocidades 
    transversal (X) a una altura Y específica.
    """
    try:
        # 1. Cargar los datos pre-procesados
        data = np.load(npz_path)
        
        # Obtenemos las dimensiones de la grilla desde la matriz de densidad
        GRID_NY = data['d1'].shape[0]
        Y_MAX = 120.0
        
        # PASO CRÍTICO: Convertimos la altura física (ej. 10) al índice 
        # de la fila en la matriz (regla de tres simple según tu lógica)
        row_idx = int(altura_y * (GRID_NY / Y_MAX))
        
        # 2. Generar coordenadas X para el eje horizontal
        x_coords = np.linspace(-10.25, 10.25, data['d1'].shape[1])
        
        # 3. Cálculo de Magnitudes de Velocidad en esa "rebanada"
        # Usamos Pitágoras para obtener la rapidez absoluta de cada fase
        v0 = np.sqrt(data['vx0'][row_idx, :]**2 + data['vy0'][row_idx, :]**2)
        v1 = np.sqrt(data['vx1'][row_idx, :]**2 + data['vy1'][row_idx, :]**2)
        
        # --- GENERACIÓN DEL GRÁFICO ---
        plt.figure(figsize=(10, 6))
        
        # Graficamos con puntos y líneas suaves (o- para discos, s- para aditivos)
        plt.plot(x_coords, v0, 'o-', label='Discos Grandes (Esqueleto)', 
                 markersize=4, alpha=0.8)
        plt.plot(x_coords, v1, 's-', label='Aditivos (Pequeños)', 
                 markersize=4, alpha=0.8)
        
        # Estética del gráfico
        plt.title(f'Perfil de Velocidad Transversal (Altura Y = {altura_y})', fontsize=14)
        plt.xlabel('Posición Horizontal (X)', fontsize=12)
        plt.ylabel('Magnitud de Velocidad |V| [u/s]', fontsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.legend()
        
        # 4. Guardado organizado
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        # El nombre del archivo incluye el hash de la simulación para identificarlo
        base_name = os.path.basename(npz_path).replace(".npz", "")
        file_name = f"perfil_{base_name}_Y{altura_y}.png"
        save_path = os.path.join(output_folder, file_name)
        
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close() # Cerramos para liberar memoria en procesos largos
        
        return True

    except Exception as e:
        print(f"Error al graficar perfil para {npz_path}: {e}")
        return False

# ==========================================
# BLOQUE DE SEGURIDAD (Modularidad)
# ==========================================
if __name__ == "__main__":
    """
    Este bloque solo se ejecuta si corres 'python3 plot_perfiles.py' manualmente.
    Cuando el script maestro lo importa, este bloque se ignora, evitando
    errores de 'archivo no encontrado'.
    """
    # Ejemplo de uso manual (descomentar para probar un archivo específico)
    # test_file = "0_mapa_prepro/mapas_fc0a4302_T1.npz"
    # if os.path.exists(test_file):
    #     plot_perfil_horizontal(test_file, altura_y=15)
    pass