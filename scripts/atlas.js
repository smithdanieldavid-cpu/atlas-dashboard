fetch("data/atlas-latest.json")
  .then(res => res.json())
  .then(data => renderAtlas(data));

function renderAtlas(d) {
  document.getElementById("updated").textContent = d.overall.date;
  const dash = document.getElementById("dashboard");

  dash.innerHTML = `
    <section>
      <h2>Overall Status: ${d.overall.status}</h2>
      <p>${d.overall.comment}</p>
    </section>

    ${renderTable("Macro Indicators", d.macro)}
    ${renderTable("Micro Pulse Panel", d.micro)}
    ${renderTable("Storm Trigger Bar", d.triggers)}
  `;
}

function renderTable(title, rows) {
  return `
    <section>
      <h3>${title}</h3>
      <table>
        <thead><tr><th>Category</th><th>Status</th><th>Note</th></tr></thead>
        <tbody>
          ${rows.map(r =>
            `<tr class="${r.status}">
              <td>${r.name}</td><td>${r.status}</td><td>${r.note}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </section>
  `;
}
