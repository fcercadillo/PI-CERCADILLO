# PI-CERCADILLO - VariomeDB
### Desarrollo de algoritmos para el estudio de alteraciones genéticas de interés en medicina de precisión

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.40.1-red)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub](https://img.shields.io/badge/github-PI--CERCADILLO-black)](https://github.com/fcercadillo/PI-CERCADILLO)

---

## Descripción

**VariomeDB** es una aplicación web para la gestión, análisis y visualización de variantes genéticas provenientes de secuenciación masiva (NGS). Diseñada para laboratorios de genética molecular y diagnóstico clínico.

### Características

| Módulo | Funcionalidades |
|--------|-----------------|
| **Pacientes** | Carga desde archivos, validación de metadata, integración VCF |
| **Consultas** | Singles, Dúos, Tríos, búsqueda por variante, filtros por panel |
| **Paneles** | Creación personalizada, importación desde PanelApp |
| **Reportes** | Validación VCF/CSV, selección de variantes, cobertura |
| **Dashboard** | Estadísticas, distribuciones, mapas geográficos |

---

## Instalación Rápida

### Prerrequisitos
- Python 3.8 o superior
- MySQL 5.7+
- Git

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/fcercadillo/PI-CERCADILLO.git
cd PI-CERCADILLO

# 2. Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate       

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar base de datos
mysql -u root -p < scripts/setup_database.sql

# 5. Ejecutar la app
streamlit run src/variomedb_app.py --server.address 0.0.0.0 --server.port 8501
