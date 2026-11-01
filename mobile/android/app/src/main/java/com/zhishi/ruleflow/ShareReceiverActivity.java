package com.zhishi.ruleflow;

import android.app.Activity; import android.content.*; import android.database.Cursor; import android.net.Uri; import android.os.Bundle; import android.provider.OpenableColumns;
import java.io.*; import java.util.*; import java.util.concurrent.*; import org.json.*;

/** ContentResolver-only share receiver.  It queues each item; it never uploads it. */
public class ShareReceiverActivity extends Activity {
  private static final long MAX_BYTES=20L*1024*1024;
  private final ExecutorService io=Executors.newSingleThreadExecutor();
  @Override public void onCreate(Bundle state){super.onCreate(state);enqueue(getIntent());}
  @Override protected void onNewIntent(Intent intent){super.onNewIntent(intent);enqueue(intent);}
  private void enqueue(Intent intent){io.execute(()->{receive(intent);runOnUiThread(()->{startActivity(new Intent(this,MainActivity.class).putExtra("zhishi_share_pending",true).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP));finish();});});}
  @Override protected void onDestroy(){super.onDestroy();io.shutdown();}
  private void receive(Intent intent) {
    JSONArray queue=new JSONArray();
    LinkedHashSet<Uri> uris=new LinkedHashSet<>();
    if(Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())){
      ArrayList<Uri> multiple=intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);if(multiple!=null)uris.addAll(multiple);
    } else { Uri one=intent.getParcelableExtra(Intent.EXTRA_STREAM); if(one!=null)uris.add(one); }
    ClipData clips=intent.getClipData(); if(clips!=null)for(int i=0;i<clips.getItemCount();i++){Uri u=clips.getItemAt(i).getUri();if(u!=null)uris.add(u);}
    if(uris.size()>10){queue.put(error("too_many_files"));PendingImportStore.append(this,queue);return;}
    CharSequence sharedText=intent.getCharSequenceExtra(Intent.EXTRA_TEXT);String text=sharedText==null?null:sharedText.toString();
    if(text!=null&&!text.trim().isEmpty()) queue.put(text.length()>200000?error("text_too_large"):textItem(text));
    for(Uri uri:uris) queue.put(copy(uri));
    PendingImportStore.append(this,queue);
  }
  private JSONObject textItem(String text){try{return new JSONObject().put("id",UUID.randomUUID().toString()).put("kind",text.trim().matches("https?://\\S+")?"url":"text").put("text",text).put("state","pending").put("created_at",System.currentTimeMillis());}catch(Exception e){return error("text_encoding_failed");}}
  private JSONObject copy(Uri uri){
    JSONObject item=new JSONObject();File out=null;try {
      if(!"content".equals(uri.getScheme()))return error("uri_scheme_unsupported");
      String id=UUID.randomUUID().toString(); out=new File(getFilesDir(),"shared_"+id); long total=0;
      String mime=getContentResolver().getType(uri);String name=displayName(uri);
      long limit=(mime!=null&&mime.startsWith("image/"))?10L*1024*1024:MAX_BYTES;
      try(InputStream in=getContentResolver().openInputStream(uri); OutputStream os=new FileOutputStream(out)){
        if(in==null)throw new IOException("unreadable_uri"); byte[] b=new byte[8192]; int n;
        while((n=in.read(b))!=-1){total+=n;if(total>limit)throw new EOFException();os.write(b,0,n);}
      }
      return item.put("id",id).put("kind","file").put("local_path",out.getAbsolutePath()).put("name",name).put("mime",mime).put("size",total).put("state","pending").put("created_at",System.currentTimeMillis());
    } catch(Exception e){if(out!=null)out.delete();return error(e instanceof EOFException?"file_too_large":e instanceof SecurityException?"uri_permission_denied":"copy_failed");}
  }
  private JSONObject error(String code){try{return new JSONObject().put("id",UUID.randomUUID().toString()).put("state","failed").put("error",code).put("created_at",System.currentTimeMillis());}catch(Exception ignored){return new JSONObject();}}
  private String displayName(Uri uri){try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME},null,null,null)){if(c!=null&&c.moveToFirst())return c.getString(0);}catch(Exception ignored){}return "shared_file";}
}
