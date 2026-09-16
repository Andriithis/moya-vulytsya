"""Три допуски та приватний реєстр епізодів. Не автоматичний юридичний висновок.

Семантичний зв'язок фрагментів перевіряє аналітик; код перевіряє їх походження,
повноту та консервативні заборони. Автоматичні підказки не підтверджують епізод.
"""
import hashlib
import json
import re
from pipeline.document_scope import admission, case_key, SCOPE_VERSION
from src import addr

RULES_VERSION = 'episode-admission-v1'
POSITIVE = {'conviction', 'kupap_penalty'}
NEGATIVE = {'acquittal', 'no_event', 'no_elements', 'unproven', 'time_limit',
            'death', 'amnesty', 'decriminalized', 'transfer', 'duplicate_decision',
            'criminal_release', 'returned_materials', 'procedural'}
REVIEW = {'unknown', 'mixed_unresolved', 'minor_oral_remark'}
PRIVACY = re.compile(r'домашн\w* насильств|неповноліт|малоліт|закрит\w* судов\w* засідан|'
                     r'примусов\w* (?:заход\w* (?:медичн|виховн)|медичн)|'
                     r'статев\w* (?:злочин|свобод|недоторкан)|зґвалтуван', re.I)


def span(text, quote):
    """Фіксує однозначний дослівний фрагмент; не вгадує при повторах."""
    if not quote or text.count(quote) != 1:
        raise ValueError('Фрагмент має бути непорожнім та однозначним')
    start = text.index(quote)
    return {'start': start, 'end': start + len(quote), 'quote': quote}


def valid_span(text, value):
    return (isinstance(value, dict) and type(value.get('start')) is int
            and type(value.get('end')) is int and 0 <= value['start'] < value['end'] <= len(text)
            and text[value['start']:value['end']] == value.get('quote'))


def outcome_hint(text):
    """Тільки підказка до перегляду; навіть позитивний збіг не створює епізод."""
    patterns = [
        ('time_limit', r'закінчення.{0,50}строк|сплив.{0,30}строк'),
        ('returned_materials', r'поверну[т]\w*.{0,160}(?:дооформлен|належного оформлен)'),
        ('no_event', r'відсутніст\w*.{0,25}події.{0,40}(?:правопоруш|складу)'),
        ('no_elements', r'відсутніст\w*.{0,25}складу.{0,30}правопоруш'),
        ('minor_oral_remark', r'усн\w* зауважен'),
        ('acquittal', r'виправдати|визнати невинуват'),
        ('kupap_penalty', r'накласти.{0,60}(?:стягнення|штраф)'),
        ('conviction', r'визнати винуват|визнати винним'),
    ]
    for name, pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            return {'outcome': name, 'evidence': {'start': match.start(), 'end': match.end(), 'quote': match.group()},
                    'confirmed': False}
    return {'outcome': 'unknown', 'evidence': None, 'confirmed': False}


