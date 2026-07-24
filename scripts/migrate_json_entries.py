#!/usr/bin/env python3
"""
M1.2 - Migrate existing JSON entries to new Storage system

Converts all JSON files in entries/ folder to SQLite + ChromaDB using Storage class.
Preserves all data: content, categories, tags, file paths, timestamps.

Usage: python migrate_json_entries.py
"""

import json
from pathlib import Path

from src.storage.storage import Storage


def convert_timestamp(old_timestamp: str) -> str:
    """
    Convert old timestamp format to ISO 8601 with Z suffix.
    
    Old: "2025-11-13T18:42:35.446119" 
    New: "2025-11-13T18:42:35.446119Z"
    """
    if old_timestamp.endswith('Z'):
        return old_timestamp
    return old_timestamp + 'Z'


def clean_tags(tags_list):
    """
    Clean up tags by removing # prefix if present.
    
    Old: ["#interstitial", "#journal"]
    New: ["interstitial", "journal"]
    """
    if not tags_list:
        return []
    return [tag.lstrip('#') for tag in tags_list]


def migrate_entry(entry_data: dict, storage: Storage) -> dict:
    """
    Convert old JSON entry to new Storage format and save.

    Field mapping:
    - text:         context → content,     description = null
    - voice/image:  context → description, content = null (filled later by speech-to-text/OCR)

    Returns: dict with migration info
    """
    old_id = entry_data.get('id')
    entry_type = entry_data.get('type', 'text')
    old_context = entry_data.get('context', '')

    if entry_type == 'text':
        content = old_context
        description = None
    else:
        # voice / image: user-typed context goes to description, content filled later
        content = None
        description = old_context if old_context else None

    new_entry = {
        'id': old_id,
        'content': content,
        'description': description,
        'content_type': entry_type,
        'category': entry_data.get('category'),
        'tags': clean_tags(entry_data.get('tags')),
        'file_path': entry_data.get('file_path'),
    }
    
    # Convert and set timestamp in save() call manually to preserve original time
    old_timestamp = entry_data.get('timestamp', '')
    iso_timestamp = convert_timestamp(old_timestamp)
    
    # Save via Storage (but we need to override the timestamp)
    # Since Storage.save() auto-generates timestamps, we'll need to update after
    try:
        saved_id = storage.save(new_entry)
        
        # Update the created_at timestamp to preserve original
        if iso_timestamp:
            storage.update(saved_id, {'created_at': iso_timestamp})
        
        return {
            'status': 'success',
            'old_id': old_id,
            'new_id': saved_id,
            'type': new_entry['content_type'],
            'has_category': bool(new_entry['category']),
            'has_tags': bool(new_entry['tags']),
            'has_file': bool(new_entry['file_path']),
            'original_timestamp': old_timestamp,
            'converted_timestamp': iso_timestamp
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'old_id': old_id,
            'error': str(e),
            'entry_data': new_entry
        }


def main():
    print("🚀 Starting M1.2 - JSON Entry Migration")
    print("=" * 50)
    
    # Initialize Storage
    print("📦 Initializing Storage...")
    storage = Storage()
    
    # Find all JSON files
    entries_dir = Path("entries")
    json_files = list(entries_dir.glob("*.json"))
    
    print(f"📁 Found {len(json_files)} JSON files to migrate")
    print()
    
    # Migration statistics
    stats = {
        'total': len(json_files),
        'success': 0,
        'error': 0,
        'by_type': {'text': 0, 'voice': 0, 'image': 0},
        'with_category': 0,
        'with_tags': 0,
        'with_files': 0,
        'errors': []
    }
    
    # Process each JSON file
    for i, json_file in enumerate(json_files, 1):
        print(f"[{i:3d}/{len(json_files)}] Processing {json_file.name}...", end=' ')
        
        try:
            # Load JSON data
            with open(json_file, 'r') as f:
                entry_data = json.load(f)
            
            # Migrate entry
            result = migrate_entry(entry_data, storage)
            
            if result['status'] == 'success':
                stats['success'] += 1
                stats['by_type'][result['type']] += 1
                if result['has_category']:
                    stats['with_category'] += 1
                if result['has_tags']:
                    stats['with_tags'] += 1
                if result['has_file']:
                    stats['with_files'] += 1
                print(f"✅ {result['type']}")
            else:
                stats['error'] += 1
                stats['errors'].append(result)
                print(f"❌ ERROR: {result['error']}")
                
        except Exception as e:
            stats['error'] += 1
            stats['errors'].append({
                'status': 'error',
                'old_id': json_file.name,
                'error': f"Failed to load JSON: {e}"
            })
            print(f"❌ JSON ERROR: {e}")
    
    print()
    print("📊 Migration Summary")
    print("=" * 50)
    print(f"Total entries: {stats['total']}")
    print(f"✅ Successful: {stats['success']}")
    print(f"❌ Errors: {stats['error']}")
    print()
    print("By content type:")
    for content_type, count in stats['by_type'].items():
        print(f"  {content_type}: {count}")
    print()
    print(f"Entries with categories: {stats['with_category']}")
    print(f"Entries with tags: {stats['with_tags']}")
    print(f"Entries with files: {stats['with_files']}")
    
    # Show errors if any
    if stats['errors']:
        print()
        print("❌ Errors encountered:")
        for i, error in enumerate(stats['errors'][:5], 1):  # Show first 5 errors
            print(f"  {i}. {error['old_id']}: {error['error']}")
        if len(stats['errors']) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")
    
    print()
    
    # Verification
    if stats['success'] > 0:
        print("🔍 Quick verification...")
        recent_entries = storage.get_recent(limit=5)
        print(f"✅ Can retrieve {len(recent_entries)} recent entries from new Storage")
        
        # Check categories
        categories = storage.get_categories()
        print(f"✅ Available categories: {categories}")
        
        # Check search works
        if recent_entries:
            search_results = storage.search("journal", limit=3)
            print(f"✅ Search works: found {len(search_results)} results for 'journal'")
    
    print()
    if stats['error'] == 0:
        print("🎉 Migration completed successfully!")
        print("🗂️  All your existing notes are now in the new Storage system.")
        print("🚀 Ready for M1.3 - Refactor Streamlit UI!")
    else:
        print(f"⚠️  Migration completed with {stats['error']} errors.")
        print("🔧 Check the errors above and re-run if needed.")


if __name__ == "__main__":
    main()