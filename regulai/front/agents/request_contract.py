"""Server-owned deliverable requirements; absence of an upload grants no mock data."""
import re
import unicodedata


def plain(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


def interpret(text, *, uploaded=False, base_format=None, general=False):
    value = plain(text)
    patterns = {'docx': r'\b(word|docx)\b', 'pdf': r'\bpdf\b',
                'xlsx': r'\b(excel|xlsx|spreadsheet|hoja de calculo)\b',
                'pptx': r'\b(pptx|powerpoint|presentacion|presentation|diapositivas|slides)\b'}
    output_text = re.sub(r'\b(?:no|sin|not|without)\s+(?:(?:un|una|an?|el|la)\s+)?(?:archivo\s+)?'
        r'(?:word|docx|pdf|excel|xlsx|powerpoint|pptx)\b', '', value)
    formats = [name for name, pattern in patterns.items() if re.search(pattern, output_text)]
    target = re.search(r'\b(?:convierte|convert|transforma|exporta|export)\b.*\b(?:a|to)\s+(.+)$', output_text)
    if target:
        formats = [name for name, pattern in patterns.items() if re.search(pattern, target[1])] or formats
    if not formats and general:
        formats = [base_format] if base_format else []
    elif not formats:
        formats = [base_format or ('xlsx' if uploaded and not re.search(r'\b(informe|report|documento)\b', value) else 'docx')]
    if not general and len(formats) > 1 and set(formats) != {'docx', 'pdf'}:
        raise ValueError('agent_multiple_formats_unsupported')
    words = {'una': 1, 'un': 1, 'one': 1, 'dos': 2, 'two': 2, 'tres': 3, 'three': 3,
             'cuatro': 4, 'four': 4, 'cinco': 5, 'five': 5, 'seis': 6, 'six': 6,
             'siete': 7, 'seven': 7, 'ocho': 8, 'eight': 8, 'nueve': 9, 'nine': 9,
             'diez': 10, 'ten': 10}
    match = re.search(r'\b(\d+|' + '|'.join(words) + r')[\s-]*(?:paginas?|pages?|diapositivas?|slides?)\b', value)
    pages = (int(match[1]) if match[1].isdigit() else words[match[1]]) if match else None
    if pages is not None and not 1 <= pages <= (200 if general else 20):
        raise ValueError('agent_page_limit')
    explicit_mock = bool(re.search(r'\b(mockup|mock|fictici\w*|sintetic\w*|inventad\w*|fictional|synthetic|dummy)\b|datos de ejemplo|sample data', value))
    # A negation can never confer permission to fabricate data.
    if re.search(r'\b(no|sin|without|never|not)\b.{0,70}\b(mockup|mock|fictici\w*|sintetic\w*|invent\w*|fictional|synthetic|dummy|datos de ejemplo|sample data)\b', value):
        explicit_mock = False
    if not general and re.search(r'\b(?:en|in)\s+(?:frances|francais|french|aleman|german|deutsch|italiano|italian|portugues|portuguese|catalan|català|chino|chinese|japones|japanese|arabe|arabic)\b', value):
        raise ValueError('agent_language_unsupported')
    language = 'en' if re.search(r'\b(ingles|english)\b', value) else 'es' if re.search(r'\b(espanol|castellano|spanish)\b', value) else (
        'en' if re.search(r'\b(create|write|report|about|please)\b', value) and not re.search(r'\b(crea|informe|sobre)\b', value) else 'es')
    return {'operation': 'edit' if base_format and base_format in formats else 'transform' if uploaded or base_format else 'create',
            'base_format': base_format,
            'formats': formats, 'pages': pages, 'language': language,
            'language_explicit': bool(re.search(r'\b(ingles|english|espanol|castellano|spanish)\b', value)),
            'allow_mock': explicit_mock,
            'research_required': bool(re.search(r'\b(actualizad\w*|actuales|actualidad|latest|current|investiga\w*|fuentes|references|citad\w*)\b', value))}


def allowed_tools(request, configured, *, base=False, source=False, narrative=False):
    formats = set(request['formats'])
    allowed = set()
    if formats <= {'docx', 'pdf'}:
        allowed = {'edit_document', 'export_pdf'} if base and narrative and request.get('base_format') in ('docx', 'pdf') else (
            {'build_document', 'edit_document', 'export_pdf'} if base and request.get('base_format') in ('docx', 'pdf') else {'build_document'})
    elif formats == {'pptx'}:
        allowed = {'edit_presentation'} if base and request.get('base_format') == 'pptx' else {'build_presentation'}
    elif formats == {'xlsx'}:
        allowed = ({'rename_excel'} if request.get('base_format') == 'xlsx' else set()) if base else (
            {'build_excel'} if source else {'create_mock_excel'} if request['allow_mock'] else set())
    if formats != {'xlsx'}:
        allowed.add('research_sources')
    return [name for name in configured if name in allowed]


def check_delivery(request, format, proof):
    if not request:  # Immutable historical revisions predate this contract.
        return
    available = {format}
    if format in ('docx', 'pdf') and proof.get('docx_sha256') and proof.get('pdf_sha256'):
        available.update(('docx', 'pdf'))
    if not set(request['formats']) <= available:
        raise ValueError('deliverable_format_mismatch')
    if request.get('pages') is not None and proof.get('pages') != request['pages']:
        raise ValueError('deliverable_page_count_mismatch')
    if proof.get('data_origin') == 'invented_sample_data' and not request.get('allow_mock') and request.get('operation') != 'edit':
        raise ValueError('invented_data_not_requested')


def verification_checks(artifact):
    proof = artifact.verification
    technical = bool(proof.get('automated_passed') or proof.get('checks') and artifact.format == 'xlsx')
    visual = isinstance(proof.get('visual_review'), dict)
    def check(status, detail):
        return {'status': status, 'detail': detail}
    return {
        'integrity': check('passed' if technical else 'failed', 'Reapertura, estructura y hashes de los bytes finales.'),
        'instructions': check('not_performed',
            'Formato y extensión contrastados con la petición; cumplimiento semántico completo no comprobado.' if proof.get('request_checked') else
            'Cumplimiento de las instrucciones no comprobado.'),
        'layout': check('passed' if visual else 'not_performed',
            ('Todas las páginas revisadas en el visor; aprobación ligada a sus hashes.' if visual else
             'Paginación y render comprobados; revisión visual pendiente.' if proof.get('pages') else
             'No se ha registrado una revisión visual de la hoja.')),
        'sources': check('not_performed',
            'Datos ficticios solicitados y etiquetados.' if proof.get('data_origin') == 'invented_sample_data' else
            'Referencias consultadas y trazadas; no se ha comprobado semánticamente cada afirmación.' if proof.get('source_ids') else
            'Sin respaldo factual externo verificado. Se distinguen análisis y limitaciones.'),
        'security': check('passed' if technical else 'not_performed',
            'Permisos, política y contenido activo comprobados en este flujo. Jev se muestra por separado.'),
    }
