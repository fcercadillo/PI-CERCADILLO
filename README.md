# PI-CERCADILLO-Desarrollo de algoritmos para el estudio de alteraciones genéticas de interés en medicina de precisión (VariomeDB)

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.28%2B-red)](https://streamlit.io/)
[![GitHub Repo](https://img.shields.io/badge/github-variomedb-black)]([https://github.com/fcercadillo/variomedb](https://github.com/fcercadillo/PI-CERCADILLO)

## Descripción General

**VariomeDB** es una aplicación web integral para la gestión, análisis y visualización de variantes genéticas provenientes de secuenciación masiva (NGS). Diseñada para laboratorios de genética molecular y diagnóstico clínico, facilita el flujo de trabajo desde la carga de pacientes hasta la generación de reportes.

### Características Principales

| Módulo | Funcionalidades |
|--------|-----------------|
| **Gestión de Pacientes** | Carga desde sistema de archivos, validación de metadata, integración VCF |
| **Consultas Avanzadas** | Singles, Dúos, Tríos, búsqueda por variante, filtros por panel y frecuencia |
| **Paneles de Genes** | Creación personalizada, importación desde PanelApp, validación automática |
| **Reportes Clínicos** | Validación cruzada VCF/CSV, selección de variantes, cálculo de cobertura |
| **Visualizaciones** | Estadísticas, distribuciones, seguimiento temporal, mapas geográficos |

## Inicio Rápido

### Prerrequisitos

- Python 3.8 o superior
- MySQL 5.7+ 
- Git
- (Opcional) Entorno virtual
