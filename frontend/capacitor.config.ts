import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'ru.meterapp.app',
  appName: 'MeterApp',
  webDir: 'dist',
  server: {
    // После деплоя backend укажите URL API, например:
    // url: 'https://your-backend.onrender.com',
    // cleartext: true только для http в отладке
    androidScheme: 'https',
  },
  android: {
    allowMixedContent: true,
  },
}

export default config
