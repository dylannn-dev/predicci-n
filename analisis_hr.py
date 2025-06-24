# -*- coding: utf-8 -*-
"""
Análisis Integral de Datos de Recursos Humanos
Código combinado que incluye:
  - Estandarización de columnas mediante sinónimos
  - Normalización y mapeo de datos
  - Carga y preparación de datos (CSV o Excel)
  - Análisis: demográfico, contratos, salarial y asistencia
  - Generación de resumen integral y reporte en HTML/JSON
  - NUEVAS FUNCIONES: análisis de Licencias Médicas Electrónicas (LME)
  - NUEVA FUNCIÓN: análisis de Ausentismo (absenteeism_analysis)
  - NUEVA FUNCIÓN: comparativa de Ausentismo entre dos períodos (absenteeism_comparison)
Compatible con app.py para dashboard de RRHH
"""

# =============================================================================
# 1. Importación de librerías
# =============================================================================
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import unicodedata
import io
import os
# Configuración de visualización
plt.style.use('ggplot')
sns.set_theme(style="whitegrid")

# =============================================================================
# 2. Definición de sinónimos para la estandarización de nombres de columnas
# =============================================================================
STANDARD_COLUMN_SYNONYMS = {
    'ContractID': ['contrato'],
    'NationalID': ['rut'],
    'FullName': ['nombre completo'],
    'JobRole': ['cargo'],
    'ContractType': ['tipo de contrato', 'clasificación contrato'],
    'Department': ['gerencia', 'gerencia presupuesto', 'sub gerencia'],
    'BirthDate': ['fecha de nacimiento'],
    'Age': ['edad', 'edad al corte de mes'],
    'Gender': ['sexo'],
    'ContractStartDate': ['fecha de inicio contrato'],
    'ContractEndDate': ['fecha de término contrato'],
    'TenureMonths': ['antiguedad al corte de mes'],
    'Nationality': ['nación'],
    'RegularLeaveDays': ['días de licencia normales'],
    'MaternityLeaveDays': ['días de licencia maternales'],
    'SickLeaveDays': ['dias con licencia por accidente'],
    'PermissionDays': ['dias de permiso'],
    'AbsenceDays': ['días de falta'],
    'BaseSalary': ['sueldo bruto contractual'],
    'DaysWorked': ['días trabajados']
}

# =============================================================================
# 3. Funciones de normalización y estandarización
# =============================================================================
def normalize_string(s):
    """
    Normaliza un string: lo convierte a minúsculas, elimina espacios extremos y remueve acentos.
    """
    if not isinstance(s, str):
        s = str(s)
    s = s.lower().strip()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return s

def causales_analysis(df, causal_column="causal de termino"):
    """
    Análisis de Causales de Terminación:
    Cuenta cuántos empleados están activos e inactivos.
    Se asume que las personas activas tienen el valor "sin definir" en la columna indicada.
    
    Retorna:
      - Un diccionario con el conteo de empleados activos e inactivos.
      - Una tupla con dos figuras Plotly:
          * Un gráfico de pastel mostrando la distribución.
          * Un gráfico de barras mostrando los porcentajes.
    """
    if causal_column not in df.columns:
        raise ValueError(f"La columna '{causal_column}' no se encontró en el DataFrame.")
    
    # Normalizamos la columna para evitar discrepancias en mayúsculas/minúsculas o espacios
    df[causal_column] = df[causal_column].astype(str).str.lower().str.strip()
    
    activos = (df[causal_column] == 'sin definir').sum()
    inactivos = (df[causal_column] != 'sin definir').sum()
    total = activos + inactivos
    data = {"Activos": activos, "Inactivos": inactivos}
    
    # Gráfico de pastel
    fig_pie = px.pie(
        names=list(data.keys()),
        values=list(data.values()),
        title="Distribución de Empleados (Causales)",
        labels={"names": "Estado", "values": "Cantidad"}
    )
    
    # Gráfico de barras con porcentajes
    percentages = {k: (v / total * 100 if total > 0 else 0) for k, v in data.items()}
    fig_bar = px.bar(
        x=list(percentages.keys()),
        y=list(percentages.values()),
        title="Porcentaje de Empleados por Estado",
        labels={"x": "Estado", "y": "Porcentaje (%)"}
    )
    
    return data, (fig_pie, fig_bar)

