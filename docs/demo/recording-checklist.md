# Demo Recording Checklist

## Pre-recording

- [ ] Use https://voxforge.brohammad.tech (or local with same UI)
- [ ] Browser: Chrome, 1920×1080, dark mode
- [ ] Close unrelated tabs; hide bookmarks
- [ ] Register dashboard account beforehand
- [ ] Upload 1 sample doc to knowledge base
- [ ] Test demo call once (warm cache)

## Recording setup

- [ ] Screen recorder: OBS, Loom, or QuickTime
- [ ] Microphone: clear audio, no background noise
- [ ] Optional: webcam corner for presenter

## Assets to capture

| Asset | Duration | Output |
|-------|----------|--------|
| 60s showcase | 60s | `demo-showcase-60s.mp4` |
| 8min walkthrough | 8min | `demo-walkthrough-8min.mp4` |
| Demo GIF | 10–15s | `demo.gif` (from screen recording) |
| Landing hero | Screenshot | `landing-hero.png` ✅ |
| Demo results | Screenshot | `demo-results.png` ✅ |
| Dashboard | Screenshot | `dashboard-overview.png` ✅ |

## GIF creation

```bash
# From MP4 (requires ffmpeg)
ffmpeg -i demo-showcase-60s.mp4 -vf "fps=10,scale=800:-1" -loop 0 demo.gif
```

## Post-production

- [ ] Add title card: "VoxForge — Voice AI Infrastructure"
- [ ] Add end card: GitHub URL + live demo URL
- [ ] Upload to `docs/assets/` and link from README
- [ ] Compress for web (< 5MB GIF)

## Presenter notes

See [presenter-notes.md](presenter-notes.md).
