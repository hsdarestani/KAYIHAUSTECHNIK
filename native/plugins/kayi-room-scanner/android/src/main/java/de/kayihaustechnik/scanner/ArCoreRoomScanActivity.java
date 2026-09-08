package de.kayihaustechnik.scanner;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.opengl.GLES11Ext;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import com.google.ar.core.*;
import com.google.ar.core.exceptions.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.nio.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.ConcurrentLinkedQueue;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

public class ArCoreRoomScanActivity extends AppCompatActivity implements GLSurfaceView.Renderer {
    private static void writeBytes(File file, byte[] value) throws java.io.IOException {
        try (FileOutputStream stream = new FileOutputStream(file)) {
            stream.write(value);
            stream.flush();
        }
    }

    private static final int CAMERA_PERMISSION = 7101;
    private GLSurfaceView surfaceView; private Session session; private boolean installRequested=false; private boolean depthSupported=false;
    private final BackgroundRenderer background = new BackgroundRenderer(); private final Queue<float[]> taps = new ConcurrentLinkedQueue<>(); private final List<Pose> points = Collections.synchronizedList(new ArrayList<>());
    private TextView instruction, progress; private Button finish; private String roomName="Raum"; private volatile Frame latestFrame;

    @Override protected void onCreate(Bundle b){super.onCreate(b);roomName=getIntent().getStringExtra("roomName");if(roomName==null||roomName.isBlank())roomName="Raum";buildUi();}
    private void buildUi(){
        FrameLayout root=new FrameLayout(this);root.setBackgroundColor(Color.BLACK);surfaceView=new GLSurfaceView(this);surfaceView.setPreserveEGLContextOnPause(true);surfaceView.setEGLContextClientVersion(2);surfaceView.setEGLConfigChooser(8,8,8,8,16,0);surfaceView.setRenderer(this);surfaceView.setRenderMode(GLSurfaceView.RENDERMODE_CONTINUOUSLY);surfaceView.setOnTouchListener((v,e)->{if(e.getAction()==MotionEvent.ACTION_UP){taps.add(new float[]{e.getX(),e.getY()});return true;}return true;});root.addView(surfaceView,new FrameLayout.LayoutParams(-1,-1));
        LinearLayout top=new LinearLayout(this);top.setOrientation(LinearLayout.VERTICAL);top.setPadding(32,24,32,24);top.setBackgroundColor(0xCC07182E);instruction=new TextView(this);instruction.setTextColor(Color.WHITE);instruction.setTextSize(18);instruction.setText("Langsam bewegen – Bodenecke 1 antippen");instruction.setTypeface(null,android.graphics.Typeface.BOLD);progress=new TextView(this);progress.setTextColor(0xFFD8E6F5);progress.setTextSize(13);progress.setText("ARCore sucht Flächen und Tiefenpunkte.");top.addView(instruction);top.addView(progress);FrameLayout.LayoutParams tp=new FrameLayout.LayoutParams(-1,-2);tp.gravity=Gravity.TOP;tp.setMargins(20,20,20,0);root.addView(top,tp);
        LinearLayout bottom=new LinearLayout(this);bottom.setGravity(Gravity.CENTER);bottom.setPadding(16,16,16,16);Button cancel=new Button(this);cancel.setText("Abbrechen");cancel.setOnClickListener(v->{setResult(Activity.RESULT_CANCELED);finish();});finish=new Button(this);finish.setText("Scan speichern");finish.setEnabled(false);finish.setOnClickListener(v->completeScan());bottom.addView(cancel,new LinearLayout.LayoutParams(0,-2,1));bottom.addView(finish,new LinearLayout.LayoutParams(0,-2,1));FrameLayout.LayoutParams bp=new FrameLayout.LayoutParams(-1,-2);bp.gravity=Gravity.BOTTOM;bp.setMargins(16,0,16,20);root.addView(bottom,bp);setContentView(root);
    }

