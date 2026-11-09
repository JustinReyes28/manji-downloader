## Summary

<!-- What changed and why? Keep it focused. -->

## Related issue

<!-- e.g. Closes #123 -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] New or updated site adapter
- [ ] Documentation
- [ ] Refactor or maintenance

## Compliance checklist

- [ ] No anti-bot, Cloudflare, CAPTCHA, fingerprint-spoofing, DRM, paywall, or access-control bypass code.
- [ ] All requests go through the shared HTTP client, per-domain rate limiter, and `robots.txt` checks.
- [ ] Credentials, cookies, signed URLs, and tokens are never logged, exported, or committed.
- [ ] Fixtures, examples, and documentation use synthetic placeholders only.

## Testing

- [ ] Tests added or updated for the change.
- [ ] Zero live network calls in tests; local mock servers and offline fixtures only.
- [ ] Typecheck, lint, and test commands pass (toolchain commands: TBD).

## Documentation

- [ ] Relevant spec updated (`README`, `ARCHITECTURE`, `CONFIGURATION`, `COMPLIANCE`, `TESTING`, or `ROADMAP`).

## DCO sign-off

- [ ] Commits are signed off with `git commit -s`.
