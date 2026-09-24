import { useEffect, useState } from "react";
import "./App.css";

import WorkplaceList from "./pages/WorkplaceList";
import AddWorkplace from "./pages/AddWorkplace";
import WorkplaceMain from "./pages/WorkplaceMain";
import SafetyPolicy from "./pages/SafetyPolicy";
import PatrolDetail from "./pages/PatrolDetail";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [page, setPage] = useState("list");

  const [workplaces, setWorkplaces] =
    useState([]);

  const [
    selectedWorkplaceId,
    setSelectedWorkplaceId,
  ] = useState(null);

  const [
    selectedPatrolId,
    setSelectedPatrolId,
  ] = useState(null);

  const [loading, setLoading] =
    useState(true);

  const selectedWorkplace =
    workplaces.find(
      (workplace) =>
        workplace.id === selectedWorkplaceId
    );

  const selectedPatrol =
    selectedWorkplace?.patrols?.find(
      (patrol) =>
        patrol.id === selectedPatrolId
    );

  /*
   * ===============================
   * 작업장 목록 조회
   * ===============================
   */

  const loadWorkplaces = async () => {
    try {
      setLoading(true);

      const response = await fetch(
        `${API_URL}/workplaces`
      );

      if (!response.ok) {
        throw new Error(
          "작업장 목록 조회 실패"
        );
      }

      const data =
        await response.json();

      setWorkplaces(data);
    } catch (error) {
      console.error(error);

      alert(
        "Backend 서버에 연결할 수 없습니다."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadWorkplaces();
  }, []);

  /*
   * ===============================
   * 작업장 생성
   * ===============================
   */

  const addWorkplace = async (name) => {
    try {
      const response = await fetch(
        `${API_URL}/workplaces`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            name,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "작업장 생성 실패"
        );
      }

      const newWorkplace =
        await response.json();

      setWorkplaces((prev) => [
        ...prev,
        newWorkplace,
      ]);

      setSelectedWorkplaceId(
        newWorkplace.id
      );

      setPage("main");
    } catch (error) {
      console.error(error);

      alert(
        "작업장을 생성할 수 없습니다."
      );
    }
  };

  /*
   * ===============================
   * 작업장 선택
   * ===============================
   */

  const openWorkplace = (
    workplace
  ) => {
    setSelectedWorkplaceId(
      workplace.id
    );

    setPage("main");
  };

  /*
   * ===============================
   * 로컬 작업장 갱신
   * ===============================
   */

  const updateLocalWorkplace = (
    workplaceId,
    updater
  ) => {
    setWorkplaces((prev) =>
      prev.map((workplace) => {
        if (
          workplace.id !== workplaceId
        ) {
          return workplace;
        }

        if (
          typeof updater === "function"
        ) {
          return updater(workplace);
        }

        return {
          ...workplace,
          ...updater,
        };
      })
    );
  };

  /*
   * ===============================
   * 지도 제작 시작
   *
   * React
   * ↓
   * FastAPI
   * ↓
   * Mock Mapping
   * ===============================
   */

  const startMapping = async () => {
    if (!selectedWorkplaceId) {
      return;
    }

    try {
      /*
       * Backend에 Mapping 시작 요청
       */

      const startResponse =
        await fetch(
          `${API_URL}/workplaces/${selectedWorkplaceId}/map/start`,
          {
            method: "POST",
          }
        );

      if (!startResponse.ok) {
        throw new Error(
          "지도 제작 시작 실패"
        );
      }

      const startData =
        await startResponse.json();

      /*
       * React 화면을
       * creating 상태로 변경
       */

      updateLocalWorkplace(
        selectedWorkplaceId,
        (workplace) => ({
          ...workplace,

          map: startData.map,
        })
      );

      /*
       * =================================
       * MOCK
       *
       * 실제 하드웨어 연결 후에는
       * 이 부분이 ROS2 SLAM 완료 이벤트로
       * 교체됩니다.
       * =================================
       */

      await new Promise((resolve) =>
        setTimeout(resolve, 2500)
      );

      /*
       * Mock Mapping 완료
       */

      const completeResponse =
        await fetch(
          `${API_URL}/workplaces/${selectedWorkplaceId}/map/complete`,
          {
            method: "POST",
          }
        );

      if (!completeResponse.ok) {
        throw new Error(
          "지도 제작 완료 처리 실패"
        );
      }

      const completeData =
        await completeResponse.json();

      /*
       * Backend 결과를 React에 반영
       */

      updateLocalWorkplace(
        selectedWorkplaceId,
        (workplace) => ({
          ...workplace,

          map: completeData.map,
        })
      );
    } catch (error) {
      console.error(error);

      alert(
        "지도 제작 중 오류가 발생했습니다."
      );
    }
  };

  /*
   * ===============================
   * 안전정책 저장
   * ===============================
   */

  const savePolicies = async (
    newPolicies
  ) => {
    if (!selectedWorkplaceId) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/workplaces/${selectedWorkplaceId}/policies`,
        {
          method: "PUT",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify(
            newPolicies
          ),
        }
      );

      if (!response.ok) {
        throw new Error(
          "안전정책 저장 실패"
        );
      }

      const data =
        await response.json();

      /*
       * Backend에서 저장된 정책으로
       * React 상태 갱신
       */

      updateLocalWorkplace(
        selectedWorkplaceId,
        (workplace) => ({
          ...workplace,

          policies: data.policies,
        })
      );

      setPage("main");
    } catch (error) {
      console.error(error);

      alert(
        "안전정책을 저장할 수 없습니다."
      );
    }
  };

  /*
   * ===============================
   * 순찰 저장
   *
   * 아직 Mock / React 로컬
   * ===============================
   */

  const savePatrol = (patrol) => {
    if (!selectedWorkplaceId) {
      return;
    }

    const today =
      new Date().toLocaleDateString(
        "ko-KR"
      );

    updateLocalWorkplace(
      selectedWorkplaceId,
      (workplace) => ({
        ...workplace,

        lastPatrol: today,

        patrols: [
          patrol,
          ...(workplace.patrols || []),
        ],
      })
    );
  };

  /*
   * ===============================
   * 순찰 상세보기
   * ===============================
   */

  const openPatrolDetail = (
    patrolId
  ) => {
    setSelectedPatrolId(
      patrolId
    );

    setPage("patrolDetail");
  };

  /*
   * ===============================
   * Backend 초기 연결 중
   * ===============================
   */

  if (loading) {
    return (
      <div className="app">
        <div className="screen">
          <div className="loading-screen">
            Backend 연결 중...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">

      {/* 작업장 목록 */}

      {page === "list" && (
        <WorkplaceList
          workplaces={workplaces}
          onAdd={() =>
            setPage("add")
          }
          onSelect={
            openWorkplace
          }
        />
      )}

      {/* 작업장 추가 */}

      {page === "add" && (
        <AddWorkplace
          onBack={() =>
            setPage("list")
          }
          onCreate={
            addWorkplace
          }
        />
      )}

      {/* 작업장 메인 */}

      {page === "main" &&
        selectedWorkplace && (
          <WorkplaceMain
            workplace={
              selectedWorkplace
            }
            onBack={() =>
              setPage("list")
            }
            onOpenPolicy={() =>
              setPage("policy")
            }

            /*
             * 기존 onMapStatusChange 대신
             * Backend Mapping 함수 전달
             */
            onStartMapping={
              startMapping
            }

            onSavePatrol={
              savePatrol
            }
            onOpenPatrol={
              openPatrolDetail
            }
          />
        )}

      {/* 안전정책 */}

      {page === "policy" &&
        selectedWorkplace && (
          <SafetyPolicy
            policies={
              selectedWorkplace.policies
            }
            onBack={() =>
              setPage("main")
            }
            onSave={
              savePolicies
            }
          />
        )}

      {/* 순찰 상세 */}

      {page ===
        "patrolDetail" &&
        selectedPatrol && (
          <PatrolDetail
            patrol={
              selectedPatrol
            }
            onBack={() =>
              setPage("main")
            }
          />
        )}

    </div>
  );
}

export default App;
