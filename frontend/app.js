const API_URL = window.location.protocol === "file:"
    ? "http://127.0.0.1:8000"
    : window.location.origin;

const registerForm = document.getElementById("registerForm");

if (registerForm) {
    registerForm.addEventListener("submit", (event) => {
        event.preventDefault();
        alert("Регистрация успешно выполнена!");
        window.location.href = "dashboard.html";
    });
}

const datasetFile = document.getElementById("datasetFile");
const forecastButton = document.getElementById("forecastButton");
const forecastSelect = document.getElementById("forecastSelect");
const forecastTable = document.getElementById("forecastTable");
const datasetList = document.getElementById("datasetList");
const statusText = document.getElementById("statusText");
const canvas = document.getElementById("forecastCanvas");

function setStatus(message, isError = false) {
    if (!statusText) {
        return;
    }

    statusText.textContent = message;
    statusText.classList.toggle("error-text", isError);
}

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    }

    return data;
}

async function checkBackend() {
    if (!statusText) {
        return;
    }

    try {
        await fetchJson(`${API_URL}/health`);
        setStatus("Backend: подключен, прогноз на 24 часа готов к расчёту");
    } catch (error) {
        setStatus("Backend не отвечает. Запустите сервер FastAPI.", true);
    }
}

async function loadDatasets() {
    if (!datasetList) {
        return;
    }

    try {
        const data = await fetchJson(`${API_URL}/datasets`);
        const datasets = data.datasets || [];

        if (!datasets.length) {
            datasetList.textContent = "Список пуст";
            return;
        }

        datasetList.innerHTML = "";

        datasets.forEach((name) => {
            const item = document.createElement("div");
            item.className = "file-item";

            const label = document.createElement("span");
            label.className = "file-pill";
            label.textContent = name;

            const button = document.createElement("button");
            button.className = "file-delete-btn";
            button.type = "button";
            button.textContent = "Удалить";
            button.addEventListener("click", () => deleteDataset(name));

            item.append(label, button);
            datasetList.append(item);
        });
    } catch (error) {
        datasetList.textContent = "Не удалось загрузить список";
    }
}

async function deleteDataset(filename) {
    if (!confirm(`Удалить датасет "${filename}"?`)) {
        return;
    }

    try {
        const data = await fetchJson(`${API_URL}/delete-dataset/${encodeURIComponent(filename)}`, {
            method: "DELETE",
        });

        setStatus(data.message || "Датасет удалён");
        await loadDatasets();
    } catch (error) {
        setStatus(error.message || "Не удалось удалить датасет", true);
    }
}

async function loadForecasts() {
    if (!forecastSelect) {
        return;
    }

    try {
        const data = await fetchJson(`${API_URL}/forecasts`);
        const forecasts = data.forecasts || [];

        forecastSelect.innerHTML = forecasts.length
            ? forecasts.map((name) => `<option value="${name}">${name}</option>`).join("")
            : `<option value="">Нет прогнозов</option>`;

        if (forecasts.length) {
            const latest = forecasts[forecasts.length - 1];
            forecastSelect.value = latest;
            await loadForecastData(latest);
        }
    } catch (error) {
        forecastSelect.innerHTML = `<option value="">Ошибка загрузки</option>`;
    }
}

async function createForecast() {
    if (!datasetFile || !datasetFile.files.length) {
        alert("Выберите CSV-файл");
        return;
    }

    const formData = new FormData();
    formData.append("file", datasetFile.files[0]);
    setStatus("Рассчитываем вероятность осадков на ближайшие сутки...");

    try {
        const data = await fetchJson(`${API_URL}/forecast`, {
            method: "POST",
            body: formData,
        });

        if (data.error) {
            setStatus(data.error, true);
            return;
        }

        setStatus(data.message || "Прогноз построен");
        await loadDatasets();
        await loadForecasts();

        if (data.forecast) {
            forecastSelect.value = data.forecast;
            await loadForecastData(data.forecast);
        }
    } catch (error) {
        setStatus(error.message || "Не удалось построить прогноз", true);
    }
}

async function loadForecastData(filename) {
    if (!filename || !forecastTable) {
        return;
    }

    try {
        const rows = await fetchJson(`${API_URL}/forecast-data/${filename}`);
        renderForecast(rows);
    } catch (error) {
        forecastTable.innerHTML = `<tr><td colspan="3">Не удалось загрузить прогноз</td></tr>`;
    }
}

function renderForecast(rows) {
    if (!rows.length) {
        forecastTable.innerHTML = `<tr><td colspan="3">Прогноз пуст</td></tr>`;
        return;
    }

    forecastTable.innerHTML = rows.map((row) => `
        <tr>
            <td>${formatDate(row.date)}</td>
            <td>${row.rain}</td>
            <td>${row.probability}%</td>
        </tr>
    `).join("");

    updateSummary(rows);
    drawForecast(rows);
}

function updateSummary(rows) {
    const row = rows[0];
    setText("oneDayValue", `${row.rain} мм, ${row.probability}%`);
    setText("weekValue", "24 часа вперёд");
    setText("twoWeeksValue", "model_xgb_24h");
    setText("threeWeeksValue", Number(row.probability) >= 50 ? "Осадки вероятны" : "Осадки маловероятны");
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function drawForecast(rows) {
    if (!canvas || !rows.length) {
        return;
    }

    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const padding = 36;
    const probability = Number(rows[0].probability || 0);
    const barWidth = width - padding * 2;
    const barHeight = 62;
    const x = padding;
    const y = height / 2 - barHeight / 2;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#f3f7f8";
    ctx.fillRect(0, 0, width, height);
    ctx.fillStyle = "#dce5ea";
    ctx.fillRect(x, y, barWidth, barHeight);
    ctx.fillStyle = probability >= 50 ? "#176d76" : "#f0b84f";
    ctx.fillRect(x, y, barWidth * probability / 100, barHeight);
    ctx.fillStyle = "#17202a";
    ctx.font = "bold 28px Arial";
    ctx.fillText(`Вероятность осадков: ${probability}%`, x, y - 18);
    ctx.font = "18px Arial";
    ctx.fillText(`Ожидаемые осадки: ${rows[0].rain} мм`, x, y + barHeight + 34);
}

function formatDate(value) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString("ru-RU");
}

function selectedForecast() {
    return forecastSelect ? forecastSelect.value : "";
}

function downloadForecast(format) {
    const filename = selectedForecast();

    if (!filename) {
        alert("Сначала создайте прогноз");
        return;
    }

    window.open(`${API_URL}/download/${format}/${filename}`, "_blank");
}

if (forecastButton) {
    forecastButton.addEventListener("click", createForecast);
}

if (forecastSelect) {
    forecastSelect.addEventListener("change", () => loadForecastData(forecastSelect.value));
}

document.querySelectorAll("[data-format]").forEach((button) => {
    button.addEventListener("click", () => downloadForecast(button.dataset.format));
});

checkBackend();
loadDatasets();
loadForecasts();