    @Override protected void onResume(){super.onResume();if(!ensureSession())return;try{session.resume();surfaceView.onResume();}catch(CameraNotAvailableException e){showError("Kamera nicht verfügbar.");}}
    @Override protected void onPause(){super.onPause();if(session!=null){surfaceView.onPause();session.pause();}}
    @Override protected void onDestroy(){if(session!=null){session.close();session=null;}super.onDestroy();}
    private boolean ensureSession(){
        if(session!=null)return true;if(ContextCompat.checkSelfPermission(this,Manifest.permission.CAMERA)!=PackageManager.PERMISSION_GRANTED){ActivityCompat.requestPermissions(this,new String[]{Manifest.permission.CAMERA},CAMERA_PERMISSION);return false;}
        try{ArCoreApk.InstallStatus status=ArCoreApk.getInstance().requestInstall(this,!installRequested);if(status==ArCoreApk.InstallStatus.INSTALL_REQUESTED){installRequested=true;return false;}session=new Session(this);Config config=session.getConfig();depthSupported=session.isDepthModeSupported(Config.DepthMode.AUTOMATIC);if(depthSupported)config.setDepthMode(Config.DepthMode.AUTOMATIC);config.setPlaneFindingMode(Config.PlaneFindingMode.HORIZONTAL_AND_VERTICAL);session.configure(config);return true;}catch(Exception e){showError("ARCore konnte nicht gestartet werden: "+e.getMessage());return false;}
    }
    @Override public void onRequestPermissionsResult(int r,@NonNull String[] p,@NonNull int[] g){super.onRequestPermissionsResult(r,p,g);if(r==CAMERA_PERMISSION&&g.length>0&&g[0]==PackageManager.PERMISSION_GRANTED)onResume();else showError("Kamerazugriff ist für das Aufmaß erforderlich.");}
    private void showError(String text){runOnUiThread(()->{progress.setText(text);progress.setTextColor(0xFFFFB3B3);});}

