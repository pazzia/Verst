package app.verst.core.model

import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.HandoffLinksDto
import app.verst.core.model.dto.HandoffPartDto
import java.net.URLDecoder
import java.security.KeyPairGenerator
import java.security.Signature
import java.util.Base64
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** ADR-0015 §1: Яндекс URL-scheme signing (SHA256withRSA, Base64, URL-encoded, last parameter). */
class HandoffSignerTest {
    private val pair = KeyPairGenerator.getInstance("RSA").apply { initialize(2048) }.generateKeyPair()
    private val pem = "-----BEGIN PRIVATE KEY-----\n" +
        Base64.getMimeEncoder(64, "\n".toByteArray()).encodeToString(pair.private.encoded) +
        "\n-----END PRIVATE KEY-----\n"
    private val url = "yandexnavi://build_route_on_map?lat_to=57.626100&lon_to=39.884500&client=verst"

    private fun verifies(signed: String, original: String): Boolean {
        assertTrue(signed.startsWith("$original&signature="))
        val sig = URLDecoder.decode(signed.substringAfterLast("&signature="), "UTF-8")
        return Signature.getInstance("SHA256withRSA").run {
            initVerify(pair.public)
            update(original.toByteArray(Charsets.UTF_8))
            verify(Base64.getDecoder().decode(sig))
        }
    }

    @Test
    fun signatureIsTheLastParameterAndVerifiesWithThePublicKey() {
        val signed = HandoffSigner("verst", pem).sign(url)
        assertTrue(verifies(signed, url))
        // '+', '/' and '=' of Base64 are percent-encoded, so the signature survives the URI parser
        val raw = signed.substringAfterLast("&signature=")
        assertFalse(raw.contains('+') || raw.contains('/') || raw.contains('='))
    }

    @Test
    fun bareBase64BodyWorksLikePem() {
        val body = Base64.getEncoder().encodeToString(pair.private.encoded)
        assertTrue(verifies(HandoffSigner("verst", body).sign(url), url))
    }

    @Test
    fun handoffSignsEveryLinkListedInToSignAndLeavesTheWebLink() {
        val maps = "yandexmaps://maps.yandex.ru/?rtext=~57.626100,39.884500&rtt=auto&client=verst"
        val web = "https://yandex.ru/maps/?rtext=~57.626100,39.884500&rtt=auto"
        val h = HandoffDto(
            mode = "car",
            day = 1,
            parts = listOf(
                HandoffPartDto(
                    links = HandoffLinksDto(navigator = url, maps = maps, web = web, navigatorNext = url),
                    toSign = mapOf("navigator" to url, "navigatorNext" to url, "maps" to maps),
                ),
            ),
        )
        val l = HandoffSigner("verst", pem).sign(h).parts.single().links
        assertTrue(verifies(l.navigator!!, url))
        assertTrue(verifies(l.navigatorNext!!, url))
        assertTrue(verifies(l.maps!!, maps))
        assertEquals(web, l.web)
    }

    @Test
    fun aHandoffWithoutToSignIsUnchanged() {
        val h = HandoffDto(mode = "walk", parts = listOf(HandoffPartDto(links = HandoffLinksDto(maps = "yandexmaps://x"))))
        assertEquals(h, HandoffSigner("verst", pem).sign(h))
    }

    @Test
    fun noKeyMeansUnsignedAndABadKeyIsReportedNotThrown() {
        assertNull(HandoffSigner.of("", ""))
        assertNull(HandoffSigner.of("verst", ""))
        var error: Exception? = null
        assertNull(HandoffSigner.of("verst", "bm90IGEga2V5") { error = it })
        assertNotNull(error)
        val pkcs1 = "-----BEGIN RSA PRIVATE KEY-----\nAAAA\n-----END RSA PRIVATE KEY-----"
        assertNull(HandoffSigner.of("verst", pkcs1) { error = it })
        assertTrue(error!!.message!!.contains("openssl pkcs8"))
        assertNotNull(HandoffSigner.of("verst", pem))
    }

    @Test
    fun argsCarryTheClientOnlyWhenSigning() {
        fun client(json: String) = EngineJson.json.parseToJsonElement(json).jsonObject["signing"]?.jsonObject?.get("client")?.jsonPrimitive?.content
        assertNull(client(HandoffArgs.day(1)))
        assertEquals("verst", client(HandoffArgs.day(1, "verst")))
        assertEquals("verst", client(HandoffArgs.fromStop("d1s02", "verst")))
        assertEquals("verst", client(HandoffArgs.walk("verst")))
        assertNull(client(HandoffArgs.walk()))
    }
}
