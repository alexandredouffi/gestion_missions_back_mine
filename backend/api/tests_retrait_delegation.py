"""Notification au retrait d'un membre de la délégation."""
from datetime import date

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import (User, Entite, Destination, CategorieEmploye, Bareme, Mission,
                        Delegation, Paiement, JustificationHebergement,
                        PieceJustificative, Profil)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RetraitDelegationTest(TestCase):
    client_class = APIClient

    def setUp(self):
        self.ent = Entite.objects.create(nom='ENT', abreviation='ENT')
        self.dest = Destination.objects.create(nom='DEST')
        self.cat = CategorieEmploye.objects.create(nom='CAT')
        Bareme.objects.create(filiale=self.ent, categorie=self.cat, destination=self.dest,
                              hebergement=50000, perdiem=10000, communication=5000, transport=20000)

        def mk(nom, tel):
            return User.objects.create_user(
                username=nom, password='x', matricule=nom, telephone=tel,
                first_name=nom.title(), last_name='T',
                filiale=self.ent, category=self.cat, email_reciever=f'{nom}@ex.com')

        self.demandeur = mk('demandeur', '01')
        self.membre = mk('membre', '02')
        self.gestionnaire = mk('gestionnaire', '03')
        self.tresorier = mk('tresorier', '04')
        self.comptable = mk('comptable', '05')
        self.comptable.profil = Profil.objects.get_or_create(nom='Comptable')[0]
        self.comptable.save()

        self.mission = Mission.objects.create(
            date_demande=date.today(), entite=self.ent, objet_mission='Audit annuel',
            date_depart=date(2026, 1, 1), date_retour=date(2026, 1, 3),
            lieu_mission='Bouaké', destination_mission=self.dest,
            demandeur=self.demandeur, statut_mission='APPROUVEE')

    def _deleg(self, employe=None, chef=False):
        return Delegation.objects.create(mission=self.mission,
                                         employe=employe or self.membre, est_chef=chef)

    def _retirer(self, deleg, acteur):
        c = self.client_class()
        c.force_authenticate(user=acteur)
        return c.delete(f'/api/v1/delegation/{deleg.pk}/')

    def _corps(self, msg):
        return msg.alternatives[0][0]

    def _par_destinataire(self):
        return {m.to[0]: m for m in mail.outbox}

    def test_retrait_simple_notifie_membre_et_demandeur(self):
        d = self._deleg()
        montant = d.montant_total
        self.assertGreater(montant, 0)
        mail.outbox.clear()

        r = self._retirer(d, self.gestionnaire)
        self.assertEqual(r.status_code, 204)

        recus = self._par_destinataire()
        self.assertEqual(set(recus), {'membre@ex.com', 'demandeur@ex.com'})

        au_membre = recus['membre@ex.com']
        self.assertIn('Vous avez été retiré de la mission', au_membre.subject)
        corps = self._corps(au_membre)
        self.assertIn('Audit annuel', corps)
        self.assertIn('T Gestionnaire', corps)              # retiré par
        self.assertIn(f'{montant:,.0f}', corps)             # indemnités annulées
        self.assertIn('MEMBRE RETIRÉ', corps)

        au_demandeur = recus['demandeur@ex.com']
        self.assertIn('Membre retiré de la délégation', au_demandeur.subject)
        self.assertIn('T Membre', self._corps(au_demandeur))

    def test_auteur_du_retrait_ne_se_notifie_pas(self):
        d = self._deleg()
        mail.outbox.clear()
        self._retirer(d, self.membre)          # le membre se retire lui-même
        self.assertEqual(set(self._par_destinataire()), {'demandeur@ex.com'})

    def test_retrait_du_chef_de_delegation_est_signale(self):
        d = self._deleg(chef=True)
        mail.outbox.clear()
        self._retirer(d, self.gestionnaire)
        corps = self._corps(self._par_destinataire()['membre@ex.com'])
        self.assertIn('chef de délégation', corps)
        self.assertIn("n'a plus de chef désigné", corps)

    def test_paiement_supprime_en_cascade_est_signale_au_tresorier(self):
        d = self._deleg()
        Paiement.objects.create(delegation=d, mode='CHEQUE', montant=d.montant_total,
                                reference_cheque='CHQ-42', date_paiement=date.today(),
                                effectue=True, enregistre_par=self.tresorier)
        mail.outbox.clear()

        self._retirer(d, self.gestionnaire)

        recus = self._par_destinataire()
        self.assertEqual(set(recus),
                         {'membre@ex.com', 'demandeur@ex.com', 'tresorier@ex.com'})

        corps = self._corps(recus['membre@ex.com'])
        self.assertIn('PAIEMENT SUPPRIMÉ', corps)
        self.assertIn('paiement enregistré a été supprimé', corps)
        self.assertIn('CHQ-42', corps)
        self.assertIn('Chèque', corps)
        self.assertIn('déjà effectué', corps)

        au_tresorier = recus['tresorier@ex.com']
        self.assertIn('Paiement supprimé', au_tresorier.subject)
        self.assertIn('CHQ-42', au_tresorier.body)

        # la cascade a bien eu lieu
        self.assertEqual(Paiement.objects.count(), 0)

    def test_justification_supprimee_en_cascade_est_signalee(self):
        d = self._deleg()
        j = JustificationHebergement.objects.create(delegation=d,
                                                    valide_par_comptable=self.comptable,
                                                    date_validation_comptable=timezone.now())
        PieceJustificative.objects.create(justification=j, libelle='Hôtel', montant=30000,
                                          document=SimpleUploadedFile('a.pdf', b'x'))
        PieceJustificative.objects.create(justification=j, libelle='Nuit 2', montant=20000,
                                          document=SimpleUploadedFile('b.pdf', b'x'))
        mail.outbox.clear()

        self._retirer(d, self.gestionnaire)

        corps = self._corps(self._par_destinataire()['membre@ex.com'])
        self.assertIn("justification d'hébergement a été supprimée", corps)
        self.assertIn('2 pièce(s)', corps)
        self.assertIn('50,000 F CFA', corps)
        self.assertIn('validée par T Comptable', corps)

        self.assertEqual(JustificationHebergement.objects.count(), 0)
        self.assertEqual(PieceJustificative.objects.count(), 0)

    def test_ajout_notifie_toujours(self):
        mail.outbox.clear()
        c = self.client_class()
        c.force_authenticate(user=self.gestionnaire)
        r = c.post(f'/api/v1/delegation/mission/{self.mission.pk}/',
                   {'employe': self.membre.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Vous avez été ajouté à la mission', mail.outbox[0].subject)
