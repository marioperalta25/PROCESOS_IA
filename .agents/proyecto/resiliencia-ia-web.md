# Gestor Global de Resiliencia para IA Web

Fecha de creación: 4 de noviembre de 2026.
Ubicación del módulo: `src/procesos_ia/aplicacion/ia_web/comun/gestor_resiliencia_web.py`.

## 1. Propósito y Alcance

El gestor de resiliencia centraliza los mecanismos de tolerancia a fallos, detección de anomalías de red, sanitización de respuestas generadas por modelos de lenguaje y salvaguarda incremental de datos en disco.

Está diseñado de forma transversal y desacoplada del dominio empresarial, lo que permite su importación y reutilización directa en cualquier módulo de automatización web:
- **Modo IA Conversacional**: procesamiento de lotes tabulares con IA interactiva.
- **Google Lens**: consultas visuales, extracción OCR y resolución de anomalías DOM.
- **Navegación automatizada y scrapers**: flujos basados en CDP (Chrome DevTools Protocol) y Playwright/Selenium.

---

## 2. Componentes y Funciones Disponibles

### 2.1 Clasificación de Incidentes (`TipoFalloWeb` y `clasificar_fallo_web`)

Define una taxonomía estandarizada para tipificar fallos en tiempo de ejecución:

```python
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    TipoFalloWeb,
    clasificar_fallo_web,
)

# Valores posibles de TipoFalloWeb:
# - SIN_CONEXION: fallo a nivel de socket o caída del enlace a internet.
# - LIMITE_IA: cuota alcanzada en la interfaz web del modelo.
# - NAVEGADOR_CAIDO: proceso Chrome/Edge terminado o desconexión CDP.
# - LOTE_INCOMPLETO: cantidad insuficiente de filas evaluadas respecto al lote.
# - TIMEOUT_INFERENCIA: tiempo de espera de respuesta agotado.
# - DESCONOCIDO: cualquier otra excepción no catalogada.

tipo = clasificar_fallo_web(excepcion=err, texto_resp=texto_dom)
if tipo == TipoFalloWeb.SIN_CONEXION:
    # Activar rutina de pausa y espera
    ...
elif tipo == TipoFalloWeb.LIMITE_IA:
    # Pausar lote y alertar al operador
    ...
```

### 2.2 Verificación y Espera de Conectividad a Internet

Provee comprobaciones ultraligeras mediante sockets sin llamadas HTTP pesadas ni dependencias externas:

```python
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    verificar_conexion_internet,
    esperar_restablecimiento_conexion,
)

# 1. Comprobacion puntual no bloqueante:
if not verificar_conexion_internet():
    print("[ALERTA] Sin salida a internet.")

# 2. Espera asincrona con sondeo reactivo:
conexion_ok = await esperar_restablecimiento_conexion(
    callback_log=lambda msg: print(msg),
    timeout_max_seg=300.0,  # 5 minutos maximo
    intervalo_seg=4.0,       # chequeo cada 4s
)
if not conexion_ok:
    # Abortar ordenadamente si se supera el tiempo limite
    ...
```

### 2.3 Filtrado y Sanitización Agnóstica de Respuestas de IA

Los LLMs con frecuencia agregan frases de cortesía al inicio o al final (ej. *"Aquí tienes las respuestas"*, *"Listo para el siguiente lote"*). Si el parser evalúa el texto completo como un bloque indivisible, estas frases invalidan el lote completo.

`filtrar_lineas_datos_ia` procesa el texto línea por línea descartando charla conversacional sin depender de nombres de columnas específicos:

```python
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    filtrar_lineas_datos_ia,
    es_linea_conversacional,
)

texto_ia = (
    "Por supuesto, aqui estan los resultados:\n"
    "[FILA 1]: APROBADO | Detalle 1\n"
    "[FILA 2]: RECHAZADO | Detalle 2\n"
    "Quedo a la espera del siguiente lote para continuar."
)

lineas_validas = filtrar_lineas_datos_ia(texto_ia, max_filas=2)
# Resultado: ['[FILA 1]: APROBADO | Detalle 1', '[FILA 2]: RECHAZADO | Detalle 2']
```

