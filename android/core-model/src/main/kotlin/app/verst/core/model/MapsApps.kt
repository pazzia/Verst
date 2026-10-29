package app.verst.core.model

import java.util.Locale
import kotlinx.serialization.Serializable

/**
 * «Настройки → Навигация» (CEO 29.10): which maps app gets the day's route. [AUTO] follows the country the phone is
 * in ([MapsCountries.auto]); the other two are the user's own choice and always win.
 */
@Serializable
enum class MapsChoice { AUTO, YANDEX, GOOGLE }

/** The maps app a route is handed to with all its points (the navigator takes only one point from us). */
enum class MapsApp { YANDEX, GOOGLE }

/** Where Яндекс builds routes with confidence, and the automatic choice that follows from it. */
object MapsCountries {
    /**
     * Яндекс Router API: страны, где строятся маршруты — Россия, Абхазия, Турция, Азербайджан, Армения, Казахстан,
     * Киргизия, Таджикистан, Беларусь, Грузия, Узбекистан, Молдова. Абхазия has no ISO 3166 code: phones there
     * report RU (Russian SIM cards) or GE (MCC 289), both in the set. Everywhere else Google Карты lead.
     */
    val YANDEX: Set<String> = setOf("RU", "TR", "AZ", "AM", "KZ", "KG", "TJ", "BY", "GE", "UZ", "MD")

    /** [iso] as a two-letter upper-case code («ru » → «RU»), or null when it is not one. */
    fun normalize(iso: String?): String? =
        iso?.trim()?.uppercase(Locale.ROOT)?.takeIf { it.length == 2 && it.all { c -> c in 'A'..'Z' } }

    /** The automatic choice for [country]: Яндекс where it routes well, Google elsewhere; unknown → Яндекс (the app is for Russia). */
    fun auto(country: String?): MapsApp {
        val c = normalize(country) ?: return MapsApp.YANDEX
        return if (c in YANDEX) MapsApp.YANDEX else MapsApp.GOOGLE
    }

    /** The app that leads: the user's [choice] wins; [MapsChoice.AUTO] follows [country]. */
    fun preferred(choice: MapsChoice, country: String?): MapsApp = when (choice) {
        MapsChoice.AUTO -> auto(country)
        MapsChoice.YANDEX -> MapsApp.YANDEX
        MapsChoice.GOOGLE -> MapsApp.GOOGLE
    }
}
