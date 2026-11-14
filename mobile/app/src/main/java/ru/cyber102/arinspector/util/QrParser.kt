package ru.cyber102.arinspector.util

object QrParser {
    private val FALLBACK_ID_REGEX = Regex("[A-Za-z][A-Za-z0-9_-]{1,31}")
    private val VALID_KEY_CHAR_REGEX = Regex("[A-HJ-NP-Z2-9]")

    fun extractEquipmentId(rawText: String?): String? {
        if (rawText.isNullOrBlank()) return null
        val trimmed = rawText.trim()

        val afterSlash = trimmed.substringAfterLast('/', trimmed)
        val beforeQuery = afterSlash.substringBefore('?').trim()

        if (beforeQuery.isNotEmpty() && beforeQuery.none { it.isWhitespace() }) {
            return beforeQuery
        }

        return FALLBACK_ID_REGEX.find(trimmed)?.value
    }

    /**
     * Фильтрует индивидуальный ключ: допустимы латинские A-H, J-N, P-Z и цифры 2-9,
     * пробелы и дефисы игнорируются, максимум 10 символов в верхнем регистре.
     */
    fun sanitizeAccessKey(input: String): String {
        val sb = StringBuilder(10)
        for (ch in input) {
            if (ch.isWhitespace() || ch == '-') continue
            val upper = ch.uppercaseChar()
            if (VALID_KEY_CHAR_REGEX.matches(upper.toString())) {
                sb.append(upper)
                if (sb.length == 10) break
            }
        }
        return sb.toString()
    }
}
