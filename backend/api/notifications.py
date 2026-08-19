from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

FROM = settings.DEFAULT_FROM_EMAIL

# ── Palette ────────────────────────────────────────────────────────────────
COLOR_PRIMARY   = '#1B3A6B'   # bleu marine
COLOR_ACCENT    = '#2E86DE'   # bleu vif
COLOR_SUCCESS   = '#27AE60'   # vert
COLOR_DANGER    = '#E74C3C'   # rouge
COLOR_WARNING   = '#F39C12'   # orange
COLOR_LIGHT     = '#F4F6F9'   # fond gris clair
COLOR_TEXT      = '#2C3E50'   # texte principal
COLOR_MUTED     = '#7F8C8D'   # texte secondaire


def _email(user):
    addr = getattr(user, 'email_reciever', None)
    if addr and addr != 'Inconnu' and '@' in addr:
        return addr
    return None


def _log(sujet, destinataires, statut, erreur=None):
    from .models import NotificationLog
    NotificationLog.objects.create(
        sujet=sujet,
        destinataires=', '.join(destinataires),
        statut=statut,
        erreur=erreur,
    )


def _nom(user):
    nom = f"{user.last_name} {user.first_name}".strip()
    return nom if nom else user.username


# ── Template HTML de base ───────────────────────────────────────────────────

def _html(titre, couleur_titre, lignes_html, badge=None, badge_couleur=None, cta_label=None):
    """
    Génère un email HTML complet.
    lignes_html : liste de chaînes HTML insérées dans le corps.
    """
    badge_html = ''
    if badge:
        bg = badge_couleur or COLOR_ACCENT
        badge_html = f'''
        <div style="text-align:center;margin:0 0 24px 0;">
          <span style="display:inline-block;background:{bg};color:#fff;
                       padding:6px 18px;border-radius:20px;font-size:13px;
                       font-weight:600;letter-spacing:.5px;">{badge}</span>
        </div>'''

    rows = ''.join(
        f'<p style="margin:0 0 12px 0;color:{COLOR_TEXT};font-size:15px;line-height:1.6;">{l}</p>'
        for l in lignes_html
    )

    cta_html = ''
    if cta_label:
        cta_html = f'''
        <div style="text-align:center;margin:28px 0 0 0;">
          <a href="#" style="display:inline-block;background:{COLOR_ACCENT};color:#fff;
                             padding:12px 32px;border-radius:6px;font-size:15px;
                             font-weight:600;text-decoration:none;">{cta_label}</a>
        </div>'''

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:{COLOR_LIGHT};font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:{COLOR_LIGHT};padding:32px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;background:#ffffff;
                      border-radius:10px;overflow:hidden;
                      box-shadow:0 2px 12px rgba(0,0,0,.08);">

          <!-- En-tête -->
          <tr>
            <td style="background:{COLOR_PRIMARY};padding:28px 36px;">
              <p style="margin:0;color:#fff;font-size:20px;font-weight:700;letter-spacing:.3px;">
                ✈&nbsp; Gestion des Missions
              </p>
              <p style="margin:4px 0 0 0;color:rgba(255,255,255,.65);font-size:13px;">
                Système de gestion des déplacements professionnels
              </p>
            </td>
          </tr>

          <!-- Titre section -->
          <tr>
            <td style="background:{couleur_titre};padding:18px 36px;">
              <p style="margin:0;color:#fff;font-size:17px;font-weight:600;">
                {titre}
              </p>
            </td>
          </tr>

          <!-- Corps -->
          <tr>
            <td style="padding:32px 36px;">
              {badge_html}
              {rows}
              {cta_html}
            </td>
          </tr>

          <!-- Séparateur info-mission (si données dans lignes) -->

          <!-- Pied de page -->
          <tr>
            <td style="background:{COLOR_LIGHT};padding:20px 36px;
                       border-top:1px solid #E0E6EF;">
              <p style="margin:0;color:{COLOR_MUTED};font-size:12px;line-height:1.6;">
                Cet email a été envoyé automatiquement par le système de Gestion des Missions.<br>
                Merci de ne pas répondre directement à ce message.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _info_block(libelle, valeur):
    """Ligne de données dans un bloc d'information."""
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid #E0E6EF;border-radius:6px;margin:16px 0;overflow:hidden;">'
        f'<tr>'
        f'<td style="background:{COLOR_LIGHT};padding:10px 16px;width:40%;'
        f'font-size:13px;color:{COLOR_MUTED};font-weight:600;border-right:1px solid #E0E6EF;">'
        f'{libelle}</td>'
        f'<td style="padding:10px 16px;font-size:14px;color:{COLOR_TEXT};font-weight:500;">'
        f'{valeur}</td>'
        f'</tr></table>'
    )

