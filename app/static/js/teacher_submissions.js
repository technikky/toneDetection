/** Stage 12: teacher-facing submission history, grouped by student for a given day. */
(function () {
  const dateFilter = document.getElementById("date-filter");
  const studentFilter = document.getElementById("student-filter");
  const resultCount = document.getElementById("result-count");
  const tableWrap = document.getElementById("submissions-table");

  function scoreColorClass(score) {
    if (score >= 85) return "text-emerald-600 dark:text-emerald-400";
    if (score >= 65) return "text-amber-600 dark:text-amber-400";
    return "text-rose-600 dark:text-rose-400";
  }

  function groupByStudent(rows) {
    const groups = new Map();
    for (const row of rows) {
      if (!groups.has(row.student_name)) groups.set(row.student_name, []);
      groups.get(row.student_name).push(row);
    }
    return groups;
  }

  async function load() {
    tableWrap.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400">Loading&hellip;</p>';
    const params = new URLSearchParams({ date: dateFilter.value });
    if (studentFilter.value.trim()) params.set("student", studentFilter.value.trim());

    let rows;
    try {
      const res = await fetch(`/api/submissions?${params}`);
      if (!res.ok) throw new Error(res.statusText);
      rows = await res.json();
    } catch (err) {
      tableWrap.innerHTML = '<p class="text-sm text-rose-600 dark:text-rose-400">Could not load submissions.</p>';
      return;
    }

    resultCount.textContent = `${rows.length} submission${rows.length === 1 ? "" : "s"}`;

    if (!rows.length) {
      tableWrap.innerHTML = '<p class="text-sm text-slate-500 dark:text-slate-400 py-6">No submissions for this date.</p>';
      return;
    }

    const groups = groupByStudent(rows);
    const sections = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));

    const table = document.createElement("table");
    table.className = "w-full text-sm";
    const thead = `
      <thead>
        <tr class="text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-slate-700">
          <th class="py-2 pr-3">Student</th>
          <th class="py-2 pr-3">Exercise</th>
          <th class="py-2 pr-3">Time</th>
          <th class="py-2 pr-3 text-right">Pitch</th>
          <th class="py-2 pr-3 text-right">Pronunciation</th>
          <th class="py-2 pr-3 text-right">Overall</th>
        </tr>
      </thead>`;

    const bodyRows = sections.flatMap(([student, takes]) =>
      takes.map((r, i) => `
        <tr class="border-b border-slate-100 dark:border-slate-800 last:border-0">
          <td class="py-2 pr-3 font-medium">${i === 0 ? student : ""}</td>
          <td class="py-2 pr-3 text-slate-600 dark:text-slate-400">${r.song_title}</td>
          <td class="py-2 pr-3 text-slate-500 dark:text-slate-500">${r.submitted_at.slice(11, 16)}</td>
          <td class="py-2 pr-3 text-right">${r.pitch_accuracy}%</td>
          <td class="py-2 pr-3 text-right">${r.pronunciation_accuracy}%</td>
          <td class="py-2 pr-3 text-right font-semibold ${scoreColorClass(r.overall_score)}">${r.overall_score}%</td>
        </tr>`).join("")
    ).join("");

    table.innerHTML = thead + `<tbody>${bodyRows}</tbody>`;
    tableWrap.innerHTML = "";
    tableWrap.appendChild(table);
  }

  let debounceTimer = null;
  function debouncedLoad() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 250);
  }

  dateFilter.addEventListener("change", load);
  studentFilter.addEventListener("input", debouncedLoad);

  load();
})();
