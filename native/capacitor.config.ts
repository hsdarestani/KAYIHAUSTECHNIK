import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'de.kayihaustechnik.app',
  appName: 'KAYI Haustechnik',
  webDir: 'www',
  server: { androidScheme: 'https' },
  ios: { contentInset: 'automatic', preferredContentMode: 'mobile' },
  android: { allowMixedContent: false },
  plugins: { CapacitorHttp: { enabled: true } },
};
export default config;