def assess_episode(document, text, episode, review):
    """Кожний епізод має власні особу, результат, висновок суду і місце."""
    reasons = []
    result = episode.get('outcome', 'unknown')
    evidence = episode.get('evidence', {})
    if result not in POSITIVE | NEGATIVE | REVIEW:
        raise ValueError('Невідомий результат розгляду')
    for field in ('facts', 'finding', 'disposition'):
        if not valid_span(text, evidence.get(field)):
            reasons.append('missing_' + field)
    if not episode.get('episode_id') or not episode.get('subject'):
        reasons.append('unresolved_episode_or_subject')
    if not review.get('analyst') or not review.get('reviewed_at'):
        reasons.append('missing_analyst')
    if episode.get('court_accepted') is not True:
        reasons.append('not_court_finding')
    if episode.get('scope_resolved') is not True:
        reasons.append('unresolved_charge_scope')
    mode = episode.get('procedure', 'ordinary')
    if mode not in {'ordinary', 'agreement', 'simplified'}:
        reasons.append('unknown_procedure')
    if mode in {'agreement', 'simplified'} and not valid_span(text, evidence.get('charge_scope')):
        reasons.append('missing_charge_scope')
    if result not in POSITIVE:
        reasons.append(result)
    disposition = evidence.get('disposition', {}).get('quote', '')
    if result in POSITIVE:
        guilty = re.search(r'визнати\s+(?:\S+\s+){0,8}вин(?:ним|ною|уватим|уватою)', disposition, re.I)
        penalty = re.search(r'накласти|застосувати.{0,40}стягнення', disposition, re.I | re.S)
        if (not guilty or (result == 'kupap_penalty' and not penalty)
                or re.search(r'виправдати|невинуват|провадження.{0,40}закрити|закрити.{0,40}провадження',
                             disposition, re.I | re.S)):
            reasons.append('disposition_not_positive_or_mixed')
    if (result == 'conviction' and document.get('justice_kind') != '2' or
            result == 'kupap_penalty' and document.get('justice_kind') != '5'):
        reasons.append('outcome_stream_mismatch')
    confirmed = not reasons
    location = None
    location_evidence = evidence.get('location')
    if confirmed and valid_span(text, location_evidence):
        facts = evidence['facts']
        # Посилання на адресу саме в межах підтверджених обставин епізоду.
        if (facts['start'] <= location_evidence['start'] < location_evidence['end'] <= facts['end']
                and episode.get('location_link_checked') is True):
            candidates = addr.extract_candidates(location_evidence['quote'])
            selected = addr.select_event_candidate(candidates)
            if selected:
                location = {'street': selected.street, 'house': selected.house,
                            'evidence': location_evidence}
    if not location:
        reasons.append('no_linked_event_location')
    category = 'unspecified'
    if document.get('category_code') in {'41090', '5952'}:
        subtype = episode.get('subtype')
        if subtype == 'examination_refusal' and valid_span(text, evidence.get('subtype')) and valid_span(text, evidence.get('facts')):
            if (evidence['facts']['start'] <= evidence['subtype']['start']
                    and evidence['subtype']['end'] <= evidence['facts']['end']
                    and re.search(r'відмов', evidence['subtype']['quote'], re.I)):
                category = 'examination_refusal'
        elif subtype == 'impaired_driving' and valid_span(text, evidence.get('subtype')) and valid_span(text, evidence.get('facts')):
            q = evidence['subtype']['quote']
            if (evidence['facts']['start'] <= evidence['subtype']['start']
                    and evidence['subtype']['end'] <= evidence['facts']['end']
                    and re.search(r'керува', q, re.I)
                    and re.search(r'стані.{0,30}сп[’\x27]яніння', q, re.I)
                    and not re.search(r'відмов|ознаками', q, re.I)):
                category = 'impaired_driving'
        if category == 'unspecified':
            reasons.append('article_130_subtype_unverified')
    else:
        category = document.get('category_code')
    # Позитивна розмітка не обходить текстові приватні виключення.
    if PRIVACY.search(text) or episode.get('privacy_checked') is not True:
        reasons.append('privacy_unverified_or_excluded')
    if episode.get('location_privacy_checked') is not True:
        reasons.append('location_privacy_unverified')
    finality = episode.get('finality', {})
    finality_quote = finality.get('evidence', {}).get('quote', '')
    if (finality.get('status') != 'verified' or not finality.get('verified_by')
            or not valid_span(text, finality.get('evidence'))
            or finality.get('basis') != 'explicit_effective_statement'
            or not re.search(r'(?:набрав|набрала|набрало) законної сили\s+\d{2}\.\d{2}\.\d{4}', finality_quote, re.I)
            or re.search(r'\bне\b|якщо|після|у разі|після закінчення', finality_quote, re.I)):
        reasons.append('finality_unverified')
    # Геометрична межа та допустима точність перевіряються окремо від суду/тексту.
    if episode.get('geocode_verified') is not True or episode.get('within_kyiv_verified') is not True:
        reasons.append('geography_unverified')
    return {'episode_id': episode.get('episode_id'), 'subject': episode.get('subject'),
            'outcome': result, 'confirmed': confirmed, 'category': category,
            'location': location, 'evidence': evidence, 'finality': finality,
            'publication_allowed': not reasons, 'reasons': reasons,
            'rules_version': RULES_VERSION}


def analyze_document(document, text, review=None):
    digest = hashlib.sha256(text.encode()).hexdigest()
    reason = admission(document.get('justice_kind'), document.get('judgment_code'),
                       document.get('category_code'), document.get('instance_code'))
    result = {'doc_id': document['doc_id'], 'case_number': document.get('case_number'),
              'source_url': document['source_url'], 'source_row_hash': document['source_row_hash'],
              'text_sha256': digest, 'scope_version': SCOPE_VERSION, 'rules_version': RULES_VERSION,
              'admission': reason, 'hint': outcome_hint(text), 'episodes': [],
              'publication_allowed': False, 'review_kind': 'unreviewed'}
    if reason != 'analysis_candidate' or not review:
        return result
    if (review.get('text_sha256') != digest or review.get('source_row_hash') != document['source_row_hash']
            or review.get('doc_id') != document['doc_id'] or review.get('rules_version') != RULES_VERSION):
        raise ValueError('Розмітка не відповідає джерелу або версії правил')
    episodes = review.get('episodes', [])
    keys = [e.get('episode_id') for e in episodes]
    if len(set(keys)) != len(keys):
        raise ValueError('Повторний епізод у розмітці')
    result['review_kind'] = review.get('review_kind', 'analyst_development')
    result['episodes'] = [assess_episode(document, text, e, review) for e in episodes]
    result['publication_allowed'] = any(e['publication_allowed'] for e in result['episodes'])
    return result


