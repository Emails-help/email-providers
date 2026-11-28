import copy
import json
import plistlib
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from scripts.build_autoconfig import generate, build, ROOT, USERNAME, AUTH, SOCKET


class AutoconfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.providers = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'providers').glob('*.json'))]
        cls.by_slug = {p['slug']: p for p in cls.providers}
        cls.version = json.loads((ROOT/'dist/email-providers.json').read_text(encoding='utf-8'))['version']
        cls.files = generate(cls.providers, cls.version)

    def xml(self, slug):
        return ET.fromstring(self.files[f'thunderbird/{slug}.xml'])

    def profile(self, slug):
        return plistlib.loads(self.files[f'apple/{slug}.mobileconfig'])

    def test_reproducible_and_current(self):
        self.assertEqual(self.files, generate(list(reversed(self.providers)), self.version))
        self.assertEqual(self.files, build(check=True))

    def test_aol_golden(self):
        self.assertEqual(self.xml('aol').findtext('emailProvider/domain'), 'aol.com')
        servers = self.xml('aol').findall('.//incomingServer') + self.xml('aol').findall('.//outgoingServer')
        self.assertEqual([(s.get('type'), s.findtext('hostname'), s.findtext('port'), s.findtext('socketType'), s.findtext('username'), s.findtext('authentication')) for s in servers], [
            ('imap','imap.aol.com','993','SSL','%EMAILADDRESS%','password-cleartext'),
            ('pop3','pop.aol.com','995','SSL','%EMAILADDRESS%','password-cleartext'),
            ('smtp','smtp.aol.com','465','SSL','%EMAILADDRESS%','password-cleartext')])
        m = self.profile('aol')['PayloadContent'][0]
        self.assertEqual((m['EmailAccountType'],m['IncomingMailServerHostName'],m['IncomingMailServerPortNumber'],m['OutgoingMailServerHostName'],m['OutgoingMailServerPortNumber']), ('EmailTypeIMAP','imap.aol.com',993,'smtp.aol.com',465))

    def test_gmail_golden(self):
        s = self.xml('gmail').find('.//outgoingServer')
        self.assertEqual((s.findtext('hostname'), s.findtext('port'), s.findtext('socketType')), ('smtp.gmail.com','587','STARTTLS'))
        self.assertEqual([a.text for a in s.findall('authentication')], ['OAuth2','password-cleartext'])
        self.assertEqual(self.profile('gmail')['PayloadContent'][0]['OutgoingMailServerPortNumber'], 587)

    def test_spectrum_golden(self):
        for slug in ('spectrum-charter','spectrum-brighthouse','spectrum-twc'):
            self.assertNotIn(f'thunderbird/{slug}.xml', self.files)
            self.assertNotIn(f'apple/{slug}.mobileconfig', self.files)
            self.assertIn(f'`{slug}` smtp: security undocumented', self.files['SKIPPED.md'].decode())

    def test_oauth_only_and_pop_fallback(self):
        self.assertNotIn('apple/outlook.mobileconfig', self.files)
        self.assertEqual([a.text for a in self.xml('outlook').findall('.//outgoingServer/authentication')], ['OAuth2'])
        self.assertEqual(self.profile('frontier')['PayloadContent'][0]['EmailAccountType'], 'EmailTypePOP')

    def test_alternatives(self):
        self.assertEqual([s.findtext('port') for s in self.xml('fastmail').findall('.//outgoingServer')], ['465','587'])
        self.assertEqual(len(self.xml('yahoo').findall('.//outgoingServer')), 1)

    def test_xml_and_provenance(self):
        allowed = {'clientConfig','emailProvider','domain','displayName','displayShortName','incomingServer','outgoingServer','hostname','port','socketType','username','authentication'}
        for path, content in self.files.items():
            if not path.endswith('.xml'):
                continue
            p = self.by_slug[Path(path).stem]
            tree = ET.fromstring(content)
            self.assertEqual(tree.attrib, {'version':'1.1'})
            self.assertTrue({e.tag for e in tree.iter()} <= allowed)
            self.assertEqual([e.text for e in tree.findall('.//domain')], p['domains'])
            self.assertEqual(tree.findtext('.//displayName'), p['name'])
            for s in tree.findall('.//incomingServer') + tree.findall('.//outgoingServer'):
                kind = s.get('type')
                source = p['outgoing' if kind=='smtp' else 'incoming'][kind]
                self.assertEqual(s.findtext('hostname'), source['host'])
                candidates = [(source['port'], source['security'])] if source['security_documented'] else []
                if kind=='smtp' and source.get('alternative', {}).get('security') in SOCKET:
                    alt = source['alternative']; candidates.append((alt['port'],alt['security']))
                self.assertIn((int(s.findtext('port')),s.findtext('socketType')), [(port,SOCKET[sec]) for port,sec in candidates])
                self.assertEqual(s.findtext('username'), USERNAME[p['username']])
                self.assertEqual(tuple(e.text for e in s.findall('authentication')), AUTH[p['authentication']])

    def test_profiles_and_provenance(self):
        uuids = set()
        for path, content in self.files.items():
            if not path.endswith('.mobileconfig'):
                continue
            p = self.by_slug[Path(path).stem]
            profile = plistlib.loads(content)
            self.assertEqual(plistlib.dumps(profile, sort_keys=True), content)
            self.assertEqual(profile['PayloadType'], 'Configuration')
            self.assertEqual(len(profile['PayloadContent']), 1)
            m = profile['PayloadContent'][0]
            self.assertEqual(m['PayloadType'], 'com.apple.mail.managed')
            for payload in (profile,m):
                self.assertEqual(payload['PayloadVersion'],1)
                self.assertTrue(payload['PayloadIdentifier'].startswith('help.emails.'))
                self.assertEqual(uuid.UUID(payload['PayloadUUID']).version,5)
                self.assertNotIn(payload['PayloadUUID'], uuids); uuids.add(payload['PayloadUUID'])
            self.assertTrue(m['OutgoingPasswordSameAsIncomingPassword'])
            self.assertFalse(set(m) & {'EmailAddress','IncomingMailServerUsername','OutgoingMailServerUsername','IncomingPassword','OutgoingPassword'})
            xml = self.xml(p['slug'])
            for prefix, server in [('Incoming',xml.find('.//incomingServer')),('Outgoing',xml.find('.//outgoingServer'))]:
                self.assertEqual(m[prefix+'MailServerHostName'], server.findtext('hostname'))
                self.assertEqual(m[prefix+'MailServerPortNumber'], int(server.findtext('port')))
                self.assertTrue(m[prefix+'MailServerUseSSL'])
                self.assertEqual(m[prefix+'MailServerAuthentication'],'EmailAuthPassword')

    def test_unknown_fields_never_guessed(self):
        for field, value in [('username','unknown'),('authentication','password maybe'),('domains',[]),('client_access',False)]:
            p = copy.deepcopy(self.by_slug['aol']); p[field] = value
            self.assertEqual(json.loads(generate([p],self.version)['index.json'])['aol'],[])
        for field, value in [('security_documented',False),('security',None),('port',None),('host',None)]:
            p = copy.deepcopy(self.by_slug['aol']); p['outgoing']['smtp'][field] = value
            self.assertEqual(json.loads(generate([p],self.version)['index.json'])['aol'],[])


if __name__ == '__main__':
    unittest.main()
