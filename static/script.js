
const money = amount =>
    new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2
    }).format(amount);

let categoryChart = null;

const $ = id => document.getElementById(id);

function showMessage(message, success = false) {
    const element = $("form-message");
    element.textContent = message;
    element.className = "form-message " + (success ? "success" : "failure");
}

async function api(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...options.headers
        }
    });

    const data = await response.json().catch(() => ({}));

    if (response.status === 401 || response.redirected) {
        window.location.href = "/login";
        throw new Error("Please sign in again.");
    }

    if (!response.ok) {
        throw new Error(data.error || "Something went wrong.");
    }

    return data;
}

function renderChart(categories) {
    const labels = Object.keys(categories);
    const values = Object.values(categories);

    if (categoryChart) {
        categoryChart.destroy();
    }

    categoryChart = new Chart($("category-chart"), {
        type: "doughnut",
        data: {
            labels: labels.length ? labels : ["No expenses yet"],
            datasets: [{
                data: values.length ? values : [1],
                backgroundColor: [
                    "#6258e8", "#24a77a", "#f2ad55",
                    "#e76f85", "#4e9bd8", "#9b79d6",
                    "#49b9bd", "#ef8d4c", "#9ca3af"
                ],
                borderWidth: 0,
                hoverOffset: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "68%",
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        usePointStyle: true,
                        pointStyle: "circle",
                        padding: 15,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: context =>
                            `${context.label}: ${money(
                                values.length ? context.raw : 0
                            )}`
                    }
                }
            }
        }
    });
}

async function loadSummary() {
    const data = await api("/api/summary");

    $("total-income").textContent = money(data.total_income);
    $("total-expenses").textContent = money(data.total_expenses);
    $("balance").textContent = money(data.balance);
    $("month-income").textContent = money(data.month_income);
    $("month-expenses").textContent = money(data.month_expenses);
    $("insight").textContent = data.insight;

    renderChart(data.categories);
}

function makeCell(text, className = "") {
    const cell = document.createElement("td");
    cell.textContent = text;
    if (className) cell.className = className;
    return cell;
}

async function loadTransactions() {
    const items = await api("/api/transactions");
    const tbody = $("transaction-list");
    tbody.replaceChildren();

    if (items.length === 0) {
        const row = document.createElement("tr");
        const cell = makeCell("No transactions yet. Add your first one above.");
        cell.colSpan = 6;
        cell.className = "empty-state";
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
    }

    items.forEach(item => {
        const row = document.createElement("tr");

        row.appendChild(makeCell(item.title));
        row.appendChild(makeCell(item.category));
        row.appendChild(makeCell(item.date));

        const typeCell = document.createElement("td");
        const pill = document.createElement("span");
        pill.className = "type-pill";
        pill.textContent = item.kind === "income" ? "Income" : "Expense";
        typeCell.appendChild(pill);
        row.appendChild(typeCell);

        row.appendChild(makeCell(
            (item.kind === "income" ? "+" : "-") + money(item.amount),
            item.kind === "income" ? "amount-income" : "amount-expense"
        ));

        const actionCell = document.createElement("td");
        const button = document.createElement("button");
        button.className = "delete-btn";
        button.textContent = "Delete";

        button.addEventListener("click", async () => {
            if (!confirm(`Delete "${item.title}"?`)) return;

            try {
                await api(`/api/transactions/${item.id}`, {
                    method: "DELETE"
                });
                await refreshDashboard();
                showMessage("Transaction deleted successfully.", true);
            } catch (error) {
                showMessage(error.message);
            }
        });

        actionCell.appendChild(button);
        row.appendChild(actionCell);
        tbody.appendChild(row);
    });
}

async function refreshDashboard() {
    await Promise.all([loadSummary(), loadTransactions()]);
}

$("transaction-form").addEventListener("submit", async event => {
    event.preventDefault();

    const form = event.currentTarget;
    const button = form.querySelector('button[type="submit"]');
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "Adding...";

    const transaction = {
        title: $("title").value.trim(),
        amount: Number($("amount").value),
        kind: $("kind").value,
        category: $("category").value,
        date: $("date").value
    };

    try {
        await api("/api/transactions", {
            method: "POST",
            body: JSON.stringify(transaction)
        });

        form.reset();
        $("date").value = getLocalDate();
        $("kind").value = "expense";

        await refreshDashboard();
        showMessage("Transaction added successfully!", true);
    } catch (error) {
        showMessage(error.message);
    } finally {
        button.disabled = false;
        button.textContent = originalText;
    }
});

function getLocalDate() {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

async function initializeDashboard() {
    $("today-date").textContent = new Date().toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric"
    });

    $("date").value = getLocalDate();

    try {
        await refreshDashboard();
    } catch (error) {
        showMessage(error.message);
    }
}

initializeDashboard();
