#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VariomeDB - Plataforma de Análisis de Variantes Genéticas
===========================================================
Versión: 2.0
Fecha: 12/03/2026
Autor: Francisco Cercadillo
Repositorio: https://github.com/fcercadillo/pi-cercadillo

DESCRIPCIÓN GENERAL:
--------------------
VariomeDB es una aplicación web desarrollada en Python/Streamlit para la gestión,
análisis y visualización de variantes genéticas provenientes de secuenciación
masiva (NGS). La plataforma permite la carga estructurada de pacientes, consultas
avanzadas con filtros por paneles de genes, creación de paneles personalizados,
y generación automatizada de reportes clínicos en formato Word.

CARACTERÍSTICAS PRINCIPALES:
-----------------------------
1. Gestión de Pacientes:
   - Carga de pacientes desde sistema de archivos
   - Validación de metadata completa (datos demográficos, clínicos, técnicos)
   - Integración con archivos VCF
   - Visualización de tabla de pacientes con filtros

2. Consultas Avanzadas:
   - Singles: variantes de un paciente con filtros por panel y frecuencia alélica
   - Dúos: comparación entre dos pacientes (intersección, exclusivas)
   - Tríos: análisis de tres pacientes (múltiples combinaciones)
   - Búsqueda por variante específica (formato Franklin/VarSome o campos individuales)
   - Exportación de resultados a VCF con metadatos completos

3. Paneles de Genes:
   - Creación de paneles personalizados desde base de datos local
   - Importación de paneles desde PanelApp UK y Australia
   - Validación automática de genes contra la base de datos
   - Visualización de genes incluidos en cada panel

4. Reportes Clínicos:
   - Validación cruzada entre VCF y CSV de Franklin
   - Selección interactiva de variantes a incluir
   - Cálculo de cobertura física por panel
   - Generación de informe Word con:
     * Datos del paciente
     * Variantes patogénicas y VUS
     * Tablas de variantes formateadas
     * Anexos con genes de cada panel y cobertura
   - Registro de cierre de informe en base de datos

5. Visualizaciones:
   - Estadísticas generales (pacientes, variantes)
   - Distribución por sexo, tipo de estudio, diagnóstico
   - Seguimiento temporal de solicitudes
   - Distribución geográfica de pacientes

ARQUITECTURA:
-------------
- Frontend: Streamlit con componentes personalizados (AgGrid)
- Backend: MySQL para persistencia
- Procesamiento: Pandas, NumPy
- Visualización: Plotly, Altair
- Reportes: python-docx

DEPENDENCIAS PRINCIPALES:
-------------------------
- Python 3.8+
- streamlit >= 1.28.0
- pandas >= 2.0.0
- mysql-connector-python >= 8.1.0
- plotly >= 5.17.0
- python-docx >= 0.8.11
- st-aggrid >= 0.3.4

Ver documentación completa en:
https://github.com/fcercadillo/pi-cercadillo/wiki

