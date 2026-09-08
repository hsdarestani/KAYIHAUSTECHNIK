package de.kayihaustechnik.scanner;

import android.app.Activity;
import android.content.Intent;
import android.os.Build;
import androidx.activity.result.ActivityResult;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.ar.core.ArCoreApk;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@CapacitorPlugin(name = "KayiRoomScanner")
public class KayiRoomScannerPlugin extends Plugin {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @PluginMethod public void getCapabilities(PluginCall call) {
        boolean arAvailable = ArCoreApk.getInstance().checkAvailability(getContext()).isSupported();
        JSObject result = new JSObject();
        result.put("supported", arAvailable); result.put("provider", "android_arcore_depth"); result.put("depth", arAvailable);
        result.put("requiresHumanConfirmation", true); result.put("deviceModel", Build.MANUFACTURER + " " + Build.MODEL); result.put("operatingSystem", "Android " + Build.VERSION.RELEASE);
        if (!arAvailable) result.put("reason", "ARCore ist auf diesem Gerät nicht verfügbar."); call.resolve(result);
    }

    @PluginMethod public void startScan(PluginCall call) {
        Intent intent = new Intent(getContext(), ArCoreRoomScanActivity.class);
        intent.putExtra("roomName", call.getString("roomName", "Raum")); startActivityForResult(call, intent, "scanFinished");
    }

    @ActivityCallback private void scanFinished(PluginCall call, ActivityResult result) {
        if (call == null) return;
        Intent data = result.getData();
        if (result.getResultCode() != Activity.RESULT_OK || data == null) { call.reject("Scan wurde abgebrochen.", "SCAN_CANCELLED"); return; }
        JSObject output = new JSObject(); output.put("scanId", data.getStringExtra("scanId")); output.put("provider", "android_arcore_depth"); output.put("roomName", data.getStringExtra("roomName")); output.put("createdAt", data.getStringExtra("createdAt")); output.put("payloadPath", data.getStringExtra("payloadPath")); output.put("modelPath", data.getStringExtra("modelPath")); call.resolve(output);
    }

    @PluginMethod public void listPendingScans(PluginCall call) {
        executor.execute(() -> { try { JSArray items = new JSArray(); for (PendingScan scan : ScanStore.list(getContext().getFilesDir())) items.put(scan.toJson()); JSObject result = new JSObject(); result.put("scans", items); call.resolve(result); } catch (Exception e) { call.reject("Lokale Scans konnten nicht gelesen werden.", e); } });
    }

    @PluginMethod public void deletePendingScan(PluginCall call) {
        String scanId = call.getString("scanId"); if (scanId == null) { call.reject("scanId fehlt."); return; }
        executor.execute(() -> { try { JSObject r = new JSObject(); r.put("deleted", ScanStore.delete(getContext().getFilesDir(), scanId)); call.resolve(r); } catch (Exception e) { call.reject("Scan konnte nicht gelöscht werden.", e); } });
    }

    @PluginMethod public void uploadScan(PluginCall call) {
        String scanId=call.getString("scanId"), base=call.getString("apiBaseUrl"), token=call.getString("token"); Integer projectId=call.getInt("projectId");
        if(scanId==null||base==null||token==null||projectId==null){call.reject("scanId, projectId, apiBaseUrl und token sind erforderlich.");return;}
        executor.execute(() -> { try { JSONObject response = upload(ScanStore.load(getContext().getFilesDir(), scanId), projectId, base, token); call.resolve(JSObject.fromJSONObject(response)); } catch(Exception e){call.reject("Upload fehlgeschlagen: "+e.getMessage(),"UPLOAD_FAILED",e);} });
    }

