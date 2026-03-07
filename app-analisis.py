import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import re

st.set_page_config(layout="wide", page_title="Dashboard")

@st.cache_data
def load_and_fix_data():
    # --- 1. CARGA DE DATOS ---
    df_av = pd.read_csv("processed_data/1_avalanche_data/resultados_completos_esqueleto.csv")
    df_idx = pd.read_csv("master_sim_index.csv")
    df_arcos = pd.read_csv('processed_data/1_avalanche_data/resultados_completos_arcos.csv')

    def get_name(row):
        try:
            g = json.loads(row['grain_json'])
            n = {1: "Disco", 3: "Triangulo", 4: "Cuadrado", 5: "Pentagono"}
            n1 = n.get(g[0]['sides'], "Polig")
            return f"{n1}-{n.get(g[1]['sides'], 'P')}" if len(g)>1 else f"{n1}-Puro"
        except: return "Otros"

    df_idx['sistema'] = df_idx.apply(get_name, axis=1)
    df_idx['chi'] = df_idx['path'].apply(lambda x: float(re.search(r"Chi_(\d+p\d+)_", str(x)).group(1).replace('p', '.')) if "Chi_" in str(x) else 0.0)
    df_idx = df_idx[df_idx['chi'] <= 0.201]
    df_master = pd.merge(df_av, df_idx[['sim_hash', 'chi', 'sistema']], on='sim_hash')
    
    df_arcos['sistema'] = df_arcos['sistema_detallado'].apply(lambda x: x.replace(" ", "").replace("(G)", "").replace("(C)", ""))
    df_arcos['sistema'] = df_arcos['sistema'].apply(lambda x: x.replace("Puro", "-Puro").replace("--", "-"))
    df_arcos = df_arcos[df_arcos['chi_nominal'] <= 0.201]
    df_arcos['f_real'] = df_arcos['Particulas_Tipo_1'] / df_arcos['Total_Particulas_Arco']
    
    if 'Particulas_Tipo_0' not in df_arcos.columns:
        df_arcos['Particulas_Tipo_0'] = df_arcos['Total_Particulas_Arco'] - df_arcos['Particulas_Tipo_1']

    # --- 2. INYECCIÓN CHI=0 ---
    puros_av = df_master[df_master['chi'] == 0.0].copy()
    puros_ar = df_arcos[df_arcos['chi_nominal'] == 0.0].copy()
    df_master = df_master[df_master['chi'] > 0.0].copy()
    df_arcos = df_arcos[df_arcos['chi_nominal'] > 0.0].copy()

    sistemas_mezcla = list(df_master['sistema'].unique())
    df_av_final, df_ar_final = [df_master], [df_arcos]

    for sis in sistemas_mezcla:
        base_shape = sis.split('-')[0] 
        p_av = puros_av[puros_av['sistema'].str.contains(base_shape)].copy()
        p_ar = puros_ar[puros_ar['sistema'].str.contains(base_shape)].copy()
        p_av['sistema'], p_ar['sistema'] = sis, sis
        df_av_final.append(p_av); df_ar_final.append(p_ar)

    df_master = pd.concat(df_av_final, ignore_index=True)
    df_arcos = pd.concat(df_ar_final, ignore_index=True)

    # --- 3. ESTADÍSTICAS ---
    stats = df_master.groupby(['sistema', 'chi'])['tamano_big'].agg(['mean', 'std']).reset_index()
    stats.rename(columns={'mean': 'tamano_big', 'std': 'std_S'}, inplace=True)
    stats['CV'] = stats['std_S'] / stats['tamano_big']

    s0_df = stats[stats['chi'] == 0.0][['sistema', 'tamano_big']].rename(columns={'tamano_big': 'S0'})
    stats = pd.merge(stats, s0_df, on='sistema')
    stats['y_log'] = np.log((stats['tamano_big'] / stats['S0']) + 1)
    
    res_n_temp = df_arcos.groupby(['sistema', 'chi_nominal'])[['Total_Particulas_Arco', 'f_real']].mean().reset_index()
    n0_temp = res_n_temp[res_n_temp['chi_nominal'] == 0.0][['sistema', 'Total_Particulas_Arco']].rename(columns={'Total_Particulas_Arco': 'N0'})
    res_n_temp = pd.merge(res_n_temp, n0_temp, on='sistema')
    res_n_temp['N_norm'] = res_n_temp['Total_Particulas_Arco'] / res_n_temp['N0']
    res_n_temp['epsilon'] = res_n_temp.apply(lambda r: r['f_real']/r['chi_nominal'] if r['chi_nominal'] > 0 else 1.0, axis=1)

    # --- 4. CÁLCULO DE LÍMITES PARA LIMS ---
    S_LIMIT = df_master['tamano_big'].quantile(0.98)
    temp_max_dens = 0
    for s in df_master['sistema'].unique():
        for c in df_master['chi'].unique():
            sub = df_master[(df_master['sistema'] == s) & (df_master['chi'] == c)]
            if not sub.empty:
                counts, _ = np.histogram(sub['tamano_big'], bins=50, range=(0, S_LIMIT), density=True)
                if counts.max() > temp_max_dens: temp_max_dens = counts.max()

    LIMS = {
        'S_max': S_LIMIT,
        'Y_dens_max': temp_max_dens * 1.15,
        'Y_log_max': stats['y_log'].max() * 1.1,
        'N_max': df_arcos['Total_Particulas_Arco'].max() * 1.05,
        'N_norm_max': res_n_temp['N_norm'].max() * 1.05, 
        'CV_max': stats['CV'].max() * 1.1,
        'EPS_max': res_n_temp['epsilon'].max() * 1.1,
        'F_REAL_max': res_n_temp['f_real'].max() * 1.1,
        'max_t1': df_arcos['Particulas_Tipo_1'].max(), 
        'max_t0': df_arcos['Particulas_Tipo_0'].max(),
        'SISTEMAS': sorted(df_master['sistema'].unique()), 
        'CHI_VALS': sorted(df_master['chi'].unique())
    }
    return df_master, df_arcos, stats, res_n_temp, LIMS

