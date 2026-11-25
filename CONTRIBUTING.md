# Contributing a provider

Thank you for improving this. A wrong setting fixed here reaches everyone who uses the dataset, the [resolver package](https://www.npmjs.com/package/emails-help) and, in time, Thunderbird.

The whole value of this dataset is that its values can be trusted. One rule protects that, and it is the rule every contribution is checked against:

> **Every setting comes from the provider's own documentation, and that page is recorded in `sources`. Where the provider does not state something, we say so — we never fill the gap with a plausible value.**

## Adding or fixing a provider

1. Create or edit `providers/<slug>.json`. The filename is the `slug`.
2. Fill it in the shape below. Validate it against [`schema/provider.schema.json`](schema/provider.schema.json).
3. Open a pull request. In the description, say **which page you read the values from** and the date you checked it.

CI validates the file against the schema and the rules below. You can run the same check locally:

```bash
python3 scripts/validate.py
```

## The fields

| Field | What it is |
|---|---|
| `slug` | lowercase identifier, matches the filename |
| `name` | the provider's own name for itself |
| `domains` | the address domains people type (`gmail.com`, `googlemail.com`) |
| `mx_patterns` | MX host suffixes, so a custom domain on this provider resolves |
| `client_access` | `false` if the provider offers no IMAP/SMTP at all |
| `incoming.imap` / `incoming.pop3` | `{ host, port, security, security_documented }` |
| `outgoing.smtp` | the same, plus an optional `alternative` port |
| `undocumented` | field names the provider publishes a server for but never specifies |
| `sources` | the provider's own page(s) each value was read from — **required** |
| `guide` | a human-readable guide, if one exists; otherwise `null` |
| `verified` | the date (YYYY-MM-DD) the values were last checked against `sources` |

`security` is one of `"ssl"`, `"starttls"`, `"none"` or `null`.

## The three things that get a pull request sent back

**A value with no source.** If `sources` does not contain the page the setting came from, it cannot be verified, and an unverifiable setting is exactly what this dataset exists not to be. Marketing pages, forum posts and third-party "how-to"s are not the provider's documentation.

**A guess dressed as a fact.** If the provider publishes a server but does not state its encryption, set `security` to `null` and add the field to `undocumented` — for example `"undocumented": ["smtp_security"]`. Do **not** infer it from the port, from how the server happens to answer, or from what "usually" means. A reader cannot tell a wrong value from a right one; `null` they can.

**A date that is not real.** `verified` is the day you actually opened the source and confirmed the values, not today's date by default. If you did not check it, leave the entry's existing date alone.

## Providers with no client access

Some providers (Proton, Tuta) encrypt mailboxes end to end and offer no IMAP or SMTP. Record that plainly:

```json
{
  "slug": "tuta",
  "name": "Tuta",
  "domains": ["tuta.com", "tutanota.com"],
  "client_access": false,
  "sources": ["https://tuta.com/support"],
  "verified": "2026-10-23"
}
```

The absence of servers is the answer, not an omission.

## How accepted changes flow

The canonical copy of this data is maintained at [emails.help](https://emails.help), where each value is checked against its source. Accepted pull requests are merged here and folded back into that copy, so the two stay in step. You do not need to do anything for that — open the PR against this repository.

## No affiliation

Recording a provider's settings is not a claim to represent them. Entries are independent and say so.
