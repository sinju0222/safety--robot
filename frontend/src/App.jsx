import { useEffect, useState } from "react";
import "./App.css";

import WorkplaceList from "./pages/WorkplaceList";
import AddWorkplace from "./pages/AddWorkplace";
import WorkplaceMain from "./pages/WorkplaceMain";
import SafetyPolicy from "./pages/SafetyPolicy";
import PatrolDetail from "./pages/PatrolDetail";
import MapObjectSetup from "./pages/MapObjectSetup";

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

    /*
     * 만약 초기 사물 설정 도중
     * 화면을 나갔다가 다시 들어온 경우
     * 설정 화면으로 복귀
     */

    if (
      workplace.map?.status ===
      "object_setup"
    ) {
      setPage("mapObjectSetup");
      return;
    }

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
   * empty
   * ↓
   * creating
   * ↓
   * Mock Scan
   * ↓
   * object_setup
   * ↓
   * MapObjectSetup
   * ===============================
   */

  const startMapping = async () => {
    if (!selectedWorkplaceId) {
      return;
    }

    try {
      /*
       * 1.
       * Backend Mapping 시작
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
       * 2.
       * React를 creating 상태로 변경
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
       * MOCK MAPPING
       *
       * 실제 시스템에서는
       * TurtleBot3 + SLAM이
       * 작업장을 스캔하는 시간
       *
       * 추후 ROS2 이벤트로 교체
       * =================================
       */

      await new Promise((resolve) =>
        setTimeout(resolve, 2500)
      );

      /*
       * 3.
       * 지도 스캔 완료
       *
       * 여기서 Backend가
       * Mock 탐지 객체를 생성
       */

      const scanResponse =
        await fetch(
          `${API_URL}/workplaces/${selectedWorkplaceId}/map/scan-complete`,
          {
            method: "POST",
          }
        );

      if (!scanResponse.ok) {
        const errorData =
          await scanResponse.json();

        throw new Error(
          errorData.detail ||
            "지도 스캔 완료 처리 실패"
        );
      }

      const scanData =
        await scanResponse.json();

      /*
       * 4.
       * 지도 + 탐지 객체
       * React 상태에 저장
       */

      updateLocalWorkplace(
        selectedWorkplaceId,
        (workplace) => ({
          ...workplace,

          map: scanData.map,
        })
      );

      /*
       * 5.
       * 초기 사물 설정 화면으로 이동
       */

      setPage("mapObjectSetup");
    } catch (error) {
      console.error(error);

      alert(
        error.message ||
          "지도 제작 중 오류가 발생했습니다."
      );
    }
  };

  /*
   * ===============================
   * 초기 지도 객체 설정 완료
   *
   * MapObjectSetup에서
   * Backend 저장까지 완료된 후 호출
   * ===============================
   */

  const completeMapObjectSetup = (
    mapData
  ) => {
    if (!selectedWorkplaceId) {
      return;
    }

    /*
     * Backend에서 받은
     * 최종 ready Map 저장
     */

    updateLocalWorkplace(
      selectedWorkplaceId,
      (workplace) => ({
        ...workplace,

        map: mapData,
      })
    );

    /*
     * 작업장 메인으로 복귀
     */

    setPage("main");
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
   * Backend 초기 연결
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

      {/* ============================= */}
      {/* 작업장 목록 */}
      {/* ============================= */}

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

      {/* ============================= */}
      {/* 작업장 추가 */}
      {/* ============================= */}

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

      {/* ============================= */}
      {/* 작업장 메인 */}
      {/* ============================= */}

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

      {/* ============================= */}
      {/* 초기 사물 설정 */}
      {/* ============================= */}

      {page === "mapObjectSetup" &&
        selectedWorkplace && (
          <MapObjectSetup
            workplace={
              selectedWorkplace
            }

            onComplete={
              completeMapObjectSetup
            }
          />
        )}

      {/* ============================= */}
      {/* 안전정책 */}
      {/* ============================= */}

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

      {/* ============================= */}
      {/* 순찰 상세 */}
      {/* ============================= */}

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