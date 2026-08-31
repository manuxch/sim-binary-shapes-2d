#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pandas as pd
import os

def filtrar():
    archivo = "resumen_fuerza_normal_por_configuracion.csv"
    if not os.path.exists(archivo):
        print(f"No encuentro {archivo}")
        return

    df = pd.read_csv(archivo)
    
    # Definimos los patrones exactos. 
    # Si quieres 'Cuad-Disco' pero NO 'Disco-Cuad', usamos comparacion de igualdad exacta.
    salidas = {
        "filtrado_cuadrados_disco.csv": df[df['geometry_label'] == 'Cuad-Disco'],
        "filtrado_triangulos_disco.csv": df[df['geometry_label'] == 'Tri-Disco'],
        "filtrado_pentagonos_disco.csv": df[df['geometry_label'] == 'Pent-Disco'],
        "filtrado_disco_disco.csv": df[df['geometry_label'] == 'Disco-Disco']
    }

    for nombre, data in salidas.items():
        if not data.empty:
            data.to_csv(nombre, index=False)
            print(f"✔️ {nombre}: {len(data)} filas guardadas.")
        else:
            print(f"⚠️ {nombre}: vacio (ninguna fila coincide exactamente con el formato).")

if __name__ == "__main__":
    filtrar()