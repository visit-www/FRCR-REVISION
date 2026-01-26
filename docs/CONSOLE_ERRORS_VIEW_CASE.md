# View-case console errors – explanation

When viewing a case (e.g. `/view-case/25`) on production (`https://www.radinsights.xyz`), you may see these console messages.

## Expected / benign

### Anki (localhost:8765)

- **"[blocked] requested insecure content from http://localhost:8765/"**
- **"Not allowed to request resource"**
- **"Fetch API cannot load http://localhost:8765/ due to access control checks"**

These are expected when:

- The page is served over HTTPS (e.g. radinsights.xyz) and the app tries to reach AnkiConnect at `http://localhost:8765/`, or
- AnkiConnect is not running, or
- The request is cross-origin and the browser blocks it.

No code change is required. To use Anki integration, use the app over HTTP on the same machine where Anki + AnkiConnect run, or via a supported bridge.

### PWA / service worker

- **"Went offline"** / **"Back online"**

Normal service-worker lifecycle messages when the tab loses/regains connectivity. They can be ignored unless you need to debug offline behaviour.

---

## 403 “Failed to load resource”

- **"Failed to load resource: the server responded with a status of 403 () (status, line 0)"**

The console often does not show the request URL. To fix it:

1. Open DevTools → **Network**.
2. Reload the page (or perform the action that triggers the error).
3. Find the request with status **403** and note its URL and initiator.

Typical sources on view-case:

- **`/notes/api/notion/status`** – can 403 if the Notion integration is not allowed for the current user/role or the route requires extra permissions.
- **`/resources/api/sciencedirect/status`** – same idea for ScienceDirect.
- **`/api/case/...`** – may 403 when the user is not allowed to access that case.

After you have the exact URL, adjust that route (or the caller) so that it returns 403 only when intended (e.g. “integration not configured”) and consider returning a JSON body like `{"error": "..."}` instead of a bare 403 when the cause is “not configured” rather than “forbidden”.

---

## Summary

| Message / behaviour              | Likely cause                          | Action                          |
|----------------------------------|---------------------------------------|---------------------------------|
| localhost:8765 blocked / CORS    | AnkiConnect on HTTP / cross-origin    | Expected; use local or bridge   |
| Went offline / Back online       | PWA / network changes                 | Ignore unless debugging         |
| 403 (no URL in console)          | Some API call returns 403             | Use Network tab → fix that route |
