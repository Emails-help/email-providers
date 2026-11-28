"""Generate offline mail client configurations from documented provider settings."""
import json
import plistlib
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, 'emails.help')
USERNAME = dict.fromkeys((
    'Your full email address', 'Your full cox.net email address',
    'Your full Spectrum-provided email address', 'Your full Comcast.net email address',
    'Your full address, including @verizon.net', 'Your full email address (memberid@juno.com)',
), '%EMAILADDRESS%')
USERNAME['The part of your address before the @'] = '%EMAILLOCALPART%'
AUTH_METHODS = frozenset(('password', 'app-password', 'oauth2'))
PASSWORD_METHODS = frozenset(('password', 'app-password'))
SOCKET = {'ssl': 'SSL', 'starttls': 'STARTTLS'}
ACCOUNT = {'imap': 'EmailTypeIMAP', 'pop3': 'EmailTypePOP'}


def thunderbird_auth(methods):
    """Return supported XML methods in preference order, or None for a gap."""
    if (not isinstance(methods, list) or not methods
            or any(not isinstance(m, str) or m not in AUTH_METHODS for m in methods)
            or len(set(methods)) != len(methods)):
        return None
    return tuple(method for method, enabled in (
        ('OAuth2', 'oauth2' in methods),
        ('password-cleartext', bool(PASSWORD_METHODS.intersection(methods))),
    ) if enabled)


def server_errors(server):
    errors = []
    if not isinstance(server.get('host'), str) or not server['host'].strip():
        errors.append('host missing')
    if type(server.get('port')) is not int or not 1 <= server['port'] <= 65535:
        errors.append('port missing or invalid')
    if server.get('security_documented') is not True:
        errors.append('security undocumented')
    if server.get('security') not in SOCKET:
        errors.append(f"security {server.get('security')!r} unsupported")
    return errors


def element(parent, tag, value):
    ET.SubElement(parent, tag).text = str(value)


def thunderbird(p, version, incoming, outgoing, username, auth):
    root = ET.Element('clientConfig', version='1.1')
    root.append(ET.Comment(f' Emails.help dataset version {version} '))
    provider = ET.SubElement(root, 'emailProvider', id=p['domains'][0])
    for domain in p['domains']:
        element(provider, 'domain', domain)
    element(provider, 'displayName', p['name'])
    element(provider, 'displayShortName', p['name'])
    for tag, servers in (('incomingServer', incoming), ('outgoingServer', outgoing)):
        for protocol, server in servers:
            node = ET.SubElement(provider, tag, type=protocol)
            for key, value in (('hostname', server['host']), ('port', server['port']),
                               ('socketType', SOCKET[server['security']]), ('username', username)):
                element(node, key, value)
            for method in auth:
                element(node, 'authentication', method)
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'


def apple(p, version, incoming, outgoing):
    protocol, server = incoming[0]
    smtp = outgoing[0][1]
    slug = p['slug']
    def metadata(kind, suffix):
        return {'PayloadType': kind, 'PayloadVersion': 1,
                'PayloadIdentifier': f'help.emails.{slug}.{suffix}',
                'PayloadUUID': str(uuid.uuid5(NAMESPACE, f'{slug}:{suffix}'))}
    mail = metadata('com.apple.mail.managed', protocol)
    mail.update(EmailAccountType=ACCOUNT[protocol], EmailAccountDescription=p['name'],
                OutgoingPasswordSameAsIncomingPassword=True)
    for prefix, settings in (('Incoming', server), ('Outgoing', smtp)):
        mail.update({prefix+'MailServerHostName': settings['host'],
                     prefix+'MailServerPortNumber': settings['port'],
                     prefix+'MailServerUseSSL': True,
                     prefix+'MailServerAuthentication': 'EmailAuthPassword'})
    profile = metadata('Configuration', 'profile')
    profile.update(PayloadContent=[mail], PayloadDisplayName=p['name'],
                   PayloadDescription=f'Emails.help dataset version {version}')
    return plistlib.dumps(profile, sort_keys=True)


def generate(providers, version):
    files, index = {}, {}
    skipped = ['# Skipped configurations', '', f'Dataset version: {version}', '']
    for p in sorted(providers, key=lambda row: row['slug']):
        slug = p['slug']
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or slug in index:
            raise ValueError(f'Invalid or duplicate slug: {slug}')
        index[slug] = []
        reasons = []
        if p.get('client_access') is not True:
            reasons.append('client_access is not true')
        if not p.get('domains'):
            reasons.append('no fixed domains')
        username = USERNAME.get(p.get('username'))
        if username is None:
            reasons.append('username is missing or not in the exact mapping')
        methods = p.get('auth_methods')
        auth = thunderbird_auth(methods)
        if auth is None:
            reasons.append('auth_methods is missing, null or invalid')
        incoming, outgoing = [], []
        for protocol, target in (('imap', incoming), ('pop3', incoming), ('smtp', outgoing)):
            server = p.get('outgoing' if protocol == 'smtp' else 'incoming', {}).get(protocol)
            if server is None:
                continue
            errors = server_errors(server)
            if not errors:
                target.append((protocol, server))
            else:
                skipped.append(f'- `{slug}` {protocol}: ' + '; '.join(errors) + '.')
            if protocol == 'smtp' and 'alternative' in server:
                alt = server['alternative']
                # The provider schema uses null for undocumented alternative security.
                alternative = dict(host=server.get('host'), port=alt.get('port'),
                                   security=alt.get('security'), security_documented=alt.get('security') in SOCKET)
                errors = server_errors(alternative)
                if not errors:
                    outgoing.append(('smtp', alternative))
                else:
                    skipped.append(f'- `{slug}` smtp alternative: ' + '; '.join(errors) + '.')
        if not incoming:
            reasons.append('no eligible incoming server')
        if not outgoing:
            reasons.append('no eligible outgoing server')
        if reasons:
            skipped.append(f'- `{slug}`: ' + '; '.join(reasons) + '.')
            continue
        path = f'thunderbird/{slug}.xml'
        files[path] = thunderbird(p, version, incoming, outgoing, username, auth)
        index[slug].append(path)
        if not PASSWORD_METHODS.intersection(methods):
            skipped.append(f'- `{slug}` Apple: Apple payload has no OAuth authentication value.')
        else:
            path = f'apple/{slug}.mobileconfig'
            files[path] = apple(p, version, incoming, outgoing)
            index[slug].append(path)
    files['SKIPPED.md'] = ('\n'.join(skipped) + '\n').encode()
    files['index.json'] = (json.dumps(index, indent=2, sort_keys=True) + '\n').encode()
    return files


def build(root=ROOT, check=False):
    version = json.loads((root/'dist/email-providers.json').read_text(encoding='utf-8'))['version']
    providers = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((root/'providers').glob('*.json'))]
    if not providers:
        raise ValueError('No provider files found')
    files = generate(providers, version)
    output = root/'dist/autoconfig'
    if check:
        actual = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob('*') if p.is_file()}
        if files != actual:
            raise ValueError('Generated autoconfig files are stale; rebuild first')
        return files
    for relative, content in files.items():
        path = output/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for path in output.rglob('*'):
        if path.is_file() and path.relative_to(output).as_posix() not in files:
            path.unlink()
    return files


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if generated files differ')
    result = build(check=parser.parse_args().check)
    print(f'Generated {len(result)} files: {sum(p.endswith(".xml") for p in result)} Thunderbird, '
          f'{sum(p.endswith(".mobileconfig") for p in result)} Apple, plus index and skip report.')