    @Override public void onSurfaceCreated(GL10 gl,EGLConfig cfg){GLES20.glClearColor(0,0,0,1);background.create();}
    @Override public void onSurfaceChanged(GL10 gl,int w,int h){GLES20.glViewport(0,0,w,h);if(session!=null)session.setDisplayGeometry(getWindowManager().getDefaultDisplay().getRotation(),w,h);}
    @Override public void onDrawFrame(GL10 gl){GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT|GLES20.GL_DEPTH_BUFFER_BIT);if(session==null)return;try{session.setCameraTextureName(background.textureId);Frame frame=session.update();latestFrame=frame;background.draw(frame);Camera camera=frame.getCamera();if(camera.getTrackingState()!=TrackingState.TRACKING){updateTracking(camera.getTrackingFailureReason());return;}float[] tap;while((tap=taps.poll())!=null)handleTap(frame,tap[0],tap[1]);}catch(Exception ignored){}}
    private void updateTracking(TrackingFailureReason reason){runOnUiThread(()->progress.setText(reason==TrackingFailureReason.NONE?"Gerät langsam bewegen …":"Tracking: "+reason));}
    private void handleTap(Frame frame,float x,float y){
        for(HitResult hit:frame.hitTest(x,y)){Trackable t=hit.getTrackable();boolean valid=t instanceof DepthPoint||t instanceof Point||(t instanceof Plane&&((Plane)t).isPoseInPolygon(hit.getHitPose()));if(!valid)continue;points.add(hit.getHitPose());runOnUiThread(this::updateStep);return;}runOnUiThread(()->progress.setText("Kein sicherer Tiefen-/Flächenpunkt. Gerät bewegen und erneut tippen."));
    }
    private void updateStep(){int n=points.size();String[] steps={"Bodenecke 1 antippen","Bodenecke 2 antippen","Bodenecke 3 antippen","Bodenecke 4 antippen","Decke über der Raummitte antippen"};if(n<5){instruction.setText("Langsam bewegen – "+steps[n]);progress.setText((depthSupported?"Depth aktiv":"Plane/Point-Messung")+" · "+n+"/5 Punkte");}else{instruction.setText("Messpunkte vollständig");progress.setText("Maße prüfen und Scan speichern. Jeder Wert bleibt im Portal prüfpflichtig.");finish.setEnabled(true);}}

    private void completeScan(){if(points.size()<5)return;try{
        List<Pose> p=new ArrayList<>(points.subList(0,5));double a=distanceXZ(p.get(0),p.get(1)),b=distanceXZ(p.get(1),p.get(2)),c=distanceXZ(p.get(2),p.get(3)),d=distanceXZ(p.get(3),p.get(0));double length=Math.max((a+c)/2,(b+d)/2),width=Math.min((a+c)/2,(b+d)/2);double floorY=(p.get(0).ty()+p.get(1).ty()+p.get(2).ty()+p.get(3).ty())/4.0;double height=Math.abs(p.get(4).ty()-floorY);if(length<0.2||width<0.2||height<1.2)throw new IllegalStateException("Messpunkte ergeben keine plausiblen Raummaße.");
        UUID id=UUID.randomUUID();File dir=new File(new File(getFilesDir(),"kayi_room_scans"),id.toString());if(!dir.mkdirs()&&!dir.isDirectory())throw new IOException("Scan-Ordner konnte nicht erstellt werden.");File payloadFile=new File(dir,"payload.json"),modelFile=new File(dir,"room.obj"),metaFile=new File(dir,"metadata.json");JSONArray corners=new JSONArray();for(int i=0;i<4;i++)corners.put(poseJson(p.get(i)));
        JSONArray walls=new JSONArray();for(int i=0;i<4;i++){Pose p1=p.get(i),p2=p.get((i+1)%4);double len=distanceXZ(p1,p2);walls.put(new JSONObject().put("identifier","wall-"+(i+1)).put("dimensions",new JSONObject().put("width_m",len).put("height_m",height).put("depth_m",0.02)).put("start",poseJson(p1)).put("end",poseJson(p2)));}
        JSONObject payload=new JSONObject().put("schema_version","1.0").put("provider","android_arcore_depth").put("coordinate_system","right_handed_y_up").put("room",new JSONObject().put("name",roomName).put("dimensions",new JSONObject().put("length_m",length).put("width_m",width).put("height_m",height))).put("walls",walls).put("doors",new JSONArray()).put("windows",new JSONArray()).put("openings",new JSONArray()).put("objects",new JSONArray()).put("corners",corners).put("confidence",depthSupported?0.72:0.55).put("warnings",new JSONArray().put("Android-Depth-Aufmaß und Deckenpunkt manuell prüfen."));writeUtf8(payloadFile,payload.toString(2));writeObj(modelFile,p,height);
        String now=new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", java.util.Locale.US).format(new java.util.Date());JSONObject meta=new JSONObject().put("scanId",id.toString()).put("provider","android_arcore_depth").put("roomName",roomName).put("createdAt",now).put("payloadPath",payloadFile.getAbsolutePath()).put("modelPath",modelFile.getAbsolutePath());writeUtf8(metaFile,meta.toString(2));Intent result=new Intent();result.putExtra("scanId",id.toString());result.putExtra("roomName",roomName);result.putExtra("createdAt",now);result.putExtra("payloadPath",payloadFile.getAbsolutePath());result.putExtra("modelPath",modelFile.getAbsolutePath());setResult(Activity.RESULT_OK,result);finish();
    }catch(Exception e){showError(e.getMessage());}}
    private JSONObject poseJson(Pose p)throws Exception{return new JSONObject().put("x_m",p.tx()).put("y_m",p.ty()).put("z_m",p.tz());}
    private static void writeUtf8(File file,String value)throws IOException{try(Writer writer=new OutputStreamWriter(new FileOutputStream(file),StandardCharsets.UTF_8)){writer.write(value);}}
    private double distanceXZ(Pose a,Pose b){double x=a.tx()-b.tx(),z=a.tz()-b.tz();return Math.sqrt(x*x+z*z);}
    private void writeObj(File file,List<Pose> p,double height)throws Exception{try(Writer w=new OutputStreamWriter(new FileOutputStream(file),StandardCharsets.UTF_8)){w.write("# KAYI ARCore room scan\n");for(int i=0;i<4;i++)w.write("v "+p.get(i).tx()+" 0 "+p.get(i).tz()+"\n");for(int i=0;i<4;i++)w.write("v "+p.get(i).tx()+" "+height+" "+p.get(i).tz()+"\n");w.write("f 1 2 3 4\nf 8 7 6 5\nf 1 5 6 2\nf 2 6 7 3\nf 3 7 8 4\nf 4 8 5 1\n");}}

    private static final class BackgroundRenderer {
        int textureId=-1,program=-1,position=-1,texCoord=-1,sampler=-1;FloatBuffer quad,uv;
        final float[] quadCoords={-1,-1,1,-1,-1,1,1,1};final float[] uvCoords=new float[8];
        void create(){int[] tex=new int[1];GLES20.glGenTextures(1,tex,0);textureId=tex[0];GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,textureId);GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_LINEAR);GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_LINEAR);program=link(VERTEX,FRAGMENT);position=GLES20.glGetAttribLocation(program,"a_Position");texCoord=GLES20.glGetAttribLocation(program,"a_TexCoord");sampler=GLES20.glGetUniformLocation(program,"sTexture");quad=buffer(quadCoords);uv=buffer(uvCoords);}
        void draw(Frame frame){if(frame.hasDisplayGeometryChanged())frame.transformCoordinates2d(Coordinates2d.OPENGL_NORMALIZED_DEVICE_COORDINATES,FloatBuffer.wrap(quadCoords),Coordinates2d.TEXTURE_NORMALIZED,FloatBuffer.wrap(uvCoords));uv=buffer(uvCoords);GLES20.glDisable(GLES20.GL_DEPTH_TEST);GLES20.glDepthMask(false);GLES20.glUseProgram(program);GLES20.glActiveTexture(GLES20.GL_TEXTURE0);GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,textureId);GLES20.glUniform1i(sampler,0);GLES20.glEnableVertexAttribArray(position);GLES20.glVertexAttribPointer(position,2,GLES20.GL_FLOAT,false,0,quad);GLES20.glEnableVertexAttribArray(texCoord);GLES20.glVertexAttribPointer(texCoord,2,GLES20.GL_FLOAT,false,0,uv);GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4);GLES20.glDisableVertexAttribArray(position);GLES20.glDisableVertexAttribArray(texCoord);GLES20.glDepthMask(true);}
        static FloatBuffer buffer(float[] a){FloatBuffer b=ByteBuffer.allocateDirect(a.length*4).order(ByteOrder.nativeOrder()).asFloatBuffer();b.put(a).position(0);return b;}
        static int shader(int type,String code){int s=GLES20.glCreateShader(type);GLES20.glShaderSource(s,code);GLES20.glCompileShader(s);return s;}static int link(String v,String f){int p=GLES20.glCreateProgram();GLES20.glAttachShader(p,shader(GLES20.GL_VERTEX_SHADER,v));GLES20.glAttachShader(p,shader(GLES20.GL_FRAGMENT_SHADER,f));GLES20.glLinkProgram(p);return p;}
        static final String VERTEX="attribute vec4 a_Position;attribute vec2 a_TexCoord;varying vec2 v_TexCoord;void main(){gl_Position=a_Position;v_TexCoord=a_TexCoord;}";
        static final String FRAGMENT="#extension GL_OES_EGL_image_external : require\nprecision mediump float;uniform samplerExternalOES sTexture;varying vec2 v_TexCoord;void main(){gl_FragColor=texture2D(sTexture,v_TexCoord);}";
    }
}

final class KayiUtf8Files {
    private KayiUtf8Files() {}

    static void writeString(File file, String value) throws java.io.IOException {
        try (OutputStreamWriter writer = new OutputStreamWriter(
                new FileOutputStream(file), java.nio.charset.StandardCharsets.UTF_8)) {
            writer.write(value);
        }
    }

    static String readString(File file) throws java.io.IOException {
        try (FileInputStream input = new FileInputStream(file);
             ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return new String(output.toByteArray(), java.nio.charset.StandardCharsets.UTF_8);
        }
    }
}
