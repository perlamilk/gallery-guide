#!/usr/bin/env python3
"""Merge a verified metadata batch without deleting previously collected works.

Usage: python3 tools/merge-artworks.py path/to/batch.json
Copy any referenced image files into the app before running. Review the diff
and bump sw.js VERSION before publishing. Partial batches never remove works.
"""
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'data/artworks.json'

def merge(existing, batch):
    records = existing['artworks']
    updates = batch['artworks']
    for group in (records, updates):
        ids = [str(a['id']) for a in group]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate artwork IDs')
    by_id = {str(a['id']): dict(a) for a in records}
    for update in updates:
        if not str(update.get('title', '')).strip():
            raise ValueError('Every update needs a title')
        key = str(update['id'])
        old = by_id.get(key, {})
        # Missing/blank values in a partial extraction are not deletion signals.
        fresh = {k: v for k, v in update.items() if v is not None and v != ''}
        by_id[key] = {**old, **fresh, 'id': key}
        if fresh.get('image'):
            by_id[key].pop('img', None)
    result = {**existing, 'artworks': list(by_id.values()), 'count': len(by_id)}
    result['lastBatchChecked'] = batch.get('checked')
    result['complete'] = False
    return result

if __name__ == '__main__':
    existing = json.loads(target.read_text())
    batch = json.loads(Path(sys.argv[1]).read_text())
    result = merge(existing, batch)
    for a in batch['artworks']:
        if a.get('image'):
            p = (root / a['image']).resolve()
            if not p.is_relative_to(root) or not p.is_file():
                raise ValueError(f'Missing or unsafe image path: {a["image"]}')
    temporary = target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    os.replace(temporary, target)
    print(f'{len(existing["artworks"])} → {result["count"]} works; merged {len(batch["artworks"])} verified records')