def _envoyer_async(subject, texte, html, *recipients):
    valides = [e for e in recipients if e]
    if not valides:
        _log(subject, [], 'IGNORE')
        return

    def _send():
        try:
            print(f"Envoi de l'email '{subject}' à {valides}...")
            msg = EmailMultiAlternatives(subject, texte, FROM, valides)
            msg.attach_alternative(html, 'text/html')
            msg.send(fail_silently=False)
            _log(subject, valides, 'ENVOYE')
        except Exception as exc:
            print(f"Erreur lors de l'envoi de l'email '{subject}' à {valides} : {exc}")
            _log(subject, valides, 'ECHEC', erreur=str(exc))

    executor.submit(_send)


def _envoyer(subject, texte, html, *recipients):
    _envoyer_async(subject, texte, html, *recipients)
    # valides = [e for e in recipients if e]
    # if not valides:
    #     _log(subject, [], 'IGNORE')
    #     return
    # try:
    #     print(f"Envoi de l'email '{subject}' à {valides}...")
    #     msg = EmailMultiAlternatives(subject, texte, FROM, valides)
    #     msg.attach_alternative(html, 'text/html')
    #     msg.send()
    #     _log(subject, valides, 'ENVOYE')
    # except Exception as exc:
    #     print(f"Erreur lors de l'envoi de l'email '{subject}' à {valides} : {exc}")
    #     _log(subject, valides, 'ECHEC', erreur=str(exc))


# ── 0. OTP ──────────────────────────────────────────────────────────────────

def _envoyer_otp(user, code):
    sujet = "[Gestion Missions] Votre code de connexion"
    texte = (
        f"Bonjour {_nom(user)},\n\n"
        f"Votre code de connexion est : {code}\n\n"
        f"Ce code est valable 5 minutes.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
        f"Cordialement,\nGestion Missions"
    )

    # Chaque chiffre dans sa propre case
    chiffres_html = ''.join(
        f'<td style="padding:0 6px;">'
        f'<span style="display:inline-block;width:52px;height:64px;line-height:64px;'
        f'text-align:center;background:#fff;border:2px solid {COLOR_ACCENT};'
        f'border-radius:10px;font-size:32px;font-weight:800;color:{COLOR_PRIMARY};'
        f'box-shadow:0 2px 8px rgba(43,134,222,.15);">{c}</span></td>'
        for c in code
    )

    bloc_code = (
        f'<table cellpadding="0" cellspacing="0" style="margin:28px auto;">'
        f'<tr>{chiffres_html}</tr>'
        f'</table>'
    )

    bloc_timer = (
        f'<div style="text-align:center;margin:0 0 20px;">'
        f'<span style="display:inline-flex;align-items:center;gap:6px;'
        f'background:#FFF3CD;border:1px solid #FFEAA7;border-radius:20px;'
        f'padding:8px 20px;font-size:13px;font-weight:600;color:#856404;">'
        f'⏱&nbsp; Ce code expire dans <strong>5 minutes</strong></span></div>'
    )

    bloc_securite = (
        f'<div style="background:{COLOR_LIGHT};border-left:3px solid {COLOR_MUTED};'
        f'border-radius:4px;padding:12px 16px;margin-top:20px;">'
        f'<p style="margin:0;font-size:12px;color:{COLOR_MUTED};">'
        f'🔒 <strong>Sécurité :</strong> Ne partagez jamais ce code. '
        f"Gestion Missions ne vous demandera jamais votre mot de passe par email.</p>"
        f'</div>'
    )

    html = _html(
        titre="Code de vérification",
        couleur_titre=COLOR_PRIMARY,
        badge="AUTHENTIFICATION EN 2 ÉTAPES", badge_couleur=COLOR_ACCENT,
        lignes_html=[
            f"Bonjour <strong>{_nom(user)}</strong>,",
            "Entrez le code suivant pour finaliser votre connexion à <strong>Gestion Missions</strong>.",
            bloc_code,
            bloc_timer,
            bloc_securite,
        ],
    )
    _envoyer(sujet, texte, html, _email(user))


