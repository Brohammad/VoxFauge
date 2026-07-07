const API = "/api/v1";
const { Room, RoomEvent, Track, ConnectionState } = LivekitClient;

let token = localStorage.getItem("voxforge_token") || "";
let room = null;
let sessionId = null;

const els = {
  tokenInput: document.getElementById("token-input"),
  identityInput: document.getElementById("identity-input"),
  nameInput: document.getElementById("name-input"),
  connectBtn: document.getElementById("connect-btn"),
  disconnectBtn: document.getElementById("disconnect-btn"),
  errorBanner: document.getElementById("error-banner"),
  statusConnection: document.getElementById("status-connection"),
  statusSession: document.getElementById("status-session"),
  statusRoom: document.getElementById("status-room"),
  statusUrl: document.getElementById("status-url"),
  statusParticipants: document.getElementById("status-participants"),
  statusMic: document.getElementById("status-mic"),
  audioContainer: document.getElementById("audio-container"),
  eventLog: document.getElementById("event-log"),
};

els.tokenInput.value = token;
els.identityInput.value = localStorage.getItem("voxforge_identity") || `user-${crypto.randomUUID().slice(0, 8)}`;

function log(message) {
  const line = `[${new Date().toLocaleTimeString()}] ${message}`;
  els.eventLog.textContent = `${line}\n${els.eventLog.textContent}`.slice(0, 8000);
}

function showError(msg) {
  els.errorBanner.textContent = msg;
  els.errorBanner.classList.remove("hidden");
}

function clearError() {
  els.errorBanner.classList.add("hidden");
}

function setStatus(key, value) {
  if (els[key]) els[key].textContent = value;
}

function updateParticipantCount() {
  if (!room) {
    setStatus("statusParticipants", "0");
    return;
  }
  setStatus("statusParticipants", String(room.remoteParticipants.size + 1));
}

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function attachAudioTrack(track, participantIdentity) {
  const wrap = document.createElement("div");
  wrap.className = "audio-track";
  wrap.dataset.participant = participantIdentity;

  const label = document.createElement("span");
  label.className = "audio-label";
  label.textContent = participantIdentity;

  const audioEl = track.attach();
  audioEl.autoplay = true;

  wrap.appendChild(label);
  wrap.appendChild(audioEl);
  els.audioContainer.appendChild(wrap);
  log(`Subscribed to audio from ${participantIdentity}`);
}

function detachParticipantTracks(participantIdentity) {
  els.audioContainer
    .querySelectorAll(`[data-participant="${participantIdentity}"]`)
    .forEach((el) => el.remove());
}

function wireRoomEvents(activeRoom) {
  activeRoom.on(RoomEvent.ConnectionStateChanged, (state) => {
    setStatus("statusConnection", state);
    log(`Connection state: ${state}`);
  });

  activeRoom.on(RoomEvent.ParticipantConnected, (participant) => {
    log(`Participant joined: ${participant.identity}`);
    updateParticipantCount();
  });

  activeRoom.on(RoomEvent.ParticipantDisconnected, (participant) => {
    detachParticipantTracks(participant.identity);
    log(`Participant left: ${participant.identity}`);
    updateParticipantCount();
  });

  activeRoom.on(RoomEvent.TrackSubscribed, (track, _pub, participant) => {
    if (track.kind === Track.Kind.Audio) {
      attachAudioTrack(track, participant.identity);
    }
  });

  activeRoom.on(RoomEvent.TrackUnsubscribed, (track, _pub, participant) => {
    track.detach().forEach((el) => el.remove());
    detachParticipantTracks(participant.identity);
  });

  activeRoom.on(RoomEvent.Disconnected, (reason) => {
    log(`Disconnected${reason ? `: ${reason}` : ""}`);
    cleanupUi();
  });
}

function cleanupUi() {
  els.connectBtn.disabled = false;
  els.disconnectBtn.disabled = true;
  setStatus("statusMic", "off");
  setStatus("statusConnection", "idle");
  updateParticipantCount();
}

async function connect() {
  clearError();
  token = els.tokenInput.value.trim();
  const identity = els.identityInput.value.trim();
  const name = els.nameInput.value.trim() || identity;

  if (!token) {
    showError("JWT access token is required.");
    return;
  }
  if (!identity) {
    showError("Participant identity is required.");
    return;
  }

  localStorage.setItem("voxforge_token", token);
  localStorage.setItem("voxforge_identity", identity);

  els.connectBtn.disabled = true;
  setStatus("statusConnection", "connecting");
  log("Creating WebRTC session…");

  try {
    const session = await api("/sessions", {
      method: "POST",
      body: JSON.stringify({ transport_type: "webrtc" }),
    });
    sessionId = session.session_id;
    setStatus("statusSession", sessionId);

    log(`Session created: ${sessionId}`);
    log("Requesting LiveKit token…");

    const lk = await api(`/livekit/sessions/${sessionId}/token`, {
      method: "POST",
      body: JSON.stringify({
        participant_identity: identity,
        participant_name: name,
      }),
    });

    setStatus("statusRoom", lk.room_name);
    setStatus("statusUrl", lk.livekit_url);
    log(`Joining room ${lk.room_name}…`);

    room = new Room({ adaptiveStream: true, dynacast: true });
    wireRoomEvents(room);

    await room.connect(lk.livekit_url, lk.token);
    await room.localParticipant.setMicrophoneEnabled(true);

    setStatus("statusMic", "on");
    els.disconnectBtn.disabled = false;
    updateParticipantCount();
    log("Connected — microphone published");
  } catch (err) {
    showError(err.message);
    log(`Error: ${err.message}`);
    await disconnect();
  }
}

async function disconnect() {
  els.disconnectBtn.disabled = true;
  if (room) {
    if (room.state !== ConnectionState.Disconnected) {
      await room.disconnect();
    }
    room = null;
  }
  els.audioContainer.innerHTML = "";
  sessionId = null;
  setStatus("statusSession", "—");
  setStatus("statusRoom", "—");
  setStatus("statusUrl", "—");
  cleanupUi();
  log("Session ended");
}

els.connectBtn.addEventListener("click", connect);
els.disconnectBtn.addEventListener("click", disconnect);