def standardize_column_names(df):
    """
    Revisa cada columna del DataFrame y, si su nombre (normalizado) coincide con alguno
    de los sinónimos definidos, la renombra a la clave estándar.
    """
    new_columns = {}
    for col in df.columns:
        norm_col = normalize_string(col)
        found = False
        for standard, synonyms in STANDARD_COLUMN_SYNONYMS.items():
            synonyms_normalized = [normalize_string(s) for s in synonyms]
            if norm_col in synonyms_normalized:
                new_columns[col] = standard
                found = True
                break
        if not found:
            new_columns[col] = col
    return df.rename(columns=new_columns)

def normalize_and_map_data(df):
    """
    Aplica mapeo de valores y normaliza columnas numéricas específicas.
    
    Mapeo:
      - En la columna 'Gender': 'F' se mapea a 'Femenino' y 'M' a 'Masculino'.
    
    Normalización (min-max) para columnas de asistencia:
      - AbsenceDays, SickLeaveDays, RegularLeaveDays, MaternityLeaveDays, PermissionDays
    """
    gender_mapping = {'F': 'Femenino', 'M': 'Masculino'}
    if 'Gender' in df.columns:
        df['Gender'] = df['Gender'].map(gender_mapping).fillna(df['Gender'])
    
    cols_to_normalize = ['AbsenceDays', 'SickLeaveDays', 'RegularLeaveDays', 'MaternityLeaveDays', 'PermissionDays']
    for col in cols_to_normalize:
        if col in df.columns:
            min_val = df[col].min()
            max_val = df[col].max()
            if max_val - min_val != 0:
                df[f'Normalized_{col}'] = (df[col] - min_val) / (max_val - min_val)
            else:
                df[f'Normalized_{col}'] = 0.0
    return df

# =============================================================================
# 4. Función de carga y preparación de datos
# =============================================================================
def load_hr_data(file_input):
    """
    Carga datos desde CSV o Excel, estandariza nombres de columnas y normaliza datos
    """
    try:
        if hasattr(file_input, 'name'):
            file_name = file_input.name
        else:
            file_name = str(file_input)
        
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_input, delimiter=';', decimal=',', thousands='.')
        elif file_name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file_input)
        else:
            raise ValueError("Formato no soportado")
        
        # Estandarizar nombres de columnas
        df = standardize_column_names(df)
        # Eliminar columnas duplicadas (se conserva la primera aparición)
        df = df.loc[:, ~df.columns.duplicated()]
        
        if 'Faena' in df.columns:
            df['Faena'] = df['Faena'].fillna('').astype(str)
        
        date_cols = ['BirthDate', 'ContractStartDate', 'ContractEndDate']
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
        
        if 'TenureMonths' in df.columns:
            df['TenureYears'] = df['TenureMonths'] / 12
        
        if 'Age' in df.columns:
            age_bins = [18, 25, 35, 45, 55, 65, 100]
            age_labels = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
            df['AgeGroup'] = pd.cut(df['Age'], bins=age_bins, labels=age_labels, right=False)
        
        df = normalize_and_map_data(df)
        
        return df
    except Exception as e:
        print(f"Error cargando datos: {str(e)}")
        return None

# =============================================================================
# 5. Funciones de análisis (demográfico, contratos, salarial, asistencia)
# =============================================================================
def demographic_analysis(df):
    """
    Análisis demográfico: Distribución de edad, género, nacionalidad y antigüedad.
    Retorna una figura Plotly.
    """
    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{'type': 'bar'}, {'type': 'pie'}],
               [{'type': 'bar'}, {'type': 'bar'}]],
        subplot_titles=(
            'Distribución por Edad',
            'Distribución por Género',
            'Distribución por Nacionalidad',
            'Antigüedad Promedio por Género'
        )
    )
    if 'AgeGroup' in df.columns:
        age_dist = df['AgeGroup'].value_counts().sort_index()
        fig.add_trace(go.Bar(x=age_dist.index.astype(str), y=age_dist.values, name='Edad'), row=1, col=1)
    if 'Gender' in df.columns:
        gender_dist = df['Gender'].value_counts()
        fig.add_trace(go.Pie(labels=gender_dist.index, values=gender_dist.values, name='Género'), row=1, col=2)
    if 'Nationality' in df.columns:
        # Convertimos el conteo a porcentaje
        nat_pct = df['Nationality'].value_counts(normalize=True) * 100
        fig.add_trace(go.Bar(x=nat_pct.index.astype(str), y=nat_pct.values, name='Nacionalidad (%)'), row=2, col=1)
    if 'Gender' in df.columns and 'TenureYears' in df.columns:
        tenure_by_gender = df.groupby('Gender')['TenureYears'].mean()
        fig.add_trace(go.Bar(x=tenure_by_gender.index, y=tenure_by_gender.values, name='Antigüedad'), row=2, col=2)
    fig.update_layout(height=800, showlegend=False, title_text="Análisis Demográfico")
    return fig

