import numpy as np
import pandas as pd  # Usaremos pandas para exportar los datos limpiamente

def guardar_tensor_estres_por_particula(archivo_xy, archivo_contactos, archivo_salida='estres_particulas.csv'):
    """
    Calcula las 4 componentes del tensor de estrés para cada partícula 
    y guarda los resultados en un archivo CSV.
    """
    particulas = {}
    
    # 1. Leer posiciones y RADIOS desde el archivo .xy
    with open(archivo_xy, 'r') as f:
        for linea in f:
            partes = linea.strip().split()
            if not partes:
                continue
            idx = int(partes[0])
            num_vertices = int(partes[1])
            
            # Solo procesamos discos (num_vertices == 1)
            if num_vertices == 1:
                x = float(partes[2])
                y = float(partes[3])
                r = float(partes[4]) # Radio
                
                # Inicializamos la matriz acumuladora de fuerza x rama S (2x2)
                particulas[idx] = {
                    'centro': np.array([x, y]),
                    'radio': r,
                    'S': np.zeros((2, 2))  
                }
                
    # 2. Procesar los contactos uno a uno
    with open(archivo_contactos, 'r') as f:
        for linea in f:
            if linea.startswith('#') or not linea.strip():
                continue
                
            partes = linea.strip().split()
            id_A = int(partes[0])
            id_B = int(partes[1])
            pos_c = np.array([float(partes[2]), float(partes[3])])
            I_n = float(partes[4])
            I_t = float(partes[5])
            
            es_particula_A = id_A in particulas
            es_particula_B = id_B in particulas
            
            # Calcular el vector normal unitario (de A hacia B)
            if es_particula_A and es_particula_B:
                vec_n = particulas[id_B]['centro'] - particulas[id_A]['centro']
            elif not es_particula_A and es_particula_B:
                vec_n = particulas[id_B]['centro'] - pos_c
            elif es_particula_A and not es_particula_B:
                vec_n = pos_c - particulas[id_A]['centro']
            else:
                continue
                
            norma_n = np.linalg.norm(vec_n)
            if norma_n == 0:
                continue
            n = vec_n / norma_n
            t = np.array([-n[1], n[0]]) # Vector tangente
            
            # Fuerza que el cuerpo A ejerce sobre el cuerpo B
            f_fuerza_B = I_n * n + I_t * t
            # Fuerza que el cuerpo B ejerce sobre el cuerpo A (Tercera ley)
            f_fuerza_A = -f_fuerza_B
            
            # Acumular f_alpha * b_beta para la partícula A
            if es_particula_A:
                b_A = pos_c - particulas[id_A]['centro'] # Vector rama
                particulas[id_A]['S'] += np.outer(f_fuerza_A, b_A)
                
            # Acumular f_alpha * b_beta para la partícula B
            if es_particula_B:
                b_B = pos_c - particulas[id_B]['centro'] # Vector rama
                particulas[id_B]['S'] += np.outer(f_fuerza_B, b_B)

    # 3. Calcular los tensores finales desglosados en componentes y preparar la lista
    lista_resultados = []
    
    for idx, datos in particulas.items():
        area_particula = np.pi * (datos['radio'] ** 2)
        
        # Dividir la matriz acumulada por el área del grano
        tensor_particula = datos['S'] / area_particula
        
        # Extraer individualmente las 4 componentes de la matriz 2x2
        sigma_xx = tensor_particula[0, 0]
        sigma_xy = tensor_particula[0, 1]
        sigma_yx = tensor_particula[1, 0]
        sigma_yy = tensor_particula[1, 1]
        
        # Calcular también la presión (P) y el esfuerzo de corte máximo (Tau) por utilidad
        presion = 0.5 * (sigma_xx + sigma_yy)
        
        # Guardamos todo en un diccionario para pasarlo a DataFrame
        lista_resultados.append({
            'id_particula': idx,
            'sigma_xx': sigma_xx,
            'sigma_xy': sigma_xy,
            'sigma_yx': sigma_yx,
            'sigma_yy': sigma_yy,
            'presion': presion
        })
        
    # 4. Convertir a DataFrame de Pandas y exportar a CSV
    df = pd.DataFrame(lista_resultados)
    df.to_csv(archivo_salida, index=False)
    print(f"¡Cálculo completado! Los datos de {len(df)} partículas se guardaron en '{archivo_salida}'.")
    
    return df

# --- Ejecución del código ---
# Reemplaza con las rutas correctas de tus archivos de ejemplo
df_estres = guardar_tensor_estres_por_particula('atasco_00001.xy', 'atasco_contacts_00001.dat')

# Mostrar las primeras filas del resultado en consola para verificar
print("\nPrimeras 5 filas del archivo generado:")
print(df_estres.head())