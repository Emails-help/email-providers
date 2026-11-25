This folder holds one JSON file per provider, named <slug>.json.

Generate or refresh them from the canonical dataset with:

    php artisan dataset:export --split=providers

and the combined consumer file with:

    php artisan dataset:export --path=dist/email-providers.json

See CONTRIBUTING.md to add or correct a provider by hand.
