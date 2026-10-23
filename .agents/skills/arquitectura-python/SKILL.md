---
name: arquitectura-python
description: Crear o modificar módulos Python de PROCESOS_IA, sus contratos y recursos compartidos. Aplicar al organizar responsabilidades o ampliar capacidades existentes.
---

# Arquitectura modular en Python

Leer [las reglas comunes](../../reglas/AGENTS.md). Consultar
[la propuesta de arquitectura](../../proyecto/arquitectura.md) solo si la tarea
la necesita; no convertirla en una estructura aprobada. El análisis de impacto
se aplica antes de cambiar contratos, según el procedimiento común.

## Procedimiento

1. Identificar el caso de uso solicitado y buscar funciones, contratos y consumidores
   existentes antes de añadir código. En un repositorio vacío, declarar que aún
   no existen implementaciones que reutilizar.
2. Elegir la capa responsable y el contrato mínimo. Evitar interfaces para elementos
   triviales que no cruzan un límite ni requieren sustitución durante pruebas.
3. Reutilizar por composición o delegación; extender contratos con compatibilidad.
   Si una migración es imprescindible, localizar todos sus consumidores.
4. Construir los recursos compartidos en arranque y pasarlos como dependencias.
   Especificar propietario, alcance, seguridad de concurrencia y forma de cierre.
5. Mantener el dominio independiente del framework. Los adaptadores traducen
   datos y errores externos a resultados comprensibles para aplicación.
6. Revisar tamaño de archivos y cohesión. Separar una responsabilidad completa
   antes de alcanzar el límite establecido en las reglas comunes.

## Criterios específicos

- Anotaciones de tipos en contratos y funciones públicas; usar estructuras simples
  y preferentemente inmutables para intercambiar datos entre capas.
- No iniciar tareas, conexiones ni lecturas de hardware al importar un módulo.
- No crear metaclases singleton o registros globales para sustituir la inyección.
- Evitar una clase que concentre configuración, UI, instalación e inferencia.
- Manejar errores concretos en el límite apropiado, conservando su causa técnica.
- Usar rutas robustas y separadas del directorio actual; distinguir recursos
  empaquetados de datos modificables del usuario.
- Prohibido hardcodear en código: rutas, puertos, URLs, nombres de modelo, números
  mágicos o textos fijos deben ser siempre configurables o inyectados.
- Almacenamiento centralizado y gestor de rutas: Todo módulo debe canalizar sus
  entradas, salidas y archivos de trabajo mediante `EnrutadorSalidas`.
  La carpeta raíz predeterminada (`PROCESOS_IA_SALIDAS` o la configurada por el usuario en la ventana principal)
  se segmenta de forma determinista en subcarpetas estructuradas: `datos/` (archivos CSV, Excel y datos de entrada),
  `imagenes/` (archivos visuales locales), `analisis/` (enriquecimientos tabulares organizados por subdirectorios de trabajo y fecha),
  `extracciones/` (resultados de Google Lens, Gemini y DeepSeek), `plantillas/`, `conversaciones/`, `reportes/` y `temporales/`.
  Ninguna vista ni servicio debe dispersar archivos en ubicaciones arbitrarias ni asumir `Path.home()` como carpeta por defecto para datos.

## Resultado verificable

El cambio tiene un propietario claro, aprovecha lo existente y puede probarse
sin construir una interfaz ni conectarse a Ollama salvo que la prueba lo requiera.
Los recursos tienen cierre definido y los contratos no dependen de implementaciones.
