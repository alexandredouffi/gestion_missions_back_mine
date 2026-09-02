from django.core.mail import EmailMultiAlternatives
from django.conf import settings

FROM = settings.DEFAULT_FROM_EMAIL
import os
import requests

BREVO_API_KEY = settings.BREVO_API_KEY
FROM_EMAIL = FROM
FROM_NAME = "GEMA"

def envoyer_mail_brevo(subject, html_content, recipients, text_content=""):
    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "name": FROM_NAME,
            "email": FROM_EMAIL,
        },
        "to": [{"email": email} for email in recipients if email],
        "subject": subject,
        "htmlContent": html_content,
    }

    if text_content:
        payload["textContent"] = text_content

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
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

def _html(titre, couleur_titre, lignes_html, badge=None, badge_couleur=None, cta_label=None, cta_url=None):
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
        href = cta_url or '#'
        cta_html = f'''
        <div style="text-align:center;margin:28px 0 0 0;">
          <a href="{href}" style="display:inline-block;background:{COLOR_ACCENT};color:#fff;
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


def _envoyer(subject, texte, html, *recipients):
    valides = [e for e in recipients if e]
    if not valides:
        _log(subject, [], 'IGNORE')
        return
    try:
        # msg = EmailMultiAlternatives(subject, texte, FROM, valides)
        # msg.attach_alternative(html, 'text/html')
        # msg.send()
        envoyer_mail_brevo(subject, html, valides, text_content="")
        _log(subject, valides, 'ENVOYE')
    except Exception as exc:
        _log(subject, valides, 'ECHEC', erreur=str(exc))


# ── 0 bis. Définition du mot de passe ───────────────────────────────────────

def notifier_lien_mot_de_passe(user, url, duree_heures, motif='CREATION'):
    """Envoie le lien à usage unique permettant de définir son mot de passe."""
    creation = motif == 'CREATION'

    sujet = (
        "[Gestion Missions] Activez votre compte"
        if creation else
        "[Gestion Missions] Réinitialisation de votre mot de passe"
    )

    intro = (
        "Un compte vient d'être créé pour vous sur Gestion Missions."
        if creation else
        "Une réinitialisation de votre mot de passe a été demandée."
    )

    texte = (
        f"Bonjour {_nom(user)},\n\n"
        f"{intro}\n\n"
        f"Définissez votre mot de passe en ouvrant le lien ci-dessous :\n{url}\n\n"
        f"Identifiant : {user.username}\n"
        f"Ce lien est valable {duree_heures} heures et ne peut être utilisé qu'une seule fois.\n\n"
        f"Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
        f"Cordialement,\nGestion Missions"
    )

    bloc_bouton = (
        f'<div style="text-align:center;margin:28px 0;">'
        f'<a href="{url}" style="display:inline-block;background:{COLOR_ACCENT};color:#fff;'
        f'padding:14px 36px;border-radius:6px;font-size:15px;font-weight:600;'
        f'text-decoration:none;">Définir mon mot de passe</a></div>'
    )

    bloc_lien = (
        f'<div style="background:{COLOR_LIGHT};border-radius:6px;padding:14px 16px;margin:20px 0;">'
        f'<p style="margin:0 0 6px 0;font-size:12px;color:{COLOR_MUTED};font-weight:600;">'
        f'Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :</p>'
        f'<p style="margin:0;font-size:12px;word-break:break-all;">'
        f'<a href="{url}" style="color:{COLOR_ACCENT};text-decoration:none;">{url}</a></p>'
        f'</div>'
    )

    bloc_expiration = (
        f'<div style="text-align:center;margin:20px 0 0;">'
        f'<span style="display:inline-block;background:#FFF3CD;border:1px solid #FFEAA7;'
        f'border-radius:20px;padding:8px 20px;font-size:13px;font-weight:600;color:#856404;">'
        f'⏱&nbsp; Ce lien expire dans <strong>{duree_heures} heures</strong></span></div>'
    )

    bloc_securite = (
        f'<div style="background:{COLOR_LIGHT};border-left:3px solid {COLOR_MUTED};'
        f'border-radius:4px;padding:12px 16px;margin-top:20px;">'
        f'<p style="margin:0;font-size:12px;color:{COLOR_MUTED};">'
        f'🔒 <strong>Sécurité :</strong> ce lien est personnel et à usage unique. '
        f"Ne le transmettez à personne. Gestion Missions ne vous demandera jamais "
        f"votre mot de passe par email.</p>"
        f'</div>'
    )

    html = _html(
        titre="Définissez votre mot de passe",
        couleur_titre=COLOR_PRIMARY,
        badge="ACTIVATION DU COMPTE" if creation else "RÉINITIALISATION",
        badge_couleur=COLOR_ACCENT if creation else COLOR_WARNING,
        lignes_html=[
            f"Bonjour <strong>{_nom(user)}</strong>,",
            intro + " Pour y accéder, vous devez d'abord choisir votre mot de passe.",
            _info_block("Identifiant de connexion", user.username),
            bloc_bouton,
            bloc_lien,
            bloc_expiration,
            bloc_securite,
        ],
    )
    _envoyer(sujet, texte, html, _email(user))


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


def collecter_contexte_retrait_delegation(delegation):
    """
    À appeler AVANT la suppression d'une délégation : capture les données qui
    vont disparaître, y compris ce que la cascade va effacer (paiement,
    justification d'hébergement et ses pièces).
    """
    contexte = {
        'mission': delegation.mission,
        'employe': delegation.employe,
        'montant_total': delegation.montant_total,
        'etait_chef': delegation.est_chef,
        'paiement': None,
        'justification': None,
    }

    paiement = getattr(delegation, 'paiement', None)
    if paiement is not None:
        contexte['paiement'] = {
            'mode': paiement.get_mode_display(),
            'montant': paiement.montant,
            'reference': paiement.reference_cheque,
            'effectue': paiement.effectue,
            'enregistre_par': paiement.enregistre_par,
        }

    justification = getattr(delegation, 'justification_hebergement', None)
    if justification is not None:
        contexte['justification'] = {
            'montant': justification.montant_total_justifie,
            'nb_pieces': justification.pieces.count(),
            'validee_par': justification.valide_par_comptable,
        }

    return contexte


def notifier_retrait_delegation(contexte, auteur):
    """Notifie le retrait d'un membre de délégation. `contexte` vient de
    collecter_contexte_retrait_delegation(), appelée avant la suppression."""
    mission = contexte['mission']
    employe = contexte['employe']
    paiement = contexte['paiement']
    justification = contexte['justification']
    numero = mission.numero_mission

    # La suppression d'un paiement est le cas le plus grave.
    if paiement:
        badge, badge_couleur, couleur = "PAIEMENT SUPPRIMÉ", COLOR_DANGER, COLOR_DANGER
    elif justification or contexte['etait_chef']:
        badge, badge_couleur, couleur = "MEMBRE RETIRÉ", COLOR_WARNING, COLOR_WARNING
    else:
        badge, badge_couleur, couleur = "MEMBRE RETIRÉ", COLOR_MUTED, COLOR_PRIMARY

    alertes_html, alertes_texte = [], []

    if contexte['etait_chef']:
        alertes_html.append(
            f'<div style="background:#FFF3CD;border-left:3px solid {COLOR_WARNING};'
            f'border-radius:4px;padding:12px 16px;margin:16px 0;">'
            f'<p style="margin:0;font-size:13px;color:#856404;">'
            f'⚠️ Ce membre était <strong>chef de délégation</strong>. '
            f'La mission n\'a plus de chef désigné.</p></div>'
        )
        alertes_texte.append("ATTENTION : ce membre était chef de délégation. "
                             "La mission n'a plus de chef désigné.")

    if paiement:
        details = f"{paiement['mode']} — {paiement['montant']:,.0f} F CFA"
        if paiement['reference']:
            details += f" (réf. {paiement['reference']})"
        etat = "déjà effectué" if paiement['effectue'] else "non encore effectué"
        alertes_html.append(
            f'<div style="background:#FDEDEC;border-left:3px solid {COLOR_DANGER};'
            f'border-radius:4px;padding:12px 16px;margin:16px 0;">'
            f'<p style="margin:0;font-size:13px;color:{COLOR_DANGER};">'
            f'⚠️ <strong>Un paiement enregistré a été supprimé</strong> avec ce membre : '
            f'{details}, {etat}.</p></div>'
        )
        alertes_texte.append(f"ATTENTION : un paiement enregistré a été supprimé "
                             f"avec ce membre : {details}, {etat}.")

    if justification:
        detail_valid = ""
        if justification['validee_par']:
            detail_valid = f", validée par {_nom(justification['validee_par'])}"
        alertes_html.append(
            f'<div style="background:#FDEDEC;border-left:3px solid {COLOR_DANGER};'
            f'border-radius:4px;padding:12px 16px;margin:16px 0;">'
            f'<p style="margin:0;font-size:13px;color:{COLOR_DANGER};">'
            f'⚠️ <strong>La justification d\'hébergement a été supprimée</strong> : '
            f'{justification["nb_pieces"]} pièce(s) pour '
            f'{justification["montant"]:,.0f} F CFA{detail_valid}.</p></div>'
        )
        alertes_texte.append(
            f"ATTENTION : la justification d'hébergement a été supprimée : "
            f"{justification['nb_pieces']} pièce(s) pour "
            f"{justification['montant']:,.0f} F CFA{detail_valid}.")

    def _lignes(destinataire, intro):
        return [
            f"Bonjour <strong>{_nom(destinataire)}</strong>,",
            intro,
            _info_block("Référence", numero),
            _info_block("Objet", mission.objet_mission),
            _info_block("Période", f"Du {mission.date_depart} au {mission.date_retour}"),
            _info_block("Lieu", mission.lieu_mission),
            _info_block("Membre retiré", _nom(employe)),
            _info_block("Retiré par", _nom(auteur)),
            _info_block("Indemnités annulées", f"{contexte['montant_total']:,.0f} F CFA"),
            *alertes_html,
        ]

    texte_commun = (
        f"Mission : {numero} — {mission.objet_mission}\n"
        f"Période : du {mission.date_depart} au {mission.date_retour}\n"
        f"Membre retiré : {_nom(employe)}\n"
        f"Retiré par : {_nom(auteur)}\n"
        f"Indemnités annulées : {contexte['montant_total']:,.0f} F CFA\n"
        + ''.join(f"{a}\n" for a in alertes_texte)
    )

    destinataires = []

    # 1. Le membre retiré
    if employe.pk != auteur.pk:
        destinataires.append((
            employe,
            f"[Gestion Missions] Vous avez été retiré de la mission {numero}",
            "Vous avez été retiré(e) de la délégation de la mission suivante.",
            "Vous avez été retiré(e) de la délégation de la mission suivante.",
            "Retrait de la délégation",
        ))

    # 2. Le demandeur de la mission
    demandeur = mission.demandeur
    if demandeur.pk not in (auteur.pk, employe.pk):
        destinataires.append((
            demandeur,
            f"[Gestion Missions] Membre retiré de la délégation — {numero}",
            f"<strong>{_nom(employe)}</strong> a été retiré(e) de la délégation de votre mission.",
            f"{_nom(employe)} a été retiré(e) de la délégation de votre mission.",
            "Membre retiré de la délégation",
        ))

    # 3. Le trésorier qui avait enregistré le paiement supprimé
    if paiement and paiement['enregistre_par']:
        tresorier = paiement['enregistre_par']
        if tresorier.pk not in (auteur.pk, employe.pk, demandeur.pk):
            destinataires.append((
                tresorier,
                f"[Gestion Missions] Paiement supprimé suite à un retrait de délégation — {numero}",
                f"Le paiement que vous avez enregistré pour <strong>{_nom(employe)}</strong> "
                f"a été supprimé : ce membre a été retiré de la délégation.",
                f"Le paiement que vous avez enregistré pour {_nom(employe)} a été supprimé : "
                f"ce membre a été retiré de la délégation.",
                "Paiement supprimé",
            ))

    for destinataire, sujet, intro_html, intro_texte, titre in destinataires:
        texte = (
            f"Bonjour {_nom(destinataire)},\n\n{intro_texte}\n\n"
            f"{texte_commun}\nCordialement,\nGestion Missions"
        )
        html = _html(
            titre=titre,
            couleur_titre=couleur,
            badge=badge, badge_couleur=badge_couleur,
            lignes_html=_lignes(destinataire, intro_html),
        )
        _envoyer(sujet, texte, html, _email(destinataire))


def notifier_suppleance(suppleance, auteur, evenement='CREATION'):
    """Prévient le suppléant et le titulaire de l'ouverture ou de la fin d'une suppléance."""
    titulaire = suppleance.titulaire
    suppleant = suppleance.suppleant
    creation = evenement == 'CREATION'

    periode = (f"du {suppleance.date_debut:%d/%m/%Y %H:%M} "
               f"au {suppleance.date_fin:%d/%m/%Y %H:%M}")

    couleur = COLOR_ACCENT if creation else COLOR_MUTED
    badge = "SUPPLÉANCE OUVERTE" if creation else "SUPPLÉANCE TERMINÉE"

    infos = [
        _info_block("Titulaire", _nom(titulaire)),
        _info_block("Suppléant", _nom(suppleant)),
        _info_block("Période", periode),
        _info_block("Motif", suppleance.motif or "—"),
        _info_block("Déclarée par", _nom(auteur)),
    ]

    texte_commun = (
        f"Titulaire : {_nom(titulaire)}\n"
        f"Suppléant : {_nom(suppleant)}\n"
        f"Période : {periode}\n"
        f"Motif : {suppleance.motif or '—'}\n"
        f"Déclarée par : {_nom(auteur)}\n"
    )

    # ── Au suppléant ───────────────────────────────────────────────────────
    if creation:
        sujet_s = "[Gestion Missions] Vous êtes désigné suppléant"
        intro_s = (f"<strong>{_nom(titulaire)}</strong> vous a désigné pour traiter "
                   f"ses validations de mission pendant son absence.")
    else:
        sujet_s = "[Gestion Missions] Fin de votre suppléance"
        intro_s = (f"Votre suppléance pour <strong>{_nom(titulaire)}</strong> a pris fin. "
                   f"Ses validations lui reviennent.")

    html_s = _html(
        titre="Suppléance de signature",
        couleur_titre=couleur,
        badge=badge, badge_couleur=couleur,
        lignes_html=[f"Bonjour <strong>{_nom(suppleant)}</strong>,", intro_s, *infos],
    )
    _envoyer(
        sujet_s,
        f"Bonjour {_nom(suppleant)},\n\n"
        + ("Vous avez été désigné suppléant pour les validations de mission.\n\n"
           if creation else "Votre suppléance a pris fin.\n\n")
        + texte_commun + "\nCordialement,\nGestion Missions",
        html_s, _email(suppleant),
    )

    # ── Au titulaire, s'il n'est pas l'auteur ──────────────────────────────
    if titulaire.pk != auteur.pk:
        sujet_t = ("[Gestion Missions] Une suppléance a été ouverte pour vous"
                   if creation else "[Gestion Missions] Votre suppléance a été clôturée")
        intro_t = (f"<strong>{_nom(auteur)}</strong> a désigné "
                   f"<strong>{_nom(suppleant)}</strong> pour traiter vos validations "
                   f"pendant votre absence." if creation else
                   f"<strong>{_nom(auteur)}</strong> a mis fin à la suppléance "
                   f"assurée par <strong>{_nom(suppleant)}</strong>.")
        html_t = _html(
            titre="Suppléance de signature",
            couleur_titre=couleur,
            badge=badge, badge_couleur=couleur,
            lignes_html=[f"Bonjour <strong>{_nom(titulaire)}</strong>,", intro_t, *infos],
        )
        _envoyer(
            sujet_t,
            f"Bonjour {_nom(titulaire)},\n\n{texte_commun}\n"
            f"Cordialement,\nGestion Missions",
            html_t, _email(titulaire),
        )


# ── 3. Traitement d'une étape workflow ──────────────────────────────────────

def notifier_traitement_mission(etape, signataire):
    from .models import MissionWorkflow
    mission = etape.mission
    nouveau_statut = etape.statut
    numero = mission.numero_mission
    objet = mission.objet_mission
    est_approuve = nouveau_statut == 'APPROUVE'

    # Suppléance : l'action a-t-elle été faite pour le compte d'un autre ?
    titulaire = etape.user_validation if etape.suppleance_id else None
    if titulaire is not None and titulaire.pk == signataire.pk:
        titulaire = None
    mention_suppleance = (
        f" pour le compte de <strong>{_nom(titulaire)}</strong>" if titulaire else ""
    )
    bloc_suppleance = (
        [_info_block("Agissant pour", f"{_nom(titulaire)} (suppléance)")] if titulaire else []
    )

    # Confirmation au signataire
    action_label = "approuvé" if est_approuve else "rejeté"
    couleur_action = COLOR_SUCCESS if est_approuve else COLOR_DANGER
    badge_action = "APPROUVÉ" if est_approuve else "REJETÉ"

    sujet_sig = f"[Gestion Missions] Confirmation de votre action — {numero}"
    texte_sig = (
        f"Bonjour {_nom(signataire)},\n\n"
        f"Vous avez {action_label} l'étape « {etape.libelle_etape} » pour la mission {numero}"
        + (f", pour le compte de {_nom(titulaire)}." if titulaire else ".") + "\n"
        f"Date : {etape.date_validation}\n\nCordialement,\nGestion Missions"
    )
    html_sig = _html(
        titre=f"Étape {action_label}e — {numero}",
        couleur_titre=couleur_action,
        badge=f"ÉTAPE {badge_action}", badge_couleur=couleur_action,
        lignes_html=[
            f"Bonjour <strong>{_nom(signataire)}</strong>,",
            f"Vous avez <strong>{action_label}</strong> l'étape "
            f"<strong>« {etape.libelle_etape} »</strong>{mention_suppleance} "
            f"pour la mission suivante.",
            _info_block("Référence", numero),
            _info_block("Objet", objet),
            *bloc_suppleance,
            _info_block("Date de traitement", str(etape.date_validation)[:16] if etape.date_validation else "—"),
            *([] if est_approuve else [_info_block("Motif", etape.commentaire or "Aucun commentaire")]),
        ],
    )
    _envoyer(sujet_sig, texte_sig, html_sig, _email(signataire))

    # Le titulaire absent doit savoir ce qui a été signé en son nom.
    if titulaire is not None:
        sujet_t = f"[Gestion Missions] Étape traitée en votre nom — {numero}"
        texte_t = (
            f"Bonjour {_nom(titulaire)},\n\n"
            f"{_nom(signataire)}, votre suppléant, a {action_label} l'étape "
            f"« {etape.libelle_etape} » de la mission {numero} en votre nom.\n"
            f"Date : {etape.date_validation}\n"
            + (f"Motif : {etape.commentaire or 'Aucun commentaire'}\n" if not est_approuve else "")
            + "\nCordialement,\nGestion Missions"
        )
        html_t = _html(
            titre=f"Étape traitée en votre nom — {numero}",
            couleur_titre=couleur_action,
            badge="TRAITÉ PAR VOTRE SUPPLÉANT", badge_couleur=couleur_action,
            lignes_html=[
                f"Bonjour <strong>{_nom(titulaire)}</strong>,",
                f"<strong>{_nom(signataire)}</strong>, votre suppléant, a "
                f"<strong>{action_label}</strong> l'étape "
                f"<strong>« {etape.libelle_etape} »</strong> en votre nom.",
                _info_block("Référence", numero),
                _info_block("Objet", objet),
                _info_block("Traité par", _nom(signataire)),
                _info_block("Date de traitement", str(etape.date_validation)[:16] if etape.date_validation else "—"),
                *([] if est_approuve else [_info_block("Motif", etape.commentaire or "Aucun commentaire")]),
            ],
        )
        _envoyer(sujet_t, texte_t, html_t, _email(titulaire))

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


def notifier_piece_retiree(justification, libelle, montant, auteur, etait_complete):
    """Alerte le comptable (et l'employé) qu'une pièce justificative a été retirée."""
    from .models import User

    delegation = justification.delegation
    mission = delegation.mission
    employe = delegation.employe
    numero = mission.numero_mission

    total = justification.montant_total_justifie
    attendu = delegation.montant_hebergement
    reste = attendu - total
    deja_validee = justification.valide_par_comptable is not None

    if deja_validee:
        badge, badge_couleur, couleur = "RETRAIT APRÈS VALIDATION", COLOR_DANGER, COLOR_DANGER
    elif etait_complete:
        badge, badge_couleur, couleur = "JUSTIFICATION INCOMPLÈTE", COLOR_WARNING, COLOR_WARNING
    else:
        badge, badge_couleur, couleur = "PIÈCE RETIRÉE", COLOR_MUTED, COLOR_PRIMARY

    alerte = ''
    if deja_validee:
        alerte = (
            f'<div style="background:#FDEDEC;border-left:3px solid {COLOR_DANGER};'
            f'border-radius:4px;padding:12px 16px;margin:16px 0;">'
            f'<p style="margin:0;font-size:13px;color:{COLOR_DANGER};">'
            f'⚠️ <strong>Attention :</strong> cette justification avait déjà été validée par '
            f'{_nom(justification.valide_par_comptable)}. Le montant justifié ne couvre '
            f'plus nécessairement le montant dû.</p></div>'
        )
    elif etait_complete:
        alerte = (
            f'<div style="background:#FFF3CD;border-left:3px solid {COLOR_WARNING};'
            f'border-radius:4px;padding:12px 16px;margin:16px 0;">'
            f'<p style="margin:0;font-size:13px;color:#856404;">'
            f'⚠️ La justification était complète : elle ne l\'est plus et ne peut plus '
            f'être validée en l\'état.</p></div>'
        )

    def _lignes(destinataire, intro):
        lignes = [
            f"Bonjour <strong>{_nom(destinataire)}</strong>,",
            intro,
            _info_block("Mission", f"{numero} — {mission.objet_mission}"),
            _info_block("Bénéficiaire", _nom(employe)),
            _info_block("Pièce retirée", f"{libelle} — {montant:,.0f} F CFA"),
            _info_block("Retirée par", _nom(auteur)),
            _info_block("Montant justifié restant", f"{total:,.0f} F CFA"),
            _info_block("Montant attendu", f"{attendu:,.0f} F CFA"),
        ]
        if reste > 0:
            lignes.append(_info_block(
                "Reste à justifier",
                f"<strong style='color:{COLOR_DANGER};'>{reste:,.0f} F CFA</strong>"))
        if alerte:
            lignes.append(alerte)
        return lignes

    texte_commun = (
        f"Pièce retirée : {libelle} — {montant:,.0f} F CFA\n"
        f"Mission : {numero}\n"
        f"Bénéficiaire : {_nom(employe)}\n"
        f"Retirée par : {_nom(auteur)}\n"
        f"Montant justifié restant : {total:,.0f} F CFA sur {attendu:,.0f} F CFA attendus\n"
        + (f"Reste à justifier : {reste:,.0f} F CFA\n" if reste > 0 else "")
        + ("ATTENTION : cette justification avait déjà été validée.\n" if deja_validee else "")
    )

    # ── Comptables de la filiale ───────────────────────────────────────────
    comptables = User.objects.filter(
        profil__nom='Comptable',
        filiales_attribuees=mission.entite,
        is_active=True,
    )
    for comptable in comptables:
        if comptable.pk == auteur.pk:
            continue
        sujet = f"[Gestion Missions] Pièce justificative retirée — {numero}"
        texte = (
            f"Bonjour {_nom(comptable)},\n\n"
            f"Une pièce justificative a été retirée d'un dossier de votre filiale.\n\n"
            f"{texte_commun}\nCordialement,\nGestion Missions"
        )
        html = _html(
            titre="Pièce justificative retirée",
            couleur_titre=couleur,
            badge=badge, badge_couleur=badge_couleur,
            lignes_html=_lignes(
                comptable,
                "Une pièce justificative vient d'être retirée d'un dossier d'hébergement "
                "de votre filiale."),
        )
        _envoyer(sujet, texte, html, _email(comptable))

    # ── L'employé, si le retrait vient de quelqu'un d'autre ────────────────
    if auteur.pk != employe.pk:
        sujet = f"[Gestion Missions] Une pièce de votre justification a été retirée — {numero}"
        texte = (
            f"Bonjour {_nom(employe)},\n\n"
            f"Une pièce de votre justification de frais d'hébergement a été retirée.\n\n"
            f"{texte_commun}\nCordialement,\nGestion Missions"
        )
        html = _html(
            titre="Une pièce de votre justification a été retirée",
            couleur_titre=couleur,
            badge=badge, badge_couleur=badge_couleur,
            lignes_html=_lignes(
                employe,
                "Une pièce de votre justification de frais d'hébergement a été retirée."),
        )
        _envoyer(sujet, texte, html, _email(employe))


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