# ── 1. Création de mission ──────────────────────────────────────────────────

def notifier_creation_mission(mission):
    from .models import MissionWorkflow
    demandeur = mission.demandeur
    numero = mission.numero_mission
    objet = mission.objet_mission

    # --- Demandeur ---
    sujet = f"[Gestion Missions] Votre mission {numero} a été soumise"
    texte = (
        f"Bonjour {_nom(demandeur)},\n\n"
        f"Votre demande de mission « {objet} » (réf. {numero}) a bien été enregistrée.\n"
        f"Période : du {mission.date_depart} au {mission.date_retour}\n\n"
        f"Vous serez notifié à chaque étape.\n\nCordialement,\nGestion Missions"
    )
    html = _html(
        titre="Votre mission a été soumise",
        couleur_titre=COLOR_ACCENT,
        badge="EN ATTENTE DE VALIDATION", badge_couleur=COLOR_WARNING,
        lignes_html=[
            f"Bonjour <strong>{_nom(demandeur)}</strong>,",
            f"Votre demande de mission a bien été enregistrée et est en attente de validation.",
            _info_block("Référence", numero),
            _info_block("Objet", objet),
            _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
            _info_block("Lieu", mission.lieu_mission),
            "Vous recevrez une notification à chaque étape du processus de validation.",
        ],
        cta_label="Consulter ma mission",
    )
    _envoyer(sujet, texte, html, _email(demandeur))

    # --- Premier signataire ---
    premiere_etape = MissionWorkflow.objects.filter(
        mission=mission
    ).select_related('user_validation').order_by('numero_etape').first()

    if premiere_etape and premiere_etape.user_validation:
        signataire = premiere_etape.user_validation
        sujet2 = f"[Gestion Missions] Mission {numero} en attente de votre signature"
        texte2 = (
            f"Bonjour {_nom(signataire)},\n\n"
            f"La mission {numero} — {objet} nécessite votre validation.\n"
            f"Demandeur : {_nom(demandeur)}\n"
            f"Période : du {mission.date_depart} au {mission.date_retour}\n\n"
            f"Connectez-vous pour traiter cette demande.\n\nCordialement,\nGestion Missions"
        )
        html2 = _html(
            titre="Une mission attend votre signature",
            couleur_titre=COLOR_WARNING,
            badge="ACTION REQUISE", badge_couleur=COLOR_WARNING,
            lignes_html=[
                f"Bonjour <strong>{_nom(signataire)}</strong>,",
                f"Une nouvelle mission nécessite votre validation à l'étape "
                f"<strong>« {premiere_etape.libelle_etape} »</strong>.",
                _info_block("Référence", numero),
                _info_block("Objet", objet),
                _info_block("Demandeur", _nom(demandeur)),
                _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
                _info_block("Lieu", mission.lieu_mission),
            ],
            cta_label="Traiter la mission",
        )
        _envoyer(sujet2, texte2, html2, _email(signataire))


