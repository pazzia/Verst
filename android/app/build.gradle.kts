import java.util.zip.ZipFile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.chaquopy)
}
val repoRoot: File = rootDir.parentFile
val buildNumber = (System.getenv("VERST_BUILD_NUMBER") ?: "1").toInt()

/**
 * ENG-05: an AppMetrica API key from the Gradle property [property] or the environment variable [env] (property
 * first). Empty = analytics off: the app uses its no-op and never activates the SDK. A key is a UUID; anything else
 * fails the build rather than shipping a silently dead key.
 */
fun appMetricaKey(property: String, env: String): String {
    val key = ((findProperty(property) as String?)?.trim()?.takeIf { it.isNotEmpty() } ?: System.getenv(env)?.trim()).orEmpty()
    require(key.isEmpty() || Regex("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}").matches(key)) {
        "$property / $env: an AppMetrica API key is a UUID (got ${key.length} characters)"
    }
    return key
}
// Tracking plan §0.7: release builds report to the real key; debug and demo builds only ever see the separate test key.
val appMetricaReleaseKey = appMetricaKey("verst.appmetricaKey", "VERST_APPMETRICA_KEY")
val appMetricaTestKey = appMetricaKey("verst.appmetricaTestKey", "VERST_APPMETRICA_TEST_KEY")
android {
    namespace = "app.verst"
    compileSdk = 36
    defaultConfig {
        applicationId = "app.verst"
        minSdk = 26
        targetSdk = 36
        versionCode = buildNumber
        versionName = "0.2.$buildNumber-mock"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") } // M§3.3; Compose ships libandroidx.graphics.path.so
        buildConfigField("int", "BUILD_NUMBER", "$buildNumber")
        buildConfigField("String", "GIT_SHA", "\"${(System.getenv("VERST_GIT_SHA") ?: "local").take(12)}\"")
        // D-IR-20 build details: the UTC time CI built the APK (local builds say "local")
        buildConfigField("String", "BUILD_DATE", "\"${System.getenv("VERST_BUILD_DATE") ?: "local"}\"")
        // SRV-01: the test backend (ADR-0020); empty = no server, the phone engine only
        buildConfigField("String", "SERVER_URL", "\"${System.getenv("VERST_SERVER_URL") ?: ""}\"")
    }
    // Security review 28.10 (К-1): the demo signing key is a CI secret, never in the repository. CI decodes
    // VERST_SIGNING_KEYSTORE_B64 to a file and passes its path and passwords; without it (local builds, a missing
    // secret) the demo APK gets the throwaway debug key and will not install over a CI build.
    // a secret pasted with a trailing line break is still the same password
    fun signingEnv(name: String): String? = System.getenv(name)?.trimEnd('\r', '\n')
    val demoKeystore = System.getenv("VERST_SIGNING_KEYSTORE")?.let { file(it) }?.takeIf { it.isFile }
    signingConfigs {
        if (demoKeystore != null) {
            create("demo") {
                storeFile = demoKeystore
                storePassword = signingEnv("VERST_SIGNING_STORE_PASSWORD")
                keyAlias = signingEnv("VERST_SIGNING_KEY_ALIAS")
                keyPassword = signingEnv("VERST_SIGNING_KEY_PASSWORD")
            }
        }
    }
    buildTypes {
        create("demo") {
            initWith(getByName("release"))
            isDebuggable = false
            isMinifyEnabled = false
            applicationIdSuffix = ".demo"
            signingConfig = signingConfigs.getByName(if (demoKeystore != null) "demo" else "debug")
            matchingFallbacks += listOf("release")
            buildConfigField("String", "APPMETRICA_API_KEY", "\"$appMetricaTestKey\"")
        }
        getByName("debug") {
            applicationIdSuffix = ".debug"
            buildConfigField("String", "APPMETRICA_API_KEY", "\"$appMetricaTestKey\"")
        }
        // After `demo` on purpose: `initWith(release)` above must not copy the release key into the demo APK.
        getByName("release") {
            buildConfigField("String", "APPMETRICA_API_KEY", "\"$appMetricaReleaseKey\"")
        }
    }
    testBuildType = "demo" // androidTest APK targets the APK the CEO installs
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    buildFeatures { compose = true; buildConfig = true }
    sourceSets {
        getByName("main") { assets.srcDir(repoRoot.resolve("backend/planner/fixtures")) } // assets/worlds/*.json
        getByName("androidTest") { assets.srcDir(repoRoot.resolve("backend/planner/tests/golden")) } // cases/, snapshots/
    }
    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            all {
                it.systemProperty("verst.repoRoot", repoRoot.absolutePath)
                it.systemProperty(
                    "verst.screenshots.dir",
                    System.getenv("VERST_SCREENSHOTS_DIR")
                        ?: layout.buildDirectory.dir("outputs/screenshots").get().asFile.absolutePath,
                )
                it.maxHeapSize = "3g"
            }
        }
    }
    lint { abortOnError = true; warningsAsErrors = false; xmlReport = true; sarifReport = true; checkReleaseBuilds = false }
}
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
chaquopy {
    defaultConfig {
        version = "3.12"
        pip { install("tzdata==2025.2") }
        // fallback switch (ADR-0010 risks): extractPackages("verst_planner")
    }
    sourceSets { getByName("main") { srcDir(layout.buildDirectory.dir("planner-src")) } }
}