CONTACTO:
---------
Francisco Cercadillo
Email: francisco.cercadillo@unc.edu.ar
GitHub: @fcercadillo
"""
# =============================================================================
# MÓDULOS ESTÁNDAR
# =============================================================================
import io
import time
import logging
import os
import re
import altair as altair
import numpy as np
from io import BytesIO
from datetime import date, datetime
from pathlib import Path
from typing import List, Union, Optional, Tuple, Dict, Any, Set

# =============================================================================
# MÓDULOS DE TERCEROS
# =============================================================================
import pandas as pd
import plotly.express as px
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from mysql.connector import connect, Error as MySQLError
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode
import streamlit as st
from datetime import datetime

# =============================================================================
# MÓDULOS PROPIOS (TODOS LOS IMPORTS ORIGINALES)
# =============================================================================
from etapa3_main_dbv2 import (
    query_by_patient, query_by_variant,
    duo_intersection, duo_exclusive_a, duo_exclusive_b,
    trio_intersection, trio_exclusive,
    filter_by_panel_multigen, query_patient_metadata
)

from conexion_a_dbv2 import run_and_df, get_connection

from dbv2_logica_de_carga import (
    convertir_vcf_a_tsv,
    cargar_tsv_en_bd,
    verificar_existencia_paciente,
    guardar_paciente_con_metadata,
    validar_nombre_paciente,
    validar_metadata
)

from dbv_armado_panel import fetch_all_gene_names, create_names_df, df_to_excel_bytes

from dbv2_reportes_logica import (
    extraer_variantes_vcf,
    extraer_variantes_csv,
    guardar_cierre_del_informe,
    validar_cierre_informe,
    reemplazar_texto_en_parrafos,
    reemplazar_texto_en_tablas,
    insertar_lista_numerada,
    reemplazar_placeholder_con_tabla,
    traducir_acmg,
    extraer_paneles_y_genes_desde_vcf,
    extraer_id_paciente_desde_vcf,
    leer_csv_seleccionado,
    reemplazar_texto_en_encabezado,
    formatear_solo_placeholders,
    insertar_anexo_1,
    insertar_anexo_2,
    normalizar_nombre_panel,
    extraer_variantes_vcf,
    extraer_variantes_csv,
    numero_a_letras
)

from dbv2_cobertura_fisica import calcular_cobertura_para_informe

# =============================================================================
# CONFIGURACIÓN GLOBAL
# =============================================================================

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('variomedb.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes de configuración (TODAS las rutas originales comentadas)
PANEL_ACCIONABLE_PATH = "/home/fcercadillo/VariomeDB/Carpetas/panel_accionable.xlsx"
BASE_PATH = "/home/fcercadillo/VariomeDB/Carpetas/Pacientes"
PANEL_DIR = Path("/home/fcercadillo/VariomeDB/Carpetas/Paneles")
PLANTILLA_PATH = Path("/home/fcercadillo/VariomeDB/Carpetas/PLANTILLA_MODELO.docx")
PLANTILLA_VACIA_PATH = Path("/home/fcercadillo/VariomeDB/Carpetas/PLANTILLA_MODELO_VACIO.docx")

# Configuración de fechas
MIN_DATE = date(1900, 1, 1)
MAX_DATE = date.today()

# Patrones para validación de genes
PATRONES_EXCLUIR_GENES = [
    r"^GEN(ES|E|S| LIST| LSIT|E LIST)?$",
    r"^ENTITY\s*NAME$",
    r"^GENE\s*(NAME|SYMBOL|ID|LIST)?$",
    r"^NOMBRE\s*(GEN|DEL\s*GEN)?$",
    r"^LISTA\s*DE\s*GEN(ES)?$",
    r"^ENTITNEAEM$",
]

# Columnas para visualización
COLUMNAS_VARIANTES = [
    "CHROM", "POS", "REF", "ALT", "GEN_NAME", "ZYG",
    "freq_alelica", "freq_alelica_clinico", "freq_alelica_oncologico",
    "freq_pob_total", "freq_pob_clinico", "freq_pob_oncologico"
]

# Diagnósticos completo (TODAS las opciones originales)
DIAGNOSTICOS = {
    "No indicado": [],
    "Cáncer hereditario": [
        "Glioma", "Astrocitoma subependimario", "Meduloblastoma",
        "Papiloma de plexo coroideo", "Neurinoma bilateral del VIII par craneal",
    ],
    "Colagenopatías": ["Síndrome de Ehlers-Danlos"],
    "Encefalopatías epilépticas": [
        "Encefalopatía mioclónica temprana",
        "Epilepsia focal migratoria de la infancia",
        "Síndrome de Angelman",
        "Síndrome de Doose",
        "Síndrome de Dravet",
        "Síndrome de Landau-Kleffner",
        "Síndrome de Lennox-Gastaut",
        "Síndrome de Ohtahara",
        "Síndrome de punta onda continua durante el sueño lento",
        "Síndrome de Rett",
        "Síndrome de West",
    ],
    "Accidente cerebrovascular (ACV)": [
        "ACV isquémico", "ACV hemorrágico", "ACV ataque isquémico transitorio",
    ],
    "Aneurisma cerebral": [],
    "Disección arterial": [],
    "Enfermedad cerebral de pequeños vasos": [
        "CADASIL (NOTCH3)", "CARASIL1 (NOTCH3)", "CARASIL2 (HTRA1)",
        "BSVD1 (COL4A1)", "BSVD2 (COL4A2)", "BSVD3 (COLGALT1)",
        "BSVD4 (NIT1)", "BSVD5 (ARHGEF15)", "Hiperintensidades en sustancia blanca",
        "Microsangrados", "Infartos lacunares", "Atrofia cerebral",
        "Angiopatía amiloidea cerebral", "Vasculitis",
    ],
    "Malformaciones arteriovenosas": [],
    "Enfermedad de moyamoya": [],
    "Tromboflebitis": [],
    "Cefalea o migraña": ["Migraña hemipléjica familiar"],
    "Policitemia": [],
    "Purpura trombocitopenica": [],
    "Telangiectasia hereditaria hemorrágica": [],
    "Enfermedades metabólicas": [
        "Fabry (GLA)", "Gaucher (GBA)", "Niemann-Pick (SMPD1)",
    ],
    "Enfermedades mitocondriales adn nuclear": [
        "Acidosis láctica", "Ataxia", "Atrofia óptica", "Cetoacidosis",
        "Deficiencia de coenzima Q10", "Dismorfia", "Encefalomiopatía",
        "Encefalopatía", "Hepatopatía", "Hipopotasemia", "Hipotonía",
        "Leucodistrofia", "Miocardiopatía", "Miopatía", "Retraso del desarrollo",
        "Síndrome de Alpers-Huttenlocher", "Síndrome de Barth",
        "Síndrome de Leigh", "Tubulopatía renal",
    ],
    "Enfermedades neurodegenerativas": [
        "Alzheimer de inicio temprano", "Alzheimer de inicio tardío",
        "Atrofia cortical", "Demencia", "Demencia por cuerpos de Lewy",
        "Demencia fronto-temporal (DFT)", "Deterioro cognitivo",
        "Esclerosis lateral amiotrófica (ELA)", "ELA/DFT",
        "Enfermedad de motoneurona", "Enfermedad de Creutzfeldt-Jakob (ECJ)",
        "Trastorno psiquiátrico",
    ],
    "Enfermedades neuromusculares": [
        "Artrogriposis", "Miopatía", "Miopatía congénita", "Miopatía distal",
        "Miopatía metabólica", "Síndrome miasténico congénito",
        "Distrofia muscular de cinturas (LGMD)",
        "Distrofia facioescapulohumeral (FSHD)", "Distrofia muscular congénita",
        "HiperCKemia", "Rabdomiólisis",
    ],
    "Epilepsias": [
        "Epilepsia", "Epilepsia refractaria", "Epilepsia focal",
        "Epilepsia generalizada", "Epilepsia focal y generalizada",
        "Síndrome de deficiencia de GLUT1",
    ],
    "Neuropatías hereditarias": [
        "Charcot-Marie-Tooth (CMT)", "Neuropatía sensitiva", "Neuropatía motora",
        "Neuropatía sensitiva-motora", "Neuropatía autonómica",
    ],
    "Rasopatías": [
        "Neurofibromatosis tipo 1", "Neurofibromatosis tipo 2",
        "Síndrome de Noonan", "Síndrome de Costello",
    ],
    "Trastornos del movimiento": [
        "Ataxia de inicio en el adulto", "Ataxia de inicio en la infancia",
        "Corea", "Disquinesia", "Distonía", "Enfermedad de Parkinson",
        "Paraparesia espástica hereditaria (adulto)",
        "Paraparesia espástica hereditaria (infantil)", "Parkinsonismo",
        "Síndrome corticobasal", "Temblor",
    ],
    "Trastornos del neurodesarrollo": [
        "Discapacidad intelectual", "Retraso del desarrollo",
        "Síndrome de Kabuki", "Trastornos del espectro autista (TEA)",
    ],
    "Trastornos de la sustancia blanca / leucoencefalopatías": [
        "Adrenoleucodistrofia ligada al X", "Leucodistrofia infantil",
        "Leucodistrofia del adulto", "Hipomielinización",
        "Síndrome Aicardi-Goutieres", "Síndrome de Fahr",
    ],
}

# Opciones de paneles (TODAS las originales)
OPCIONES_PANELES = [
    "No indicado",
    "Accidente cerebrovascular",
    "Aneurisma o disección de la aorta torácica",
    "Ataxia hereditaria",
    "Ataxia hereditaria con inicio en el adulto",
    "Ataxia hereditaria con inicio en la infancia",
    "Atrofia óptica",
    "Autismo",
    "Cáncer hereditario",
    "Coloboma ocular",
    "Demencia de inicio temprano",
    "Diabetes familiar",
    "Disautonomía familiar",
    "Discapacidad intelectual",
    "Disquinesia paroxística",
    "Distonía y corea",
    "Distonía, corea o trastorno del movimiento relacionado de inicio en el adulto",
    "Distonía, corea o trastorno del movimiento relacionado de inicio en la infancia",
    "Distrofia muscular congénita",
    "Enfermedad cerebral familiar de pequeños vasos",
    "Enfermedad de Parkinson y parkinsonismo complejo",
    "Enfermedades autoinflamatorias",
    "Enfermedades de la retina",
    "Enfermedades hereditarias de la sustancia blanca",
    "Enfermedades metabólicas",
    "Enfermedades mitocondriales (genes nucleares)",
    "Enfermedades neurodegenerativas de inicio en el adulto",
    "Epilepsia de inicio temprano o sindrómica",
    "Epilepsia focal",
    "Epilepsia generalizada",
    "Epilepsia genética",
    "Epilepsia mioclónica progresiva",
    "Esclerosis lateral amiotrófica",
    "Hipoplasia cerebelar",
    "Inmunodeficiencia primaria",
    "Leucodistrofia",
    "Leucodistrofia de inicio en el adulto",
    "Leucodistrofia de inicio en la infancia",
    "Lipofuscinosis ceroidea neuronal",
    "Lisencefalia y heterotopía de banda",
    "Malformaciones del desarrollo cortical",
    "Malformaciones vasculares cerebrales",
    "Microcefalia",
    "Miopatía congénita",
    "Miopatía metabólica y rabdomiólisis",
    "Miopatía y distrofia muscular",
    "Neurofibromatosis tipo 1",
    "Neuropatía hereditaria",
    "Neuropatía óptica",
    "Paraparesia espástica hereditaria",
    "Paraparesia espástica hereditaria de inicio en el adulto",
    "Paraparesia espástica hereditaria de inicio en la infancia",
    "Polimicrogiria y esquizencefalia",
    "Rabdomiólisis aguda",
    "Rasopatías",
    "Síndromes similares a Angelman-Rett",
    "Tubulopatías renales",
]

# Opciones de países (TODOS los originales)
PAISES = [
    "No indicado", "Argentina",
    "Afganistán", "Albania", "Alemania", "Andorra", "Angola", "Antigua y Barbuda",
    "Arabia Saudita", "Argelia", "Armenia", "Australia", "Austria", "Azerbaiyán",
    "Bahamas", "Bangladés", "Barbados", "Baréin", "Bélgica", "Belice", "Benín",
    "Bielorrusia", "Birmania", "Bolivia", "Bosnia y Herzegovina", "Botsuana",
    "Brasil", "Brunéi", "Bulgaria", "Burkina Faso", "Burundi", "Bután",
    "Cabo Verde", "Camboya", "Camerún", "Canadá", "Catar", "Chad", "Chile",
    "China", "Chipre", "Colombia", "Comoras", "Corea del Norte", "Corea del Sur",
    "Costa de Marfil", "Costa Rica", "Croacia", "Cuba", "Dinamarca", "Dominica",
    "Ecuador", "Egipto", "El Salvador", "Emiratos Árabes Unidos", "Eritrea",
    "Eslovaquia", "Eslovenia", "España", "Estados Unidos", "Estonia", "Esuatini",
    "Etiopía", "Filipinas", "Finlandia", "Fiyi", "Francia", "Gabón", "Gambia",
    "Georgia", "Ghana", "Granada", "Grecia", "Guatemala", "Guyana", "Guinea",
    "Guinea-Bisáu", "Guinea Ecuatorial", "Haití", "Honduras", "Hungría", "India",
    "Indonesia", "Irak", "Irán", "Irlanda", "Islandia", "Islas Marshall",
    "Islas Salomón", "Israel", "Italia", "Jamaica", "Japón", "Jordania",
    "Kazajistán", "Kenia", "Kirguistán", "Kiribati", "Kuwait", "Laos", "Lesoto",
    "Letonia", "Líbano", "Liberia", "Libia", "Liechtenstein", "Lituania",
    "Luxemburgo", "Madagascar", "Malasia", "Malaui", "Maldivas", "Malí", "Malta",
    "Marruecos", "Mauricio", "Mauritania", "México", "Micronesia", "Moldavia",
    "Mónaco", "Mongolia", "Montenegro", "Mozambique", "Namibia", "Nauru", "Nepal",
    "Nicaragua", "Níger", "Nigeria", "Noruega", "Nueva Zelanda", "Omán",
    "Países Bajos", "Pakistán", "Palaos", "Palestina", "Panamá",
    "Papúa Nueva Guinea", "Paraguay", "Perú", "Polonia", "Portugal",
    "Reino Unido", "República Centroafricana", "República Checa",
    "República Democrática del Congo", "República del Congo",
    "República Dominicana", "Ruanda", "Rumanía", "Rusia", "Samoa",
    "San Cristóbal y Nieves", "San Marino", "San Vicente y las Granadinas",
    "Santa Lucía", "Santo Tomé y Príncipe", "Senegal", "Serbia", "Seychelles",
    "Sierra Leona", "Singapur", "Siria", "Somalia", "Sri Lanka", "Sudáfrica",
    "Sudán", "Sudán del Sur", "Suecia", "Suiza", "Surinam", "Tailandia",
    "Tanzania", "Tayikistán", "Timor Oriental", "Togo", "Tonga",
    "Trinidad y Tobago", "Túnez", "Turkmenistán", "Turquía", "Tuvalu", "Ucrania",
    "Uganda", "Uruguay", "Uzbekistán", "Vanuatu", "Vaticano", "Venezuela",
    "Vietnam", "Yemen", "Yibuti", "Zambia", "Zimbabue"
]

PROVINCIAS = [
    "No indicado", "Buenos Aires", "Catamarca", "Chaco", "Chubut", "Córdoba",
    "Corrientes", "Entre Ríos", "Formosa", "Jujuy", "La Pampa", "La Rioja",
    "Mendoza", "Misiones", "Neuquén", "Río Negro", "Salta", "San Juan",
    "San Luis", "Santa Cruz", "Santa Fe", "Santiago del Estero",
    "Tierra del Fuego", "Tucumán", "Ciudad Autónoma de Buenos Aires (CABA)"
]

PROFESIONALES = [
    "Agata Claudia Fernandez Gamba",
    "Eugenia Arias Cebollada",
    "Victoria Massazza",
    "Daniel Avendaño",
    "Tatiana Itzcovich",
    "Francisco Cercadillo"
]

# =============================================================================
# CARGA DE PANEL ACCIONABLE
# =============================================================================

try:
    df_acc = pd.read_excel(
        PANEL_ACCIONABLE_PATH,
        usecols=[0],
        dtype=str,
        engine="openpyxl"
    )
    PANEL_ACCIONABLE = (
        df_acc.iloc[:, 0]
        .dropna()
        .str.strip()
        .tolist()
    )
    logger.info(f"Panel accionable cargado: {len(PANEL_ACCIONABLE)} genes")
except Exception as e:
    logger.warning(f"No se pudo cargar el panel accionable: {e}")
    PANEL_ACCIONABLE = []

# =============================================================================
# CONFIGURACIÓN DE STREAMLIT
# =============================================================================

st.set_page_config(
    page_title="VariomeDB - Análisis Genético",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado (TODOS los estilos originales)
st.markdown("""
<style>
    /* Estilos para navbar */
    .navbar-button {
        background-color: #f0f2f6;
        color: #000;
        border: none;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 15px;
        font-weight: 500;
        margin-right: 8px;
        cursor: pointer;
        transition: background-color 0.2s ease;
        width: 100%;
        text-align: center;
    }
    .navbar-button:hover {
        background-color: #e8ecf1;
    }
    .navbar-button-active {
        background-color: #0078d4 !important;
        color: white !important;
        font-weight: 600 !important;
    }
    
    /* Estilos para tablas */
    .stDataFrame {
        font-size: 14px;
    }
    
    /* Estilos para métricas */
    .metric-container {
        text-align: center;
        padding: 1rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-title {
        font-size: 16px;
        font-weight: 500;
        color: #495057;
    }
    .metric-value {
        font-size: 32px;
        font-weight: 600;
        color: #0078d4;
    }
    
    /* Ajustes de padding */
    .block-container {
        padding-top: 2rem !important;
    }
    
    div[data-testid="stMarkdownContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    
    div[data-baseweb="select"] span {
        font-size: 18px !important;   
    }
    
    /* Estilos para AgGrid */
    .ag-header-cell-label {
        justify-content: left !important;
        text-align: left !important;
    }
    .centered-header {
        text-align: left !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# INICIALIZACIÓN DE ESTADO DE SESIÓN
# =============================================================================

def inicializar_estado_sesion() -> None:
    """Inicializa todas las variables de estado de sesión."""
    
    if 'df_pacientes' not in st.session_state:
        try:
            sql_pacs = (
                "SELECT id_paciente AS id, nombre_paciente AS nombre "
                "FROM tabla_pacientes"
            )
            st.session_state.df_pacientes = run_and_df(sql_pacs)
            st.session_state.pacientes_nombres = (
                st.session_state.df_pacientes['nombre'].tolist()
            )
            logger.info(f"Pacientes cargados: {len(st.session_state.pacientes_nombres)}")
        except Exception as e:
            logger.error(f"Error cargando pacientes: {e}")
            st.session_state.df_pacientes = pd.DataFrame()
            st.session_state.pacientes_nombres = []

    if "page" not in st.session_state:
        st.session_state.page = "Inicio"

    if "modo" not in st.session_state:
        st.session_state.modo = "Búsqueda"

    if "df_result" not in st.session_state:
        st.session_state.df_result = None

    if "coberturas" not in st.session_state:
        st.session_state.coberturas = {}

    if "paciente_existe" not in st.session_state:
        st.session_state.paciente_existe = None

    if "vcf_encontrado" not in st.session_state:
        st.session_state.vcf_encontrado = None

    if "vcf_ruta" not in st.session_state:
        st.session_state.vcf_ruta = None

    if "prev_nombre" not in st.session_state:
        st.session_state.prev_nombre = None

inicializar_estado_sesion()

# =============================================================================
# FUNCIONES AUXILIARES GENERALES
# =============================================================================

def salto_linea(px: int = 20) -> None:
    """Agrega un espacio vertical en la interfaz."""
    st.markdown(f"<div style='margin-top:{px}px;'></div>", unsafe_allow_html=True)


def slugify(text: str) -> str:
    """Convierte texto a formato slug (URL-friendly)."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")


def reset_single() -> None:
    """Resetea resultado de consulta single."""
    st.session_state.df_result = None


def reset_duo() -> None:
    """Resetea resultado de consulta dúo."""
    st.session_state.df_result = None


def reset_trio() -> None:
    """Resetea resultado de consulta trío."""
    st.session_state.df_result = None


def cantidad_pacientes_disponibles(apt: Path) -> int:
    """
    Cuenta pacientes disponibles en el sistema de archivos.
    
    Args:
        apt: Ruta base a explorar
        
    Returns:
        Número de pacientes disponibles
    """
    contador = 0
    try:
        for carpeta in apt.iterdir():
            if carpeta.is_dir():
                vcf_path = carpeta / f"{carpeta.name}.final.vcf"
                if vcf_path.exists():
                    contador += 1
    except Exception as e:
        logger.error(f"Error contando pacientes: {e}")
    return contador


def es_gen_valido(nombre: str) -> bool:
    """Valida si un nombre de gen es válido (no es encabezado)."""
    g = nombre.strip().upper()
    if len(g) <= 1:
        return False
    for patron in PATRONES_EXCLUIR_GENES:
        if re.fullmatch(patron, g):
            return False
    return True


def validate_panel(panel_genes: List[str]) -> Tuple[List[str], List[str]]:
    """
    Valida una lista de genes contra la base de datos.
    
    Returns:
        Tupla (genes_válidos, genes_faltantes)
    """
    if not panel_genes:
        return [], []
    
    placeholders = ",".join(["%s"] * len(panel_genes))
    sql = (
        "SELECT nombre_gen "
        "FROM tabla_genes "
        f"WHERE nombre_gen IN ({placeholders})"
    )
    try:
        dfv = run_and_df(sql, tuple(panel_genes))
        valid = dfv['nombre_gen'].tolist()
        missing = sorted(set(panel_genes) - set(valid))
        return valid, missing
    except Exception as e:
        logger.error(f"Error validando panel: {e}")
        return [], panel_genes


def obtener_total(query: str, columna: str) -> int:
    """Ejecuta query y retorna valor numérico."""
    try:
        df = run_and_df(query)
        return int(df.at[0, columna]) if not df.empty else 0
    except Exception as e:
        logger.error(f"Error en query: {e}")
        return 0


def mostrar_metrica(titulo: str, valor: Union[int, float], columna) -> None:
    """Muestra una métrica con formato personalizado."""
    with columna:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-title">{titulo}</div>
            <div class="metric-value">{valor:,}</div>
        </div>
        """, unsafe_allow_html=True)


def graficar_pie(df: pd.DataFrame, columna: str, titulo: str, 
                 color_map: Optional[Dict] = None, 
                 orden: Optional[List] = None) -> None:
    """Genera gráfico de torta con Plotly."""
    st.markdown(f"#### {titulo}")
    
    if df.empty:
        st.write("No hay datos.")
        return

    df[columna] = (
        df[columna].astype(str).str.strip().replace("", "No indicado").str.title()
    )

    fig = px.pie(
        df, names=columna, values="total",
        color=columna if color_map else None,
        color_discrete_map=color_map if color_map else None,
        category_orders={columna: orden} if orden else None
    )
    fig.update_traces(
        hovertemplate=f"<b>{columna.title()}</b>: %{{label}}<br><b>Total</b>: %{{value:,}}<extra></extra>"
    )
    st.plotly_chart(fig, use_container_width=True)


@st.cache_data(ttl=300)
def get_cached_gene_names() -> List[str]:
    """Obtiene lista de genes desde BD con caché."""
    return fetch_all_gene_names()


# =============================================================================
# FUNCIONES DE GENERACIÓN VCF (VERSIÓN COMPLETA)
# =============================================================================

def generate_vcf_bytes(
    df: pd.DataFrame,
    sample_name: str = "SAMPLE1",
    paneles_dict: Optional[Dict[str, List[str]]] = None,
    analysis_tag: Optional[str] = None
) -> bytes:
    """
    Genera archivo VCF en memoria (versión completa con todos los campos).
    """
    # Validación
    required_cols = {'CHROM', 'POS', 'REF', 'ALT'}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"DataFrame debe contener: {required_cols}")
    
    buf = io.StringIO()

    # Header
    buf.write("##fileformat=VCFv4.1\n")
    buf.write(f"##fileDate={datetime.now().strftime('%Y%m%d')}\n")
    buf.write("##source=VARIOMEDB_V2_24122025\n")
    buf.write("##reference=GRCh37\n")
    buf.write("##contig=<ID=chr1,length=248956422,assembly=GRCh37>\n")

    # Metadatos paciente
    buf.write(f"##PACIENTE_CASO={sample_name}\n")
    if analysis_tag:
        buf.write(f"##TIPO_DE_ANALISIS={analysis_tag}\n")

    # Paneles
    if paneles_dict:
        buf.write("##PANEL_FILTER=TRUE\n")
        for idx, (nombre, genes) in enumerate(paneles_dict.items(), start=1):
            nombre_limpio = str(nombre).replace(" ", "_").lower()
            genes_limpios = sorted({g.strip() for g in genes if g})
            buf.write(f"##PANEL_NAMES_{idx}={nombre_limpio}\n")
            buf.write(f"##PANEL_GENES_{idx}={','.join(genes_limpios)}\n")
    else:
        buf.write("##PANEL_FILTER=FALSE\n")

    # INFO tags (TODOS los campos originales)
    buf.write('##INFO=<ID=AF,Number=1,Type=Float,Description="Allele Frequency (Total)">\n')
    buf.write('##INFO=<ID=AF_CLIN,Number=1,Type=Float,Description="Allele Frequency (Clinical)">\n')
    buf.write('##INFO=<ID=AF_ONCO,Number=1,Type=Float,Description="Allele Frequency (Oncology)">\n')
    buf.write('##INFO=<ID=PF,Number=1,Type=Float,Description="Population Frequency (Total)">\n')
    buf.write('##INFO=<ID=PF_CLIN,Number=1,Type=Float,Description="Population Frequency (Clinical)">\n')
    buf.write('##INFO=<ID=PF_ONCO,Number=1,Type=Float,Description="Population Frequency (Oncology)">\n')
    buf.write('##INFO=<ID=GENE,Number=1,Type=String,Description="Gene symbol">\n')
    buf.write('##INFO=<ID=ZYG,Number=1,Type=String,Description="Zygosity (HET/HOM)">\n')

    # FORMAT
    buf.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')

    # Columnas
    buf.write(f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}\n")

    # Variantes
    for _, row in df.iterrows():
        chrom = str(row.CHROM)
        pos = str(row.POS)
        ref = str(row.REF)
        alt = str(row.ALT)

        def fmt(val):
            try:
                return f"{float(val):.4f}"
            except (ValueError, TypeError):
                return str(val) if val not in (None, "") else "."

        info_parts = [
            f"AF={fmt(row.get('freq_alelica', 0))}",
            f"AF_CLIN={fmt(row.get('freq_alelica_clinico', 0))}",
            f"AF_ONCO={fmt(row.get('freq_alelica_oncologico', 0))}",
            f"PF={fmt(row.get('freq_pob_total', 0))}",
            f"PF_CLIN={fmt(row.get('freq_pob_clinico', 0))}",
            f"PF_ONCO={fmt(row.get('freq_pob_oncologico', 0))}",
            f"GENE={row.get('GEN_NAME', '')}",
            f"ZYG={row.get('ZYG', '')}"
        ]
        info = ";".join(info_parts)

        zyg = str(row.get("ZYG", "")).upper()
        gt = {"HET": "0/1", "HOM": "1/1"}.get(zyg, "0/0")

        buf.write(f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\tPASS\t{info}\tGT\t{gt}\n")

    return buf.getvalue().encode("utf-8")


# =============================================================================
# FUNCIONES DE CARGA DE PACIENTES (COMPLETAS)
# =============================================================================

def paso_ingresar_nombre_con_autocomplete() -> str:
    """
    Paso 1: Selección de paciente desde el sistema de archivos.
    Versión completa con toda la lógica original.
    """
    carpeta_base = Path(BASE_PATH)

    # Obtener nombres ya cargados
    try:
        df_bd = run_and_df("SELECT nombre_paciente FROM tabla_pacientes")
        nombres_cargados = df_bd["nombre_paciente"].astype(str).tolist()
        ids_base_cargados = set(n.split("_")[0] for n in nombres_cargados)
    except Exception as e:
        logger.error(f"Error obteniendo pacientes cargados: {e}")
        ids_base_cargados = set()

    # Agrupar carpetas por ID base
    grupos = {}
    for sub in carpeta_base.iterdir():
        if not sub.is_dir():
            continue
        nombre_carpeta = sub.name
        id_base = nombre_carpeta.split("_")[0]
        grupos.setdefault(id_base, []).append(nombre_carpeta)

    opciones_finales = []

    # Procesar cada ID base
    for id_base, carpetas in grupos.items():
        if id_base in ids_base_cargados:
            continue

        carpeta_modapy_con_vcf = None
        carpeta_con_vcf = None
        cualquier_carpeta = None

        for c in carpetas:
            cualquier_carpeta = c
            vcf_path = carpeta_base / c / f"{c}.final.vcf"
            tiene_vcf = vcf_path.exists()

            if "MODAPY" in c.upper() and tiene_vcf:
                carpeta_modapy_con_vcf = c
            elif tiene_vcf:
                carpeta_con_vcf = c

        if carpeta_modapy_con_vcf:
            opciones_finales.append(carpeta_modapy_con_vcf)
        elif carpeta_con_vcf:
            opciones_finales.append(carpeta_con_vcf)
        else:
            opciones_finales.append(cualquier_carpeta)

    opciones_finales = sorted(opciones_finales)

    elegido = st.selectbox(
        "📁 Cargar un paciente desde */DATA/NGS/Pacientes*",
        options=opciones_finales,
        index=None,
        placeholder="Seleccione una ID paciente",
        help="Puede recorrer la lista, escribir o copiar/pegar el nombre del paciente."
    )

    return elegido if elegido else ""


def boton_verificar_paciente(nombre: str) -> None:
    """Paso 2: Verificar si el paciente existe en BD y buscar su VCF."""
    valido, msg = validar_nombre_paciente(nombre)
    if nombre and not valido:
        st.error(f"❌ Error de formato: {msg}")

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.button("🔍 Validar paciente"):
        if not nombre:
            st.warning("❌ Debe ingresar un nombre")
            return
        if not valido:
            return

        existe = verificar_existencia_paciente(nombre)
        st.session_state["paciente_existe"] = existe

        if existe:
            st.warning(f"⚠️ El paciente **{nombre}** ya está cargado")
        else:
            st.info(f"ℹ️ El paciente **{nombre}** no está cargado")
            carpeta, vcf = paso_buscar_carpeta_y_vcf(nombre)
            st.session_state["vcf_ruta"] = vcf


def paso_buscar_carpeta_y_vcf(nombre: str) -> Tuple[str, Optional[str]]:
    """Busca la carpeta y archivo VCF del paciente."""
    id_sin_ext = Path(nombre).stem
    carpeta_paciente = os.path.join(BASE_PATH, id_sin_ext)

    if os.path.isdir(carpeta_paciente):
        vcf_path = os.path.join(carpeta_paciente, f"{nombre}.final.vcf")
        if os.path.isfile(vcf_path):
            st.success(f"✅ VCF encontrado para **{nombre}**")
            st.session_state["vcf_encontrado"] = True
            return carpeta_paciente, vcf_path
        else:
            st.warning(f"⚠️ No se encontró {nombre}.final.vcf")
            st.session_state["vcf_encontrado"] = False
    else:
        st.warning(f"⚠️ No existe la carpeta {carpeta_paciente}")
        st.session_state["vcf_encontrado"] = False

    return carpeta_paciente, None


def paso_ingresar_metadata(nombre: str, carpeta_paciente: str, vcf_path: str) -> None:
    """
    Paso 3: Formulario completo de ingreso de metadata del paciente.
    Versión con TODOS los campos originales.
    """
    salto_linea(10)
    st.markdown("### 📋 Formulario de ingreso de metadata del paciente")
    st.markdown("<hr>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="large")

    def campo(label_html, input_widget):
        with st.container():
            st.markdown(f"""
                <div style='margin-bottom:3px; font-size:15px; font-weight:500;'>
                    {label_html}
                </div>
            """, unsafe_allow_html=True)
            return input_widget()

    # Columna 1
    with col1:
        apellido_paciente = campo(
            "Apellido del paciente <span style='color:red;'>(obligatorio)</span>",
            lambda: st.text_input(" ", key="apellido_paciente", label_visibility="collapsed",
                                  placeholder="Ingrese apellido completo").strip().upper()
        )

        nombre_paciente = campo(
            "Nombre del paciente <span style='color:red;'>(obligatorio)</span>",
            lambda: st.text_input(" ", key="nombre_paciente", label_visibility="collapsed",
                                 placeholder="Ingrese nombre completo").strip().upper()
        )

        nombre_real_paciente = None
        if apellido_paciente and nombre_paciente:
            nombre_real_paciente = f"{apellido_paciente}, {nombre_paciente}"

        dni_paciente = campo(
            "DNI del paciente <span style='color:red;'>(obligatorio)</span>",
            lambda: st.text_input(" ", key="dni_paciente", label_visibility="collapsed",
                                 placeholder="Ingrese DNI").strip().upper()
        )

        fecha_nacimiento = campo(
            "Fecha de nacimiento <span style='color:red;'>(obligatorio)</span>",
            lambda: st.date_input(
                " ",
                value=None,
                min_value=MIN_DATE,
                max_value=MAX_DATE,
                key="fnacimiento",
                label_visibility="collapsed"
            )
        )

        sexo = campo(
            "Sexo <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(
                " ",
                options=["Femenino", "Masculino"],
                index=None,
                placeholder="Elija una opción",
                label_visibility="collapsed"
            )
        )

        conoce_inicio = campo(
            "Edad de inicio de síntomas <span style='color:red;'>(obligatorio)</span>",
            lambda: st.radio(
                " ",
                options=["No indicado", "Sí"],
                label_visibility="collapsed"
            )
        )

        edad_inicio_sintomas = "No indicado"
        if conoce_inicio == "Sí":
            col_valor, col_unidad = st.columns([2, 1])
            with col_valor:
                edad_valor = st.number_input(
                    "Edad", min_value=0, max_value=150, step=1, label_visibility="collapsed"
                )
            with col_unidad:
                unidad = st.selectbox(
                    "Unidad", options=["meses", "años"], label_visibility="collapsed"
                )
            edad_inicio_sintomas = f"{edad_valor} {unidad}"

    # Columna 2
    with col2:
        profesional_carga = campo(
            "Data entry <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(
                " ",
                options=PROFESIONALES,
                index=None,
                placeholder="Seleccione quién realizó la carga",
                label_visibility="collapsed"
            )
        )

        fecha_solicitud = campo(
            "Fecha de solicitud <span style='color:red;'>(obligatorio)</span>",
            lambda: st.date_input(
                " ",
                value=None,
                min_value=MIN_DATE,
                max_value=MAX_DATE,
                key="fsolicitud",
                label_visibility="collapsed"
            )
        )

        tipo_estudio = campo(
            "Tipo de estudio <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(" ", options=["Clínico", "Oncológico"],
                                 index=None, placeholder="Elija una opción", label_visibility="collapsed")
        )

        tipo_de_muestra = campo(
            "Tipo de muestra <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(" ", options=["No indicado", "Sangre", "Sangre en papel"], index=None,
                                 placeholder="Elija una opción", label_visibility="collapsed")
        )

        diagnostico_principal = campo(
            "Diagnóstico y/o sospecha clínica <span style='color:red;'>(obligatorio)</span>",
            lambda: st.multiselect(
                " ",
                options=["No indicado"] + sorted(k for k in DIAGNOSTICOS.keys() if k != "No indicado"),
                placeholder="Seleccione una o más categorías",
                label_visibility="collapsed"
            )
        )

        subdiagnosticos = []
        if diagnostico_principal:
            opciones_sub = []
            for cat in diagnostico_principal:
                opciones_sub.extend(DIAGNOSTICOS.get(cat, []))
            subdiagnosticos = campo(
                "Subdiagnóstico",
                lambda: st.multiselect(
                    " ",
                    options=sorted(set(opciones_sub)),
                    placeholder="Seleccione uno o más subdiagnósticos",
                    label_visibility="collapsed"
                )
            )

        sintomas = campo(
            "Descripción de los síntomas",
            lambda: st.text_area(" ", placeholder="Agregue una descripción de los síntomas", 
                                label_visibility="collapsed").strip() or None
        )

    # Columna 3
    with col3:
        paneles_utilizados = campo(
            "Paneles de genes aplicados",
            lambda: st.multiselect(
                " ",
                options=OPCIONES_PANELES,
                placeholder="Seleccione los paneles a utilizar",
                help="Listado actualizado al 09/02/26 por PanelApp",
                label_visibility="collapsed"
            ) or None
        )

        cap_kit = campo(
            "Kit de captura <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(
                " ",
                options=["No indicado", "SureSelect V4-post", "SureSelect V5-post",
                         "SureSelect V6-post", "SureSelect V7-post", "TWIST 100X",
                         "Nextera XT kits"],
                index=None, placeholder="Elija una opción", label_visibility="collapsed"
            )
        )

        secuenciador = campo(
            "Secuenciador <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(
                " ",
                options=[
                    "No indicado", "HiSeq4000", "Illumina HiSeq System",
                    "Illumina Platform", "Novaseq 6000, 150bp PE, Illumina Platform",
                    "Novaseq X, 150bp PE, Illumina Platform"
                ],
                index=None, placeholder="Elija una opción", label_visibility="collapsed"
            )
        )

        antecedentes_familiares = campo(
            "Antecedentes familiares <span style='color:red;'>(obligatorio)</span>",
            lambda: st.selectbox(
                " ",
                options=["No indicado", "Sí", "No"],
                index=None, placeholder="Elija una opción", label_visibility="collapsed"
            )
        )

        if antecedentes_familiares == "Sí":
            detalle_antecedentes = st.text_area(
                "Detalle de antecedentes familiares",
                placeholder="Describa los antecedentes familiares relevantes"
            )
        else:
            detalle_antecedentes = None

        region_pais = campo(
            "País",
            lambda: st.selectbox(
                " ",
                options=PAISES,
                index=None, placeholder="Elija el país de nacimiento",
                label_visibility="collapsed"
            )
        )

        region_provincia = None
        if region_pais == "Argentina":
            region_provincia = campo(
                "Provincia",
                lambda: st.selectbox(
                    " ",
                    options=PROVINCIAS,
                    index=None, placeholder="Elija la provincia de nacimiento",
                    label_visibility="collapsed"
                )
            )

    # Botón final
    st.markdown("<hr>", unsafe_allow_html=True)

    if st.button("💾 Cargar paciente", type="primary"):
        diagnostico_str = ", ".join(diagnostico_principal) if diagnostico_principal else "No indicado"
        
        metadata = {
            "nombre_real_paciente": nombre_real_paciente,
            "sexo": sexo,
            "fecha_nacimiento": fecha_nacimiento.strftime("%Y-%m-%d") if fecha_nacimiento else None,
            "fecha_inicio_sintomas": edad_inicio_sintomas,
            "diagnostico_sospecha_clinica": diagnostico_str,
            "tipo_estudio": tipo_estudio,
            "cap_kit": cap_kit,
            "secuenciador": secuenciador,
            "antecedentes_familiares": antecedentes_familiares,
            "tipo_de_muestra": tipo_de_muestra,
            "fecha_solicitud": fecha_solicitud.strftime("%Y-%m-%d") if fecha_solicitud else None,
            "sintomas": sintomas,
            "region_pais": region_pais,
            "region_provincia": region_provincia,
            "cierre_del_informe": None,
            "fecha_cierre_del_informe": None
        }

        errores = validar_metadata(metadata)
        if errores:
            for e in errores:
                st.error(e)
            return

        try:
            start_time = time.time()
            status = st.empty()
            progress = st.progress(0)
            
            guardar_paciente_con_metadata(nombre, metadata)
            
            tsv_path = convertir_vcf_a_tsv(vcf_path, status=status, progress=progress)
            resultado = cargar_tsv_en_bd(tsv_path, nombre, status=status, progress=progress)

            end_time = time.time()
            minutos = int((end_time - start_time) // 60)
            segundos = int((end_time - start_time) % 60)

            if resultado.exitoso:
                st.success(f"✅ Paciente **{nombre}** cargado. Tiempo: {minutos}m {segundos}s")
                for key in ("paciente_existe", "vcf_encontrado"):
                    st.session_state.pop(key, None)
            else:
                st.error(f"❌ Error: {resultado.mensaje}")

        except Exception as e:
            st.error(f"❌ Error inesperado: {e}")
            logger.exception("Error en carga de paciente")


def main_carga_pacientes() -> None:
    """Flujo principal de carga de pacientes."""
    nombre_input = paso_ingresar_nombre_con_autocomplete()
    if not nombre_input:
        return

    prev = st.session_state.get("prev_nombre")
    if prev != nombre_input:
        for key in ("paciente_existe", "vcf_ruta"):
            st.session_state.pop(key, None)
        st.session_state["prev_nombre"] = nombre_input

    boton_verificar_paciente(nombre_input)

    if (st.session_state.get("paciente_existe") is False and 
        st.session_state.get("vcf_ruta")):
        carpeta = os.path.join(BASE_PATH, Path(nombre_input).stem)
        paso_ingresar_metadata(nombre_input, carpeta, st.session_state["vcf_ruta"])


# =============================================================================
# FUNCIONES DE PÁGINA DE INICIO (COMPLETAS)
# =============================================================================

def pagina_inicio() -> None:
    """Página de inicio con estadísticas y visualizaciones."""
    
    total_pacientes = obtener_total(
        "SELECT COUNT(*) AS total_pacientes FROM tabla_pacientes", "total_pacientes"
    )
    total_variantes = obtener_total(
        "SELECT COUNT(*) AS total_variantes FROM tabla_variantes", "total_variantes"
    )
    # total_disponibles = cantidad_pacientes_disponibles(Path("/home/biomolecular/DATA/NGS/Pacientes"))

    col1, col2, col3 = st.columns(3, gap="large")
    mostrar_metrica("🧑 Pacientes cargados", total_pacientes, col1)
    mostrar_metrica("🧬 Total de variantes", total_variantes, col3)

    st.markdown("---")

    # Gráficos
    col1, col2 = st.columns([1, 1])

    # Sexo
    df_sexo = run_and_df(
        "SELECT COALESCE(sexo, 'Desconocido') AS sexo, COUNT(*) AS total FROM tabla_pacientes GROUP BY sexo"
    )
    color_map_sexo = {"Femenino": "#1f77b4", "Masculino": "#aec7e8", "No Indicado": "#d62728"}
    orden_sexo = ["Femenino", "Masculino", "No Indicado"]
    with col1:
        graficar_pie(df_sexo, "sexo", "Distribución por Sexo", color_map_sexo, orden_sexo)

    # Zigosidad (datos de ejemplo o reales)
    df_zyg = pd.DataFrame({
        "Cigosidad": ["Heterocigota", "Homocigota"],
        "total": [36237754, 22887636]
    })
    with col2:
        df_zyg = df_zyg[df_zyg["Cigosidad"] != "."].copy()
        df_zyg["Cigosidad"] = df_zyg["Cigosidad"].str.replace("_", " ").str.title()
        graficar_pie(df_zyg, "Cigosidad", "Distribución de Cigosidad")

    st.markdown("---")

    # Tipo de estudio y diagnóstico
    col1, col2 = st.columns([1, 1])

    with col1:
        df = run_and_df("SELECT tipo_estudio, COUNT(*) AS total FROM tabla_pacientes GROUP BY tipo_estudio")
        df["tipo_estudio"] = df["tipo_estudio"].astype(str).str.strip().replace("", "No indicado").str.title()
        orden = ["Clínico", "Oncológico", "No Indicado"]
        color_map = {"Clínico": "#1f77b4", "Oncológico": "#aec7e8", "No Indicado": "#d62728"}
        graficar_pie(df, "tipo_estudio", "Tipo de Estudio", color_map, orden)

    with col2:
        st.markdown("#### Diagnóstico y/o Sospecha Clínica")
        df = run_and_df("SELECT diagnostico_sospecha_clinica FROM tabla_pacientes")
        if not df.empty:
            df = df.assign(
                diagnostico=df["diagnostico_sospecha_clinica"].fillna("").str.strip()
                .replace("", "No indicado").str.split(",")
            ).explode("diagnostico")
            df["diagnostico"] = df["diagnostico"].str.strip().str.title()
            conteos = df["diagnostico"].value_counts().rename_axis("Diagnóstico").reset_index(name="Total")

            fig = px.bar(conteos.head(15), x="Total", y="Diagnóstico", orientation="h")
            fig.update_traces(hovertemplate="<b>Diagnóstico</b>: %{y}<br><b>Total</b>: %{x:,}<extra></extra>")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Solicitudes por mes
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("#### Seguimiento de Solicitudes")
        df = run_and_df("SELECT fecha_solicitud FROM tabla_pacientes WHERE fecha_solicitud IS NOT NULL")

        if not df.empty:
            df["fecha_solicitud"] = pd.to_datetime(df["fecha_solicitud"], errors="coerce")
            df = df.dropna(subset=["fecha_solicitud"])
            df = df[df["fecha_solicitud"].dt.year != 1900].copy()

            if not df.empty:
                df["año"] = df["fecha_solicitud"].dt.year
                df["mes_num"] = df["fecha_solicitud"].dt.month
                meses = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
                         7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}
                df["mes"] = pd.Categorical(df["mes_num"].map(meses), categories=meses.values(), ordered=True)
                año_sel = st.selectbox("Seleccionar año", sorted(df["año"].unique(), reverse=True))
                resumen = df[df["año"] == año_sel].groupby("mes").size().reindex(meses.values(), fill_value=0).reset_index(name="cantidad")
                fig = px.bar(resumen, x="mes", y="cantidad")
                fig.update_traces(hovertemplate="<b>Mes</b>: %{x}<br><b>Solicitudes</b>: %{y}<extra></extra>")
                fig.update_yaxes(dtick=1, title="Cantidad de solicitudes")
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("#### Distribución Geográfica")
        sql = """
        SELECT region_pais, region_provincia 
        FROM tabla_pacientes 
        WHERE region_pais IS NOT NULL OR region_provincia IS NOT NULL
        """
        df = run_and_df(sql)
        if not df.empty:
            df["region_pais"] = df["region_pais"].fillna("Desconocido").str.title()
            df["region_provincia"] = df["region_provincia"].fillna("Desconocido").str.title()
            pais = st.selectbox("Seleccionar país", sorted(df["region_pais"].unique()))
            df_ciudad = df[(df["region_pais"] == pais) & (df["region_provincia"] != "Desconocido")]
            resumen = df_ciudad["region_provincia"].value_counts().reset_index()
            resumen.columns = ["Provincia", "Total"]

            fig = px.bar(resumen.head(15), x="Provincia", y="Total")
            fig.update_layout(
                xaxis_tickangle=0, yaxis_tickformat=',d', yaxis=dict(dtick=1),
                yaxis_title="Cantidad de pacientes"
            )
            fig.update_traces(marker_color='lightskyblue')
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
# FUNCIONES DE CONSULTAS (COMPLETAS)
# =============================================================================

