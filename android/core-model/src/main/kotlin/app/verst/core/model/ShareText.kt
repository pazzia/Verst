package app.verst.core.model

/**
 * CEO 29.10 (trips abroad): the engine's share text says its rouble total as is. When that total leaves the costs
 * abroad out (`trip.abroad.roubleTotalIncomplete`), the total line gets [note] («без расходов за границей»), so a
 * shared «Итого ≈ 300 ₽» is not read as the whole trip. The engine's `explain/share.py` is unchanged (its contract).
 */
object ShareText {
    /** «Итого ≈ 300 ₽ на 2 чел. — без расходов за границей»; [text] unchanged when complete or already said. */
    fun withAbroad(text: String, incomplete: Boolean, note: String): String {
        if (!incomplete || note.isBlank() || text.contains(note)) return text
        val lines = text.trimEnd().lines().toMutableList()
        val total = lines.indexOfLast { it.trimStart().startsWith("Итого") || it.trimStart().startsWith("Total") }
        if (total < 0) return text.trimEnd() + "\n" + note.replaceFirstChar { it.uppercase() }
        lines[total] = lines[total].trimEnd() + " — " + note
        return lines.joinToString("\n")
    }
}
