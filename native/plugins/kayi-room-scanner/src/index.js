import { registerPlugin } from '@capacitor/core';
export const KayiRoomScanner = registerPlugin('KayiRoomScanner', { web: () => import('./web.js').then(m => new m.KayiRoomScannerWeb()) });
