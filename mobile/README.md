# Recordatin Android (APK)

App nativa (Capacitor) que abre `https://spentor.app/paciente/` y programa
**notificaciones locales** en el teléfono (más precisas que solo Web Push).

## APK listo

Tras el último build:

`mobile/dist/Recordatin-debug.apk` (~3.6 MB)

También en:

`mobile/android/app/build/outputs/apk/debug/app-debug.apk`

## Instalar en el celular

1. Copie el APK al teléfono e instálelo (permitir orígenes desconocidos).
2. Abra **Recordatin** e inicie sesión.
3. En **Mis medicinas** → **Activar alarmas en este celular**.
4. Acepte notificaciones y, si Android lo pide, alarmas exactas.

## Importante

La app carga la web de producción. Debe desplegar en el servidor el
`paciente/static/paciente/js/alarmas.js` actualizado (detecta Capacitor y
programa alarmas nativas). Sin ese deploy, el APK abre Recordatin pero las
alarmas locales no se activan.

## Regenerar el APK

```powershell
cd mobile
$env:JAVA_HOME = "C:\Program Files\Android\Android Studio\jbr"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
npm run sync
cd android
.\gradlew.bat assembleDebug
copy app\build\outputs\apk\debug\app-debug.apk ..\dist\Recordatin-debug.apk
```

## App Links (QR → app)

Tras desplegar el servidor, debe existir:

`https://spentor.app/.well-known/assetlinks.json`

Con la APK debug reinstalada, al escanear un QR de paciente
(`…/paciente/entrar/…`) Android puede abrir **Recordatin** en lugar del navegador.
La primera vez puede preguntar “abrir con…”: elija Recordatin y **Siempre**.