    private JSONObject upload(PendingScan scan,int projectId,String base,String token)throws Exception{
        URL url=new URL(base.replaceAll("/+$","")+"/api/native-scans/");String boundary="KayiBoundary"+UUID.randomUUID();HttpURLConnection c=(HttpURLConnection)url.openConnection();c.setRequestMethod("POST");c.setDoOutput(true);c.setConnectTimeout(20000);c.setReadTimeout(120000);c.setRequestProperty("Authorization","Token "+token);c.setRequestProperty("Content-Type","multipart/form-data; boundary="+boundary);
        try(OutputStream out=c.getOutputStream()){
            field(out,boundary,"client_scan_id",scan.scanId);field(out,boundary,"project_id",String.valueOf(projectId));field(out,boundary,"provider",scan.provider);field(out,boundary,"app_version","2.2.0");field(out,boundary,"device_model",Build.MANUFACTURER+" "+Build.MODEL);field(out,boundary,"operating_system","Android "+Build.VERSION.RELEASE);field(out,boundary,"payload",readUtf8(new File(scan.payloadPath)));
            File model=new File(scan.modelPath);out.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\"model_file\"; filename=\"room.obj\"\r\nContent-Type: model/obj\r\n\r\n").getBytes(StandardCharsets.UTF_8));copy(model,out);out.write(("\r\n--"+boundary+"--\r\n").getBytes(StandardCharsets.UTF_8));
        }
        int code=c.getResponseCode();InputStream stream=code>=200&&code<300?c.getInputStream():c.getErrorStream();String body=readUtf8(stream);if(code<200||code>=300)throw new IOException("HTTP "+code+": "+body);return new JSONObject(body);
    }
    private void field(OutputStream out,String boundary,String name,String value)throws IOException{out.write(("--"+boundary+"\r\nContent-Disposition: form-data; name=\""+name+"\"\r\n\r\n"+value+"\r\n").getBytes(StandardCharsets.UTF_8));}
    private static String readUtf8(File file)throws IOException{try(InputStream in=new FileInputStream(file)){return readUtf8(in);}}
    private static String readUtf8(InputStream in)throws IOException{ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int read;while((read=in.read(buffer))!=-1)out.write(buffer,0,read);return out.toString(StandardCharsets.UTF_8.name());}
    private static void copy(File file,OutputStream out)throws IOException{try(InputStream in=new FileInputStream(file)){byte[] buffer=new byte[8192];int read;while((read=in.read(buffer))!=-1)out.write(buffer,0,read);}}

    static final class PendingScan {
        final String scanId,provider,roomName,createdAt,payloadPath,modelPath;
        PendingScan(String id,String p,String room,String created,String payload,String model){scanId=id;provider=p;roomName=room;createdAt=created;payloadPath=payload;modelPath=model;}
        JSONObject toJson()throws Exception{return new JSONObject().put("scanId",scanId).put("provider",provider).put("roomName",roomName).put("createdAt",createdAt).put("payloadPath",payloadPath).put("modelPath",modelPath);}
        static PendingScan fromJson(JSONObject o){return new PendingScan(o.optString("scanId"),o.optString("provider"),o.optString("roomName"),o.optString("createdAt"),o.optString("payloadPath"),o.optString("modelPath"));}
    }
    static final class ScanStore {
        static File root(File files){return new File(files,"kayi_room_scans");}
        static List<PendingScan> list(File files)throws Exception{File root=root(files);if(!root.exists())return new ArrayList<>();File[] dirs=root.listFiles(File::isDirectory);List<PendingScan> result=new ArrayList<>();if(dirs!=null)for(File dir:dirs){File meta=new File(dir,"metadata.json");if(meta.exists())result.add(PendingScan.fromJson(new JSONObject(readUtf8(meta))));}result.sort((a,b)->b.createdAt.compareTo(a.createdAt));return result;}
        static PendingScan load(File files,String id)throws Exception{for(PendingScan scan:list(files))if(scan.scanId.equals(id))return scan;throw new FileNotFoundException("Lokaler Scan nicht gefunden.");}
        static boolean delete(File files,String id)throws Exception{File dir=new File(root(files),id);if(!dir.exists())return false;deleteRecursive(dir);return true;}
        static void deleteRecursive(File f)throws Exception{File[] children=f.listFiles();if(children!=null)for(File child:children)deleteRecursive(child);if(!f.delete())throw new IOException("Datei konnte nicht gelöscht werden: "+f);}
    }
}