def pagina_consultas() -> None:
    """Página de consultas con todos los modos originales."""
    
    st.markdown("## 🔍 Consultas")
    st.markdown("<hr>", unsafe_allow_html=True)

    # Selector de modo con botones
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("Búsqueda", use_container_width=True,
                     type="primary" if st.session_state.modo == "Búsqueda" else "secondary"):
            st.session_state.modo = "Búsqueda"
            st.session_state.df_result = None
    with col2:
        if st.button("Singles", use_container_width=True,
                     type="primary" if st.session_state.modo == "Singles" else "secondary"):
            st.session_state.modo = "Singles"
            st.session_state.df_result = None
    with col3:
        if st.button("Dúos", use_container_width=True,
                     type="primary" if st.session_state.modo == "Dúos" else "secondary"):
            st.session_state.modo = "Dúos"
            st.session_state.df_result = None
    with col4:
        if st.button("Tríos", use_container_width=True,
                     type="primary" if st.session_state.modo == "Tríos" else "secondary"):
            st.session_state.modo = "Tríos"
            st.session_state.df_result = None

    salto_linea(20)

    # Ejecutar según modo
    if st.session_state.modo == "Singles":
        consulta_singles_completa()
    elif st.session_state.modo == "Dúos":
        consulta_duos_completa()
    elif st.session_state.modo == "Tríos":
        consulta_trios_completa()
    else:
        consulta_busqueda_completa()


