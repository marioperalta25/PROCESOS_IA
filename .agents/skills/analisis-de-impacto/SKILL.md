---
name: analisis-de-impacto
description: Analizar consumidores, contratos y efectos antes de editar código o configuración con comportamiento. Aplicar a cambios de firmas, retornos, errores, nombres y formatos persistidos; ampliar según el alcance.
---

# Análisis de impacto antes de editar

Leer [las reglas comunes](../../reglas/AGENTS.md). Este procedimiento sirve para
distintos lenguajes y agentes; usar las herramientas de búsqueda disponibles.

## Procedimiento proporcional

1. Precisar el cambio observable. Localizar definición y contrato actual: entradas,
   retorno, errores, valores predeterminados, efectos y condiciones que deben conservarse.
2. Buscar consumidores por símbolo, módulo, alias y registro. Seguir el flujo donde
   existan llamadas indirectas: callbacks, señales, eventos, plugins, configuración o reflexión.
   Revisar pruebas, ejemplos y documentación pública si consumen el contrato.
3. Identificar datos persistidos o intercambiados: claves, esquema, rutas, formatos
   y semántica. Un cambio de tipo puede afectar una ventana, serialización y caché
   aunque el nombre de la función permanezca igual.
4. Clasificar alcance: local, entre módulos, persistencia o consumidor externo.
   La incertidumbre no es ausencia de impacto; comprobarla o declararla.
5. Elegir la modificación mínima compatible. Reutilizar funciones existentes.
   Si se necesita migrar, actualizar consumidores accesibles en el mismo incremento;
   usar adaptación de compatibilidad solo si responde a una necesidad real.
6. Seleccionar comprobaciones del contrato y al menos del consumidor afectado
   pertinente. Registrar fallos previos si aparecen; no atribuirlos sin evidencia.
7. Revisar la diferencia final por cambios no previstos y llamadas desactualizadas.
   Si existe Git, aprovecharlo; si no, comparar el contenido disponible.

## Registro mínimo

Antes de la edición, conservar una nota de trabajo breve, proporcional al riesgo:

```text
Cambio solicitado:
Contrato y condición que debe conservarse:
Consumidores comprobados y límites de la búsqueda:
Efectos y compatibilidad:
Comprobación prevista:
```

Un cambio local simple admite una sola frase. La nota puede quedar en la conversación
o estado de trabajo; no crear un documento por cada edición. Un cambio entre módulos
requiere rutas o símbolos comprobados, sin exigir razonamiento interno.

## Casos que necesitan más evidencia

Una búsqueda textual sin resultados no descarta usos dinámicos. Inspeccionar
registro y configuración cuando existan. Si un consumidor externo no es accesible,
preservar el contrato cuando sea viable o declarar el límite y resolver cualquier
decisión que exceda el alcance; no afirmar compatibilidad completa.

Verificar APIs y versiones antes de basar una edición en ellas. Si no se puede
comprobar un dato esencial, detener solo la parte dependiente y explicar qué falta.
No cambiar nombres o llamadas por preferencia personal.

## Resultado

Entregar cambio, consumidores revisados, comprobaciones ejecutadas y limitaciones.
La prueba del símbolo editado por sí sola no demuestra que sus consumidores funcionen.
