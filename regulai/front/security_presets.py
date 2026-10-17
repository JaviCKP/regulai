"""Small, explicit team policies. PII treatment remains in privacy settings."""

TEAM_RULES = (
    {
        'name': 'Claves privadas', 'severity': 'critical', 'action': 'block',
        'description': 'Bloquea claves privadas PEM y OpenSSH.',
        'yara_rule': r'''rule PrivateKeys {
 strings:
  $key = /-----BEGIN (RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----/
 condition: $key
}''',
    },
    {
        'name': 'Credenciales de acceso', 'severity': 'critical', 'action': 'block',
        'description': 'Bloquea valores asignados a contraseñas, tokens y claves API.',
        'yara_rule': r'''rule AccessCredentials {
 strings:
  $assignment = /\b(api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd)[ \t]*["']?[ \t]*[:=][ \t]*["']?[A-Za-z0-9_+\/.!@#$%&*=-]{12,}/ nocase
  $bearer = /\bAuthorization[ \t]*:[ \t]*Bearer[ \t]+[A-Za-z0-9_.=-]{20,}/ nocase
 condition: any of them
}''',
    },
    {
        'name': 'Documentación interna', 'severity': 'high', 'action': 'block',
        'description': 'Bloquea documentos con una marca explícita de uso restringido.',
        'yara_rule': r'''rule InternalDocuments {
 strings:
  $header = /(^|[\r\n])[ \t]*(CONFIDENCIAL|SOLO USO INTERNO|NO COMPARTIR FUERA)([ \t]*[\r\n:]|$)/ nocase
  $document = "DOCUMENTO CONFIDENCIAL" nocase
 condition: any of them
}''',
    },
    {
        'name': 'Datos de personal', 'severity': 'high', 'action': 'consent',
        'description': 'Pide confirmación para listados de personal con salarios o nóminas.',
        'yara_rule': r'''rule PersonnelRecords {
 strings:
  $context1 = "listado de personal" nocase
  $context2 = "informe de personal" nocase
  $data1 = "salario" nocase
  $data2 = "nomina" nocase
  $data3 = "nómina" nocase
 condition: any of ($context*) and any of ($data*)
}''',
    },
)

PRIVACY_SAMPLE = ('Prepara una ficha con estos datos ficticios: Lucia Romero, '
    'lucia.romero@example.com, DNI 12345678Z, teléfono +34 612 345 678, '
    'IBAN ES91 2100 0418 4502 0005 1332 y tarjeta 4111 1111 1111 1111.')
PRIVACY_CATEGORIES = {category: 'reversible' for category in ('EMAIL', 'PHONE', 'ID', 'ACCOUNT', 'CARD')}
