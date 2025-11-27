<script setup>
import { computed, onMounted, ref } from "vue";
import dilgLogo from "./assets/dilg-logo.png";

// Adjust this if your backend runs elsewhere
const API_BASE = "http://localhost:8000/api";

const voterId = ref("");
const pin = ref("");
const token = ref(localStorage.getItem("sessionToken") || "");
const voter = ref(null);

const adminUsername = ref("");
const adminPassword = ref("");
const adminToken = ref(localStorage.getItem("adminToken") || "");
const admin = ref(null);

const view = ref("session");
const navDrawerOpen = ref(true);
const navLinks = [
  { key: "session", label: "Session" },
  { key: "admin", label: "Admin" },
  { key: "vote", label: "Vote" },
  { key: "candidates", label: "Candidates" },
  { key: "tally", label: "Tally" },
];

const positions = ref([]);
const candidates = ref([]);
const selectedPosition = ref("");
const selectedCandidate = ref("");

const tally = ref([]);

const loading = ref(false);
const loginLoading = ref(false);
const adminLoginLoading = ref(false);
const voteLoading = ref(false);
const tallyLoading = ref(false);

const statusMessage = ref("");
const statusType = ref("info");

const filteredCandidates = computed(() => {
  if (!selectedPosition.value) return candidates.value;
  return candidates.value.filter(
    (cand) => String(cand.position) === String(selectedPosition.value),
  );
});

const summary = computed(() => {
  const totalVotes = tally.value.reduce((sum, pos) => {
    const votesForPosition = (pos.candidates || []).reduce(
      (inner, cand) => inner + (cand.votes || 0),
      0,
    );
    return sum + votesForPosition;
  }, 0);

  return {
    positions: positions.value.length,
    candidates: candidates.value.length,
    votes: totalVotes,
  };
});

const sessionLabel = computed(() => {
  if (admin.value) return "Admin active";
  if (voter.value) return "Session active";
  return "Awaiting login";
});

const sessionState = computed(() => {
  if (admin.value) return "admin";
  if (voter.value) return "on";
  return "off";
});

const heroPillType = computed(() => {
  if (admin.value) return "warning";
  if (voter.value) return "success";
  return "info";
});

const heroPillLabel = computed(() => {
  if (admin.value) return "Admin mode";
  if (voter.value) return "Logged in";
  return "Guest view";
});

const setStatus = (message, type = "info") => {
  statusMessage.value = message;
  statusType.value = type;
};

const setView = (next) => {
  view.value = next;
  navDrawerOpen.value = false;
  // reset transient errors when switching context
  statusMessage.value = "";
};

const request = async (
  path,
  { method = "GET", body, auth = false, adminAuth = false } = {},
) => {
  const headers = { "Content-Type": "application/json" };
  if (auth && token.value) {
    headers["X-Session-Token"] = token.value;
  }
  if (adminAuth && adminToken.value) {
    headers["X-Admin-Token"] = adminToken.value;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    data = {};
  }

  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
};

const loadPositions = async () => {
  const data = await request("/positions/");
  positions.value = data || [];
};

const loadCandidates = async () => {
  const data = await request("/candidates/");
  candidates.value = data || [];
};

const loadTally = async () => {
  tallyLoading.value = true;
  try {
    const data = await request("/tally/");
    tally.value = data || [];
    setStatus("Tally refreshed.", "success");
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    tallyLoading.value = false;
  }
};

const checkSession = async () => {
  if (!token.value) return;
  try {
    const data = await request("/me/", { auth: true });
    if (data.authenticated) {
      voter.value = data.voter;
      setStatus("Session restored.", "success");
    } else {
      token.value = "";
      localStorage.removeItem("sessionToken");
    }
  } catch (err) {
    token.value = "";
    localStorage.removeItem("sessionToken");
  }
};

const checkAdminSession = async () => {
  if (!adminToken.value) return;
  try {
    const data = await request("/admin/me/", { adminAuth: true });
    if (data.authenticated) {
      admin.value = data.admin;
      setStatus("Admin session restored.", "success");
    } else {
      adminToken.value = "";
      localStorage.removeItem("adminToken");
    }
  } catch (err) {
    adminToken.value = "";
    admin.value = null;
    localStorage.removeItem("adminToken");
  }
};

const login = async () => {
  loginLoading.value = true;
  setStatus("");
  try {
    const data = await request("/login/", {
      method: "POST",
      body: { voter_id: voterId.value, pin: pin.value },
    });
    token.value = data.token;
    localStorage.setItem("sessionToken", data.token);
    voter.value = data.voter;
    setStatus("Logged in successfully.", "success");
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    loginLoading.value = false;
  }
};

