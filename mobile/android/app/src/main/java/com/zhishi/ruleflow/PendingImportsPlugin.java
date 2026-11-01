package com.zhishi.ruleflow;

import android.content.Context;
import android.content.Intent;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import org.json.JSONArray;

@CapacitorPlugin(name = "PendingImports")
public class PendingImportsPlugin extends Plugin {
  @PluginMethod public void getPending(PluginCall call) {
    String raw=PendingImportStore.read(getContext()).toString();
    try { JSObject result=new JSObject();result.put("items",new JSArray(raw));call.resolve(result); }
    catch(Exception e){call.reject("pending_queue_invalid");}
  }
  @PluginMethod public void clearPending(PluginCall call) {
    PendingImportStore.clear(getContext(),call.getArray("ids"));call.resolve();
  }
  @Override protected void handleOnNewIntent(Intent intent){
    if(intent.getBooleanExtra("zhishi_share_pending",false))notifyListeners("pendingImportsChanged",new JSObject(),true);
  }
}
