import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.config import settings
from app.schemas.defect import DefectItem, DefectCategory
from app.schemas.inspection import LLMRecommendation, CriticalityLevel

logger = logging.getLogger("toir_llm")

CHIEF_EXPERT_SYSTEM_PROMPT = """
Ты — Главный эксперт по техническому обслуживанию и ремонту (ТОиР) промышленного оборудования и опасных производственных объектов с опытом более 25 лет.
Твоя задача — проводить глубокий предиктивный и диагностический инженерный анализ дефектов (очаги коррозии, дефекты сварных соединений, трещины, усталостные повреждения), обнаруженных системами машинного зрения на агрегатах.

ТВОИ ПРАВИЛА:
1. Анализируй дефекты с учетом типа оборудования, возраста узла, даты последнего планового ТО и уверенности нейросетей.
2. Определи уровень критичности (criticality):
   - "high": наличие трещин, глубокая язвенная/щелевая коррозия, дефекты сварных швов (Bad Weld) на несущих или напорных узлах, создающие риск разрушения, аварии или внепланового останова производства.
   - "medium": умеренная коррозия, поверхностные поры или непровары, требующие устранения при ближайшем планово-предупредительном ремонте (ППР).
   - "low": начальные поверхностные следы окисления, незначительные отклонения, не угрожающие целостности агрегата в текущем межремонтном интервале.
3. Четко обоснуй физико-механическую и эксплуатационную причину возникновения дефекта (probable_cause) с привязкой к возрасту узла и сроку с последнего ТО.
4. Предоставь конкретную пошаговую инженерную рекомендацию (recommendations) в виде списка действий:
   - Немедленные действия (ограничение параметров, разгрузка, вывод в резерв);
   - Инструментальный контроль (УЗК, вихретоковый контроль, толщинометрия);
   - Ремонтная технология (зачистка, выбор электродов, подогрев, термообработка, антикоррозийная система);
   - Контроль качества и допуск к работе.

ФОРМАТ ОТВЕТА:
Строгий JSON следующей структуры, без лишнего вступительного текста:
{
  "criticality": "low" | "medium" | "high",
  "probable_cause": "Подробное инженерное описание причины дефекта",
  "recommendations": [
    "Шаг 1: ...",
    "Шаг 2: ...",
    "Шаг 3: ..."
  ]
}
""".strip()