def init_ledger(conn):
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS episode_ledger(
          event_id TEXT PRIMARY KEY, case_key TEXT NOT NULL, episode_key TEXT NOT NULL,
          source_document TEXT NOT NULL, payload TEXT NOT NULL, eligible INTEGER NOT NULL,
          UNIQUE(case_key,episode_key));
        CREATE TABLE IF NOT EXISTS case_changes(
          change_id TEXT PRIMARY KEY, case_key TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE VIEW IF NOT EXISTS public_episode_counts AS
          SELECT case_key, count(*) AS count FROM episode_ledger WHERE eligible=1 GROUP BY case_key;
    ''')


def store_analysis(conn, analysis):
    """Повний повтор документа замінює його епізоди й прибирає застарілі."""
    key = case_key(analysis.get('case_number'))
    if not key:
        raise ValueError('Немає ідентичності справи')
    with conn:
        conn.execute('DELETE FROM episode_ledger WHERE source_document=?', (analysis['doc_id'],))
        for e in analysis['episodes']:
            if not e['episode_id']:
                continue
            event_id = hashlib.sha256(f"{key}|{e['episode_id']}".encode()).hexdigest()
            existing = conn.execute('SELECT source_document FROM episode_ledger WHERE event_id=?', (event_id,)).fetchone()
            if existing and existing[0] != analysis['doc_id']:
                raise ValueError('Два основні документи епізоду: потрібне явне узгодження')
            eligible = e['publication_allowed']
            for (payload,) in conn.execute('SELECT payload FROM case_changes WHERE case_key=?', (key,)):
                change = json.loads(payload)
                if change['action'] in {'cancelled', 'punishment_changed'} and (
                        change.get('episode_ids') is None or e['episode_id'] in change['episode_ids']):
                    eligible = False
            payload = {**e, 'provenance': {k: analysis[k] for k in
                       ('doc_id', 'source_url', 'source_row_hash', 'text_sha256', 'review_kind')}}
            conn.execute('INSERT OR REPLACE INTO episode_ledger VALUES(?,?,?,?,?,?)',
                         (event_id, key, e['episode_id'], analysis['doc_id'], json.dumps(payload, ensure_ascii=False), int(eligible)))


def apply_case_change(conn, change, text):
    """Перевірений зв'язок апеляції/касації; подання скарги не є скасуванням.

    Зміна покарання консервативно призупиняє допуск до окремої перевірки фактів.
    Немає автоматичного пошуку чи автоматичного відновлення після скасування.
    """
    if (change.get('action') not in {'cancelled', 'punishment_changed', 'appeal_upheld', 'cassation_filed'}
            or not change.get('source_url') or not change.get('doc_id') or not change.get('verified_by')
            or change.get('text_sha256') != hashlib.sha256(text.encode()).hexdigest()
            or not valid_span(text, change.get('evidence')) or not change.get('case_link_checked')
            or not case_key(change.get('case_number'))):
        raise ValueError('Неперевірена зміна справи')
    key = case_key(change['case_number'])
    change_id = str(change['doc_id'])
    payload = json.dumps(change, ensure_ascii=False, sort_keys=True)
    with conn:
        old = conn.execute('SELECT payload FROM case_changes WHERE change_id=?', (change_id,)).fetchone()
        if old and old[0] != payload:
            raise ValueError('Зміна вже застосованого рішення потребує окремого перегляду')
        conn.execute('INSERT OR IGNORE INTO case_changes VALUES(?,?,?)', (change_id, key, payload))
        if change['action'] in {'cancelled', 'punishment_changed'}:
            if change.get('episode_ids') is None:
                conn.execute('UPDATE episode_ledger SET eligible=0 WHERE case_key=?', (key,))
            else:
                for episode in change['episode_ids']:
                    conn.execute('UPDATE episode_ledger SET eligible=0 WHERE case_key=? AND episode_key=?', (key, episode))
