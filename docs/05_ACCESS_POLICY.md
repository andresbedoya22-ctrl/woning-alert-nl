# Access Policy

## Access states

- `allowed`: operationally usable within robots, terms, and rate limits.
- `limited`: usable only with explicit narrow behavior such as lower frequency or fewer fields.
- `permission_required`: not operational until approval or licensing exists.
- `legal_review`: unresolved legal or contractual ambiguity.
- `blocked`: explicit technical or policy stop signal.

## Robots and terms rules

- Robots and explicit terms must be checked before runtime collection work.
- The compliance gate is binding for every networked path.
- If robots or terms disallow the intended path, the source is not operationally allowed.
- Rate limits and crawl-delay are part of policy, not optimization.

## Blocked behavior

Treat the source as `blocked` when any of the following appear:

- CAPTCHA;
- login wall;
- `403`;
- paywall;
- explicit anti-bot or access prohibition;
- source behavior indicating ordinary access is not permitted.

Blocked means stop. It does not mean retry with stronger tooling.

## Permission-required behavior

Use `permission_required` when a source appears technically reachable but the repo should not operationalize it without explicit approval, contract, or license.

## No-bypass policy

- No stealth.
- No residential proxies.
- No IP rotation.
- No fingerprint spoofing.
- No false identity or login replay.
- No CAPTCHA solving.
- No browser automation intended to evade detection.

## Funda

Funda is benchmark, reference, or manual-review material only. It is not part of the operational scraping pipeline.

## Pararius

Pararius is outside the operational pipeline unless explicit permission, license, or review changes that status. By default it is benchmark, manual reference, or permission-track only.

## CAPTCHA, login, and `403`

- CAPTCHA: classify as blocked.
- Login wall: classify as blocked or permission-required.
- `403`: classify as blocked until a compliant explanation proves otherwise.
- Do not push through these signals with automation tricks.
