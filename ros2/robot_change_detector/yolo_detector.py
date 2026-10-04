from ultralytics import YOLO


class YoloDetector:
    """
    Raspberry Pi 4 / 4GB:
    - YOLO11n
    - 변화 확정 때만 실행
    - imgsz=320
    - CPU
    - 첫 사용 때 모델 로드 후 재사용
    """

    def __init__(
        self,
        model_path="yolo11n.pt",
        confidence=0.40,
        image_size=320,
        max_det=10,
    ):
        self.model_path = model_path
        self.confidence = float(confidence)
        self.image_size = int(image_size)
        self.max_det = int(max_det)
        self.model = None

    def _ensure_model(self):
        if self.model is None:
            self.model = YOLO(
                self.model_path
            )

    def detect(self, image_path):
        self._ensure_model()

        results = self.model.predict(
            source=image_path,
            conf=self.confidence,
            imgsz=self.image_size,
            device="cpu",
            max_det=self.max_det,
            verbose=False,
        )

        detected = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(
                    box.cls[0].item()
                )
                confidence = float(
                    box.conf[0].item()
                )

                bbox = [
                    round(float(value), 1)
                    for value in box.xyxy[0].tolist()
                ]

                detected.append(
                    {
                        "label": str(
                            result.names[class_id]
                        ),
                        "confidence": round(
                            confidence,
                            4,
                        ),
                        "bbox": bbox,
                    }
                )

        return detected
