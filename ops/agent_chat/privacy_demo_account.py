"""Explicit configuration of the existing local demo account; no provider calls.

The caller backs up the database and checks ownership/idleness before invoking
this function. Existing credentials, passwords, models and history are retained.
"""
import json


def configure():
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from front.agents.capabilities import profile_for, limits
    from front.models import (AgentModelProfile, AuditLog, Company, Conversation,
                              Rule, RulesGroup)
    from front.privacy_policy import activate_revision, simulate_revision
    from front.security_presets import TEAM_RULES, PRIVACY_CATEGORIES, PRIVACY_SAMPLE

    with transaction.atomic():
        actor = get_user_model().objects.get(pk=1, username='admin', is_active=True)
        company = Company.objects.select_for_update().get(pk=actor.profile.company_id)
        if company.pk != 3 or company.name != 'Pruebas de Javi':
            raise RuntimeError('expected_existing_demo_company_required')
        profile = AgentModelProfile.objects.select_related('connection', 'model').get(pk=profile_for(actor))
        if not (profile.professional and profile.enabled and profile.connection.active
                and profile.connection.api_key and profile.model.active):
            raise RuntimeError('configured_professional_connection_required')
        limits(profile)
        group, _ = RulesGroup.objects.get_or_create(company=company, name='Seguridad del equipo',
            defaults={'description': 'Claves, documentación interna y datos de personal.'})
        # Only the five identified legacy demo rules. Store their exact previous
        # values in the existing private audit trail; never delete a rule/history.
        expected = {
            4: 'Credenciales y claves privadas',
            5: 'Documentos marcados como confidenciales',
            6: 'Correo electrónico o DNI: pedir consentimiento',
            7: 'Prueba de bloqueo: REGULAI_TEST_BLOCK',
            8: 'Credenciales y claves privadas',
        }
        changed = []
        for row in Rule.objects.select_for_update().filter(rules_group__company=company, pk__in=expected):
            if row.name != expected[row.pk]:
                raise RuntimeError('legacy_demo_rule_changed:' + str(row.pk))
            if row.active:
                changed.append({'id': row.pk, 'active': True, 'name': row.name, 'yara_rule': row.yara_rule,
                                'action': row.action, 'severity': row.severity, 'applies_to': row.applies_to})
                row.active = False
                row.save(update_fields=['active'])
        installed = []
        for item in TEAM_RULES:
            row, created = Rule.objects.get_or_create(rules_group=group, name=item['name'],
                defaults={**item, 'applies_to': 'both', 'active': True})
            if any(getattr(row, key) != value for key, value in item.items()) or not row.active or row.applies_to != 'both':
                raise RuntimeError('existing_team_rule_differs:' + row.name)
            row.full_clean()
            installed.append({'id': row.pk, 'name': row.name, 'action': row.action})
        if changed:
            AuditLog.objects.create(company=company, user=actor, action='demo_rules_configure',
                details=json.dumps({'previous_rules': changed, 'new_rule_ids': [r['id'] for r in installed]}))
        # Preserve any existing privacy setup; do not overwrite a user's revision.
        if not company.ai_config.get('privacy'):
            review = simulate_revision(actor, {'categories': PRIVACY_CATEGORIES}, PRIVACY_SAMPLE)
            activate_revision(actor, review['revision_id'], review['review_token'])
        old_name = profile.name
        if old_name == 'Documentos con DeepSeek real':
            profile.name = 'Asistente de trabajo'
            profile.save(update_fields=['name'])
            AuditLog.objects.create(company=company, user=actor, action='demo_agent_rename',
                details=json.dumps({'profile_id': profile.pk, 'previous_name': old_name, 'name': profile.name}))
        # Empty conversations are real starting points, never fabricated answers.
        chats = []
        for title, mode in [('Contacto de ejemplo', 'chat'), ('Plan de trabajo', 'agent')]:
            chat, _ = Conversation.objects.get_or_create(user=actor, title=title, mode=mode)
            chats.append({'id': chat.pk, 'title': title, 'mode': mode})
        company.refresh_from_db()
        return {'company': company.name, 'user': actor.username, 'rules': installed,
                'privacy_revision': company.ai_config['privacy']['revision_id'],
                'agent': profile.name, 'model': profile.model.name, 'chats': chats}
