# Cobrar por la app: plan para revisar

Borrador para decidir, no algo ya montado. Nada de esto está implementado más
allá del hueco de `Entitlements.swift` y la pantalla `PaywallView`.

## La idea que propusiste

- **Gratis**: un equipo, una liga.
- **Pro (suscripción mensual)**: varias ligas, incluso en plataformas distintas.
- El valor: todo desde la misma app, sin saltar entre Sleeper, Yahoo y ESPN.

Es una buena línea de corte porque **el límite se explica solo**: el usuario topa
con él justo cuando ya ha visto que la app funciona, no antes.

## Qué se paga y qué no

| | Gratis | Pro |
| --- | --- | --- |
| Ligas | 1 | Ilimitadas |
| Plataformas | Una | Todas las integradas |
| Widgets | Todos, de esa liga | Uno por liga |
| Live Activity | Sí | Sí |
| Avisos de anotación | Sí | Sí, de todas las ligas |
| Avisos de lesión | Sí | Sí, de todas |

Recomendación fuerte: **no recortes las notificaciones ni los widgets en el
gratis**. Son el enganche. Lo que se cobra es la *amplitud* (varias ligas), no
el funcionamiento. Una app gratuita que ya avisa bien de una liga es la mejor
publicidad para pagar por las cinco.

## Precio

| Opción | Mensual | Anual | Comentario |
| --- | --- | --- | --- |
| Conservadora | 1,99 € | 14,99 € | Compra por impulso, sin pensarlo |
| **Recomendada** | **2,99 €** | **19,99 €** | Lo normal en apps de fantasy de nicho |
| Alta | 4,99 € | 34,99 € | Solo si añades análisis propio, no solo marcador |

Detalles que importan más que el número:

- **Anual con descuento visible** (~40 % frente a 12 meses). La temporada NFL
  dura 5 meses: mucha gente pagará el año entero por no pensar.
- **Prueba de 7 días** en la suscripción. Que caiga en semana de partidos.
- Apple se queda el **30 %** el primer año y el **15 %** a partir del segundo año
  de un mismo suscriptor. Si entras en el App Store Small Business Program
  (menos de 1 M USD al año) es **15 % desde el principio**: apúntate, es un
  formulario.

## Cómo se implementa (por orden)

1. **App Store Connect**: crear el producto de suscripción auto-renovable
   (grupo "Pro", nivel mensual + anual), rellenar la ficha y adjuntar capturas.
2. **StoreKit 2** en la app: `Product.products(for:)`, `product.purchase()`, y
   escuchar `Transaction.updates`. Son unas 150 líneas.
3. **Verificación**: para uso personal basta `Transaction.currentEntitlements`
   en el dispositivo. Si algún día hay servidor, se valida ahí.
4. **Enchufar el resultado a `EntitlementStore.set(plan:)`**. Ese es el único
   punto que toca el resto de la app: hoy el límite ya funciona contra él.
5. **Restaurar compras** (obligatorio para que Apple lo apruebe).
6. **Pantalla de Pro**: ya está (`PaywallView`), falta el botón real de compra y
   los precios traídos de StoreKit.

Tiempo estimado con el producto ya dado de alta: **un día de trabajo**.

## Riesgos que conviene mirar antes de cobrar

1. **Los términos de Sleeper.** Su API de lectura es pública y gratuita, pero
   cobrar por una app construida encima puede requerir permiso suyo. Es lo
   primero que preguntaría, por correo, antes de publicar. No es un detalle
   menor: es la fuente de todos los datos.
2. **ESPN y NFL.com no tienen API pública.** Cobrar por una integración que
   depende de endpoints no publicados es frágil (pueden romperla mañana) y
   discutible en sus términos. Yahoo, con OAuth oficial, es terreno mucho más
   firme: sería la primera plataforma de pago que yo integraría.
3. **Apple rechaza paywalls confusos.** El límite tiene que verse antes de
   pagar y la suscripción explicar precio, periodo y renovación en la propia
   pantalla.
4. **Marcas registradas.** No usar logos de la NFL ni de los equipos. Los
   avatares de Sleeper son contenido del usuario; los escudos de equipo que hoy
   se usan para las defensas vienen del CDN de Sleeper y conviene revisarlo.

## Lo que yo haría primero

Publicar **gratis, con una liga y sin suscripción**, y mirar cuánta gente la usa
dos domingos seguidos. Añadir el cobro cuando haya alguien a quien cobrarle es
más barato que al revés: si la suscripción está desde el día uno, cada rechazo
de Apple y cada duda de términos retrasa el lanzamiento entero.
