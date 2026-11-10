// app.js
// Topic picking (via a rendered skill-tree graph), running a practice
// session against the BKT backend, and the local-only engagement layer
// (XP / streaks / session summary) that sits on top of it.

// ---------------------------------------------------------------- identity

let studentId = localStorage.getItem("basis_student_id");
if (!studentId) {
    studentId = crypto.randomUUID();
    localStorage.setItem("basis_student_id", studentId);
}

// ------------------------------------------------------------- skill graph
//
// Mirrors the prerequisite edges defined in app/skills.py. The backend
// remains the source of truth for mastery, locking, and difficulty - this
// only supplies the edges so the tree can be laid out and drawn client
// side. Keep in sync with skills.py when skills are added there.

const SKILL_GRAPH = {
    integer_arithmetic: { prereqs: [] },
    order_of_operations: { prereqs: ["integer_arithmetic"] },
    fractions: { prereqs: ["integer_arithmetic"] },
    percentages: { prereqs: ["fractions"] },
    ratios_proportions: { prereqs: ["fractions"] },
    combining_like_terms: { prereqs: ["order_of_operations"] },
    distributive_property: { prereqs: ["order_of_operations"] },
    exponents: { prereqs: ["integer_arithmetic"] },
    polynomial_add_sub: { prereqs: ["combining_like_terms", "exponents"] },
    one_step_equations: { prereqs: ["integer_arithmetic"] },
    absolute_value_equations: { prereqs: ["one_step_equations"] },
    two_step_equations: { prereqs: ["one_step_equations", "combining_like_terms"] },
    inequalities: { prereqs: ["two_step_equations"] },
    multi_step_equations: { prereqs: ["two_step_equations", "distributive_property"] },
    slope: { prereqs: ["fractions", "integer_arithmetic"] },
    slope_intercept_form: { prereqs: ["slope", "two_step_equations"] },
    systems_of_equations: { prereqs: ["multi_step_equations", "slope_intercept_form"] },
    factoring_quadratics: { prereqs: ["distributive_property", "exponents"] },
};

const MASTERY_THRESHOLD = 0.95; // mirrors app/skills.py, display only

function masteryColor(mastery) {
    const hue = Math.max(0, Math.min(1, mastery)) * 120; // 0 = red, 120 = green
    return `hsl(${hue}, 72%, 52%)`;
}

function masteryColorSoft(mastery) {
    const hue = Math.max(0, Math.min(1, mastery)) * 120;
    return `hsl(${hue}, 45%, 16%)`;
}

// ---------------------------------------------------------- gamification

const XP_KEY = "basis_total_xp";
const STREAK_KEY = "basis_current_streak";
const BEST_STREAK_KEY = "basis_best_streak";

function loadStoredNumber(key, fallback) {
    const raw = localStorage.getItem(key);
    const n = raw === null ? fallback : Number(raw);
    return Number.isFinite(n) ? n : fallback;
}

let totalXp = loadStoredNumber(XP_KEY, 0);
let currentStreak = loadStoredNumber(STREAK_KEY, 0);
let bestStreak = loadStoredNumber(BEST_STREAK_KEY, 0);

function persistGamification() {
    localStorage.setItem(XP_KEY, String(totalXp));
    localStorage.setItem(STREAK_KEY, String(currentStreak));
    localStorage.setItem(BEST_STREAK_KEY, String(bestStreak));
}

function renderGamificationBar() {
    const level = Math.floor(totalXp / 100) + 1;
    const barPct = totalXp % 100;
    document.getElementById("streak-value").textContent = currentStreak;
    document.getElementById("best-streak-value").textContent = bestStreak > 0 ? `best ${bestStreak}` : "";
    document.getElementById("level-value").textContent = level;
    document.getElementById("xp-bar-fill").style.width = `${barPct}%`;
    document.getElementById("xp-value").textContent = `${totalXp} XP`;
}

