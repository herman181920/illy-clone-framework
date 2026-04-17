# NextAuth Subdomain Auth Topology

The specific SaaS auth pattern you'll hit on targets that run their web app on a subdomain separate from their marketing site. Recognizing it in the first minute saves an hour of confused cookie debugging.

Cross-reference: `skills/import-browser-cookies/SKILL.md`, `scripts/import_browser_cookies.py`.

---

## 1. Topology diagram

```
                 ┌─────────────────────────────┐
                 │  target.com                 │
                 │  (marketing site)           │
                 │                             │
                 │  "Login" button             │
                 └──────────┬──────────────────┘
                            │ redirect
                            ▼
                 ┌─────────────────────────────┐
                 │  auth.provider.app          │
                 │  (OAuth broker)             │
                 │  WorkOS AuthKit / Clerk /   │
                 │  Auth0 / Mirage             │
                 │                             │
                 │  ?client_id=client_01...    │
                 │  &callbackUrl=https://...   │
                 └──────────┬──────────────────┘
                            │ callback + set-cookie on app subdomain
                            ▼
                 ┌─────────────────────────────┐
                 │  app.target.com             │
                 │  (the actual web app)       │
                 │                             │
                 │  NextAuth session cookie    │
                 │  __Secure-next-auth         │
                 │  .session-token             │
                 │  (scoped to app.target.com) │
                 └─────────────────────────────┘
```

The marketing login sets cookies on `auth.provider.app` and maybe `target.com`. It does NOT set the app session cookie. The web app issues its own cookie on its own subdomain after the OAuth callback lands there.

---

## 2. Telltale signs — recognize in seconds

Check the login redirect URL and the cookie jar. These patterns identify the topology immediately:

**In the login redirect URL:**
- `client_id=client_01...` — WorkOS AuthKit client ID prefix
- `callbackUrl=https://app.target.com/...` — shows where the session will land
- `auth.` or `id.` subdomain handling the login page (not the app subdomain)
- `redirect_uri` pointing at the app subdomain

**In the cookie jar (Chrome DevTools or `import_browser_cookies.py --list`):**
- `__Secure-next-auth.session-token` on `app.target.com` — this is the one that grants access
- `studio_login_credentials` or `app_login_credentials` JWT on `target.com` — marketing-domain session, does NOT grant app access
- `_mirage_session` or `_workos_session` on `auth.provider.app` — broker session, does NOT grant app access
- Absence of `__Secure-next-auth.session-token` on the app subdomain = you are not authenticated to the app

**Quick check command:**
```bash
python3 scripts/import_browser_cookies.py --browser chrome --profile "Default" \
  --domain target.com --out /tmp/debug-cookies.json && \
  python3 -c "
import json
cookies = json.load(open('/tmp/debug-cookies.json'))
for c in cookies:
    if 'session' in c['name'].lower() or 'auth' in c['name'].lower():
        print(c['domain'], c['name'])
"
```

If `app.target.com` does not appear in output with a session-token cookie, the user has not authenticated the web app specifically.

---

## 3. The trap

**"I'm already logged in" does not mean logged into the app.**

Users often log into the marketing site (`target.com`) or the desktop app, never having opened `app.target.com` in a browser. The marketing login:
- Creates a cookie on `target.com` (marketing-domain JWT — looks real, is real for marketing, but not the app).
- Possibly creates a session on the auth broker subdomain.
- Does NOT hit `app.target.com` at all if the user just clicked a marketing CTA and wasn't redirected to the web app.

Result: you extract cookies from Chrome, load them into Playwright, navigate to `app.target.com`, and land on the login page. The cookies look correct in the JSON file. Nothing is wrong with the extraction. The issue is that the right cookie was never created.

**Another variant:** user uses the iOS or desktop app exclusively. The native app authenticates through a different OAuth flow (PKCE + local redirect) and never touches the browser cookie store at all. Zero browser cookies for the app.

---

## 4. The fix flow

1. **Confirm the problem.** Check the cookie JSON for `__Secure-next-auth.session-token` on the exact app subdomain. If absent, proceed.
2. **Ask the user to open `app.target.com` in their real Chrome browser and log in.** They may need to explicitly go to the web app URL — the marketing login does not count.
3. **Wait for them to confirm they see the authenticated dashboard in Chrome.**
4. **Re-run the import script** with the app's domain included:
   ```bash
   python3 scripts/import_browser_cookies.py \
     --browser chrome --profile "Default" \
     --domain target.com \
     --out clones/target.com/cookies.json
   ```
   Suffix matching means `--domain target.com` captures `app.target.com`, `auth.target.com`, and `target.com` itself.
5. **Verify the key cookie is now present:**
   ```bash
   python3 -c "
   import json
   cookies = json.load(open('clones/target.com/cookies.json'))
   found = [c for c in cookies if '__Secure-next-auth' in c['name']]
   for c in found:
       print(c['domain'], c['name'], 'expires:', c['expires'])
   "
   ```
6. **Load into Playwright and navigate to the app.** If still redirected to login: check the profile (user may be signed into the target site from a non-default Chrome profile). Run `--list` to see all profiles and ask which one has the session.

---

## 5. Auth provider variants

Different providers use different cookie names. Use this table to identify the provider from cookie inspection.

