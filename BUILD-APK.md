# Как получить приложение на Android

В облачной среде разработки **нельзя** собрать готовый `.apk` (нет Android SDK, ~нескольких ГБ).
Ниже два рабочих способа.

---

## Способ A — быстро, без APK (рекомендуется сейчас)

MeterApp уже **PWA**. На телефоне Android:

1. Запустите backend + frontend на компьютере **или** задеплойте в интернет (см. DEPLOY.md).
2. На телефоне в **Chrome** откройте сайт (например `http://192.168.x.x:5173` в той же Wi‑Fi или ваш URL после деплоя).
3. Меню Chrome (⋮) → **«Установить приложение»** / **«На экран «Домой»»**.
4. Иконка MeterApp появится как обычное приложение.

Минус: телефон должен «видеть» сервер (локальная сеть или интернет-деплой).

---

## Способ B — настоящий APK через Android Studio (на вашем Windows)

### Что установить на ПК

1. **Node.js 20+** — https://nodejs.org  
2. **Android Studio** — https://developer.android.com/studio  
   При установке отметьте Android SDK, SDK Platform 34+, Build-Tools.
3. Backend должен быть **доступен с телефона** (деплой на Render и т.п., не `localhost`).

### Команды (PowerShell)

```powershell
cd C:\Projects\PLAT\meter-app\frontend

# Указать URL вашего backend (обязательно для APK!)
$env:VITE_API_URL = "https://ВАШ-BACKEND.onrender.com"

npm install
npm install @capacitor/core @capacitor/cli @capacitor/android --save
npm run build
npx cap add android
npx cap sync android
npx cap open android
```

Откроется **Android Studio**:

1. Дождитесь Gradle Sync.
2. Меню **Build → Build Bundle(s) / APK(s) → Build APK(s)**.
3. Готовый файл обычно здесь:

```text
frontend\android\app\build\outputs\apk\debug\app-debug.apk
```

Скопируйте `app-debug.apk` на телефон и установите (разрешите «Установка из неизвестных источников»).

### Release (подписанный) APK

В Android Studio: **Build → Generate Signed Bundle / APK** → создайте keystore → APK.
Такой файл можно распространять или выложить в Google Play (нужен аккаунт разработчика).

---

## Важно про API

Приложение в APK **не использует** `localhost` компьютера.
Перед `npm run build` задайте:

```powershell
$env:VITE_API_URL = "https://ваш-сервер"
```

Без этого регистрация и данные с телефона не заработают.

---

## Итог

| Цель | Что делать |
|------|------------|
| Пользоваться уже сейчас | Способ A (PWA) |
| Файл `.apk` на телефон | Способ B (Android Studio у вас) |
| Google Play | Signed release APK + аккаунт разработчика |

Конфиг Capacitor уже лежит в `frontend/capacitor.config.ts` (`appId`: `ru.meterapp.app`).
