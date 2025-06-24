import os
import streamlit as st
import pandas as pd
import plotly.express as px
import tempfile
# ───── Página Config (SIEMPRE lo primero) ───────────────────────────────────────
st.set_page_config(page_title="RR.HH Integrado", page_icon="👥", layout="wide")

# ----- S3 -----
from s3_manager import S3Manager
from analisis_hr import load_hr_data, absenteeism_analysis  # …y el resto

# ───── Config S3 ────────────────────────────────────────────────────────────────
BUCKET_OR_AP = os.getenv(
    "AWS_ACCESS_POINT_ARN",
    "arn:aws:s3:us-east-2:715841338590:accesspoint/acceso-betel"
)
REGION = os.getenv("AWS_REGION", "us-east-2")

if not BUCKET_OR_AP:
    st.error("Falta la variable de entorno AWS_ACCESS_POINT_ARN con el ARN de tu Access Point.")
    st.stop()

S3 = S3Manager(BUCKET_OR_AP, region=REGION)

# …el resto de tu código…

def setup_sidebar() -> str | None:
    st.sidebar.header("📁 Gestión de datos")
    uploaded = st.sidebar.file_uploader("Subir CSV / Excel (se guarda en S3)", type=["csv", "xlsx"])

    if uploaded:
        # usa el directorio temporal del sistema, portable a Windows
        tmp_dir  = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, uploaded.name)
        with open(tmp_path, "wb") as f:
            f.write(uploaded.read())
        key = f"uploads/{uploaded.name}"
        S3.upload(tmp_path, key)
        st.sidebar.success(f"Archivo guardado en S3 → {key}")
        st.session_state["current_key"] = key

    # listado en S3
    keys = S3.list_keys("uploads/")
    sel_key = st.sidebar.selectbox("Histórico en S3", keys, index=0 if keys else None)

    if sel_key:
        # descarga también en temp dir
        tmp_dir  = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, os.path.basename(sel_key))
        S3.download(sel_key, tmp_path)
        st.sidebar.info(f"Mostrando: {sel_key}")
        # devuelve ruta local
        return tmp_path

    st.sidebar.info("Sin datos.")
    return None
# --------------------------------------------------------------------------------
# Importaciones de tus módulos
# --------------------------------------------------------------------------------
from analisis_hr import (
    load_hr_data, 
    demographic_analysis, 
    contract_analysis, 
    salary_analysis, 
    attendance_analysis,
    analyze_total_LME,
    analyze_grupo_diagnostico_LME,
    analyze_duracion_LME,
    absenteeism_analysis,
    absenteeism_comparison,
    causales_analysis
)

from integrar import (
    horas_extras_vs_sueldos,
    faltas_vs_sueldo,
    antiguedad,
    dotacion,
    composicion_ausencias,
    empleados_activos,
    faltas_por_cargo_y_departamento
)

# --------------------------------------------------------------------------------
# Funciones Auxiliares
# --------------------------------------------------------------------------------
def init_session_state():
    if "column_mappings" not in st.session_state:
        st.session_state["column_mappings"] = {}
    if "df_original" not in st.session_state:
        st.session_state["df_original"] = pd.DataFrame()
    if "df_filtered" not in st.session_state:
        st.session_state["df_filtered"] = pd.DataFrame()

@st.cache_data
def cached_load_data(file) -> pd.DataFrame:
    return load_hr_data(file)

def inject_css():
    st.markdown(
        """
        <style>
        body { background-color: #f8f9fa; font-family: 'Segoe UI', sans-serif; color: #333; }
        .main-header {
            background: linear-gradient(90deg, #28a745, #20c997);
            color: white; padding: 1.5rem; border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            margin-bottom: 2rem; text-align: center;
        }
        .dashboard-card {
            background-color: white; padding: 1.5rem; border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            margin-bottom: 1.5rem; transition: transform 0.2s, box-shadow 0.2s;
        }
        .dashboard-card:hover {
            transform: translateY(-5px); box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
        }
        .section-title {
            color: #28a745; border-bottom: 2px solid #e9ecef;
            padding-bottom: 0.5rem; margin-bottom: 1rem; font-weight: 600;
        }
        .sidebar-header {
            background: linear-gradient(90deg, #28a745, #20c997);
            color: white; padding: 1rem; border-radius: 5px;
            margin-bottom: 1rem; text-align: center;
        }
        .stButton>button {
            background-color: #28a745; color: white; border: none;
            border-radius: 5px; padding: 0.5rem 1rem; font-weight: 500;
            transition: all 0.2s;
        }
        .stButton>button:hover {
            background-color: #218838; box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def display_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div class="main-header">
                <img src="https://betel-website.s3.us-east-2.amazonaws.com/logos.png" width="120">
                <h1>Dashboard de Recursos Humanos Integrado</h1>
                <p>Análisis completo para toma de decisiones estratégicas</p>
            </div>
            """,
            unsafe_allow_html=True
        )

