"""
Fetch Supabase project credentials using Management API
"""
import requests
import json

# Your Supabase credentials
USERNAME = "tripathideepak89"
ACCESS_TOKEN = "sbp_94bbdafe8df09ba99e8f7666d928ca33672e5aef"
PROJECT_REF = "lmpajbaylwrlqtcqmwoo"

def fetch_project_credentials():
    """Fetch project API keys and database password"""
    
    print("🔍 Fetching Supabase project credentials...")
    print(f"📍 Project: {PROJECT_REF}")
    print()
    
    # Supabase Management API base URL
    base_url = "https://api.supabase.com/v1"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Get project details
    print("📡 Fetching project details...")
    try:
        response = requests.get(
            f"{base_url}/projects/{PROJECT_REF}",
            headers=headers
        )
        
        if response.status_code == 200:
            project = response.json()
            print(f"✅ Project found: {project.get('name', 'N/A')}")
            print(f"   Region: {project.get('region', 'N/A')}")
            print(f"   Status: {project.get('status', 'N/A')}")
        else:
            print(f"❌ Failed to fetch project: {response.status_code}")
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print()
    
    # Get API keys
    print("🔑 Fetching API keys...")
    try:
        response = requests.get(
            f"{base_url}/projects/{PROJECT_REF}/api-keys",
            headers=headers
        )
        
        if response.status_code == 200:
            api_keys = response.json()
            
            anon_key = None
            service_key = None
            
            for key in api_keys:
                if key.get('name') == 'anon':
                    anon_key = key.get('api_key')
                    print(f"✅ Anon Key: {anon_key[:50]}...")
                elif key.get('name') == 'service_role':
                    service_key = key.get('api_key')
                    print(f"✅ Service Key: {service_key[:50]}...")
            
            if not anon_key or not service_key:
                print("⚠️  Could not find all required keys")
                print(f"   Keys found: {[k.get('name') for k in api_keys]}")
        else:
            print(f"❌ Failed to fetch API keys: {response.status_code}")
            print(f"   Response: {response.text}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    print()
    
    # Get database config
    print("🗄️  Fetching database configuration...")
    try:
        response = requests.get(
            f"{base_url}/projects/{PROJECT_REF}/config/database/postgres",
            headers=headers
        )
        
        if response.status_code == 200:
            db_config = response.json()
            print(f"✅ Database host: {db_config.get('host', 'N/A')}")
            print(f"   Database port: {db_config.get('port', 5432)}")
        else:
            print(f"⚠️  Could not fetch database config: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Error fetching database config: {e}")
    
    print()
    print("=" * 70)
    print("📋 Your Supabase Credentials")
    print("=" * 70)
    print()
    print("Add these to your .env file:")
    print()
    print(f"SUPABASE_URL=https://{PROJECT_REF}.supabase.co")
    if anon_key:
        print(f"SUPABASE_ANON_KEY={anon_key}")
    if service_key:
        print(f"SUPABASE_SERVICE_KEY={service_key}")
    print()
    print("⚠️  NOTE: Database password cannot be retrieved via API")
    print("   You need to get it from Supabase Dashboard:")
    print(f"   → https://supabase.com/dashboard/project/{PROJECT_REF}/settings/database")
    print("   Or reset it if you forgot it")
    print()
    print("=" * 70)
    
    # Save to .env file
    print()
    response = input("💾 Would you like to update .env file automatically? (y/n): ")
    
    if response.lower() == 'y':
        update_env_file(PROJECT_REF, anon_key, service_key)
    else:
        print("👍 Please update .env file manually with the credentials above")

def update_env_file(project_ref, anon_key, service_key):
    """Update .env file with Supabase credentials"""
    try:
        # Read current .env
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        # Update lines
        updated_lines = []
        for line in lines:
            if line.startswith('SUPABASE_URL='):
                updated_lines.append(f"SUPABASE_URL=https://{project_ref}.supabase.co\n")
            elif line.startswith('SUPABASE_ANON_KEY=') and anon_key:
                updated_lines.append(f"SUPABASE_ANON_KEY={anon_key}\n")
            elif line.startswith('SUPABASE_SERVICE_KEY=') and service_key:
                updated_lines.append(f"SUPABASE_SERVICE_KEY={service_key}\n")
            else:
                updated_lines.append(line)
        
        # Write updated .env
        with open('.env', 'w') as f:
            f.writelines(updated_lines)
        
        print("✅ .env file updated successfully!")
        print()
        print("⚠️  IMPORTANT: You still need to add SUPABASE_DB_PASSWORD manually")
        print("   Get it from: https://supabase.com/dashboard/project/{project_ref}/settings/database")
        
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")

if __name__ == "__main__":
    fetch_project_credentials()
