package app.verst

import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.test.core.app.ApplicationProvider
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Release review P0-1 on the Android side: the shared deny-list file (also used by the Python test). */
object BrandDenyList {
    private val root = File(System.getProperty("verst.repoRoot") ?: "../..")
    val brands: List<String> = root.resolve("backend/planner/tests/brand_denylist.txt").readLines()
        .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }

    /** S3-R1: string keys that may name the external navigator app (hand-off only). */
    val handoffKeys: Set<String> = root.resolve("backend/planner/tests/brand_handoff_keys.txt").readLines()
        .map { it.trim() }.filter { it.isNotEmpty() && !it.startsWith("#") }.toSet()

    /** Rendered texts may contain the allowed hand-off values (set by [allow]); those are cut out before matching. */
    var allowed: List<String> = emptyList()

    fun allow(context: android.content.Context) {
        allowed = handoffKeys.map { k ->
            val id = app.verst.core.ui.R.string::class.java.getField(k).getInt(null)
            context.getString(id)
        }.sortedByDescending { it.length }
    }

    fun hits(text: String): List<String> {
        val t = allowed.fold(text) { acc, a -> acc.replace(a, "") }
        return brands.filter { t.contains(it, ignoreCase = true) }.map { "«$it» in «${text.take(80)}»" }
    }

    /** Every text of a semantics tree (unmerged), for the rendered-screen check. */
    fun texts(node: SemanticsNode): List<String> =
        (node.config.getOrNull(SemanticsProperties.Text)?.map { it.text }.orEmpty() +
            listOfNotNull(node.config.getOrNull(SemanticsProperties.ContentDescription)?.joinToString(" "))) +
            node.children.flatMap { texts(it) }
}

@RunWith(RobolectricTestRunner::class)
@Config(qualifiers = "ru-rRU")
class BrandDenyListTest {
    private val context = ApplicationProvider.getApplicationContext<android.content.Context>()

    @Test
    fun noMergedStringResourceNamesARealBrand() {
        // core-ui's R lists every deck key; resolving through the app context gives the merged (overridden) value.
        val fields = app.verst.core.ui.R.string::class.java.fields + app.verst.R.string::class.java.fields
        assertTrue("merged string resources found: ${fields.size}", fields.size > 300)
        val bad = fields.filter { it.name !in BrandDenyList.handoffKeys }
            .flatMap { f -> BrandDenyList.hits(context.getString(f.getInt(null))).map { "${f.name}: $it" } }
        assertEquals(emptyList<String>(), bad)
        // The allow-list is explicit: each key exists, and each really is a hand-off app name.
        for (k in BrandDenyList.handoffKeys) {
            val v = context.getString(app.verst.core.ui.R.string::class.java.getField(k).getInt(null))
            assertTrue("$k = $v", v.startsWith("Яндекс "))
        }
    }

    @Test
    fun sharedTextIsMarkedAsDemo() {
        val shared = mockShareText(context, "Золотое кольцо · 761 км · 3 дня\n")
        assertTrue(shared, shared.endsWith(context.getString(app.verst.core.ui.R.string.mock_share_note)))
        assertTrue(BrandDenyList.brands.contains("Лукойл"))
    }
}