const adminLogin = async () => {
  adminLoginLoading.value = true;
  setStatus("");
  try {
    const data = await request("/admin/login/", {
      method: "POST",
      body: { username: adminUsername.value, password: adminPassword.value },
    });
    adminToken.value = data.token;
    localStorage.setItem("adminToken", data.token);
    admin.value = data.admin;
    setStatus("Admin logged in successfully.", "success");
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    adminLoginLoading.value = false;
  }
};

const logout = async () => {
  try {
    await request("/logout/", { method: "POST", auth: true });
  } catch (e) {
    // ignore logout errors so user can still clear the session
  }
  token.value = "";
  voter.value = null;
  localStorage.removeItem("sessionToken");
  setStatus("Logged out.", "info");
};

const adminLogout = async () => {
  try {
    await request("/admin/logout/", { method: "POST", adminAuth: true });
  } catch (e) {
    // allow client-side clear if token is already invalid
  }
  adminToken.value = "";
  admin.value = null;
  localStorage.removeItem("adminToken");
  setStatus("Admin logged out.", "info");
};

const castVote = async () => {
  if (!voter.value || !token.value) {
    setStatus("Please log in first.", "error");
    return;
  }
  if (!selectedPosition.value || !selectedCandidate.value) {
    setStatus("Select a position and candidate.", "error");
    return;
  }

  voteLoading.value = true;
  setStatus("");
  try {
    await request("/vote/", {
      method: "POST",
      body: {
        position_id: selectedPosition.value,
        candidate_id: selectedCandidate.value,
      },
      auth: true,
    });
    setStatus("Vote cast successfully!", "success");
    voter.value = { ...voter.value, has_voted: true };
    await loadTally();
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    voteLoading.value = false;
  }
};

const maxVotesForPosition = (position) => {
  if (!position || !position.candidates || !position.candidates.length) return 0;
  return Math.max(...position.candidates.map((cand) => Number(cand.votes) || 0));
};

const votePercent = (candidate, position) => {
  const max = maxVotesForPosition(position);
  if (!max) return 0;
  return Math.round(((Number(candidate.votes) || 0) / max) * 100);
};

const init = async () => {
  loading.value = true;
  try {
    await Promise.all([loadPositions(), loadCandidates()]);
    await Promise.all([checkSession(), checkAdminSession()]);
    await loadTally();
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  init();
});
</script>