df_master, df_arcos, stats, res_n_norm, LIMS = load_and_fix_data()

st.title("🔬 Dashboard de Tesis UNLPam v18.8 - Análisis Final")
sistema_sel = st.sidebar.selectbox("Fijar Sistema para Sección 2", LIMS['SISTEMAS'])

# =============================================================================
# SECCIÓN 1: TENDENCIAS GLOBALES
# =============================================================================
st.header("1. Tendencias Globales")

st.subheader("A. Eficacia de Flujo $\ln(S/S_0 + 1)$")
st.plotly_chart(px.line(stats, x='chi', y='y_log', color='sistema', markers=True).add_hline(y=np.log(2), line_dash="dash").update_layout(template="plotly_white", height=450, yaxis_range=[0.5, LIMS['Y_log_max']]), use_container_width=True)

st.subheader("B. Composición Real del Arco ($f_{real}$ vs $\chi$)")
fig_b = px.line(res_n_norm, x='chi_nominal', y='f_real', color='sistema', markers=True)
fig_b.add_trace(go.Scatter(x=[0, 0.21], y=[0, 0.21], mode='lines', line=dict(color='black', dash='dot'), name='Mezcla Ideal'))
st.plotly_chart(fig_b.update_layout(template="plotly_white", height=450, yaxis_range=[0, LIMS['F_REAL_max']], xaxis_range=[0, 0.21]), use_container_width=True)

st.subheader("C. ($\epsilon = f_{real} / \chi$)")
st.plotly_chart(px.line(res_n_norm[res_n_norm['chi_nominal']>0], x='chi_nominal', y='epsilon', color='sistema', markers=True).add_hline(y=1.0, line_dash="dash").update_layout(template="plotly_white", height=450, yaxis_range=[0, LIMS['EPS_max']]), use_container_width=True)

st.subheader("D. Estructura Relativa ($N/N_0$)")
st.plotly_chart(px.line(res_n_norm, x='chi_nominal', y='N_norm', color='sistema', markers=True).add_hline(y=1.0, line_dash="dash").update_layout(template="plotly_white", height=450, yaxis_range=[0, LIMS['N_norm_max']]), use_container_width=True)

# =============================================================================
# SECCIÓN 2: ANÁLISIS MICROSCÓPICO (ZOOM)
# =============================================================================
st.markdown("---")
st.header(f"2. Análisis Microscópico: {sistema_sel}")



