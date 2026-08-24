"""Test bout-en-bout : création de compte → lien email → définition du mot de passe."""
from django.test import TestCase, override_settings
from django.core import mail
from rest_framework.test import APIClient

from api.models import User, PasswordSetupToken, NotificationLog


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_URL='https://missions.example.com',
    PASSWORD_SETUP_PATH='definir-mot-de-passe',
    PASSWORD_SETUP_TOKEN_HOURS=48,
)
class FluxDefinitionMotDePasseTest(TestCase):
    client_class = APIClient

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='flux_admin', password='Sup3rAdm1n!x', matricule='ADM-T',
            telephone='0000000001', email_reciever='admin@example.com',
        )
        self.client.force_authenticate(user=self.admin)

    def _creer_utilisateur(self, **extra):
        payload = {
            'username': 'flux_user', 'first_name': 'Jean', 'last_name': 'Kouassi',
            'matricule': 'MAT-1', 'fonction': 'Analyste', 'date_naissance': '1990-05-12',
            'telephone': '0700000001', 'email_reciever': 'jean.kouassi@example.com',
        }
        payload.update(extra)
        return self.client.post('/api/v1/utilisateur/', payload, content_type='application/json')

    def test_flux_complet(self):
        # 1. Création sans mot de passe
        r = self._creer_utilisateur()
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['lien_mot_de_passe_envoye'])

        u = User.objects.get(username='flux_user')
        self.assertFalse(u.has_usable_password())

        # 2. Lien généré et email envoyé
        jeton = PasswordSetupToken.objects.get(user=u)
        url = jeton.construire_url()
        self.assertTrue(url.startswith('https://missions.example.com/definir-mot-de-passe/'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('jean.kouassi@example.com', mail.outbox[0].to)
        self.assertIn(url, mail.outbox[0].alternatives[0][0])
        self.assertIn(url, mail.outbox[0].body)

        # 3. Connexion refusée tant que le mot de passe n'est pas défini
        anon = self.client_class()
        r = anon.post('/api/v1/authentification/',
                      {'username': 'flux_user', 'password': 'peu importe'},
                      content_type='application/json')
        self.assertEqual(r.status_code, 403)
        self.assertTrue(r.json().get('mot_de_passe_a_definir'))

        # 4. GET du lien
        r = anon.get(f'/api/v1/definir-mot-de-passe/{jeton.token}/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['valide'])
        self.assertEqual(r.json()['username'], 'flux_user')

        # 5. Mot de passe trop faible
        r = anon.post(f'/api/v1/definir-mot-de-passe/{jeton.token}/',
                      {'password': '1234', 'password2': '1234'}, content_type='application/json')
        self.assertEqual(r.status_code, 400)

        # 6. Confirmation différente
        r = anon.post(f'/api/v1/definir-mot-de-passe/{jeton.token}/',
                      {'password': 'M0tDeP@sseSolide!', 'password2': 'Autre!42xyz'},
                      content_type='application/json')
        self.assertEqual(r.status_code, 400)

        # 7. Définition réussie
        r = anon.post(f'/api/v1/definir-mot-de-passe/{jeton.token}/',
                      {'password': 'M0tDeP@sseSolide!', 'password2': 'M0tDeP@sseSolide!'},
                      content_type='application/json')
        self.assertEqual(r.status_code, 200)
        u.refresh_from_db(); jeton.refresh_from_db()
        self.assertTrue(u.check_password('M0tDeP@sseSolide!'))
        self.assertTrue(jeton.is_used)
        self.assertIsNotNone(jeton.used_at)

        # 8. Lien à usage unique
        r = anon.post(f'/api/v1/definir-mot-de-passe/{jeton.token}/',
                      {'password': 'Encore1Autre!', 'password2': 'Encore1Autre!'},
                      content_type='application/json')
        self.assertEqual(r.status_code, 400)

        # 9. Lien inconnu
        r = anon.get('/api/v1/definir-mot-de-passe/jeton-bidon/')
        self.assertEqual(r.status_code, 404)

        # 10. Connexion : arrive à l'étape OTP
        r = anon.post('/api/v1/authentification/',
                      {'username': 'flux_user', 'password': 'M0tDeP@sseSolide!'},
                      content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get('otp_required'))

        # 11. Renvoi du lien par l'admin
        r = self.client.post(f'/api/v1/utilisateur/{u.pk}/lien-mot-de-passe/', {},
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        nouveau = PasswordSetupToken.objects.get(user=u, is_used=False)
        self.assertEqual(nouveau.motif, 'REINITIALISATION')
        self.assertNotEqual(nouveau.token, jeton.token)

    def test_creation_avec_mot_de_passe_nenvoie_pas_de_lien(self):
        r = self._creer_utilisateur(username='flux_direct', matricule='MAT-2',
                                    telephone='0700000002', password='M0tDeP@sseDirect!')
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.json()['lien_mot_de_passe_envoye'])
        self.assertTrue(User.objects.get(username='flux_direct').has_usable_password())
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(PasswordSetupToken.objects.count(), 0)

    def test_lien_expire_refuse(self):
        from django.utils import timezone
        from datetime import timedelta
        self._creer_utilisateur()
        jeton = PasswordSetupToken.objects.get()
        jeton.expires_at = timezone.now() - timedelta(minutes=1)
        jeton.save(update_fields=['expires_at'])
        anon = self.client_class()
        r = anon.get(f'/api/v1/definir-mot-de-passe/{jeton.token}/')
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()['valide'])

    def test_inscription_endpoint_envoie_le_lien(self):
        r = self.client.post('/api/v1/inscription/', {
            'username': 'flux_inscr', 'email': 'i@example.com', 'matricule': 'MAT-3',
            'fonction': 'RH', 'date_naissance': '1988-01-01', 'telephone': '0700000003',
            'email_reciever': 'inscr@example.com',
        }, content_type='application/json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['lien_mot_de_passe_envoye'])
        self.assertEqual(len(mail.outbox), 1)
