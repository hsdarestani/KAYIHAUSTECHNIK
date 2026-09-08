export interface NativeScanCapabilities { supported:boolean; provider:string; lidar?:boolean; depth?:boolean; reason?:string }
export interface PendingScan { scanId:string; provider:string; roomName:string; createdAt:string; payloadPath?:string; modelPath?:string }
export interface KayiRoomScannerPlugin {
  getCapabilities():Promise<NativeScanCapabilities>;
  startScan(options?:{roomName?:string}):Promise<PendingScan>;
  listPendingScans():Promise<{scans:PendingScan[]}>;
  uploadScan(options:{scanId:string;projectId:number;apiBaseUrl:string;token:string}):Promise<Record<string,unknown>>;
  deletePendingScan(options:{scanId:string}):Promise<{deleted:boolean}>;
}
export declare const KayiRoomScanner: KayiRoomScannerPlugin;
