package com.zhishi.ruleflow;

import android.content.Context;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.File;

/** Synchronizes the private queue only; no network or account state. */
final class PendingImportStore {
  static synchronized JSONArray read(Context context) {
    try { return new JSONArray(context.getSharedPreferences("zhishi_pending_import",Context.MODE_PRIVATE).getString("queue","[]")); }
    catch(Exception ignored){ return new JSONArray(); }
  }
  static synchronized void append(Context context, JSONArray incoming) {
    JSONArray queue=read(context);
    for(int i=0;i<incoming.length();i++) queue.put(incoming.opt(i));
    context.getSharedPreferences("zhishi_pending_import",Context.MODE_PRIVATE).edit().putString("queue",queue.toString()).commit();
  }
  static synchronized void clear(Context context, JSONArray selected) {
    JSONArray queue=read(context);
    java.util.HashSet<String> ids=new java.util.HashSet<>();
    if(selected!=null)for(int i=0;i<selected.length();i++)ids.add(selected.optString(i));
    JSONArray remaining=new JSONArray();
    for(int i=0;i<queue.length();i++) {
      JSONObject item=queue.optJSONObject(i);if(item==null)continue;
      if(selected!=null&&!ids.contains(item.optString("id"))){remaining.put(item);continue;}
      try {
        File file=new File(item.optString("local_path","")).getCanonicalFile();
        if(context.getFilesDir().getCanonicalFile().equals(file.getParentFile()) && file.getName().startsWith("shared_")) file.delete();
      } catch(Exception ignored) { /* Never delete outside the private share directory. */ }
    }
    context.getSharedPreferences("zhishi_pending_import",Context.MODE_PRIVATE).edit().putString("queue",remaining.toString()).commit();
  }
}
