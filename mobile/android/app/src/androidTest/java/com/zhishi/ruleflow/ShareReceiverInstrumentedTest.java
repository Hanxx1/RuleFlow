package com.zhishi.ruleflow;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import androidx.core.content.FileProvider;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import org.junit.*;
import org.junit.runner.RunWith;
import org.json.*;
import java.io.*;
import java.util.*;
import static org.junit.Assert.*;

/** Synthetic inputs only. Preserves all pre-existing pending queue entries. */
@RunWith(AndroidJUnit4.class)
public class ShareReceiverInstrumentedTest {
  private Context context;
  private final HashSet<String> baseline=new HashSet<>();
  private final HashSet<String> testIds=new HashSet<>();
  private final ArrayList<File> created=new ArrayList<>();
  @Before public void snapshot(){
    context=InstrumentationRegistry.getInstrumentation().getTargetContext();
    JSONArray all=PendingImportStore.read(context);
    for(int i=0;i<all.length();i++)baseline.add(all.optJSONObject(i).optString("id"));
  }
  @After public void cleanup(){
    JSONArray ids=new JSONArray();for(String id:testIds)ids.put(id);
    PendingImportStore.clear(context,ids);for(File file:created)file.delete();
  }
  private JSONArray awaitItems(int count) throws Exception {
    long end=System.currentTimeMillis()+5000;
    while(System.currentTimeMillis()<end){
      JSONArray result=new JSONArray(),all=PendingImportStore.read(context);
      for(int i=0;i<all.length();i++){JSONObject item=all.optJSONObject(i);boolean synthetic=item.optString("name").startsWith("instrumented-")||item.optString("text").equals("https://example.com/synthetic-notice")||item.optString("error").equals("uri_scheme_unsupported");if(!baseline.contains(item.optString("id"))&&synthetic){result.put(item);testIds.add(item.optString("id"));}}
      if(result.length()>=count)return result;Thread.sleep(50);
    }
    fail("share receiver did not persist items");return new JSONArray();
  }
  private void launch(Intent intent){context.startActivity(intent.setClass(context,ShareReceiverActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_GRANT_READ_URI_PERMISSION));}
  private Uri textFile(String name) throws Exception {
    File file=new File(context.getCacheDir(),"instrumented-"+System.nanoTime()+name);created.add(file);
    try(FileOutputStream stream=new FileOutputStream(file)){stream.write("Synthetic share input".getBytes("UTF-8"));}
    return FileProvider.getUriForFile(context,context.getPackageName()+".fileprovider",file);
  }
  @Test public void multipleExtraStreamUsesContentResolverAndCleansSnapshot() throws Exception {
    ArrayList<Uri> streams=new ArrayList<>();streams.add(textFile("-one.txt"));streams.add(textFile("-two.txt"));
    launch(new Intent(Intent.ACTION_SEND_MULTIPLE).setType("text/plain").putParcelableArrayListExtra(Intent.EXTRA_STREAM,streams));
    JSONArray items=awaitItems(2),ids=new JSONArray();ArrayList<File> copies=new ArrayList<>();
    for(int i=0;i<items.length();i++){JSONObject item=items.getJSONObject(i);assertEquals("pending",item.getString("state"));assertEquals("file",item.getString("kind"));File file=new File(item.getString("local_path"));assertTrue(file.exists());copies.add(file);ids.put(item.getString("id"));}
    PendingImportStore.clear(context,ids);for(File file:copies)assertFalse(file.exists());assertEquals(baseline.size(),PendingImportStore.read(context).length());
  }
  @Test public void sharedUrlIsQueuedWithoutNetwork() throws Exception {
    launch(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT,"https://example.com/synthetic-notice"));
    JSONObject item=awaitItems(1).getJSONObject(0);assertEquals("url",item.getString("kind"));assertEquals("pending",item.getString("state"));
  }
  @Test public void rawFilePathIsRejectedWithoutLeakingUri() throws Exception {
    launch(new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_STREAM,Uri.parse("file:///private/synthetic.txt")));
    JSONObject item=awaitItems(1).getJSONObject(0);assertEquals("failed",item.getString("state"));assertEquals("uri_scheme_unsupported",item.getString("error"));assertFalse(item.toString().contains("/private/"));
  }
}