// correct: +10 XP, plus a +25 bonus every time the streak lands on a
// multiple of 5. wrong: +2 XP (consolation) and the streak resets.
function recordAnswer(correct) {
    let xpGained;
    if (correct) {
        currentStreak += 1;
        xpGained = 10;
        if (currentStreak % 5 === 0) {
            xpGained += 25;
        }
        bestStreak = Math.max(bestStreak, currentStreak);
    } else {
        currentStreak = 0;
        xpGained = 2;
    }
    totalXp += xpGained;
    persistGamification();
    renderGamificationBar();
    return xpGained;
}

// --------------------------------------------------------------- elements

const topicScreen = document.getElementById("topic-screen");
const problemScreen = document.getElementById("problem-screen");
const summaryScreen = document.getElementById("summary-screen");

const treeSvg = document.getElementById("skill-tree-svg");
const questionEl = document.getElementById("question-text");
const answerForm = document.getElementById("answer-form");
const answerInput = document.getElementById("answer-input");
const checkBtn = document.getElementById("check-btn");
const feedbackEl = document.getElementById("feedback");
const postAnswerActions = document.getElementById("post-answer-actions");
const nextProblemBtn = document.getElementById("next-problem-btn");
const difficultyBadge = document.getElementById("difficulty-badge");
const topicLabelEl = document.getElementById("current-topic-label");
const unlockBanner = document.getElementById("unlock-banner");
const problemCard = document.getElementById("problem-card");
const masteryFill = document.getElementById("mastery-progress-fill");
const masteryLabel = document.getElementById("mastery-progress-label");
const progressDotsEl = document.getElementById("session-progress-dots");

const SESSION_LENGTH = 10;

let session = null; // { sessionId, skillId, label, masteryStart, masteryCurrent, xpStart, results: [] }
let currentProblemId = null;

function showScreen(id) {
    for (const el of document.querySelectorAll(".screen")) {
        el.classList.toggle("hidden", el.id !== id);
    }
}

// ------------------------------------------------------------- skill tree

function computeDepths(graph) {
    const depth = {};
    function visit(id) {
        if (depth[id] !== undefined) return depth[id];
        const prereqs = graph[id].prereqs;
        depth[id] = prereqs.length === 0 ? 0 : 1 + Math.max(...prereqs.map(visit));
        return depth[id];
    }
    Object.keys(graph).forEach(visit);
    return depth;
}

function buildLayout() {
    const depth = computeDepths(SKILL_GRAPH);
    const byLevel = {};
    for (const id of Object.keys(SKILL_GRAPH)) {
        (byLevel[depth[id]] = byLevel[depth[id]] || []).push(id);
    }
    const levels = Object.keys(byLevel).map(Number).sort((a, b) => a - b);

    const colGap = 240;
    const rowGap = 92;
    const nodeW = 196;
    const nodeH = 68;
    const padding = 40;
    const maxCount = Math.max(...levels.map((l) => byLevel[l].length));
    const totalHeight = maxCount * rowGap;

    const positions = {};
    for (const lvl of levels) {
        const ids = byLevel[lvl];
        const colHeight = ids.length * rowGap;
        const startY = (totalHeight - colHeight) / 2;
        ids.forEach((id, i) => {
            positions[id] = { x: lvl * colGap + padding, y: startY + i * rowGap + padding };
        });
    }

    const width = levels.length * colGap + padding;
    const height = totalHeight + padding * 2;
    return { positions, width, height, nodeW, nodeH };
}