# ── 2. Ajout délégation ─────────────────────────────────────────────────────

def notifier_ajout_delegation(delegation):
    employe = delegation.employe
    mission = delegation.mission
    sujet = f"[Gestion Missions] Vous avez été ajouté à la mission {mission.numero_mission}"
    texte = (
        f"Bonjour {_nom(employe)},\n\n"
        f"Vous avez été intégré à la délégation de la mission {mission.numero_mission}.\n"
        f"Objet : {mission.objet_mission}\n"
        f"Période : du {mission.date_depart} au {mission.date_retour}\n\n"
        f"Cordialement,\nGestion Missions"
    )
    html = _html(
        titre="Vous faites partie d'une délégation",
        couleur_titre=COLOR_ACCENT,
        badge="DÉLÉGATION", badge_couleur=COLOR_ACCENT,
        lignes_html=[
            f"Bonjour <strong>{_nom(employe)}</strong>,",
            "Vous avez été intégré(e) à la délégation de la mission suivante.",
            _info_block("Référence", mission.numero_mission),
            _info_block("Objet", mission.objet_mission),
            _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
            _info_block("Lieu", mission.lieu_mission),
        ],
        cta_label="Voir les détails",
    )
    _envoyer(sujet, texte, html, _email(employe))


# ── 3. Traitement d'une étape workflow ──────────────────────────────────────

