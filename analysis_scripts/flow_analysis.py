import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import json

def get_detailed_system_name(row):
    try:
        grains = json.loads(row['grain_json'])
        gs = sorted(grains, key=lambda x: x['radius'], reverse=True)
        nombres = {1: "Disco", 3: "Tri", 4: "Cuad", 5: "Pent"}
        n1 = nombres.get(gs[0]['sides'], "Pol")
        n2 = nombres.get(gs[1]['sides'], "Pol") if len(gs)>1 else "Puro"
        return f"{n1}(G)-{n2}(C)"
    except: return "Otros"

def main(mode='ratio_sweep', fixed_val=0.01, normalize=True, target_system=None,
    idx_path = "../master_sim_index.csv",
    av_path = "../processed_data/1_avalanche_data/resultados_completos_esqueleto.csv"):
    
    if not os.path.exists(idx_path): return print("Ejecutá indexer.py primero.")
    
    df_idx = pd.read_csv(idx_path)
    df_av = pd.read_csv(av_path)
    
    # Metadatos
    df_idx['sistema'] = df_idx.apply(get_detailed_system_name, axis=1)
    df_idx['grano_base'] = df_idx['sistema'].apply(lambda x: x.split('-')[0])
    
    df = pd.merge(df_av, df_idx[['sim_hash', 'chi', 'r_ratio', 'area_ratio', 'sistema', 'grano_base']], on='sim_hash')

    df = df[df['chi'] <= 0.2]

    # --- LÓGICA DE NORMALIZACIÓN ---
    puros = df[df['chi'] == 0.0].groupby('grano_base').agg(
        mean_0=('tamano_big', 'mean'),
        sem_0=('tamano_big', 'sem')
    ).reset_index()

    # --- CONFIGURACIÓN DE MODO ---
    if mode == 'ratio_sweep':
        # FILTRO CRÍTICO 1: Solo el chi que nos interesa
        stats = df[df['chi'] == fixed_val].copy()
        x_col, x_label = 'area_ratio', r"Ratio de Areas ($A_{S}/A_{L}$)"
        suffix = f"ratio_sweep_chi{str(fixed_val).replace('.','p')}"
        
        # FILTRO CRÍTICO 2: Solo el sistema que nos interesa (NUEVO)
        if target_system is not None:
            stats = stats[stats['sistema'] == target_system].copy()
            # Limpiamos el nombre para que el archivo de salida no tenga caracteres raros
            sys_safe = target_system.replace("(", "").replace(")", "").replace("-", "_")
            suffix += f"_{sys_safe}"
            
    else:
        stats = df.copy()
        x_col, x_label = 'chi', r"Concentración $\chi$"
        suffix = "chi_sweep"
        
        # Si quisieras también filtrar por sistema en el barrido de chi
        if target_system is not None:
            stats = stats[stats['sistema'] == target_system].copy()
            sys_safe = target_system.replace("(", "").replace(")", "").replace("-", "_")
            suffix += f"_{sys_safe}"

    # Verificación de seguridad por si el filtro dejó el dataset vacío
    if stats.empty:
        print(f"⚠️ No hay datos para procesar con chi={fixed_val} y sistema={target_system}. Saltando gráfico...")
        return

    # Agregación
    res = stats.groupby(['sistema', 'chi', 'r_ratio', 'area_ratio', 'grano_base']).agg(
        y_raw=('tamano_big', 'mean'),
        y_err_raw=('tamano_big', 'sem')
    ).reset_index()

    # Unimos con los casos puros
    res = pd.merge(res, puros, on='grano_base', how='left')

    # Si no hay casos puros (chi=0), desactivamos normalización para evitar NaNs
    if res['mean_0'].isnull().all():
        print("⚠️ No se detectó Chi=0.0. Usando valores absolutos.")
        normalize = False

    if normalize:
        res['mean_0'] = res['mean_0'].fillna(1.0) # Evitar div por cero
        res['val'] = res['y_raw'] / res['mean_0']
        res['err'] = res['val'] * np.sqrt((res['y_err_raw']/res['y_raw'])**2 + (res['sem_0'].fillna(0)/res['mean_0'])**2)
        ylabel = r"$\ln(\langle S \rangle / \langle S \rangle_0 + 1)$"
    else:
        res['val'], res['err'] = res['y_raw'], res['y_err_raw']
        ylabel = r"$\ln(\langle S \rangle + 1)$"

    res['y_plot'] = np.log(res['val'] + 1)
    res['y_err_plot'] = res['err'] / (res['val'] + 1)

    # --- LIMPIEZA DE NaNs ANTES DE GRAFICAR ---
    res = res.dropna(subset=['y_plot'])

    # Graficación
    plt.figure(figsize=(10, 6))
    
    if mode == 'chi_sweep':
        for sis in res['sistema'].unique():
            df_sis = res[res['sistema'] == sis]
            
            # Identificamos el radio "principal"
            r_counts = df_sis['r_ratio'].value_counts()
            main_r = r_counts.idxmax()
            
            # DESCARTAMOS el resto
            grupo_principal = df_sis[df_sis['r_ratio'] == main_r].sort_values(x_col)
            
            # Trazamos la línea limpia
            plt.errorbar(grupo_principal[x_col], grupo_principal['y_plot'], 
                         yerr=grupo_principal['y_err_plot'], fmt='o-', 
                         label=sis, capsize=3)
    else:
        # Comportamiento original para el barrido de áreas (ratio_sweep)
        for sis, group in res.groupby('sistema'):
            group = group.sort_values(x_col)
            plt.errorbar(group[x_col], group['y_plot'], yerr=group['y_err_plot'], fmt='o-', label=sis, capsize=3)

    plt.xlabel(x_label)
    plt.ylabel(ylabel)
    
    titulo = f"Análisis de Atascamiento ({mode})"
    if target_system: titulo += f" - {target_system}"
    plt.title(titulo)
    
    # Ajustamos la leyenda para que no se superpongan demasiados elementos
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    
    os.makedirs("../processed_data/1_avalanche_data", exist_ok=True)
    
    # Mantenemos el guardado en formato vectorial SVG
    plt.savefig(f"../processed_data/1_avalanche_data/plot_{suffix}.svg", bbox_inches='tight', format='svg')
    res.to_csv(f"../processed_data/1_avalanche_data/datos_{suffix}.csv", index=False)
    
    print(f"✅ Finalizado: plot_{suffix}.svg con {len(res)} puntos.")

if __name__ == "__main__":
    # Ejemplo probando desde acá:
    main(mode='ratio_sweep', fixed_val=0.01, normalize=True, target_system='Disco(G)-Disco(C)')
    
    # También podés correr el barrido clásico descomentando la línea de abajo:
    #main(mode='chi_sweep', normalize=True)