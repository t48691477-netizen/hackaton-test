package ru.cyber102.arinspector.data

import kotlinx.coroutines.delay

/**
 * Локальный «сервер» на случай, если бэкенд недоступен.
 * Это страховка для сцены: приложение обязано показать полный сценарий без Wi-Fi.
 */
object DemoData {

    private val pump402 = Equipment(
        id = "PUMP-402",
        name = "Насосный агрегат ЦНС 38-220",
        location = "Цех №4 · Насосная станция, поз. 12",
        components = listOf(
            EquipmentComponent("C1", "Корпус насоса", Offset3(0.00f, 0.10f, 0.00f), 0.30f),
            EquipmentComponent("C2", "Патрубок нагнетания", Offset3(0.32f, 0.36f, 0.06f), 0.22f),
            EquipmentComponent("C3", "Фланец №3", Offset3(-0.28f, 0.44f, -0.04f), 0.20f),
            EquipmentComponent("C4", "Подшипниковый узел", Offset3(0.14f, -0.02f, 0.26f), 0.24f),
            EquipmentComponent("C5", "Электродвигатель", Offset3(-0.40f, 0.18f, 0.44f), 0.32f),
            EquipmentComponent("C6", "Муфта", Offset3(0.06f, 0.24f, 0.40f), 0.20f)
        )
    )

    private val pump118 = Equipment(
        id = "PUMP-118",
        name = "Насос центробежный К-80",
        location = "Цех №2 · Линия подачи реагента",
        components = listOf(
            EquipmentComponent("C1", "Корпус", Offset3(0f, 0.1f, 0f)),
            EquipmentComponent("C2", "Патрубок", Offset3(0.3f, 0.3f, 0f)),
            EquipmentComponent("C3", "Опорная рама", Offset3(-0.25f, -0.05f, 0.2f))
        )
    )

    private val valve77 = Equipment(
        id = "VALVE-77",
        name = "Задвижка клиновая DN200",
        location = "Цех №4 · Узел №7",
        components = listOf(
            EquipmentComponent("C1", "Корпус задвижки", Offset3(0f, 0.05f, 0f)),
            EquipmentComponent("C2", "Шпиндель", Offset3(0f, 0.35f, 0f)),
            EquipmentComponent("C3", "Фланцы", Offset3(0.28f, 0.1f, 0f))
        )
    )

    private val catalogue = mapOf(
        pump402.id to pump402,
        pump118.id to pump118,
        valve77.id to valve77
    )

    val demoIds: List<String> = catalogue.keys.toList()

    suspend fun equipment(id: String): Equipment {
        delay(650)
        return catalogue[id] ?: Equipment(
            id = id,
            name = "Оборудование $id",
            location = "Зона не определена",
            components = pump402.components
        )
    }

    suspend fun inspection(equipmentId: String): InspectResponse {
        delay(1650)
        return when (equipmentId) {
            "PUMP-118" -> InspectResponse(
                status = "medium",
                defects = listOf(
                    Defect(
                        id = "D-118-1",
                        nodeId = "C2",
                        type = "wear",
                        title = "Износ уплотнения патрубка",
                        confidence = 0.78f,
                        severity = "medium",
                        polygon = listOf(
                            NormalizedPoint(0.52f, 0.38f),
                            NormalizedPoint(0.70f, 0.34f),
                            NormalizedPoint(0.76f, 0.46f),
                            NormalizedPoint(0.60f, 0.52f)
                        ),
                        analysis = "Кромка уплотнения имеет следы абразивного износа. " +
                            "Риск протечки при повышении давления выше 1.2 МПа.",
                        recommendation = "Заменить уплотнение в плановом порядке."
                    )
                ),
                analysis = "Обнаружен один дефект средней критичности. " +
                    "Оборудование сохраняет работоспособность, требуется плановое ТО.",
                inspectedAt = "2026-11-13T10:42:00Z",
                model = "demo-vision"
            )

            "VALVE-77" -> InspectResponse(
                status = "ok",
                defects = emptyList(),
                analysis = "Дефектов не обнаружено. Поверхности чистые, следов коррозии нет.",
                inspectedAt = "2026-11-13T10:42:00Z",
                model = "demo-vision"
            )

            else -> InspectResponse(
                status = "high",
                defects = listOf(
                    Defect(
                        id = "D-402-1",
                        nodeId = "C3",
                        type = "rust",
                        title = "Коррозия фланцевого соединения",
                        confidence = 0.94f,
                        severity = "high",
                        polygon = listOf(
                            NormalizedPoint(0.54f, 0.345f),
                            NormalizedPoint(0.66f, 0.300f),
                            NormalizedPoint(0.77f, 0.365f),
                            NormalizedPoint(0.79f, 0.480f),
                            NormalizedPoint(0.69f, 0.550f),
                            NormalizedPoint(0.56f, 0.505f)
                        ),
                        analysis = "На поверхности фланца №3 обнаружена очаговая коррозия " +
                            "с локальной потерей сечения до 12%. Наиболее вероятная причина — " +
                            "разрушение прокладки и постоянный контакт с влажной средой. " +
                            "Риск: потеря герметичности и разгерметизация соединения под давлением.",
                        recommendation = "Зачистить поверхность до металла, заменить прокладку, " +
                            "протянуть крепёж моментом 120 Н·м. Повторный осмотр через 72 часа."
                    ),
                    Defect(
                        id = "D-402-2",
                        nodeId = "C1",
                        type = "crack",
                        title = "Трещина на корпусе насоса",
                        confidence = 0.87f,
                        severity = "high",
                        polygon = listOf(
                            NormalizedPoint(0.245f, 0.555f),
                            NormalizedPoint(0.415f, 0.555f),
                            NormalizedPoint(0.415f, 0.700f),
                            NormalizedPoint(0.245f, 0.700f)
                        ),
                        bbox = listOf(0.245f, 0.555f, 0.415f, 0.700f),
                        analysis = "Линейный дефект длиной ~38 мм с branching-паттерном, " +
                            "характерным для усталостной трещины. Расположен в зоне концентрации " +
                            "напряжений у опорного пояса. Требует немедленной разгрузки узла.",
                        recommendation = "Остановить агрегат, провести УЗК-контроль, " +
                            "подготовить замену корпуса. Эксплуатация до устранения не рекомендуется."
                    ),
                    Defect(
                        id = "D-402-3",
                        nodeId = "C6",
                        type = "rust",
                        title = "Поверхностная коррозия муфты",
                        confidence = 0.72f,
                        severity = "medium",
                        polygon = listOf(
                            NormalizedPoint(0.435f, 0.605f),
                            NormalizedPoint(0.520f, 0.585f),
                            NormalizedPoint(0.545f, 0.655f),
                            NormalizedPoint(0.455f, 0.680f)
                        ),
                        analysis = "Поверхностная коррозия без признаков потери сечения. " +
                            "На эксплуатацию влияет слабо, но требует защиты покрытием.",
                        recommendation = "Обработать преобразователем ржавчины и покрыть защитным составом."
                    )
                ),
                analysis = "Зафиксировано 3 дефекта, два из них высокого риска. " +
                    "Критический узел — фланец №3: коррозия прогрессирует по кромке. " +
                    "Корпус насоса требует УЗК-контроля. Рекомендуется остановить агрегат " +
                    "и оформить акт ТО с заказом запчастей.",
                inspectedAt = "2026-11-13T10:42:00Z",
                model = "demo-llm-vision"
            )
        }
    }
}
