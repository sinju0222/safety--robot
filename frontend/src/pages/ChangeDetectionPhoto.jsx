import {
  useEffect,
  useState,
} from "react";


const API_URL =
  "http://127.0.0.1:8000";


function ChangeDetectionPhoto() {

  const [
    event,
    setEvent,
  ] = useState(null);


  useEffect(() => {

    const loadEvent =
      async () => {

        try {

          const response =
            await fetch(
              `${API_URL}/api/robot-events/latest`
            );

          if (!response.ok) {
            return;
          }

          const data =
            await response.json();

          if (data.event) {
            setEvent(
              data.event
            );
          }

        } catch (error) {

          console.error(
            "변화 사진 로딩 실패:",
            error
          );

        }
      };


    loadEvent();


    const timer =
      setInterval(
        loadEvent,
        1000
      );


    return () => {

      clearInterval(
        timer
      );

    };

  }, []);


  if (!event) {

    return (

      <div
        className="change-photo-card"
      >

        <h4>
          변화 탐지 사진
        </h4>

        <p>
          아직 탐지된 변화가 없습니다.
        </p>

      </div>

    );

  }


  const objectName =
    event.objects &&
    event.objects.length > 0
      ? event.objects[0].label
      : "알 수 없음";


  const confidence =
    event.objects &&
    event.objects.length > 0
      ? Math.round(
          event.objects[0]
            .confidence
          * 100
        )
      : null;


  return (

    <div
      className="change-photo-card"
    >

      <h4>
        변화 탐지 사진
      </h4>


      {event.imageUrl && (

        <img
          src={
            `${API_URL}`
            + event.imageUrl
          }
          alt="변화 탐지"
          style={{
            width: "100%",
            borderRadius: "10px",
            marginTop: "10px",
          }}
        />

      )}


      <div
        style={{
          marginTop: "10px",
        }}
      >

        <strong>
          {event.change?.type}
        </strong>


        <div>
          객체:
          {" "}
          {objectName}

          {confidence !== null &&
            ` (${confidence}%)`
          }
        </div>


        <div>
          변화 위치:
          {" "}
          {event.change?.x},
          {" "}
          {event.change?.y}
        </div>


        <div>
          시간:
          {" "}
          {event.timestamp
            ? new Date(
                event.timestamp
              ).toLocaleString(
                "ko-KR"
              )
            : "-"
          }
        </div>

      </div>

    </div>

  );

}


export default ChangeDetectionPhoto;