st.subheader("F. Arcos (Mapa de Calor 2D)")
data_arcos_sys = df_arcos[df_arcos['sistema'] == sistema_sel]
z_max_prob = 0
for c in LIMS['CHI_VALS']:
    sub = data_arcos_sys[data_arcos_sys['chi_nominal'] == c]
    if not sub.empty:
        counts, _, _ = np.histogram2d(sub['Particulas_Tipo_1'], sub['Particulas_Tipo_0'], bins=[np.arange(-0.5, LIMS['max_t1']+1.5), np.arange(-0.5, LIMS['max_t0']+1.5)])
        z_max_prob = max(z_max_prob, (counts / counts.sum()).max())

fig_heat = go.Figure()
for c in LIMS['CHI_VALS']:
    sub = data_arcos_sys[data_arcos_sys['chi_nominal'] == c]
    fig_heat.add_trace(go.Histogram2d(x=sub['Particulas_Tipo_1'], y=sub['Particulas_Tipo_0'], xbins=dict(start=-0.5, end=LIMS['max_t1']+0.5, size=1), ybins=dict(start=-0.5, end=LIMS['max_t0']+0.5, size=1), histnorm='probability', zmin=0, zmax=z_max_prob, colorscale='Viridis', visible=False))
fig_heat.data[0].visible = True
steps_h = [dict(method="update", label=str(c), args=[{"visible": [i==j for j in range(len(LIMS['CHI_VALS']))]}]) for i, c in enumerate(LIMS['CHI_VALS'])]
fig_heat.update_layout(sliders=[dict(active=0, steps=steps_h, currentvalue={"prefix": "Chi: "})], template="plotly_dark", height=500, xaxis_title="Aditivos", yaxis_title="Grandes")
st.plotly_chart(fig_heat, use_container_width=True)


    # st.subheader("G. Correlación: Fracción vs Tamaño")
    # fig_corr = go.Figure()
    # for c in LIMS['CHI_VALS']:
    #     sub = data_arcos_sys[data_arcos_sys['chi_nominal'] == c]
    #     fig_corr.add_trace(go.Scatter(x=sub['Total_Particulas_Arco'], y=sub['f_real'], mode='markers', marker=dict(color='#ff7f0e', opacity=0.4, size=10), visible=False))
    # fig_corr.data[0].visible = True
    # steps_c = [dict(method="update", label=str(c), args=[{"visible": [i==j for j in range(len(LIMS['CHI_VALS']))]}]) for i, c in enumerate(LIMS['CHI_VALS'])]
    # fig_corr.update_layout(sliders=[dict(active=0, steps=steps_c, currentvalue={"prefix": "Chi: "})], template="plotly_white", height=500, xaxis_range=[0, LIMS['N_max']], yaxis_range=[0, 0.6], xaxis_title="N (Tamaño Arco)", yaxis_title="f_real")
    # st.plotly_chart(fig_corr, use_container_width=True)

# H. Histograma PDF
st.subheader("H. Distribución de Avalanchas (PDF)")
data_sys = df_master[df_master['sistema'] == sistema_sel]
fig_hist = go.Figure()
for c in LIMS['CHI_VALS']:
    sub = data_sys[data_sys['chi'] == c]
    fig_hist.add_trace(go.Histogram(x=sub['tamano_big'], nbinsx=50, visible=False, marker_color='#1f77b4', histnorm='probability density', xbins=dict(start=0, end=LIMS['S_max'], size=LIMS['S_max']/50), name=f"chi={c}"))
fig_hist.data[0].visible = True
steps_hist = [dict(method="update", label=str(c), args=[{"visible": [i==j for j in range(len(LIMS['CHI_VALS']))]}]) for i, c in enumerate(LIMS['CHI_VALS'])]
fig_hist.update_layout(sliders=[dict(active=0, steps=steps_hist, currentvalue={"prefix": "Chi: "})], template="plotly_white", height=500, xaxis_range=[0, LIMS['S_max']], yaxis_range=[0, LIMS['Y_dens_max']], xaxis_title="S (Tamaño Avalancha)", yaxis_title="Densidad PDF")
st.plotly_chart(fig_hist, use_container_width=True)
