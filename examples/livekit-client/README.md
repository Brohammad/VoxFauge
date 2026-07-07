# LiveKit WebRTC Client Example

Browser demo for VoxForge WebRTC voice sessions using the [LiveKit JavaScript SDK](https://docs.livekit.io/client-sdk-js/).

## Prerequisites

1. VoxForge API running (`docker compose up -d`)
2. LiveKit Cloud project (or self-hosted LiveKit server)
3. JWT access token from `POST /api/v1/auth/login`

Set in `.env`:

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

## Usage

Open http://localhost:8000/examples/livekit

1. Paste your JWT access token
2. Set participant identity (defaults to a random `user-*` id)
3. Click **Start WebRTC Session**

The client will:

- Create a `webrtc` transport session via the VoxForge API
- Fetch a LiveKit participant token
- Connect to the room and publish your microphone
- Play audio from remote participants (e.g. a future VoxForge agent worker)

## Flow

```
Browser                    VoxForge API              LiveKit
   | POST /sessions/webrtc      |                        |
   |--------------------------->|                        |
   | POST /livekit/.../token    |                        |
   |--------------------------->|                        |
   | connect(url, token)        |                        |
   |----------------------------------------------------->|
   | publish mic track          |                        |
   |----------------------------------------------------->|
```

## Notes

- Token generation is implemented server-side; a LiveKit **agent worker** that bridges room audio into the VoxForge voice pipeline is the next integration step.
- For WebSocket voice (fully wired today), use `/api/v1/ws/voice` instead.