def notifier_traitement_mission(etape, signataire):
    from .models import MissionWorkflow
    mission = etape.mission
    nouveau_statut = etape.statut
    numero = mission.numero_mission
    objet = mission.objet_mission
    est_approuve = nouveau_statut == 'APPROUVE'

    # Confirmation au signataire
    action_label = "approuvé" if est_approuve else "rejeté"
    couleur_action = COLOR_SUCCESS if est_approuve else COLOR_DANGER
    badge_action = "APPROUVÉ" if est_approuve else "REJETÉ"

    sujet_sig = f"[Gestion Missions] Confirmation de votre action — {numero}"
    texte_sig = (
        f"Bonjour {_nom(signataire)},\n\n"
        f"Vous avez {action_label} l'étape « {etape.libelle_etape} » pour la mission {numero}.\n"
        f"Date : {etape.date_validation}\n\nCordialement,\nGestion Missions"
    )
    html_sig = _html(
        titre=f"Étape {action_label}e — {numero}",
        couleur_titre=couleur_action,
        badge=f"ÉTAPE {badge_action}", badge_couleur=couleur_action,
        lignes_html=[
            f"Bonjour <strong>{_nom(signataire)}</strong>,",
            f"Vous avez <strong>{action_label}</strong> l'étape "
            f"<strong>« {etape.libelle_etape} »</strong> pour la mission suivante.",
            _info_block("Référence", numero),
            _info_block("Objet", objet),
            _info_block("Date de traitement", str(etape.date_validation)[:16] if etape.date_validation else "—"),
            *([] if est_approuve else [_info_block("Motif", etape.commentaire or "Aucun commentaire")]),
        ],
    )
    _envoyer(sujet_sig, texte_sig, html_sig, _email(signataire))

    membres = list(mission.delegations.select_related('employe').all())

    if not est_approuve:
        commentaire = etape.commentaire or "Aucun commentaire."
        for d in membres:
            sujet_m = f"[Gestion Missions] Mission {numero} rejetée"
            texte_m = (
                f"Bonjour {_nom(d.employe)},\n\n"
                f"La mission {numero} a été rejetée par {_nom(signataire)}.\n"
                f"Motif : {commentaire}\n\nCordialement,\nGestion Missions"
            )
            html_m = _html(
                titre=f"Mission rejetée — {numero}",
                couleur_titre=COLOR_DANGER,
                badge="REJETÉE", badge_couleur=COLOR_DANGER,
                lignes_html=[
                    f"Bonjour <strong>{_nom(d.employe)}</strong>,",
                    f"La mission <strong>{numero}</strong> a été rejetée à l'étape "
                    f"<strong>« {etape.libelle_etape} »</strong> "
                    f"par <strong>{_nom(signataire)}</strong>.",
                    _info_block("Référence", numero),
                    _info_block("Objet", objet),
                    _info_block("Rejeté par", _nom(signataire)),
                    _info_block("Motif", commentaire),
                    "Le demandeur peut modifier et resoumettre la mission.",
                ],
            )
            _envoyer(sujet_m, texte_m, html_m, _email(d.employe))

    else:
        reste_en_attente = MissionWorkflow.objects.filter(
            mission=mission
        ).exclude(statut='APPROUVE').exists()

        if not reste_en_attente:
            for d in membres:
                sujet_m = f"[Gestion Missions] Mission {numero} entièrement approuvée 🎉"
                texte_m = (
                    f"Bonjour {_nom(d.employe)},\n\n"
                    f"La mission {numero} — {objet} a été entièrement approuvée.\n"
                    f"Période : du {mission.date_depart} au {mission.date_retour}\n\n"
                    f"Cordialement,\nGestion Missions"
                )
                html_m = _html(
                    titre=f"Mission entièrement approuvée — {numero}",
                    couleur_titre=COLOR_SUCCESS,
                    badge="APPROUVÉE", badge_couleur=COLOR_SUCCESS,
                    lignes_html=[
                        f"Bonjour <strong>{_nom(d.employe)}</strong>,",
                        "Bonne nouvelle ! Votre mission a été entièrement approuvée.",
                        _info_block("Référence", numero),
                        _info_block("Objet", objet),
                        _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
                        _info_block("Lieu", mission.lieu_mission),
                        "Vous serez notifié(e) dès que votre paiement sera enregistré.",
                    ],
                    cta_label="Voir ma mission",
                )
                _envoyer(sujet_m, texte_m, html_m, _email(d.employe))
        else:
            for d in membres:
                sujet_m = f"[Gestion Missions] Étape validée — mission {numero}"
                texte_m = (
                    f"Bonjour {_nom(d.employe)},\n\n"
                    f"L'étape « {etape.libelle_etape} » de la mission {numero} a été approuvée.\n\n"
                    f"Cordialement,\nGestion Missions"
                )
                html_m = _html(
                    titre=f"Étape validée — {numero}",
                    couleur_titre=COLOR_ACCENT,
                    badge="ÉTAPE APPROUVÉE", badge_couleur=COLOR_SUCCESS,
                    lignes_html=[
                        f"Bonjour <strong>{_nom(d.employe)}</strong>,",
                        f"L'étape <strong>« {etape.libelle_etape} »</strong> de votre mission a été approuvée "
                        f"par <strong>{_nom(signataire)}</strong>.",
                        _info_block("Référence", numero),
                        _info_block("Objet", objet),
                        "La mission est en attente de la prochaine validation.",
                    ],
                )
                _envoyer(sujet_m, texte_m, html_m, _email(d.employe))

            prochaine_etape = MissionWorkflow.objects.filter(
                mission=mission,
                statut='EN_ATTENTE',
                numero_etape__gt=etape.numero_etape
            ).select_related('user_validation').order_by('numero_etape').first()

            if prochaine_etape and prochaine_etape.user_validation:
                prochain = prochaine_etape.user_validation
                sujet_p = f"[Gestion Missions] Mission {numero} en attente de votre signature"
                texte_p = (
                    f"Bonjour {_nom(prochain)},\n\n"
                    f"La mission {numero} est à votre niveau pour validation.\n"
                    f"Étape : {prochaine_etape.libelle_etape}\n\n"
                    f"Cordialement,\nGestion Missions"
                )
                html_p = _html(
                    titre="Une mission attend votre signature",
                    couleur_titre=COLOR_WARNING,
                    badge="ACTION REQUISE", badge_couleur=COLOR_WARNING,
                    lignes_html=[
                        f"Bonjour <strong>{_nom(prochain)}</strong>,",
                        f"La mission suivante est maintenant à votre niveau pour validation "
                        f"(<strong>étape : {prochaine_etape.libelle_etape}</strong>).",
                        _info_block("Référence", numero),
                        _info_block("Objet", objet),
                        _info_block("Demandeur", _nom(mission.demandeur)),
                        _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
                    ],
                    cta_label="Traiter la mission",
                )
                _envoyer(sujet_p, texte_p, html_p, _email(prochain))


