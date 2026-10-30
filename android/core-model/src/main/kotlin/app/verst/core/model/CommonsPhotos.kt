package app.verst.core.model

import app.verst.core.model.dto.PhotoCreditDto
import app.verst.core.model.dto.PoiImageDto

/**
 * Wikimedia Commons URLs for a file name: the same form the engine builds (`catalogue/photos.py`,
 * ADR-0012 §6): `Special:FilePath/<file>?width=<w>` redirects to a rasterised thumbnail on upload.wikimedia.org.
 */
object CommonsPhotos {
    const val CARD_WIDTH = 800
    const val THUMB_WIDTH = 400
    private const val BASE = "https://commons.wikimedia.org/wiki/"

    /** Python `quote(s, safe="()_,-.")`: unreserved ASCII + `()_,-.~` stay, every other UTF-8 byte is %XX. */
    fun title(file: String): String {
        val s = file.trim().replace(' ', '_')
        val out = StringBuilder()
        for (b in s.toByteArray(Charsets.UTF_8)) {
            val c = b.toInt() and 0xFF
            val ch = c.toChar()
            if (c < 0x80 && (ch.isLetterOrDigit() || ch in "()_,-.~")) out.append(ch) else out.append('%').append("%02X".format(c))
        }
        return out.toString()
    }

    fun thumbUrl(file: String, width: Int): String = "${BASE}Special:FilePath/${title(file)}?width=$width"

    fun pageUrl(file: String): String = "${BASE}File:${title(file)}"

    /**
     * S3-R3 debug override (real photos before the data run): files that exist on Commons, picked to cover the
     * frame's cases — landscape JPEG (crop), portrait JPEG (upper-third crop), SVG → PNG (flag, contain on the
     * mat when extreme), transparent PNG (coat of arms → contain).
     */
    val DEBUG_FILES = listOf(
        "Moscow July 2011-16.jpg",
        "Mona Lisa, by Leonardo da Vinci, from C2RMF retouched.jpg",
        "Coat of Arms of the Russian Federation.svg",
        "Example.jpg",
        "Flag of Russia.svg",
    )

    /** [image] with the card / thumb / page of [file]; area and label stay (a hotel keeps «Фото района»). */
    fun debugImage(image: PoiImageDto?, file: String): PoiImageDto = PoiImageDto(
        card = thumbUrl(file, CARD_WIDTH),
        thumb = thumbUrl(file, THUMB_WIDTH),
        page = pageUrl(file),
        credit = PhotoCreditDto(author = file.substringBeforeLast('.'), licence = "Wikimedia Commons"),
        isArea = image?.isArea ?: false,
        labelRu = image?.labelRu,
    )
}
