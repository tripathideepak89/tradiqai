"""Setup script for AutoTrade AI"""
import os
import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(text)
    print("="*60 + "\n")


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"⏳ {description}...")
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ {description} - Done")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed")
        print(f"Error: {e.stderr}")
        return False


def check_python_version():
    """Check if Python version is compatible"""
    print_header("Checking Python Version")
    
    version = sys.version_info
    if version.major == 3 and version.minor >= 11:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Requires Python 3.11+")
        return False


def create_env_file():
    """Create .env file from template"""
    print_header("Setting Up Environment Configuration")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if env_file.exists():
        print("⚠️  .env file already exists")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Skipping .env creation")
            return True
    
    if env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
        print("\n⚠️  IMPORTANT: Edit .env file with your credentials!")
        return True
    else:
        print("❌ .env.example not found")
        return False


def create_directories():
    """Create necessary directories"""
    print_header("Creating Directories")
    
    directories = ['logs', 'data', 'backtest_results']
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created {directory}/")
    
    return True


def install_dependencies():
    """Install Python dependencies"""
    print_header("Installing Dependencies")
    
    print("This may take a few minutes...")
    
    # Upgrade pip
    if not run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Upgrading pip"
    ):
        return False
    
    # Install requirements
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing Python packages"
    ):
        return False
    
    return True


def setup_database():
    """Initialize database"""
    print_header("Database Setup")
    
    print("⚠️  Make sure PostgreSQL and Redis are running!")
    response = input("Continue with database setup? (y/N): ")
    
    if response.lower() != 'y':
        print("Skipping database setup")
        return True
    
    try:
        from database import init_db
        init_db()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("\nℹ️  You can initialize it later by running:")
        print("   python -c \"from database import init_db; init_db()\"")
        return False


def print_next_steps():
    """Print next steps"""
    print_header("Setup Complete! 🎉")
    
    print("Next Steps:")
    print("\n1. Edit .env file with your credentials:")
    print("   - Zerodha API keys")
    print("   - Database URLs")
    print("   - Telegram bot token")
    
    print("\n2. Start PostgreSQL and Redis:")
    print("   docker-compose up -d postgres redis")
    
    print("\n3. Initialize database (if not done):")
    print("   python -c \"from database import init_db; init_db()\"")
    
    print("\n4. Test the system:")
    print("   python cli.py status")
    
    print("\n5. Start trading system:")
    print("   python main.py")
    
    print("\n6. Or start API server:")
    print("   python api.py")
    
    print("\n⚠️  IMPORTANT:")
    print("   - Keep PAPER_TRADING=true until you're confident")
    print("   - Start with small capital")
    print("   - Test thoroughly before going live")
    
    print("\n📚 Read README.md for detailed documentation")
    print("\n" + "="*60 + "\n")


def main():
    """Main setup function"""
    print_header("AutoTrade AI - Setup Script")
    print("This script will help you set up the trading system.")
    
    # Check Python version
    if not check_python_version():
        print("\n❌ Setup failed: Incompatible Python version")
        sys.exit(1)
    
    # Create directories
    if not create_directories():
        print("\n❌ Setup failed: Could not create directories")
        sys.exit(1)
    
    # Create .env file
    if not create_env_file():
        print("\n❌ Setup failed: Could not create .env file")
        sys.exit(1)
    
    # Install dependencies
    response = input("\nInstall Python dependencies? (y/N): ")
    if response.lower() == 'y':
        if not install_dependencies():
            print("\n❌ Setup failed: Could not install dependencies")
            sys.exit(1)
    else:
        print("⏭️  Skipping dependency installation")
    
    # Setup database
    setup_database()
    
    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed with error: {e}")
        sys.exit(1)