class TOIRExpertService:
    def __init__(self):
        self.system_prompt = CHIEF_EXPERT_SYSTEM_PROMPT

    def _format_defects_input(self, defects: List[DefectItem]) -> List[Dict[str, Any]]:
        return [
            {
                "id": d.id,
                "label": d.label,
                "category": d.category.value if hasattr(d.category, "value") else str(d.category),
                "confidence": round(d.confidence, 4),
                "model_source": d.model_source,
                "has_segmentation_mask": d.polygon is not None and len(d.polygon) > 0,
            }
            for d in defects
        ]

    def _call_gemini_api(self, prompt: str) -> Optional[LLMRecommendation]:
        """Вызов Google Gemini API через официальный SDK или прямой HTTP запрос."""
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        try:
            import requests
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{self.system_prompt}\n\nВХОДНЫЕ ДАННЫЕ:\n{prompt}"}]
                    }
                ],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.2
                }
            }
            resp = requests.post(url, json=payload, timeout=12)
            if resp.status_code == 200:
                result_json = resp.json()
                text = result_json["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return LLMRecommendation(
                    criticality=CriticalityLevel(parsed.get("criticality", "medium").lower()),
                    probable_cause=parsed.get("probable_cause", "Не установлена"),
                    recommendations=parsed.get("recommendations", [])
                )
        except Exception as e:
            logger.warning(f"Ошибка вызова Gemini API: {e}. Переключение на локальный экспертный движок.")
        return None

    def _generate_rule_based_expert(
        self,
        equipment_name: str,
        component_age: str,
        last_maintenance_date: str,
        defects: List[DefectItem]
    ) -> LLMRecommendation:
        """
        Инженерный экспертный движок ТОиР (детерминированный fallback).
        Использует промышленную логику стандартов ГОСТ 18442, ГОСТ 14782 и правил Ростехнадзора.
        """
        if not defects:
            return LLMRecommendation(
                criticality=CriticalityLevel.LOW,
                probable_cause=f"Агрегат '{equipment_name}' (возраст: {component_age}, последнее ТО: {last_maintenance_date}) находится в удовлетворительном техническом состоянии. Визуально-оптическим методом дефектов не выявлено.",
                recommendations=[
                    "1. Эксплуатация агрегата разрешена в штатном паспортном режиме.",
                    "2. Продолжить регламентный мониторинг вибрации и температуры подшипниковых узлов.",
                    "3. Провести очередной осмотр согласно утвержденному графику ППР."
                ]
            )

        has_corrosion = any(d.category == DefectCategory.CORROSION for d in defects)
        has_welding = any(d.category in (DefectCategory.WELDING_DEFECT, DefectCategory.CRACK) for d in defects)
        max_conf = max(d.confidence for d in defects)

        # Оценка критичности
        if has_welding or (has_corrosion and max_conf > 0.85):
            criticality = CriticalityLevel.HIGH
        elif has_corrosion and max_conf > 0.5:
            criticality = CriticalityLevel.MEDIUM
        else:
            criticality = CriticalityLevel.LOW

        # Формирование физической причины
        causes = []
        if has_welding:
            causes.append(
                f"Нарушение сплошности сварного шва вследствие циклических знакопеременных напряжений, "
                f"усталостной микродеформации металла шва и возможного нарушения термообработки при предыдущем ТО ({last_maintenance_date})"
            )
        if has_corrosion:
            causes.append(
                f"Электрохимическая коррозия защитного слоя металла узла (наработка: {component_age}) "
                f"под воздействием агрессивной производственной влаги и конденсата с деградацией лакокрасочного покрытия"
            )
        probable_cause = ". ".join(causes) + "."

        # Формирование пошаговой рекомендации
        recs = [
            f"1. Локализация и режим: Ограничить эксплуатационную нагрузку на агрегат '{equipment_name}' на 20-30% или переключить на резервную линию до завершения ремонтных процедур.",
            "2. Неразрушающий контроль: Выполнить ультразвуковой контроль (УЗК) сварного соединения и ультразвуковую толщинометрию стенок в зоне дефектов по ГОСТ 14782-86.",
            "3. Подготовка поверхности: Произвести механическую зачистку зоны дефектов проволочными щетками и пескоструйной обработкой до степени чистоты Sa 2.5.",
        ]

        if has_welding:
            recs.append(
                "4. Сварочно-восстановительные работы: Выполнить выборку дефектного участка шва воздушно-дуговой строжкой, "
                "произвести повторную заварку с предварительным подогревом до 150°C электродами повышенной вязкости."
            )
        if has_corrosion:
            recs.append(
                "5. Антикоррозийная пассивация: Нанести эпоксидный цинконаполненный грунт (толщина сухого слоя не менее 80 мкм) "
                "с финишным полиуретановым защитным слоем стойким к промышленным средам."
            )

        recs.append(f"6. Приемка и допуск: Провести повторную фотофиксацию, внести акт в систему ТОиР и опломбировать узел.")

        return LLMRecommendation(
            criticality=criticality,
            probable_cause=probable_cause,
            recommendations=recs
        )

    def analyze(
        self,
        equipment_name: str,
        component_age: str,
        last_maintenance_date: str,
        defects: List[DefectItem]
    ) -> LLMRecommendation:
        """
        Основной входной метод анализа:
        Принимает имя оборудования, возраст узла, дату последнего ТО и список найденных дефектов с уверенностью.
        Возвращает строгую схему LLMRecommendation.
        """
        defects_payload = self._format_defects_input(defects)

        user_prompt = json.dumps({
            "equipment_name": equipment_name,
            "component_age": component_age,
            "last_maintenance_date": last_maintenance_date,
            "defects_found": defects_payload,
            "defects_count": len(defects)
        }, ensure_ascii=False, indent=2)

        # 1. Попытка вызова внешней LLM
        llm_result = self._call_gemini_api(user_prompt)
        if llm_result is not None:
            return llm_result

        # 2. Надежный экспертный fallback
        return self._generate_rule_based_expert(
            equipment_name=equipment_name,
            component_age=component_age,
            last_maintenance_date=last_maintenance_date,
            defects=defects
        )

llm_expert_service = TOIRExpertService()
