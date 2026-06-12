# Discovery Sources Registry

## Objetivo

Este registry manual define las fuentes iniciales para ampliar cobertura de makelaars y woningaanbod en Noord-Brabant antes de construir scrapers de viviendas. Su funcion es separar claramente:

- fuentes para importar o enriquecer el censo de oficinas;
- fuentes para descubrir propiedades que revelen nuevos makelaars;
- fuentes que solo deben usarse con revision manual.

Este modulo no ejecuta scraping, no hace llamadas externas y no cambia el importador actual.

## Reglas operativas

- `allowed_use` usa un unico valor principal por fuente para evitar ambiguedad en etapas posteriores.
- `requires_manual_review=true` significa que la fuente no debe pasar a automatizacion sin validacion humana de estructura, cobertura o restricciones.
- Las fuentes agregadoras sirven para discovery y benchmarking, no como verdad canonica del inventario de makelaars.

## Funda policy

- Funda is not an automated scraping source.
- It can only be used as manual benchmark/reference.
- No captcha bypass.
- No recurring automated extraction.

## Fuentes iniciales

| Source | Para que sirve | Que esperamos extraer | Riesgo principal | Automatizacion / revision |
| --- | --- | --- | --- | --- |
| Existing NVM harvester seed | Base inicial ya procesada para arrancar el censo y medir mejora frente al estado actual. | Nombre de oficina, website, root domain, plaats, provincia, koopaanbod URL y flags de review. | Cobertura parcial, duplicados residuales y koopaanbod URL sospechosas o faltantes. | Se puede reutilizar como `seed_import` sin scraping nuevo; no requiere revision previa para cargarlo. |
| NVM official makelaar search | Ampliar oficinas NVM fuera del seed y contrastar miembros activos. | Oficinas, perfil de makelaar, plaats, website y senales de membresia. | Cambios de estructura, filtros regionales y posibles restricciones futuras. | Candidato a automatizacion posterior, pero ahora queda en revision manual. |
| NVM Brabant Noord-Oost regional page | Capturar oficinas de la region noreste con mejor granularidad territorial. | Oficinas, websites, plaats y contexto regional. | La URL regional puede cambiar o no listar todas las oficinas relevantes. | Requiere revision manual antes de convertirla en extractor estable. |
| NVM Brabant Zuidoost regional page | Cubrir Eindhoven y el sudeste, donde puede haber densidad alta de oficinas. | Oficinas, websites, plaats y datos de contacto visibles. | Estructura regional distinta a la del buscador general y cobertura no homogenea. | Revision manual obligatoria antes de automatizar. |
| NVM West-Brabant / regional search placeholder | Mantener explicito el hueco de discovery regional pendiente de confirmar. | Patrones de busqueda regional y candidatas a URL definitiva. | URL exacta no confirmada y riesgo de apuntar a una pagina incorrecta o incompleta. | No automatizable todavia; es un placeholder de `manual_review`. |
| Vastgoed Nederland main site | Descubrir makelaars no NVM mediante directorio o paginas de asociacion. | Miembros, paginas de oficina, websites y senales de afiliacion. | Permisos de uso y estructura interna por revisar; puede mezclar contenido institucional y directorio. | Debe revisarse manualmente antes de disenar automatizacion. |
| Vastgoed Nederland aanbod | Descubrir oficinas desde propiedades ya publicadas por miembros de la asociacion. | URLs de propiedades, nombres de makelaar, locaties y enlaces de oficina cuando existan. | Duplicados, mezcla de listings y dependencia de paginas intermedias. | Util para property discovery; revision manual obligatoria antes de scraping futuro. |
| Huislijn Noord-Brabant koopwoningen | Agregador provincial para identificar aanbod activo y makelaars visibles. | URLs de propiedad, makelaar, plaats, precio y metadata basica. | Duplicidad con otras plataformas y atribucion inconsistente del makelaar. | Automatizable mas adelante, pero por ahora queda en revision manual. |
| Huispedia Noord-Brabant koopwoningen | Capa complementaria para detectar propiedades y oficinas que no aparezcan en otros directorios. | URLs de propiedad, direcciones, nombres de makelaar y contexto de mercado. | Estructura cambiante y mezcla de datos editoriales con listings. | Requiere revision manual previa. |
| Pararius Noord-Brabant koopwoningen | Fuente complementaria para koopwoningen con visibilidad de makelaar en ciertos listings. | URLs de propiedad, lugares, makelaar y pricing metadata. | Cobertura desigual por ciudad y posible foco mas fuerte en alquiler en otras areas del sitio. | Se trata como discovery complementario con revision manual. |
| Google/Bing controlled gemeente queries | Cerrar huecos de cobertura por gemeente cuando los directorios no alcanzan. | Dominios candidatos, nombres de oficina, patrones de busqueda y municipios faltantes. | Alto ruido, resultados variables y necesidad de trazabilidad del metodo usado. | No debe automatizarse sin reglas muy controladas; requiere revision manual resultado por resultado. |
| Manual advisor input from Domek | Incorporar conocimiento local interno y correcciones de negocio. | Nombres de oficina, websites, aanbod URLs, prioridades y notas operativas. | Sesgo manual, formatos inconsistentes y necesidad de normalizacion posterior. | Es manual por definicion y debe conservar trazabilidad de quien aporto cada dato. |
| Funda Noord-Brabant benchmark only | Referencia manual para contrastar cobertura publica aproximada. | Solo conteo benchmark aproximado publico; sin extraccion de datos. | Riesgo de mal uso si se trata como fuente automatizable o si se intenta bypass de captcha. | Solo `benchmark_only;no_automated_scraping`, con revision manual obligatoria. |

## Como usar este registry en la siguiente fase

- Priorizar fuentes `priority=1` para ampliar cobertura de oficinas y websites.
- Usar las fuentes agregadoras solo para descubrir candidatos y enriquecer senales.
- Registrar siempre el origen exacto cuando una fuente produzca una oficina o una propiedad candidata.
- Mantener separado el discovery de makelaars del discovery de propiedades hasta que exista deduplicacion razonable.

## Fuera de alcance en este modulo

- No se ejecuta scraping.
- No se hacen llamadas externas.
- No se anade dashboard.
- No se anade Supabase.
- No se modifica `data/raw` ni `data/processed`.
- No se integra Funda como fuente de scraping.
