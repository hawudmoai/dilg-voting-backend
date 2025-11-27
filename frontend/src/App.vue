<script setup>
import { computed, onMounted, ref } from "vue";

// Adjust this if your backend runs elsewhere
const API_BASE = "http://localhost:8000/api";

const voterId = ref("");
const pin = ref("");
const token = ref(localStorage.getItem("sessionToken") || "");
const voter = ref(null);

const positions = ref([]);
const candidates = ref([]);
const selectedPosition = ref("");
const selectedCandidate = ref("");

const tally = ref([]);

const loading = ref(false);
const loginLoading = ref(false);
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

const setStatus = (message, type = "info") => {
  statusMessage.value = message;
  statusType.value = type;
};

const request = async (path, { method = "GET", body, auth = false } = {}) => {
  const headers = { "Content-Type": "application/json" };
  if (auth && token.value) {
    headers["X-Session-Token"] = token.value;
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

const init = async () => {
  loading.value = true;
  try {
    await Promise.all([loadPositions(), loadCandidates()]);
    await checkSession();
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
    <header class="hero">
      <div>
        <p class="eyebrow">DILG Voting System</p>
        <h1>Vote, verify, and view tallies in one place.</h1>
        <p class="subhead">
          Log in with your Voter ID and PIN, cast your votes, and see live results.
        </p>
      </div>
      <div class="badge">Frontend · Vue</div>
    </header>

    <section class="status" v-if="statusMessage">
      <div class="pill" :data-type="statusType">{{ statusMessage }}</div>
    </section>

    <section class="grid">
      <article class="card">
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
              placeholder="••••"
            />
          </label>

          <button type="submit" :disabled="loginLoading">
            {{ loginLoading ? "Signing in..." : "Log In" }}
          </button>
        </form>
      </article>

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
                {{ pos.name }} <span v-if="pos.level">({{ pos.level }})</span>
              </option>
            </select>
          </label>

          <label class="field">
            <span>Candidate</span>
            <select v-model="selectedCandidate">
              <option value="">Select a candidate</option>
              <option v-for="cand in filteredCandidates" :key="cand.id" :value="cand.id">
                {{ cand.full_name }} — {{ cand.party || "Independent" }}
              </option>
            </select>
          </label>

          <button type="button" :disabled="voteLoading" @click="castVote">
            {{ voteLoading ? "Submitting..." : "Submit Vote" }}
          </button>
        </div>

        <p class="note" v-if="!voter">
          Log in first to enable voting.
        </p>
      </article>
    </section>

    <section class="card">
      <div class="card-header">
        <div>
          <p class="eyebrow">Candidates</p>
          <h2>Browse candidates</h2>
        </div>
        <button class="ghost" type="button" @click="() => { loadCandidates(); setStatus('Candidates refreshed.', 'info'); }">
          Refresh
        </button>
      </div>

      <div class="candidate-grid">
        <div class="candidate" v-for="cand in filteredCandidates" :key="cand.id">
          <div class="row">
            <h3>{{ cand.full_name }}</h3>
            <span class="tag">{{ cand.party || "Independent" }}</span>
          </div>
          <p class="muted">{{ cand.position_name || "Position" }}</p>
          <p class="bio" v-if="cand.bio">{{ cand.bio }}</p>
        </div>
      </div>
    </section>

    <section class="card">
      <div class="card-header">
        <div>
          <p class="eyebrow">Results</p>
          <h2>Live tally</h2>
        </div>
        <button class="ghost" type="button" :disabled="tallyLoading" @click="loadTally">
          {{ tallyLoading ? "Refreshing..." : "Refresh" }}
        </button>
      </div>

      <div class="tally">
        <div class="tally-block" v-for="pos in tally" :key="pos.position_id">
          <div class="row">
            <h3>{{ pos.position }}</h3>
            <span class="tag">{{ pos.level }}</span>
          </div>
          <div class="tally-table">
            <div class="tally-row header">
              <span>Candidate</span>
              <span>Votes</span>
            </div>
            <div class="tally-row" v-for="cand in pos.candidates" :key="cand.candidate_id">
              <span>{{ cand.full_name }} <small class="muted">({{ cand.party || "Independent" }})</small></span>
              <span class="count">{{ cand.votes }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <footer class="footer">
      <p>Need help? Ensure the API is running at {{ API_BASE }} and CORS is enabled.</p>
    </footer>
  </div>
</template>
