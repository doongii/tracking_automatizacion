HTML = '''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tracking Automatizado</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 font-sans">
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-white shadow-xl rounded-xl p-5 w-full max-w-md">
      <h1 class="text-xl font-bold text-center text-gray-800 mb-6">Tracking Automatizado</h1>

      <!-- Selector de proyecto -->
      <label for="proyecto" class="block mb-2 text-gray-700 font-medium">Proyecto</label>
      <select id="proyecto" name="proyecto" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg">
        <option value="dreamfit">Dreamfit</option>
        <option value="profitness">ProFitness</option>
        <option value="mqa">MQA</option>
        <option value="beup">BeUp</option>
      </select>

      <label for="entero" class="block mb-2 text-gray-700 font-medium">Semana actual</label>
      <input type="number" id="entero" name="entero" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <label for="close_day" class="block mb-2 text-gray-700 font-medium">Fecha cierre (ej. aaaa-mm-dd hh:mm:ss)</label>
      <input type="text" id="close_day" name="close_day" placeholder="YYYY-MM-DD HH:MM:SS" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <label for="recordatorio" class="block mb-2 text-gray-700 font-medium">Fecha recordatorio (ej. mm-dd-aaaa)</label>
      <input type="text" id="recordatorio" name="recordatorio" placeholder="DD-MM-YYYY" class="w-full px-4 py-2 mb-4 border border-gray-300 rounded-lg" required>

      <div class="flex items-center mb-4">
        <input type="checkbox" id="test_mode" name="test_mode" class="mr-2 h-4 w-4 text-blue-600 border-gray-300 rounded">
        <label for="test_mode" class="text-gray-700 font-medium">Test:</label>
      </div>

      <!-- Drop area normal -->
      <div id="drop-area" class="w-full h-40 border-2 border-dashed border-gray-400 rounded-lg flex flex-col items-center justify-center cursor-pointer bg-gray-50 hover:bg-gray-100 transition mb-4">
        <p class="text-gray-500">Arrastra y suelta un archivo .xlsx o haz clic</p>
        <input type="file" id="fileElem" accept=".xlsx" class="hidden">
      </div>

      <!-- Drop areas específicos para BeUp -->
      <div id="beup-dropareas" class="hidden">
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Barakaldo - BeUp</p>
          <div id="drop-area-1" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 1</p>
            <input type="file" id="fileElem1" accept=".xlsx" class="hidden">
          </div>
        </div>
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Burgos - BeUp</p>
          <div id="drop-area-2" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 2</p>
            <input type="file" id="fileElem2" accept=".xlsx" class="hidden">
          </div>
        </div>
        <div class="mb-4">
          <p class="text-gray-700 font-medium mb-2">Santander - BeUp</p>
          <div id="drop-area-3" class="drop-area">
            <p class="text-gray-500">Arrastra y suelta Archivo 3</p>
            <input type="file" id="fileElem3" accept=".xlsx" class="hidden">
          </div>
        </div>
      </div>

      <button id="enviar" class="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition">Enviar</button>

      <div id="message" class="mt-4 text-sm text-gray-700 text-center"></div>
    </div>
  </div>

  <style>
    .drop-area {
      width: 100%;
      height: 150px;
      border: 2px dashed #ccc;
      border-radius: 0.5rem;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #f9fafb;
      cursor: pointer;
    }
  </style>

  <script>
    function getWeekNumber(d) {
      d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
      const dayNum = d.getUTCDay() || 7;
      d.setUTCDate(d.getUTCDate() + 4 - dayNum);
      const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
      return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
    }

    window.addEventListener('load', () => {
      const today = new Date();
      document.getElementById('entero').value = getWeekNumber(today);

      const closeDate = new Date(today);
      closeDate.setDate(closeDate.getDate() + 7);
      document.getElementById('close_day').value = closeDate.toISOString().split('T')[0] + ' 23:00:00';

      const reminderDate = new Date(today);
      reminderDate.setDate(reminderDate.getDate() + 2);
      const dd = String(reminderDate.getDate()).padStart(2, '0');
      const mm = String(reminderDate.getMonth() + 1).padStart(2, '0');
      const yyyy = reminderDate.getFullYear();
      document.getElementById('recordatorio').value = `${mm}-${dd}-${yyyy}`;
    });

    // Mostrar/ocultar drop areas según proyecto
    document.getElementById("proyecto").addEventListener("change", () => {
      const proyecto = document.getElementById("proyecto").value;
      const beupDropAreas = document.getElementById("beup-dropareas");
      const normalDropArea = document.getElementById("drop-area");
      if (proyecto === "beup") {
        beupDropAreas.classList.remove("hidden");
        normalDropArea.classList.add("hidden");
      } else {
        beupDropAreas.classList.add("hidden");
        normalDropArea.classList.remove("hidden");
      }
    });

    // Drag & Drop común
    const dropArea = document.getElementById("drop-area");
    const fileInput = document.getElementById("fileElem");
    const message = document.getElementById("message");
    const button = document.getElementById("enviar");

    dropArea.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", handleFiles);

    ['dragenter', 'dragover'].forEach(eventName => {
      dropArea.addEventListener(eventName, e => {
        e.preventDefault();
        dropArea.classList.add("border-blue-500");
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropArea.addEventListener(eventName, e => {
        e.preventDefault();
        dropArea.classList.remove("border-blue-500");
      });
    });

    dropArea.addEventListener("drop", e => {
      const dt = e.dataTransfer;
      const files = dt.files;
      fileInput.files = files;
      handleFiles();
    });

    function handleFiles() {
      if (fileInput.files.length) {
        message.innerText = `Archivo: ${fileInput.files[0].name}`;
      }
    }

    // Drag & Drop para BeUp (3 areas)
    for (let i = 1; i <= 3; i++) {
      const area = document.getElementById(`drop-area-${i}`);
      const input = document.getElementById(`fileElem${i}`);

      area.addEventListener("click", () => input.click());
      input.addEventListener("change", () => {
        if (input.files.length) {
          area.querySelector("p").innerText = `Archivo: ${input.files[0].name}`;
        }
      });

      ['dragenter', 'dragover'].forEach(eventName => {
        area.addEventListener(eventName, e => {
          e.preventDefault();
          area.classList.add("border-blue-500");
        });
      });

      ['dragleave', 'drop'].forEach(eventName => {
        area.addEventListener(eventName, e => {
          e.preventDefault();
          area.classList.remove("border-blue-500");
        });
      });

      area.addEventListener("drop", e => {
        const dt = e.dataTransfer;
        const files = dt.files;
        input.files = files;
        if (input.files.length) {
          area.querySelector("p").innerText = `Archivo: ${input.files[0].name}`;
        }
      });
    }

    // Enviar
    button.addEventListener("click", () => {
      const proyecto = document.getElementById("proyecto").value;
      const numero = document.getElementById("entero").value;
      const closeDay = document.getElementById("close_day").value;
      const recordatorio = document.getElementById("recordatorio").value;
      const testMode = document.getElementById("test_mode").checked ? "1" : "0";

      const formData = new FormData();
      formData.append("entero", numero);
      formData.append("close_day", closeDay);
      formData.append("recordatorio", recordatorio);
      formData.append("test_mode", testMode);
      formData.append("proyecto", proyecto);

      if (proyecto === "beup") {
        for (let i = 1; i <= 3; i++) {
          const input = document.getElementById(`fileElem${i}`);
          if (!input.files[0]) {
            message.innerText = `Falta Archivo ${i}.`;
            return;
          }
          formData.append(`file${i}`, input.files[0]);
        }
      } else {
        const file = fileInput.files[0];
        if (!file || !numero || !closeDay || !recordatorio) {
          message.innerText = "Faltan uno o más campos.";
          return;
        }
        formData.append("file", file);
      }

      message.innerText = "Enviando...";

      fetch(`/upload`, {
        method: "POST",
        body: formData
      })
      .then(res => res.json())
      .then(data => {
        message.innerHTML = data.message || "Éxito";
        if (data.archivos_partidos) {
          data.archivos_partidos.forEach(nombre => {
            message.innerHTML += `<br><a class="text-blue-600 underline" href="/descargar/${nombre}" download>${nombre}</a>`;
          });
        }
      })
      .catch(err => {
        message.innerText = "Error en la petición.";
        console.error(err);
      });
    });
  </script>
</body>
</html>

'''