def contract_analysis(df):
    """
    Análisis de contratos.
    """
    if 'ContractType' not in df.columns or 'Department' not in df.columns:
        return go.Figure().update_layout(title="Datos insuficientes para análisis de contratos")
    
    contract_dist = df['ContractType'].value_counts()
    contract_dept = pd.crosstab(df['Department'], df['ContractType'])
    
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{'type': 'pie'}, {'type': 'bar'}]],
        subplot_titles=('Distribución de Contratos', 'Contratos por Departamento')
    )
    fig.add_trace(go.Pie(labels=contract_dist.index, values=contract_dist.values), row=1, col=1)
    for contract in contract_dept.columns:
        fig.add_trace(go.Bar(x=contract_dept.index.astype(str), y=contract_dept[contract], name=contract), row=1, col=2)
    fig.update_layout(barmode='stack', title_text="Análisis de Contratos")
    return fig

def salary_analysis(df):
    """
    Análisis salarial modificado para mostrar la distribución en porcentajes por Departamento.
    """
    try:
        if 'Department' not in df.columns or 'BaseSalary' not in df.columns:
            raise ValueError("Columnas necesarias no encontradas")
        df_clean = df.dropna(subset=['Department', 'BaseSalary']).copy()
        bins = [0, 500_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000, float('inf')]
        labels = ['<500k', '500k-1M', '1M-1.5M', '1.5M-2M', '2M-3M', '3M+']
        df_clean['SalaryBand'] = pd.cut(df_clean['BaseSalary'], bins=bins, labels=labels, include_lowest=True)
        df_clean = df_clean.dropna(subset=['SalaryBand'])
        if df_clean.empty:
            raise ValueError("No hay datos válidos para generar el gráfico")
        
        # Agrupamos por Departamento y SalaryBand y contamos la cantidad de empleados
        df_counts = df_clean.groupby(['Department', 'SalaryBand']).size().reset_index(name='count')
        # Calculamos el porcentaje respecto al total de empleados en cada departamento
        df_counts['perc'] = df_counts.groupby('Department')['count'].transform(lambda x: x / x.sum() * 100)
        
        # Creamos un gráfico de barras apiladas para mostrar los porcentajes
        fig = px.bar(
            df_counts,
            x='Department',
            y='perc',
            color='SalaryBand',
            title='Distribución Salarial por Departamento (Porcentajes)',
            labels={'perc': 'Porcentaje (%)'}
        )
        fig.update_layout(barmode='stack', yaxis=dict(ticksuffix='%'))
        return fig
    except Exception as e:
        print(f"Error en análisis salarial: {str(e)}")
        return px.scatter(title="Error en datos salariales")


def attendance_analysis(df):
    """
    Análisis de asistencia.
    """
    try:
        leave_columns = ['RegularLeaveDays', 'MaternityLeaveDays', 'SickLeaveDays', 'PermissionDays']
        existing_leave = [col for col in leave_columns if col in df.columns]
        if existing_leave:
            df['TotalLeave'] = df[existing_leave].sum(axis=1)
        else:
            df['TotalLeave'] = 0

        if 'VacationDays' not in df.columns:
            df['VacationDays'] = 0

        required = ['Department', 'DaysWorked', 'AbsenceDays']
        for col in required:
            if col not in df.columns:
                raise ValueError(f"No se encontró la columna requerida: {col}")
        
        attendance_dept = df.groupby('Department')[['DaysWorked', 'AbsenceDays', 'VacationDays']].mean().reset_index()
        fig = px.bar(attendance_dept, x='Department', y=['DaysWorked', 'AbsenceDays', 'VacationDays'],
                     barmode='group', title='Patrones de Asistencia por Departamento',
                     labels={'value': 'Días', 'variable': 'Tipo'})
        return fig
    except Exception as e:
        print(f"Error en análisis de asistencia: {str(e)}")
        return px.scatter(title="Error en datos de asistencia")

