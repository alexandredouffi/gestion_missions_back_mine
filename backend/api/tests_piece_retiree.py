"""Notification à l'envoi ET au retrait d'une pièce justificative."""
from datetime import date

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import (User, Entite, Destination, CategorieEmploye, Bareme, Mission,
                        Delegation, JustificationHebergement, PieceJustificative, Profil)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RetraitPieceJustificativeTest(TestCase):
    client_class = APIClient

    def setUp(self):
        self.ent = Entite.objects.create(nom='ENT', abreviation='ENT')
        self.dest = Destination.objects.create(nom='DEST')
        self.cat = CategorieEmploye.objects.create(nom='CAT')
        Bareme.objects.create(filiale=self.ent, categorie=self.cat, destination=self.dest,
                              hebergement=50000, perdiem=10000)

        def mk(nom, tel):
            return User.objects.create_user(
                username=nom, password='x', matricule=nom, telephone=tel,
                first_name=nom.title(), last_name='T',
                filiale=self.ent, category=self.cat, email_reciever=f'{nom}@ex.com')

        self.employe = mk('employe', '01')
        self.comptable = mk('comptable', '02')
        self.comptable.profil = Profil.objects.get_or_create(nom='Comptable')[0]
        self.comptable.save()
        self.comptable.filiales_attribuees.add(self.ent)

        mission = Mission.objects.create(
            date_demande=date.today(), entite=self.ent, objet_mission='Audit',
            date_depart=date(2026, 1, 1), date_retour=date(2026, 1, 3),
            lieu_mission='L', destination_mission=self.dest,
            demandeur=self.employe, statut_mission='APPROUVEE')
        self.deleg = Delegation.objects.create(mission=mission, employe=self.employe)
        self.justif = JustificationHebergement.objects.create(delegation=self.deleg)
        self.attendu = self.deleg.montant_hebergement
        self.assertGreater(self.attendu, 0)

    def _ajouter(self, montant, libelle='Hôtel'):
        return PieceJustificative.objects.create(
            justification=self.justif, libelle=libelle, montant=montant,
            document=SimpleUploadedFile('f.pdf', b'x'))

    def _retirer(self, piece, acteur):
        c = self.client_class()
        c.force_authenticate(user=acteur)
        return c.delete(f'/api/v1/piece-justificative/{piece.pk}/')

    def test_retrait_rendant_la_justification_incomplete(self):
        piece = self._ajouter(self.attendu)
        self.assertTrue(self.justif.est_complet)
        mail.outbox.clear()

        r = self._retirer(piece, self.employe)
        self.assertEqual(r.status_code, 204)

        # le comptable est alerté, l'employé (auteur du retrait) ne l'est pas
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['comptable@ex.com'])
        self.assertIn('Pièce justificative retirée', msg.subject)
        corps = msg.alternatives[0][0]
        self.assertIn('JUSTIFICATION INCOMPLÈTE', corps)
        self.assertIn('T Employe', corps)          # retirée par
        self.assertIn('Reste à justifier', corps)
        self.assertIn(f'{self.attendu:,.0f}', msg.body)

    def test_retrait_apres_validation_alerte_en_rouge(self):
        piece = self._ajouter(self.attendu)
        self.justif.valide_par_comptable = self.comptable
        self.justif.date_validation_comptable = timezone.now()
        self.justif.save()
        mail.outbox.clear()

        self._retirer(piece, self.employe)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].alternatives[0][0]
        self.assertIn('RETRAIT APRÈS VALIDATION', corps)
        self.assertIn('avait déjà été validée', corps)
        self.assertIn('avait déjà été validée', mail.outbox[0].body)

    def test_retrait_partiel_sur_justification_deja_incomplete(self):
        self._ajouter(10000, 'Nuit 1')
        piece = self._ajouter(5000, 'Nuit 2')
        self.assertFalse(self.justif.est_complet)
        mail.outbox.clear()

        self._retirer(piece, self.employe)
        self.assertEqual(len(mail.outbox), 1)
        corps = mail.outbox[0].alternatives[0][0]
        self.assertIn('PIÈCE RETIRÉE', corps)
        self.assertNotIn('JUSTIFICATION INCOMPLÈTE', corps)
        self.assertIn('Nuit 2', corps)
        # montant restant recalculé après suppression
        self.assertIn('10,000 F CFA', corps)

    def test_retrait_par_le_comptable_notifie_l_employe(self):
        piece = self._ajouter(self.attendu)
        mail.outbox.clear()

        self._retirer(piece, self.comptable)

        # le comptable auteur ne se notifie pas lui-même ; l'employé est prévenu
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['employe@ex.com'])
        self.assertIn('Une pièce de votre justification a été retirée', msg.subject)
        self.assertIn('T Comptable', msg.alternatives[0][0])

    def test_ajout_notifie_toujours_quand_la_justification_devient_complete(self):
        mail.outbox.clear()
        c = self.client_class()
        c.force_authenticate(user=self.employe)
        r = c.post(f'/api/v1/justification/{self.justif.pk}/piece/', {
            'libelle': 'Hôtel', 'montant': self.attendu,
            'document': SimpleUploadedFile('f.pdf', b'x'),
        }, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Justification complète à valider', mail.outbox[0].subject)
