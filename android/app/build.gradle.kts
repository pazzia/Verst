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
    }
    signingConfigs {
        create("demo") {
            storeFile = file("demo.keystore")
            storePassword = "verstdemo"
            keyAlias = "verst-demo"
            keyPassword = "verstdemo"
        }
    }
    buildTypes {
        create("demo") {
            initWith(getByName("release"))
            isDebuggable = false
            isMinifyEnabled = false
            applicationIdSuffix = ".demo"
            signingConfig = signingConfigs.getByName("demo")
            matchingFallbacks += listOf("release")
        }
        getByName("debug") {
            applicationIdSuffix = ".debug"
            signingConfig = signingConfigs.getByName("demo")
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
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun collect() {
        val root = cacheRoot.get().asFile
        val out = outputDir.get().asFile.resolve("licences").apply { deleteRecursively(); mkdirs() }
        val files = root.walkTopDown().filter { it.isFile }.sortedBy { it.path }.toList()
        val pomLicence = Regex("<license>.*?<name>(.*?)</name>(?:.*?<url>(.*?)</url>)?.*?</license>", RegexOption.DOT_MATCHES_ALL)
        val entryName = Regex("(?i)(^|/)(LICEN[CS]E|COPYING|NOTICE)[^/]*$")
        val text = StringBuilder("Chaquopy (com.chaquo.python) — licences found in the build's Gradle cache\n\n")
        val index = mutableListOf<Map<String, String>>()
        fun coord(f: File): String = f.relativeTo(root).path.split(File.separatorChar).take(2).joinToString(":")
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
val chaquopyLicences = tasks.register<ChaquopyLicences>("chaquopyLicences") {
    cacheRoot.set(File(gradle.gradleUserHomeDir, "caches/modules-2/files-2.1/com.chaquo.python"))
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
    "demoImplementation"(libs.compose.ui.test.manifest)
    debugImplementation(libs.compose.ui.test.manifest)
    testImplementation(libs.junit)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.core)
    testImplementation(platform(libs.compose.bom))
    testImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(platform(libs.compose.bom))
    androidTestImplementation(libs.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
}
