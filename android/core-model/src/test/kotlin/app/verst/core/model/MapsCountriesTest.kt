package app.verst.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** CEO 29.10: the maps app of the hand-off by the country the phone is in, and the user's choice over it. */
class MapsCountriesTest {
    @Test
    fun russiaAndTheRouterApiCountriesGetYandex() {
        assertEquals(MapsApp.YANDEX, MapsCountries.auto("RU"))
        assertEquals(MapsApp.YANDEX, MapsCountries.auto("ru")) // TelephonyManager answers in lower case
        assertEquals(MapsApp.YANDEX, MapsCountries.auto(" kz "))
        for (c in listOf("TR", "AZ", "AM", "KZ", "KG", "TJ", "BY", "GE", "UZ", "MD")) assertEquals(c, MapsApp.YANDEX, MapsCountries.auto(c))
    }

    @Test
    fun elsewhereGoogle() {
        assertEquals(MapsApp.GOOGLE, MapsCountries.auto("DE"))
        assertEquals(MapsApp.GOOGLE, MapsCountries.auto("us"))
        assertEquals(MapsApp.GOOGLE, MapsCountries.auto("TH"))
    }

    @Test
    fun unknownCountryGetsYandex() {
        assertEquals(MapsApp.YANDEX, MapsCountries.auto(null))
        assertEquals(MapsApp.YANDEX, MapsCountries.auto(""))
        assertEquals(MapsApp.YANDEX, MapsCountries.auto("RUS")) // not an alpha-2 code
        assertNull(MapsCountries.normalize("1A"))
        assertEquals("RU", MapsCountries.normalize("ru"))
    }

    @Test
    fun theUsersChoiceWins() {
        assertEquals(MapsApp.GOOGLE, MapsCountries.preferred(MapsChoice.AUTO, "DE"))
        assertEquals(MapsApp.YANDEX, MapsCountries.preferred(MapsChoice.YANDEX, "DE"))
        assertEquals(MapsApp.GOOGLE, MapsCountries.preferred(MapsChoice.GOOGLE, "RU"))
        assertEquals(MapsApp.GOOGLE, MapsCountries.preferred(MapsChoice.GOOGLE, null))
        assertEquals(MapsApp.YANDEX, MapsCountries.preferred(MapsChoice.AUTO, null))
    }

    @Test
    fun theChoiceIsASettingThatDefaultsToAutomatic() {
        assertEquals(MapsChoice.AUTO, AppSettings().mapsApp)
        val s = AppSettings(mapsApp = MapsChoice.GOOGLE)
        assertEquals(s, AppSettings.decode(AppSettings.encode(s)))
        // an older settings file without the field, and an unknown value, fall back to automatic
        assertEquals(MapsChoice.AUTO, AppSettings.decode("""{"currency":"USD"}""").mapsApp)
        assertEquals(MapsChoice.AUTO, AppSettings.decode("""{"currency":"USD","mapsApp":"HERE"}""").mapsApp)
        assertTrue(AppSettings.decode("""{"currency":"USD","mapsApp":"HERE"}""").currency == "USD")
    }
}
