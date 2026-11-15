"""
Эмулятор сервера ввода/вывода (OPC UA / Modbus TCP) и телеметрии датчиков.
Читает 500 строк почасового датасета механической вибрации и температуры,
рассчитывает уставки по ГОСТ/ISO 10816 и эмулирует потоковые измерения
с поддержкой редких аномалий для демонстрации ТОиР.
"""

from __future__ import annotations

import math
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import openpyxl
except ImportError:
    openpyxl = None  # type: ignore


# Пороги по ГОСТ / ISO 10816 и техническому регламенту ТОиР
THRESHOLDS = {
    "v_rms": {"warn": 2.8, "alarm": 4.5, "unit": "мм/с", "name": "СКЗ виброскорости"},
    "amp_1x": {"warn": 2.8, "alarm": 4.5, "unit": "мм/с", "name": "Амплитуда 1x (дисбаланс РК)"},
    "amp_2x": {"warn": 1.8, "alarm": 3.0, "unit": "мм/с", "name": "Амплитуда 2x (расцентровка муфты)"},
    "hf_noise": {"warn": 2.5, "alarm": 3.5, "unit": "g", "name": "ВЧ шум (подшипник/кавитация)"},
    "bearing_temp": {"warn": 75.0, "alarm": 90.0, "unit": "°C", "name": "Температура подшипника"},
    "motor_temp": {"warn": 90.0, "alarm": 110.0, "unit": "°C", "name": "Температура обмоток ЭД"},
}

MODBUS_MAP = {
    "shaft_speed_rpm": {"register": 40001, "scale": 1, "type": "uint16"},
    "vibration_overall_rms": {"register": 40002, "scale": 100, "type": "uint16"},
    "vibration_amplitude_1x": {"register": 40003, "scale": 100, "type": "uint16"},
    "vibration_amplitude_2x": {"register": 40004, "scale": 100, "type": "uint16"},
    "vibration_hf_noise": {"register": 40005, "scale": 100, "type": "uint16"},
    "pump_bearing_temperature": {"register": 40006, "scale": 10, "type": "uint16"},
    "motor_winding_temperature": {"register": 40007, "scale": 10, "type": "uint16"},
    "diagnosis_code": {"register": 40008, "scale": 1, "type": "uint16"},
}


@dataclass
class TelemetryReading:
    timestamp: str
    rpm: float
    v_rms: float
    amp_1x: float
    amp_2x: float
    hf_noise: float
    bearing_temp: float
    motor_temp: float
    diagnosis: str
    severity: str  # "normal" | "warning" | "alarm"
    anomaly: bool