# ── 4. Paiement ─────────────────────────────────────────────────────────────

def notifier_paiement(paiement, tresorier):
    employe = paiement.delegation.employe
    mission = paiement.delegation.mission
    montant = paiement.montant
    mode = paiement.get_mode_display()
    numero = mission.numero_mission

    # Confirmation trésorier
    sujet_t = f"[Gestion Missions] Paiement enregistré — {numero}"
    texte_t = (
        f"Bonjour {_nom(tresorier)},\n\n"
        f"Vous avez enregistré le paiement de {montant:,.0f} F CFA pour {_nom(employe)}.\n"
        f"Mission : {numero}\nMode : {mode}\n\nCordialement,\nGestion Missions"
    )
    html_t = _html(
        titre=f"Paiement enregistré — {numero}",
        couleur_titre=COLOR_SUCCESS,
        badge="PAIEMENT EFFECTUÉ", badge_couleur=COLOR_SUCCESS,
        lignes_html=[
            f"Bonjour <strong>{_nom(tresorier)}</strong>,",
            "Le paiement suivant a été enregistré avec succès.",
            _info_block("Bénéficiaire", _nom(employe)),
            _info_block("Mission", f"{numero} — {mission.objet_mission}"),
            _info_block("Montant", f"{montant:,.0f} F CFA"),
            _info_block("Mode", mode),
            _info_block("Date", str(paiement.date_paiement)),
        ],
    )
    _envoyer(sujet_t, texte_t, html_t, _email(tresorier))

    # Notification bénéficiaire
    sujet_e = f"[Gestion Missions] Votre indemnité de mission a été payée — {numero}"
    texte_e = (
        f"Bonjour {_nom(employe)},\n\n"
        f"Votre indemnité pour la mission {numero} a été payée.\n"
        f"Montant : {montant:,.0f} F CFA\nMode : {mode}\n\nCordialement,\nGestion Missions"
    )
    html_e = _html(
        titre="Votre indemnité de mission a été payée",
        couleur_titre=COLOR_SUCCESS,
        badge="PAIEMENT REÇU", badge_couleur=COLOR_SUCCESS,
        lignes_html=[
            f"Bonjour <strong>{_nom(employe)}</strong>,",
            "Votre indemnité de mission a été enregistrée.",
            _info_block("Mission", f"{numero} — {mission.objet_mission}"),
            _info_block("Montant", f"<strong style='color:{COLOR_SUCCESS};font-size:18px;'>{montant:,.0f} F CFA</strong>"),
            _info_block("Mode de paiement", mode),
            _info_block("Date", str(paiement.date_paiement)),
            _info_block("Enregistré par", _nom(tresorier)),
        ],
    )
    _envoyer(sujet_e, texte_e, html_e, _email(employe))


# ── 5. Justification complète ────────────────────────────────────────────────