def consulta_singles_completa() -> None:
    """Consulta Single con toda la funcionalidad original."""
    
    nombre = st.selectbox(
        "👤 Paciente caso",
        st.session_state.pacientes_nombres,
        index=None,
        placeholder="Seleccione un paciente",
        key="busqueda_paciente_nombre",
        on_change=reset_single,
        help="Si recientemente se incorporó un nuevo paciente y aún no figura, actualice la página."
    )

    if not nombre:
        st.info("Seleccione un paciente para continuar")
        return

    salto_linea(15)
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Panel de genes</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""", 
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1], gap="Large")
    
    with col1:
        servidor_files = (
            sorted([f.name for f in PANEL_DIR.iterdir() if f.suffix.lower() == ".xlsx"])
            if PANEL_DIR.exists() else []
        )
        panel_servidor = st.multiselect(
            "Elegir paneles desde */DATA/NGS/Paneles*",
            options=servidor_files,
            placeholder="Seleccione uno o varios paneles",
            key="panel_paci_servidor",
            help="Seleccioná uno o más paneles de genes disponibles en el servidor."
        )

    with col2:
        salto_linea(30)
        panel_accionable = st.checkbox(
            "Aplicar panel accionable",
            key="panel_acc_paci",
            help="Activa un panel predefinido de genes clínicamente accionables."
        )

    if not panel_servidor and not panel_accionable:
        st.warning("⚠️ Debe seleccionar al menos un panel")
        return

    # Construir genes
    genes_panel = set()
    
    if panel_accionable and PANEL_ACCIONABLE:
        genes_acc = [g.strip().upper() for g in PANEL_ACCIONABLE if g]
        genes_panel.update(genes_acc)
        with st.expander(f"ℹ️ Panel Accionable ({len(genes_acc)} genes)", expanded=False):
            st.markdown(f"<small>{', '.join(sorted(set(PANEL_ACCIONABLE)))}</small>", unsafe_allow_html=True)

    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            lista_genes = [g for g in lista_genes if es_gen_valido(g)]
            genes_panel.update(lista_genes)
            
            with st.expander(f"ℹ️ {nombre_panel} ({len(lista_genes)} genes)", expanded=False):
                st.markdown(f"<small>{', '.join(lista_genes)}</small>", unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"No pude leer el panel {nombre_panel}: {e}")

    if genes_panel:
        validos, faltantes = validate_panel(sorted(genes_panel))
        if faltantes:
            st.warning(f"⚠️ Genes no encontrados ({len(faltantes)}): {', '.join(faltantes)}")
        genes_panel = set(validos + faltantes)

    if not genes_panel:
        st.error("No se pudo construir un conjunto de genes válido")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    col1, col2 = st.columns([2, 8])
    with col1:
        ejecutar = st.button("🚀 Ejecutar consulta", key="btn_buscar_paciente")

    if ejecutar:
        paciente_id = int(
            st.session_state.df_pacientes
            .query("nombre == @nombre")
            .id
            .iloc[0]
        )

        with st.spinner("Procesando consulta..."):
            start = time.time()
            df_base = query_by_patient(paciente_id, sorted(genes_panel))
            st.session_state.df_result = df_base
            elapsed = time.time() - start
            st.info(f"⏱️ Tiempo: {elapsed:.2f}s")

    if st.session_state.df_result is None:
        st.info("Ejecute la consulta para ver resultados")
        return

    df = st.session_state.df_result.copy()

    # Filtros de frecuencia
    salto_linea(15)
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Frecuencia Alélica</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""",
                unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="Large")
    
    with col1:
        fa_numerica = st.selectbox(
            "Umbral de frecuencia alélica",
            ["<5%", "<1%", "Sin filtro"],
            key="fa_numerica"
        )

    with col2:
        fa_estudio = st.selectbox(
            "Tipo de frecuencia alélica",
            ["Total", "Clínico", "Oncológico"],
            key="fa_estudio"
        )

    col_fa = {
        "Total": "freq_alelica",
        "Clínico": "freq_alelica_clinico",
        "Oncológico": "freq_alelica_oncologico"
    }[fa_estudio]

    if col_fa not in df.columns:
        st.warning(f"No se encontró {col_fa}, usando 0")
        df[col_fa] = 0.0

    df[col_fa] = pd.to_numeric(df[col_fa], errors="coerce")
    df = df[df[col_fa] > 0]

    if fa_numerica == "<5%":
        df = df[df[col_fa] <= 0.05]
    elif fa_numerica == "<1%":
        df = df[df[col_fa] <= 0.01]

    if df.empty:
        st.info("No se encontraron variantes con los filtros aplicados")
        return

    st.write(f"**Se encontraron {len(df)} variantes después del filtrado**")

    # Mostrar tabla
    df_view = df.copy()
    for col in df_view.columns:
        if "freq" in col:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").round(5)

    gb = GridOptionsBuilder.from_dataframe(df_view)
    
    column_config = {
        "CHROM": ("CHROM", 90), "POS": ("POS", 80), "REF": ("REF", 60),
        "ALT": ("ALT", 60), "GEN_NAME": ("GEN", 160), "ZYG": ("ZYG", 80),
        "freq_alelica": ("FA Total", 90), "freq_alelica_clinico": ("FA Clínico", 90),
        "freq_alelica_oncologico": ("FA Oncológico", 90),
        "freq_pob_total": ("FP Total", 90), "freq_pob_clinico": ("FP Clínico", 90),
        "freq_pob_oncologico": ("FP Oncológico", 90),
    }

    for col in df_view.columns:
        if col in column_config:
            header, width = column_config[col]
            if col == "GEN_NAME":
                gb.configure_column(col, header_name=header, filter="agTextColumnFilter",
                                   filterParams={"filterOptions": ["contains"]},
                                   minWidth=width)
            else:
                gb.configure_column(col, header_name=header, minWidth=width)

    gb.configure_selection("multiple", use_checkbox=True, header_checkbox=True)
    gb.configure_grid_options(quickFilter=True)
    gb.configure_side_bar()

    grid = AgGrid(
        df_view,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True
    )

    selected = pd.DataFrame(grid["selected_rows"])

    if selected.empty:
        st.warning("Seleccione al menos una variante para descargar")
        return

    st.success(f"{len(selected)} variantes seleccionadas")

    # Descarga VCF
    keys = ["CHROM", "POS", "REF", "ALT"]
    selected_full = df.merge(selected[keys], on=keys, how="inner")

    nombre_trim = nombre.split("_", 1)[0]
    
    paneles_dict = {}
    if panel_accionable and PANEL_ACCIONABLE:
        paneles_dict["panel_accionable"] = sorted([g.strip().upper() for g in PANEL_ACCIONABLE if g])
    
    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            nombre_limpio = Path(nombre_panel).stem.lower().replace(" ", "_")
            paneles_dict[nombre_limpio] = sorted(lista_genes)
        except Exception as e:
            st.warning(f"No pude leer {nombre_panel}: {e}")

    base = f"caso({nombre_trim})_singles"
    vcf_bytes = generate_vcf_bytes(
        selected_full,
        sample_name=nombre,
        paneles_dict=paneles_dict,
        analysis_tag=base
    )

    prefijo = f"caso({nombre_trim})_single"
    sufijo_raw = st.text_input("Texto opcional para el nombre", key="vcf_sufijo_paci")
    sufijo = slugify(sufijo_raw) if sufijo_raw.strip() else ""
    filename = f"{prefijo}_{sufijo}.vcf" if sufijo else f"{prefijo}.vcf"

    st.markdown(f"**Archivo:** `{filename}`")
    st.download_button(
        "📥 Descargar VCF",
        data=vcf_bytes,
        file_name=filename,
        mime="text/vcf",
        key="download_paci"
    )