def setup_period_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.markdown("### ⏱️ Filtros Temporales")
    df_filtered = df.copy()

    if 'Período' not in df_filtered.columns:
        if 'ContractStartDate' in df_filtered.columns:
            df_filtered['Período'] = df_filtered['ContractStartDate'].dt.strftime("%Y%m")
            st.sidebar.info("Se creó 'Período' a partir de 'ContractStartDate'.")
        else:
            st.sidebar.warning("No se encontró 'Período' ni 'ContractStartDate'.")
            return df_filtered

    df_filtered['Período'] = df_filtered['Período'].astype(str)
    unique_periods = df_filtered['Período'].unique()
    unique_years = sorted({p[:4] for p in unique_periods if len(p) >= 6})
    unique_months = sorted({p[4:6] for p in unique_periods if len(p) >= 6})

    month_names = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }
    month_options = ["Todos"] + [f"{month_names.get(m, m)} ({m})" for m in unique_months]

    with st.sidebar.form("filtros_form"):
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Año", options=["Todos"] + unique_years, key="year_filter")
        with col2:
            selected_month_display = st.selectbox("Mes", options=month_options, key="month_filter")
        selected_month = "Todos" if selected_month_display == "Todos" else selected_month_display.split("(")[1].strip(")")

        state_options = ["Todos", "Activos", "No Activos"]
        selected_state = st.selectbox("Estado del Trabajador", state_options, key="state_filter")
        map_estado = st.checkbox("¿Mapear columna para estado del trabajador?")
        custom_estado = None
        custom_active_value = None
        if map_estado:
            req = {"Estado": "Columna que indica estado del trabajador:"}
            mapping_estado = dynamic_column_mapping(df_filtered, req, "estado_trabajador")
            if len(mapping_estado) == 1:
                custom_estado = mapping_estado["Estado"]
                st.info(f"Columna mapeada: {custom_estado}")
                custom_active_value = st.text_input("Valor que indica activo:", value="Active")
            else:
                st.warning("Complete el mapeo para proceder.")

        submit_filters = st.form_submit_button("Aplicar Filtros")

    if selected_year != "Todos":
        df_filtered = df_filtered[df_filtered['Período'].str.startswith(selected_year)]
    if selected_month != "Todos":
        df_filtered = df_filtered[df_filtered['Período'].str.endswith(selected_month)]

    if selected_state in ["Activos", "No Activos"]:
        if custom_estado:
            if selected_state == "Activos":
                df_filtered = df_filtered[
                    df_filtered[custom_estado].astype(str).str.lower().str.strip() == custom_active_value.lower().strip()
                ]
            else:
                df_filtered = df_filtered[
                    df_filtered[custom_estado].astype(str).str.lower().str.strip() != custom_active_value.lower().strip()
                ]
        else:
            if "Status" in df_filtered.columns:
                if selected_state == "Activos":
                    df_filtered = df_filtered[df_filtered['Status'] == 'Active']
                else:
                    df_filtered = df_filtered[df_filtered['Status'] != 'Active']
            elif 'causal de termino' in df_filtered.columns:
                if selected_state == "Activos":
                    df_filtered = df_filtered[
                        df_filtered['causal de termino'].astype(str).str.lower().str.strip() == 'sin definir'
                    ]
                else:
                    df_filtered = df_filtered[
                        df_filtered['causal de termino'].astype(str).str.lower().str.strip() != 'sin definir'
                    ]

    st.sidebar.markdown(f"**Registros:** {len(df_filtered):,}")
    return df_filtered

