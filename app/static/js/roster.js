/** Stage 15: teacher roster management -- add students, generate access
 * codes, toggle a student active/inactive without deleting their history.
 */
(function () {
  const nameInput = document.getElementById("f-name");
  const consentInput = document.getElementById("f-consent");
  const addBtn = document.getElementById("add-btn");
  const addStatus = document.getElementById("add-status");
  const tableWrap = document.getElementById("roster-table");

  function showStatus(message, isError) {
    addStatus.textContent = message;
    addStatus.className = `text-sm ${isError ? "text-rose-600 dark:text-rose-400" : "text-emerald-600 dark:text-emerald-400"}`;
    addStatus.classList.remove("hidden");
  }

  async function loadRoster() {
    tableWrap.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">Loading&hellip;</p>';
    let roster;
    try {
      const res = await fetch("/api/roster");
      if (!res.ok) throw new Error(res.statusText);
      roster = await res.json();
    } catch (err) {
      tableWrap.innerHTML = '<p class="text-sm text-rose-600 dark:text-rose-400">Could not load the roster.</p>';
      return;
    }

    if (!roster.length) {
      tableWrap.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">No students yet -- add one on the left.</p>';
      return;
    }

    const table = document.createElement("table");
    table.className = "w-full text-sm";
    table.innerHTML = `
      <thead>
        <tr class="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
          <th class="py-2 pr-3">Name</th>
          <th class="py-2 pr-3">Access Code</th>
          <th class="py-2 pr-3">Consent</th>
          <th class="py-2 pr-3">Status</th>
          <th class="py-2"></th>
        </tr>
      </thead>
      <tbody>
        ${roster.map((s) => `
          <tr class="border-b border-slate-100 dark:border-slate-800 last:border-0" data-id="${s.id}">
            <td class="py-2 pr-3 font-medium ${s.active ? "" : "line-through text-slate-400"}">${s.name}</td>
            <td class="py-2 pr-3 font-mono tracking-wider">${s.access_code}</td>
            <td class="py-2 pr-3">
              ${s.consent_on_file
                ? '<span class="pill bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">On file</span>'
                : '<span class="pill bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">Missing</span>'}
            </td>
            <td class="py-2 pr-3">${s.active ? "Active" : "Inactive"}</td>
            <td class="py-2 text-right">
              <button type="button" class="toggle-active text-sm text-brand-600 dark:text-brand-400 hover:underline">
                ${s.active ? "Deactivate" : "Reactivate"}
              </button>
            </td>
          </tr>
        `).join("")}
      </tbody>`;
    tableWrap.innerHTML = "";
    tableWrap.appendChild(table);

    tableWrap.querySelectorAll(".toggle-active").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const row = btn.closest("tr");
        const id = row.dataset.id;
        const currentlyActive = btn.textContent.trim() === "Deactivate";
        await fetch(`/api/roster/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: !currentlyActive }),
        });
        loadRoster();
      });
    });
  }

  addBtn.addEventListener("click", async () => {
    const name = nameInput.value.trim();
    if (!name) { showStatus("Enter a student name.", true); nameInput.focus(); return; }

    addBtn.disabled = true;
    addBtn.textContent = "Adding…";
    try {
      const res = await fetch("/api/roster", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, consent_on_file: consentInput.checked }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail));
      }
      const student = await res.json();
      showStatus(`Added "${student.name}" -- their access code is ${student.access_code}. Write it down for them!`, false);
      nameInput.value = "";
      consentInput.checked = false;
      loadRoster();
    } catch (err) {
      showStatus("Could not add student: " + err.message, true);
    } finally {
      addBtn.disabled = false;
      addBtn.textContent = "Add Student & Generate Code";
    }
  });

  loadRoster();
})();