function renderSkillTree(topics) {
    const topicById = {};
    topics.forEach((t) => (topicById[t.key] = t));

    const layout = buildLayout();
    treeSvg.setAttribute("width", layout.width);
    treeSvg.setAttribute("height", layout.height);
    treeSvg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
    treeSvg.innerHTML = "";

    const svgNS = "http://www.w3.org/2000/svg";

    const defs = document.createElementNS(svgNS, "defs");
    defs.innerHTML = `
        <marker id="tree-arrow" viewBox="0 0 10 10" refX="8" refY="5"
                markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="#454c63"></path>
        </marker>`;
    treeSvg.appendChild(defs);

    // edges beneath nodes
    for (const [id, node] of Object.entries(SKILL_GRAPH)) {
        const to = layout.positions[id];
        for (const prereq of node.prereqs) {
            const from = layout.positions[prereq];
            const x1 = from.x + layout.nodeW;
            const y1 = from.y + layout.nodeH / 2;
            const x2 = to.x;
            const y2 = to.y + layout.nodeH / 2;
            const midX = (x1 + x2) / 2;
            const path = document.createElementNS(svgNS, "path");
            path.setAttribute("d", `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`);
            path.setAttribute("class", "tree-edge");
            path.setAttribute("marker-end", "url(#tree-arrow)");
            treeSvg.appendChild(path);
        }
    }

    // nodes
    for (const id of Object.keys(SKILL_GRAPH)) {
        const topic = topicById[id];
        if (!topic) continue;
        const pos = layout.positions[id];

        const fo = document.createElementNS(svgNS, "foreignObject");
        fo.setAttribute("x", pos.x);
        fo.setAttribute("y", pos.y);
        fo.setAttribute("width", layout.nodeW);
        fo.setAttribute("height", layout.nodeH);

        const div = document.createElement("div");
        div.className = "tree-node" + (topic.locked ? " locked" : "");
        if (!topic.locked) {
            div.style.background = masteryColorSoft(topic.mastery);
            div.style.borderColor = masteryColor(topic.mastery);
        }

        const label = document.createElement("span");
        label.className = "tree-node-label";
        label.textContent = topic.label;

        const sub = document.createElement("span");
        sub.className = "tree-node-sub";
        sub.textContent = topic.locked
            ? "locked"
            : topic.mastered
                ? "mastered"
                : `${Math.round(topic.mastery * 100)}% mastery`;

        div.appendChild(label);
        div.appendChild(sub);

        if (!topic.locked) {
            div.addEventListener("click", () => startTopic(id, topic.label));
        } else {
            div.title = topic.band;
        }

        fo.appendChild(div);
        treeSvg.appendChild(fo);
    }
}

async function loadTopics() {
    const res = await fetch(`/api/topics?student_id=${studentId}`);
    const topics = await res.json();
    renderSkillTree(topics);
}

// ------------------------------------------------------------ session flow

function updateMasteryProgress(mastery) {
    const pct = Math.min(100, Math.round((mastery / MASTERY_THRESHOLD) * 100));
    masteryFill.style.width = `${pct}%`;
    masteryFill.style.background = masteryColor(mastery);
    masteryLabel.textContent = `${Math.round(mastery * 100)}% mastery`;
}

function renderProgressDots() {
    progressDotsEl.innerHTML = "";
    for (let i = 0; i < SESSION_LENGTH; i++) {
        const dot = document.createElement("span");
        dot.className = "progress-dot";
        if (session && i < session.results.length) {
            dot.classList.add(session.results[i] ? "correct" : "incorrect");
        }
        progressDotsEl.appendChild(dot);
    }
}

function flashCard(correct) {
    problemCard.classList.remove("flash-correct", "shake-wrong");
    void problemCard.offsetWidth; // restart animation
    problemCard.classList.add(correct ? "flash-correct" : "shake-wrong");
}

async function startTopic(skillId, label) {
    const res = await fetch("/api/session/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, skill_id: skillId }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "That skill is locked.");
        return;
    }
    const data = await res.json();

    session = {
        sessionId: data.session_id,
        skillId,
        label,
        masteryStart: data.mastery,
        masteryCurrent: data.mastery,
        xpStart: totalXp,
        results: [],
    };

    topicLabelEl.textContent = label;
    showScreen("problem-screen");
    renderProgressDots();
    await loadNextProblem();
}

