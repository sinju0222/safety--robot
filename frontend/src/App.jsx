import {
  useEffect,
  useState,
} from "react";

import "./App.css";

import WorkplaceList
  from "./pages/WorkplaceList";

import AddWorkplace
  from "./pages/AddWorkplace";

import WorkplaceMain
  from "./pages/WorkplaceMain";

import SafetyPolicy
  from "./pages/SafetyPolicy";

import PatrolDetail
  from "./pages/PatrolDetail";

import MapZoneSetup
  from "./pages/MapZoneSetup";

import MapObjectSetup
  from "./pages/MapObjectSetup";


const API_BASE =
  "http://127.0.0.1:8000";


function App() {
  /*
   * ==========================================
   * Page
   * ==========================================
   *
   * workplaceList
   * addWorkplace
   * main
   * policy
   * patrolDetail
   * mapZoneSetup
   * mapObjectSetup
   */

  const [
    page,
    setPage,
  ] = useState(
    "workplaceList"
  );


  /*
   * ==========================================
   * Workplace
   * ==========================================
   */

  const [
    workplaces,
    setWorkplaces,
  ] = useState([]);


  const [
    selectedWorkplaceId,
    setSelectedWorkplaceId,
  ] = useState(null);


  /*
   * ==========================================
   * Patrol
   * ==========================================
   */

  const [
    selectedPatrolId,
    setSelectedPatrolId,
  ] = useState(null);


  /*
   * ==========================================
   * Loading
   * ==========================================
   */

  const [
    loading,
    setLoading,
  ] = useState(true);


  /*
   * ==========================================
   * Selected Workplace
   * ==========================================
   */

  const selectedWorkplace =
    workplaces.find(
      (workplace) =>
        workplace.id ===
        selectedWorkplaceId
    ) || null;


  /*
   * ==========================================
   * Initial Load
   * ==========================================
   */

  useEffect(() => {
    loadWorkplaces();
  }, []);


  /*
   * ==========================================
   * Load Workplaces
   * ==========================================
   */

  const loadWorkplaces =
    async () => {
      try {
        setLoading(true);

        const response =
          await fetch(
            `${API_BASE}/workplaces`
          );

        if (!response.ok) {
          throw new Error(
            "작업장 목록을 불러오지 못했습니다."
          );
        }

        const data =
          await response.json();

        setWorkplaces(
          data
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          "Backend 서버 연결을 확인해주세요."
        );
      } finally {
        setLoading(false);
      }
    };


  /*
   * ==========================================
   * Local Workplace Update
   * ==========================================
   */

  const updateLocalWorkplace = (
    workplaceId,
    updates
  ) => {
    setWorkplaces(
      (prev) =>
        prev.map(
          (workplace) =>
            workplace.id ===
            workplaceId
              ? {
                  ...workplace,
                  ...updates,
                }
              : workplace
        )
    );
  };


  /*
   * ==========================================
   * Map Update
   * ==========================================
   */

  const updateLocalMap = (
    workplaceId,
    mapData
  ) => {
    setWorkplaces(
      (prev) =>
        prev.map(
          (workplace) =>
            workplace.id ===
            workplaceId
              ? {
                  ...workplace,

                  map:
                    mapData,
                }
              : workplace
        )
    );
  };


  /*
   * ==========================================
   * Open Workplace
   * ==========================================
   */

  const openWorkplace = (
    workplace
  ) => {
    setSelectedWorkplaceId(
      workplace.id
    );

    setSelectedPatrolId(
      null
    );

    /*
     * 지도 제작 도중 화면을 나갔다가
     * 다시 들어왔을 경우
     * 현재 단계로 자동 복귀
     */

    if (
      workplace.map?.status ===
      "zone_setup"
    ) {
      setPage(
        "mapZoneSetup"
      );

      return;
    }

    if (
      workplace.map?.status ===
      "object_setup"
    ) {
      setPage(
        "mapObjectSetup"
      );

      return;
    }

    setPage(
      "main"
    );
  };


  /*
   * ==========================================
   * Back To Workplace List
   * ==========================================
   */

  const backToWorkplaceList =
    () => {
      setSelectedWorkplaceId(
        null
      );

      setSelectedPatrolId(
        null
      );

      setPage(
        "workplaceList"
      );
    };


  /*
   * ==========================================
   * Add Workplace Page
   * ==========================================
   */

  const openAddWorkplace =
    () => {
      setPage(
        "addWorkplace"
      );
    };


  /*
   * ==========================================
   * Create Workplace
   * ==========================================
   */

  const createWorkplace =
    async (name) => {
      const trimmedName =
        name.trim();

      if (!trimmedName) {
        alert(
          "작업장 이름을 입력해주세요."
        );

        return;
      }

      try {
        const response =
          await fetch(
            `${API_BASE}/workplaces`,
            {
              method:
                "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify({
                  name:
                    trimmedName,
                }),
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "작업장 생성에 실패했습니다."
          );
        }

        const workplace =
          await response.json();

        setWorkplaces(
          (prev) => [
            ...prev,
            workplace,
          ]
        );

        setSelectedWorkplaceId(
          workplace.id
        );

        setPage(
          "main"
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "작업장을 생성할 수 없습니다."
        );
      }
    };


  /*
   * ==========================================
   * Start Mapping
   * ==========================================
   *
   * 1. map/start
   * 2. Mock Mapping
   * 3. scan-complete
   * 4. STEP 1 구역 설정
   */

  const startMapping =
    async () => {
      if (
        !selectedWorkplace
      ) {
        return;
      }

      const workplaceId =
        selectedWorkplace.id;

      try {
        /*
         * --------------------------------------
         * 1. Mapping 시작
         * --------------------------------------
         */

        const startResponse =
          await fetch(
            `${API_BASE}/workplaces/${workplaceId}/map/start`,
            {
              method:
                "POST",
            }
          );

        if (
          !startResponse.ok
        ) {
          const errorData =
            await startResponse.json();

          throw new Error(
            errorData.detail ||
              "지도 제작을 시작할 수 없습니다."
          );
        }

        const startData =
          await startResponse.json();

        updateLocalMap(
          workplaceId,
          startData.map
        );


        /*
         * --------------------------------------
         * 현재는 Mock Mapping
         *
         * 추후 실제 구현:
         * TurtleBot3
         * → LiDAR
         * → SLAM
         * → Mapping 완료 신호
         * --------------------------------------
         */

        await new Promise(
          (resolve) =>
            setTimeout(
              resolve,
              2500
            )
        );


        /*
         * --------------------------------------
         * 2. Scan Complete
         * --------------------------------------
         */

        const scanResponse =
          await fetch(
            `${API_BASE}/workplaces/${workplaceId}/map/scan-complete`,
            {
              method:
                "POST",
            }
          );

        if (
          !scanResponse.ok
        ) {
          const errorData =
            await scanResponse.json();

          throw new Error(
            errorData.detail ||
              "지도 스캔 완료 처리에 실패했습니다."
          );
        }

        const scanData =
          await scanResponse.json();


        /*
         * Backend:
         *
         * creating
         * →
         * zone_setup
         */

        updateLocalMap(
          workplaceId,
          scanData.map
        );


        /*
         * STEP 1
         */

        setPage(
          "mapZoneSetup"
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "지도 제작 중 오류가 발생했습니다."
        );
      }
    };


  /*
   * ==========================================
   * STEP 1 Complete
   * ==========================================
   *
   * MapZoneSetup
   *
   * zone_setup
   * →
   * object_setup
   */

  const completeZoneSetup = (
    mapData
  ) => {
    if (
      !selectedWorkplaceId
    ) {
      return;
    }

    updateLocalMap(
      selectedWorkplaceId,
      mapData
    );

    /*
     * STEP 2로 이동
     */

    setPage(
      "mapObjectSetup"
    );
  };


  /*
   * ==========================================
   * STEP 2 Complete
   * ==========================================
   *
   * MapObjectSetup
   *
   * object_setup
   * →
   * ready
   */

  const completeMapObjectSetup = (
    mapData
  ) => {
    if (
      !selectedWorkplaceId
    ) {
      return;
    }

    updateLocalMap(
      selectedWorkplaceId,
      mapData
    );

    /*
     * Baseline Semantic Map 완성
     */

    setPage(
      "main"
    );
  };


  /*
   * ==========================================
   * Safety Policy
   * ==========================================
   */

  const openPolicy =
    () => {
      setPage(
        "policy"
      );
    };


  const savePolicies =
    async (policies) => {
      if (
        !selectedWorkplace
      ) {
        return;
      }

      try {
        const response =
          await fetch(
            `${API_BASE}/workplaces/${selectedWorkplace.id}/policies`,
            {
              method:
                "PUT",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body:
                JSON.stringify(
                  policies
                ),
            }
          );

        if (!response.ok) {
          const errorData =
            await response.json();

          throw new Error(
            errorData.detail ||
              "안전정책 저장에 실패했습니다."
          );
        }

        const savedPolicies =
          await response.json();

        updateLocalWorkplace(
          selectedWorkplace.id,
          {
            policies:
              savedPolicies,
          }
        );

        setPage(
          "main"
        );
      } catch (error) {
        console.error(
          error
        );

        alert(
          error.message ||
            "안전정책 저장 중 오류가 발생했습니다."
        );
      }
    };


  /*
   * ==========================================
   * Save Patrol
   * ==========================================
   */

  const savePatrol = (
    completedPatrol
  ) => {
    if (
      !selectedWorkplace
    ) {
      return;
    }

    const workplaceId =
      selectedWorkplace.id;

    setWorkplaces(
      (prev) =>
        prev.map(
          (workplace) => {
            if (
              workplace.id !==
              workplaceId
            ) {
              return workplace;
            }

            const existingPatrols =
              workplace.patrols ||
              [];

            const alreadyExists =
              existingPatrols.some(
                (patrol) =>
                  patrol.id ===
                  completedPatrol.id
              );

            const updatedPatrols =
              alreadyExists
                ? existingPatrols.map(
                    (patrol) =>
                      patrol.id ===
                      completedPatrol.id
                        ? completedPatrol
                        : patrol
                  )
                : [
                    completedPatrol,
                    ...existingPatrols,
                  ];

            return {
              ...workplace,

              lastPatrol:
                completedPatrol.completedAt,

              patrols:
                updatedPatrols,
            };
          }
        )
    );
  };


  /*
   * ==========================================
   * Open Patrol Detail
   * ==========================================
   */

  const openPatrol = (
    patrolId
  ) => {
    setSelectedPatrolId(
      patrolId
    );

    setPage(
      "patrolDetail"
    );
  };


  /*
   * ==========================================
   * Back To Main
   * ==========================================
   */

  const backToMain =
    () => {
      setSelectedPatrolId(
        null
      );

      setPage(
        "main"
      );
    };


  /*
   * ==========================================
   * Loading
   * ==========================================
   */

  if (loading) {
    return (
      <div className="screen">

        <div
          style={{
            padding: "40px 24px",
            textAlign: "center",
          }}
        >
          작업장 정보를
          불러오는 중...
        </div>

      </div>
    );
  }


  /*
   * ==========================================
   * Render
   * ==========================================
   */

  return (
    <>

      {/* ================================= */}
      {/* WORKPLACE LIST */}
      {/* ================================= */}

      {page ===
        "workplaceList" && (
        <WorkplaceList
          workplaces={
            workplaces
          }
          onAdd={
            openAddWorkplace
          }
          onSelect={
            openWorkplace
          }
        />
      )}


      {/* ================================= */}
      {/* ADD WORKPLACE */}
      {/* ================================= */}

      {page ===
        "addWorkplace" && (
        <AddWorkplace
          onBack={() =>
            setPage(
              "workplaceList"
            )
          }
          onCreate={
            createWorkplace
          }
        />
      )}


      {/* ================================= */}
      {/* WORKPLACE MAIN */}
      {/* ================================= */}

      {page === "main" &&
        selectedWorkplace && (
          <WorkplaceMain
            workplace={
              selectedWorkplace
            }
            onBack={
              backToWorkplaceList
            }
            onOpenPolicy={
              openPolicy
            }
            onStartMapping={
              startMapping
            }
            onSavePatrol={
              savePatrol
            }
            onOpenPatrol={
              openPatrol
            }
          />
        )}


      {/* ================================= */}
      {/* STEP 1 - ZONE SETUP */}
      {/* ================================= */}

      {page ===
        "mapZoneSetup" &&
        selectedWorkplace && (
          <MapZoneSetup
            workplace={
              selectedWorkplace
            }
            onComplete={
              completeZoneSetup
            }
          />
        )}


      {/* ================================= */}
      {/* STEP 2 - OBJECT SETUP */}
      {/* ================================= */}

      {page ===
        "mapObjectSetup" &&
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


      {/* ================================= */}
      {/* SAFETY POLICY */}
      {/* ================================= */}

      {page ===
        "policy" &&
        selectedWorkplace && (
          <SafetyPolicy
            workplace={
              selectedWorkplace
            }
            onBack={
              backToMain
            }
            onSave={
              savePolicies
            }
          />
        )}


      {/* ================================= */}
      {/* PATROL DETAIL */}
      {/* ================================= */}

      {page ===
        "patrolDetail" &&
        selectedWorkplace &&
        selectedPatrolId !==
          null && (
          <PatrolDetail
            workplace={
              selectedWorkplace
            }
            patrolId={
              selectedPatrolId
            }
            onBack={
              backToMain
            }
          />
        )}

    </>
  );
}


export default App;