def notifier_justification_complete(justification):
    from .models import User
    delegation = justification.delegation
    mission = delegation.mission
    employe = delegation.employe

    comptables = User.objects.filter(
        profil__nom='Comptable',
        filiales_attribuees=mission.entite,
        is_active=True,
    )

    for comptable in comptables:
        sujet = f"[Gestion Missions] Justification complète à valider — {mission.numero_mission}"
        texte = (
            f"Bonjour {_nom(comptable)},\n\n"
            f"{_nom(employe)} a complètement justifié ses frais d'hébergement "
            f"pour la mission {mission.numero_mission}.\n"
            f"Montant : {justification.montant_total_justifie:,.0f} F CFA\n\n"
            f"Cordialement,\nGestion Missions"
        )
        html = _html(
            titre="Justification complète — validation requise",
            couleur_titre=COLOR_WARNING,
            badge="À VALIDER", badge_couleur=COLOR_WARNING,
            lignes_html=[
                f"Bonjour <strong>{_nom(comptable)}</strong>,",
                f"<strong>{_nom(employe)}</strong> a complètement justifié ses frais "
                f"d'hébergement. Votre validation est requise.",
                _info_block("Mission", f"{mission.numero_mission} — {mission.objet_mission}"),
                _info_block("Bénéficiaire", _nom(employe)),
                _info_block("Montant justifié", f"{justification.montant_total_justifie:,.0f} F CFA"),
                _info_block("Montant attendu", f"{delegation.montant_hebergement:,.0f} F CFA"),
            ],
            cta_label="Valider la justification",
        )
        _envoyer(sujet, texte, html, _email(comptable))


# ── 6. Validation comptable ──────────────────────────────────────────────────

def notifier_validation_comptable(justification, comptable):
    employe = justification.delegation.employe
    mission = justification.delegation.mission
    numero = mission.numero_mission

    # Confirmation comptable
    sujet_c = f"[Gestion Missions] Justification validée — {numero}"
    texte_c = (
        f"Bonjour {_nom(comptable)},\n\n"
        f"Vous avez validé la justification de {_nom(employe)} pour la mission {numero}.\n"
        f"Montant : {justification.montant_total_justifie:,.0f} F CFA\n\nCordialement,\nGestion Missions"
    )
    html_c = _html(
        titre=f"Validation enregistrée — {numero}",
        couleur_titre=COLOR_SUCCESS,
        badge="VALIDÉE", badge_couleur=COLOR_SUCCESS,
        lignes_html=[
            f"Bonjour <strong>{_nom(comptable)}</strong>,",
            "Vous avez validé la justification suivante.",
            _info_block("Bénéficiaire", _nom(employe)),
            _info_block("Mission", f"{numero} — {mission.objet_mission}"),
            _info_block("Montant validé", f"{justification.montant_total_justifie:,.0f} F CFA"),
            _info_block("Date de validation", str(justification.date_validation_comptable)[:16] if justification.date_validation_comptable else "—"),
        ],
    )
    _envoyer(sujet_c, texte_c, html_c, _email(comptable))

    # Notification membre
    sujet_e = f"[Gestion Missions] Votre justification a été validée — {numero}"
    texte_e = (
        f"Bonjour {_nom(employe)},\n\n"
        f"Votre justification de frais d'hébergement pour la mission {numero} a été validée.\n"
        f"Montant : {justification.montant_total_justifie:,.0f} F CFA\n\nCordialement,\nGestion Missions"
    )
    html_e = _html(
        titre="Votre justification a été validée",
        couleur_titre=COLOR_SUCCESS,
        badge="JUSTIFICATION VALIDÉE", badge_couleur=COLOR_SUCCESS,
        lignes_html=[
            f"Bonjour <strong>{_nom(employe)}</strong>,",
            "Votre justification de frais d'hébergement a été validée par le comptable.",
            _info_block("Mission", f"{numero} — {mission.objet_mission}"),
            _info_block("Montant validé", f"<strong style='color:{COLOR_SUCCESS};'>{justification.montant_total_justifie:,.0f} F CFA</strong>"),
            _info_block("Validé par", _nom(comptable)),
            _info_block("Date", str(justification.date_validation_comptable)[:16] if justification.date_validation_comptable else "—"),
        ],
    )
    _envoyer(sujet_e, texte_e, html_e, _email(employe))