// Python sources: only the package `verst_planner` (no tests/, tools/, fixtures/ — the worlds ship once, as assets).
val stagePlanner = tasks.register<Sync>("stagePlannerSources") {
    from(repoRoot.resolve("backend/planner")) {
        include("verst_planner/**")
        exclude("**/__pycache__/**", "**/*.pyc")
    }
    into(layout.buildDirectory.dir("planner-src"))
}
tasks.matching { it.name.contains("Python") }.configureEach { dependsOn(stagePlanner) }

/**
 * Third-party licences of Chaquopy (DEV-101 review): every `<licenses>` entry of the `com.chaquo.python` POMs in
 * the Gradle cache and every LICENSE/COPYING/NOTICE entry of their jars, zips and aars, written to
 * `assets/licences/chaquopy.txt` (shipped in the APK) and `chaquopy.json` (read by CI into ci-logs).
 */
abstract class ChaquopyLicences : DefaultTask() {
    @get:Internal abstract val cacheRoot: DirectoryProperty

    /** POMs / jars resolved explicitly (the restored CI cache does not always contain them). */
    @get:InputFiles abstract val resolved: ConfigurableFileCollection
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun collect() {
        val root = cacheRoot.get().asFile
        val out = outputDir.get().asFile.resolve("licences").apply { deleteRecursively(); mkdirs() }
        val cached = if (root.isDirectory) root.walkTopDown().filter { it.isFile }.toList() else emptyList()
        val files = (cached + resolved.files.filter { it.isFile }).distinctBy { it.canonicalPath }.sortedBy { it.name }
        val pomLicence = Regex("<license>.*?<name>(.*?)</name>(?:.*?<url>(.*?)</url>)?.*?</license>", RegexOption.DOT_MATCHES_ALL)
        val entryName = Regex("(?i)(^|/)(LICEN[CS]E|COPYING|NOTICE)[^/]*$")
        val text = StringBuilder("Chaquopy (com.chaquo.python) — licences found in the build's Gradle cache\n\n")
        val index = mutableListOf<Map<String, String>>()
        // modules-2 layout: <group>/<artifact>/<version>/<sha1>/<file> (root = the group dir) → «artifact:version».
        fun coord(f: File): String = f.parentFile.parentFile.let { v -> "${v.parentFile.name}:${v.name}" }
        for (pom in files.filter { it.name.endsWith(".pom") }) {
            for (m in pomLicence.findAll(pom.readText())) {
                val (name, url) = m.destructured
                text.append("${coord(pom)}: ${name.trim()} ${url.trim()}\n")
                index += mapOf("artifact" to coord(pom), "source" to pom.name, "licence" to name.trim(), "url" to url.trim())
            }
        }
        for (archive in files.filter { f -> listOf(".jar", ".zip", ".aar").any { f.name.endsWith(it) } }) {
            ZipFile(archive).use { zip ->
                for (e in zip.entries().asSequence().filter { !it.isDirectory && entryName.containsMatchIn(it.name) && it.size < 300_000 }) {
                    val body = zip.getInputStream(e).bufferedReader().use { it.readText() }
                    val first = body.lineSequence().map { it.trim() }.firstOrNull { it.isNotEmpty() }.orEmpty()
                    text.append("\n===== ${coord(archive)} ${archive.name}!/${e.name}\n").append(body).append('\n')
                    index += mapOf("artifact" to coord(archive), "source" to "${archive.name}!/${e.name}", "firstLine" to first)
                }
            }
        }
        if (index.isEmpty()) text.append("NONE FOUND under ${root.path}\n")
        out.resolve("chaquopy.txt").writeText(text.toString())
        out.resolve("chaquopy.json").writeText(groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(index)) + "\n")
    }
}
// The Chaquopy plugin and runtime artifacts whose licences ship in the APK, resolved from Maven Central.
val chaquopyLicenceArtifacts = configurations.detachedConfiguration(
    dependencies.create("com.chaquo.python:gradle:${libs.versions.chaquopy.get()}@pom"),
    dependencies.create("com.chaquo.python:gradle:${libs.versions.chaquopy.get()}@jar"),
    dependencies.create("com.chaquo.python:target:3.12.7-0@pom"),
).apply { isTransitive = false }
val chaquopyLicences = tasks.register<ChaquopyLicences>("chaquopyLicences") {
    cacheRoot.set(File(gradle.gradleUserHomeDir, "caches/modules-2/files-2.1/com.chaquo.python"))
    resolved.from(chaquopyLicenceArtifacts)
    outputs.upToDateWhen { false }
    mustRunAfter(tasks.matching { it.name.contains("Python") }) // the runtime artifacts are resolved by then
}
androidComponents {
    onVariants { variant -> variant.sources.assets?.addGeneratedSourceDirectory(chaquopyLicences, ChaquopyLicences::outputDir) }
}
dependencies {
    implementation(project(":core-model"))
    implementation(project(":core-ui"))
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.foundation)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.kotlinx.coroutines.android)
    // Sprint 3 (ADR-0012 §6–7): the only two network uses — Commons photos (Coil) and Nominatim addresses.
    implementation(libs.okhttp)
    implementation(libs.coil.compose)
    // ENG-05: AppMetrica (MIT). Activated only when the build has a key (`APPMETRICA_API_KEY`).
    implementation(libs.appmetrica.analytics)
    // Release review P2-4: no ui-test-manifest in the demo APK (it merges an exported ComponentActivity); the
    // Robolectric screen tests run on `debug` (CI `:app:testDebugUnitTest`).
    debugImplementation(libs.compose.ui.test.manifest)
    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.okhttp.mockwebserver)
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.okhttp.mockwebserver)
}