# =============================================================================
# 5bis. Funciones para análisis de Licencias Médicas Electrónicas (LME)
# =============================================================================
def analyze_total_LME(df):
    total = df.groupby(['Año', 'Tipo de Licencia'])['Cantidad'].sum().reset_index()
    pivot = total.pivot(index='Tipo de Licencia', columns='Año', values='Cantidad').reset_index()
    if 2023 in pivot.columns and 2024 in pivot.columns:
        pivot['Variación %'] = ((pivot[2024] - pivot[2023]) / pivot[2023]) * 100
    fig = px.bar(total, x='Tipo de Licencia', y='Cantidad', color='Año', barmode='group',
                 title="LME emitidas por Tipo y Año")
    return pivot, fig

def analyze_LME_por_seguro(df):
    df_tipo1 = df[df['Tipo de Licencia'] == "Enfermedad o Accidente Común"]
    seguro = df_tipo1.groupby(['Seguro', 'Año'])['Cantidad'].sum().reset_index()
    pivot = seguro.pivot(index='Seguro', columns='Año', values='Cantidad').reset_index()
    if 2023 in pivot.columns and 2024 in pivot.columns:
        pivot['Variación %'] = ((pivot[2024] - pivot[2023]) / pivot[2023]) * 100
    fig = px.bar(seguro, x='Seguro', y='Cantidad', color='Año', barmode='group',
                 title="LME 'Enfermedad o Accidente Común' por Seguro")
    return pivot, fig

def analyze_trabajadores_LME(df):
    if 'TrabajadorID' not in df.columns:
        return None, None
    unique = df[df['Tipo de Licencia'] == "Enfermedad o Accidente Común"]\
                .groupby(['Seguro', 'Año'])['TrabajadorID'].nunique().reset_index()
    pivot = unique.pivot(index='Seguro', columns='Año', values='TrabajadorID').reset_index()
    if 2023 in pivot.columns and 2024 in pivot.columns:
        pivot['Variación %'] = ((pivot[2024] - pivot[2023]) / pivot[2023]) * 100
    fig = px.bar(unique, x='Seguro', y='TrabajadorID', color='Año', barmode='group',
                 title="Trabajadores Únicos por Seguro")
    return pivot, fig

def analyze_estado_resolucion_LME(df):
    estado = df.groupby(['Año', 'Estado Resolución', 'Seguro'])['Cantidad'].sum().reset_index()
    total_por_seguro = df.groupby(['Año', 'Seguro'])['Cantidad'].sum().reset_index().rename(columns={'Cantidad':'Total'})
    rechazados = df[df['Estado Resolución'] == "Rechazase"].groupby(['Año', 'Seguro'])['Cantidad'].sum().reset_index().rename(columns={'Cantidad':'Rechazados'})
    tasa = pd.merge(total_por_seguro, rechazados, on=['Año', 'Seguro'], how='left')
    tasa['Rechazados'] = tasa['Rechazados'].fillna(0)
    tasa['Tasa Rechazo (%)'] = (tasa['Rechazados'] / tasa['Total']) * 100
    fig = px.bar(tasa, x='Seguro', y='Tasa Rechazo (%)', color='Año', barmode='group',
                 title="Tasa de Rechazo por Seguro")
    return estado, fig

def analyze_grupo_diagnostico_LME(df):
    grupo = df.groupby(['Año', 'Grupo Diagnostico'])['Cantidad'].sum().reset_index()
    pivot = grupo.pivot(index='Grupo Diagnostico', columns='Año', values='Cantidad').reset_index()
    if 2023 in pivot.columns and 2024 in pivot.columns:
        pivot['Variación %'] = ((pivot[2024] - pivot[2023]) / pivot[2023]) * 100
    fig = px.bar(grupo, x='Grupo Diagnostico', y='Cantidad', color='Año', barmode='group',
                 title="LME por Grupo Diagnóstico")
    return pivot, fig

