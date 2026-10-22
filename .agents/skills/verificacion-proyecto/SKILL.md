---
name: verificacion-proyecto
description: Revisar cambios de PROCESOS_IA y comprobar reglas, contratos y criterios de entrega. Aplicar al cerrar incrementos o revisar regresiones concretas.
---

# Verificación del proyecto

Leer [las reglas comunes](../../reglas/AGENTS.md) y el resultado solicitado por el usuario.
La ruta anterior es una propuesta, no un criterio aprobado. Consultar
[los casos del esquema](../../referencias/evaluacion.md) solo al revisar
instrucciones de agentes.

## Procedimiento

1. Identificar cambios y contrato esperado; revisar también consumidores indirectos,
   persistencia y llamadas. Comparar con el análisis de impacto antes de elegir pruebas.
2. Ejecutar las herramientas ya existentes y pertinentes. Si aún no hay código,
   validar documentos, enlaces y estructura sin inventar pruebas de aplicación.
3. Comprobar idioma, tamaño de archivos, dependencias entre capas, reutilización
   de lógica y cierre de los recursos afectados.
4. Probar efectos observables y fallos relevantes del incremento. No repetir
   toda la batería sin un cambio o riesgo que lo justifique.
5. Contrastar con el encargo vigente. Distinguir fallos nuevos de fallos previos
   comprobados y declarar consumidores o entornos que no se pudieron verificar.

## Comprobaciones según el cambio

| Cambio | Evidencia útil |
| --- | --- |
| Contrato o caso de uso | Resultado normal y error relevante con adaptador sustituible |
| Arranque | Apertura sin instalación, descarga ni carga de modelos |
| Ollama | Conexión fallida, modelo ausente, transmisión interrumpida y cancelación |
| Instalador | Plan autorizado, fallo, reutilización y verificación del resultado |
| Interfaz | Respuesta durante trabajo lento, teclado y escalado pertinente |
| Rendimiento | Condiciones reproducibles y comparación con medición inicial |
| Habilidades | Metadatos válidos, activación precisa, enlaces y escenarios conductuales |
| Memoria | Fuente, fecha, estado vigente y propuestas sin convertir en acuerdos |

## Alcance y herramientas

Las pruebas unitarias deben funcionar sin Ollama, GPU ni red mediante dependencias
inyectadas. Separar las pruebas de integración que sí necesiten esos recursos y
explicar sus requisitos. Las pruebas ordinarias no instalan software ni modelos.

Cuando se implemente código, incorporar el recuento automatizado de líneas y
herramientas de formato, análisis y pruebas compatibles con el entorno elegido.
No crear un archivo de configuración que finja validaciones todavía inexistentes.

## Resultado verificable

Informar archivos o capacidades cambiadas, comprobaciones ejecutadas y resultado.
Separar lo comprobado de lo pendiente; no presentar simulaciones de hardware como
aceleración real ni una revisión estática como una prueba completa de interfaz.
