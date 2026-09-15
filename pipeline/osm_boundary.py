"""Відтворюване збирання межі з повного XML relation OpenStreetMap.

Не замикає розірвані лінії навмання і не відкидає внутрішні кільця.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from src.geocode_quality import Boundary


def join_rings(segments):
    remaining = [list(s) for s in segments]
    if any(len(s) < 2 for s in remaining):
        raise ValueError('Порожній відрізок межі')
    rings = []
    while remaining:
        ring = remaining.pop(0)
        while ring[-1] != ring[0]:
            matches = [(i, s if s[0] == ring[-1] else list(reversed(s)))
                       for i, s in enumerate(remaining) if ring[-1] in (s[0], s[-1])]
            if len(matches) != 1:
                raise ValueError('Розірвана або розгалужена межа')
            index, segment = matches[0]
            ring.extend(segment[1:])
            remaining.pop(index)
        if len(ring) < 4:
            raise ValueError('Кільце має менше трьох вершин')
        rings.append(ring)
    return rings


def convert(path, reviewed_at):
    raw = Path(path).read_bytes()
    root = ET.fromstring(raw)
    matches = [r for r in root.findall('relation') if r.get('id') == '421866']
    if len(matches) != 1:
        raise ValueError('Потрібен relation 421866')
    relation = matches[0]
    tags = {t.get('k'): t.get('v') for t in relation.findall('tag')}
    if any(tags.get(k) != v for k, v in {
        'name': 'Київ', 'boundary': 'administrative', 'admin_level': '4', 'wikidata': 'Q1899',
    }.items()):
        raise ValueError('Relation не відповідає адміністративній межі Києва')
    nodes = {n.get('id'): [float(n.get('lon')), float(n.get('lat'))] for n in root.findall('node')}
    ways = {w.get('id'): [n.get('ref') for n in w.findall('nd')] for w in root.findall('way')}
    allowed = {('way', 'outer'), ('way', 'inner'), ('relation', 'subarea'),
               ('node', 'admin_centre'), ('node', 'label')}
    if any((m.get('type'), m.get('role')) not in allowed for m in relation.findall('member')):
        raise ValueError('Невідомий член relation; потрібна перевірка джерела')
    geometry_ids = [m.get('ref') for m in relation.findall('member') if m.get('type') == 'way']
    if len(geometry_ids) != len(set(geometry_ids)):
        raise ValueError('Дубльований геометричний член relation')
    assembled = {}
    for role in ('outer', 'inner'):
        members = [m for m in relation.findall('member') if m.get('role') == role]
        if any(m.get('type') != 'way' or m.get('ref') not in ways for m in members):
            raise ValueError('Відсутній або непідтримуваний член межі')
        rings = join_rings([ways[m.get('ref')] for m in members])
        assembled[role] = [[[nodes[n][0], nodes[n][1]] for n in ring] for ring in rings]
    polygons = [[ring] for ring in assembled['outer']]
    for hole in assembled['inner']:
        containers = [p for p in polygons if Boundary.ring_contains(p[0], *hole[0]) is True]
        if len(containers) != 1:
            raise ValueError('Внутрішнє кільце не має однозначного зовнішнього')
        containers[0].append(hole)
    feature = {'type': 'Feature', 'properties': {
        'name': 'Київ', 'boundary': 'administrative', 'admin_level': '4',
        'source_url': 'https://api.openstreetmap.org/api/0.6/relation/421866/full',
        'osm_relation_id': 421866, 'osm_version': int(relation.get('version')),
        'osm_timestamp': relation.get('timestamp'),
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'reviewed_at': reviewed_at, 'reviewed_by': 'assistant',
        'review_scope': 'source_identity_and_geometry', 'independent_human_review': False,
        'attribution': '© OpenStreetMap contributors', 'license': 'ODbL-1.0',
    }, 'geometry': {'type': 'MultiPolygon', 'coordinates': polygons}}
    boundary = Boundary(feature)
    centres = [m for m in relation.findall('member') if m.get('role') == 'admin_centre']
    if len(centres) != 1 or centres[0].get('ref') not in nodes:
        raise ValueError('Немає контрольного адміністративного центру')
    lon, lat = nodes[centres[0].get('ref')]
    if not boundary.contains(lat, lon):
        raise ValueError('Адміністративний центр поза зібраною межею')
    return feature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reviewed-at', required=True)
    args = parser.parse_args()
    feature = convert(args.source, args.reviewed_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(feature, out, ensure_ascii=False, separators=(',', ':'))
    print(json.dumps({'polygons': len(feature['geometry']['coordinates']),
                      'rings': sum(map(len, feature['geometry']['coordinates'])),
                      'source_sha256': feature['properties']['source_sha256']}))


if __name__ == '__main__':
    main()