| Provider | Auth subdomain pattern | App session cookie | Marketing/broker cookie | Notes |
|---|---|---|---|---|
| **NextAuth (generic)** | varies | `next-auth.session-token` or `__Secure-next-auth.session-token` | none (NextAuth is app-side only) | `__Secure-` prefix appears when app is served over HTTPS |
| **WorkOS AuthKit** | `auth.{company}.app` or `id.{company}.com` | app sets its own session after callback (often NextAuth on top of WorkOS) | `client_id=client_01...` in redirect URL is the fingerprint | WorkOS handles the OAuth; NextAuth or custom session handler issues the app cookie |
| **Clerk** | `clerk.{domain}` or `accounts.{domain}` | `__session` or `__clerk_db_jwt` on app domain | `__client_uat` on parent domain | Clerk dev instances use `clerk.{app}.lcl.dev`. Production: custom domain. |
| **Auth0** | `{tenant}.auth0.com` | `appSession` or custom name (configurable) | `auth0` cookie on `auth0.com` | App uses `nextjs-auth0` library; cookie name is configurable in `AUTH0_SECRET` session config. |
| **Supabase Auth** | `{project}.supabase.co` or self-hosted | `sb-{project-ref}-auth-token` | — | Supabase sets cookie directly on app domain; no separate broker domain unless custom. |
| **Firebase Auth** | `securetoken.googleapis.com` | not a cookie — ID token in `localStorage` | — | No cookie to import. Need to inject `localStorage` token instead. |

---

## 6. Keychain command — works vs fails

When `import_browser_cookies.py` calls the macOS Keychain to get the AES key, it uses:

```bash
# WORKS — service name as -s, password-only output flag -w
security find-generic-password -s "Chrome Safe Storage" -w

# FAILS with "security: SecKeychainSearchCopyNext: The specified item could not be found in the keychain."
# -wa is parsed as -w -a (account match), not the service name
security find-generic-password -wa "Chrome Safe Storage"
```

The `-a` flag in `security` means "match by account name", not service. Passing the service name to `-a` returns item-not-found because no account is named "Chrome Safe Storage". The script uses `-s SERVICE -w` which is correct.

If you see "item not found" from the Keychain and you're sure the browser is Chrome: check whether the Keychain Access popup was denied. User needs to open Keychain Access.app, find "Chrome Safe Storage", go to Access Control tab, and add Terminal (or iTerm).

---

## 7. Quick-reference checklist

Run this list when hitting a "not authenticated" wall:

- [ ] **Right domain?** Confirm the app URL (check the browser address bar when the user is logged in). It is often different from the marketing URL.
- [ ] **Right profile?** Run `python3 scripts/import_browser_cookies.py --browser chrome --list`. Ask the user which Chrome profile has the active web app session.
- [ ] **Session cookie present?** After extraction, search the JSON for `__Secure-next-auth.session-token` (or the provider-specific name from section 5). If absent, user needs to log in at the specific app URL in Chrome.
- [ ] **Cookie not expired?** Check the `expires` field is greater than current Unix timestamp. If expired, user needs to re-login and re-extract.
- [ ] **Correct `--domain` filter?** `--domain target.com` captures all subdomains via suffix match. If you used `--domain app.target.com`, you missed cookies on `target.com`. Usually set the root domain and let suffix matching handle the rest.
- [ ] **Cookie loaded into Playwright context?** Verify `context.add_cookies()` returned without error. Navigate to the app URL in the Playwright session and take a screenshot — confirm you see the authenticated state, not the login page.
- [ ] **Keychain allowed?** On first run, macOS shows a Keychain dialog. User must click "Always Allow" (not "Allow" — "Allow" requires re-approval every run). If they clicked "Deny": Keychain Access.app → login keychain → search "Chrome Safe Storage" → Access Control tab → remove Terminal, then re-run.

---

## 8. What each provider's login redirect looks like

Use the redirect URL when "Login" is clicked on the marketing site to instantly identify the auth provider.

**WorkOS AuthKit:**
```
https://auth.{company}.app/user/login?
  client_id=client_01...
  &redirect_uri=https://app.{company}.com/api/auth/callback/workos
  &response_type=code
  &state=...
  &callbackUrl=https://app.{company}.com/projects
```
Fingerprint: `client_id=client_01`, `auth.{company}.app` subdomain, `callback/workos` in redirect URI.

**Clerk:**
```
https://accounts.{company}.com/sign-in?
  redirect_url=https://app.{company}.com/...
  &after_sign_in_url=...
```
Or in dev: `https://clerk.{app-name}.lcl.dev`. Fingerprint: `accounts.` subdomain or `lcl.dev`. Cookie set: `__session`, `__client_uat`.

**Auth0:**
```
https://{tenant}.auth0.com/authorize?
  client_id=...
  &redirect_uri=https://app.{company}.com/api/auth/callback/auth0
  &response_type=code
  &scope=openid+profile+email
```
Fingerprint: `auth0.com` in the redirect URL. App-side cookie depends on `nextjs-auth0` config — default is `appSession`.

**Supabase Auth:**
No separate auth subdomain. Redirect stays on the app domain:
```
https://app.{company}.com/auth/callback?code=...&next=/dashboard
```
Cookie: `sb-{project-ref}-auth-token` (a JSON string, base64-encoded). Sometimes split into `-0` and `-1` chunks if too large for a single cookie.

**Self-hosted NextAuth (no external provider):**
Credentials or magic link. Cookie set directly by the Next.js app:
- `next-auth.session-token` (HTTP, dev)
- `__Secure-next-auth.session-token` (HTTPS, production)
- `__Host-next-auth.csrf-token` (CSRF token, also scoped to the app)

---

## 9. Cross-references

- **`scripts/import_browser_cookies.py`** — the extraction tool. Run with `--list` first to see profiles. Use `--domain` for suffix-match filtering.
- **`skills/import-browser-cookies/SKILL.md`** — full 5-step workflow including Playwright MCP loading and token rotation after use.
- **CLAUDE.md "Cookie-subdomain pitfall" rule** — the policy statement this doc elaborates on.
