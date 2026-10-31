package app.verst.core.model

/** Build number and commit of the running app (DEV-100); shown as «Сборка <n> · <sha7>». */
data class BuildInfo(val number: Int, val gitSha: String) {
    val sha7: String get() = gitSha.take(7)
    val label: String get() = "Сборка $number · $sha7"
}
