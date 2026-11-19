---
id: ia_web_extraccion_datos
titulo: Extracción de Ficha Comercial IA Web
descripcion: Extrae entidades estructuradas (dueño, empresa, teléfono, ubicación) desde filas tabulares con '|'.
categoria: ia_web
columnas_requeridas: 
columnas_salida: 
version: 1
resultados_json: [{"clave": "propietario", "criterio": "Nombre del dueño o persona de contacto", "entradas": ["datos"], "tipo": "texto", "opciones": []}, {"clave": "negocio", "criterio": "Nombre comercial del negocio", "entradas": ["datos"], "tipo": "texto", "opciones": []}]
creado_en_utc: 2026-10-26T23:31:10.544631+00:00
---
Extrae la ficha comercial de cada registro recibido.
ESTRUCTURA DE ENTRADA:
1. Delimitador de filas: Cada fila/registro esta en una linea separada precedida por '[FILA <id>]:'.
2. Delimitador de columnas: Dentro de cada fila, las columnas estan delimitadas por ' | '.
Usa esta estructura para distinguir exactamente donde termina cada columna y donde cambia de fila.

CAMPOS A EXTRAER:
- propietario: Nombre del dueño o persona de contacto.
- negocio: Nombre de la empresa o negocio comercial.
- categoria: Actividades y servicios que realiza.
- telefono: Número de contacto detectado.
- ubicacion: Ciudad o estado donde opera.
Responde estrictamente en formato JSON con la clave 'resultados'.
