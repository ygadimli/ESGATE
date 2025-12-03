#!/usr/bin/env python3
"""
Script to delete user data for huseynbabaproya and aytac accounts
"""
import sqlite3
import sys

def delete_user_data():
    usernames_to_delete = ['huseynbabapro', 'Aytac']
    
    # Connect to users database
    user_conn = sqlite3.connect('users.db')
    user_cursor = user_conn.cursor()
    
    # Connect to data database
    data_conn = sqlite3.connect('data.db')
    data_cursor = data_conn.cursor()
    
    deleted_count = 0
    
    for username in usernames_to_delete:
        print(f"\n🔍 Searching for user: {username}")
        
        # Get user_id from users.db
        user_cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        result = user_cursor.fetchone()
        
        if not result:
            print(f"   ❌ User '{username}' not found in users.db")
            continue
        
        user_id = result[0]
        print(f"   ✅ Found user_id: {user_id}")
        
        # Delete from all tables in data.db
        tables_to_clean = [
            'predictions',
            'company_data',
            'kids_expenses',
            'kids_goals',
            'kids_progress',
            'kids_badges',
            'kids_lessons',
            'kids_tasks',
            'chat_history',
            'business_simulator',
            'talent_tasks'
        ]
        
        for table in tables_to_clean:
            try:
                data_cursor.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
                count = data_cursor.rowcount
                if count > 0:
                    print(f"   🗑️  Deleted {count} row(s) from {table}")
            except sqlite3.OperationalError as e:
                if "no such table" not in str(e).lower():
                    print(f"   ⚠️  Error deleting from {table}: {e}")
        
        # Delete from users.db
        user_cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        if user_cursor.rowcount > 0:
            print(f"   🗑️  Deleted user '{username}' from users.db")
            deleted_count += 1
    
    # Commit changes
    user_conn.commit()
    data_conn.commit()
    
    # Close connections
    user_conn.close()
    data_conn.close()
    
    print(f"\n✅ Deletion complete! Deleted {deleted_count} user(s).")

if __name__ == '__main__':
    print("🚀 Starting user data deletion...")
    try:
        delete_user_data()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

