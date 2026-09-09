# Para publicar en la App Store

Estado de lo que hace falta. Marcado lo que ya está hecho y lo que no puedo
hacer yo desde aquí.

## Hecho

- [x] Icono de app de 1024 px (`Assets.xcassets/AppIcon.appiconset`)
- [x] `PrivacyInfo.xcprivacy` en la app y en el widget, declarando el uso de
      UserDefaults del grupo y de las fechas de archivo. Sin recogida de datos
      ni seguimiento
- [x] `ITSAppUsesNonExemptEncryption = false` (evita el cuestionario de cifrado
      en cada envío)
- [x] Solo HTTPS: nada de excepciones de transporte
- [x] La sección de pruebas está entre `#if DEBUG`, así que no viaja en la
      compilación de Release
- [x] Modo oscuro forzado y coherente en app, widgets y Live Activity
- [x] Traducción al inglés (`Localizable.xcstrings`), incluido el nombre visible
- [x] Nombre visible sin marcas ajenas: "Marcador Fantasy" / "Fantasy Scoreboard"

## Pendiente, y lo tienes que hacer tú

- [ ] **Programa de desarrollador de Apple** (99 USD/año). Sin eso no hay envío
- [ ] **Small Business Program**: si facturas menos de 1 M USD, la comisión baja
      del 30 % al 15 %. Es un formulario y se aprueba en días
- [ ] **Bundle ID definitivo** registrado en developer.apple.com. Hoy es
      `dev.calvi.sleeperscore`; si lo cambias, cámbialo también en el widget
      (`.widget`) y en el App Group
- [ ] **Capturas** para 6,7" y 6,1" como mínimo. Se hacen en el simulador con
      ⌘S. Aquí no puedo generarlas
- [ ] **Ficha**: nombre, subtítulo, descripción, palabras clave, categoría
      (Deportes) y URL de soporte
- [ ] **Política de privacidad**: una URL obligatoria aunque no recojas datos.
      `fantasy.calvi.dev/privacidad` serviría
- [ ] **Cuestionario de privacidad** en App Store Connect: marcar "no se
      recopilan datos", coherente con el manifiesto

## Antes del primer envío

- [ ] Subir `MARKETING_VERSION` a 1.0 y `CURRENT_PROJECT_VERSION` a 1
- [ ] Probar la compilación de **Release** en un dispositivo, no solo Debug
- [ ] Revisar que la app arranca **sin liga configurada** y no se ve rota
- [ ] Revisar el comportamiento sin red: debe salir "Datos guardados"
- [ ] Añadir icono para la Live Activity si se quiere personalizar en la isla

## Dos avisos serios

1. **Permiso de Sleeper.** La app se apoya entera en su API pública. Antes de
   publicar —y mucho más antes de cobrar— conviene escribirles y preguntar. Es
   la fuente de todos los datos y la única dependencia real del producto.
2. **Marcas.** Nada de logos de la NFL ni nombres de equipos en el icono, el
   nombre de la app o las capturas. El nombre visible ya es **"Marcador
   Fantasy"** ("Fantasy Scoreboard" en inglés), que evita la marca ajena;
   `SleeperScore` se queda solo como nombre interno del proyecto, que no ve
   nadie. Al crear la ficha en App Store Connect, usa el nombre visible.
