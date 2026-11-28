# Email provider settings

The open, verified dataset of how to connect to the world's email providers — IMAP, POP3 and SMTP — with every value cited to the provider's own documentation and dated.

```
providers/gmail.json, providers/fastmail.json, providers/proton.json, …
```

- **Verified, not scraped.** Every setting is read off the provider's own help page, and that page is recorded next to it.
- **Honest about gaps.** Where a provider publishes a server but never states its encryption, this says so — it does not fill the hole with a plausible guess.
- **Machine- and human-readable.** One JSON file per provider, a combined file for consumers, and a [schema](schema/provider.schema.json) that every entry is checked against in CI.
- **Open.** CC BY 4.0. Use it in an app, a client, a script, a paper.

Maintained alongside **[emails.help](https://emails.help)**.

## Why this exists

Every list of email settings prints a host and a port. None of them tell you which values the provider actually published and which the author worked out.

Spectrum makes the difference concrete. Its support article gives outgoing port 587 with "SSL: On", and never says whether that means STARTTLS or implicit TLS. Every dataset that prints a value there is printing a guess you cannot tell apart from a fact. This one records:

```json
"outgoing": {
  "smtp": {
    "host": "mobile.charter.net",
    "port": 587,
    "security": null,
    "security_documented": false
  }
},
"undocumented": ["smtp_security"]
```

`null` with an entry in `undocumented` is not missing data. It is the answer: **the provider does not state this.**

## How this differs from Thunderbird's ISPDB

[Thunderbird's ISPDB](https://github.com/thunderbird/autoconfig) is the closest thing that exists, and it is excellent at its job — but its job is different. It is autoconfig XML that Thunderbird consumes, it deliberately omits any provider that serves its own autoconfig, and it records a value without recording where the value came from.

This dataset is positioned the other way round: JSON first, every provider (including the ones ISPDB skips), and provenance on every field — the source page and the date it was checked — so the data is **citable**, not just usable. The two are complements. Verified settings here are also [submitted upstream to the ISPDB](https://github.com/thunderbird/autoconfig), so Thunderbird configures those accounts with no website visited at all.

## Use it

Read the combined file directly:

```
dist/email-providers.json
```

Or install the resolver, which ships this data compiled in and falls back to the lookups a mail client performs (autoconfig, ISPDB, MX):

```bash
npm install emails-help
```

```js
import { resolve } from 'emails-help';
const r = await resolve('me@fastmail.com');
r.imap;        // { host, port, security, securityDocumented }
r.method;      // where the answer came from
r.confidence;  // 'documented' | 'undocumented' | 'inferred'
```

## Autoconfig files

Browse the [generated configurations](dist/autoconfig/index.json), or rebuild them offline:

```sh
python3 scripts/build_autoconfig.py
python3 scripts/build_autoconfig.py --check
```

- **Thunderbird / ISPDB:** `dist/autoconfig/thunderbird/<slug>.xml` is an ISPDB-style clientConfig 1.1 file. Domain owners can serve a reviewed file at their autoconfig endpoint, or use it as a starting point for an upstream ISPDB submission. Review the domains, authentication methods and upstream contribution requirements before deploying or submitting it.
- **Apple Mail:** `dist/autoconfig/apple/<slug>.mobileconfig` is an unsigned, single-account configuration profile for interactive installation on iPhone, iPad or Mac. Inspect the server names and profile contents before installation, then follow the operating system's profile installation prompts. An unsigned profile cannot authenticate its author; an unsigned-profile warning is expected. Do not bypass your device's security or management restrictions. Usernames, email addresses and passwords are not embedded.
- **Never guess:** a server needs a documented host, port and supported encryption setting. Providers with unknown username or authentication mappings, no fixed domains, no client access or no usable incoming/outgoing pair are omitted. Apple profiles also omit providers that require OAuth2. Alternative SMTP settings are emitted only when the dataset specifies their security. See [SKIPPED.md](dist/autoconfig/SKIPPED.md) for every omission.

A provider marked `settings_unverified: true` retains historical settings for transparency, but those settings must not be treated as verified or used for automatic configuration. The generator excludes the entire provider. The iCloud Thunderbird configuration uses the IMAP local part and SMTP full address; try the full IMAP address if needed, as Apple documents. Apple profiles leave usernames unset.

These files are generated from the provider dataset, not a live connection or installation test. The build is deterministic; regenerate the files when provider settings change.

## The shape of one provider

```json
{
  "slug": "fastmail",
  "name": "Fastmail",
  "domains": ["fastmail.com"],
  "mx_patterns": ["messagingengine.com"],
  "client_access": true,
  "incoming": { "imap": { "host": "imap.fastmail.com", "port": 993, "security": "ssl", "security_documented": true } },
  "outgoing": { "smtp": { "host": "smtp.fastmail.com", "port": 465, "security": "ssl", "security_documented": true } },
  "undocumented": [],
  "sources": ["https://www.fastmail.help/hc/en-us/articles/1500000278342"],
  "guide": "https://emails.help/fastmail/server-settings",
  "verified": "2026-10-23"
}
```

`security` is one of `ssl`, `starttls`, `none` or `null`. A provider with no IMAP/SMTP at all (Proton, Tuta) has `client_access: false`, and that absence is the answer — a client should stop there, not guess.

`auth_methods` is a required structured field: a non-empty, duplicate-free list of `password`, `app-password` and/or `oauth2`, or `null` when the authentication evidence is unclear, absent or not applicable. The original `authentication` text and cited first-party sources remain the evidence. Autoconfig reads only the structured methods, preferring OAuth2 when available and omitting Apple profiles if OAuth2 is the only method. Unknown methods are never inferred from the prose.

The full field list is in [`schema/provider.schema.json`](schema/provider.schema.json).

## Contributing

Wrong or missing settings are the most useful thing you can send. A provider is one new file; a correction touches one. The rules — first-party sources, cite them, never guess — are in [CONTRIBUTING.md](CONTRIBUTING.md), and CI checks every change against them.

## Licence

CC BY 4.0. Attribute to [emails.help](https://emails.help).
