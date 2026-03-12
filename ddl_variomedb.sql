-- =====================================================
-- PI-CERCADILLO - VariomeDB
-- Script completo de creación de base de datos
-- Tesis: Desarrollo de algoritmos para el estudio de 
-- alteraciones genéticas de interés en medicina de precisión
-- Autor: Francisco Cercadillo
-- Fecha: 2026
-- =====================================================

-- Eliminar base de datos si existe (con cuidado!)
DROP DATABASE IF EXISTS `variomedb`;

-- Crear base de datos nueva
CREATE DATABASE `variomedb` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `variomedb`;

-- =====================================================
-- TABLA 1: pacientes
-- =====================================================
DROP TABLE IF EXISTS `tabla_pacientes`;

CREATE TABLE `tabla_pacientes` (
  `id_paciente` int(11) NOT NULL AUTO_INCREMENT,
  `nombre_paciente` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nombre_real_paciente` varchar(250) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fecha_solicitud` date NOT NULL DEFAULT '1900-01-01',
  `fecha_nacimiento` date NOT NULL DEFAULT '1900-01-01',
  `diagnostico_sospecha_clinica` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `cap_kit` enum(
    'No indicado',
    'SureSelect V4-post',
    'SureSelect V5-post',
    'SureSelect V6-post',
    'SureSelect V7-post',
    'TWIST 100X',
    'Nextera XT kits'
  ) COLLATE utf8mb4_unicode_ci NOT NULL,
  `secuenciador` enum(
    'No indicado',
    'HiSeq4000',
    'Illumina HiSeq System',
    'Illumina Platform',
    'Novaseq 6000, 150bp PE, Illumina Platform',
    'Novaseq X, 150bp PE, Illumina Platform'
  ) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tipo_de_muestra` enum(
    'No indicado',
    'Sangre'
  ) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sexo` enum(
    '',
    'Femenino',
    'Masculino'
  ) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `antecedentes_familiares` enum(
    'Sí',
    'No',
    'No indicado'
  ) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'No indicado',
  `tipo_estudio` enum(
    '',
    'Clínico',
    'Oncológico'
  ) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '',
  `fecha_inicio_sintomas` date DEFAULT NULL,
  `sintomas` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `region_pais` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `region_provincia` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `cierre_del_informe` enum(
    'Incierto',
    'Resuelto',
    'No Resuelto'
  ) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `fecha_cierre_del_informe` date DEFAULT NULL,
  
  PRIMARY KEY (`id_paciente`),
  UNIQUE KEY `unique_nombre_paciente` (`nombre_paciente`),
  KEY `idx_pac_tipo_estudio` (`tipo_estudio`),
  KEY `idx_pac_sexo` (`sexo`)
) ENGINE=InnoDB AUTO_INCREMENT=641 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- TABLA 2: variantes
-- =====================================================
DROP TABLE IF EXISTS `tabla_variantes`;

CREATE TABLE `tabla_variantes` (
  `id_variante` int(11) NOT NULL AUTO_INCREMENT,
  `CHROM` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `POS` bigint(20) NOT NULL,
  `REF` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ALT` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  `GEN_NAME` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  
  PRIMARY KEY (`id_variante`),
  KEY `idx_variant_coords` (`CHROM`,`POS`,`REF`(100),`ALT`(100)),
  KEY `idx_var_chrom` (`CHROM`),
  KEY `idx_var_gen_name` (`GEN_NAME`),
  FULLTEXT KEY `ft_var_gen_name` (`GEN_NAME`)
) ENGINE=InnoDB AUTO_INCREMENT=60782264 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- TABLA 3: pacientes y variantes (relación muchos a muchos)
-- =====================================================
DROP TABLE IF EXISTS `tabla_pacientes_y_variantes`;

CREATE TABLE `tabla_pacientes_y_variantes` (
  `id_paciente` int(11) NOT NULL,
  `id_variante` int(11) NOT NULL,
  `ZYG` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  
  PRIMARY KEY (`id_paciente`,`id_variante`),
  KEY `idx_pacientes_y_variantes_variante` (`id_variante`),
  
  CONSTRAINT `fk_pacientes_y_variantes_paciente` 
    FOREIGN KEY (`id_paciente`) REFERENCES `tabla_pacientes` (`id_paciente`) ON DELETE CASCADE,
  CONSTRAINT `fk_pacientes_y_variantes_variante` 
    FOREIGN KEY (`id_variante`) REFERENCES `tabla_variantes` (`id_variante`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- TABLA 4: genes
-- =====================================================
DROP TABLE IF EXISTS `tabla_genes`;

CREATE TABLE `tabla_genes` (
  `id_gen` int(11) NOT NULL AUTO_INCREMENT,
  `chrom` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nombre_gen` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `gene_start` int(11) NOT NULL,
  `gene_end` int(11) NOT NULL,
  `gene_stable_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `gene_stable_id_version` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `gen_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  
  PRIMARY KEY (`id_gen`),
  UNIQUE KEY `unq_gene_stable_id_version` (`gene_stable_id_version`)
) ENGINE=InnoDB AUTO_INCREMENT=78650 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =====================================================
-- VERIFICACIÓN
-- =====================================================
SELECT '✅ Base de datos variomedb creada correctamente' AS 'Status';
SELECT 'Tablas creadas:' AS ' ';
SHOW TABLES;
