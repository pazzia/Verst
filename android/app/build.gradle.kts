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
    sourceSets { getByName("main") { srcDir(repoRoot.resolve("backend/planner")) } }
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
