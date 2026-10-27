package app.verst.core.model

import app.verst.core.model.dto.HandoffDto
import app.verst.core.model.dto.HandoffLinksDto
import java.net.URLEncoder
import java.security.KeyFactory
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.PKCS8EncodedKeySpec
import java.util.Base64

/**
 * ADR-0015 §1: signs Яндекс Навигатор / Карты launch URLs, so they are not limited to 5 launches a day per device.
 *
 * Yandex's scheme: the URL already carries `client=<id>` (the engine adds it when `HandoffArgs` passes the client);
 * SHA256withRSA over the whole URL string, Base64, URL-encoded, appended as the last parameter `&signature=`.
 * [privateKey] is the PKCS#8 key Yandex issues, as PEM or its bare Base64 body. A PKCS#1 key
 * (`BEGIN RSA PRIVATE KEY`) is converted once with `openssl pkcs8 -topk8 -nocrypt`.
 */
class HandoffSigner(val client: String, privateKey: String) {
    private val key: PrivateKey = parse(privateKey)

    init {
        require(CLIENT.matches(client)) { "client id: letters, digits, '.', '_' or '-'" }
    }

    fun sign(url: String): String {
        val s = Signature.getInstance("SHA256withRSA")
        s.initSign(key)
        s.update(url.toByteArray(Charsets.UTF_8))
        val sig = Base64.getEncoder().encodeToString(s.sign())
        return "$url&signature=${URLEncoder.encode(sig, "UTF-8")}"
    }

    /** The engine's hand-off with every link listed in `toSign` replaced by its signed form (`web` stays as is). */
    fun sign(h: HandoffDto): HandoffDto = h.copy(
        parts = h.parts.map { p ->
            val toSign = p.toSign ?: return@map p
            val signed = toSign.mapValues { (_, url) -> sign(url) }
            p.copy(links = p.links.withSigned(signed))
        },
    )

    private fun HandoffLinksDto.withSigned(s: Map<String, String>) = copy(
        navigator = s["navigator"] ?: navigator,
        navigatorNext = s["navigatorNext"] ?: navigatorNext,
        maps = s["maps"] ?: maps,
    )

    companion object {
        private val CLIENT = Regex("[A-Za-z0-9._-]+")

        /** The build's signer, or null when the build has no key (unsigned hand-off) or the key does not parse. */
        fun of(client: String, privateKey: String, onError: (Exception) -> Unit = {}): HandoffSigner? {
            if (client.isBlank() || privateKey.isBlank()) return null
            return try {
                HandoffSigner(client.trim(), privateKey)
            } catch (e: Exception) {
                onError(e)
                null
            }
        }

        fun parse(privateKey: String): PrivateKey {
            require("BEGIN RSA PRIVATE KEY" !in privateKey) { "PKCS#1 key: convert with `openssl pkcs8 -topk8 -nocrypt`" }
            val body = privateKey.replace(Regex("-----[A-Z ]+-----"), "").replace(Regex("\\s"), "")
            return KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(Base64.getDecoder().decode(body)))
        }
    }
}
