---
name: rendimiento-local
description: Diagnosticar uso de GPU integrada, memoria y latencia de PROCESOS_IA. Aplicar a mediciones puntuales, elección de límites y optimizaciones del procesamiento local.
---

# Rendimiento y recursos locales

Leer [las reglas comunes](../../reglas/AGENTS.md),
[las decisiones pendientes](../../proyecto/decisiones.md) y
[los parámetros](../../proyecto/proyecto.toml).

## Procedimiento

1. Definir qué se quiere medir y por qué: tiempo de arranque, primera respuesta,
   velocidad de generación, RAM, memoria compartida o uso de GPU.
2. Recopilar solo los datos necesarios, por acción puntual. Registrar sistema,
   GPU exacta, controladores y versión de Ollama pertinentes al resultado.
3. Consultar el soporte oficial de ese conjunto. Diferenciar incompatibilidad
   conocida, falta de evidencia y aceleración confirmada.
4. Establecer una medición inicial con un modelo existente y carga acotada.
   Si hace falta descargar, pasar por la elección explícita del usuario.
5. Comparar cambios manteniendo modelo, cuantización, contexto, entrada y condiciones
   equivalentes. Separar carga inicial del modelo y ejecución con modelo residente.
6. Ajustar una variable relevante y conservar solo mejoras medidas que no degraden
   estabilidad, memoria disponible o respuesta de la interfaz.

## Criterios específicos

- Una gráfica integrada puede compartir memoria con CPU; no contar dos veces
  la misma memoria como capacidad independiente disponible para modelos.
- La GPU presente no demuestra que Ollama la esté utilizando. Buscar evidencia
  del backend y del reparto de carga durante la inferencia.
- Usar límites de concurrencia comprobados o un experimento acotado autorizado;
  los parámetros propuestos no son acuerdos. Limitar colas y no aumentar trabajo
  simultáneo para mejorar artificialmente una cifra de rendimiento.
- No fijar tamaño de modelo o contexto antes de conocer recursos y presión de memoria.
- Usar caché de diagnóstico con fecha, versión y condiciones relevantes. Invalidarla
  tras cambios conocidos o fallos pertinentes; ofrecer actualización manual.
- No agregar vigilancia continua o sondeos frecuentes para una necesidad puntual.
- No activar variables experimentales, cambiar controladores o alterar el servicio
  de Ollama sin un plan concreto acorde con el control del usuario.

## Resultado verificable

Registrar condiciones, método y resultados sin datos privados de conversación.
Distinguir hechos de inferencias y anotar limitaciones. Proponer presupuestos
medibles de arranque, memoria y latencia basados en el equipo real.

Fuente de consulta: [soporte de hardware de Ollama](https://docs.ollama.com/gpu).