def analyze_duracion_LME(df):
    duracion = df.groupby(['Año', 'Grupo Diagnostico'])['DiasAutorizados'].mean().reset_index()
    fig = px.bar(duracion, x='Grupo Diagnostico', y='DiasAutorizados', color='Año', barmode='group',
                 title="Duración Promedio de LME por Grupo Diagnóstico")
    return duracion, fig

# =============================================================================
# NUEVA FUNCIÓN: Análisis de Ausentismo
# =============================================================================
def absenteeism_analysis(df):
    """
    Análisis de Ausentismo mejorado:
      - Agrega días de ausentismo por 'Período' (YYYYMM) y calcula porcentajes.
      - Formatea el período a "Mes Año" (en español).
      - Genera:
         * Un gráfico de barras apiladas con los días de ausencia por tipo.
         * Un gráfico de línea con la evolución total de ausentismo.
         * Dos gráficos de pastel (uno absoluto y otro porcentual) para el período más reciente.
      - Retorna la tabla agregada, una tupla de figuras (barras, línea, diccionario de pastel) y un texto resumen.
    """

    if 'Período' not in df.columns:
        if 'ContractStartDate' in df.columns:
            df['Período'] = df['ContractStartDate'].dt.strftime("%Y%m")
        else:
            raise ValueError("No se encontró la columna 'Período' ni 'ContractStartDate' para el análisis de ausentismo.")
    
    absence_cols = []
    for col in ['AbsenceDays', 'SickLeaveDays', 'RegularLeaveDays', 'MaternityLeaveDays', 'PermissionDays']:
        if col in df.columns:
            absence_cols.append(col)
    if not absence_cols:
        return None, (None, None, {}), "No se encontraron columnas de ausentismo."

    agg_df = df.groupby('Período')[absence_cols].sum().reset_index()
    agg_df['TotalAusentismo'] = agg_df[absence_cols].sum(axis=1)

    for col in absence_cols:
        agg_df[f"{col}_pct"] = (agg_df[col] / agg_df['TotalAusentismo']) * 100

    month_map = {
        "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
        "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
        "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
    }

    def format_period(yyyymm):
        if len(yyyymm) == 6:
            year = yyyymm[:4]
            month = yyyymm[4:]
            return f"{month_map.get(month, month)} {year}"
        else:
            return yyyymm

    agg_df['Período_formateado'] = agg_df['Período'].apply(format_period)

    # Gráfico de barras apiladas
    df_melted = agg_df.melt(
        id_vars=['Período_formateado', 'TotalAusentismo'],
        value_vars=absence_cols,
        var_name='TipoAusencia',
        value_name='DiasAusencia'
    )
    fig_stacked = px.bar(
        df_melted,
        x='Período_formateado',
        y='DiasAusencia',
        color='TipoAusencia',
        title="Días de Ausentismo por Tipo (Barras Apiladas)",
        labels={'DiasAusencia': 'Días de Ausencia', 'Período_formateado': 'Período'},
    )
    fig_stacked.update_layout(xaxis_title="Período", yaxis_title="Días de Ausencia", barmode='stack')

    # Gráfico de línea
    fig_total_line = px.line(
        agg_df,
        x='Período_formateado',
        y='TotalAusentismo',
        markers=True,
        title="Evolución del Total de Ausentismo",
        labels={'TotalAusentismo': 'Días de Ausentismo', 'Período_formateado': 'Período'}
    )
    fig_total_line.update_layout(xaxis_title="Período", yaxis_title="Días de Ausentismo")

    # Gráficos de pastel para el período más reciente
    selected_row = agg_df.iloc[-1]
    pie_data_absolute = {col: selected_row[col] for col in absence_cols}
    pie_data_percent = {col: selected_row[f"{col}_pct"] for col in absence_cols}

    fig_pie_absolute = px.pie(
        names=list(pie_data_absolute.keys()),
        values=list(pie_data_absolute.values()),
        title=f"Distribución Absoluta en {selected_row['Período_formateado']}"
    )
    fig_pie_percent = px.pie(
        names=list(pie_data_percent.keys()),
        values=list(pie_data_percent.values()),
        title=f"Distribución Porcentual en {selected_row['Período_formateado']}"
    )
    pie_dict = {"Absoluta": fig_pie_absolute, "Porcentual": fig_pie_percent}

    total_ausentismo = agg_df['TotalAusentismo'].sum()
    idx_max = agg_df['TotalAusentismo'].idxmax()
    idx_min = agg_df['TotalAusentismo'].idxmin()
    periodo_max = agg_df.loc[idx_max, 'Período_formateado']
    valor_max = agg_df.loc[idx_max, 'TotalAusentismo']
    periodo_min = agg_df.loc[idx_min, 'Período_formateado']
    valor_min = agg_df.loc[idx_min, 'TotalAusentismo']

    resumen_global = f"""
**Resumen Global de Ausentismo**  
- **Total de días de ausentismo:** {total_ausentismo:.0f}  
- **Período con mayor ausentismo:** {periodo_max} ({valor_max:.0f} días)  
- **Período con menor ausentismo:** {periodo_min} ({valor_min:.0f} días)
    """
    predominant_type = max(pie_data_percent, key=pie_data_percent.get)
    predominant_percentage = pie_data_percent[predominant_type]
    resumen_periodo = f"En {selected_row['Período_formateado']}, el tipo de ausencia predominante fue **{predominant_type}** con un **{predominant_percentage:.1f}%**."
    texto_resumen = resumen_global + "\n" + resumen_periodo

    return agg_df, (fig_stacked, fig_total_line, pie_dict), texto_resumen

