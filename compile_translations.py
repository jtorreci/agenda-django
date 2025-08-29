#!/usr/bin/env python
"""
Script to compile Django translations from .po to .mo files
Run this script after updating translations in the .po files
"""

import os
import sys

if __name__ == '__main__':
    # Set Django settings module
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agenda_academica.settings')
    
    print("Compiling translation messages...")
    
    try:
        # Use Django's management command directly
        from django.core.management import execute_from_command_line
        
        # Execute compilemessages command
        execute_from_command_line(['manage.py', 'compilemessages', '--verbosity=2'])
        
        print("\n✅ Translation messages compiled successfully!")
        print("📁 Generated files:")
        
        # List generated .mo files
        locale_dir = os.path.join(os.getcwd(), 'locale')
        if os.path.exists(locale_dir):
            for root, dirs, files in os.walk(locale_dir):
                for file in files:
                    if file.endswith('.mo'):
                        filepath = os.path.join(root, file)
                        print(f"   📄 {filepath}")
        
        print("\n🚀 Your Django application is now ready to use Spanish translations!")
        print("💡 Tip: Restart your Django development server to see the changes.")
        
    except Exception as e:
        print(f"❌ Error compiling messages: {e}")
        print("\n💡 Try running this command directly instead:")
        print("   python manage.py compilemessages")
        sys.exit(1)