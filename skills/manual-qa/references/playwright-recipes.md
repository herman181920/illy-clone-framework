# Playwright MCP recipes for manual QA

Copy-paste these into `mcp__plugin_playwright_playwright__browser_evaluate`. All examples use plain JS (the evaluator rejects TypeScript annotations and `as X` casts).

Replace the `app:` localStorage namespace and the `app` IndexedDB database name with whatever your cloned app uses. Inspect DevTools → Application → Storage on the live clone to see the exact strings.

## State inspection

### Read current project from localStorage

```js
() => {
  const raw = localStorage.getItem('app:project-index');
  const index = raw ? JSON.parse(raw) : [];
  const latest = index.sort((a, b) => b.updatedAt - a.updatedAt)[0];
  if (!latest) return { error: 'no project' };
  const proj = JSON.parse(localStorage.getItem('app:project:' + latest.id) || '{}');
  return {
    assetCount: proj.assets?.length,
    clipCount: proj.clips?.length,
    textCount: proj.texts?.length,
    duration: proj.duration,
  };
}
```

### Inspect IndexedDB asset count

```js
() => new Promise((resolve) => {
  const req = indexedDB.open('app', 1);
  req.onsuccess = () => {
    const db = req.result;
    const tx = db.transaction('assets', 'readonly');
    const count = tx.objectStore('assets').count();
    count.onsuccess = () => resolve({ assetsInIdb: count.result });
    count.onerror = () => resolve({ error: count.error?.message });
  };
  req.onerror = () => resolve({ error: req.error?.message });
})
```

### Read the timecode shown in the preview bar

```js
() => {
  const el = Array.from(document.querySelectorAll('div'))
    .find(d => /^\d\d:\d\d\.\d \/ \d\d:\d\d\.\d$/.test((d.textContent || '').trim()));
  return { timecode: el ? el.textContent.trim() : null };
}
```

### Inspect the preview <video> element

```js
() => {
  const vids = Array.from(document.querySelectorAll('video'));
  const main = vids.find(v => v.clientWidth > 100) || vids[0];
  return {
    vidCount: vids.length,
    currentTime: main?.currentTime ?? null,
    paused: main?.paused ?? null,
    muted: main?.muted ?? null,
    readyState: main?.readyState ?? null,
  };
}
```

## Synthetic interactions (when ref-based click is fragile)

### Click a button by visible text

```js
() => {
  const btns = Array.from(document.querySelectorAll('button'));
  const b = btns.find(x => (x.textContent || '').trim() === '+ Text overlay');
  if (b) b.click();
  return { clicked: !!b };
}
```

### Click the timeline ruler at N seconds

```js
() => {
  const rulers = Array.from(document.querySelectorAll('div'))
    .filter(el => /\bcursor-pointer\b/.test(el.className || ''));
  const ruler = rulers.find(el => /0s.*1s.*2s/s.test(el.textContent || ''));
  if (!ruler) return { error: 'ruler not found' };
  const rect = ruler.getBoundingClientRect();
  const pxPerSec = 50; // matches default zoom=50
  const seconds = 2.5;
  const ev = new MouseEvent('click', {
    bubbles: true,
    cancelable: true,
    clientX: rect.left + seconds * pxPerSec,
    clientY: rect.top + 10,
  });
  ruler.dispatchEvent(ev);
  return { clicked: true, seconds };
}
```

### Click a timeline clip by asset name

```js
() => {
  const els = Array.from(document.querySelectorAll('div'))
    .filter(d =>
      (d.textContent || '').includes('test-5s.mp4') &&
      d.getAttribute('style')?.includes('position: absolute')
    );
  const target = els[0];
  if (target) target.click();
  return { clicked: !!target };
}
```

## Verifying toasts

Toasts auto-dismiss after ~3.5 seconds. Capture immediately:

```js
() => {
  const btns = Array.from(document.querySelectorAll('button'));
  const toasts = btns.filter(b =>
    /Render|AI|Requesting|stub|Select a clip/i.test(b.textContent || '')
  );
  return { visible: toasts.map(t => (t.textContent || '').slice(0, 120)) };
}
```

Or: read the `ToastHost` container directly:

```js
() => {
  const host = document.querySelector('.fixed.bottom-4.right-4');
  if (!host) return { toasts: [] };
  return { toasts: Array.from(host.querySelectorAll('button')).map(b => b.textContent) };
}
```

## Verifying API calls

Use the dedicated network tool (not evaluate):

```
mcp__plugin_playwright_playwright__browser_network_requests
  static: false
  requestBody: false
  requestHeaders: false
  filter: "/api/"
```

Expected shape after clicking a stubbed AI button and Export:
```
[POST] http://localhost:3000/api/ai/transcribe => [200] OK
[POST] http://localhost:3000/api/render => [200] OK
```

## Reset between tests

If a test run left state behind:

```js
() => {
  Object.keys(localStorage)
    .filter(k => k.startsWith('app:'))
    .forEach(k => localStorage.removeItem(k));
  return new Promise((resolve) => {
    const req = indexedDB.deleteDatabase('app');
    req.onsuccess = () => resolve({ reset: true });
    req.onerror = () => resolve({ reset: false, error: req.error?.message });
    req.onblocked = () => resolve({ reset: false, reason: 'blocked (close open tabs)' });
  });
}
```

Then `browser_navigate` to reload. The editor will show a fresh "Untitled project".