# =============================================================================
# NUEVA FUNCIÓN: Comparativa de Ausentismo entre dos períodos
# =============================================================================
def absenteeism_comparison(agg_df, period1, period2):
    """
    Compara dos períodos de ausentismo a partir del DataFrame agregado (agg_df) generado por absenteeism_analysis.
    period1 y period2 deben ser cadenas en formato YYYYMM.
    
    Retorna:
      - DataFrame comparativo con los valores absolutos y porcentuales por tipo.
      - Figura comparativa (barras agrupadas) que muestra los días de ausencia por tipo para ambos períodos.
      - Texto resumen que indica las principales diferencias estadísticas.
    """
    comp1 = agg_df[agg_df['Período'] == period1]
    comp2 = agg_df[agg_df['Período'] == period2]
    
    if comp1.empty or comp2.empty:
        raise ValueError("Uno o ambos de los períodos seleccionados no existen en los datos.")
    
    comp1 = comp1.iloc[0]
    comp2 = comp2.iloc[0]
    
    comparison_data = []
    absence_cols = [col for col in ['AbsenceDays', 'SickLeaveDays', 'RegularLeaveDays', 'MaternityLeaveDays', 'PermissionDays'] if col in agg_df.columns]
    for col in absence_cols:
        val1 = comp1[col]
        val2 = comp2[col]
        pct1 = comp1[f"{col}_pct"]
        pct2 = comp2[f"{col}_pct"]
        diff = val2 - val1
        diff_pct = ((val2 - val1) / val1 * 100) if val1 != 0 else None
        comparison_data.append({
            "TipoAusencia": col,
            f"{period1}": val1,
            f"{period2}": val2,
            "Diferencia": diff,
            "Diferencia (%)": diff_pct,
            f"{period1}_pct": pct1,
            f"{period2}_pct": pct2,
        })
    comp_df = pd.DataFrame(comparison_data)
    
    comp_fig = px.bar(comp_df, x="TipoAusencia", y=[f"{period1}", f"{period2}"],
                      barmode="group", title="Comparativa de Ausentismo por Tipo",
                      labels={"value": "Días de Ausentismo", "variable": "Período"})
    
    total1 = comp1['TotalAusentismo']
    total2 = comp2['TotalAusentismo']
    total_diff = total2 - total1
    total_diff_pct = ((total2 - total1) / total1 * 100) if total1 != 0 else None
    resumen = f"Comparación entre {comp1['Período_formateado']} y {comp2['Período_formateado']}:\n"
    resumen += f"- Total de ausentismo en {comp1['Período_formateado']}: {total1:.0f} días.\n"
    resumen += f"- Total de ausentismo en {comp2['Período_formateado']}: {total2:.0f} días.\n"
    resumen += f"- Diferencia total: {total_diff:.0f} días ({total_diff_pct:.1f}% {'aumento' if total_diff_pct and total_diff_pct>0 else 'disminución'}).\n"
    for item in comparison_data:
        diff_pct = item["Diferencia (%)"]
        if diff_pct is not None and abs(diff_pct) > 10:
            resumen += f"- En {item['TipoAusencia']}, se observó una diferencia de {diff_pct:.1f}%.\n"
    
    return comp_df, comp_fig, resumen

