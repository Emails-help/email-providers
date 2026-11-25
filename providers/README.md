This folder holds one JSON file per provider, named <slug>.json.

The canonical source is the [Emails.help dataset](https://emails.help/api/email-providers.json).
In the Laravel project, `php artisan dataset:export --path=/path/to/email-providers.json`
exports the combined source. To refresh this repo, copy each entry from the
export's `providers` array to its matching file here.

After editing these files, rebuild and validate the combined consumer file:

    python3 scripts/validate.py --rebuild

See CONTRIBUTING.md to add or correct a provider by hand.
