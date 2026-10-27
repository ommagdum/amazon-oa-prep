#!/usr/bin/env python3
"""
Merges csv/1.csv, csv/2.csv, csv/3.csv into questions.js
Strategy:
  - Use csv/3.csv as the primary source (has ID, Topics, Timeframe, Frequency)
  - Enrich with data from csv/1.csv (higher-granularity frequency score)
  - Normalize difficulty to Title Case, frequency to float 0-100
  - Deduplicate by (slug from URL), keeping highest-frequency entry
  - Output: questions.js with `const QUESTIONS = [...]`
"""

import csv
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))


def slugify(url: str) -> str:
    url = url.strip().rstrip('/')
    return url.split('/')[-1]


def parse_freq(val: str) -> float:
    if not val:
        return 0.0
    val = val.strip().rstrip('%')
    try:
        return float(val)
    except ValueError:
        return 0.0


def normalize_difficulty(d: str) -> str:
    d = d.strip()
    dl = d.lower()
    if dl == 'easy':
        return 'Easy'
    elif dl == 'medium':
        return 'Medium'
    elif dl == 'hard':
        return 'Hard'
    return d.title()


def parse_topics(raw: str) -> list:
    raw = raw.strip().strip('"')
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


# Load CSV 1
csv1_by_slug = {}
with open(os.path.join(BASE, 'csv', '1.csv'), newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if not row.get('Link', '').strip():
            continue
        slug = slugify(row['Link'])
        freq = parse_freq(row.get('Frequency', ''))
        acc_raw = row.get('Acceptance Rate', '0') or '0'
        try:
            acc = round(float(acc_raw) * 100, 1)
        except ValueError:
            acc = 0.0
        csv1_by_slug[slug] = {
            'frequency': freq,
            'acceptance': acc,
            'topics': parse_topics(row.get('Topics', '')),
        }

# Load CSV 2
csv2_by_slug = {}
with open(os.path.join(BASE, 'csv', '2.csv'), newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if not row.get('URL', '').strip():
            continue
        slug = slugify(row['URL'])
        lc_id_raw = row.get('ID', '').strip()
        lc_id = int(lc_id_raw) if lc_id_raw.isdigit() else None
        csv2_by_slug[slug] = {
            'id': lc_id,
            'frequency': parse_freq(row.get('Frequency %', '')),
            'acceptance': parse_freq(row.get('Acceptance %', '')),
        }

# Load CSV 3 as primary
seen_slugs = {}
with open(os.path.join(BASE, 'csv', '3.csv'), newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        url = row.get('URL', '').strip()
        title = row.get('Title', '').strip()
        if not url or not title:
            continue
        slug = slugify(url)
        difficulty = normalize_difficulty(row.get('Difficulty', ''))
        freq3 = parse_freq(row.get('Frequency %', ''))
        acc3 = parse_freq(row.get('Acceptance %', ''))
        topics3 = parse_topics(row.get('Topics', ''))
        timeframe = row.get('Timeframe', '').strip()
        lc_id_raw = row.get('ID', '').strip()
        lc_id = int(lc_id_raw) if lc_id_raw.isdigit() else None

        c1 = csv1_by_slug.get(slug, {})
        c2 = csv2_by_slug.get(slug, {})

        frequency = c1.get('frequency') or freq3 or c2.get('frequency') or 0.0
        acceptance = c1.get('acceptance') or acc3 or c2.get('acceptance') or 0.0
        topics = c1.get('topics') or topics3 or []
        lc_id = lc_id or c2.get('id')

        entry = {
            'slug': slug,
            'id': lc_id,
            'title': title,
            'difficulty': difficulty,
            'frequency': round(frequency, 1),
            'acceptance': round(acceptance, 1),
            'topics': topics,
            'timeframe': timeframe,
            'url': f'https://leetcode.com/problems/{slug}',
        }

        if slug not in seen_slugs or frequency > seen_slugs[slug]['frequency']:
            seen_slugs[slug] = entry

# Add CSV1-only entries
for slug, c1 in csv1_by_slug.items():
    if slug in seen_slugs:
        continue
    c2 = csv2_by_slug.get(slug, {})
    title = slug.replace('-', ' ').title()
    seen_slugs[slug] = {
        'slug': slug,
        'id': c2.get('id'),
        'title': title,
        'difficulty': 'Medium',
        'frequency': round(c1.get('frequency', 0.0), 1),
        'acceptance': round(c1.get('acceptance', 0.0), 1),
        'topics': c1.get('topics', []),
        'timeframe': 'all',
        'url': f'https://leetcode.com/problems/{slug}',
    }

# Add CSV2-only entries
for slug, c2 in csv2_by_slug.items():
    if slug in seen_slugs:
        continue
    title = slug.replace('-', ' ').title()
    seen_slugs[slug] = {
        'slug': slug,
        'id': c2.get('id'),
        'title': title,
        'difficulty': 'Medium',
        'frequency': round(c2.get('frequency', 0.0), 1),
        'acceptance': round(c2.get('acceptance', 0.0), 1),
        'topics': [],
        'timeframe': 'all',
        'url': f'https://leetcode.com/problems/{slug}',
    }

# Sort by frequency desc
questions = sorted(
    seen_slugs.values(),
    key=lambda q: (-q['frequency'], q['id'] if q['id'] else 99999)
)

# Collect all unique topics
all_topics = set()
for q in questions:
    for t in q['topics']:
        all_topics.add(t)
sorted_topics = sorted(all_topics)

print(f"Total unique questions: {len(questions)}")
print(f"Unique topics: {len(sorted_topics)}")
diff_counts = {}
for q in questions:
    diff_counts[q['difficulty']] = diff_counts.get(q['difficulty'], 0) + 1
print(f"Difficulty distribution: {diff_counts}")
timeframe_counts = {}
for q in questions:
    t = q.get('timeframe', '')
    timeframe_counts[t] = timeframe_counts.get(t, 0) + 1
print(f"Timeframe distribution: {timeframe_counts}")

out_path = os.path.join(BASE, 'questions.js')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('// Auto-generated by generate_data.py\n')
    f.write(f'const QUESTIONS = {json.dumps(questions, ensure_ascii=False, indent=2)};\n\n')
    f.write(f'const ALL_TOPICS = {json.dumps(sorted_topics, ensure_ascii=False, indent=2)};\n')

print(f"\nWritten to {out_path}")
