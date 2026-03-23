import numpy as np
import matplotlib.pyplot as plt
import os
import matplotlib

# Evita errores en entornos sin interfaz gráfica
matplotlib.use('Agg')

# --- CONFIGURACIÓN ---
POSTPRO_DIR = "/work/lab/project/sim-binary-shapes-2d/processed_data/2_spatial_maps"

def plot_segregation_analysis(npz_path, chi_global=0.1, output_folder=POSTPRO_DIR):
    """
    Genera un mapa de calor de alta calidad de la distribución de aditivos.
    """
    try:
        # 1. Cargar datos
        data = np.load(npz_path)
        s_hash = os.path.basename(npz_path).replace(".npz", "")
        
        # d0: Grandes, d1: Chicas
        d1 = data['d1']
        # Extensión real: [X_min, X_max, Y_min, Y_max]
        extent = [-10.25, 10.25, 0, 120]

        # --- GENERACIÓN DE LA FIGURA ---
        # Ajustamos el figsize para que sea coherente con un silo alto y estrecho
        fig, ax = plt.subplots(figsize=(6, 10), constrained_layout=True)

        # Usamos 'aspect=auto' o calculamos uno para que el silo mantenga su forma
        # Para un silo de 20.5 de ancho y 120 de alto:
        im0 = ax.imshow(d1, origin='lower', extent=extent, 
                        cmap='viridis', interpolation='gaussian', 
                        aspect='auto') # 'auto' permite que el figsize mande

        # 2. MEJORAS VISUALES
        # Añadimos las paredes del silo (líneas blancas o negras en los bordes de extent)
        ax.axvline(-10.25, color='black', linewidth=2, alpha=0.7)
        ax.axvline(10.25, color='black', linewidth=2, alpha=0.7)

        # Títulos y etiquetas
        ax.set_title(f"Distribución Espacial de Aditivos\nHash: {s_hash}", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel("Posición Horizontal (X)", fontsize=11)
        ax.set_ylabel("Altura del Silo (Y)", fontsize=11)

        # Colorbar ajustada
        cbar = plt.colorbar(im0, ax=ax, shrink=0.8)
        cbar.set_label('Densidad Promedio (partículas/celda)', fontsize=10)

        # 3. GUARDADO
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            
        save_path = os.path.join(output_folder, f"{s_hash}_segregacion.png")
        
        # Guardamos con alta resolución (DPI 300) para publicaciones
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✅ Éxito: Mapa de densidad optimizado para {s_hash}")
        return True

    except Exception as e:
        print(f"❌ Error en density_map para {npz_path}: {e}")
        return False

if __name__ == "__main__":
    # Ejemplo de uso:
    # plot_segregation_analysis("0_mapa_prepro/mapas_XXXX_T1.npz")
    pass