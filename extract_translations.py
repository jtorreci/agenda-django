#!/usr/bin/env python
"""
Script to extract translatable strings from Django project and update .po files
Run this script whenever you add new translatable strings to your code
"""

import os
import sys
import django
from django.core.management import execute_from_command_line
from django.core.management.commands.makemessages import Command as MakeMessagesCommand

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
    django.setup()
    
    print("Extracting translatable strings...")
    print("🔍 Scanning Python files (.py) and templates (.html)...")
    
    # Extract messages for Spanish using execute_from_command_line
    execute_from_command_line([
        'manage.py', 
        'makemessages', 
        '-l', 'es',
        '--verbosity=2',
        '-e', 'html,py'
    ])
    
    print("\n✅ Translatable strings extracted successfully!")
    print("📁 Updated file: locale/es/LC_MESSAGES/django.po")
    print("\n📝 Next steps:")
    print("1. Edit locale/es/LC_MESSAGES/django.po to add Spanish translations")
    print("2. Run: python compile_translations.py")
    print("3. Restart your Django development server")
    
    # Show stats about translations
    po_file = os.path.join('locale', 'es', 'LC_MESSAGES', 'django.po')
    if os.path.exists(po_file):
        with open(po_file, 'r', encoding='utf-8') as f:
            content = f.read()
            msgid_count = content.count('msgid "')
            msgstr_count = content.count('msgstr ""')
            translated_count = msgid_count - msgstr_count
            
        print(f"\n📊 Translation statistics:")
        print(f"   🔤 Total strings: {msgid_count}")
        print(f"   ✅ Translated: {translated_count}")
        print(f"   ❌ Untranslated: {msgstr_count}")
        print(f"   📈 Progress: {(translated_count/msgid_count*100):.1f}%")