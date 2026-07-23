# Web app

A Flutter web app that displays live sensor readings alongside an outdoor
forecast pulled from [Open-Meteo](https://open-meteo.com).

## Setup

1. Edit `apiUrl` near the top of `lib/main.dart` to point at your FastAPI
   server:

```dart
const apiUrl = 'http://<your-server-ip>:8000';
```

2. Update `lat` / `lon` to your location if you want accurate outdoor
   forecast data.

3. Build for web:

```bash
flutter pub get
flutter build web
```

This outputs static files to `build/web/`.

## Running as a service (recommended for permanent hosting)

1. Copy `weatherweb.service` to `/etc/systemd/system/`, editing the
   `WorkingDirectory` and `User` fields to match your system.

```bash
sudo cp weatherweb.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weatherweb
sudo systemctl start weatherweb
```

2. Visit `http://<your-server-ip>:8080` in a browser.

## Notes

- This serves the built static files with Python's built-in HTTP server —
  fine for a home network, not intended for public internet exposure.
- If you see a `NetworkError` in the browser, it's almost always CORS (fixed
  server-side, see `api/readme.md`) or the API service simply not running.
