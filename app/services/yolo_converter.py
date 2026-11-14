from typing import List, Dict, Any, Optional
import numpy as np
from app.schemas.defect import DefectItem, DefectCategory

class YOLOOutputConverter:
    """
    Конвертер результатов инференса моделей YOLO (Ultralytics).
    Преобразует маски сегментации в массивы точек [x, y] нормализованных координат,
    а боксы — в формат [x_min, y_min, x_max, y_max] (в пикселях и нормализованные).
    """

    @staticmethod
    def _map_category(label: str, source_model: str) -> DefectCategory:
        lbl = label.lower()
        if "rust" in lbl or "corros" in lbl:
            return DefectCategory.CORROSION
        if "crack" in lbl:
            return DefectCategory.CRACK
        if "weld" in lbl or "defect" in lbl:
            return DefectCategory.WELDING_DEFECT
        if "corrosion" in source_model.lower():
            return DefectCategory.CORROSION
        return DefectCategory.WELDING_DEFECT

    @classmethod
    def convert_results(
        cls, 
        results: Any, 
        source_model: str, 
        conf_threshold: float = 0.25,
        start_id: int = 1
    ) -> List[DefectItem]:
        """
        Преобразует объект Results из Ultralytics YOLO в список схем DefectItem.
        """
        defects: List[DefectItem] = []
        if not results:
            return defects

        # Results может быть списком или одиночным объектом
        res = results[0] if isinstance(results, list) else results

        boxes = getattr(res, "boxes", None)
        masks = getattr(res, "masks", None)
        names = getattr(res, "names", {})

        if boxes is None or len(boxes) == 0:
            return defects

        orig_shape = getattr(res, "orig_shape", (1, 1)) # (height, width)
        h, w = orig_shape[0], orig_shape[1]

        # Извлекаем данные масок сегментации
        # xyn возвращает список массивов numpy размера (N, 2) в нормализованных координатах [0, 1]
        normalized_polygons: List[Optional[List[List[float]]]] = []
        if masks is not None and hasattr(masks, "xyn") and masks.xyn is not None:
            for poly in masks.xyn:
                if poly is not None and len(poly) > 0:
                    pts = [[round(float(p[0]), 4), round(float(p[1]), 4)] for p in poly]
                    normalized_polygons.append(pts)
                else:
                    normalized_polygons.append(None)
        elif masks is not None and hasattr(masks, "xy") and masks.xy is not None:
            # Fallback к пиксельным координатам, деленным на w и h
            for poly in masks.xy:
                if poly is not None and len(poly) > 0 and w > 0 and h > 0:
                    pts = [[round(float(p[0]) / w, 4), round(float(p[1]) / h, 4)] for p in poly]
                    normalized_polygons.append(pts)
                else:
                    normalized_polygons.append(None)

        current_id = start_id
        for idx, box in enumerate(boxes):
            conf = float(box.conf[0])
            if conf < conf_threshold:
                continue

            cls_id = int(box.cls[0])
            label = str(names.get(cls_id, f"class_{cls_id}"))

            # Пропускаем класс 'Good Weld' - это не дефект
            if label.strip().lower() == "good weld":
                continue

            # Координаты бокса в пикселях: [x_min, y_min, x_max, y_max]
            xyxy = box.xyxy[0].tolist()
            bbox_px = [
                round(float(xyxy[0]), 2),
                round(float(xyxy[1]), 2),
                round(float(xyxy[2]), 2),
                round(float(xyxy[3]), 2),
            ]

            # Координаты бокса, нормализованные [0, 1]: [x_min, y_min, x_max, y_max]
            if hasattr(box, "xyxyn") and box.xyxyn is not None:
                xyxyn = box.xyxyn[0].tolist()
                bbox_norm = [
                    round(float(xyxyn[0]), 4),
                    round(float(xyxyn[1]), 4),
                    round(float(xyxyn[2]), 4),
                    round(float(xyxyn[3]), 4),
                ]
            else:
                bbox_norm = [
                    round(float(bbox_px[0] / max(w, 1)), 4),
                    round(float(bbox_px[1] / max(h, 1)), 4),
                    round(float(bbox_px[2] / max(w, 1)), 4),
                    round(float(bbox_px[3] / max(h, 1)), 4),
                ]

            # Полигон маски сегментации для данного бокса
            polygon = None
            if idx < len(normalized_polygons):
                polygon = normalized_polygons[idx]

            category = cls._map_category(label, source_model)

            defect_item = DefectItem(
                id=f"defect_{current_id}",
                label=label,
                category=category,
                confidence=round(conf, 4),
                bbox=bbox_px,
                bbox_normalized=bbox_norm,
                polygon=polygon,
                model_source=source_model,
            )
            defects.append(defect_item)
            current_id += 1

        return defects
