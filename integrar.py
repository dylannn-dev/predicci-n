# analysis.py
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import pandas as pd

def horas_extras_vs_sueldos(df: pd.DataFrame):
    st.header("Análisis: Horas Extras vs. Sueldos")
    required_cols = ["Periodo", "HrsExt_Normales", "HrsExt_Dobles", "HrsExt_215", "SueldoBrutoDiasTrab"]
    if not all(col in df.columns for col in required_cols):
        st.warning(f"Faltan columnas: {set(required_cols) - set(df.columns)}")
        return

    group_data = df.groupby("Periodo").agg({
        "HrsExt_Normales": "sum",
        "HrsExt_Dobles": "sum",
        "HrsExt_215": "sum",
        "SueldoBrutoDiasTrab": "sum"
    }).reset_index()

    st.write("Resumen por Período")
    st.dataframe(group_data)

    fig_bar = px.bar(
        group_data,
        x="Periodo",
        y="HrsExt_Normales",
        title="Horas Extras Normales por Período",
        labels={"HrsExt_Normales": "Horas Extras Normales"}
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    fig_line = px.line(
        group_data,
        x="Periodo",
        y="SueldoBrutoDiasTrab",
        title="Sueldo Bruto (Días Trabajados) por Período",
        labels={"SueldoBrutoDiasTrab": "Sueldo Bruto"}
    )
    st.plotly_chart(fig_line, use_container_width=True)

def faltas_vs_sueldo(df: pd.DataFrame):
    st.header("Análisis: Faltas vs. Sueldo")
    required_cols = ["Periodo", "DiasFalta", "SueldoBrutoContractual", "SueldoBrutoDiasTrab"]
    if not all(col in df.columns for col in required_cols):
        st.warning(f"Faltan columnas: {set(required_cols) - set(df.columns)}")
        return

    group_data = df.groupby("Periodo").agg({
        "DiasFalta": "sum",
        "SueldoBrutoContractual": "sum",
        "SueldoBrutoDiasTrab": "sum"
    }).reset_index()

    group_data["DescuentoTotal"] = group_data["SueldoBrutoContractual"] - group_data["SueldoBrutoDiasTrab"]
    group_data["DescuentoPromedioPorDiaFalta"] = np.where(
        group_data["DiasFalta"] > 0,
        group_data["DescuentoTotal"] / group_data["DiasFalta"],
        0
    )

    st.write("Resumen por Período")
    st.dataframe(group_data)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=group_data["Periodo"],
        y=group_data["SueldoBrutoContractual"],
        mode="lines+markers",
        name="Sueldo Contractual"
    ))
    fig.add_trace(go.Scatter(
        x=group_data["Periodo"],
        y=group_data["SueldoBrutoDiasTrab"],
        mode="lines+markers",
        name="Sueldo Efectivo"
    ))
    fig.update_layout(
        title="Comparación de Sueldo Contractual vs. Sueldo Efectivo",
        xaxis_title="Período",
        yaxis_title="Sueldo"
    )
    st.plotly_chart(fig, use_container_width=True)

def antiguedad(df: pd.DataFrame):
    st.header("Análisis: Antigüedad de Empleados")
    if "AntiguedadMes" not in df.columns:
        st.warning("No se encontró la columna 'AntiguedadMes'.")
        return
    if "Rut" not in df.columns:
        st.warning("No se encontró la columna 'Rut'.")
        return

    bins = [0, 1, 3, 5, 10, 20, 50]
    labels = ["0-1", "1-3", "3-5", "5-10", "10-20", "20+"]
    df["RangoAntiguedad"] = pd.cut(df["AntiguedadMes"], bins=bins, labels=labels, right=False)
    count_antiguedad = df.groupby("RangoAntiguedad")["Rut"].nunique().reset_index(name="NumEmpleados")

    st.write("Distribución de empleados por rango de antigüedad")
    st.dataframe(count_antiguedad)

    fig_pie = px.pie(
        count_antiguedad,
        names="RangoAntiguedad",
        values="NumEmpleados",
        title="Distribución de Antigüedad"
    )
    st.plotly_chart(fig_pie, use_container_width=True)

