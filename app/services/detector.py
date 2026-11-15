import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional

from app.config import settings
from app.schemas.defect import DefectItem, DefectCategory
from app.services.model_loader import model_loader
from app.services.yolo_converter import YOLOOutputConverter

class DefectDetectorService:
    def __init__(self):
        self.converter = YOLOOutputConverter()

    def detect(self, image_path: Path) -> Tuple[List[DefectItem], Optional[Path]]:
        """
        Запускает единую ONNX-модель детекции дефектов (weights/defects_yolo.onnx, CPU).

        Возвращает:
        - Список обнаруженных дефектов (DefectItem)
        - Путь к размеченному изображению с визуализацией
        """
        model = model_loader.load_unified_model()

        # Загружаем изображение
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise ValueError(f"Не удалось прочитать изображение по пути {image_path}")

        all_defects: List[DefectItem] = []
        if model is not None:
            try:
                results = model.predict(
                    source=str(image_path),
                    conf=settings.CONF_THRESHOLD,
                    device="cpu",
                    verbose=False
                )
                all_defects = self.converter.convert_results(
                    results=results,
                    source_model=settings.UNIFIED_LOCAL_PATH.stem,
                    conf_threshold=settings.CONF_THRESHOLD,
                    start_id=1
                )
            except Exception as e:
                print(f"[Detector] Ошибка при инференсе единой модели: {e}")

        # Генерация аннотированного изображения
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