def display_key_metrics(df: pd.DataFrame):
    st.markdown('<h3 class="section-title">📊 Métricas Clave</h3>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    
    total_empleados = len(df)
    with c1:
        st.metric(label="Total Empleados", value=total_empleados)

    with c2:
        if 'Status' in df.columns:
            activos = (df['Status'] == 'Active').sum()
        elif 'causal de termino' in df.columns:
            activos = (df['causal de termino'].astype(str).str.lower().str.strip() == 'sin definir').sum()
        else:
            activos = 0
        st.metric(label="Empleados Activos", value=activos)

    with c3:
        if 'Salary' in df.columns and pd.api.types.is_numeric_dtype(df['Salary']):
            avg = df['Salary'].mean()
            st.metric(label="Salario Prom.", value=f"${avg:,.2f}")
        elif 'BaseSalary' in df.columns and pd.api.types.is_numeric_dtype(df['BaseSalary']):
            avg = df['BaseSalary'].mean()
            st.metric(label="Salario Prom.", value=f"${avg:,.2f}")
        else:
            st.metric(label="Salario Prom.", value="N/A")

    with c4:
        if 'Department' in df.columns:
            deptos = df['Department'].nunique()
            st.metric(label="Departamentos", value=deptos)
        else:
            st.metric(label="Departamentos", value="N/A")

def dynamic_column_mapping(df: pd.DataFrame, required_cols: dict, mapping_key: str = "") -> dict:
    if mapping_key in st.session_state["column_mappings"]:
        saved_mapping = st.session_state["column_mappings"][mapping_key]
    else:
        saved_mapping = {}

    st.markdown("### Mapeo de Columnas")
    new_mapping = {}
    for key, label_msg in required_cols.items():
        default_value = saved_mapping.get(key, "-- Seleccione --")
        # Ajustar el índice para selectbox si estaba guardado
        if default_value in df.columns:
            idx = list(df.columns).index(default_value) + 1
        else:
            idx = 0

        opcion = st.selectbox(
            label_msg,
            options=["-- Seleccione --"] + list(df.columns),
            index=idx,
            key=f"{mapping_key}_{key}"
        )
        if opcion != "-- Seleccione --":
            new_mapping[key] = opcion

    if new_mapping:
        st.session_state["column_mappings"][mapping_key] = new_mapping

    return new_mapping

def convalidacion_licencias(df: pd.DataFrame):
    st.markdown("### Convalidación de Licencias")
    st.write("Agrupa los días de licencia acumulados por empleado y periodo.")
    
    req = {
        "EmployeeID": "Columna para Empleado (Rut/Nombre):",
        "BaseSalary": "Columna para Salario Base:",
        "LicenseDays": "Columna para Días de Licencia:",
        "Period": "Columna para Período (YYYYMM):"
    }
    mapping = dynamic_column_mapping(df, req, "convalidacion")
    if len(mapping) == len(req):
        df_conv = df.copy()
        df_conv["BaseSalary"] = pd.to_numeric(df_conv[mapping["BaseSalary"]], errors="coerce")
        df_conv["LicenseDays"] = pd.to_numeric(df_conv[mapping["LicenseDays"]], errors="coerce")
        if "Period" not in df_conv.columns:
            df_conv["Period"] = df_conv[mapping["Period"]]
        grouped = df_conv.groupby([mapping["EmployeeID"], "Period"]).agg({
            "LicenseDays": "sum",
            "BaseSalary": "first"
        }).reset_index()
        min_days = st.number_input("Mínimo de días a pagar:", min_value=0, value=5)
        grouped["DailyWage"] = grouped["BaseSalary"] / 30
        grouped["LicenciaPagadaDias"] = grouped["LicenseDays"].apply(lambda x: max(x, min_days))
        grouped["PagoLicencia"] = grouped["LicenciaPagadaDias"] * grouped["DailyWage"]
        st.dataframe(grouped)
        st.write(f"**Pago Total:** ${grouped['PagoLicencia'].sum():,.2f}")
    else:
        st.info("Complete el mapeo para la convalidación de licencias.")

# --------------------------------------------------------------------------------
# MOSTRAR ANÁLISIS
# --------------------------------------------------------------------------------
def display_analysis(df: pd.DataFrame):
    analysis_options = {
        "📋 Datos Procesados": "DatosProcesados",
        "👥 Análisis Demográfico": "Demografico",
        "📑 Análisis de Contratos": "Contratos",
        "💰 Análisis Salarial": "Salarial",
        "⏰ Análisis de Asistencia": "Asistencia",
        "📈 Análisis LME": "LME",
        "📉 Análisis de Ausentismo": "Ausentismo",
        "📊 Análisis de Causales": "Causales",
        "🔧 Análisis Integrados": "Integrados"
    }
    st.sidebar.markdown("### 📈 Tipo de Análisis")
    selected_analysis = st.sidebar.radio("Seleccione qué desea visualizar:", list(analysis_options.keys()))
    st.markdown(f'<h3 class="section-title">{selected_analysis}</h3>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        key = analysis_options[selected_analysis]

        # Secciones originales (DatosProcesados, Demografico, etc.)...
        # --------------------------------------------------------------------
        if key == "DatosProcesados":
            st.write("Visualización del DataFrame filtrado.")
            srch = st.text_input("🔍 Buscar en los datos:")
            if srch:
                disp_df = df[df.astype(str).apply(lambda x: x.str.contains(srch, case=False)).any(axis=1)]
            else:
                disp_df = df
            page_size = st.selectbox("Registros por página", [10, 20, 50, 100], index=0)
            total_pages = (len(disp_df) // page_size) + (1 if len(disp_df) % page_size else 0)
            page = st.slider("Página", 1, max(1,total_pages), 1)
            st.dataframe(disp_df.iloc[(page-1)*page_size : page*page_size])
            st.download_button(
                "📥 Descargar datos filtrados",
                data=disp_df.to_csv(index=False).encode("utf-8"),
                file_name="datos_filtrados.csv",
                mime="text/csv"
            )

        elif key == "Demografico":
            st.write("Análisis Demográfico")
            st.plotly_chart(demographic_analysis(df), use_container_width=True)
            if st.checkbox("Mapear columnas para análisis Demográfico"):
                req = {
                    "Edad": "Columna para Edad:",
                    "Género": "Columna para Género:",
                    "Nacionalidad": "Columna para Nacionalidad:",
                    "Antigüedad": "Columna para Antigüedad (años):"
                }
                mp = dynamic_column_mapping(df, req, "demografico")
                if len(mp) == len(req):
                    df2 = df.copy()
                    try:
                        df2["AgeGroup"] = pd.cut(
                            pd.to_numeric(df2[mp["Edad"]], errors="coerce"),
                            bins=[18,25,35,45,55,65,100],
                            labels=["18-24","25-34","35-44","45-54","55-64","65+"]
                        )
                    except:
                        st.error("Error al convertir edades.")
                    df2["Gender"] = df2[mp["Género"]]
                    df2["Nationality"] = df2[mp["Nacionalidad"]]
                    df2["TenureYears"] = pd.to_numeric(df2[mp["Antigüedad"]], errors="coerce")
                    st.plotly_chart(demographic_analysis(df2), use_container_width=True)
                else:
                    st.info("Complete el mapeo demográfico.")

        elif key == "Contratos":
            st.write("Análisis de Contratos")
            st.plotly_chart(contract_analysis(df), use_container_width=True)
            if st.checkbox("Mapear columnas para análisis de Contratos"):
                req = {
                    "ContractType": "Columna Tipo de Contrato:",
                    "Department": "Columna Departamento:"
                }
                mp = dynamic_column_mapping(df, req, "contratos")
                if len(mp) == 2:
                    df2 = df.rename(columns={
                        mp["ContractType"]: "ContractType",
                        mp["Department"]: "Department"
                    })
                    st.plotly_chart(contract_analysis(df2), use_container_width=True)
                else:
                    st.info("Complete el mapeo.")

        elif key == "Salarial":
            st.write("Análisis Salarial")
            st.plotly_chart(salary_analysis(df), use_container_width=True)
            if st.checkbox("Mapear columnas para análisis Salarial"):
                req = {
                    "Department": "Columna Departamento:",
                    "BaseSalary": "Columna Salario Base:"
                }
                mp = dynamic_column_mapping(df, req, "salarial")
                if len(mp) == 2:
                    df2 = df.rename(columns={
                        mp["Department"]: "Department",
                        mp["BaseSalary"]: "BaseSalary"
                    })
                    st.plotly_chart(salary_analysis(df2), use_container_width=True)
                else:
                    st.info("Complete el mapeo.")
            if st.checkbox("Realizar Convalidación de Licencias"):
                convalidacion_licencias(df)

        elif key == "Asistencia":
            st.write("Análisis de Asistencia")
            try:
                st.plotly_chart(attendance_analysis(df), use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")
            if st.checkbox("Mapear columnas para Asistencia"):
                req = {
                    "DaysWorked": "Columna Días Trabajados:",
                    "AbsenceDays": "Columna Días de Falta:",
                    "VacationDays": "Columna Días de Vacaciones:"
                }
                mp = dynamic_column_mapping(df, req, "asistencia")
                if len(mp) == 3:
                    df2 = df.rename(columns={
                        mp["DaysWorked"]: "DaysWorked",
                        mp["AbsenceDays"]: "AbsenceDays",
                        mp["VacationDays"]: "VacationDays"
                    })
                    st.plotly_chart(attendance_analysis(df2), use_container_width=True)
                else:
                    st.info("Complete el mapeo para Asistencia.")

        elif key == "LME":
            st.write("Análisis de Licencias Médicas (LME)")
            lme_options = ["Total LME", "Grupo Diagnóstico", "Duración Promedio"]
            lme_sel = st.selectbox("Seleccione el subanálisis:", lme_options)
            if lme_sel == "Total LME":
                pivot, fig = analyze_total_LME(df)
                st.dataframe(pivot)
                st.plotly_chart(fig, use_container_width=True)
            elif lme_sel == "Grupo Diagnóstico":
                pivot, fig = analyze_grupo_diagnostico_LME(df)
                st.dataframe(pivot)
                st.plotly_chart(fig, use_container_width=True)
            elif lme_sel == "Duración Promedio":
                dur, fig = analyze_duracion_LME(df)
                st.dataframe(dur)
                st.plotly_chart(fig, use_container_width=True)
            st.info("Si tus columnas difieren, ajusta en analisis_hr.py o añade un mapeo similar.")

        elif key == "Ausentismo":
            st.write("Análisis de Ausentismo")
            agg_df, figs, text = absenteeism_analysis(df)
            if agg_df is None:
                st.warning("No se detectaron columnas estándar de ausentismo.")
                return
            st.markdown(text)
            st.dataframe(agg_df)
            st.plotly_chart(figs[0], use_container_width=True)
            st.plotly_chart(figs[1], use_container_width=True)
            pie_opt = st.selectbox("Gráfico de pastel:", ["Absoluta","Porcentual"])
            st.plotly_chart(figs[2][pie_opt], use_container_width=True)

            st.markdown("### Comparativa de Períodos")
            periods = agg_df["Período"].unique().tolist()
            cA, cB = st.columns(2)
            with cA:
                p1 = st.selectbox("Período 1", periods)
            with cB:
                p2 = st.selectbox("Período 2", periods)
            if st.button("Comparar"):
                try:
                    comp_df, comp_fig, comp_text = absenteeism_comparison(agg_df, p1, p2)
                    st.dataframe(comp_df)
                    st.plotly_chart(comp_fig, use_container_width=True)
                    st.markdown(comp_text)
                except Exception as e:
                    st.error(f"Error: {e}")

        elif key == "Causales":
            st.write("Causales de Terminación")
            c_col = "causal de termino"
            if c_col not in df.columns:
                st.warning("No existe 'causal de termino'. Usa mapeo si tu columna se llama distinto.")
                req = {"Causal": "Columna para la causal de término:"}
                mp = dynamic_column_mapping(df, req, "causal")
                if len(mp) == 1:
                    c_col = mp["Causal"]
                else:
                    st.info("No se pudo mapear la columna.")
                    return
            data, (fpie, fbar) = causales_analysis(df, c_col)
            st.write(f"**Activos:** {data['Activos']}  |  **Inactivos:** {data['Inactivos']}")
            st.plotly_chart(fpie, use_container_width=True)
            st.plotly_chart(fbar, use_container_width=True)

        # ----------------------------------------------------------------------
        # NUEVA SECCIÓN: Análisis Integrados con mapeo dinámico
        # ----------------------------------------------------------------------
        elif key == "Integrados":
            st.write("Funciones desde integrar.py con mapeo dinámico opcional.")
            integrated_options = [
                "Horas Extras vs Sueldos",
                "Faltas vs Sueldo",
                "Antigüedad",
                "Dotación",
                "Composición Ausencias",
                "Empleados Activos (Corte)",
                "Faltas por Cargo y Dpto"
            ]
            choice = st.selectbox("Seleccione análisis integrado:", integrated_options)

            if choice == "Horas Extras vs Sueldos":
                st.write("Relación entre horas extra y sueldos.")
                # Diccionario de columnas requeridas
                req = {
                    "Periodo": "Columna para Período (YYYYMM):",
                    "HrsExt_Normales": "Columna para Horas Extras Normales:",
                    "HrsExt_Dobles": "Columna para Horas Extras Dobles:",
                    "HrsExt_215": "Columna para Horas Extras 2.15:",
                    "SueldoBrutoDiasTrab": "Columna para Sueldo Bruto Días Trabajados:"
                }
                if st.checkbox("Mapear columnas para 'Horas Extras vs Sueldos'"):
                    mp = dynamic_column_mapping(df, req, "horas_extras_sueldos")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["Periodo"]: "Periodo",
                            mp["HrsExt_Normales"]: "HrsExt_Normales",
                            mp["HrsExt_Dobles"]: "HrsExt_Dobles",
                            mp["HrsExt_215"]: "HrsExt_215",
                            mp["SueldoBrutoDiasTrab"]: "SueldoBrutoDiasTrab"
                        })
                        horas_extras_vs_sueldos(df2)
                    else:
                        st.info("Complete el mapeo para todas las columnas.")
                else:
                    horas_extras_vs_sueldos(df)

            elif choice == "Faltas vs Sueldo":
                st.write("Faltas vs. Sueldo efectivo vs. Sueldo contractual.")
                req = {
                    "Periodo": "Columna para Período (YYYYMM):",
                    "DiasFalta": "Columna para Días de Falta:",
                    "SueldoBrutoContractual": "Columna para Sueldo Bruto Contractual:",
                    "SueldoBrutoDiasTrab": "Columna para Sueldo Bruto Dias Trabajados:"
                }
                if st.checkbox("Mapear columnas para 'Faltas vs Sueldo'"):
                    mp = dynamic_column_mapping(df, req, "faltas_vs_sueldo")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["Periodo"]: "Periodo",
                            mp["DiasFalta"]: "DiasFalta",
                            mp["SueldoBrutoContractual"]: "SueldoBrutoContractual",
                            mp["SueldoBrutoDiasTrab"]: "SueldoBrutoDiasTrab"
                        })
                        faltas_vs_sueldo(df2)
                    else:
                        st.info("Complete el mapeo.")
                else:
                    faltas_vs_sueldo(df)

            elif choice == "Antigüedad":
                st.write("Distribución de antigüedad en meses.")
                req = {
                    "AntiguedadMes": "Columna para Antigüedad en Meses:",
                    "Rut": "Columna para Rut/Identificador:"
                }
                if st.checkbox("Mapear columnas para 'Antigüedad'"):
                    mp = dynamic_column_mapping(df, req, "antiguedad")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["AntiguedadMes"]: "AntiguedadMes",
                            mp["Rut"]: "Rut"
                        })
                        antiguedad(df2)
                    else:
                        st.info("Complete el mapeo.")
                else:
                    antiguedad(df)

            elif choice == "Dotación":
                st.write("Distribución de empleados por Período y Gerencia.")
                req = {
                    "Rut": "Columna para Rut/ID empleado:",
                    "Periodo": "Columna para Período (YYYYMM):",
                    "Gerencia": "Columna para Gerencia/Departamento:"
                }
                if st.checkbox("Mapear columnas para 'Dotación'"):
                    mp = dynamic_column_mapping(df, req, "dotacion")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["Rut"]: "Rut",
                            mp["Periodo"]: "Periodo",
                            mp["Gerencia"]: "Gerencia"
                        })
                        dotacion(df2)
                    else:
                        st.info("Complete el mapeo.")
                else:
                    dotacion(df)

            elif choice == "Composición Ausencias":
                st.write("Días trabajados, faltas, licencias, vacaciones, etc.")
                req = {
                    "Periodo": "Columna para Período (YYYYMM):",
                    "DiasTrabajados": "Columna para Días Trabajados:",
                    "DiasFalta": "Columna para Días de Falta:",
                    "DiasLicenciaNormales": "Columna para Licencias Normales:",
                    "DiasLicenciaMaternales": "Columna para Licencias Maternales:",
                    "DiasVacaciones": "Columna para Días de Vacaciones:"
                }
                if st.checkbox("Mapear columnas para 'Composición Ausencias'"):
                    mp = dynamic_column_mapping(df, req, "composicion_ausencias")
                    # Podemos renombrar sólo las que sí mapearon
                    rename_dict = {}
                    for col_key, col_name in mp.items():
                        rename_dict[col_name] = col_key
                    df2 = df.rename(columns=rename_dict)
                    composicion_ausencias(df2)
                else:
                    composicion_ausencias(df)

            elif choice == "Empleados Activos (Corte)":
                st.write("Muestra cuántos empleados siguen activos a lo largo del tiempo.")
                req = {
                    "FechaTerminoContrato": "Columna para Fecha de Término de Contrato (vacía si sigue activo):",
                    "Rut": "Columna para Rut/ID:",
                    "Periodo": "Columna para Período (YYYYMM):"
                }
                if st.checkbox("Mapear columnas para 'Empleados Activos'"):
                    mp = dynamic_column_mapping(df, req, "empleados_activos")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["FechaTerminoContrato"]: "FechaTerminoContrato",
                            mp["Rut"]: "Rut",
                            mp["Periodo"]: "Periodo"
                        })
                        empleados_activos(df2)
                    else:
                        st.info("Complete el mapeo.")
                else:
                    empleados_activos(df)

            elif choice == "Faltas por Cargo y Dpto":
                st.write("Visualiza faltas por cargo y gerencia.")
                req = {
                    "Cargo": "Columna para Cargo/Puesto:",
                    "Gerencia": "Columna para Gerencia/Departamento:",
                    "DiasFalta": "Columna para Días de Falta:"
                }
                if st.checkbox("Mapear columnas para 'Faltas por Cargo y Dpto'"):
                    mp = dynamic_column_mapping(df, req, "faltas_por_cargo")
                    if len(mp) == len(req):
                        df2 = df.rename(columns={
                            mp["Cargo"]: "Cargo",
                            mp["Gerencia"]: "Gerencia",
                            mp["DiasFalta"]: "DiasFalta"
                        })
                        faltas_por_cargo_y_departamento(df2)
                    else:
                        st.info("Complete el mapeo.")
                else:
                    faltas_por_cargo_y_departamento(df)

        st.markdown('</div>', unsafe_allow_html=True)

    # (Opcional) Sección de insights si deseas para cada sección
    if key not in ["DatosProcesados","Integrados"]:
        st.markdown('<h4 class="section-title">🔍 Insights Clave</h4>', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
        if key == "Demografico":
            st.markdown("- Distribución por género y edad ...")
        # Resto de insights ...
        st.markdown('</div>', unsafe_allow_html=True)


def run_dashboard():
    inject_css()
    display_header()
    init_session_state()

    # Nueva sidebar: devuelve la ruta local que ya se subió a S3
    data_path = setup_sidebar()

    if not data_path:
        st.info("Sube un archivo CSV o Excel para iniciar el análisis.")
        return

    try:
        with st.spinner("Procesando datos..."):
            df_loaded = cached_load_data(data_path)      # <─ lee desde la ruta
            if df_loaded is None or df_loaded.empty:
                st.error("No se pudo cargar el archivo o está vacío.")
                return

            st.session_state["df_original"] = df_loaded
            df_filtered = setup_period_filters(df_loaded)
            st.session_state["df_filtered"] = df_filtered

        if df_filtered.empty:
            st.error("No hay datos para el período / estado seleccionado.")
            return

        display_key_metrics(df_filtered)
        display_analysis(df_filtered)

    except Exception as e:
        st.error(f"Error al procesar los datos: {e}")


if __name__ == "__main__":
    run_dashboard()
