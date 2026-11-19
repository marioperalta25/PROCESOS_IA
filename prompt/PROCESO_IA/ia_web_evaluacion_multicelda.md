---
id: ia_web_evaluacion_multicelda
titulo: Evaluación Multi-Columna IA Web
descripcion: Plantilla general para evaluar varias celdas/columnas delimitadas con '|' en DeepSeek, Gemini y Modo IA.
categoria: ia_web
columnas_requeridas: 
columnas_salida: 
version: 1
resultados_json: [{"clave": "calificacion", "criterio": "Evaluación integral del registro", "entradas": ["datos"], "tipo": "texto", "opciones": ["Aceptable", "Observado", "Descartado"]}, {"clave": "motivo", "criterio": "Justificación de la evaluación", "entradas": ["datos"], "tipo": "texto", "opciones": []}]
creado_en_utc: 2026-10-26T23:31:10.543249+00:00
---
Analiza detenidamente la información proporcionada para cada registro.
ESTRUCTURA DE ENTRADA:
1. Delimitador de filas: Cada fila/registro esta en una linea separada precedida por '[FILA <id>]:'.
2. Delimitador de columnas: Dentro de cada fila, las columnas estan delimitadas por ' | '.
Usa esta estructura para distinguir exactamente donde termina cada columna y donde cambia de fila.

INSTRUCCIONES:
1. Evalúa la información según el objetivo requerido.
2. Clasifica y valida la coherencia entre los campos del registro.
3. Responde estrictamente en formato JSON con la clave 'resultados'.
