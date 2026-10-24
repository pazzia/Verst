pluginManagement { repositories { google(); mavenCentral(); gradlePluginPortal() } }
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.PREFER_SETTINGS)   // not FAIL_*: a plugin adding a repo must not break the build
    repositories { google(); mavenCentral() }
}
rootProject.name = "verst"
include(":core-model", ":core-ui", ":app")
