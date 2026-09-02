import Header from "./components/Header";
import StatusCard from "./components/StatusCard";
import PatrolSummary from "./components/PatrolSummary";

function App() {
  return (
    <div>
      <Header />

      <main>
        <StatusCard />
        <PatrolSummary />
      </main>
    </div>
  );
}

export default App;