class TelemetryEmulatorService:
    def __init__(self) -> None:
        self._dataset: List[TelemetryReading] = []
        self._current_index = 0
        self._last_tick = time.time()
        self._load_dataset()

    def _load_dataset(self) -> None:
        """Ищет и парсит xlsx датасет на 500 строк."""
        candidate_paths = [
            Path("database/data/vibration_values.xlsx"),
            Path("c:/Users/ardor/merge_work/database/data/vibration_values.xlsx"),
            Path("c:/Users/ardor/Desktop/Новая папка/БД значений (вибрация).xlsx"),
        ]
        chosen = None
        for p in candidate_paths:
            if p.exists():
                chosen = p
                break

        if not chosen or openpyxl is None:
            self._generate_synthetic_fallback()
            return

        try:
            wb = openpyxl.load_workbook(str(chosen), data_only=True)
            sheet = wb.active
            rows = []
            for r in range(2, sheet.max_row + 1):
                dt_val = sheet.cell(row=r, column=1).value
                rpm_val = sheet.cell(row=r, column=2).value
                rms_val = sheet.cell(row=r, column=3).value
                a1_val = sheet.cell(row=r, column=4).value
                a2_val = sheet.cell(row=r, column=5).value
                hf_val = sheet.cell(row=r, column=6).value
                diag_val = sheet.cell(row=r, column=7).value

                if rms_val is None:
                    continue

                rpm = float(rpm_val or 2950.0)
                v_rms = float(rms_val or 1.0)
                amp_1x = float(a1_val or 0.8)
                amp_2x = float(a2_val or 0.3)
                hf_noise = float(hf_val or 0.1)
                diag = str(diag_val or "Норма")

                # Расчёт температур под диагноз
                is_alarm = "тревога" in diag.lower()
                is_warn = "пред" in diag.lower() or "warning" in diag.lower()

                if "подшипник" in diag.lower() or "шум" in diag.lower():
                    b_temp = round(random.uniform(76.0, 88.0) if is_warn else random.uniform(89.0, 96.0), 1)
                elif is_alarm:
                    b_temp = round(random.uniform(72.0, 82.0), 1)
                else:
                    b_temp = round(random.uniform(54.0, 68.0), 1)

                if "расцентровк" in diag.lower() or "дисбаланс" in diag.lower():
                    m_temp = round(random.uniform(86.0, 96.0) if is_warn else random.uniform(97.0, 108.0), 1)
                elif is_alarm:
                    m_temp = round(random.uniform(82.0, 91.0), 1)
                else:
                    m_temp = round(random.uniform(66.0, 78.0), 1)

                if is_alarm:
                    sev = "alarm"
                elif is_warn:
                    sev = "warning"
                else:
                    sev = "normal"

                rows.append(
                    TelemetryReading(
                        timestamp=str(dt_val or datetime.now(timezone.utc).isoformat()),
                        rpm=rpm,
                        v_rms=v_rms,
                        amp_1x=amp_1x,
                        amp_2x=amp_2x,
                        hf_noise=hf_noise,
                        bearing_temp=b_temp,
                        motor_temp=m_temp,
                        diagnosis=diag,
                        severity=sev,
                        anomaly=sev != "normal",
                    )
                )

            if rows:
                self._dataset = rows
            else:
                self._generate_synthetic_fallback()
        except Exception:
            self._generate_synthetic_fallback()

    def _generate_synthetic_fallback(self) -> None:
        """Синтетический резервный генератор 50 записей при недоступности файла."""
        self._dataset = []
        base_time = datetime.now(timezone.utc)
        for i in range(50):
            has_anomaly = i in (7, 18, 33, 42)
            if has_anomaly:
                diag = random.choice([
                    "Пред: Рост дисбаланса",
                    "Тревога: Расцентровка",
                    "Пред: Износ/Шум",
                    "Тревога: Дефект подшипника",
                ])
                sev = "alarm" if "тревога" in diag.lower() else "warning"
                v_rms = round(random.uniform(3.0, 5.2), 2)
                a1 = round(random.uniform(2.9, 4.8), 2)
                a2 = round(random.uniform(1.9, 3.4), 2)
                hf = round(random.uniform(2.6, 4.0), 2)
                bt = round(random.uniform(78.0, 92.0), 1)
                mt = round(random.uniform(88.0, 102.0), 1)
            else:
                diag = "Норма"
                sev = "normal"
                v_rms = round(random.uniform(0.9, 1.4), 2)
                a1 = round(random.uniform(0.7, 1.1), 2)
                a2 = round(random.uniform(0.2, 0.5), 2)
                hf = round(random.uniform(0.05, 0.3), 2)
                bt = round(random.uniform(55.0, 67.0), 1)
                mt = round(random.uniform(65.0, 76.0), 1)

            self._dataset.append(
                TelemetryReading(
                    timestamp=base_time.isoformat(),
                    rpm=round(random.uniform(2945.0, 2965.0), 1),
                    v_rms=v_rms,
                    amp_1x=a1,
                    amp_2x=a2,
                    hf_noise=hf,
                    bearing_temp=bt,
                    motor_temp=mt,
                    diagnosis=diag,
                    severity=sev,
                    anomaly=has_anomaly,
                )
            )

    def get_current_reading(
        self,
        equipment_id: str = "PUMP-402",
        force_anomaly: bool = False,
    ) -> Dict[str, Any]:
        """Возвращает текущий срез телеметрии датчиков с метаданными протокола ввода/вывода."""
        if not self._dataset:
            self._generate_synthetic_fallback()

        # Если принудительно запрошена аномалия, берем случайную аномальную запись
        if force_anomaly:
            anomalies = [r for r in self._dataset if r.anomaly]
            reading = random.choice(anomalies) if anomalies else self._dataset[0]
        else:
            # Смещаем текущий индекс с течением времени (каждые 4 секунды шаг по датасету)
            elapsed = time.time() - self._last_tick
            steps = int(elapsed // 4)
            if steps > 0:
                self._current_index = (self._current_index + steps) % len(self._dataset)
                self._last_tick = time.time()
            reading = self._dataset[self._current_index]

        # Добавим микро-джиттер для живости, если значение штатное
        jitter = random.uniform(-0.02, 0.02)
        v_rms_live = round(max(0.1, reading.v_rms + jitter), 2)
        amp_1x_live = round(max(0.05, reading.amp_1x + jitter), 2)
        amp_2x_live = round(max(0.02, reading.amp_2x + (jitter * 0.5)), 2)
        hf_live = round(max(0.01, reading.hf_noise + (jitter * 0.3)), 2)
        rpm_live = round(reading.rpm + random.uniform(-2.0, 2.0), 1)
        b_temp_live = round(reading.bearing_temp + random.uniform(-0.3, 0.3), 1)
        m_temp_live = round(reading.motor_temp + random.uniform(-0.4, 0.4), 1)

        now_iso = datetime.now(timezone.utc).isoformat()

        # Формируем структуру каналов
        channels = [
            {
                "id": "v_rms",
                "name": "СКЗ виброскорости",
                "modality": "vibration",
                "value": v_rms_live,
                "unit": "мм/с",
                "warning_threshold": THRESHOLDS["v_rms"]["warn"],
                "alarm_threshold": THRESHOLDS["v_rms"]["alarm"],
                "status": "alarm" if v_rms_live >= 4.5 else "warning" if v_rms_live >= 2.8 else "normal",
                "standard": "ГОСТ ISO 10816-3",
                "location": "Корпус подшипника насоса",
            },
            {
                "id": "amp_1x",
                "name": "Амплитуда 1x (оборотная)",
                "modality": "vibration",
                "value": amp_1x_live,
                "unit": "мм/с",
                "warning_threshold": THRESHOLDS["amp_1x"]["warn"],
                "alarm_threshold": THRESHOLDS["amp_1x"]["alarm"],
                "status": "alarm" if amp_1x_live >= 4.5 else "warning" if amp_1x_live >= 2.8 else "normal",
                "standard": "Индикатор дисбаланса РК",
                "location": "Вал насоса",
            },
            {
                "id": "amp_2x",
                "name": "Амплитуда 2x (удвоенная)",
                "modality": "vibration",
                "value": amp_2x_live,
                "unit": "мм/с",
                "warning_threshold": THRESHOLDS["amp_2x"]["warn"],
                "alarm_threshold": THRESHOLDS["amp_2x"]["alarm"],
                "status": "alarm" if amp_2x_live >= 3.0 else "warning" if amp_2x_live >= 1.8 else "normal",
                "standard": "Индикатор расцентровки муфты",
                "location": "Муфтовое соединение",
            },
            {
                "id": "hf_noise",
                "name": "ВЧ шум (ускорение)",
                "modality": "vibration",
                "value": hf_live,
                "unit": "g",
                "warning_threshold": THRESHOLDS["hf_noise"]["warn"],
                "alarm_threshold": THRESHOLDS["hf_noise"]["alarm"],
                "status": "alarm" if hf_live >= 3.5 else "warning" if hf_live >= 2.5 else "normal",
                "standard": "Маркер кавитации и подшипников",
                "location": "Гидравлическая часть",
            },
            {
                "id": "bearing_temp",
                "name": "Температура подшипника",
                "modality": "temperature",
                "value": b_temp_live,
                "unit": "°C",
                "warning_threshold": THRESHOLDS["bearing_temp"]["warn"],
                "alarm_threshold": THRESHOLDS["bearing_temp"]["alarm"],
                "status": "alarm" if b_temp_live >= 90.0 else "warning" if b_temp_live >= 75.0 else "normal",
                "standard": "Техрегламент ТОиР",
                "location": "Опорно-упорный подшипник",
            },
            {
                "id": "motor_temp",
                "name": "Температура статора ЭД",
                "modality": "temperature",
                "value": m_temp_live,
                "unit": "°C",
                "warning_threshold": THRESHOLDS["motor_temp"]["warn"],
                "alarm_threshold": THRESHOLDS["motor_temp"]["alarm"],
                "status": "alarm" if m_temp_live >= 110.0 else "warning" if m_temp_live >= 90.0 else "normal",
                "standard": "Класс изоляции F/H",
                "location": "Обмотка статора",
            },
            {
                "id": "shaft_speed_rpm",
                "name": "Частота вращения",
                "modality": "speed",
                "value": rpm_live,
                "unit": "об/мин",
                "warning_threshold": None,
                "alarm_threshold": None,
                "status": "normal",
                "standard": "Номинал 3000 об/мин",
                "location": "Вал электродвигателя",
            },
        ]

        # Вычисляем общий статус по максимуму критичности
        has_alarm = any(c["status"] == "alarm" for c in channels)
        has_warn = any(c["status"] == "warning" for c in channels)
        overall_severity = "alarm" if has_alarm else "warning" if has_warn else "normal"

        diag_text = reading.diagnosis
        if overall_severity == "normal" and diag_text != "Норма":
            diag_text = "Норма"
        elif overall_severity == "alarm" and "тревога" not in diag_text.lower():
            diag_text = f"Тревога: превышение порогов ({diag_text})"

        return {
            "equipment_id": equipment_id,
            "timestamp": now_iso,
            "dataset_time": reading.timestamp,
            "overall_status": overall_severity,
            "diagnosis": diag_text,
            "rpm": rpm_live,
            "channels": channels,
            "integration": {
                "source": "Сервер ввода/вывода (SCADA Gateway)",
                "protocols": ["OPC UA", "Modbus TCP"],
                "opc_endpoint": "opc.tcp://10.161.120.19:4840/promscan/sensors",
                "modbus_endpoint": "modbus-tcp://10.161.120.19:502 (Unit ID: 1)",
                "status": "online (эмуляция по реальному архиву)",
                "db_archive": "TimescaleDB / PostgreSQL (таблица promscan.measurements)",
                "dataset_rows_total": len(self._dataset),
                "current_row_index": self._current_index,
            },
        }

    def get_history(self, equipment_id: str = "PUMP-402", limit: int = 24) -> List[Dict[str, Any]]:
        """Возвращает историю измерений для графиков тренда."""
        if not self._dataset:
            self._generate_synthetic_fallback()

        total = len(self._dataset)
        start = max(0, self._current_index - limit + 1)
        slice_items = self._dataset[start : self._current_index + 1]
        if len(slice_items) < limit and total >= limit:
            slice_items = self._dataset[total - (limit - len(slice_items)) :] + slice_items

        result = []
        for it in slice_items:
            result.append(
                {
                    "timestamp": it.timestamp,
                    "v_rms": it.v_rms,
                    "amp_1x": it.amp_1x,
                    "amp_2x": it.amp_2x,
                    "hf_noise": it.hf_noise,
                    "bearing_temp": it.bearing_temp,
                    "motor_temp": it.motor_temp,
                    "rpm": it.rpm,
                    "diagnosis": it.diagnosis,
                    "severity": it.severity,
                }
            )
        return result


telemetry_service = TelemetryEmulatorService()
