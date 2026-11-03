import { useEffect, useState } from "react";

function App() {
  const [backendStatus, setBackendStatus] = useState("Comprobando...");

  useEffect(() => {
    fetch("/api/health/")
      .then((response) => {
        if (!response.ok) {
          throw new Error("Error en el backend");
        }

        return response.json();
      })
      .then((data) => {
        if (data.status === "ok") {
          setBackendStatus("Backend conectado correctamente ✅");
        } else {
          setBackendStatus("El backend respondió, pero no está OK");
        }
      })
      .catch((error) => {
        console.error(error);
        setBackendStatus("No se puede conectar con el backend ❌");
      });
  }, []);

  return (
    <div>
      <h1>Staffing App</h1>
      <p>{backendStatus}</p>
    </div>
  );
}

export default App;