# Domek Wonen — Codex Pack v6

Fecha: 12/06/2026  
Objetivo: convertir el plan Domek Wonen v5 en una arquitectura construible con Codex, reduciendo consumo de tokens y eliminando el cuello de botella de cobertura de makelaars.

## Decisión central

El sistema no debe depender de una sola fuente. El harvester NVM actual es una buena base inicial, pero no es suficiente como columna vertebral completa. La arquitectura v6 separa dos conceptos:

1. **Office Discovery Layer**: descubrir makelaars/oficinas y sus webs propias.
2. **Property Discovery Layer**: descubrir viviendas disponibles, aunque el makelaar no esté todavía en la base.

La base inicial de 417 oficinas únicas / 327 koopaanbod_url es válida para arrancar, pero el MVP debe mejorar cobertura con agregadores y plataformas inmobiliarias.

## Estrategia de construcción

Construir por módulos pequeños en Codex, siempre con tests, fixtures HTML y criterios de aceptación. No pedir a Codex que “construya todo”. Cada sesión debe tocar máximo 1 módulo.

## Orden correcto

1. Congelar repo y documentación.
2. Normalizar el CSV actual del harvester.
3. Crear base de datos y tablas.
4. Importar sources.
5. Construir scrapers por fuente/plataforma, no por makelaar individual.
6. Enriquecer con PDOK/BAG/EP-Online.
7. Matching con clientes activos.
8. Notificaciones internas.
9. Dashboard.
10. Validación con 2-3 clientes reales.

## Regla de oro

No se debe depender de Funda scraping. Funda puede usarse como referencia humana o para análisis manual, pero no como job automatizado. Si aparece CAPTCHA, no se intenta evadir.
