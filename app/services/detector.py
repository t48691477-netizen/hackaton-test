import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from PIL import Image

from app.config import settings
from app.schemas.defect import DefectItem, DefectCategory
from app.services.model_loader import model_loader
from app.services.yolo_converter import YOLOOutputConverter

class DefectDetectorService:
    def __init__(self):
        self.converter = YOLOOutputConverter()

    def detect(self, image_path: Path) -> Tuple[List[DefectItem], Optional[Path]]:
        """
        Запускает ансамбль из двух моделей:
        1. Сегментация коррозии (Decizez/yolov-corrosion-detection)
        2. Детекция дефектов сварных швов (avinashhm/welding-defect-yolov8-full-training)
        
        Возвращает:
        - Список объединенных дефектов (DefectItem)
        - Путь к размеченному изображению с визуализацией
        """
        all_defects: List[DefectItem] = []
        corrosion_model = model_loader.load_corrosion_model()
        welding_model = model_loader.load_welding_model()

        # Загружаем изображение
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Не удалось прочитать изображение по пути {image_path}")

        h, w = img_bgr.shape[:2]

        # 1. Инференс модели сегментации коррозии
        if corrosion_model is not None:
            try:
                res_corrosion = corrosion_model.predict(
                    source=str(image_path),
                    conf=settings.CONF_THRESHOLD_CORROSION,
                    verbose=False
                )
                corrosion_defects = self.converter.convert_results(
                    results=res_corrosion,
                    source_model=settings.CORROSION_MODEL_REPO,
                    conf_threshold=settings.CONF_THRESHOLD_CORROSION,
                    start_id=len(all_defects) + 1
                )
                all_defects.extend(corrosion_defects)
            except Exception as e:
                print(f"[Detector] Ошибка при инференсе модели коррозии: {e}")

        # 2. Инференс модели сварных швов
        if welding_model is not None:
            try:
                res_welding = welding_model.predict(
                    source=str(image_path),
                    conf=settings.CONF_THRESHOLD_WELDING,
                    verbose=False
                )
                welding_defects = self.converter.convert_results(
                    results=res_welding,
                    source_model=settings.WELDING_MODEL_REPO,
                    conf_threshold=settings.CONF_THRESHOLD_WELDING,
                    start_id=len(all_defects) + 1
                )
                all_defects.extend(welding_defects)
            except Exception as e:
                print(f"[Detector] Ошибка при инференсе модели сварки: {e}")

        # 3. Генерация аннотированного изображения
        annotated_path = self._draw_annotations(img_bgr, all_defects, image_path)

        return all_defects, annotated_path

    def _draw_annotations(self, img_bgr: np.ndarray, defects: List[DefectItem], orig_path: Path) -> Path:
        vis = img_bgr.copy()
        h, w = vis.shape[:2]

        for defect in defects:
            # Отрисовка полигона маски (если есть)
            if defect.polygon and len(defect.polygon) > 2:
                pts_px = np.array(
                    [[int(p[0] * w), int(p[1] * h)] for p in defect.polygon],
                    dtype=np.int32
                )
                overlay = vis.copy()
                color = (0, 0, 255) if defect.category == DefectCategory.CORROSION else (255, 128, 0)
                cv2.fillPoly(overlay, [pts_px], color)
                cv2.addWeighted(overlay, 0.4, vis, 0.6, 0, vis)
                cv2.polylines(vis, [pts_px], isClosed=True, color=color, thickness=2)

            # Отрисовка бокса
            bx = [int(v) for v in defect.bbox]
            cv2.rectangle(vis, (bx[0], bx[1]), (bx[2], bx[3]), (0, 255, 0), 2)

            # Подпись
            text = f"{defect.label}: {defect.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(vis, (bx[0], max(0, bx[1] - 20)), (bx[0] + tw + 6, max(0, bx[1])), (0, 255, 0), -1)
            cv2.putText(vis, text, (bx[0] + 3, max(14, bx[1] - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

        annotated_path = orig_path.parent / f"{orig_path.stem}_annotated{orig_path.suffix}"
        cv2.imwrite(str(annotated_path), vis)
        return annotated_path

defect_detector = DefectDetectorService()
