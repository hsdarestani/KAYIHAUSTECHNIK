import { WebPlugin } from '@capacitor/core';
export class KayiRoomScannerWeb extends WebPlugin {
  async getCapabilities(){return {supported:false,provider:'web',reason:'Native RoomPlan/ARCore app required'}}
  async startScan(){throw new Error('Native room scanning is not available in the browser.')}
  async listPendingScans(){return {scans:[]}}
  async uploadScan(){throw new Error('No native scan available.')}
  async deletePendingScan(){return {deleted:false}}
}