def consulta_duos_completa() -> None:
    """Consulta Dúo con toda la funcionalidad original."""
    
    A_nombre = st.selectbox(
        "👤 Paciente caso",
        st.session_state.pacientes_nombres,
        index=None,
        placeholder="Seleccione paciente",
        key="duoA",
        on_change=reset_duo
    )
    B_nombre = st.selectbox(
        "👤 Paciente B",
        st.session_state.pacientes_nombres,
        index=None,
        placeholder="Seleccione paciente",
        key="duoB",
        on_change=reset_duo
    )

    if not A_nombre or not B_nombre:
        st.info("Seleccione ambos pacientes")
        return
    
    if A_nombre == B_nombre:
        st.error("Los pacientes deben ser distintos")
        return

    A_base = A_nombre.split("_", 1)[0]
    B_base = B_nombre.split("_", 1)[0]

    opciones_duo = [
        f"Intersección {A_nombre} & {B_nombre}",
        f"Exclusivas {A_nombre}",
        f"Exclusivas {B_nombre}"
    ]
    
    opt_duo = st.selectbox("Seleccionar combinación", opciones_duo, key="opt_duo", on_change=reset_duo)

    # Paneles
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Panel de genes</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""",
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1], gap="Large")
    
    with col1:
        servidor_files = (
            sorted([f.name for f in PANEL_DIR.iterdir() if f.suffix.lower() == ".xlsx"])
            if PANEL_DIR.exists() else []
        )
        panel_servidor = st.multiselect(
            "Elegir paneles",
            options=servidor_files,
            key="panel_servidor_duo"
        )

    with col2:
        salto_linea(30)
        panel_accionable = st.checkbox("Panel accionable", key="panel_accionable_duo")

    if not panel_servidor and not panel_accionable:
        st.warning("Seleccione al menos un panel")
        return

    # Construir genes
    genes_panel = set()
    
    if panel_accionable and PANEL_ACCIONABLE:
        genes_panel.update(g.upper() for g in PANEL_ACCIONABLE if g)
    
    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            lista_genes = [g for g in lista_genes if es_gen_valido(g)]
            genes_panel.update(lista_genes)
        except Exception as e:
            st.warning(f"Error con {nombre_panel}: {e}")

    if genes_panel:
        validos, faltantes = validate_panel(sorted(genes_panel))
        if faltantes:
            st.warning(f"Genes no encontrados: {', '.join(faltantes)}")
        genes_panel = set(validos + faltantes)

    if not genes_panel:
        st.error("No se pudieron obtener genes válidos")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 9])
    with col1:
        ejecutar = st.button("🚀 Ejecutar consulta", key="ejecutar_duo")

    if ejecutar:
        A = int(st.session_state.df_pacientes.query("nombre == @A_nombre").id.iloc[0])
        B = int(st.session_state.df_pacientes.query("nombre == @B_nombre").id.iloc[0])

        with st.spinner("Procesando..."):
            start = time.time()
            
            if opt_duo == opciones_duo[0]:
                df = duo_intersection(A, B, sorted(genes_panel))
            elif opt_duo == opciones_duo[1]:
                df = duo_exclusive_a(A, B, sorted(genes_panel))
            else:
                df = duo_exclusive_b(A, B, sorted(genes_panel))
            
            st.session_state.df_result = df
            elapsed = time.time() - start
            st.info(f"⏱️ Tiempo: {elapsed:.2f}s")

    if st.session_state.df_result is None:
        st.info("Ejecute la consulta para ver resultados")
        return

    df_orig = st.session_state.df_result.copy()
    df = df_orig.copy()

    # Filtros de frecuencia
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Frecuencia Alélica</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""",
                unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="Large")
    
    with col1:
        fa_numerica = st.selectbox(
            "Umbral",
            ["<5%", "<1%", "Sin filtro"],
            key="fa_numerica_duo"
        )
    
    with col2:
        fa_estudio = st.selectbox(
            "Tipo",
            ["Total", "Clínico", "Oncológico"],
            key="fa_estudio_duo"
        )

    col_fa = {
        "Total": "freq_alelica",
        "Clínico": "freq_alelica_clinico",
        "Oncológico": "freq_alelica_oncologico"
    }[fa_estudio]

    if col_fa not in df.columns:
        st.warning(f"No se encontró {col_fa}")
        df[col_fa] = 0.0

    df[col_fa] = pd.to_numeric(df[col_fa], errors="coerce")
    df = df[df[col_fa] > 0]

    if fa_numerica == "<5%":
        df = df[df[col_fa] <= 0.05]
    elif fa_numerica == "<1%":
        df = df[df[col_fa] <= 0.01]

    if df.empty:
        st.info("No hay variantes con los filtros aplicados")
        return

    st.write(f"**Se encontraron {len(df)} variantes**")

    # Mostrar tabla
    cols_to_show = [c for c in COLUMNAS_VARIANTES if c in df.columns]
    df_view = df[cols_to_show].copy()
    
    for col in df_view.columns:
        if "freq" in col:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").round(5)

    gb = GridOptionsBuilder.from_dataframe(df_view)
    
    column_config = {
        "CHROM": ("CHROM", 90), "POS": ("POS", 80), "REF": ("REF", 60),
        "ALT": ("ALT", 60), "GEN_NAME": ("GEN", 160), "ZYG": ("ZYG", 80),
        "freq_alelica": ("FA Total", 90), "freq_alelica_clinico": ("FA Clínico", 90),
        "freq_alelica_oncologico": ("FA Oncológico", 90),
        "freq_pob_total": ("FP Total", 90), "freq_pob_clinico": ("FP Clínico", 90),
        "freq_pob_oncologico": ("FP Oncológico", 90),
    }

    for col in df_view.columns:
        if col in column_config:
            header, width = column_config[col]
            gb.configure_column(col, header_name=header, minWidth=width)

    gb.configure_selection("multiple", use_checkbox=True, header_checkbox=True)
    gb.configure_grid_options(quickFilter=True)

    grid = AgGrid(
        df_view,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True
    )

    selected = pd.DataFrame(grid["selected_rows"])

    if selected.empty:
        st.warning("Seleccione variantes para descargar")
        return

    st.success(f"{len(selected)} variantes seleccionadas")

    # Descarga VCF
    keys = ["CHROM", "POS", "REF", "ALT"]
    selected_full = df_orig.merge(selected[keys], on=keys, how="inner")

    paneles_dict = {}
    if panel_accionable and PANEL_ACCIONABLE:
        paneles_dict["panel_accionable"] = sorted(set(PANEL_ACCIONABLE))
    
    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            nombre_limpio = Path(nombre_panel).stem.lower().replace(" ", "_")
            paneles_dict[nombre_limpio] = sorted(lista_genes)
        except Exception as e:
            st.warning(f"Error con {nombre_panel}: {e}")

    prefijos_nombre = {
        opciones_duo[0]: f"caso({A_base})_{B_base}_int",
        opciones_duo[1]: f"caso({A_base})_{B_base}_exc_{A_base}",
        opciones_duo[2]: f"caso({A_base})_{B_base}_exc_{B_base}",
    }
    base = prefijos_nombre[opt_duo]

    vcf_bytes = generate_vcf_bytes(
        selected_full,
        sample_name=A_nombre,
        paneles_dict=paneles_dict,
        analysis_tag=base
    )

    sufijo_raw = st.text_input("Texto opcional", key="vcf_sufijo_duo")
    sufijo = slugify(sufijo_raw) if sufijo_raw.strip() else ""
    filename = f"{base}_{sufijo}.vcf" if sufijo else f"{base}.vcf"

    st.markdown(f"**Archivo:** `{filename}`")
    st.download_button(
        "📥 Descargar VCF",
        data=vcf_bytes,
        file_name=filename,
        mime="text/vcf",
        key="download_duo"
    )


