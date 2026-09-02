import { useEffect, useState } from "react";

function StatusCard() {
  const [backendStatus, setBackendStatus] = useState("확인 중");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((response) => response.json())
      .then((data) => {
        if (data.status === "ok") {
          setBackendStatus("정상");
        } else {
          setBackendStatus("오류");
        }
      })
      .catch(() => {
        setBackendStatus("연결 실패");
      });
  }, []);

  return (
    <section>
      <h2>System Status</h2>
      <p>Backend: {backendStatus}</p>
      <p>Risk Level: NORMAL</p>
      <p>Active Policies: 0</p>
    </section>
  );
}

export default StatusCard;