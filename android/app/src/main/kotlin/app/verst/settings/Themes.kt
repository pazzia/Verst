package app.verst.settings

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import app.verst.core.model.AppTheme

object Themes {
    /** DAY, or SYSTEM while the phone is in light mode. */
    fun isDay(context: Context, theme: AppTheme): Boolean = when (theme) {
        AppTheme.NIGHT -> false
        AppTheme.DAY -> true
        AppTheme.SYSTEM -> (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) != Configuration.UI_MODE_NIGHT_YES
    }

    /**
     * Starts the app again in a new process so every token is read with the new palette. The current trip survives:
     * it is in `last.json` (P1-2), and the saved trips are on disk.
     */
    fun restart(activity: Activity) {
        val intent = activity.packageManager.getLaunchIntentForPackage(activity.packageName) ?: return
        activity.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        activity.finishAffinity()
        Runtime.getRuntime().exit(0)
    }
}