def consulta_trios_completa() -> None:
    """Consulta Trío con toda la funcionalidad original."""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        A_nombre = st.selectbox(
            "Paciente caso",
            st.session_state.pacientes_nombres,
            index=None,
            key="trioA",
            on_change=reset_trio
        )
    with col2:
        B_nombre = st.selectbox(
            "Paciente B",
            st.session_state.pacientes_nombres,
            index=None,
            key="trioB",
            on_change=reset_trio
        )
    with col3:
        C_nombre = st.selectbox(
            "Paciente C",
            st.session_state.pacientes_nombres,
            index=None,
            key="trioC",
            on_change=reset_trio
        )

    if not A_nombre or not B_nombre or not C_nombre:
        st.info("Seleccione tres pacientes")
        return
    
    if len({A_nombre, B_nombre, C_nombre}) < 3:
        st.error("Los pacientes deben ser distintos")
        return

    A_base, B_base, C_base = [n.split("_", 1)[0] for n in (A_nombre, B_nombre, C_nombre)]

    opciones_trio = [
        f"Intersección {A_nombre} & {B_nombre}",
        f"Intersección {A_nombre} & {C_nombre}",
        f"Intersección {B_nombre} & {C_nombre}",
        f"Intersección {A_nombre} & {B_nombre} & {C_nombre}",
        f"Exclusivas {A_nombre}",
        f"Exclusivas {B_nombre}",
        f"Exclusivas {C_nombre}"
    ]
    opt_trio = st.selectbox("Seleccionar combinación", opciones_trio, key="opt_trio", on_change=reset_trio)

    # Paneles
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Panel de genes</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""",
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1], gap="Large")
    
    with col1:
        servidor_files = (
            sorted([f.name for f in PANEL_DIR.iterdir() if f.suffix.lower() == ".xlsx"])
            if PANEL_DIR.exists() else []
        )
        panel_servidor = st.multiselect(
            "Elegir paneles",
            options=servidor_files,
            key="panel_servidor_trio"
        )

    with col2:
        salto_linea(35)
        panel_accionable = st.checkbox("Panel accionable", key="panel_accionable_trio")

    if not panel_servidor and not panel_accionable:
        st.warning("Seleccione al menos un panel")
        return

    # Construir genes
    genes_panel = set()
    
    if panel_accionable and PANEL_ACCIONABLE:
        genes_panel.update(g.upper() for g in PANEL_ACCIONABLE if g)
    
    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            lista_genes = [g for g in lista_genes if es_gen_valido(g)]
            genes_panel.update(lista_genes)
        except Exception as e:
            st.warning(f"Error con {nombre_panel}: {e}")

    if genes_panel:
        validos, faltantes = validate_panel(sorted(genes_panel))
        if faltantes:
            st.warning(f"Genes no encontrados: {', '.join(faltantes)}")
        genes_panel = set(validos + faltantes)

    if not genes_panel:
        st.error("No se pudieron obtener genes válidos")
        return

    st.markdown("<hr>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 9])
    with col1:
        ejecutar = st.button("🚀 Ejecutar consulta", key="ejecutar_trio")

    if ejecutar:
        A = int(st.session_state.df_pacientes.query("nombre == @A_nombre").id.iloc[0])
        B = int(st.session_state.df_pacientes.query("nombre == @B_nombre").id.iloc[0])
        C = int(st.session_state.df_pacientes.query("nombre == @C_nombre").id.iloc[0])

        with st.spinner("Procesando..."):
            start = time.time()
            
            if opt_trio == opciones_trio[0]:
                df = trio_intersection([A, B], sorted(genes_panel))
            elif opt_trio == opciones_trio[1]:
                df = trio_intersection([A, C], sorted(genes_panel))
            elif opt_trio == opciones_trio[2]:
                df = trio_intersection([B, C], sorted(genes_panel))
            elif opt_trio == opciones_trio[3]:
                df = trio_intersection([A, B, C], sorted(genes_panel))
            elif opt_trio == opciones_trio[4]:
                df = trio_exclusive([A, B, C], A, sorted(genes_panel))
            elif opt_trio == opciones_trio[5]:
                df = trio_exclusive([A, B, C], B, sorted(genes_panel))
            else:
                df = trio_exclusive([A, B, C], C, sorted(genes_panel))
            
            st.session_state.df_result = df
            elapsed = time.time() - start
            st.info(f"⏱️ Tiempo: {elapsed:.2f}s")

    if st.session_state.df_result is None:
        st.info("Ejecute la consulta para ver resultados")
        return

    df_orig = st.session_state.df_result.copy()
    df = df_orig.copy()

    # Filtros de frecuencia
    st.markdown("""<p style="margin:0; font-size:18px; font-weight:600;">Filtrado por Frecuencia Alélica</p>
                <hr style="border:none; height:1px; background-color:#ccc; margin:5px 0 10px 0;">""",
                unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="Large")
    
    with col1:
        fa_numerica = st.selectbox(
            "Umbral",
            ["<5%", "<1%", "Sin filtro"],
            key="fa_numerica_trio"
        )
    
    with col2:
        fa_estudio = st.selectbox(
            "Tipo",
            ["Total", "Clínico", "Oncológico"],
            key="fa_estudio_trio"
        )

    col_fa = {
        "Total": "freq_alelica",
        "Clínico": "freq_alelica_clinico",
        "Oncológico": "freq_alelica_oncologico"
    }[fa_estudio]

    if col_fa not in df.columns:
        st.warning(f"No se encontró {col_fa}")
        df[col_fa] = 0.0

    df[col_fa] = pd.to_numeric(df[col_fa], errors="coerce")
    df = df[df[col_fa] > 0]

    if fa_numerica == "<5%":
        df = df[df[col_fa] <= 0.05]
    elif fa_numerica == "<1%":
        df = df[df[col_fa] <= 0.01]

    if df.empty:
        st.info("No hay variantes con los filtros aplicados")
        return

    st.write(f"**Se encontraron {len(df)} variantes**")

    # Mostrar tabla
    cols_to_show = [c for c in COLUMNAS_VARIANTES if c in df.columns]
    df_view = df[cols_to_show].copy()
    
    for col in df_view.columns:
        if "freq" in col:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").round(5)

    gb = GridOptionsBuilder.from_dataframe(df_view)
    
    column_config = {
        "CHROM": ("CHROM", 90), "POS": ("POS", 80), "REF": ("REF", 60),
        "ALT": ("ALT", 60), "GEN_NAME": ("GEN", 160), "ZYG": ("ZYG", 80),
        "freq_alelica": ("FA Total", 90), "freq_alelica_clinico": ("FA Clínico", 90),
        "freq_alelica_oncologico": ("FA Oncológico", 90),
        "freq_pob_total": ("FP Total", 90), "freq_pob_clinico": ("FP Clínico", 90),
        "freq_pob_oncologico": ("FP Oncológico", 90),
    }

    for col in df_view.columns:
        if col in column_config:
            header, width = column_config[col]
            gb.configure_column(col, header_name=header, minWidth=width)

    gb.configure_selection("multiple", use_checkbox=True, header_checkbox=True)

    grid = AgGrid(
        df_view,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True
    )

    selected = pd.DataFrame(grid["selected_rows"])

    if selected.empty:
        st.warning("Seleccione variantes para descargar")
        return

    st.success(f"{len(selected)} variantes seleccionadas")

    # Descarga VCF
    keys = ["CHROM", "POS", "REF", "ALT"]
    selected_full = df_orig.merge(selected[keys], on=keys, how="inner")

    paneles_dict = {}
    if panel_accionable and PANEL_ACCIONABLE:
        paneles_dict["panel_accionable"] = sorted(set(PANEL_ACCIONABLE))
    
    for nombre_panel in panel_servidor:
        try:
            ruta = PANEL_DIR / nombre_panel
            df_panel = pd.read_excel(ruta, usecols=[0], dtype=str, engine="openpyxl")
            lista_genes = (
                df_panel.iloc[:, 0]
                .dropna()
                .astype(str)
                .str.strip()
                .str.upper()
                .tolist()
            )
            nombre_limpio = Path(nombre_panel).stem.lower().replace(" ", "_")
            paneles_dict[nombre_limpio] = sorted(lista_genes)
        except Exception as e:
            st.warning(f"Error con {nombre_panel}: {e}")

    prefijos_trio = {
        opciones_trio[3]: f"caso({A_base})_{B_base}_{C_base}_int_todos",
        opciones_trio[0]: f"caso({A_base})_{B_base}_{C_base}_int_{A_base}_{B_base}",
        opciones_trio[1]: f"caso({A_base})_{B_base}_{C_base}_int_{A_base}_{C_base}",
        opciones_trio[2]: f"caso({A_base})_{B_base}_{C_base}_int_{B_base}_{C_base}",
        opciones_trio[4]: f"caso({A_base})_{B_base}_{C_base}_exc_{A_base}",
        opciones_trio[5]: f"caso({A_base})_{B_base}_{C_base}_exc_{B_base}",
        opciones_trio[6]: f"caso({A_base})_{B_base}_{C_base}_exc_{C_base}",
    }
    base = prefijos_trio[opt_trio]

    vcf_bytes = generate_vcf_bytes(
        selected_full,
        sample_name=A_nombre,
        paneles_dict=paneles_dict,
        analysis_tag=base
    )

    sufijo_raw = st.text_input("Texto opcional", key="vcf_sufijo_trio")
    sufijo = slugify(sufijo_raw) if sufijo_raw.strip() else ""
    filename = f"{base}_{sufijo}.vcf" if sufijo else f"{base}.vcf"

    st.markdown(f"**Archivo:** `{filename}`")
    st.download_button(
        "📥 Descargar VCF",
        data=vcf_bytes,
        file_name=filename,
        mime="text/vcf",
        key="download_trio"
    )


def consulta_busqueda_completa() -> None:
    """Búsqueda por variante con toda la funcionalidad original."""
    
    tab1, tab2 = st.tabs(["🔤 Formato Franklin/VarSome", "📝 Campos individuales"])

    with tab1:
        variant_text = st.text_input(
            "Buscar variante",
            placeholder="e.g. Chr1:43424519-T-G o chr1-43424519-T-G",
            help="Formatos: Chr1:43424519-T-G, chr1-43424519-T-G, chr1:43424519T>G"
        ).strip()

        salto_linea(20)
        st.markdown("<hr>", unsafe_allow_html=True)

        if st.button("Ejecutar consulta", key="btn_franklin"):
            if not variant_text:
                st.warning("Ingrese una variante")
                return

            # Parsear
            patterns = [
                r"^chr?(\w+)[-:](\d+)([ACGTacgt]+)>([ACGTacgt]+)$",
                r"^(\w+):(\d+):([ACGTacgt]+):([ACGTacgt]+)$",
                r"^(?i)chr([0-9]+|X|Y|M|MT):(\d+)-([ACGT])-([ACGT])$",
                r"^(?i)chr([0-9]+|X|Y|M|MT)-(\d+)-([ACGT])-([ACGT])$"
            ]

            parsed = None
            for pattern in patterns:
                match = re.match(pattern, variant_text)
                if match:
                    parsed = match.groups()
                    break

            if not parsed:
                st.error("Formato no reconocido")
                return

            chrom, pos, ref, alt = parsed
            df = query_by_variant(f"chr{chrom}", int(pos), ref, alt)

            if df.empty:
                st.warning("No se encontraron variantes")
                return

            st.success(f"✅ {len(df)} pacientes encontrados")
            mostrar_resultados_busqueda_completa(df, chrom, pos, ref, alt)

    with tab2:
        c1, c2, c3, c4 = st.columns(4, gap="Large")

        with c1:
            chrom = st.selectbox("CHROM", [str(i) for i in range(1, 23)] + ["X", "Y"])
        with c2:
            pos_text = st.text_input("POS", placeholder="e.g 14653")
        with c3:
            opciones_ref = ["A", "C", "G", "T", "Otra secuencia"]
            ref_choice = st.selectbox("REF", opciones_ref, index=None, placeholder="Elija una opción")
            ref = st.text_input("REF personalizada", placeholder="e.g. ATG", key="ref_text").upper().strip() if ref_choice == "Otra secuencia" else ref_choice
        with c4:
            opciones_alt = ["A", "C", "G", "T", "Otra secuencia"]
            alt_choice = st.selectbox("ALT", opciones_alt, index=None, placeholder="Elija una opción")
            alt = st.text_input("ALT personalizada", placeholder="e.g. GGA", key="alt_text").upper().strip() if alt_choice == "Otra secuencia" else alt_choice

        st.markdown("<hr>", unsafe_allow_html=True)

        if st.button("Ejecutar consulta", key="btn_fields"):
            errores = []
            
            if not pos_text or not pos_text.isdigit() or int(pos_text) < 1:
                errores.append("POS debe ser un número entero válido")
            if not ref or not re.match(r"^[ACGT]+$", ref, re.IGNORECASE):
                errores.append("REF no válida")
            if not alt or not re.match(r"^[ACGT]+$", alt, re.IGNORECASE):
                errores.append("ALT no válida")

            if errores:
                for e in errores:
                    st.error(e)
                return

            df = query_by_variant(f"chr{chrom}", int(pos_text), ref, alt)

            if df.empty:
                st.warning("No se encontraron variantes")
                return

            st.success(f"✅ {len(df)} pacientes encontrados")
            mostrar_resultados_busqueda_completa(df, chrom, pos_text, ref, alt)


def mostrar_resultados_busqueda_completa(df: pd.DataFrame, chrom: str, pos: str, ref: str, alt: str) -> None:
    """Muestra resultados de búsqueda con toda la funcionalidad."""
    
    # Enlaces externos
    col1, col2, col3 = st.columns(3)
    
    franklin_id = f"chr{chrom}-{pos}-{ref}-{alt}"
    varsome_id = f"{chrom}:{pos}:{ref}:{alt}"
    
    col1.markdown(
        f'<a href="https://franklin.genoox.com/clinical-db/variant/snp/{franklin_id}" '
        f'target="_blank"><div style="background:#4a6fa5;padding:10px;border-radius:6px;'
        f'color:white;text-align:center;">🔬 Franklin</div></a>',
        unsafe_allow_html=True
    )
    
    col2.markdown(
        f'<a href="https://varsome.com/variant/hg38/{varsome_id.replace(":","%3A")}?annotation-mode=germline" '
        f'target="_blank"><div style="background:#4a6fa5;padding:10px;border-radius:6px;'
        f'color:white;text-align:center;">🧬 VarSome</div></a>',
        unsafe_allow_html=True
    )
    
    col3.markdown(
        f'<a href="https://www.ncbi.nlm.nih.gov/search/all/?term={varsome_id}" '
        f'target="_blank"><div style="background:#4a6fa5;padding:10px;border-radius:6px;'
        f'color:white;text-align:center;">📚 dbSNP</div></a>',
        unsafe_allow_html=True
    )

    salto_linea(15)

    # Columnas a mostrar
    cols_to_show = [
        "nombre_paciente", "GEN_NAME", "ZYG",
        "freq_alelica", "freq_alelica_clinico", "freq_alelica_oncologico",
        "freq_pob_total", "freq_pob_clinico", "freq_pob_oncologico"
    ]
    cols_presentes = [c for c in cols_to_show if c in df.columns]
    
    df_view = df[cols_presentes].copy()
    
    rename_map = {
        "nombre_paciente": "Paciente",
        "GEN_NAME": "Gen",
        "ZYG": "Zigosidad",
        "freq_alelica": "FA Total",
        "freq_alelica_clinico": "FA Clínico",
        "freq_alelica_oncologico": "FA Oncológico",
        "freq_pob_total": "FP Total",
        "freq_pob_clinico": "FP Clínico",
        "freq_pob_oncologico": "FP Oncológico",
    }
    df_view = df_view.rename(columns={k: v for k, v in rename_map.items() if k in df_view.columns})

    for col in df_view.columns:
        if "FA" in col or "FP" in col:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").round(3)

    st.dataframe(df_view, use_container_width=True)


# =============================================================================
# FUNCIONES DE CREAR PANEL (COMPLETAS)
# =============================================================================

def pagina_crear_panel() -> None:
    """Página para creación de paneles (completa)."""
    
    st.markdown("## 📋 Crear panel de genes")
    st.markdown("<hr>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🖊️ Crear desde base de datos", "📤 Cargar desde Panel App"])

    with tab1:
        crear_panel_desde_bd_completo()

    with tab2:
        cargar_panel_desde_panelapp_completo()


def crear_panel_desde_bd_completo() -> None:
    """Crea panel seleccionando genes de BD (completo)."""
    
    genes = get_cached_gene_names()
    
    if not genes:
        st.warning("No hay genes en la base de datos")
        return

    seleccion = st.multiselect(
        "Seleccionar genes",
        options=genes
    )

    if seleccion:
        df_genes = pd.DataFrame({"panel_genes": seleccion})
        st.dataframe(df_genes)

        st.markdown("<hr>", unsafe_allow_html=True)

        nombre = st.text_input(
            "Nombre del panel",
            placeholder="e.g. PANEL_CARDIO",
            help="Nombre identificador para el panel"
        ).strip().replace(" ", "_")

        if not nombre:
            st.warning("Ingrese un nombre")
            return

        archivo = f"panelGenes_{nombre}.xlsx"
        st.info(f"Se guardará en */DATA/NGS/Paneles* como `{archivo}`")

        if st.button("💾 Guardar panel", type="primary"):
            ruta = PANEL_DIR / archivo
            
            if ruta.exists():
                st.error("Ya existe un panel con ese nombre")
                return

            try:
                PANEL_DIR.mkdir(exist_ok=True)
                datos = df_to_excel_bytes(df_genes, sheet_name="Genes")
                
                with open(ruta, "wb") as f:
                    f.write(datos)
                
                st.success(f"✅ Panel guardado como {archivo}")
                
            except Exception as e:
                st.error(f"Error guardando: {e}")


def cargar_panel_desde_panelapp_completo() -> None:
    """Carga panel desde PanelApp (completo)."""
    
    archivo = st.file_uploader(
        "Cargar panel",
        type=["tsv", "xlsx"],
        help="Archivo de PanelApp UK o Australia"
    )

    if not archivo:
        return

    try:
        if archivo.name.endswith(".tsv"):
            df = pd.read_csv(archivo, sep="\t", dtype=str)
        else:
            df = pd.read_excel(archivo, dtype=str, engine="openpyxl")

        genes_raw = df.iloc[:, 0].dropna().str.strip().tolist()
        genes_validos, genes_faltantes = validate_panel(sorted(set(genes_raw)))

        col1, col2 = st.columns([2, 7], gap="small")
        
        with col2:
            if genes_faltantes:
                st.warning(f"Genes no encontrados: {', '.join(genes_faltantes)}")
            else:
                st.success("✅ Todos los genes son válidos")

        with col1:
            st.dataframe(pd.DataFrame(genes_raw, columns=["panel_genes"]))

        base_nombre = Path(archivo.name).stem.replace(" ", "_")

        if "version" in df.columns:
            version = df["version"].dropna().astype(str).unique()[0]
        else:
            version = "v1.0"

        st.info(f"Versión detectada: **{version}**")
        nombre_sugerido = f"panelApp_{base_nombre}_v{version}"

        if "nombre_panel_usuario" not in st.session_state:
            st.session_state.nombre_panel_usuario = nombre_sugerido

        nombre_final = st.text_input(
            "Nombre del panel",
            value=st.session_state.nombre_panel_usuario,
            key="nombre_panel_input"
        ).strip()

        st.session_state.nombre_panel_usuario = nombre_final

        if not nombre_final:
            st.warning("Ingrese un nombre")
            return

        fecha_creacion = datetime.now().strftime("%Y-%m-%d")
        trazabilidad = f"Original: {archivo.name} | Version: {version} | Fecha: {fecha_creacion}"
        
        nombre_archivo = f"{nombre_final}.xlsx"

        st.markdown("<hr>", unsafe_allow_html=True)

        if st.button("💾 Guardar panel", key="guardar_panelApp", type="primary"):
            destino = PANEL_DIR / nombre_archivo

            if destino.exists():
                st.warning(f"Ya existe un panel con ese nombre")
            else:
                try:
                    df_genes = pd.DataFrame({"panel_genes": genes_raw})

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_genes.to_excel(writer, index=False, sheet_name="genes")
                        
                        # Agregar metadata
                        pd.DataFrame([[trazabilidad]]).to_excel(
                            writer, sheet_name="metadata",
                            index=False, header=False, startrow=0, startcol=0
                        )

                    output.seek(0)

                    with open(destino, "wb") as f:
                        f.write(output.getvalue())

                    st.success(f"✅ Panel guardado como {destino.name}")
                    
                except Exception as e:
                    st.error(f"Error guardando: {e}")

    except Exception as e:
        st.error(f"Error procesando archivo: {e}")


# =============================================================================
# FUNCIONES DE REPORTES (COMPLETAS)
# =============================================================================

def pagina_reportes() -> None:
    """Página de reportes con toda la funcionalidad original."""
    
    st.markdown("## 📄 Reportes")
    st.markdown("<hr>", unsafe_allow_html=True)

    col_vcf, col_csv = st.columns(2, gap="large")
    
    with col_vcf:
        vcf_file = st.file_uploader("Archivo VCF", type=["vcf"])
    
    with col_csv:
        data_file = st.file_uploader(
            "Archivo CSV o Excel",
            type=["csv", "xls", "xlsx"]
        )

    if not vcf_file or not data_file:
        st.info("Suba ambos archivos para comenzar")
        return

    # Validaciones
    paciente_id = extraer_id_paciente_desde_vcf(vcf_file)
    if not paciente_id:
        st.error("No se encontró ID en el VCF")
        return

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                sql = """
                    SELECT nombre_real_paciente, fecha_solicitud,
                           tipo_de_muestra, cap_kit, secuenciador
                    FROM tabla_pacientes
                    WHERE nombre_paciente = %s
                """
                cur.execute(sql, (paciente_id,))
                resultado = cur.fetchone()
    except Exception as e:
        st.error(f"Error consultando BD: {e}")
        return

    if not resultado:
        st.error(f"Paciente {paciente_id} no existe en BD")
        return

    nombre_real, fecha_solicitud, tipo_muestra, cap_kit, secuenciador = resultado
    st.success(f"✅ Paciente {paciente_id} encontrado")

    # Leer CSV
    filename = data_file.name.lower()

    if filename.endswith(".csv"):
        try:
            contenido = data_file.read().decode("utf-8")
        except UnicodeDecodeError:
            data_file.seek(0)
            contenido = data_file.read().decode("latin-1")
        data_file.seek(0)

        lineas = contenido.splitlines()
        header = lineas[0]
        n_cols = header.count(",") + 1
        lineas_validas = [header] + [l for l in lineas[1:] if l.count(",") + 1 == n_cols]
        df_csv = pd.read_csv(io.StringIO("\n".join(lineas_validas)))
    else:
        df_csv = pd.read_excel(data_file)

    if df_csv.empty:
        st.error("Archivo vacío")
        return

    columnas_req = {"Gene", "Chr", "Ref", "Alt", "Zygosity"}
    faltantes = columnas_req - set(df_csv.columns)
    if faltantes:
        st.error(f"Faltan columnas: {faltantes}")
        return

    # Validar variantes
    variantes_csv = extraer_variantes_csv(df_csv)
    variantes_vcf = extraer_variantes_vcf(vcf_file)
    faltantes_vcf = variantes_csv - variantes_vcf

    if faltantes_vcf:
        st.error(f"{len(faltantes_vcf)} variantes del CSV no están en el VCF")
        return

    st.success("✅ Validación exitosa")

    # Mostrar info paciente
    with st.expander("ℹ️ Información del paciente", expanded=False):
        st.text_input("Protocolo", paciente_id.replace("_MODApy", ""), disabled=True)
        st.text_input("Nombre", nombre_real or "No indicado", disabled=True)
        st.text_input("Fecha solicitud", str(fecha_solicitud) if fecha_solicitud else "No indicado", disabled=True)
        st.text_input("Muestra", tipo_muestra or "No indicado", disabled=True)
        st.text_input("Kit", cap_kit or "No indicado", disabled=True)
        st.text_input("Secuenciador", secuenciador or "No indicado", disabled=True)

    paneles_dict = extraer_paneles_y_genes_desde_vcf(vcf_file)

    st.markdown("<hr>", unsafe_allow_html=True)

    df_variantes = leer_csv_seleccionado(df_csv)
    total_encontradas = len(df_variantes)
    st.markdown(f"#### Tabla de variantes ({total_encontradas} encontradas)")

    # Configurar grid
    df_variantes["CIGOSIDAD"] = df_variantes["CIGOSIDAD"].str.upper()
    df_view = df_variantes.copy()

    order_keywords = ["gen", "variante", "predicción", "cigosidad", "frecuencia", "clasificación", "link"]
    
    cols = list(df_view.columns)
    ordered_cols = []
    used = set()
    for kw in order_keywords:
        for c in cols:
            if c in used:
                continue
            if kw in c.lower():
                ordered_cols.append(c)
                used.add(c)
    remaining = [c for c in cols if c not in used]
    display_cols = ordered_cols + remaining
    if display_cols:
        df_display = df_view[display_cols].copy()
    else:
        df_display = df_view.copy()

    # Formatear frecuencias
    freq_keywords = ["freq", "af", "frequency", "frecuencia", "allele"]
    freq_cols = [c for c in df_display.columns if any(k in c.lower() for k in freq_keywords)]
    
    for c in freq_cols:
        df_display[c] = (df_display[c]
                         .astype(str)
                         .str.replace(',', '.', regex=False))
        df_display[c] = pd.to_numeric(df_display[c], errors='coerce').round(6)

    # Configurar grid
    gb = GridOptionsBuilder.from_dataframe(df_display)
    
    if "ALTERNATIVO_VARIANTE" in df_display.columns:
        gb.configure_column("ALTERNATIVO_VARIANTE", hide=True)
    if "LINK" in df_display.columns:
        gb.configure_column("LINK", hide=True)
    
    gb.configure_default_column(resizable=True, filter=True, sortable=True, minWidth=50)
    gb.configure_selection("multiple", use_checkbox=True, header_checkbox=True)

    col_width_map = {
        "VARIANTE": 180, "GEN": 150, "PREDICCIÓN PROTEICA": 150,
        "CIGOSIDAD": 100, "FRECUENCIA ALÉLICA": 250, "CLASIFICACIÓN ACMG": 180,
    }
    for col_name, w in col_width_map.items():
        if col_name in df_display.columns:
            gb.configure_column(col_name, width=w, minWidth=int(w*0.5))

    gb.configure_grid_options(domLayout='normal', rowHeight=35)

    grid = AgGrid(
        df_display,
        gridOptions=gb.build(),
        update_mode='SELECTION_CHANGED',
        theme='streamlit',
        allow_unsafe_jscode=True,
        fit_columns_on_grid_load=True,
    )

    # Procesar selección
    sel_raw = grid.get('selected_rows')
    if sel_raw is None:
        seleccionadas = []
    elif isinstance(sel_raw, list):
        seleccionadas = sel_raw
    elif isinstance(sel_raw, pd.DataFrame):
        seleccionadas = sel_raw.to_dict('records')
    else:
        seleccionadas = []

    metadatos_ph = st.empty()

    # Mostrar metadata de variantes seleccionadas
    for sel in seleccionadas:
        var_str = sel.get("ALTERNATIVO_VARIANTE", "")
        try:
            chrom, pos, ref, alt = var_str.split(":")
            pos = int(pos)
        except ValueError:
            st.warning(f"Formato inválido: {var_str}")
            continue

        df_meta = query_by_variant(f"chr{chrom}", pos, ref, alt)

        nombres = df_meta['nombre_paciente'].unique().tolist() if 'nombre_paciente' in df_meta.columns else []
        
        if nombres:
            df_pac_meta = query_patient_metadata(nombres)
            df_combined = df_meta.merge(df_pac_meta, how='left', on='nombre_paciente')
        else:
            df_combined = df_meta.copy()

        df_display_meta = df_combined.rename(columns={
            'nombre_paciente': 'Paciente',
            'GEN_NAME': 'Gen',
            'ZYG': 'Cigosidad',
            'freq_alelica': 'Frecuencia alélica',
            'freq_poblacional': 'Frecuencia poblacional',
            'fecha_inicio_sintomas': 'Fecha inicio síntomas',
            'edad': 'Edad',
            'diagnostico': 'Diagnóstico',
            'sintomas': 'Síntomas',
            'region_pais': 'País',
            'region_provincia': 'Provincia',
            'sexo_y': 'Sexo'
        })

        display_cols_meta = [
            'Paciente', 'Cigosidad', 'Frecuencia alélica', 'Frecuencia poblacional',
            'Sexo', 'Edad', 'Fecha inicio síntomas', 'Diagnóstico', 'País', 'Provincia'
        ]

        for col in display_cols_meta:
            if col not in df_display_meta.columns:
                df_display_meta[col] = pd.NA

        df_display_meta[display_cols_meta] = df_display_meta[display_cols_meta].fillna('No indicado')

        n_rows = len(df_display_meta)
        
        with st.expander(f"ℹ️ Variante {var_str} ({n_rows} pacientes)", expanded=False):
            st.dataframe(df_display_meta[display_cols_meta], use_container_width=True)

    df_seleccionadas = pd.DataFrame(seleccionadas)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("##### Cierre y descarga del informe")

    col1, col2, col3 = st.columns(3)

    with col1:
        paciente_clean = paciente_id.replace("MODApy", "").strip("_")
        prefijo = f"{paciente_clean}_{datetime.now().strftime('%Y%m%d')}"
        
        st.markdown("<div style='font-size:15px;'>Texto opcional</div>", unsafe_allow_html=True)
        sufijo_raw = st.text_input(" ", value="", placeholder=" ", label_visibility="collapsed", key="sufijo_reporte")
        sufijo = slugify(sufijo_raw) if sufijo_raw.strip() else ""
        filename = f"{prefijo}_{sufijo}.docx" if sufijo else f"{prefijo}.docx"
        st.markdown(f"**Archivo:** `{filename}`")

    with col2:
        cierre = st.selectbox(
            "Estado *",
            options=["Incierto", "Resuelto", "No Resuelto"],
            index=None,
            placeholder="Seleccione estado",
            key="cierre_reporte"
        )

    with col3:
        fecha_cierre = st.date_input(
            "Fecha cierre *",
            value=None,
            format="YYYY/MM/DD",
            key="fecha_cierre"
        )
        
        profesional = st.selectbox(
            "Profesional *",
            options=PROFESIONALES,
            index=None,
            placeholder="Seleccione",
            key="prof_reporte"
        )

    # Validar cierre
    errores_cierre = validar_cierre_informe(cierre, fecha_cierre)
    if errores_cierre:
        for e in errores_cierre:
            st.error(e)
        return

    def _on_download():
        guardar_cierre_del_informe(paciente_id, cierre, fecha_cierre)

    # Botón calcular cobertura
    st.markdown("<hr>", unsafe_allow_html=True)
    
    if st.button("📊 Calcular cobertura", type="secondary"):
        with st.spinner("Calculando coberturas..."):
            resultados_cov = {}
            paneles = list(paneles_dict.keys())
            
            if paneles:
                status = st.empty()
                
                for idx, panel in enumerate(paneles, 1):
                    status.write(f"Procesando: {panel} ({idx}/{len(paneles)})...")
                    try:
                        res = calcular_cobertura_para_informe(
                            paciente_id=paciente_id,
                            paneles_dict={panel: paneles_dict[panel]}
                        )
                        resultados_cov.update(res)
                    except Exception as e:
                        st.warning(f"Error en {panel}: {e}")
                
                status.success(f"✅ Cobertura calculada para {len(paneles)} paneles")
                st.session_state.coberturas = resultados_cov

    # Botón generar informe
    if st.button("📄 Generar informe", type="primary"):
        with st.spinner("Generando informe..."):
            
            # Preparar textos
            if not df_seleccionadas.empty and "CLASIFICACIÓN ACMG" in df_seleccionadas.columns:
                df_tmp = df_seleccionadas.copy()
                df_tmp["CLAS_ES"] = df_tmp["CLASIFICACIÓN ACMG"].apply(traducir_acmg)
                
                clas_pato = df_tmp[df_tmp["CLAS_ES"].str.contains("Patogénic", na=False)]
                clas_vus = df_tmp[df_tmp["CLAS_ES"] == "Significado clínico incierto"]
                
                n_pato = len(clas_pato)
                n_vus = len(clas_vus)
                
                if n_pato > 0:
                    n_txt = numero_a_letras(n_pato)
                    texto_pato = (
                        f"Se encontraron {n_txt} variante{'s' if n_pato != 1 else ''} "
                        f"patogénica{'s' if n_pato != 1 else ''}.\n\n" +
                        "\n\n".join([f"• {row['GEN']}: {row['VARIANTE']}" for _, row in clas_pato.iterrows()])
                    )
                else:
                    texto_pato = "No se encontraron variantes patogénicas ni probablemente patogénicas."

                if n_vus > 0:
                    n_txt = numero_a_letras(n_vus)
                    texto_vus = (
                        f"Se encontraron {n_txt} variante{'s' if n_vus != 1 else ''} "
                        f"de significado clínico incierto.\n\n" +
                        "\n\n".join([f"• {row['GEN']}: {row['VARIANTE']}" for _, row in clas_vus.iterrows()])
                    )
                else:
                    texto_vus = "No se encontraron variantes de significado clínico incierto."
            else:
                texto_pato = "No se encontraron variantes patogénicas."
                texto_vus = "No se encontraron variantes de significado clínico incierto."

            fecha_informe = datetime.now().strftime("%d/%m/%Y")
            
            reemplazos = {
                "{{PACIENTE_ID}}": paciente_clean,
                "{{PACIENTE_NOMBRE}}": nombre_real or "",
                "{{FECHA}}": fecha_solicitud.strftime("%d/%m/%Y") if fecha_solicitud else "",
                "{{FECHA_INFORME}}": fecha_informe,
                "{{TIPO_DE_MUESTRA}}": tipo_muestra or "",
                "{{CLAS_PATO}}": texto_pato,
                "{{CLAS_VUS}}": texto_vus,
                "{{KITYSEQ}}": f"Kit: {cap_kit}. Secuenciador: {secuenciador}",
            }

            # Elegir plantilla
            plantilla = PLANTILLA_VACIA_PATH if df_seleccionadas.empty else PLANTILLA_PATH
            doc = Document(plantilla)

            # Aplicar reemplazos
            reemplazar_texto_en_parrafos(doc, reemplazos)
            reemplazar_texto_en_encabezado(doc, reemplazos)
            reemplazar_texto_en_tablas(doc, reemplazos)

            # Paneles
            paneles_lista = [p for p in paneles_dict.keys() if p.lower() != "panel_accionable"]
            paneles_limpios = [normalizar_nombre_panel(p) for p in paneles_lista]
            insertar_lista_numerada(doc, "{{PANELES}}", paneles_limpios)

            # Anexos con coberturas
            coberturas = st.session_state.get("coberturas", {})
            insertar_anexo_1(doc, "{{ANEXO_1}}", "panel_accionable", paneles_dict, coberturas)
            insertar_anexo_2(doc, "{{ANEXO_2}}", paneles_dict, coberturas)

            # Tabla de variantes
            if not df_seleccionadas.empty:
                cols_excluir = ["CLASIFICACIÓN ACMG", "ALTERNATIVO_VARIANTE"]
                cols_presentes = [c for c in cols_excluir if c in df_seleccionadas.columns]
                df_tabla = df_seleccionadas.drop(columns=cols_presentes)
                
                if "CLAS_ES" in df_seleccionadas.columns:
                    df_tabla = df_tabla.rename(columns={"CLAS_ES": "CLASIFICACIÓN ACMG"})
                
                cols_word = ["LINK", "GEN", "VARIANTE", "PREDICCIÓN PROTEICA", 
                            "CIGOSIDAD", "FRECUENCIA ALÉLICA", "CLASIFICACIÓN ACMG"]
                cols_word = [c for c in cols_word if c in df_tabla.columns]
                
                if cols_word:
                    df_tabla = df_tabla[cols_word]
                
                reemplazar_placeholder_con_tabla(doc, "{{TABLA_VARIANTES}}", df_tabla)

            # Formatear y guardar
            formatear_solo_placeholders(doc, reemplazos, size=10, font_name="Arial")
            
            buffer = BytesIO()
            doc.save(buffer)
            buffer.seek(0)

            # Botón descarga
            st.download_button(
                "📥 Descargar informe",
                data=buffer,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_docx",
                on_click=_on_download
            )


def mostrar_tabla_pacientes() -> None:
    """Muestra tabla de pacientes con filtros."""
    
    try:
        sql = "SELECT * FROM tabla_pacientes;"
        df = run_and_df(sql)

        # Renombrar
        rename_map = {
            "id_paciente": "ID",
            "nombre_paciente": "Protocolo",
            "nombre_real_paciente": "Paciente",
            "fecha_solicitud": "Solicitud",
            "fecha_nacimiento": "Nacimiento",
            "diagnostico_sospecha_clinica": "Diagnóstico",
            "cap_kit": "Kit",
            "secuenciador": "Secuenciador",
            "tipo_de_muestra": "Muestra",
            "sexo": "Sexo",
            "antecedentes_familiares": "Antecedentes",
            "tipo_estudio": "Estudio",
            "fecha_inicio_sintomas": "Inicio síntomas",
            "sintomas": "Síntomas",
            "region_pais": "País",
            "region_provincia": "Provincia",
        }
        df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
        
        if "ID" in df.columns:
            df = df.drop(columns=["ID"])

        # Procesar fechas
        for col in ["Solicitud", "Nacimiento", "Inicio síntomas"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
                df.loc[df[col] == pd.Timestamp("1900-01-01"), col] = pd.NaT
                df[col] = df[col].dt.strftime("%d/%m/%Y")

        # Rellenar nulos
        df = df.fillna("No indicado")

        # Buscador
        busqueda = st.text_input(
            "🔍 Buscar",
            placeholder="Filtrar tabla..."
        )

        if busqueda:
            mask = df.apply(
                lambda row: row.astype(str).str.contains(busqueda, case=False).any(),
                axis=1
            )
            df = df[mask]

        total = len(df)
        st.caption(f"Mostrando {total} registros")

        # Estilo para "No indicado"
        def estilo_no_indicado(val):
            if val == "No indicado":
                return "color: #9e9e9e;"
            return ""

        st.dataframe(
            df.style.applymap(estilo_no_indicado),
            height=500,
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        logger.exception("Error en tabla pacientes")


# =============================================================================
# NAVEGACIÓN PRINCIPAL
# =============================================================================

def main():
    """Función principal."""
    
    st.markdown("""
    <div style="text-align: center; margin-bottom: 1rem;">
        <h1>🧬 Base de Datos de Variantes Genómicas</h1>
    </div>
    """, unsafe_allow_html=True)

    # Navbar
    pages = ["Inicio", "Agregar pacientes", "Crear panel", "Consultas", "Reportes"]
    
    cols = st.columns(len(pages))
    
    for i, page in enumerate(pages):
        with cols[i]:
            is_active = (st.session_state.page == page)
            if st.button(
                page,
                key=f"nav_{page}",
                use_container_width=True,
                type="primary" if is_active else "secondary"
            ):
                st.session_state.page = page
                if page != "Consultas":
                    st.session_state.df_result = None

    st.markdown("<hr>", unsafe_allow_html=True)

    # Renderizar página
    if st.session_state.page == "Inicio":
        pagina_inicio()
    elif st.session_state.page == "Agregar pacientes":
        st.markdown("## 👤 Agregar pacientes")
        st.markdown("<hr>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["📥 Cargar Pacientes", "📋 Tabla de Pacientes"])
        with tab1:
            main_carga_pacientes()
        with tab2:
            mostrar_tabla_pacientes()
    elif st.session_state.page == "Crear panel":
        pagina_crear_panel()
    elif st.session_state.page == "Consultas":
        pagina_consultas()
    else:  # Reportes
        pagina_reportes()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Error fatal")
        st.error(f"Error inesperado: {e}")