async function loadNextProblem() {
    feedbackEl.classList.add("hidden");
    postAnswerActions.classList.add("hidden");
    unlockBanner.classList.add("hidden");
    answerInput.value = "";
    answerInput.disabled = false;
    checkBtn.disabled = false;
    answerInput.focus();
    problemCard.classList.remove("flash-correct", "shake-wrong");

    const res = await fetch(`/api/session/${session.sessionId}/problem`);
    const data = await res.json();

    currentProblemId = data.problem_id;
    questionEl.textContent = data.question;
    difficultyBadge.textContent = data.difficulty;
    updateMasteryProgress(data.mastery);
}

answerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const answer = answerInput.value.trim();
    if (!answer || !session) return;

    answerInput.disabled = true;
    checkBtn.disabled = true;

    const res = await fetch(`/api/session/${session.sessionId}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem_id: currentProblemId, answer }),
    });
    const result = await res.json();

    session.masteryCurrent = result.mastery_after;
    session.results.push(result.correct);

    const xpGained = recordAnswer(result.correct);

    updateMasteryProgress(result.mastery_after);
    difficultyBadge.textContent = result.next_difficulty;
    renderProgressDots();
    flashCard(result.correct);

    feedbackEl.classList.remove("hidden");
    postAnswerActions.classList.remove("hidden");

    const pct = Math.round(result.mastery_after * 100);
    if (result.correct) {
        feedbackEl.textContent = `Correct! +${xpGained} XP${result.mastered ? " — skill mastered!" : ""}  (mastery ${pct}%)`;
        feedbackEl.className = "feedback correct";
    } else {
        feedbackEl.textContent = `Not quite — the answer was ${result.correct_answer}. +${xpGained} XP  (mastery ${pct}%)`;
        feedbackEl.className = "feedback incorrect";
    }

    if (result.newly_unlocked && result.newly_unlocked.length) {
        const plural = result.newly_unlocked.length > 1 ? "s" : "";
        unlockBanner.textContent = `New skill${plural} unlocked: ${result.newly_unlocked.join(", ")}`;
        unlockBanner.classList.remove("hidden");
    }

    nextProblemBtn.textContent = session.results.length >= SESSION_LENGTH ? "See summary" : "Next problem";
});

nextProblemBtn.addEventListener("click", () => {
    if (!session) return;
    if (session.results.length >= SESSION_LENGTH) {
        showSummary();
    } else {
        loadNextProblem();
    }
});

document.getElementById("change-topic-btn").addEventListener("click", () => {
    if (session) showSummary();
});

// --------------------------------------------------------------- summary

function showSummary() {
    const attempted = session.results.length;
    const correctCount = session.results.filter(Boolean).length;
    const accuracy = attempted > 0 ? Math.round((correctCount / attempted) * 100) : 0;
    const xpEarned = totalXp - session.xpStart;

    document.getElementById("summary-topic-label").textContent = session.label;
    document.getElementById("summary-attempted").textContent = attempted;
    document.getElementById("summary-accuracy").textContent = `${accuracy}%`;
    document.getElementById("summary-xp").textContent = `+${xpEarned}`;
    document.getElementById("summary-streak").textContent = currentStreak;

    const before = session.masteryStart;
    const after = session.masteryCurrent;
    document.getElementById("summary-mastery-text").textContent =
        `${Math.round(before * 100)}% → ${Math.round(after * 100)}%`;

    const fill = document.getElementById("summary-mastery-fill");
    fill.style.width = `${Math.round(after * 100)}%`;
    fill.style.background = masteryColor(after);
    document.getElementById("summary-mastery-marker").style.left = `${Math.round(before * 100)}%`;

    showScreen("summary-screen");
}

document.getElementById("summary-continue-btn").addEventListener("click", async () => {
    session = null;
    showScreen("topic-screen");
    await loadTopics();
});

// ------------------------------------------------------------------ init

renderGamificationBar();
loadTopics();
