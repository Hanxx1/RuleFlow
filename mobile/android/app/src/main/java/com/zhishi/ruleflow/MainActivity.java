package com.zhishi.ruleflow;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
  @Override public void onCreate(android.os.Bundle state){registerPlugin(PendingImportsPlugin.class);super.onCreate(state);}
}
