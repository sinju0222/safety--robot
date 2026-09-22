from ultralytics import YOLO


class YoloDetector:

    def __init__(
        self,
        model_path="yolo11n.pt",
        confidence=0.40
    ):

        self.model = YOLO(
            model_path
        )

        self.confidence = confidence

    def detect(self, image_path):

        results = self.model(
            image_path,
            conf=self.confidence,
            verbose=False
        )

        detected_objects = []

        for result in results:

            for box in result.boxes:

                class_id = int(
                    box.cls[0]
                )

                confidence = float(
                    box.conf[0]
                )

                label = self.model.names[
                    class_id
                ]

                bbox = (
                    box.xyxy[0]
                    .cpu()
                    .tolist()
                )

                detected_objects.append(
                    {
                        "label": label,

                        "confidence": round(
                            confidence,
                            3
                        ),

                        "bbox": [
                            round(v, 1)
                            for v in bbox
                        ]
                    }
                )

        return detected_objects