import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
import os

# --- CONFIGURACIÓN DE ARCHIVOS ---
FILE_INDEX = "../master_sim_index.csv"
FILE_RESULTS = "../processed_data/5_segregation_analysis/reporte_segregacion_final.csv"

def identificar_sistema(json_str):
    """Clasifica la mezcla según los lados (G-C)"""
    try:
        g = json.loads(json_str)
        g_sorted = sorted(g, key=lambda x: x['radius'], reverse=True)
        
        nombres_plural = {1: "Discos", 3: "Triangulos", 4: "Cuadrados", 5: "Pentagonos"}
        
        big_s = nombres_plural.get(g_sorted[0]['sides'], f"Polig({g_sorted[0]['sides']})")
        small_s = nombres_plural.get(g_sorted[1]['sides'], f"Polig({g_sorted[1]['sides']})").lower()
        
        return f"{big_s} G. + {small_s} C."
    except:
        return "Desconocido"

def main():
    # 1. Verificación de archivos
    if not os.path.exists(FILE_INDEX) or not os.path.exists(FILE_RESULTS):
        print("❌ Error: Faltan archivos CSV. Ejecuta primero el analizador maestro.")
        return

    # 2. Cargar y Unir Datos
    df_idx = pd.read_csv(FILE_INDEX)
    df_res = pd.read_csv(FILE_RESULTS)

    df = pd.merge(df_res, df_idx[['sim_hash', 'grain_json']], on='sim_hash')
    df['Sistema'] = df['grain_json'].apply(identificar_sistema)

    # 3. Promediar Tiradas por experimento físico
    # Agrupamos por Sistema y por la concentración nominal (redondeada para agrupar tiradas)
    df['chi_nom_round'] = df['chi_nominal'].round(3)

    df_avg = df.groupby(['Sistema', 'chi_nom_round']).agg({
        'chi_nominal': 'mean',
        'chi_efectivo': 'mean'
    }).reset_index()

    # --- 4. CÁLCULO DE LA DIFERENCIA (EJE Y) ---
    # Delta Chi = Cuánto se perdió en las paredes (%)
    df_avg['delta_chi'] = ((df_avg['chi_nominal'] - df_avg['chi_efectivo']) / df_avg['chi_nominal']) * 100

    # --- 5. GENERAR LA GRÁFICA ---
    # Obtenemos los sistemas únicos que realmente existen en el DataFrame
    sistemas_reales = df_avg['Sistema'].unique()
    
    # Lista de colores y marcadores extendida para soportar más variedades
    colores = ['#2980b9', '#e67e22', '#27ae60', '#c0392b', '#8e44ad', '#f39c12']
    marcadores = ['o', 's', 'D', '^', 'v', 'p']

    plt.figure(figsize=(10, 6))

    for i, sist in enumerate(sistemas_reales):
        data = df_avg[df_avg['Sistema'] == sist].sort_values('chi_nominal')
        
        # Asignamos color y marcador cíclicamente por si hay más de 6 sistemas
        col = colores[i % len(colores)]
        mar = marcadores[i % len(marcadores)]
        
        if not data.empty:
            plt.plot(data['chi_nominal'], data['delta_chi'], 
                     label=sist, color=col, marker=mar, markersize=8, 
                     linestyle='None', markerfacecolor='white', markeredgewidth=1.5)



    # Formato de ejes
    plt.xlabel(r"$\chi$ Inyectado ($\chi_{nom}$)", fontsize=12)
    plt.ylabel(r"Pérdida de $\chi$ (%)", fontsize=12)
    
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(title="Geometría del Sistema", loc='upper right')
    plt.axhline(0, color='black', linewidth=1, alpha=0.5)

    # Guardar y mostrar
    plt.tight_layout()
    output_path = "../processed_data/5_segregation_analysis/grafica_delta_chi_puntos.svg"
    plt.savefig(output_path, format='svg')
    print(f"✅ Gráfica generada: {output_path}")
    # plt.show()

# --- BLOQUE PRINCIPAL ---
if __name__ == "__main__":
    main()