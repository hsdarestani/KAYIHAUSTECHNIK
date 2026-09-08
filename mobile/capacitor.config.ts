import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'sbs.smarbiz.kayi',
  appName: 'KAYI Haustechnik',
  webDir: 'www',
  server: { url: 'https://kayi.smarbiz.sbs/app/', cleartext: false, allowNavigation: ['kayi.smarbiz.sbs'] },
  plugins: {
    SplashScreen: { launchShowDuration: 1200, backgroundColor: '#0b111b' },
    PushNotifications: { presentationOptions: ['badge', 'sound', 'alert'] }
  },
  android: { allowMixedContent: false, captureInput: true },
  ios: { contentInset: 'automatic', preferredContentMode: 'mobile' }
};
export default config;