def dotacion(df: pd.DataFrame):
    st.header("Análisis: Dotación")
    needed_cols = ["Rut", "Periodo", "Gerencia"]
    missing = [col for col in needed_cols if col not in df.columns]
    if missing:
        st.warning(f"Faltan columnas para este análisis de dotación: {missing}")
        return

    dotacion_total = df["Rut"].nunique()
    st.write(f"**Dotación total:** {dotacion_total} empleados únicos.")

    dotacion_por_periodo_depto = (
        df.groupby(["Periodo", "Gerencia"])["Rut"]
        .nunique()
        .reset_index(name="NumEmpleados")
    )

    st.subheader("Distribución de empleados por Período y Departamento")
    st.dataframe(dotacion_por_periodo_depto)

    fig_bar = px.bar(
        dotacion_por_periodo_depto,
        x="Periodo",
        y="NumEmpleados",
        color="Gerencia",
        barmode="group",
        title="Cantidad de Empleados por Año-Mes y Departamento",
        labels={"NumEmpleados": "Número de Empleados"}
    )
    st.plotly_chart(fig_bar, use_container_width=True)

def composicion_ausencias(df: pd.DataFrame):
    st.header("Análisis: Composición de Ausencias")
    ausencias_cols = [
        "DiasTrabajados",
        "DiasFalta",
        "DiasLicenciaNormales",
        "DiasLicenciaMaternales",
        "DiasVacaciones"
    ]
    ausencias_cols = [col for col in ausencias_cols if col in df.columns]

    if len(ausencias_cols) > 1 and "Periodo" in df.columns:
        comp_ausencias = df.groupby("Periodo")[ausencias_cols].sum().reset_index()
        st.write("Resumen de Ausencias por Período")
        st.dataframe(comp_ausencias)

        fig_area = go.Figure()
        for col in ausencias_cols:
            fig_area.add_trace(go.Scatter(
                x=comp_ausencias["Periodo"],
                y=comp_ausencias[col],
                mode="lines",
                stackgroup="one",
                name=col
            ))
        fig_area.update_layout(
            title="Composición de Ausencias",
            xaxis_title="Período",
            yaxis_title="Días"
        )
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.warning("No se encontraron las columnas de ausencias requeridas o la columna 'Periodo'.")

def empleados_activos(df: pd.DataFrame):
    st.header("Análisis: Empleados Activos (Corte)")
    if "FechaTerminoContrato" not in df.columns:
        st.warning("La columna 'FechaTerminoContrato' no está presente en el DataFrame.")
        return
    if "Rut" not in df.columns or "Periodo" not in df.columns:
        st.warning("Falta la columna 'Rut' o 'Periodo' para este análisis.")
        return

    df_activos = df[df["FechaTerminoContrato"].isna()]
    activos_por_periodo = (
        df_activos.groupby("Periodo")["Rut"]
        .nunique()
        .reset_index(name="NumEmpleadosActivos")
    )

    st.write("Empleados activos por Período")
    st.dataframe(activos_por_periodo)

    fig_line_activos = px.line(
        activos_por_periodo,
        x="Periodo",
        y="NumEmpleadosActivos",
        title="Empleados Activos a lo largo del tiempo",
        labels={"NumEmpleadosActivos": "Número de Empleados Activos"}
    )
    st.plotly_chart(fig_line_activos, use_container_width=True)

def faltas_por_cargo_y_departamento(df: pd.DataFrame):
    st.header("Análisis: Faltas por Cargo y Departamento")
    needed_cols = ["Cargo", "Gerencia", "DiasFalta"]
    missing_cols = [col for col in needed_cols if col not in df.columns]
    if missing_cols:
        st.warning(f"Faltan columnas para este análisis: {missing_cols}")
        return

    faltas_por_cargo_depto = (
        df.groupby(["Cargo", "Gerencia"])["DiasFalta"]
        .sum()
        .reset_index()
    )

    st.subheader("Tabla de Faltas por Cargo y Gerencia")
    st.dataframe(faltas_por_cargo_depto)

    fig_faltas = px.bar(
        faltas_por_cargo_depto,
        x="Cargo",
        y="DiasFalta",
        color="Gerencia",
        barmode="group",
        title="Faltas (Días) por Cargo y Departamento",
        labels={"DiasFalta": "Total Días de Falta"}
    )
    st.plotly_chart(fig_faltas, use_container_width=True)