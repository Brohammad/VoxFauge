# LiveKit WebRTC Transport

VoxForge supports WebRTC voice sessions via [LiveKit](https://livekit.io/) alongside the existing WebSocket transport.

## Flow

1. Create a session with `transport_type: "webrtc"`.
2. Request a participant token: `POST /api/v1/livekit/sessions/{session_id}/token`.
3. Connect the client SDK to the returned `livekit_url` with the JWT `token`.
4. Audio flows through LiveKit; the VoxForge agent pipeline processes turns server-side.

## Configuration

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
LIVEKIT_AGENT_NAME=voxforge-voice
LIVEKIT_DISPATCH_ENABLED=true
LIVEKIT_RECONNECT_GRACE_SECONDS=30
```

Install the optional dependency:

```bash
pip install -e ".[livekit]"
```

Run the agent worker (separate process from the API):

```bash
make livekit-worker
```

The worker bridges room audio into `VoicePipelineService` — see
[livekit-integration.md](./livekit-integration.md) for the full architecture.

## API

### Create WebRTC session

```http
POST /api/v1/sessions
{
  "transport_type": "webrtc"
}
```

Response includes `livekit_url` when configured.

### Get participant token

```http
POST /api/v1/livekit/sessions/{session_id}/token
{
  "participant_identity": "user-123",
  "participant_name": "Alice"
}
```

Returns `token`, `room_name`, and `livekit_url`. When dispatch is enabled, the API also
requests a LiveKit agent job for the room (failures are logged; token issuance still succeeds).

Rooms are named `voxforge-{session_id}` with publish/subscribe grants for the participant.

## Browser example

Open http://localhost:8000/examples/livekit for a ready-made client that:

1. Creates a WebRTC session
2. Fetches a LiveKit token
3. Connects with the LiveKit JS SDK and publishes the microphone

Source: `examples/livekit-client/`. See `examples/livekit-client/README.md` for setup.
