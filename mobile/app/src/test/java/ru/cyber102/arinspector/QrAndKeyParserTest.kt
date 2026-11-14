package ru.cyber102.arinspector

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import ru.cyber102.arinspector.util.QrParser

class QrAndKeyParserTest {

    @Test
    fun `extracts equipment id from url with query`() {
        assertEquals(
            "pump_station_3",
            QrParser.extractEquipmentId("https://kst.local/eq/pump_station_3?tab=info")
        )
    }

    @Test
    fun `extracts equipment id via regex when text has spaces`() {
        assertEquals(
            "SN-001",
            QrParser.extractEquipmentId("Оборудование SN-001 Цех 2")
        )
    }

    @Test
    fun `returns null for blank qr text`() {
        assertNull(QrParser.extractEquipmentId("   "))
    }

    @Test
    fun `sanitizes access key uppercase without spaces hyphens or ambiguous chars`() {
        assertEquals(
            "ABCDEF2345",
            QrParser.sanitizeAccessKey("ab-cd ef 23-45 iol01")
        )
    }
}
