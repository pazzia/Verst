package app.verst.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** D-IR-20 personal cabinet: settings round-trip and money in the chosen currency. */
class AppSettingsTest {
    private val rates = RatesDto("2026-10-27", "cbr", mapOf("USD" to 80.0, "EUR" to 90.0, "KZT" to 0.16, "IDR" to 0.005))

    @Test
    fun settingsRoundTripAndDefaults() {
        val s = AppSettings(AppLanguage.EN, "USD", AppTheme.DAY, TripStorage.FOLDER, "content://tree/x", "Verst")
        assertEquals(s, AppSettings.decode(AppSettings.encode(s)))
        assertEquals(AppSettings(), AppSettings.decode(null))
        assertEquals(AppSettings(), AppSettings.decode("not json"))
    }

    @Test
    fun unknownCurrencyAndUnusableStorageFallBack() {
        val s = AppSettings(currency = "XXX", storage = TripStorage.FOLDER, folderUri = null).sanitized()
        assertEquals(Money.RUB, s.currency)
        assertEquals(TripStorage.DEVICE, s.storage)
        assertEquals(TripStorage.DEVICE, AppSettings(storage = TripStorage.CLOUD).sanitized().storage)
    }

    @Test
    fun onlyTheThemeNeedsARestart() {
        val a = AppSettings()
        assertTrue(a.copy(theme = AppTheme.DAY).needsRestartComparedTo(a))
        assertFalse(a.copy(language = AppLanguage.EN, currency = "EUR").needsRestartComparedTo(a))
    }

    @Test
    fun moneyInTheChosenCurrency() {
        val t = RuFormat.THIN
        assertEquals("18${t}000 ₽", Money.format(18_000, Money.RUB, rates))
        assertEquals("$225", Money.format(18_000, "USD", rates))
        assertEquals("€200", Money.format(18_000, "EUR", rates))
        assertEquals("112${t}500 ₸", Money.format(18_000, "KZT", rates)) // ≥ 10 000 → tens
        assertEquals("3${t}600${t}000 Rp", Money.format(18_000, "IDR", rates)) // IDR → thousands
    }

    @Test
    fun withoutARateTheRoubleAmountIsShown() {
        assertEquals(Money.RUB, Money.effective("CNY", rates))
        assertEquals("500 ₽", Money.format(500, "CNY", rates))
        assertEquals("500 ₽", Money.format(500, "USD", RatesDto()))
    }

    @Test
    fun ratesDecodeIsLenient() {
        assertEquals(RatesDto(), RatesDto.decode("{oops"))
        val r = RatesDto.decode("""{"asOf":"2026-10-27","source":"cbr","rubPerUnit":{"USD":80.5}}""")
        assertTrue(r.has("USD"))
        assertFalse(r.has("EUR"))
    }
}
