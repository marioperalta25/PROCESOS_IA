---
id: ia_web_calificacion_leads
titulo: Calificación de Leads IA Web
descripcion: Clasifica prospectos y leads evaluando campos de contacto y actividad separados por '|'.
categoria: ia_web
columnas_requeridas: 
columnas_salida: 
version: 1
resultados_json: [{"clave": "prioridad", "criterio": "Prioridad de contacto comercial", "entradas": ["datos"], "tipo": "texto", "opciones": ["Alta", "Media", "Baja"]}, {"clave": "rubro", "criterio": "Actividad comercial detectada", "entradas": ["datos"], "tipo": "texto", "opciones": []}]
creado_en_utc: 2026-10-26T23:31:10.544116+00:00
---
Evalúa el siguiente lote de prospectos (leads) comerciales.
ESTRUCTURA DE ENTRADA:
1. Delimitador de filas: Cada fila/registro esta en una linea separada precedida por '[FILA <id>]:'.
2. Delimitador de columnas: Dentro de cada fila, las columnas estan delimitadas por ' | '.
Usa esta estructura para distinguir exactamente donde termina cada columna y donde cambia de fila.

OBJETIVOS:
- Determinar si cuenta con nombre, apellido o añgun identificador que diga que habla espanol o bien es latino.
- Asignar prioridad de seguimiento: apellido latino,nombre latino o habla espanol.
Responde únicamente en formato JSON con la estructura:
{"resultados": [{"id": ..., "prioridad": ""apellido latino,nombre latino o habla espanol"", ""...", "motivo": "..."}]}