# =============================================================================
# 6. Funciones adicionales para análisis integral y generación de reportes
# =============================================================================
def generate_hr_overview(df):
    overview = {}
    overview['total_employees'] = len(df)
    if 'Gender' in df.columns:
        gender_dist = df['Gender'].value_counts()
        overview['gender_distribution'] = gender_dist.to_dict()
    if 'TenureYears' in df.columns:
        overview['avg_tenure'] = df['TenureYears'].mean()
    if 'BaseSalary' in df.columns:
        overview['avg_salary'] = df['BaseSalary'].mean()
    if 'Age' in df.columns:
        overview['avg_age'] = df['Age'].mean()
    if 'Department' in df.columns:
        top_depts = df['Department'].value_counts().head(3)
        overview['top_departments'] = top_depts.to_dict()
    if 'ContractType' in df.columns:
        contract_dist = df['ContractType'].value_counts()
        overview['contract_distribution'] = contract_dist.to_dict()
    if 'DaysWorked' in df.columns and 'AbsenceDays' in df.columns:
        total_worked = df['DaysWorked'].sum()
        total_absence = df['AbsenceDays'].sum()
        overview['attendance_ratio'] = total_worked / (total_worked + total_absence) if (total_worked + total_absence) != 0 else None
    return overview

def analyze_hr_data(df):
    results = {}
    results['overview'] = generate_hr_overview(df)
    results['demographic'] = demographic_analysis(df)
    results['contracts'] = contract_analysis(df)
    results['salary'] = salary_analysis(df)
    results['attendance'] = attendance_analysis(df)
    return results

def export_analysis_report(df, results, format='html'):
    try:
        if format == 'html':
            html_report = io.StringIO()
            html_report.write("<html><head>")
            html_report.write("<title>Análisis de RRHH</title>")
            html_report.write("<style>")
            html_report.write("body {font-family: 'Segoe UI', sans-serif; padding: 20px;}")
            html_report.write(".header {background-color: #28a745; color: white; padding: 20px; text-align: center;}")
            html_report.write(".section {margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px;}")
            html_report.write("</style></head><body>")
            html_report.write("<div class='header'><h1>Informe de RRHH</h1>")
            html_report.write(f"<p>Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p></div>")
            html_report.write("<div class='section'><h2>Resumen General</h2>")
            overview = results.get('overview', {})
            for key, value in overview.items():
                html_report.write(f"<p><strong>{key.replace('_', ' ').capitalize()}:</strong> {value}</p>")
            html_report.write("</div>")
            html_report.write("</body></html>")
            return html_report.getvalue()
        elif format == 'json':
            import json
            return json.dumps(results.get('overview', {}))
        else:
            raise ValueError(f"Formato {format} no soportado")
    except Exception as e:
        print(f"Error al exportar informe: {str(e)}")
        return f"Error al generar informe: {str(e)}"

# =============================================================================
# 7. Ejecución principal para pruebas locales
# =============================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prueba local de analisis_hr")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Ruta al archivo de datos (CSV o Excel) a procesar"
    )
    args = parser.parse_args()

    df = load_hr_data(args.input)
    if df is not None:
        print("Datos cargados y procesados correctamente.")
        results = analyze_hr_data(df)

        print("\nResumen General:")
        for key, value in results['overview'].items():
            print(f"{key}: {value}")

        # Mostrar gráficas si corres en un entorno que lo soporte
        try:
            results['demographic'].show()
            results['contracts'].show()
            results['salary'].show()
            results['attendance'].show()
        except Exception:
            pass

        # Exportar reporte
        reporte_html = export_analysis_report(df, results, format='html')
        out_html = f"reporte_rrhh_{os.path.basename(args.input).split('.')[0]}.html"
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(reporte_html)
        df.to_csv(f"datos_procesados_{os.path.basename(args.input)}.csv", index=False)

        print(f"\nReporte generado: '{out_html}'")
        print(f"Datos procesados guardados en 'datos_procesados_{os.path.basename(args.input)}.csv'")
    else:
        print("Error: No se pudo cargar el archivo de datos")

"""
arn:aws:s3:us-east-2:715841338590:accesspoint/acceso-betel
"""