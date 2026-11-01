package com.zhishi.ruleflow

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import java.io.File

/** Minimal native receiver. Upload confirmation remains exclusively in the Web UI. */
class ShareReceiverActivity : Activity() {
  override fun onCreate(state: Bundle?) { super.onCreate(state); receive(intent); finish() }
  override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); receive(intent) }
  private fun receive(intent: Intent) {
    val prefs=getSharedPreferences("zhishi_pending_import", MODE_PRIVATE)
    val text=intent.getStringExtra(Intent.EXTRA_TEXT)
    val uris=mutableListOf<Uri>()
    (intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM))?.let { uris.add(it) }
    intent.clipData?.let { clip -> for (i in 0 until clip.itemCount) clip.getItemAt(i).uri?.let { uris.add(it) } }
    if (uris.size > 10) return
    val copied=uris.mapNotNull { uri ->
      runCatching { contentResolver.openInputStream(uri)?.use { input ->
        val out=File(cacheDir,"share_${System.currentTimeMillis()}_${uris.indexOf(uri)}")
        out.outputStream().use { output -> input.copyTo(output, 8192) }
        if(out.length()>20L*1024*1024) { out.delete(); null } else out.name
      }}.getOrNull()
    }
    prefs.edit().putString("text",text).putString("files",copied.joinToString(",")).apply()
    startActivity(Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP))
  }
}