### 2.4 Salvaguarda Incremental en Disco (`salvaguardar_progreso_csv`)

Evita la pérdida de datos ante cortes de energía, apagones de máquina o interrupciones forzadas, persistiendo el CSV tras procesar cada lote o elemento:

```python
from pathlib import Path
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import salvaguardar_progreso_csv

ruta_csv = Path("en_proceso/resultado_parcial.csv")
exito = salvaguardar_progreso_csv(filas_acumuladas, ruta_csv)
if exito:
    print("[INFO] Progreso incremental asegurado en disco.")
```

---

## 3. Patrón de Implementación Recomendado

A continuación se muestra el esquema estándar para integrar resiliencia en bucles de procesamiento web (por lotes o elemento por elemento):

```python
from pathlib import Path
from procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web import (
    TipoFalloWeb,
    clasificar_fallo_web,
    esperar_restablecimiento_conexion,
    filtrar_lineas_datos_ia,
    salvaguardar_progreso_csv,
)

async def procesar_flujo_resiliente(elementos, pestana_web, ruta_salida: Path):
    acumulado = []
    
    for idx, item in enumerate(elementos):
        # 1. Comprobacion preventiva de red
        if not await esperar_restablecimiento_conexion():
            print("[ERROR] Red no disponible. Deteniendo procesamiento.")
            break
            
        reintentos = 0
        exito_item = False
        
        while reintentos <= 2 and not exito_item:
            try:
                # 2. Interaccion web / extraccion
                texto_crudo = await enviar_y_esperar_respuesta(pestana_web, item)
                
                # 3. Limpieza de charla conversacional de la IA
                lineas = filtrar_lineas_datos_ia(texto_crudo)
                if not lineas:
                    tipo = clasificar_fallo_web(texto_resp=texto_crudo)
                    if tipo == TipoFalloWeb.LIMITE_IA:
                        print("[ALERTA] Limite de IA alcanzado en la interfaz web.")
                        return acumulado
                    reintentos += 1
                    continue
                
                # 4. Mapeo de datos exitoso
                resultado = parsear_lineas(lineas)
                acumulado.extend(resultado)
                exito_item = True
                
            except Exception as err:
                tipo = clasificar_fallo_web(excepcion=err)
                if tipo == TipoFalloWeb.NAVEGADOR_CAIDO:
                    print("[ERROR] El navegador se cerro inesperadamente.")
                    return acumulado
                reintentos += 1
                
        # 5. Salvaguarda continua tras cada ciclo completado
        salvaguardar_progreso_csv(acumulado, ruta_salida)
        
    return acumulado
```

---

## 4. Guía de Reutilización en Módulos Específicos

### En Google Lens (`src/procesos_ia/aplicacion/ia_web/lens/`):
- Usar `verificar_conexion_internet()` antes de subir imágenes para evitar llamadas colgadas.
- Usar `clasificar_fallo_web(excepcion=err)` al capturar errores de CDP o tiempo de espera en el panel visual.
- Usar `salvaguardar_progreso_csv()` para guardar detecciones imagen por imagen sin esperar al lote final.

### En Futuros Módulos Web (ej. Scrapers o Formularios):
- Importar directamente desde `procesos_ia.aplicacion.ia_web.comun.gestor_resiliencia_web`.
- No reinventar chequeos de socket ni expresiones regulares de cortesía.
- Añadir nuevos tipos de fallo al enum `TipoFalloWeb` si un nuevo servicio web lo requiere.

---

## 5. Reglas y Restricciones de Mantenimiento

1. **Agnosticismo de datos**: Ninguna función de `gestor_resiliencia_web.py` debe depender de nombres de columnas específicas (como `owner`, `negocio`, `telefono`).
2. **Prohibición de emojis**: Toda traza de log o mensaje debe utilizar indicadores de texto corcheteados (`[OK]`, `[ALERTA]`, `[ERROR]`, `[INFO]`).
3. **Límite de líneas físicas**: El archivo debe mantenerse estrictamente bajo 300 líneas.
4. **Pruebas unitarias**: Toda nueva utilidad de resiliencia debe acompañarse de sus pruebas en `pruebas/unitarias/test_gestor_resiliencia_web.py`.

