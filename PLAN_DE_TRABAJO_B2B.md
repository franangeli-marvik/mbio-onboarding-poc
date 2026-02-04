# Plan de Trabajo: Plataforma de Entrevistas B2B Multi-Tenant

Este documento resume el giro estratégico del proyecto hacia un modelo B2B para recruiters y define el roadmap técnico para soportar múltiples "tenants" y configuraciones personalizadas.

## 🎯 Visión Estratégica (Update Feb 4, 2026)

*   **Modelo de Negocio:** B2B (Recruiting Agencies) en lugar de B2C (Candidatos directos).
*   **Valor:** Herramienta de productividad para recruiters que automatiza y estandariza la primera entrevista técnica/cultural.
*   **Diferenciador:** Capacidad de "inyectar" la personalidad y criterios específicos de cada agencia (Tenant) en el agente de IA.

## 🏗 Arquitectura Multi-Tenant de Prompts

El sistema operará con una arquitectura de prompts en capas:

1.  **System Prompt (Nivel Marvik):** Lógica base universal. Detección de dominios (Tech, Finance, Mkt), extracción de gaps, análisis de completitud (XYZ).
2.  **Tenant Prompt (Nivel Cliente):** Configuración específica de la agencia.
    *   *Tone:* Formal, Casual, Agresivo.
    *   *Focus:* Hard Skills, Culture Fit, Sales Quotas.
    *   *Custom Instructions:* Reglas de negocio específicas (ej. "Siempre preguntar por huecos laborales de >3 meses").
3.  **User Context (Nivel Candidato):** El CV parseado y la información del usuario.

## 📅 Roadmap de Entregables

### Hito 1: Iteración Funcional V2 (Deadline: Viernes 6 Feb)
Objetivo: Tener el backend listo para pruebas internas con Daniel.

*   [ ] **Esquemas de Datos Actualizados:**
    *   Soporte para `TenantConfig` (ID, nombre, foco, instrucciones).
    *   Soporte para `SoftSkillsInference` (detectar liderazgo/comunicación).
    *   Soporte para `DomainDetection` (clasificar si es Finanzas, Tech, Ventas).
*   [ ] **Pipeline de Agentes Mejorado:**
    *   **Profile Analyzer:** Capaz de inferir soft skills y detectar el dominio profesional.
    *   **Question Planner:** Capaz de leer el `TenantConfig` y ajustar las preguntas (ej. si el tenant es "Tech Hardliner", ignorar preguntas de cultura).
*   [ ] **Pruebas de Estrés:**
    *   Validar con CVs de prueba (ej. el de Francesco) simulando 2 Tenants distintos.

### Hito 2: Preparación para Demo Recruiter (Deadline: Martes 11 Feb)
Objetivo: Demo estable para presentar a un recruiter de Finanzas real.

*   [ ] **Ingesta de CVs de Daniel:**
    *   Procesar versión "Tech Management".
    *   Procesar versión "Sales Enablement".
*   [ ] **Simulación de Escenarios:**
    *   Generar entrevistas diferenciadas para ambos perfiles.
    *   Asegurar que el vocabulario de Finanzas/Ventas sea correcto (no alucinar términos técnicos).

## 🛠 Cambios Técnicos Requeridos

### 1. Actualización de Schemas (`schemas.py`)
- [x] Agregar `TenantConfig`
- [x] Agregar `SoftSkillItem` y `domain` a `ProfileAnalysis`

### 2. Actualización de Prompts (`prompts.py`)
- [ ] Inyectar `tenant_config` en el System Prompt de todos los agentes.
- [ ] Agregar heurísticas para dominios no técnicos (Finanzas, Mkt).
- [ ] Agregar lógica de "XYZ Impact" para validar seniority.

### 3. Pipeline Orchestrator (`pipeline.py`)
- [ ] Modificar `run_interview_prep_pipeline` para aceptar `tenant_config` como argumento opcional.

---
*Documento vivo - Actualizar según feedback de demos.*