<template>
  <div class="page">
    <section class="masthead">
      <div class="masthead-left">
        <img :src="dilgLogo" alt="DILG logo" class="masthead-logo" />
        <div>
          <p class="masthead-eyebrow">Republic of the Philippines</p>
          <p class="masthead-title">Department of the Interior and Local Government</p>
        </div>
      </div>
      <div class="masthead-right">
        <p class="masthead-note">Official ballot portal</p>
      </div>
    </section>

    <header class="top-bar">
      <div class="brand">
        <div class="brand-mark">DV</div>
        <div>
          <p class="eyebrow">DILG Voting System</p>
          <p class="brand-title">Secure Balloting Portal</p>
        </div>
      </div>
      <div class="status-chip" :data-state="sessionState">
        {{ sessionLabel }}
      </div>
    </header>

    <aside class="nav-drawer" data-open="true">
      <div class="nav-drawer-inner">
        <div class="nav-drawer-header">
          <span>Navigation</span>
        </div>
        <div class="nav-drawer-links">
          <button
            v-for="link in navLinks"
            :key="link.key"
            type="button"
            :data-active="view === link.key"
            @click="setView(link.key)"
          >
            {{ link.label }}
          </button>
        </div>
        <div class="nav-drawer-status">
          <p class="muted">Status</p>
          <div class="pill" :data-type="heroPillType">{{ heroPillLabel }}</div>
        </div>
      </div>
    </aside>

    <section class="hero">
      <div class="hero-text">
        <p class="eyebrow">Transparent. Verifiable. Ready.</p>
        <h1>Vote, verify, and view tallies in one place.</h1>
        <p class="subhead">
          Log in with your Voter ID and PIN, cast your ballot, and track results in real time.
        </p>
        <div class="hero-actions">
          <button class="cta primary" type="button" @click="setView('vote')">Go to ballot</button>
          <button class="cta ghost" type="button" @click="setView('tally')">View live tally</button>
        </div>
        <div class="steps">
          <div class="step">
            <span class="step-number">1</span>
            <div>
              <p class="step-title">Authenticate</p>
              <p class="step-sub">Use your issued Voter ID and PIN to unlock the ballot.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">2</span>
            <div>
              <p class="step-title">Select</p>
              <p class="step-sub">Choose the position and candidate with clarity and context.</p>
            </div>
          </div>
          <div class="step">
            <span class="step-number">3</span>
            <div>
              <p class="step-title">Confirm</p>
              <p class="step-sub">Submit once, then watch your vote reflected in the tally.</p>
            </div>
          </div>
        </div>
      </div>
      <div class="hero-card">
        <div class="hero-card-header">
          <p class="eyebrow">Live snapshot</p>
          <span class="pill small" :data-type="heroPillType">
            {{ heroPillLabel }}
          </span>
        </div>
        <div class="stat-grid">
          <div class="stat">
            <p class="stat-label">Positions loaded</p>
            <p class="stat-value">{{ summary.positions }}</p>
          </div>
          <div class="stat">
            <p class="stat-label">Candidates</p>
            <p class="stat-value">{{ summary.candidates }}</p>
          </div>
          <div class="stat">
            <p class="stat-label">Votes tallied</p>
            <p class="stat-value">{{ summary.votes }}</p>
          </div>
        </div>
        <div class="callout">
          <p class="muted">API base</p>
          <p class="value">{{ API_BASE }}</p>
          <p class="note">Ensure the backend is reachable and CORS is enabled.</p>
        </div>
      </div>
    </section>

    <section class="view-switch">
      <div class="tab-group">
        <button
          v-for="opt in ['session', 'admin', 'vote', 'candidates', 'tally']"
          :key="opt"
          type="button"
          class="tab"
          :data-active="view === opt"
          @click="setView(opt)"
        >
          {{ opt.charAt(0).toUpperCase() + opt.slice(1) }}
        </button>
      </div>
      <p class="view-note">
        Focus on one flow at a time - switch tabs to manage sessions, admin access, voting, candidates, or tallies.
      </p>
    </section>

    <section class="status" v-if="statusMessage">
      <div class="pill" :data-type="statusType">{{ statusMessage }}</div>
    </section>

    <section v-if="view === 'session'" id="session" class="view-panel">
      <article class="card highlight">
        <div class="card-header">
          <div>
            <p class="eyebrow">Session</p>
            <h2>{{ voter ? "You are logged in" : "Log in to vote" }}</h2>
          </div>
          <span class="dot" :data-state="voter ? 'on' : 'off'"></span>
        </div>

        <div v-if="voter" class="session-box">
          <p class="label">Name</p>
          <p class="value">{{ voter.name }}</p>
          <p class="label">Voter ID</p>
          <p class="value">{{ voter.voter_id }}</p>
          <p class="label">Status</p>
          <p class="value" :class="{ success: voter.has_voted }">
            {{ voter.has_voted ? "Already voted" : "Not yet voted" }}
          </p>
          <button type="button" class="ghost" @click="logout">Logout</button>
        </div>

        <form v-else class="form" @submit.prevent="login">
          <label class="field">
            <span>Voter ID</span>
            <input
              v-model="voterId"
              required
              name="voter_id"
              autocomplete="username"
              placeholder="e.g. VOTER-001"
            />
          </label>

          <label class="field">
            <span>PIN</span>
            <input
              v-model="pin"
              required
              name="pin"
              type="password"
              autocomplete="current-password"
              placeholder="Enter your PIN"
            />
          </label>

          <button type="submit" :disabled="loginLoading">
            {{ loginLoading ? "Signing in..." : "Log In" }}
          </button>
        </form>

        <div class="helper">
          <p class="helper-title">Session tips</p>
          <ul class="helper-list">
            <li>Use the official Voter ID and PIN provided to you.</li>
            <li>Each ballot can be submitted once per voter.</li>
            <li>Log out when you are done, especially on shared devices.</li>
          </ul>
        </div>
      </article>
    </section>

      <section v-if="view === 'admin'" class="view-panel">
        <article class="card admin-card">
          <div class="card-header">
            <div>
              <p class="eyebrow">Admin</p>
              <h2>{{ admin ? "Admin control" : "Admin login" }}</h2>
              <p class="subhead small">
                Staff credentials unlock protected actions.
              </p>
            </div>
            <span class="pill small" :data-type="admin ? 'warning' : 'info'">
              {{ admin ? "Active" : "Restricted" }}
            </span>
          </div>

          <div v-if="admin" class="session-box">
            <p class="label">Admin name</p>
            <p class="value">{{ admin.name }}</p>
            <p class="label">Username</p>
            <p class="value">{{ admin.username }}</p>
            <p class="label">Role</p>
            <p class="value">{{ admin.is_superuser ? "Superuser" : "Staff" }}</p>
            <button type="button" class="ghost" @click="adminLogout">Sign out</button>
          </div>

          <form v-else class="form" @submit.prevent="adminLogin">
            <label class="field">
              <span>Username</span>
              <input
                v-model="adminUsername"
                required
                name="admin_username"
                autocomplete="username"
                placeholder="admin"
              />
            </label>

            <label class="field">
              <span>Password</span>
              <input
                v-model="adminPassword"
                required
                name="admin_password"
                type="password"
                autocomplete="current-password"
                placeholder="Enter admin password"
              />
            </label>

            <button type="submit" :disabled="adminLoginLoading">
              {{ adminLoginLoading ? "Signing in..." : "Log in as admin" }}
            </button>
          </form>

          <div class="helper">
            <p class="helper-title">Admin tips</p>
            <ul class="helper-list">
              <li>Use staff credentials created in the Django admin.</li>
              <li>Keep this session separate from voter logins.</li>
              <li>Tokens expire automatically; sign out when done.</li>
            </ul>
          </div>
        </article>
      </section>

      <section v-if="view === 'vote'" id="vote" class="view-panel">
        <article class="card">
          <div class="card-header">
            <div>
              <p class="eyebrow">Vote</p>
              <h2>Cast your vote</h2>
            </div>
          </div>

          <div class="form">
            <label class="field">
              <span>Position</span>
              <select v-model="selectedPosition">
                <option value="">Select a position</option>
                <option v-for="pos in positions" :key="pos.id" :value="pos.id">
                  {{ pos.name }}{{ pos.level ? " (" + pos.level + ")" : "" }}
                </option>
              </select>
            </label>

            <label class="field">
              <span>Candidate</span>
              <select v-model="selectedCandidate">
                <option value="">Select a candidate</option>
                <option v-for="cand in filteredCandidates" :key="cand.id" :value="cand.id">
                  {{ cand.full_name }} - {{ cand.party || "Independent" }}
                </option>
              </select>
            </label>

            <button type="button" :disabled="voteLoading" @click="castVote">
              {{ voteLoading ? "Submitting..." : "Submit Vote" }}
            </button>
          </div>

          <div class="inline-note" v-if="!voter">
            Log in to unlock the ballot and submit your vote securely.
          </div>
        </article>
      </section>

      <section v-if="view === 'candidates'" id="candidates" class="card wide view-panel">
        <div class="card-header">
          <div>
            <p class="eyebrow">Candidates</p>
            <h2>Browse candidates</h2>
            <p class="subhead small">
              Filter by selecting a position in the ballot above to focus this list.
            </p>
          </div>
          <button class="ghost" type="button" @click="() => { loadCandidates(); setStatus('Candidates refreshed.', 'info'); }">
            Refresh
          </button>
        </div>

        <div class="candidate-grid" v-if="filteredCandidates.length">
          <div class="candidate" v-for="cand in filteredCandidates" :key="cand.id">
            <div class="row">
              <div>
                <p class="eyebrow muted">Position</p>
                <h3>{{ cand.position_name || "Position" }}</h3>
              </div>
              <span class="tag">{{ cand.party || "Independent" }}</span>
            </div>
            <p class="muted">{{ cand.full_name }}</p>
            <p class="bio" v-if="cand.bio">{{ cand.bio }}</p>
          </div>
        </div>
        <div class="empty" v-else>
          <p class="muted">No candidates to display for the selected filter.</p>
        </div>
      </section>

      <section v-if="view === 'tally'" id="tally" class="card wide view-panel">
        <div class="card-header">
          <div>
            <p class="eyebrow">Results</p>
            <h2>Live tally</h2>
          </div>
          <button class="ghost" type="button" :disabled="tallyLoading" @click="loadTally">
            {{ tallyLoading ? "Refreshing..." : "Refresh" }}
          </button>
        </div>

        <div class="tally" v-if="tally.length">
          <div class="tally-block" v-for="pos in tally" :key="pos.position_id">
            <div class="row">
              <div>
                <p class="eyebrow muted">{{ pos.level }}</p>
                <h3>{{ pos.position }}</h3>
              </div>
              <span class="tag">{{ (pos.candidates || []).length }} candidates</span>
            </div>
            <div class="tally-list">
              <div class="tally-row" v-for="cand in pos.candidates" :key="cand.candidate_id">
                <div class="tally-info">
                  <p class="tally-name">{{ cand.full_name }}</p>
                  <p class="muted">{{ cand.party || "Independent" }}</p>
                </div>
                <div class="tally-bar">
                  <div class="bar" :style="{ width: votePercent(cand, pos) + '%' }"></div>
                </div>
                <div class="tally-count">
                  <span class="count">{{ cand.votes }}</span>
                  <span class="muted">{{ votePercent(cand, pos) }}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="empty" v-else>
          <p class="muted">No tally data available yet.</p>
        </div>
      </section>

    <footer class="footer">
      <p>Need help? Ensure the API is running at {{ API_BASE }} and CORS is enabled.</p>
    </footer>
  </div>
</template>


